"""Reconcile a final bordereaux against a final subledger.

For each rule ``<expr over bordereaux> = <expr over subledger>``:

1. filter both datasets (year / quarter / treaty / any column);
2. evaluate each side's expression row by row (``Decimal``), then aggregate
   per group (SUM by default) at the declared grain (``group_by`` column
   pairs; none = one total);
3. full-outer-join the two sides on the group key, so a group that exists on
   one side only is reported, never dropped;
4. compare with the tolerance and classify.

Deterministic: no randomness, no AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bordereaux.core.exceptions import ValidationError
from bordereaux.reconciliation import expr as E

AGGREGATIONS = {"SUM", "COUNT", "AVG", "MIN", "MAX"}
FILTER_OPS = {"in", "not_in", "eq", "neq", "contains", "between", "gte", "lte", "is_blank", "not_blank"}
STATUSES = ("MATCHED", "VARIANCE", "ONLY_IN_BORDEREAUX", "ONLY_IN_SUBLEDGER")
_CENT = Decimal("0.01")
_EPS = Decimal("0.000001")


def key_text(v: Any) -> str:
    return "" if v is None else str(v).strip().casefold()


@dataclass
class Tolerance:
    absolute: Decimal = Decimal("0.01")
    percentage: Decimal = Decimal("0")  # fraction: 0.001 = 0.1%
    evaluation: str = "OR"  # OR | AND

    def within(self, variance: Decimal, pct: Decimal | None) -> bool:
        abs_ok = abs(variance) <= self.absolute
        pct_ok = pct is not None and abs(pct) <= self.percentage
        if self.percentage == 0:
            return abs_ok
        if self.absolute == 0:
            return pct_ok
        return (abs_ok and pct_ok) if self.evaluation == "AND" else (abs_ok or pct_ok)


def parse_tolerance(raw: dict[str, Any] | None) -> Tolerance:
    raw = raw or {}
    try:
        t = Tolerance(
            Decimal(str(raw.get("absolute", "0.01"))),
            Decimal(str(raw.get("percentage", "0"))),
            str(raw.get("evaluation", "OR")).upper(),
        )
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("Tolerance values must be numbers") from exc
    if t.absolute < 0 or t.percentage < 0 or t.evaluation not in ("OR", "AND"):
        raise ValidationError("Tolerance must be >= 0 and evaluation OR/AND")
    return t


# --- filters ----------------------------------------------------------------


def _row_passes(row: dict[str, Any], f: dict[str, Any]) -> bool:
    op, col = f["op"], f["column"]
    cell = row.get(col)
    text = key_text(cell)
    values = [key_text(v) for v in f.get("values", [])]
    if op == "is_blank":
        return text == ""
    if op == "not_blank":
        return text != ""
    if op in ("in", "eq"):
        return text in values
    if op in ("not_in", "neq"):
        return text not in values
    if op == "contains":
        return any(v in text for v in values)
    if op in ("between", "gte", "lte"):
        raw = [v for v in f.get("values", [])]
        lo = raw[0] if raw else None
        hi = raw[1] if len(raw) > 1 else None

        def le(x: Any, y: Any) -> bool:  # x <= y, numeric when both are numbers, else text order
            xn, yn = E.decimal_or_none(x), E.decimal_or_none(y)
            return xn <= yn if xn is not None and yn is not None else key_text(x) <= key_text(y)

        if text == "":
            return False
        if op == "gte":
            return lo is None or le(lo, cell)
        if op == "lte":
            return lo is None or le(cell, lo)
        return (lo in (None, "") or le(lo, cell)) and (hi in (None, "") or le(cell, hi))
    return True


def normalize_filters(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for f in filters or []:
        op = f.get("op", "in")
        side = f.get("side", "both")
        if op not in FILTER_OPS or side not in ("bordereaux", "subledger", "both"):
            raise ValidationError(f"Invalid filter: {f}")
        column = str(f.get("column", "")).strip().lower()
        sub_col = str(f.get("subledger_column") or column).strip().lower()
        if not column:
            raise ValidationError("A filter needs a column")
        out.append({"side": side, "op": op, "column": column, "subledger_column": sub_col, "values": f.get("values", [])})
    return out


def apply_filters(rows: list[dict[str, Any]], filters: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    active = []
    for f in filters:
        if f["side"] in (side, "both"):
            col = f["subledger_column"] if side == "subledger" else f["column"]
            active.append({"op": f["op"], "column": col, "values": f["values"]})
    return [r for r in rows if all(_row_passes(r, f) for f in active)] if active else list(rows)


# --- rules ------------------------------------------------------------------


@dataclass
class CompiledRule:
    id: str
    name: str
    text: str
    comparator: str
    sides: dict[str, Any]  # {"bordereaux": ast, "subledger": ast}
    agg: dict[str, str]
    columns: dict[str, list[str]]


def compile_rule(raw: dict[str, Any], index: int, columns: dict[str, set[str]]) -> CompiledRule:
    text = str(raw.get("expression", "")).strip()
    left_t, cmp, right_t = E.split_rule(text)
    la, ra = E.parse_expression(left_t), E.parse_expression(right_t)
    sides: dict[str, Any] = {}
    for node in (la, ra):
        used = {r.side for r in E.refs(node)}
        if len(used) != 1:
            raise ValidationError(
                f"Each side of '{text}' must use columns from exactly one dataset (bordereaux or subledger)."
            )
        side = used.pop()
        if side in sides:
            raise ValidationError(f"Both sides of '{text}' use the {side}; one side must use each dataset.")
        sides[side] = node
    if set(sides) != {"bordereaux", "subledger"}:
        raise ValidationError("A rule must compare a bordereaux expression with a subledger expression.")
    used_cols: dict[str, list[str]] = {}
    for side, node in sides.items():
        cols = sorted({r.column for r in E.refs(node)})
        missing = [c for c in cols if c not in columns[side]]
        if missing:
            raise ValidationError(f"Unknown {side} column(s): {', '.join(missing)}", details=[{"field": "expression", "message": f"Unknown {side} column(s): {', '.join(missing)}"}])
        used_cols[side] = cols
    agg = {"bordereaux": str(raw.get("bordereaux_agg", raw.get("agg", "SUM"))).upper(), "subledger": str(raw.get("subledger_agg", raw.get("agg", "SUM"))).upper()}
    if any(a not in AGGREGATIONS for a in agg.values()):
        raise ValidationError(f"Aggregation must be one of {sorted(AGGREGATIONS)}")
    # "subledger.x = bordereaux.y": the left side is the subledger, so an
    # inequality must be mirrored to read bordereaux-vs-subledger.
    left_side = E.refs(la)[0].side
    flip = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
    return CompiledRule(
        id=str(raw.get("id") or f"R{index + 1}"),
        name=str(raw.get("name") or f"Rule {index + 1}"),
        text=text,
        comparator=flip.get(cmp, cmp) if left_side == "subledger" else cmp,
        sides=sides,
        agg=agg,
        columns=used_cols,
    )


def _aggregate(values: list[Decimal], how: str) -> Decimal:
    if how == "COUNT":
        return Decimal(len(values))
    if not values:
        return Decimal(0)
    if how == "SUM":
        return sum(values, Decimal(0))
    if how == "AVG":
        return sum(values, Decimal(0)) / len(values)
    return min(values) if how == "MIN" else max(values)


def _side_groups(
    rows: list[dict[str, Any]], rule: CompiledRule, side: str, group_cols: list[str]
) -> dict[tuple[str, ...], dict[str, Any]]:
    node, how = rule.sides[side], rule.agg[side]
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    for r in rows:
        key = tuple(key_text(r.get(c)) for c in group_cols)
        g = groups.setdefault(
            key, {"labels": [("" if r.get(c) is None else str(r.get(c))) for c in group_cols], "values": [], "rows": 0, "null_operands": 0, "div_zero": 0}
        )
        g["rows"] += 1
        nulls: list[int] = []
        try:
            g["values"].append(E.evaluate(node, lambda col, r=r: E.decimal_or_none(r.get(col)), nulls))
        except E.DivisionByZero:
            g["div_zero"] += 1
        g["null_operands"] += len(nulls)
    for g in groups.values():
        g["value"] = _aggregate(g.pop("values"), how)
    return groups


def _quantize(d: Decimal) -> str:
    return str(d.quantize(_CENT, rounding=ROUND_HALF_UP))


def run_rule(
    rule: CompiledRule,
    b_rows: list[dict[str, Any]],
    s_rows: list[dict[str, Any]],
    group_by: list[dict[str, str]],
    tol: Tolerance,
) -> dict[str, Any]:
    b_cols = [g["bordereaux"] for g in group_by]
    s_cols = [g["subledger"] for g in group_by]
    bg = _side_groups(b_rows, rule, "bordereaux", b_cols)
    sg = _side_groups(s_rows, rule, "subledger", s_cols)
    keys = sorted(set(bg) | set(sg))
    out_groups: list[dict[str, Any]] = []
    counts = {s: 0 for s in STATUSES}
    tot_l = tot_r = Decimal(0)
    for key in keys:
        b, s = bg.get(key), sg.get(key)
        left, right = (b["value"] if b else Decimal(0)), (s["value"] if s else Decimal(0))
        tot_l, tot_r = tot_l + left, tot_r + right
        variance = left - right
        pct = variance / max(abs(right), _EPS) if (s or b) else None
        if b is None:
            status = "ONLY_IN_SUBLEDGER"
        elif s is None:
            status = "ONLY_IN_BORDEREAUX"
        else:
            status = "MATCHED" if _holds(rule.comparator, variance, pct, tol) else "VARIANCE"
        counts[status] += 1
        out_groups.append(
            {
                "key": list(key),
                "labels": (b or s)["labels"],
                "bordereaux_value": _quantize(left),
                "subledger_value": _quantize(right),
                "variance": _quantize(variance),
                "variance_pct": None if pct is None else str(pct.quantize(Decimal("0.000001"))),
                "status": status,
                "bordereaux_rows": b["rows"] if b else 0,
                "subledger_rows": s["rows"] if s else 0,
                "null_operands": (b["null_operands"] if b else 0) + (s["null_operands"] if s else 0),
                "div_by_zero_rows": (b["div_zero"] if b else 0) + (s["div_zero"] if s else 0),
            }
        )
    total_var = tot_l - tot_r
    total_pct = total_var / max(abs(tot_r), _EPS)
    total_ok = _holds(rule.comparator, total_var, total_pct, tol)
    detail_bad = counts["VARIANCE"] + counts["ONLY_IN_BORDEREAUX"] + counts["ONLY_IN_SUBLEDGER"]
    out_groups.sort(key=lambda g: (g["status"] == "MATCHED", -abs(Decimal(g["variance"]))))
    return {
        "rule_id": rule.id,
        "name": rule.name,
        "expression": rule.text,
        "comparator": rule.comparator,
        "bordereaux_expression": E.to_text(rule.sides["bordereaux"]),
        "subledger_expression": E.to_text(rule.sides["subledger"]),
        "aggregation": rule.agg,
        "grain": [g.get("label") or g["bordereaux"] for g in group_by] or ["(total)"],
        "totals": {
            "bordereaux": _quantize(tot_l),
            "subledger": _quantize(tot_r),
            "variance": _quantize(total_var),
            "variance_pct": str(total_pct.quantize(Decimal("0.000001"))),
            "within_tolerance": total_ok,
        },
        "counts": counts,
        "status": "RECONCILED" if detail_bad == 0 else "UNRECONCILED",
        "offsetting_differences": bool(total_ok and detail_bad),
        "groups": out_groups,
    }


def _holds(cmp: str, variance: Decimal, pct: Decimal | None, tol: Tolerance) -> bool:
    if cmp == "=":
        return tol.within(variance, pct)
    if cmp == "!=":
        return not tol.within(variance, pct)
    # inequalities compare the aggregated sides: left (cmp) right, with tolerance on the edge
    if cmp in ("<=", "<"):
        return variance <= tol.absolute if cmp == "<=" else variance < 0
    return variance >= -tol.absolute if cmp == ">=" else variance > 0


def validate_group_by(group_by: list[dict[str, Any]] | None, columns: dict[str, set[str]]) -> list[dict[str, str]]:
    out = []
    for g in group_by or []:
        b = str(g.get("bordereaux", "")).strip().lower()
        s = str(g.get("subledger", "")).strip().lower()
        if b not in columns["bordereaux"] or s not in columns["subledger"]:
            raise ValidationError(f"Unknown group-by column pair: bordereaux.{b} / subledger.{s}")
        out.append({"bordereaux": b, "subledger": s, "label": g.get("label") or b})
    return out


def reconcile(
    b_rows: list[dict[str, Any]],
    s_rows: list[dict[str, Any]],
    columns: dict[str, set[str]],
    rules: list[dict[str, Any]],
    group_by: list[dict[str, Any]] | None,
    filters: list[dict[str, Any]] | None,
    tolerance: dict[str, Any] | None,
) -> dict[str, Any]:
    if not rules:
        raise ValidationError("Add at least one rule")
    compiled = [compile_rule(r, i, columns) for i, r in enumerate(rules)]
    grouping = validate_group_by(group_by, columns)
    flt = normalize_filters(filters)
    tol = parse_tolerance(tolerance)
    fb, fs = apply_filters(b_rows, flt, "bordereaux"), apply_filters(s_rows, flt, "subledger")
    results = [run_rule(c, fb, fs, grouping, tol) for c in compiled]
    return {
        "filters": flt,
        "group_by": grouping,
        "tolerance": {"absolute": str(tol.absolute), "percentage": str(tol.percentage), "evaluation": tol.evaluation},
        "rows_in_scope": {"bordereaux": len(fb), "subledger": len(fs), "bordereaux_total": len(b_rows), "subledger_total": len(s_rows)},
        "rules": results,
        "status": "RECONCILED" if all(r["status"] == "RECONCILED" for r in results) else "UNRECONCILED",
    }
