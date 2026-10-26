"""Step 8-9: run the MCR engine against the standardized dataset + the run's
treaty figures, persist every discrepancy as a ``DiscrepancyFinding`` row.

Severity classification (documented resolved ambiguity): the rule document
and MODULE_CONTRACTS.md describe CONFIRMED_ERROR / VALID_DIFFERENCE / WARNING
/ UNRESOLVED as *review outcomes*, not something the deterministic engine can
decide on its own (telling a genuine data error apart from an acceptable
business difference needs a human). Every finding is therefore persisted
with ``status=UNRESOLVED`` and ``severity=ERROR`` (the engine only reports
rules that are *in effect* for the dataset and *fail* a specific row - by
construction these are the model's strongest-evidence findings), pending
human disposition via the override endpoint. This keeps the deterministic
layer honest: Python decides what disagrees with the numbers, a human
decides what that means.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, StateError
from bordereaux.core.models import ActorType, AuditAction, DiscrepancyStatus, ProcessingRunStatus, Severity
from bordereaux.money_rules import MCRConfig, MoneyRole, MoneyRow, TreatyRates, find_discrepancies
from bordereaux.money_rules.engine import DiscrepancyCandidate
from bordereaux.money_rules.rules import approx_equal
from bordereaux.money_rules.totals import TotalRow, evaluate_total_rows
from bordereaux.money_rules.traps import detect_bundled_commission, detect_gross_is_ceded_rows
from bordereaux.treaty.derivation import rates_by_currency
from bordereaux.cleaning.parsing import try_parse_decimal
from bordereaux.core.models import ResolutionStage
from bordereaux.core.utils import to_jsonable
from bordereaux.mapping.money_resolution import resolve_unassigned_money_columns
from bordereaux.models.discrepancy import DiscrepancyFinding, DiscrepancyOverride
from bordereaux.models.mapping import ApprovedMapping
from bordereaux.models.money_rules import MoneyColumnResolution, MoneyRelation
from bordereaux.money_rules import relations as rel
from bordereaux.models.run import ProcessingRun
from bordereaux.models.treaty import TreatyFigures
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.schemas.loader import MONEY_ROLE_BY_FIELD, load_schema_definition
from bordereaux.standardization.service import load_standardized_dataset
from bordereaux.storage.service import StorageService


def _build_money_rows(rows: list[dict[str, Any]], fx_by_currency: dict[str, Decimal] | None = None) -> list[MoneyRow]:
    load_schema_definition()  # ensure MONEY_ROLE_BY_FIELD is populated
    money_rows: list[MoneyRow] = []
    valid_role_names = {r.name for r in MoneyRole}
    for row in rows:
        values: dict[MoneyRole, Decimal | None] = {}
        for field_name, role_name in MONEY_ROLE_BY_FIELD.items():
            # MONEY_ROLE_BY_FIELD values are MoneyRole *member names* (e.g.
            # "GROSS"), not their short values (e.g. "G") - look up by name.
            if role_name not in valid_role_names:
                continue
            role = MoneyRole[role_name]
            raw = row.get(field_name)
            if raw is None:
                values[role] = None
                continue
            try:
                values[role] = Decimal(str(raw))
            except Exception:
                values[role] = None
        ccy = str(row.get("original_currency") or "").strip().upper()
        money_rows.append(
            MoneyRow(
                row_number=row["_source_row_number"],
                values=values,
                fx_rate=(fx_by_currency or {}).get(ccy),
            )
        )
    return money_rows


def _build_treaty_rates(figures: TreatyFigures) -> TreatyRates:
    return TreatyRates(
        commission_pct=figures.commission_pct,
        brokerage_pct=figures.brokerage_pct,
        tax_pct=figures.tax_pct,
        cession_pct=figures.cession_pct,
        order_pct=figures.order_pct,
        fx_rate=figures.fx_rate,
        expected_si_rate=figures.expected_si_rate,
    )


def _apply_traps_and_fx(
    candidates: list[DiscrepancyCandidate],
    dataset: dict[str, Any],
    money_rows: list[MoneyRow],
    fx_by_currency: dict[str, Decimal],
    treaty: TreatyRates,
    config: MCRConfig,
) -> list[DiscrepancyCandidate]:
    """Row-level trap findings (MCR-D1/D2) replace the ordinary rule failures
    they explain; FX findings compare each row's own rate with the treaty rate
    for its currency."""
    rows_by_number = {r["_source_row_number"]: r for r in dataset["rows"]}
    sum_insured = {
        n: d for n, r in rows_by_number.items() if (d := try_parse_decimal(r.get("sum_insured"))[0]) is not None
    }
    groups = {n: str(r.get("class_of_business")).strip().lower() for n, r in rows_by_number.items() if r.get("class_of_business")}

    traps = [t for row in money_rows if (t := detect_bundled_commission(row, treaty, config))]
    traps += detect_gross_is_ceded_rows(money_rows, sum_insured, groups, treaty, config)
    explained = {(t.row_number, rid) for t in traps for rid in t.explains}
    out = [c for c in candidates if (c.row_number, c.rule_id) not in explained]
    for t in traps:
        out.append(
            DiscrepancyCandidate(
                rule_id=t.rule_id,
                category="TRAP",
                row_number=t.row_number,
                expected_value=t.expected_value,
                observed_value=t.observed_value,
                variance=(t.observed_value - t.expected_value) if t.expected_value is not None and t.observed_value is not None else None,
                message=t.message,
                evidence=t.evidence,
            )
        )

    if fx_by_currency and "fx_rate" in dataset.get("fields", []):
        for row in money_rows:
            src = rows_by_number.get(row.row_number, {})
            file_rate = try_parse_decimal(src.get("fx_rate"))[0]
            if file_rate is None or row.fx_rate is None:
                continue
            if not approx_equal(file_rate, row.fx_rate, config.tolerance):
                out.append(
                    DiscrepancyCandidate(
                        rule_id="MCR-FX1",
                        category="BASIS_ALIGNMENT",
                        row_number=row.row_number,
                        expected_value=row.fx_rate,
                        observed_value=file_rate,
                        variance=file_rate - row.fx_rate,
                        message=(
                            f"FX rate in the file ({file_rate}) differs from the treaty rate for "
                            f"{src.get('original_currency')} ({row.fx_rate})."
                        ),
                        evidence={"currency": src.get("original_currency")},
                    )
                )
    return sorted(out, key=lambda c: (c.row_number, c.rule_id))


_NUMERIC_SHARE = 0.8


def _check_total_rows(
    dataset: dict[str, Any], money_rows: list[MoneyRow], config: MCRConfig
) -> tuple[list[DiscrepancyCandidate], list[dict[str, Any]]]:
    """Category F: the file's own total/subtotal rows against the data rows.
    Every result is reported; only a failure (F3 / F2) becomes a finding."""
    raw_totals = dataset.get("total_rows") or []
    if not raw_totals:
        return [], []
    total_money = _build_money_rows(raw_totals)
    totals = [
        TotalRow(
            row=money,
            kind=raw["_kind"],
            data_row_range=tuple(raw["_data_row_range"]) if raw.get("_data_row_range") else None,
        )
        for raw, money in zip(raw_totals, total_money)
    ]
    results = evaluate_total_rows(money_rows, totals, config)
    findings = [
        DiscrepancyCandidate(
            rule_id=r.rule_id,
            category="TOTALS",
            row_number=r.row_number,
            expected_value=r.computed_sum,
            observed_value=r.total_row_value,
            variance=(r.total_row_value - r.computed_sum)
            if r.total_row_value is not None and r.computed_sum is not None
            else None,
            message=r.message,
            evidence={"field": r.field.value if r.field else None},
        )
        for r in results
        if not r.holds
    ]
    summary = [
        {
            "rule_id": r.rule_id,
            "row_number": r.row_number,
            "field": r.field.value if r.field else None,
            "holds": r.holds,
            "message": r.message,
        }
        for r in results
    ]
    return findings, summary

# Columns that are plainly not premium-flow amounts are not tested as money.
_NON_PREMIUM_NAME = re.compile(r"%|pct|percent|rate|ratio|claim|ibnr|reserve|o/s|outstanding|paid|count", re.I)


def _looks_like_ratio(values: list[Any]) -> bool:
    parsed = [d for d, ok in (try_parse_decimal(v) for v in values if v not in (None, "")) if ok and d is not None]
    return bool(parsed) and all(abs(d) <= 1 for d in parsed)


async def _infer_unmapped_money_columns(
    db: AsyncSession, run: ProcessingRun, dataset: dict[str, Any], treaty: TreatyRates, config: MCRConfig
) -> list[dict[str, Any]]:
    """Relationship check moved here from mapping: numeric columns that did not
    match the data dictionary (``extra_*`` pass-throughs) are tested against
    the premium-flow identities, now that treaty figures anchor the ratios.
    The result is a *suggestion* for the reviewer - nothing is re-mapped."""
    load_schema_definition()  # populates MONEY_ROLE_BY_FIELD
    valid_roles = {r.name for r in MoneyRole}
    rows = dataset["rows"]
    present = set(dataset["fields"])

    known: dict[MoneyRole, list[Decimal | None]] = {}
    for field_name, role_name in MONEY_ROLE_BY_FIELD.items():
        if role_name in valid_roles and field_name in present:
            known[MoneyRole[role_name]] = [try_parse_decimal(r.get(field_name))[0] for r in rows]
    role_to_field = {
        MoneyRole[role_name]: field_name
        for field_name, role_name in MONEY_ROLE_BY_FIELD.items()
        if role_name in valid_roles and field_name not in present
    }

    approved = (
        await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == run.mapping_set_id))
    ).scalars().all()
    source_of = {a.target_field: a.source_column for a in approved}

    candidates: dict[str, list[Any]] = {}
    for field_name in dataset["fields"]:
        if not field_name.startswith("extra_"):
            continue
        values = [r.get(field_name) for r in rows]
        if _NON_PREMIUM_NAME.search(source_of.get(field_name, field_name)) or _looks_like_ratio(values):
            continue
        non_blank = [v for v in values if v not in (None, "")]
        if non_blank and sum(1 for v in non_blank if try_parse_decimal(v)[1]) / len(non_blank) >= _NUMERIC_SHARE:
            candidates[field_name] = values
    if not candidates or not role_to_field or not known:
        return []

    outcomes = resolve_unassigned_money_columns(candidates, known, list(role_to_field), treaty, config)
    suggestions: list[dict[str, Any]] = []
    for extra_field, outcome in outcomes.items():
        if outcome.resolved_role is None or not outcome.matched_rules:
            continue  # no premium-flow relationship found: nothing to suggest
        resolved = outcome.resolved_role is not None and not outcome.is_ambiguous and outcome.resolved_role in role_to_field
        suggested_field = role_to_field[outcome.resolved_role] if resolved else None
        source_column = source_of.get(extra_field, extra_field)
        db.add(
            MoneyColumnResolution(
                run_id=run.id,
                source_column=source_column,
                resolved_canonical_field=suggested_field,
                resolution_stage=(
                    ResolutionStage.SEMANTIC_ARITHMETIC.value if resolved else ResolutionStage.HUMAN_REVIEW.value
                ),
                matched_rules=to_jsonable(outcome.matched_rules),
                is_ambiguous=outcome.is_ambiguous,
                evidence=to_jsonable(outcome.evidence),
            )
        )
        suggestions.append(
            {
                "source_column": source_column,
                "suggested_field": suggested_field,
                "is_ambiguous": outcome.is_ambiguous,
                "matched_rules": to_jsonable(outcome.matched_rules),
            }
        )
    await db.flush()
    return suggestions


#: Built-in per-row rules that the user's declared relations replace (traps D*, FX, totals F* and sign G1 stay).
_RELATION_REPLACED_PREFIXES = ("MCR-A", "MCR-B", "MCR-C")
_RELATION_REPLACED_IDS = {"MCR-G2", "MCR-G4"}


def _replaced_by_relations(rule_id: str) -> bool:
    return rule_id.startswith(_RELATION_REPLACED_PREFIXES) or rule_id in _RELATION_REPLACED_IDS


async def _evaluate_declared_relations(
    db: AsyncSession,
    run_id: UUID,
    dataset: dict[str, Any],
    treaty: TreatyRates,
    config: MCRConfig,
    fx_by_currency: dict[str, Decimal],
) -> tuple[list[DiscrepancyCandidate], list[dict[str, Any]]]:
    """Findings + per-relation summary for the relations the user declared for this run."""
    stored = (
        await db.execute(
            select(MoneyRelation).where(MoneyRelation.run_id == run_id).order_by(MoneyRelation.created_at, MoneyRelation.id)
        )
    ).scalars().all()
    if not stored:
        return [], []

    def fx_for_row(row: dict[str, Any]) -> Decimal | None:
        return fx_by_currency.get(str(row.get("original_currency") or "").strip().upper())

    rows = dataset["rows"]
    candidates: list[DiscrepancyCandidate] = []
    summary: list[dict[str, Any]] = []
    for index, row in enumerate(stored, start=1):
        terms = rel.parse_terms(row.terms)
        relation = rel.Relation(str(row.id), row.label, row.target_field, terms, row.origin)
        ev = rel.evaluate_relation(relation, rows, treaty, config, fx_for_row)
        row.last_rows_evaluated = ev.evaluated
        row.last_rows_failed = len(ev.failed)
        row.last_skipped_reason = ev.skipped_reason
        expression = rel.describe(row.target_field, terms)
        agreement = ev.agreement
        for failure in ev.failed:
            candidates.append(
                DiscrepancyCandidate(
                    rule_id=f"REL-{index}",
                    category=rel.category_for(terms),
                    row_number=failure.row_number,
                    expected_value=failure.expected,
                    observed_value=failure.observed,
                    variance=failure.observed - failure.expected,
                    message=(
                        f"{row.label}: {row.target_field} should be {failure.expected} "
                        f"({expression}) but the file has {failure.observed}."
                    ),
                    evidence={
                        "relation_id": str(row.id),
                        "relation_label": row.label,
                        "relation_origin": row.origin,
                        "expression": expression,
                        "inputs": failure.inputs,
                        "relation_agreement": str(agreement.quantize(Decimal("0.0001"))) if agreement is not None else None,
                        "affected_field": row.target_field,
                    },
                )
            )
        summary.append(
            {
                "id": str(row.id),
                "check_id": f"REL-{index}",
                "label": row.label,
                "expression": expression,
                "origin": row.origin,
                "rows_evaluated": ev.evaluated,
                "rows_failed": len(ev.failed),
                "skipped_reason": ev.skipped_reason,
            }
        )
    await db.flush()
    return candidates, summary


async def run_financial_checks(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID | None = None
) -> dict[str, Any]:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.TREATY_FIGURES_VALIDATED.value:
        raise StateError(
            f"Run must be TREATY_FIGURES_VALIDATED to run financial checks (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    if run.treaty_figures_id is None:
        raise StateError("Run has no treaty figures to check against")

    figures = await db.get(TreatyFigures, run.treaty_figures_id)
    if figures is None:
        raise NotFoundError("Treaty figures not found", details={"treaty_figures_id": str(run.treaty_figures_id)})

    dataset = await load_standardized_dataset(storage, run_id)
    fx_by_currency = rates_by_currency(figures.settlement_currency, figures.fx_rates)
    if figures.fx_rate is not None and figures.currency:
        fx_by_currency.setdefault(figures.currency.upper(), figures.fx_rate)
    money_rows = _build_money_rows(dataset["rows"], fx_by_currency)
    treaty = _build_treaty_rates(figures)
    config = MCRConfig()

    candidates = find_discrepancies(money_rows, treaty, config)
    candidates = _apply_traps_and_fx(candidates, dataset, money_rows, fx_by_currency, treaty, config)
    total_findings, total_checks = _check_total_rows(dataset, money_rows, config)
    relation_candidates, relation_summary = await _evaluate_declared_relations(
        db, run_id, dataset, treaty, config, fx_by_currency
    )
    if relation_summary:
        # The user's declared relations replace the built-in identity rules (traps, FX, totals and
        # the sign check still run). With nothing declared the built-in rules apply, as before.
        candidates = [c for c in candidates if not _replaced_by_relations(c.rule_id)]
    candidates = sorted([*candidates, *relation_candidates, *total_findings], key=lambda c: (c.row_number, c.rule_id))
    column_role_suggestions = await _infer_unmapped_money_columns(db, run, dataset, treaty, config)

    findings: list[DiscrepancyFinding] = []
    for candidate in candidates:
        finding = DiscrepancyFinding(
            run_id=run_id,
            check_id=candidate.rule_id,
            category=candidate.category,
            severity=Severity.ERROR.value,
            status=DiscrepancyStatus.UNRESOLVED.value,
            affected_row_number=candidate.row_number,
            affected_field=(candidate.evidence or {}).get("affected_field"),
            expected_value=candidate.expected_value,
            observed_value=candidate.observed_value,
            variance=candidate.variance,
            evidence=candidate.evidence,
            message=candidate.message,
        )
        db.add(finding)
        findings.append(finding)
    await db.flush()

    await AuditService(db).log(
        event_type="financial_checks.completed",
        target_type="ProcessingRun",
        target_id=run_id,
        action=AuditAction.EXECUTE,
        actor_id=actor_id,
        actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
        after_state={
            "discrepancies_found": len(findings),
            "rows_checked": len(money_rows),
            "column_role_suggestions": len(column_role_suggestions),
            "relations_checked": len(relation_summary),
        },
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.complete_financial_checks(run_id, actor_id)
    await sm.enter_discrepancy_review(run_id, actor_id)

    return {
        "rows_checked": len(money_rows),
        "discrepancies_found": len(findings),
        "finding_ids": [str(f.id) for f in findings],
        "column_role_suggestions": column_role_suggestions,
        "total_checks": total_checks,
        "relation_results": relation_summary,
    }


async def list_discrepancies(
    db: AsyncSession,
    run_id: UUID,
    severity: str | None = None,
    status: str | None = None,
    category: str | None = None,
) -> list[DiscrepancyFinding]:
    stmt = select(DiscrepancyFinding).where(DiscrepancyFinding.run_id == run_id)
    if severity:
        stmt = stmt.where(DiscrepancyFinding.severity == severity)
    if status:
        stmt = stmt.where(DiscrepancyFinding.status == status)
    if category:
        stmt = stmt.where(DiscrepancyFinding.category == category)
    stmt = stmt.order_by(DiscrepancyFinding.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


async def override_discrepancy(
    db: AsyncSession, discrepancy_id: UUID, actor_id: UUID, reason: str, comment: str | None = None
) -> DiscrepancyOverride:
    finding = await db.get(DiscrepancyFinding, discrepancy_id)
    if finding is None:
        raise NotFoundError("Discrepancy finding not found", details={"discrepancy_id": str(discrepancy_id)})
    if not reason or not reason.strip():
        from bordereaux.core.exceptions import ValidationError

        raise ValidationError("An override reason is required")
    if finding.status == DiscrepancyStatus.OVERRIDDEN.value:
        raise StateError("This discrepancy has already been overridden", code="ALREADY_OVERRIDDEN")

    existing = (
        await db.execute(select(DiscrepancyOverride).where(DiscrepancyOverride.discrepancy_id == discrepancy_id))
    ).scalar_one_or_none()
    if existing is not None:
        raise StateError("This discrepancy has already been overridden", code="ALREADY_OVERRIDDEN")

    override = DiscrepancyOverride(
        discrepancy_id=discrepancy_id,
        run_id=finding.run_id,
        actor_id=actor_id,
        reason=reason,
        comment=comment,
    )
    db.add(override)
    await db.flush()

    # The finding's own expected/observed/evidence columns are never
    # mutated - only its disposition status changes.
    finding.status = DiscrepancyStatus.OVERRIDDEN.value
    await db.flush()

    run = await db.get(ProcessingRun, finding.run_id)
    await AuditService(db).log(
        event_type="discrepancy.overridden",
        target_type="DiscrepancyFinding",
        target_id=finding.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        reason=reason,
        metadata={"comment": comment},
        project_id=run.project_id if run else None,
    )
    await db.commit()
    return override


async def proceed_to_report_generation(db: AsyncSession, run_id: UUID, actor_id: UUID) -> ProcessingRun:
    sm = ProcessingRunStateMachine(db)
    return await sm.proceed_to_report_generation(run_id, actor_id)
