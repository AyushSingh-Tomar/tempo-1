"""Step 4-5 orchestration: generate candidates, approve/reject/reopen/manual
override, and finalize the mapping set.

Resolution order: **exact dictionary term -> fuzzy**. A source header that is a
term of the (default or user-supplied) data dictionary scores 100%. Anything
unrecognised is never dropped: it is tagged ``extra_<header>`` and auto-approved
as pass-through (non-blocking, still visible in the review). Numeric
pass-through columns are later examined by the arithmetic relationship check in
financial checks (after treaty figures exist) - not here.

Reject workflow: rejecting a candidate frees its source column. If no other
candidate for the column is still open, the column falls back to an
``extra_`` pass-through (so no column is ever left undecided) and can be
re-mapped manually or the rejection reopened.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.credentials import resolve_llm_service
from bordereaux.ai.interactions import AI_SKIPPED, record_interaction, serialize_interaction
from bordereaux.ai.service import AI_DISABLED, build_llm_service
from bordereaux.audit.service import AuditService
from bordereaux.cleaning.service import get_latest_cleaning_result, cleaned_dataset_path
from bordereaux.core.exceptions import BusinessRuleError, NotFoundError, StateError
from bordereaux.core.models import (
    ActorType,
    AuditAction,
    MappingCandidateStatus,
    MappingOrigin,
    MappingSetStatus,
    ProcessingRunStatus,
    ResolutionStage,
)
from bordereaux.core.utils import model_snapshot, to_jsonable
from bordereaux.mapping import ai_assist
from bordereaux.mapping.aliasing import CanonicalFieldDef, build_field_index, exact_matches, fuzzy_match, is_primary_name
from bordereaux.mapping.scoring import (
    EXACT_DICTIONARY_CONFIDENCE,
    ScoredCandidate,
    calculate_confidence,
    confidence_total_decimal,
    exact_dictionary_breakdown,
)
from bordereaux.mapping.target_format import effective_fields
from bordereaux.models.asset import SourceVersion
from bordereaux.models.mapping import ApprovedMapping, MappingCandidate, MappingSet
from bordereaux.models.profile import ColumnProfile, DataProfile
from bordereaux.models.run import ProcessingRun
from bordereaux.profiling.profiler import profile_dataset
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.schemas.loader import seed_canonical_schema
from bordereaux.storage.service import StorageService

FUZZY_THRESHOLD = 0.90
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("_", text.strip().lower()).strip("_") or "column"


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


async def _load_latest_cleaned_dataset(db: AsyncSession, storage: StorageService, run_id: UUID) -> dict[str, Any]:
    latest = await get_latest_cleaning_result(db, run_id)
    raw = await storage.download(cleaned_dataset_path(run_id, latest.attempt_number))
    return json.loads(raw)


def _value_type_score(column_type: str, field: CanonicalFieldDef) -> float:
    numeric_types = {"INTEGER", "DECIMAL"}
    if column_type in numeric_types and field.type in numeric_types:
        return 1.0
    if column_type == field.type:
        return 1.0
    if column_type == "DATE" and field.type == "DATE":
        return 1.0
    if column_type == "STRING" and field.type in ("STRING", "ENUM", "COUNTRY_CODE", "CURRENCY_CODE"):
        return 0.8
    if column_type == "UNKNOWN":
        return 0.5
    return 0.3


@dataclass
class _GenerationContext:
    columns: list[str]
    rows: list[dict[str, Any]]
    column_profiles: dict[str, ColumnProfile]
    fields: list[CanonicalFieldDef]


def _numeric_hint(prof: ColumnProfile | None) -> bool:
    return prof is not None and prof.data_type in ("INTEGER", "DECIMAL")


async def generate_mapping_candidates(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID, use_ai: bool = True
) -> MappingSet:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.MAPPING_REVIEW_PENDING.value:
        raise StateError(
            f"Run must be MAPPING_REVIEW_PENDING to generate mappings (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    if run.source_version_id is None:
        raise StateError("Run has no parsed version to map")

    # Stored snapshot of the dictionary version in use (lineage); also populates MONEY_ROLE_BY_FIELD.
    schema_row = await seed_canonical_schema(db)
    # Treaty-figure fields are user-entered at Step 6, never column-mapped, so
    # ``effective_fields`` (default dictionary or the user's custom format)
    # never contains them.
    fields = build_field_index({"fields": effective_fields(run)})

    dataset = await _load_latest_cleaned_dataset(db, storage, run_id)
    columns: list[str] = dataset["columns"]
    rows: list[dict[str, Any]] = sorted(dataset["rows"], key=lambda r: r["row_number"])

    profile = await profile_dataset(db, run.source_version_id, columns, rows)
    profiles = (
        await db.execute(select(ColumnProfile).where(ColumnProfile.profile_id == profile.id))
    ).scalars().all()
    column_profiles = {p.name: p for p in profiles}

    # Supersede any prior draft mapping set for this version.
    await db.execute(
        update(MappingSet)
        .where(MappingSet.version_id == run.source_version_id, MappingSet.status == MappingSetStatus.DRAFT.value)
        .values(status=MappingSetStatus.SUPERSEDED.value)
    )

    mapping_set = MappingSet(version_id=run.source_version_id, schema_id=schema_row.id)
    db.add(mapping_set)
    await db.flush()

    # --- Stage 1 (exact dictionary term) and Stage 2 (fuzzy) ----------------
    # hit = (column, field, stage, score, ambiguous_alias_field_names)
    stage12_hits: dict[str, list[tuple[str, CanonicalFieldDef, str, float, list[str]]]] = {}
    passthrough: list[tuple[str, str]] = []  # (column, reason)
    ambiguous_alternatives: list[tuple[str, CanonicalFieldDef, list[str]]] = []

    for col in columns:
        prof = column_profiles.get(col)
        col_type = prof.data_type if prof else "UNKNOWN"
        matches = exact_matches(col, fields)
        if matches:
            primary = [m for m in matches if is_primary_name(col, m)]
            if len(matches) == 1 or len(primary) == 1:
                chosen = primary[0] if len(primary) == 1 else matches[0]
                stage12_hits.setdefault(chosen.name, []).append((col, chosen, ResolutionStage.EXACT.value, 1.0, []))
            else:
                # The header is a dictionary term of several fields ("Line",
                # "Category"...): the best value-type fit leads, the rest are
                # offered as alternatives - never a silent 100%.
                ranked = sorted(matches, key=lambda f: _value_type_score(col_type, f), reverse=True)
                names = [f.name for f in ranked]
                stage12_hits.setdefault(ranked[0].name, []).append(
                    (col, ranked[0], ResolutionStage.EXACT.value, 0.8, names)
                )
                for alt in ranked[1:]:
                    ambiguous_alternatives.append((col, alt, names))
            continue
        fuzzy = fuzzy_match(col, fields, FUZZY_THRESHOLD)
        if fuzzy is not None:
            field, score = fuzzy
            stage12_hits.setdefault(field.name, []).append((col, field, ResolutionStage.FUZZY.value, score, []))
            continue
        reason = "numeric_no_dictionary_match" if _numeric_hint(prof) else "no_canonical_match"
        passthrough.append((col, reason))

    stage_rank = {ResolutionStage.EXACT.value: 2, ResolutionStage.FUZZY.value: 1}
    scored: list[ScoredCandidate] = []

    for field_name, hits in stage12_hits.items():
        hits_sorted = sorted(hits, key=lambda h: (stage_rank[h[2]], h[3], -columns.index(h[0])), reverse=True)
        winner = hits_sorted[0]
        is_conflict = len(hits_sorted) > 1
        for col, field, stage, score, alt_names in hits_sorted:
            prof = column_profiles.get(col)
            value_score = _value_type_score(prof.data_type if prof else "UNKNOWN", field)
            ambiguous_alias = bool(alt_names)
            if stage == ResolutionStage.EXACT.value and not is_conflict and not ambiguous_alias:
                # Dictionary term -> its dictionary field: certain.
                breakdown = exact_dictionary_breakdown()
                total = EXACT_DICTIONARY_CONFIDENCE
            else:
                breakdown = {"semantic": score, "value": value_score, "context": score, "layout": 0.5, "ai": 0.5}
                total = calculate_confidence(breakdown)
            evidence: list[dict[str, Any]] = [{"type": "alias_match", "stage": stage, "score": score}]
            if is_conflict:
                evidence.append({"type": "duplicate_target_conflict", "winner": col == winner[0]})
            if ambiguous_alias:
                evidence.append({"type": "ambiguous_alias", "candidate_fields": alt_names})
            scored.append(
                ScoredCandidate(
                    source_column=col,
                    target_field=field.name,
                    stage=stage,
                    breakdown=breakdown,
                    total=total,
                    evidence=evidence,
                    is_ambiguous=(is_conflict and col != winner[0]) or ambiguous_alias,
                )
            )

    for col, alt, names in ambiguous_alternatives:
        prof = column_profiles.get(col)
        value_score = _value_type_score(prof.data_type if prof else "UNKNOWN", alt)
        breakdown = {"semantic": 0.8, "value": value_score, "context": 0.8, "layout": 0.5, "ai": 0.5}
        scored.append(
            ScoredCandidate(
                source_column=col,
                target_field=alt.name,
                stage=ResolutionStage.EXACT.value,
                breakdown=breakdown,
                total=calculate_confidence(breakdown),
                evidence=[
                    {"type": "alias_match", "stage": ResolutionStage.EXACT.value, "score": 0.8},
                    {"type": "ambiguous_alias", "candidate_fields": names},
                ],
                is_ambiguous=True,
            )
        )

    # --- Persist candidates -------------------------------------------------
    for sc in scored:
        db.add(
            MappingCandidate(
                mapping_set_id=mapping_set.id,
                source_column=sc.source_column,
                target_field=sc.target_field,
                confidence_total=confidence_total_decimal(sc.total),
                confidence_breakdown=to_jsonable(sc.breakdown),
                evidence=to_jsonable([e for e in sc.evidence if e]),
                status=MappingCandidateStatus.PROPOSED.value,
                auto_approve_eligible=sc.auto_approve_eligible,
            )
        )
    await db.flush()

    for col, reason in passthrough:
        await _add_passthrough(db, mapping_set.id, col, actor_id, {"type": "passthrough", "reason": reason})

    await db.flush()
    await AuditService(db).log(
        event_type="mapping.candidates_generated",
        target_type="MappingSet",
        target_id=mapping_set.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state={
            "candidates": len(scored) + len(passthrough),
            "passthrough_count": len(passthrough),
            "target_format": (run.target_format or {}).get("mode", "DEFAULT"),
            "exact_matches": sum(1 for sc in scored if sc.total >= EXACT_DICTIONARY_CONFIDENCE),
        },
        project_id=run.project_id,
    )
    # The deterministic mapping is final and safe on its own: persist it *before* the (slow,
    # fallible) AI call so no write lock is held while waiting and nothing is lost if AI fails.
    await db.commit()

    await run_mapping_ai(
        db, run, mapping_set, actor_id, columns=columns, rows=rows, column_profiles=column_profiles, use_ai=use_ai
    )
    return mapping_set


_AI_REASONS_UNRESOLVED = {"numeric_no_dictionary_match", "no_canonical_match"}


def _columns_needing_ai(
    candidates: list[MappingCandidate], approved: list[ApprovedMapping], columns: list[str]
) -> list[ai_assist.ColumnToResolve]:
    """Columns the deterministic stage could not settle and nobody has decided yet."""
    approved_by_col = {a.source_column: a for a in approved}
    by_col: dict[str, list[MappingCandidate]] = {}
    for c in candidates:
        by_col.setdefault(c.source_column, []).append(c)
    out: list[ai_assist.ColumnToResolve] = []
    for col in columns:
        cands = by_col.get(col, [])
        if not cands:
            continue
        evidence = [e for c in cands for e in (c.evidence or []) if isinstance(e, dict)]
        if any(e.get("type") in ("ai_suggestion", "ai_note") for e in evidence):
            continue  # AI already answered for this column
        existing = approved_by_col.get(col)
        if existing is not None and not (
            existing.origin == MappingOrigin.AUTO_APPROVED.value and existing.target_field.startswith("extra_")
        ):
            continue  # a person (or a 100% dictionary match) decided
        open_proposals = [c for c in cands if c.status == MappingCandidateStatus.PROPOSED.value]
        ambiguity = {
            e.get("type")
            for c in open_proposals
            for e in (c.evidence or [])
            if isinstance(e, dict) and e.get("type") in ("ambiguous_alias", "duplicate_target_conflict")
        }
        if ambiguity:
            out.append(
                ai_assist.ColumnToResolve(
                    col,
                    "ambiguous_alias" if "ambiguous_alias" in ambiguity else "duplicate_target_conflict",
                    [
                        {"target_field": c.target_field, "score": float(c.confidence_total)}
                        for c in sorted(open_proposals, key=lambda c: c.confidence_total, reverse=True)
                    ],
                )
            )
            continue
        passthrough = [
            e
            for c in cands
            if c.target_field.startswith("extra_")
            for e in (c.evidence or [])
            if isinstance(e, dict) and e.get("type") == "passthrough"
        ]
        if passthrough and passthrough[0].get("reason") in _AI_REASONS_UNRESOLVED:
            out.append(ai_assist.ColumnToResolve(col, str(passthrough[0]["reason"])))
    return out


async def run_mapping_ai(
    db: AsyncSession,
    run: ProcessingRun,
    mapping_set: MappingSet,
    actor_id: UUID,
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    column_profiles: dict[str, ColumnProfile],
    use_ai: bool = True,
) -> dict[str, Any]:
    """Ask the model about the columns the deterministic stage could not settle.

    Never raises and never blocks the workflow: whatever happens is written to
    ``ai_interactions`` (so the UI can say what happened) and the deterministic mapping
    stays as it is. Successful answers become PROPOSED candidates for a reviewer."""

    async def finish(**kw: Any) -> dict[str, Any]:
        row = await record_interaction(db, run, purpose="MAPPING", actor_id=actor_id, **kw)
        await db.commit()
        return serialize_interaction(row)

    try:
        llm, _source = await resolve_llm_service(db, actor_id, build_llm_service)
        if not use_ai:
            return await finish(status=AI_SKIPPED, message="AI was turned off for this mapping run. Deterministic mapping only.")
        if not llm.is_available():
            return await finish(status=AI_DISABLED, message=llm.status()["reason"] or "AI is not configured.")

        candidates = list(
            (await db.execute(select(MappingCandidate).where(MappingCandidate.mapping_set_id == mapping_set.id)))
            .scalars()
            .all()
        )
        approved = await _approved_rows(db, mapping_set.id)
        to_resolve = _columns_needing_ai(candidates, approved, columns)
        if not to_resolve:
            return await finish(
                status=AI_SKIPPED,
                message="No ambiguous columns - the deterministic mapping settled everything, so AI was not needed.",
            )
        skipped_over_cap = max(0, len(to_resolve) - ai_assist.MAX_COLUMNS_PER_CALL)
        to_resolve = to_resolve[: ai_assist.MAX_COLUMNS_PER_CALL]

        target_fields = effective_fields(run)
        field_types = {f["name"]: f.get("type", "STRING") for f in target_fields}
        aliases_of = {f["name"]: list(f.get("aliases") or f.get("terms") or []) for f in target_fields}
        taken = {a.target_field for a in approved if not a.target_field.startswith("extra_")} | {
            c.target_field
            for c in candidates
            if c.status == MappingCandidateStatus.PROPOSED.value and c.confidence_total >= Decimal("1")
        }
        catalog, taken_names = ai_assist.build_field_catalog(target_fields, aliases_of, taken)
        column_types = {c: (column_profiles[c].data_type if c in column_profiles else "UNKNOWN") for c in columns}
        prompt = ai_assist.build_prompt(
            to_resolve,
            columns=columns,
            rows=rows[:200],
            column_profiles=column_profiles,
            catalog=catalog,
            taken=taken_names,
            target_format_mode=(run.target_format or {}).get("mode", "DEFAULT"),
        )
        outcome = await llm.ask_json(prompt, system=ai_assist.SYSTEM_PROMPT)
        if not outcome.ok:
            return await finish(outcome=outcome, items_sent=len(to_resolve))

        decisions, notes = ai_assist.parse_decisions(
            outcome.data,
            sent={c.column: c for c in to_resolve},
            field_types=field_types,
            column_types=column_types,
            taken=taken,
        )
        applied = await ai_assist.apply_decisions(
            db,
            mapping_set.id,
            decisions,
            column_types=column_types,
            field_types=field_types,
            model=outcome.model,
            provider=outcome.provider,
            actor_id=actor_id,
        )
        message = f"AI reviewed {len(to_resolve)} unresolved column(s) and suggested a field for {applied}."
        if applied == 0:
            message = (
                f"AI reviewed {len(to_resolve)} unresolved column(s) but found no confident match; "
                "they stay as pass-through columns."
            )
        if skipped_over_cap:
            message += f" {skipped_over_cap} further column(s) were not sent (limit {ai_assist.MAX_COLUMNS_PER_CALL})."
        if notes:
            message += f" {len(notes)} suggestion(s) were discarded by validation."
        return await finish(outcome=outcome, message=message, items_sent=len(to_resolve), items_resolved=applied)
    except Exception as exc:  # noqa: BLE001 - AI must never break mapping
        await db.rollback()
        await db.refresh(run)
        return await finish(
            status="error",
            message=f"AI step failed unexpectedly ({type(exc).__name__}); the deterministic mapping was kept.",
        )


async def retry_mapping_ai(db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID) -> dict[str, Any]:
    """Run the AI step again on the current draft mapping set (e.g. after a timeout)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    mapping_set = await _get_draft_or_latest_mapping_set(db, run)
    _assert_editable(mapping_set, run)

    dataset = await _load_latest_cleaned_dataset(db, storage, run_id)
    columns: list[str] = dataset["columns"]
    rows = sorted(dataset["rows"], key=lambda r: r["row_number"])
    profile = (
        await db.execute(
            select(DataProfile)
            .where(DataProfile.version_id == run.source_version_id)
            .order_by(DataProfile.profiled_at.desc())
        )
    ).scalars().first()
    profiles = (
        (await db.execute(select(ColumnProfile).where(ColumnProfile.profile_id == profile.id))).scalars().all()
        if profile is not None
        else []
    )
    return await run_mapping_ai(
        db, run, mapping_set, actor_id, columns=columns, rows=rows, column_profiles={p.name: p for p in profiles}
    )


