"""Stage 3 (semantic/arithmetic) resolution for money columns whose names
give no alias signal at all (e.g. "Amount 1".."Amount 6"). Never
reimplements MCR arithmetic - this module only *searches* over candidate
column<->role assignments and scores each candidate assignment by calling
the real ``bordereaux.money_rules`` engine (``evaluate_dataset``), looking
for the assignment that makes the most rules hold on the most rows (E1/E3 of
the rule document: highest row-agreement, multi-rule corroboration wins).

Searching the assignment space: a full permutation brute force is only
tractable for a handful of unresolved columns (6! = 720), but a real file
routinely has several *unrelated* unmatched numeric columns alongside the
genuine money columns (claims reserves, percentages, ...), which would blow
the search up to an intractable size (11 columns x 6 roles = hundreds of
thousands of permutations) for no benefit - those columns have zero
resemblance to any premium-flow identity regardless of which role they're
tried against. Core-deduction identities (Category A) also all need 3+ roles
simultaneously, so there is no cheap *single-column* prefilter either.

Resolution: greedy construction (repeatedly add the single column/role pair
that most improves the current partial assignment's score) followed by
pairwise local-swap refinement (hill-climbing) until no swap improves the
score. This is O(roles^2 x names) rather than O(names!), reaches the same
optimum as brute force on every case checked against the rule document's
worked examples and the real test fixtures, and - critically for E4 - still
finds genuine ties: a pairwise swap that scores within the ambiguity margin
of the converged assignment flags both participating columns as ambiguous
rather than picking one arbitrarily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bordereaux.cleaning.parsing import try_parse_decimal
from bordereaux.money_rules import MCRConfig, MoneyRole, MoneyRow, TreatyRates
from bordereaux.money_rules.engine import evaluate_dataset

_MAX_REFINEMENT_SWEEPS = 20


@dataclass(frozen=True)
class MoneyColumnResolutionResult:
    source_column: str
    resolved_role: MoneyRole | None
    is_ambiguous: bool
    matched_rules: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def _column_decimals(values: list[Any]) -> list[Decimal | None]:
    out = []
    for v in values:
        parsed, ok = try_parse_decimal(v)
        out.append(parsed if ok else None)
    return out


def _assignment_rows(
    known: dict[MoneyRole, list[Decimal | None]],
    assignment: dict[MoneyRole, list[Decimal | None]],
    row_count: int,
) -> list[MoneyRow]:
    rows = []
    for i in range(row_count):
        values: dict[MoneyRole, Decimal | None] = {}
        for role, col_values in known.items():
            values[role] = col_values[i] if i < len(col_values) else None
        for role, col_values in assignment.items():
            values[role] = col_values[i] if i < len(col_values) else None
        rows.append(MoneyRow(row_number=i + 1, values=values))
    return rows


def _score(
    known: dict[MoneyRole, list[Decimal | None]],
    role_to_values: dict[MoneyRole, list[Decimal | None]],
    row_count: int,
    treaty: TreatyRates,
    config: MCRConfig,
) -> tuple[Decimal, int]:
    rows = _assignment_rows(known, role_to_values, row_count)
    evaluation = evaluate_dataset(rows, treaty, config)
    in_effect = evaluation.in_effect_rules()
    total_agreement = sum((r.row_agreement for r in in_effect), Decimal(0))
    return total_agreement, len(in_effect)


def _greedy_assign(
    names: list[str],
    decimals: dict[str, list[Decimal | None]],
    known: dict[MoneyRole, list[Decimal | None]],
    candidate_roles: list[MoneyRole],
    treaty: TreatyRates,
    config: MCRConfig,
    row_count: int,
) -> dict[MoneyRole, str]:
    assignment: dict[MoneyRole, str] = {}
    remaining_roles = list(candidate_roles)
    remaining_names = list(names)

    while remaining_roles and remaining_names:
        best: tuple[tuple[Decimal, int], MoneyRole, str] | None = None
        for role in remaining_roles:
            for name in remaining_names:
                trial = {r: decimals[c] for r, c in assignment.items()}
                trial[role] = decimals[name]
                score = _score(known, trial, row_count, treaty, config)
                if best is None or score > best[0]:
                    best = (score, role, name)
        assert best is not None
        _, role, name = best
        assignment[role] = name
        remaining_roles.remove(role)
        remaining_names.remove(name)
    return assignment


def _refine_with_swaps(
    assignment: dict[MoneyRole, str],
    decimals: dict[str, list[Decimal | None]],
    known: dict[MoneyRole, list[Decimal | None]],
    treaty: TreatyRates,
    config: MCRConfig,
    row_count: int,
) -> tuple[dict[MoneyRole, str], Decimal, int]:
    roles = list(assignment.keys())
    current_score = _score(known, {r: decimals[c] for r, c in assignment.items()}, row_count, treaty, config)
    for _ in range(_MAX_REFINEMENT_SWEEPS):
        improved = False
        for i in range(len(roles)):
            for j in range(i + 1, len(roles)):
                r1, r2 = roles[i], roles[j]
                swapped = dict(assignment)
                swapped[r1], swapped[r2] = swapped[r2], swapped[r1]
                score = _score(known, {r: decimals[c] for r, c in swapped.items()}, row_count, treaty, config)
                if score > current_score:
                    assignment, current_score = swapped, score
                    improved = True
        if not improved:
            break
    return assignment, current_score[0], current_score[1]


def _is_tied_swap(
    assignment: dict[MoneyRole, str],
    r1: MoneyRole,
    r2: MoneyRole,
    best_score: Decimal,
    decimals: dict[str, list[Decimal | None]],
    known: dict[MoneyRole, list[Decimal | None]],
    treaty: TreatyRates,
    config: MCRConfig,
    row_count: int,
    margin: Decimal,
) -> bool:
    swapped = dict(assignment)
    swapped[r1], swapped[r2] = swapped[r2], swapped[r1]
    score, _ = _score(known, {r: decimals[c] for r, c in swapped.items()}, row_count, treaty, config)
    return abs(best_score - score) <= margin


def resolve_unassigned_money_columns(
    columns: dict[str, list[Any]],
    known: dict[MoneyRole, list[Decimal | None]],
    candidate_roles: list[MoneyRole],
    treaty: TreatyRates,
    config: MCRConfig,
) -> dict[str, MoneyColumnResolutionResult]:
    """``columns``: unresolved numeric-looking source columns -> raw values
    (same row order across all columns and ``known``). ``known``: already
    resolved money fields -> per-row Decimal values (same row order).
    ``candidate_roles``: canonical money roles not yet claimed by any
    confidently-resolved column."""
    results: dict[str, MoneyColumnResolutionResult] = {}
    if not columns or not candidate_roles:
        for name in columns:
            results[name] = MoneyColumnResolutionResult(name, None, False, [], {"reason": "no_candidate_roles"})
        return results

    names = list(columns.keys())
    decimals = {name: _column_decimals(values) for name, values in columns.items()}
    row_count = max((len(v) for v in decimals.values()), default=0)

    # ``_greedy_assign`` stops once either side runs out, so it naturally
    # handles more-roles-than-columns and more-columns-than-roles alike.
    greedy = _greedy_assign(names, decimals, known, candidate_roles, treaty, config, row_count)
    assignment, best_agreement, best_count = _refine_with_swaps(greedy, decimals, known, treaty, config, row_count)

    unassigned_names = [n for n in names if n not in assignment.values()]
    for name in unassigned_names:
        results[name] = MoneyColumnResolutionResult(name, None, True, [], {"reason": "no_arithmetic_signal_found"})

    if best_agreement == 0:
        for role, name in assignment.items():
            results[name] = MoneyColumnResolutionResult(name, None, True, [], {"reason": "no_arithmetic_signal_found"})
        return results

    margin = config.ambiguity_margin * max(best_agreement, Decimal(1))
    roles = list(assignment.keys())
    ambiguous_roles: set[MoneyRole] = set()
    for i in range(len(roles)):
        for j in range(i + 1, len(roles)):
            if _is_tied_swap(assignment, roles[i], roles[j], best_agreement, decimals, known, treaty, config, row_count, margin):
                ambiguous_roles.add(roles[i])
                ambiguous_roles.add(roles[j])

    final_rows = _assignment_rows(known, {r: decimals[c] for r, c in assignment.items()}, row_count)
    final_evaluation = evaluate_dataset(final_rows, treaty, config)
    matched_rules = [
        {"rule_id": r.rule_id, "row_agreement": str(r.row_agreement)} for r in final_evaluation.in_effect_rules()
    ]

    for role, name in assignment.items():
        results[name] = MoneyColumnResolutionResult(
            name,
            role,
            role in ambiguous_roles,
            matched_rules,
            {"best_score": str(best_agreement), "corroborating_rules": best_count},
        )
    return results
