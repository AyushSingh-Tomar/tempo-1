"""Money-column relations for a run: options, CRUD, the standard set and AI suggestions.

The user declares the relationships (Step 7, after treaty figures); financial checks then
evaluate exactly that set, deterministically. The AI only *proposes* relations - every
proposal is re-measured by Python against the real data (agreement %) before it is shown,
and nothing is saved until the user adds it. If the AI is slow, limited or down, manual
and standard relations work exactly the same.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.credentials import resolve_llm_service
from bordereaux.ai.interactions import record_interaction, serialize_interaction
from bordereaux.ai.service import AI_DISABLED, build_llm_service
from bordereaux.audit.service import AuditService
from bordereaux.cleaning.parsing import try_parse_decimal
from bordereaux.core.exceptions import NotFoundError, StateError, ValidationError
from bordereaux.core.models import ActorType, AuditAction, ProcessingRunStatus
from bordereaux.core.utils import model_snapshot
from bordereaux.mapping.target_format import effective_fields
from bordereaux.models.mapping import ApprovedMapping
from bordereaux.models.money_rules import MoneyRelation
from bordereaux.models.run import ProcessingRun
from bordereaux.models.treaty import TreatyFigures
from bordereaux.money_rules import MCRConfig, TreatyRates
from bordereaux.money_rules import relations as rel
from bordereaux.schemas.loader import MONEY_ROLE_BY_FIELD, load_schema_definition
from bordereaux.standardization.service import load_standardized_dataset
from bordereaux.storage.service import StorageService

_NUMERIC_SHARE = 0.8
_NUMERIC_TYPES = {"DECIMAL", "INTEGER", "PERCENTAGE"}
_SAMPLE_ROWS = 15
_MIN_SUGGESTION_AGREEMENT = Decimal("0.5")
_EDITABLE = {
    ProcessingRunStatus.MAPPING_CONFIRMED.value,
    ProcessingRunStatus.TREATY_FIGURES_PENDING.value,
    ProcessingRunStatus.TREATY_FIGURES_VALIDATED.value,
}

SYSTEM_PROMPT = (
    "You are a reinsurance premium-accounting analyst. You propose arithmetic relationships between the "
    "money columns of a bordereaux. You only use the columns, treaty figures and data supplied, you never "
    "invent a column, and you only propose a relationship the sample data supports. "
    "Reply with a single JSON object and nothing else."
)


# ------------------------------------------------------------------ helpers


async def _run(db: AsyncSession, run_id: UUID) -> ProcessingRun:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    return run


def _assert_editable(run: ProcessingRun) -> None:
    if run.status not in _EDITABLE:
        raise StateError(
            "Money relations can only be changed after mapping is confirmed and before the financial checks have run "
            f"(current: {run.status}). Redo the treaty figures to go back.",
            code="RELATIONS_LOCKED",
            details={"run_id": str(run.id), "status": run.status},
        )


def treaty_rates_of(figures: TreatyFigures | None) -> TreatyRates:
    if figures is None:
        return TreatyRates()
    return TreatyRates(
        commission_pct=figures.commission_pct,
        brokerage_pct=figures.brokerage_pct,
        tax_pct=figures.tax_pct,
        cession_pct=figures.cession_pct,
        order_pct=figures.order_pct,
        fx_rate=figures.fx_rate,
        expected_si_rate=figures.expected_si_rate,
    )


async def _treaty_of(db: AsyncSession, run: ProcessingRun) -> TreatyRates:
    figures = await db.get(TreatyFigures, run.treaty_figures_id) if run.treaty_figures_id else None
    return treaty_rates_of(figures)


async def numeric_field_options(
    db: AsyncSession, storage: StorageService, run: ProcessingRun
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Numeric columns of the standardized file (the only things a relation can talk about)."""
    dataset = await load_standardized_dataset(storage, run.id)
    rows = dataset["rows"]
    load_schema_definition()
    defs = {f["name"]: f for f in effective_fields(run)}
    approved = (
        await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == run.mapping_set_id))
    ).scalars().all()
    source_of = {a.target_field: a.source_column for a in approved}

    # With the default dictionary the declared field type is reliable (an id such as ``endorsement_ref``
    # is not an amount); a user's own columns carry no reliable type, so the data decides.
    typed = (run.target_format or {}).get("mode") != "CUSTOM"
    options: list[dict[str, Any]] = []
    for name in dataset["fields"]:
        if typed and not name.startswith("extra_") and defs.get(name, {}).get("type", "STRING") not in _NUMERIC_TYPES:
            continue
        values = [r.get(name) for r in rows]
        non_blank = [v for v in values if v not in (None, "")]
        if not non_blank:
            continue
        parsed = [try_parse_decimal(v) for v in non_blank]
        numeric = [d for d, ok in parsed if ok and d is not None]
        if len(numeric) / len(non_blank) < _NUMERIC_SHARE:
            continue
        is_extra = name.startswith("extra_")
        d = defs.get(name, {})
        options.append(
            {
                "field": name,
                "label": source_of.get(name, name) if is_extra else d.get("display_name", name),
                "kind": "extra" if is_extra else "dictionary",
                "source_column": source_of.get(name),
                "money_role": MONEY_ROLE_BY_FIELD.get(name),
                "filled_rows": len(numeric),
                "min": str(min(numeric)),
                "max": str(max(numeric)),
                "sample": [str(x) for x in numeric[:3]],
            }
        )
    return options, dataset