async def _add_passthrough(
    db: AsyncSession, mapping_set_id: UUID, column: str, actor_id: UUID, evidence: dict[str, Any]
) -> MappingCandidate:
    """Record ``column`` as an ``extra_`` pass-through (candidate + approved mapping)."""
    candidate = MappingCandidate(
        mapping_set_id=mapping_set_id,
        source_column=column,
        target_field=f"extra_{_slug(column)}",
        confidence_total=Decimal("0"),
        confidence_breakdown={},
        evidence=to_jsonable([evidence]),
        status=MappingCandidateStatus.APPROVED.value,
        auto_approve_eligible=True,
    )
    db.add(candidate)
    await db.flush()
    db.add(
        ApprovedMapping(
            mapping_set_id=mapping_set_id,
            source_column=column,
            target_field=candidate.target_field,
            origin=MappingOrigin.AUTO_APPROVED.value,
            confidence_total=candidate.confidence_total,
            candidate_id=candidate.id,
            created_by=actor_id,
        )
    )
    await db.flush()
    return candidate


async def _get_draft_or_latest_mapping_set(db: AsyncSession, run: ProcessingRun) -> MappingSet:
    if run.mapping_set_id is not None:
        mapping_set = await db.get(MappingSet, run.mapping_set_id)
        if mapping_set is not None:
            return mapping_set
    stmt = (
        select(MappingSet)
        .where(MappingSet.version_id == run.source_version_id)
        .order_by(MappingSet.created_at.desc())
    )
    mapping_set = (await db.execute(stmt)).scalars().first()
    if mapping_set is None:
        raise NotFoundError("No mapping set has been generated for this run yet")
    return mapping_set


