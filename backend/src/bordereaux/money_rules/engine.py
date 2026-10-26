"""Orchestration layer over the per-row rules (``rules.py``) and totals
(``totals.py``): dataset-wide row-agreement evaluation, discrepancy
generation (Step 8), and candidate-meaning scoring for ambiguous columns
during mapping (Step 4).

Category E (disambiguation/precedence, §6) is implemented here as
``rank_candidate_roles`` / ``is_ambiguous`` rather than as standalone rules,
because it operates across candidate meanings, not within one. Category D
(trap detection, §5) is implemented here as standalone detector functions the
mapping module calls for specific scenarios - each is independently testable
against the rule document's own worked numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.rules import RULE_CATEGORY, RULES, RuleOutcome, approx_equal
from bordereaux.money_rules.types import MoneyRole, MoneyRow, RuleResult, TreatyRates

R = MoneyRole


# --------------------------------------------------------------------------
# Dataset-wide row-agreement evaluation (shared by discrepancy detection and
# candidate-meaning scoring)
# --------------------------------------------------------------------------


@dataclass
class DatasetEvaluation:
    rule_results: dict[str, RuleResult]

    def in_effect_rules(self) -> list[RuleResult]:
        return [r for r in self.rule_results.values() if r.in_effect]


def evaluate_dataset(rows: list[MoneyRow], treaty: TreatyRates, config: MCRConfig) -> DatasetEvaluation:
    """Run every registered rule across every row. A rule is only "in effect"
    (§1.4 ``row_agreement_threshold`` / ``min_rows_for_resolution``) once it
    holds on enough of the rows where it was even applicable - rows for which
    a rule's required inputs are missing or excluded (G3) don't count against
    it either way."""
    results: dict[str, RuleResult] = {}
    for rule_id, rule_fn in RULES.items():
        passed = evaluated = excluded = 0
        failing: list[int] = []
        for row in rows:
            outcome = rule_fn(row, treaty, config)
            if outcome is RuleOutcome.NOT_APPLICABLE:
                excluded += 1
                continue
            evaluated += 1
            if outcome is RuleOutcome.HOLDS:
                passed += 1
            else:
                failing.append(row.row_number)
        row_agreement = (Decimal(passed) / Decimal(evaluated)) if evaluated else Decimal(0)
        in_effect = evaluated >= config.min_rows_for_resolution and row_agreement >= config.row_agreement_threshold
        results[rule_id] = RuleResult(
            rule_id=rule_id,
            category=RULE_CATEGORY[rule_id],
            evaluated_rows=evaluated,
            passed_rows=passed,
            excluded_rows=excluded,
            row_agreement=row_agreement,
            in_effect=in_effect,
            failing_row_numbers=failing,
        )
    return DatasetEvaluation(rule_results=results)


# --------------------------------------------------------------------------
# Step 8: discrepancy generation
# --------------------------------------------------------------------------


@dataclass
class DiscrepancyCandidate:
    rule_id: str
    category: str
    row_number: int
    expected_value: Decimal | None
    observed_value: Decimal | None
    variance: Decimal | None
    message: str
    evidence: dict = field(default_factory=dict)


def _explain(rule_id: str, row: MoneyRow, treaty: TreatyRates) -> tuple[Decimal | None, Decimal | None, str]:
    """Best-effort (expected, observed) pair for evidence/messages. Falls back
    to (None, None) with a generic message for rules without a specific
    explainer - the pass/fail decision itself never depends on this."""
    g, c, b, t, n, fn, cp = (
        row.get(R.GROSS),
        row.get(R.COMMISSION),
        row.get(R.BROKERAGE),
        row.get(R.TAX),
        row.get(R.NET),
        row.get(R.FINAL_NET),
        row.get(R.CEDED_PREMIUM),
    )
    if rule_id in ("MCR-A1", "MCR-G4") and None not in (g, c, t, n):
        return g - c - t, n, f"G - C - T = {g - c - t}, expected N = {n}."
    if rule_id == "MCR-A2" and None not in (g, c, b, t, fn):
        return g - c - b - t, fn, f"G - C - B - T = {g - c - b - t}, expected FN = {fn}."
    if rule_id == "MCR-A3" and None not in (g, c, n):
        return g - c, n, f"G - C = {g - c}, expected N = {n}."
    if rule_id == "MCR-A4" and None not in (n, c, t, g):
        return n + c + t, g, f"N + C + T = {n + c + t}, expected G = {g}."
    if rule_id == "MCR-A5" and None not in (n, b, fn):
        return n - b, fn, f"N - B = {n - b}, expected FN = {fn}."
    rate_map = {
        "MCR-B1": (R.GROSS, R.COMMISSION, treaty.commission_pct, "comm%"),
        "MCR-B2": (R.GROSS, R.BROKERAGE, treaty.brokerage_pct, "brok%"),
        "MCR-B3": (R.GROSS, R.TAX, treaty.tax_pct, "tax%"),
        "MCR-B4": (R.GROSS, R.CEDED_PREMIUM, treaty.cession_pct, "cess%"),
        "MCR-B5": (R.CEDED_PREMIUM, R.COMMISSION, treaty.commission_pct, "comm%"),
        "MCR-B6": (R.CEDED_PREMIUM, R.TAX, treaty.tax_pct, "tax%"),
    }
    if rule_id in rate_map:
        base_role, target_role, rate, rate_name = rate_map[rule_id]
        base, observed = row.get(base_role), row.get(target_role)
        if base is not None and rate is not None and observed is not None:
            expected = base * rate
            return expected, observed, f"{target_role.value} should be {base_role.value} x {rate_name} = {expected}."
    return None, None, f"{rule_id} failed for this row."


def find_discrepancies(
    rows: list[MoneyRow],
    treaty: TreatyRates,
    config: MCRConfig,
    evaluation: DatasetEvaluation | None = None,
) -> list[DiscrepancyCandidate]:
    """Step 8: once mapping is final, a rule that is *in effect* for this
    dataset (holds on enough rows to be trusted) but fails on a *specific*
    row is a discrepancy on that row - not evidence the mapping is wrong."""
    evaluation = evaluation or evaluate_dataset(rows, treaty, config)
    rows_by_number = {row.row_number: row for row in rows}
    candidates: list[DiscrepancyCandidate] = []
    reportable = [
        r
        for r in evaluation.rule_results.values()
        if r.evaluated_rows >= config.min_rows_for_resolution and r.row_agreement >= config.discrepancy_agreement_threshold
    ]
    for result in reportable:
        for row_number in result.failing_row_numbers:
            row = rows_by_number[row_number]
            expected, observed, message = _explain(result.rule_id, row, treaty)
            variance = (observed - expected) if (expected is not None and observed is not None) else None
            candidates.append(
                DiscrepancyCandidate(
                    rule_id=result.rule_id,
                    category=result.category,
                    row_number=row_number,
                    expected_value=expected,
                    observed_value=observed,
                    variance=variance,
                    message=message,
                    evidence={"row_agreement": str(result.row_agreement), "evaluated_rows": result.evaluated_rows},
                )
            )
    return candidates


# --------------------------------------------------------------------------
# Step 4: candidate-meaning scoring (Category E) for ambiguous columns
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleFitScore:
    role: MoneyRole
    best_row_agreement: Decimal
    supporting_rules: list[str]
    """rule_ids, in_effect, whose formula references ``role``, ranked by E3
    multi-rule corroboration (more independent confirmations = more trust)."""

    @property
    def corroboration_count(self) -> int:
        return len(self.supporting_rules)


_ROLE_RULE_MAP: dict[MoneyRole, list[str]] = {
    R.GROSS: ["MCR-A1", "MCR-A2", "MCR-A3", "MCR-A4", "MCR-B1", "MCR-B2", "MCR-B3", "MCR-B4", "MCR-C1", "MCR-C3", "MCR-C4"],
    R.COMMISSION: ["MCR-A1", "MCR-A3", "MCR-A4", "MCR-B1", "MCR-B5", "MCR-C1"],
    R.BROKERAGE: ["MCR-A2", "MCR-A5", "MCR-B2"],
    R.TAX: ["MCR-A1", "MCR-A2", "MCR-A4", "MCR-B3", "MCR-B6"],
    R.NET: ["MCR-A1", "MCR-A3", "MCR-A4", "MCR-A5", "MCR-C1"],
    R.FINAL_NET: ["MCR-A2", "MCR-A5", "MCR-C1"],
    R.CEDED_PREMIUM: ["MCR-B4", "MCR-B5", "MCR-B6"],
    R.OUR_SHARE: ["MCR-C1", "MCR-C2"],
    R.SETTLEMENT: ["MCR-C2", "MCR-C3"],
    R.OUR_SHARE_OF_CEDED: ["MCR-C4"],
}


def rank_candidate_roles(
    rows: list[MoneyRow], candidate_roles: list[MoneyRole], treaty: TreatyRates, config: MCRConfig
) -> list[RoleFitScore]:
    """E1 (highest row-agreement wins) + E3 (multi-rule corroboration beats a
    single rule): for each candidate meaning, evaluate every rule that
    references it and keep the ones that would be "in effect", ranked by
    (number of corroborating rules, best row agreement) descending."""
    evaluation = evaluate_dataset(rows, treaty, config)
    scores: list[RoleFitScore] = []
    for role in candidate_roles:
        relevant_ids = _ROLE_RULE_MAP.get(role, [])
        supporting = [
            evaluation.rule_results[rid]
            for rid in relevant_ids
            if rid in evaluation.rule_results and evaluation.rule_results[rid].in_effect
        ]
        best = max((r.row_agreement for r in supporting), default=Decimal(0))
        scores.append(
            RoleFitScore(role=role, best_row_agreement=best, supporting_rules=[r.rule_id for r in supporting])
        )
    scores.sort(key=lambda s: (s.corroboration_count, s.best_row_agreement), reverse=True)
    return scores


def is_ambiguous(ranked: list[RoleFitScore], config: MCRConfig) -> bool:
    """E4: if the top two candidate meanings score within ``ambiguity_margin``
    of each other on row agreement, the column is ambiguous - flag it rather
    than silently picking the slightly-better fit. (E6: zero candidates with
    any support at all is also unresolved, handled by the caller checking
    ``ranked[0].best_row_agreement == 0``.)"""
    if len(ranked) < 2:
        return False
    return abs(ranked[0].best_row_agreement - ranked[1].best_row_agreement) <= config.ambiguity_margin


# --------------------------------------------------------------------------
# Category D - trap detection (§5), standalone detectors for specific
# scenarios. Each takes the minimal signals the rule document itself uses.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TrapDetection:
    rule_id: str
    detected: bool
    resolved_role: MoneyRole | None
    message: str


def detect_gross_is_ceded(
    candidate_values: list[Decimal],
    implied_gross: list[Decimal],
    commission_values: list[Decimal] | None,
    treaty: TreatyRates,
    config: MCRConfig,
) -> TrapDetection:
    """MCR-D1: a column labelled "gross" that is actually the ceded premium.
    Signal: column ~ implied_gross x cess% (per row), on enough rows."""
    if treaty.cession_pct is None or len(candidate_values) != len(implied_gross) or not candidate_values:
        return TrapDetection("MCR-D1", False, None, "Insufficient data or missing cession rate.")
    matches = sum(
        1
        for col, gross in zip(candidate_values, implied_gross)
        if gross != 0 and approx_equal(col, gross * treaty.cession_pct, config.tolerance)
    )
    agreement = Decimal(matches) / Decimal(len(candidate_values))
    detected = (
        len(candidate_values) >= config.min_rows_for_resolution and agreement >= config.row_agreement_threshold
    )
    corroborated = True
    if detected and commission_values and treaty.commission_pct is not None:
        comm_matches = sum(
            1
            for col, comm in zip(candidate_values, commission_values)
            if col != 0 and approx_equal(comm, col * treaty.commission_pct, config.tolerance)
        )
        corroborated = Decimal(comm_matches) / Decimal(len(candidate_values)) >= config.row_agreement_threshold
    detected = detected and corroborated
    return TrapDetection(
        "MCR-D1",
        detected,
        R.CEDED_PREMIUM if detected else None,
        (
            f"Column equals cess% of the implied gross in {agreement:.0%} of rows - resolved as ceded_premium, not gross."
            if detected
            else "No gross-is-ceded pattern detected."
        ),
    )


def detect_commission_bundles_brokerage(
    candidate_values: list[Decimal], gross_values: list[Decimal], treaty: TreatyRates, config: MCRConfig
) -> TrapDetection:
    """MCR-D2: a "Commission" column that is really commission + brokerage
    combined. Signal: column ~ gross x (comm% + brok%) but NOT ~ gross x comm%."""
    if (
        treaty.commission_pct is None
        or treaty.brokerage_pct is None
        or len(candidate_values) != len(gross_values)
        or not candidate_values
    ):
        return TrapDetection("MCR-D2", False, None, "Insufficient data or missing commission/brokerage rates.")
    combined_rate = treaty.commission_pct + treaty.brokerage_pct
    combined_matches = sum(
        1
        for col, g in zip(candidate_values, gross_values)
        if g != 0 and approx_equal(col, g * combined_rate, config.tolerance)
    )
    pure_matches = sum(
        1
        for col, g in zip(candidate_values, gross_values)
        if g != 0 and approx_equal(col, g * treaty.commission_pct, config.tolerance)
    )
    n = len(candidate_values)
    combined_agreement = Decimal(combined_matches) / Decimal(n)
    pure_agreement = Decimal(pure_matches) / Decimal(n)
    detected = (
        n >= config.min_rows_for_resolution
        and combined_agreement >= config.row_agreement_threshold
        and pure_agreement < config.row_agreement_threshold
    )
    return TrapDetection(
        "MCR-D2",
        detected,
        None,
        (
            "Column equals comm% + brok% of gross, exceeding commission alone - bundles commission and brokerage."
            if detected
            else "No commission/brokerage bundling detected."
        ),
    )


def detect_ambiguous_net(
    candidate_values: list[Decimal],
    gross_values: list[Decimal],
    commission_values: list[Decimal],
    tax_values: list[Decimal] | None,
    config: MCRConfig,
) -> TrapDetection:
    """MCR-D3: distinguishes a "Net" column that is really net-of-commission-
    only (A3) from a true net premium (A1). Returns the resolved role, or
    None with ``detected=False`` if both/neither identity holds (ambiguous -
    e.g. tax is uniformly zero, so A1 and A3 coincide)."""
    n = len(candidate_values)
    if n == 0 or len(gross_values) != n or len(commission_values) != n:
        return TrapDetection("MCR-D3", False, None, "Insufficient data.")
    rows = [
        MoneyRow(i, {R.GROSS: g, R.COMMISSION: c, R.TAX: t, R.NET: v})
        for i, (g, c, t, v) in enumerate(
            zip(gross_values, commission_values, tax_values or [Decimal(0)] * n, candidate_values)
        )
    ]
    treaty = TreatyRates()
    a1 = sum(1 for row in rows if rule_a1_holds(row, config))
    a3 = sum(1 for row in rows if rule_a3_holds(row, config))
    a1_agree, a3_agree = Decimal(a1) / Decimal(n), Decimal(a3) / Decimal(n)
    a1_in_effect = n >= config.min_rows_for_resolution and a1_agree >= config.row_agreement_threshold
    a3_in_effect = n >= config.min_rows_for_resolution and a3_agree >= config.row_agreement_threshold
    if a1_in_effect and not a3_in_effect:
        return TrapDetection("MCR-D3", True, R.NET, "Column satisfies G - C - T = N: true net premium.")
    if a3_in_effect and not a1_in_effect:
        return TrapDetection(
            "MCR-D3", True, R.NET, "Column satisfies G - C = N only (tax not deducted): net-of-commission-only."
        )
    return TrapDetection(
        "MCR-D3", False, None, "Both or neither deduction identity hold - genuinely ambiguous, route to review."
    )


def rule_a1_holds(row: MoneyRow, config: MCRConfig) -> bool:
    g, c, t, n = row.get(R.GROSS), row.get(R.COMMISSION), row.get(R.TAX), row.get(R.NET)
    return None not in (g, c, t, n) and approx_equal(g - c - t, n, config.tolerance)


def rule_a3_holds(row: MoneyRow, config: MCRConfig) -> bool:
    g, c, n = row.get(R.GROSS), row.get(R.COMMISSION), row.get(R.NET)
    return None not in (g, c, n) and approx_equal(g - c, n, config.tolerance)


def detect_our_share_mislabelled(
    candidate_values: list[Decimal], larger_column_values: list[Decimal], treaty: TreatyRates, config: MCRConfig
) -> TrapDetection:
    """MCR-D5: a column labelled "...(100%)" that is actually behaving as the
    our-share version of a larger column (satisfies C1 against it)."""
    if treaty.order_pct is None or len(candidate_values) != len(larger_column_values) or not candidate_values:
        return TrapDetection("MCR-D5", False, None, "Insufficient data or missing order%.")
    n = len(candidate_values)
    matches = sum(
        1
        for col, larger in zip(candidate_values, larger_column_values)
        if larger != 0 and approx_equal(col, larger * treaty.order_pct, config.tolerance)
    )
    agreement = Decimal(matches) / Decimal(n)
    detected = n >= config.min_rows_for_resolution and agreement >= config.row_agreement_threshold
    return TrapDetection(
        "MCR-D5",
        detected,
        R.OUR_SHARE if detected else None,
        (
            "Column behaves as the our-share version of a larger column despite its '100%' label."
            if detected
            else "No our-share mislabelling detected."
        ),
    )