def serialize_relation(r: MoneyRelation) -> dict[str, Any]:
    """``label`` is the human name; ``expression`` always uses field names (the UI maps them to column labels)."""
    terms = rel.parse_terms(r.terms)
    return {
        "id": str(r.id),
        "run_id": str(r.run_id),
        "label": r.label,
        "target_field": r.target_field,
        "terms": rel.terms_to_json(terms),
        "expression": rel.describe(r.target_field, terms),
        "origin": r.origin,
        "rationale": r.rationale,
        "last_rows_evaluated": r.last_rows_evaluated,
        "last_rows_failed": r.last_rows_failed,
        "last_skipped_reason": r.last_skipped_reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def list_relations(db: AsyncSession, run_id: UUID) -> list[MoneyRelation]:
    stmt = select(MoneyRelation).where(MoneyRelation.run_id == run_id).order_by(MoneyRelation.created_at, MoneyRelation.id)
    return list((await db.execute(stmt)).scalars().all())


def _evaluate_all_for_agreement(
    target: str,
    terms: tuple[rel.RelationTerm, ...],
    rows: list[dict[str, Any]],
    treaty: TreatyRates,
) -> rel.RelationEvaluation:
    probe = rel.Relation("probe", "probe", target, terms)
    return rel.evaluate_relation(probe, rows, treaty, MCRConfig())


# ------------------------------------------------------------------ queries


async def get_relation_workspace(db: AsyncSession, storage: StorageService, run_id: UUID) -> dict[str, Any]:
    run = await _run(db, run_id)
    options, _ = await numeric_field_options(db, storage, run)
    treaty = await _treaty_of(db, run)
    return {
        "editable": run.status in _EDITABLE,
        "relations": [serialize_relation(r) for r in await list_relations(db, run_id)],
        "fields": options,
        "treaty_factors": [
            {"name": n, "value": str(getattr(treaty, n)) if getattr(treaty, n) is not None else None}
            for n in rel.TREATY_FACTORS
        ],
        "tolerance": str(MCRConfig().tolerance),
    }


# ------------------------------------------------------------------ writes


async def _validated(
    db: AsyncSession, storage: StorageService, run: ProcessingRun, target: str, raw_terms: list[dict[str, Any]]
) -> tuple[tuple[rel.RelationTerm, ...], list[dict[str, Any]]]:
    options, _ = await numeric_field_options(db, storage, run)
    try:
        terms = rel.parse_terms(raw_terms)
        rel.validate(target, terms, {o["field"] for o in options})
    except rel.RelationError as exc:
        raise ValidationError(str(exc)) from exc
    return terms, options


async def create_relation(
    db: AsyncSession,
    storage: StorageService,
    run_id: UUID,
    actor_id: UUID,
    *,
    target_field: str,
    terms: list[dict[str, Any]],
    label: str | None = None,
    origin: str = "USER",
    rationale: str | None = None,
) -> MoneyRelation:
    run = await _run(db, run_id)
    _assert_editable(run)
    parsed, options = await _validated(db, storage, run, target_field, terms)
    labels = {o["field"]: o["label"] for o in options}
    sig = rel.signature(target_field, parsed)
    for existing in await list_relations(db, run_id):
        if rel.signature(existing.target_field, rel.parse_terms(existing.terms)) == sig:
            raise ValidationError("This relation is already declared.")
    row = MoneyRelation(
        run_id=run_id,
        label=(label or "").strip() or rel.describe(target_field, parsed, labels),
        target_field=target_field,
        terms=rel.terms_to_json(parsed),
        origin=origin,
        rationale=rationale,
        created_by=actor_id,
    )
    db.add(row)
    await db.flush()
    await AuditService(db).log(
        event_type="money_relation.created",
        target_type="MoneyRelation",
        target_id=row.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(row),
        project_id=run.project_id,
    )
    await db.commit()
    return row


async def update_relation(
    db: AsyncSession,
    storage: StorageService,
    run_id: UUID,
    relation_id: UUID,
    actor_id: UUID,
    *,
    target_field: str,
    terms: list[dict[str, Any]],
    label: str | None = None,
) -> MoneyRelation:
    run = await _run(db, run_id)
    _assert_editable(run)
    row = await db.get(MoneyRelation, relation_id)
    if row is None or row.run_id != run_id:
        raise NotFoundError("Money relation not found", details={"relation_id": str(relation_id)})
    parsed, options = await _validated(db, storage, run, target_field, terms)
    labels = {o["field"]: o["label"] for o in options}
    before = model_snapshot(row)
    row.target_field = target_field
    row.terms = rel.terms_to_json(parsed)
    row.label = (label or "").strip() or rel.describe(target_field, parsed, labels)
    row.last_rows_evaluated = row.last_rows_failed = row.last_skipped_reason = None
    await db.flush()
    await AuditService(db).log(
        event_type="money_relation.updated",
        target_type="MoneyRelation",
        target_id=row.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state=before,
        after_state=model_snapshot(row),
        project_id=run.project_id,
    )
    await db.commit()
    return row


async def delete_relation(db: AsyncSession, run_id: UUID, relation_id: UUID, actor_id: UUID) -> None:
    run = await _run(db, run_id)
    _assert_editable(run)
    row = await db.get(MoneyRelation, relation_id)
    if row is None or row.run_id != run_id:
        raise NotFoundError("Money relation not found", details={"relation_id": str(relation_id)})
    before = model_snapshot(row)
    await db.delete(row)
    await db.flush()
    await AuditService(db).log(
        event_type="money_relation.deleted",
        target_type="MoneyRelation",
        target_id=relation_id,
        action=AuditAction.DELETE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state=before,
        project_id=run.project_id,
    )
    await db.commit()


# ------------------------------------------------------------------ standard set


def standard_relations(present: dict[str, str]) -> list[dict[str, Any]]:
    """The premium-flow identities the platform used to hard-code, expressed as relations
    over the dictionary fields that exist in this file. ``present`` maps money role -> field."""
    g, c, t, n = (present.get(k) for k in ("GROSS", "COMMISSION", "TAX", "NET"))
    b, fn = present.get("BROKERAGE"), present.get("FINAL_NET")
    plus = lambda f, *factors: {"field": f, "sign": 1, "factors": list(factors)}  # noqa: E731
    minus = lambda f, *factors: {"field": f, "sign": -1, "factors": list(factors)}  # noqa: E731
    out: list[dict[str, Any]] = []
    if g and c and n:
        out.append({"target_field": n, "terms": [plus(g), minus(c), *([minus(t)] if t else [])]})
    if g and c and b and t and fn:
        out.append({"target_field": fn, "terms": [plus(g), minus(c), minus(b), minus(t)]})
    elif n and b and fn:
        out.append({"target_field": fn, "terms": [plus(n), minus(b)]})
    if g and c:
        out.append({"target_field": c, "terms": [plus(g, "commission_pct")]})
    if g and b:
        out.append({"target_field": b, "terms": [plus(g, "brokerage_pct")]})
    if g and t:
        out.append({"target_field": t, "terms": [plus(g, "tax_pct")]})
    for full, share in (
        (g, present.get("OUR_SHARE")),
        (c, present.get("COMMISSION_OUR_SHARE")),
        (fn, present.get("FINAL_NET_OUR_SHARE")),
    ):
        if full and share:
            out.append({"target_field": share, "terms": [plus(full, "order_pct")]})
    if present.get("SETTLEMENT") and present.get("FINAL_NET_OUR_SHARE"):
        out.append({"target_field": present["SETTLEMENT"], "terms": [plus(present["FINAL_NET_OUR_SHARE"], "fx_rate")]})
    return out


async def add_standard_relations(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID
) -> dict[str, Any]:
    """Seed the editor with the standard identities that fit this file's mapped columns.
    Identities whose treaty figure was not entered are left out (reported in ``skipped``)."""
    run = await _run(db, run_id)
    _assert_editable(run)
    options, _ = await numeric_field_options(db, storage, run)
    treaty = await _treaty_of(db, run)
    present = {o["money_role"]: o["field"] for o in options if o["money_role"]}
    existing = {rel.signature(r.target_field, rel.parse_terms(r.terms)) for r in await list_relations(db, run_id)}
    labels = {o["field"]: o["label"] for o in options}
    added, skipped = [], []
    for proto in standard_relations(present):
        terms = rel.parse_terms(proto["terms"])
        missing = sorted(n for n in rel.treaty_refs(terms) if n != "fx_rate" and getattr(treaty, n) is None)
        if missing:
            skipped.append({"expression": rel.describe(proto["target_field"], terms, labels), "reason": f"treaty figure {', '.join(missing)} not entered"})
            continue
        if rel.signature(proto["target_field"], terms) in existing:
            continue
        row = MoneyRelation(
            run_id=run_id,
            label=rel.describe(proto["target_field"], terms, labels),
            target_field=proto["target_field"],
            terms=rel.terms_to_json(terms),
            origin="STANDARD",
            created_by=actor_id,
        )
        db.add(row)
        added.append(row)
    await db.flush()
    await AuditService(db).log(
        event_type="money_relation.standard_added",
        target_type="ProcessingRun",
        target_id=run_id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state={"added": len(added), "skipped": len(skipped)},
        project_id=run.project_id,
    )
    await db.commit()
    return {"added": len(added), "skipped": skipped, "relations": [serialize_relation(r) for r in await list_relations(db, run_id)]}


# ------------------------------------------------------------------ AI suggestions


def _build_ai_prompt(
    options: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    treaty: TreatyRates,
    existing: list[dict[str, Any]],
    standard_hits: list[dict[str, Any]],
) -> str:
    fields = [
        {
            "field": o["field"],
            "label": o["label"],
            "kind": o["kind"],
            "money_role": o["money_role"],
            "min": o["min"],
            "max": o["max"],
        }
        for o in options
    ]
    names = [o["field"] for o in options]
    sample = [{n: r.get(n) for n in names} for r in rows[:_SAMPLE_ROWS]]
    document = {
        "task": (
            "Propose arithmetic relationships that hold between the numeric columns, so that the file can be "
            "checked row by row. Prefer relationships that involve unlabelled 'extra' columns, columns a standard "
            "premium-flow identity does not already cover, and the treaty figures."
        ),
        "relation_shape": "target = sum(sign * field * factor * ...), sign is 1 or -1, factors are treaty figure names or numbers",
        "rules": [
            "Use ONLY field names from numeric_fields and factor names from treaty_figures (or plain numbers).",
            "Only propose a relationship the sample rows support (check the arithmetic on several rows).",
            "Do not repeat a relationship listed in already_declared.",
            "Typical identities: net = gross - commission - tax; final net = net - brokerage; commission = gross * commission rate; "
            "our share = full amount * order share; settlement = our share * fx rate. Columns may be differently named.",
            "At most 8 relationships, each with a short rationale (max 25 words) and a confidence 0.0-1.0.",
        ],
        "numeric_fields": fields,
        "treaty_figures": {n: str(getattr(treaty, n)) for n in rel.TREATY_FACTORS if getattr(treaty, n) is not None},
        "sample_rows": sample,
        "standard_identities_measured_on_this_data": standard_hits,
        "already_declared": existing,
        "response_format": {
            "relations": [
                {
                    "label": "<short name>",
                    "target_field": "<field>",
                    "terms": [{"field": "<field>", "sign": 1, "factors": ["<treaty figure or number>"]}],
                    "rationale": "<why>",
                    "confidence": 0.0,
                }
            ]
        },
    }
    return json.dumps(document, ensure_ascii=False, default=str)


async def suggest_with_ai(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID
) -> dict[str, Any]:
    """Ask the model for relations. Always returns a result object (never raises for AI
    problems): ``status`` is ``ok`` or the exact reason the AI could not help."""
    run = await _run(db, run_id)
    _assert_editable(run)
    llm, _source = await resolve_llm_service(db, actor_id, build_llm_service)

    async def finish(suggestions: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
        row = await record_interaction(db, run, purpose="MONEY_RELATIONS", actor_id=actor_id, **kw)
        await db.commit()
        return {"status": row.status, "message": row.message, "interaction": serialize_interaction(row), "suggestions": suggestions}

    try:
        if not llm.is_available():
            return await finish([], status=AI_DISABLED, message=llm.status()["reason"] or "AI is not configured.")
        options, dataset = await numeric_field_options(db, storage, run)
        if len(options) < 2:
            return await finish([], status="skipped", message="Fewer than two numeric columns - no relationship to suggest.")
        treaty = await _treaty_of(db, run)
        rows = dataset["rows"]
        labels = {o["field"]: o["label"] for o in options}
        known = {o["field"] for o in options}
        declared = await list_relations(db, run_id)
        declared_sigs = {rel.signature(r.target_field, rel.parse_terms(r.terms)) for r in declared}

        present = {o["money_role"]: o["field"] for o in options if o["money_role"]}
        standard_hits = []
        for proto in standard_relations(present):
            terms = rel.parse_terms(proto["terms"])
            ev = _evaluate_all_for_agreement(proto["target_field"], terms, rows, treaty)
            if ev.agreement is not None:
                standard_hits.append(
                    {"relation": rel.describe(proto["target_field"], terms), "rows_checked": ev.evaluated, "agreement": f"{ev.agreement:.0%}"}
                )
        prompt = _build_ai_prompt(
            options, rows, treaty, [{"expression": rel.describe(r.target_field, rel.parse_terms(r.terms))} for r in declared], standard_hits
        )
        outcome = await llm.ask_json(prompt, system=SYSTEM_PROMPT)
        if not outcome.ok:
            return await finish([], outcome=outcome, items_sent=len(options))

        raw = outcome.data.get("relations") if isinstance(outcome.data, dict) else outcome.data
        suggestions: list[dict[str, Any]] = []
        discarded = 0
        seen = set(declared_sigs)
        for item in raw if isinstance(raw, list) else []:
            try:
                target = str(item.get("target_field"))
                terms = rel.parse_terms(item.get("terms"))
                rel.validate(target, terms, known)
            except (rel.RelationError, AttributeError):
                discarded += 1
                continue
            sig = rel.signature(target, terms)
            if sig in seen:
                continue
            seen.add(sig)
            ev = _evaluate_all_for_agreement(target, terms, rows, treaty)
            agreement = ev.agreement
            if agreement is None or agreement < _MIN_SUGGESTION_AGREEMENT:
                discarded += 1  # not supported by the data: a model guess, not a relationship of this file
                continue
            try:
                confidence = min(1.0, max(0.0, float(item.get("confidence"))))
            except (TypeError, ValueError):
                confidence = None
            suggestions.append(
                {
                    "label": str(item.get("label") or "").strip() or rel.describe(target, terms, labels),
                    "target_field": target,
                    "terms": rel.terms_to_json(terms),
                    "expression": rel.describe(target, terms),
                    "rationale": str(item.get("rationale") or "").strip()[:300],
                    "confidence": confidence,
                    "agreement": str(agreement.quantize(Decimal("0.0001"))),
                    "rows_evaluated": ev.evaluated,
                }
            )
        suggestions.sort(key=lambda s: Decimal(s["agreement"]), reverse=True)
        message = f"AI proposed {len(suggestions)} relationship(s); each was re-checked against your data below."
        if not suggestions:
            message = "AI found no additional relationship that your data supports."
        if discarded:
            message += f" {discarded} proposal(s) were discarded (unknown column or not supported by the data)."
        return await finish(suggestions, outcome=outcome, message=message, items_sent=len(options), items_resolved=len(suggestions))
    except Exception as exc:  # noqa: BLE001 - AI must never block the workflow
        await db.rollback()
        await db.refresh(run)
        return await finish(
            [], status="error", message=f"AI step failed unexpectedly ({type(exc).__name__}). Declare relations manually."
        )