async def list_candidates(db: AsyncSession, run_id: UUID) -> list[MappingCandidate]:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    try:
        mapping_set = await _get_draft_or_latest_mapping_set(db, run)
    except NotFoundError:
        return []  # candidates are generated after the target format is chosen
    stmt = select(MappingCandidate).where(MappingCandidate.mapping_set_id == mapping_set.id)
    return list((await db.execute(stmt)).scalars().all())


async def _editable_context(db: AsyncSession, candidate: MappingCandidate) -> tuple[MappingSet, ProcessingRun | None]:
    """Mapping decisions can only change while the set is a DRAFT and the run is still in mapping review."""
    mapping_set = await db.get(MappingSet, candidate.mapping_set_id)
    version = await db.get(SourceVersion, mapping_set.version_id)
    run = None
    if version is not None:
        run = (
            await db.execute(select(ProcessingRun).where(ProcessingRun.source_version_id == version.id))
        ).scalars().first()
    _assert_editable(mapping_set, run)
    return mapping_set, run


def _assert_editable(mapping_set: MappingSet, run: ProcessingRun | None) -> None:
    if mapping_set.status != MappingSetStatus.DRAFT.value or (
        run is not None and run.status != ProcessingRunStatus.MAPPING_REVIEW_PENDING.value
    ):
        raise StateError("Mappings can only be changed while the run is in mapping review", code="MAPPING_LOCKED")


