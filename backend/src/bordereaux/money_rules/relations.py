"""User-declared money-column relations (Step 7).

A relation says: ``target  ~=  sum( sign * field * factor * ... )`` where a *factor* is
a treaty figure (``commission_pct`` ...) or a decimal literal. That one shape covers
every identity the built-in rules hard-code and any a custom file needs::

    net_premium  ~= gross_premium - commission - tax                 (deduction)
    commission   ~= gross_premium * commission_pct                   (treaty ratio)
    our_share    ~= gross_premium * order_pct                        (basis alignment)
    settlement   ~= final_net_our_share * fx_rate                    (currency)
    fee_total    ~= fee_a + fee_b                                    (any two columns)

Everything here is pure, deterministic ``Decimal`` arithmetic (ADR-002). Where a
relation came from - typed by the user, taken from the standard set, or suggested by
the AI - makes no difference to how it is checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

from bordereaux.cleaning.parsing import try_parse_decimal
from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.rules import approx_equal
from bordereaux.money_rules.types import TreatyRates

#: Treaty figures a factor may refer to (names of ``TreatyRates`` attributes).
TREATY_FACTORS: tuple[str, ...] = (
    "commission_pct",
    "brokerage_pct",
    "tax_pct",
    "cession_pct",
    "order_pct",
    "fx_rate",
)
_LITERAL_RE = re.compile(r"^-?\d+(\.\d+)?$")
_RATIO_FACTORS = {"commission_pct", "brokerage_pct", "tax_pct", "cession_pct"}
MAX_TERMS = 8


class RelationError(ValueError):
    """The relation definition itself is invalid (never raised for bad *data*)."""


@dataclass(frozen=True)
class RelationTerm:
    field: str
    sign: int = 1
    factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relation:
    id: str
    label: str
    target_field: str
    terms: tuple[RelationTerm, ...]
    origin: str = "USER"


@dataclass
class RelationFailure:
    row_number: int
    expected: Decimal
    observed: Decimal
    inputs: dict[str, str]


@dataclass
class RelationEvaluation:
    relation: Relation
    evaluated: int = 0
    failed: list[RelationFailure] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def agreement(self) -> Decimal | None:
        if not self.evaluated:
            return None
        return Decimal(self.evaluated - len(self.failed)) / Decimal(self.evaluated)


def parse_terms(raw: Iterable[Any]) -> tuple[RelationTerm, ...]:
    """Validate and normalise the JSON stored in ``money_relations.terms``."""
    terms: list[RelationTerm] = []
    for item in raw or []:
        if not isinstance(item, dict):
            raise RelationError("Each term must be an object with field, sign and factors.")
        name = str(item.get("field") or "").strip()
        if not name:
            raise RelationError("Every term needs a field.")
        sign = item.get("sign", 1)
        if sign not in (1, -1):
            raise RelationError(f"The sign of '{name}' must be +1 or -1.")
        factors = tuple(str(f).strip() for f in (item.get("factors") or []) if str(f).strip())
        for f in factors:
            if f not in TREATY_FACTORS and not _LITERAL_RE.match(f):
                raise RelationError(
                    f"'{f}' is not a treaty figure ({', '.join(TREATY_FACTORS)}) or a number."
                )
        terms.append(RelationTerm(name, int(sign), factors))
    if not terms:
        raise RelationError("A relation needs at least one term on the right-hand side.")
    if len(terms) > MAX_TERMS:
        raise RelationError(f"A relation can have at most {MAX_TERMS} terms.")
    return tuple(terms)


def terms_to_json(terms: Iterable[RelationTerm]) -> list[dict[str, Any]]:
    return [{"field": t.field, "sign": t.sign, "factors": list(t.factors)} for t in terms]


def validate(target_field: str, terms: tuple[RelationTerm, ...], known_fields: set[str]) -> None:
    if target_field not in known_fields:
        raise RelationError(f"'{target_field}' is not a numeric column of the mapped file.")
    for t in terms:
        if t.field not in known_fields:
            raise RelationError(f"'{t.field}' is not a numeric column of the mapped file.")
        if t.field == target_field and not t.factors:
            raise RelationError("A column cannot be defined in terms of itself.")


def signature(target_field: str, terms: Iterable[RelationTerm]) -> tuple[Any, ...]:
    """Order-insensitive identity of a relation, used to avoid duplicates."""
    return (target_field, tuple(sorted((t.field, t.sign, tuple(sorted(t.factors))) for t in terms)))


def describe(target_field: str, terms: Iterable[RelationTerm], labels: dict[str, str] | None = None) -> str:
    """``net_premium = gross_premium - commission - tax`` (labels optional)."""
    name = (lambda f: (labels or {}).get(f, f))
    parts: list[str] = []
    for i, t in enumerate(terms):
        body = " x ".join([name(t.field), *t.factors])
        if i == 0:
            parts.append(body if t.sign > 0 else f"-{body}")
        else:
            parts.append(f"{'+' if t.sign > 0 else '-'} {body}")
    return f"{name(target_field)} = {' '.join(parts)}"


def category_for(terms: Iterable[RelationTerm]) -> str:
    """Map a relation onto the discrepancy categories the review screen already knows."""
    factors = {f for t in terms for f in t.factors}
    if factors & _RATIO_FACTORS:
        return "TREATY_RATIO"
    if factors & {"order_pct", "fx_rate"}:
        return "BASIS_ALIGNMENT"
    return "CORE_DEDUCTION"


def treaty_refs(terms: Iterable[RelationTerm]) -> set[str]:
    return {f for t in terms for f in t.factors if f in TREATY_FACTORS}


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    parsed, ok = try_parse_decimal(value)
    return parsed if ok else None


def evaluate_relation(
    relation: Relation,
    rows: list[dict[str, Any]],
    treaty: TreatyRates,
    config: MCRConfig,
    fx_for_row: Callable[[dict[str, Any]], Decimal | None] | None = None,
) -> RelationEvaluation:
    """Check ``relation`` on every row. A row missing any needed value is not evaluated
    (never guessed); a relation whose treaty figure was not entered is reported as
    skipped with the reason instead of silently passing."""
    result = RelationEvaluation(relation)
    unresolved: set[str] = set()

    for row in rows:
        observed = _decimal(row.get(relation.target_field))
        if observed is None:
            continue
        expected = Decimal(0)
        inputs: dict[str, str] = {}
        ok = True
        for term in relation.terms:
            value = _decimal(row.get(term.field))
            if value is None:
                ok = False
                break
            inputs[term.field] = str(value)
            product = value
            for f in term.factors:
                if f in TREATY_FACTORS:
                    factor = (fx_for_row(row) if f == "fx_rate" and fx_for_row else None) or getattr(treaty, f)
                    if factor is None:
                        unresolved.add(f)
                        ok = False
                        break
                else:
                    try:
                        factor = Decimal(f)
                    except InvalidOperation:  # pragma: no cover - parse_terms already rejects these
                        ok = False
                        break
                product *= factor
            if not ok:
                break
            expected += product if term.sign > 0 else -product
        if not ok:
            continue
        result.evaluated += 1
        if not approx_equal(observed, expected, config.tolerance):
            result.failed.append(RelationFailure(row.get("_source_row_number", 0), expected, observed, inputs))

    if result.evaluated == 0 and unresolved:
        names = ", ".join(sorted(unresolved))
        result.skipped_reason = f"Needs treaty figure {names}, which was not entered."
    elif result.evaluated == 0:
        result.skipped_reason = "No row had values in every column of this relation, so nothing could be checked."
    return result