async def _approved_rows(db: AsyncSession, mapping_set_id: UUID) -> list[ApprovedMapping]:
    return list(
        (await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == mapping_set_id)))
        .scalars()
        .all()
    )


async def _column_candidates(db: AsyncSession, mapping_set_id: UUID, column: str) -> list[MappingCandidate]:
    return list(
        (
            await db.execute(
                select(MappingCandidate).where(
                    MappingCandidate.mapping_set_id == mapping_set_id, MappingCandidate.source_column == column
                )
            )
        )
        .scalars()
        .all()
    )


async def _release_column(db: AsyncSession, mapping_set_id: UUID, column: str) -> None:
    """Drop the column's current approved mapping so a new decision can be made.
    Candidates that were approved become SUPERSEDED (the audit log keeps the history)."""
    for a in await _approved_rows(db, mapping_set_id):
        if a.source_column != column:
            continue
        if a.candidate_id is not None:
            cand = await db.get(MappingCandidate, a.candidate_id)
            if cand is not None and cand.status == MappingCandidateStatus.APPROVED.value:
                cand.status = MappingCandidateStatus.SUPERSEDED.value
        await db.delete(a)
    await db.flush()


async def _assert_target_free(db: AsyncSession, mapping_set_id: UUID, column: str, target_field: str) -> None:
    if target_field.startswith("extra_"):
        return
    for a in await _approved_rows(db, mapping_set_id):
        if a.target_field == target_field and a.source_column != column:
            raise StateError(
                f"'{target_field}' is already mapped from source column '{a.source_column}'. "
                "Reject or re-map that column first.",
                code="DUPLICATE_TARGET_MAPPING",
                details={"target_field": target_field, "mapped_from": a.source_column},
            )


async def _approve(
    db: AsyncSession, candidate: MappingCandidate, mapping_set: MappingSet, run: ProcessingRun | None, actor_id: UUID
) -> ApprovedMapping:
    from bordereaux.core.utils import utcnow

    if candidate.status != MappingCandidateStatus.PROPOSED.value:
        raise StateError(f"Candidate is {candidate.status}, cannot approve", code="INVALID_CANDIDATE_STATE")
    await _assert_target_free(db, mapping_set.id, candidate.source_column, candidate.target_field)

    existing = [a for a in await _approved_rows(db, mapping_set.id) if a.source_column == candidate.source_column]
    if existing and not all(
        a.origin == MappingOrigin.AUTO_APPROVED.value and a.target_field.startswith("extra_") for a in existing
    ):
        raise StateError(
            f"Source column '{candidate.source_column}' already has an approved mapping",
            code="DUPLICATE_APPROVED_MAPPING",
        )
    # An auto pass-through (initial or reject fallback) gives way to the explicit approval.
    await _release_column(db, mapping_set.id, candidate.source_column)

    candidate.status = MappingCandidateStatus.APPROVED.value
    candidate.reviewed_by = actor_id
    candidate.reviewed_at = utcnow()
    for sibling in await _column_candidates(db, mapping_set.id, candidate.source_column):
        if sibling.id != candidate.id and sibling.status == MappingCandidateStatus.PROPOSED.value:
            sibling.status = MappingCandidateStatus.SUPERSEDED.value
    approved = ApprovedMapping(
        mapping_set_id=candidate.mapping_set_id,
        source_column=candidate.source_column,
        target_field=candidate.target_field,
        origin=MappingOrigin.APPROVED.value,
        confidence_total=candidate.confidence_total,
        candidate_id=candidate.id,
        created_by=actor_id,
    )
    db.add(approved)
    await db.flush()
    await AuditService(db).log(
        event_type="mapping.candidate_approved",
        target_type="MappingCandidate",
        target_id=candidate.id,
        action=AuditAction.APPROVE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(approved),
        project_id=run.project_id if run else None,
    )
    return approved


async def approve_candidate(db: AsyncSession, candidate_id: UUID, actor_id: UUID) -> ApprovedMapping:
    candidate = await db.get(MappingCandidate, candidate_id)
    if candidate is None:
        raise NotFoundError("Mapping candidate not found", details={"candidate_id": str(candidate_id)})
    mapping_set, run = await _editable_context(db, candidate)
    approved = await _approve(db, candidate, mapping_set, run, actor_id)
    await db.commit()
    return approved


async def approve_exact_matches(db: AsyncSession, run_id: UUID, actor_id: UUID) -> dict[str, Any]:
    """Approve every still-open candidate that is a 100% dictionary match.
    Ambiguous or conflicting matches score below 100% and are never included."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    mapping_set = await _get_draft_or_latest_mapping_set(db, run)
    _assert_editable(mapping_set, run)
    approved_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    for c in await list_candidates(db, run_id):
        if c.status != MappingCandidateStatus.PROPOSED.value or c.confidence_total < Decimal("1"):
            continue
        try:
            await _approve(db, c, mapping_set, run, actor_id)
            approved_ids.append(str(c.id))
        except StateError as exc:
            skipped.append({"source_column": c.source_column, "reason": exc.message})
    await db.commit()
    return {"approved": len(approved_ids), "candidate_ids": approved_ids, "skipped": skipped}


async def reject_candidate(db: AsyncSession, candidate_id: UUID, actor_id: UUID, reason: str) -> MappingCandidate:
    from bordereaux.core.utils import utcnow

    candidate = await db.get(MappingCandidate, candidate_id)
    if candidate is None:
        raise NotFoundError("Mapping candidate not found", details={"candidate_id": str(candidate_id)})
    if candidate.status not in (MappingCandidateStatus.PROPOSED.value, MappingCandidateStatus.APPROVED.value):
        raise StateError(f"Candidate is {candidate.status}, cannot reject", code="INVALID_CANDIDATE_STATE")
    if candidate.target_field.startswith("extra_"):
        raise StateError(
            "A pass-through column has no proposed mapping to reject; use 'Map manually' to assign it a field.",
            code="INVALID_CANDIDATE_STATE",
        )
    mapping_set, run = await _editable_context(db, candidate)

    was_approved = candidate.status == MappingCandidateStatus.APPROVED.value
    if was_approved:
        await _release_column(db, mapping_set.id, candidate.source_column)
    candidate.status = MappingCandidateStatus.REJECTED.value
    candidate.reviewed_by = actor_id
    candidate.review_comment = reason
    candidate.reviewed_at = utcnow()
    await db.flush()

    # Free the column: if nothing else is open for it, it becomes a pass-through
    # so it is never silently dropped and can still be re-mapped by hand.
    siblings = await _column_candidates(db, mapping_set.id, candidate.source_column)
    still_open = any(
        s.status in (MappingCandidateStatus.PROPOSED.value, MappingCandidateStatus.APPROVED.value) for s in siblings
    )
    fallback_target = None
    if not still_open:
        fb = await _add_passthrough(
            db,
            mapping_set.id,
            candidate.source_column,
            actor_id,
            {"type": "passthrough", "reason": "mapping_rejected", "rejected_target": candidate.target_field},
        )
        fallback_target = fb.target_field

    await AuditService(db).log(
        event_type="mapping.candidate_rejected",
        target_type="MappingCandidate",
        target_id=candidate.id,
        action=AuditAction.REJECT,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        reason=reason,
        after_state={"was_approved": was_approved, "fallback_target": fallback_target},
        project_id=run.project_id if run else None,
    )
    await db.commit()
    return candidate


async def reopen_candidate(db: AsyncSession, candidate_id: UUID, actor_id: UUID) -> MappingCandidate:
    """Undo a rejection: the candidate goes back to PROPOSED for a fresh decision."""
    candidate = await db.get(MappingCandidate, candidate_id)
    if candidate is None:
        raise NotFoundError("Mapping candidate not found", details={"candidate_id": str(candidate_id)})
    if candidate.status != MappingCandidateStatus.REJECTED.value:
        raise StateError(
            f"Candidate is {candidate.status}, only rejected candidates can be reopened",
            code="INVALID_CANDIDATE_STATE",
        )
    _mapping_set, run = await _editable_context(db, candidate)
    candidate.status = MappingCandidateStatus.PROPOSED.value
    candidate.reviewed_by = None
    candidate.reviewed_at = None
    candidate.review_comment = None
    await db.flush()
    await AuditService(db).log(
        event_type="mapping.candidate_reopened",
        target_type="MappingCandidate",
        target_id=candidate.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        project_id=run.project_id if run else None,
    )
    await db.commit()
    return candidate


async def create_manual_mapping(
    db: AsyncSession, run_id: UUID, source_column: str, target_field: str, actor_id: UUID
) -> ApprovedMapping:
    from bordereaux.core.utils import utcnow

    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    mapping_set = await _get_draft_or_latest_mapping_set(db, run)
    _assert_editable(mapping_set, run)

    valid_targets = {f["name"] for f in effective_fields(run)}
    if target_field not in valid_targets and not target_field.startswith("extra_"):
        raise BusinessRuleError(
            f"'{target_field}' is not a field of the selected target format",
            details={"target_field": target_field},
        )
    if not await _column_candidates(db, mapping_set.id, source_column):
        raise NotFoundError("Source column not found in this mapping set", details={"source_column": source_column})
    await _assert_target_free(db, mapping_set.id, source_column, target_field)

    # Manual mapping is the explicit human-override tool: it replaces whatever
    # decision the column had (approved, proposed or rejected-fallback).
    before = [model_snapshot(a) for a in await _approved_rows(db, mapping_set.id) if a.source_column == source_column]
    await _release_column(db, mapping_set.id, source_column)
    for c in await _column_candidates(db, mapping_set.id, source_column):
        if c.status == MappingCandidateStatus.PROPOSED.value:
            c.status = MappingCandidateStatus.SUPERSEDED.value

    candidate = MappingCandidate(
        mapping_set_id=mapping_set.id,
        source_column=source_column,
        target_field=target_field,
        confidence_total=Decimal("1.0000"),
        confidence_breakdown={},
        evidence=[{"type": "manual_override", "description": "Assigned by a reviewer"}],
        status=MappingCandidateStatus.APPROVED.value,
        auto_approve_eligible=False,
        reviewed_by=actor_id,
        reviewed_at=utcnow(),
    )
    db.add(candidate)
    await db.flush()
    approved = ApprovedMapping(
        mapping_set_id=mapping_set.id,
        source_column=source_column,
        target_field=target_field,
        origin=MappingOrigin.MANUAL.value,
        confidence_total=Decimal("1.0000"),
        candidate_id=candidate.id,
        created_by=actor_id,
    )
    db.add(approved)
    await db.flush()

    await AuditService(db).log(
        event_type="mapping.manual_override" if before else "mapping.manual_created",
        target_type="ApprovedMapping",
        target_id=approved.id,
        action=AuditAction.UPDATE if before else AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state={"previous": before} if before else None,
        after_state=model_snapshot(approved),
        project_id=run.project_id,
    )
    await db.commit()
    return approved


async def finalize_mappings(db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID) -> MappingSet:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.MAPPING_REVIEW_PENDING.value:
        raise StateError(
            f"Run must be MAPPING_REVIEW_PENDING to finalize mappings (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    mapping_set = await _get_draft_or_latest_mapping_set(db, run)

    approved_rows = await _approved_rows(db, mapping_set.id)
    approved_targets = {a.target_field for a in approved_rows}

    all_candidates = (
        await db.execute(select(MappingCandidate).where(MappingCandidate.mapping_set_id == mapping_set.id))
    ).scalars().all()
    open_statuses = (MappingCandidateStatus.PROPOSED.value, MappingCandidateStatus.APPROVED.value)
    candidate_targets = {c.target_field for c in all_candidates if c.status in open_statuses}

    missing = [
        f["name"]
        for f in effective_fields(run)
        if f.get("required") == "mandatory" and f["name"] not in approved_targets
    ]
    present_missing = [f for f in missing if f in candidate_targets]
    source_missing = [f for f in missing if f not in candidate_targets]
    if present_missing:
        raise BusinessRuleError(
            "Cannot finalize mapping: required canonical fields are not mapped.",
            details={
                "missing_fields": present_missing,
                "source_missing_fields": source_missing,
                "message": (
                    "These required fields were found in the source file but still need an approved mapping. "
                    "Fields absent from the uploaded bordereaux are treated as source gaps and can be left "
                    "unmapped for this run."
                ),
            },
        )

    # No source column is silently dropped: anything still undecided (open
    # proposals that were never approved) is carried through as ``extra_``.
    decided = {a.source_column for a in approved_rows}
    undecided = sorted({c.source_column for c in all_candidates} - decided)
    for col in undecided:
        await _add_passthrough(
            db, mapping_set.id, col, actor_id, {"type": "passthrough", "reason": "no_decision_at_finalize"}
        )

    from bordereaux.core.utils import utcnow

    mapping_set.status = MappingSetStatus.FINALIZED.value
    mapping_set.finalized_by = actor_id
    mapping_set.finalized_at = utcnow()
    run.mapping_set_id = mapping_set.id
    await db.flush()

    await AuditService(db).log(
        event_type="mapping.finalized",
        target_type="MappingSet",
        target_id=mapping_set.id,
        action=AuditAction.APPROVE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state={**model_snapshot(mapping_set), "undecided_passed_through": undecided},
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.confirm_mapping(run_id, actor_id)
    run = await sm.enter_treaty_figures(run_id, actor_id)

    # Standardize immediately: the canonical dataset must exist before
    # financial checks (Step 8) regardless of how long treaty-figure entry takes.
    from bordereaux.standardization.service import standardize_run

    await standardize_run(db, storage, run_id)

    return mapping_set


async def set_target_format(
    db: AsyncSession,
    run_id: UUID,
    actor_id: UUID,
    mode: str,
    columns: list[str] | None = None,
    terms: dict[str, list[str]] | None = None,
    template_id: UUID | None = None,
) -> ProcessingRun:
    """Choose what the source columns are mapped *to*: the default data
    dictionary (with its built-in recognised terms), the user's own list of
    final columns plus, optionally, the terms they recognise each one by, or a
    saved format from the platform directory (``template_id``; used as a custom
    format, and a snapshot of it is stored so later edits to the saved format
    never change this run). Must be done while the run is in mapping review;
    existing candidates are then stale, so the caller regenerates them
    (``generate_mapping_candidates``)."""
    from bordereaux.core.exceptions import ValidationError
    from bordereaux.mapping.format_templates import as_target_input, get_template
    from bordereaux.mapping.target_format import build_custom_fields, clean_terms

    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.MAPPING_REVIEW_PENDING.value:
        raise StateError(
            f"Target format can only be chosen during mapping review (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    if mode == "DEFAULT" and terms:
        raise ValidationError("Recognised terms can only be supplied together with your own final columns")
    template = None
    if template_id is not None:
        if mode != "CUSTOM":
            raise ValidationError("A saved format is chosen with mode CUSTOM")
        if columns or terms:
            raise ValidationError("Choose either a saved format or your own columns, not both")
        template = await get_template(db, template_id)
        columns, terms = as_target_input(template)
    before = run.target_format
    if mode == "DEFAULT":
        run.target_format = {"mode": "DEFAULT"}
    elif mode == "CUSTOM":
        names = [c.strip() for c in (columns or []) if c and c.strip()]
        fields = build_custom_fields(columns or [], terms)
        run.target_format = {
            "mode": "CUSTOM",
            "columns": names,
            "terms": clean_terms(terms, [f["display_name"] for f in fields]),
            "fields": fields,
        }
        if template is not None:
            run.target_format["template"] = {
                "id": str(template.id),
                "name": template.name,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            }
    else:
        raise BusinessRuleError("mode must be DEFAULT or CUSTOM")
    await db.flush()
    await AuditService(db).log(
        event_type="mapping.target_format_set",
        target_type="ProcessingRun",
        target_id=run.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state={"mode": (before or {}).get("mode")},
        after_state={
            "mode": run.target_format["mode"],
            "columns": run.target_format.get("columns"),
            "recognised_terms": run.target_format.get("terms") or {},
            "template": run.target_format.get("template"),
        },
        project_id=run.project_id,
    )
    await db.commit()
    return run
