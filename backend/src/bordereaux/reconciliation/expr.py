"""Tiny, safe arithmetic language for reconciliation rules.

    bordereaux.gross_premium + bordereaux.tax = subledger.amount_total

* operands: ``bordereaux.<column>`` / ``subledger.<column>`` (``b.`` / ``s.``
  accepted as short aliases), numbers, ``abs(...)``
* operators: ``+ - * /``, unary minus, parentheses
* comparison (rule level): ``=`` (default), ``!=``, ``<=``, ``>=``, ``<``, ``>``

Parsed to an AST and interpreted with ``Decimal`` - never ``eval``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from bordereaux.core.exceptions import ValidationError

SIDES = {"bordereaux": "bordereaux", "b": "bordereaux", "subledger": "subledger", "s": "subledger"}
_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<ref>[A-Za-z_]+\.[A-Za-z_][A-Za-z0-9_]*)|(?P<fn>abs)\s*\(|(?P<op>[-+*/()]))"
)
_COMPARATORS = ["<=", ">=", "!=", "==", "=", "<", ">"]


@dataclass(frozen=True)
class Num:
    value: Decimal


@dataclass(frozen=True)
class Ref:
    side: str
    column: str


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Neg:
    operand: Any


@dataclass(frozen=True)
class Abs:
    operand: Any


def _tokenize(text: str) -> list[tuple[str, str]]:
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ValidationError(f"Cannot read the expression near '{text[pos:pos + 15]}'")
        pos = m.end()
        if m.group("num"):
            out.append(("num", m.group("num")))
        elif m.group("ref"):
            out.append(("ref", m.group("ref")))
        elif m.group("fn"):
            out.append(("fn", "abs"))
            out.append(("op", "("))
        else:
            out.append(("op", m.group("op")))
    return out


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.t, self.i = tokens, 0

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ValidationError("The expression ends unexpectedly")
        self.i += 1
        return tok

    def expr(self) -> Any:
        node = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            node = BinOp(self.take()[1], node, self.term())
        return node

    def term(self) -> Any:
        node = self.factor()
        while self.peek() in (("op", "*"), ("op", "/")):
            node = BinOp(self.take()[1], node, self.factor())
        return node

    def factor(self) -> Any:
        kind, val = self.take()
        if kind == "num":
            return Num(Decimal(val))
        if kind == "ref":
            side_raw, column = val.split(".", 1)
            side = SIDES.get(side_raw.lower())
            if side is None:
                raise ValidationError(f"'{side_raw}' is not a dataset - use 'bordereaux.' or 'subledger.' before the column name")
            return Ref(side, column.lower())
        if (kind, val) == ("op", "-"):
            return Neg(self.factor())
        if kind == "fn":
            self.take()  # "("
            node = self.expr()
            if self.take() != ("op", ")"):
                raise ValidationError("Missing ')' after abs(...)")
            return Abs(node)
        if (kind, val) == ("op", "("):
            node = self.expr()
            if self.take() != ("op", ")"):
                raise ValidationError("Missing ')'")
            return node
        raise ValidationError(f"Unexpected '{val}' in the expression")


def parse_expression(text: str) -> Any:
    tokens = _tokenize(text)
    if not tokens:
        raise ValidationError("The expression is empty")
    p = _Parser(tokens)
    node = p.expr()
    if p.peek() is not None:
        raise ValidationError(f"Unexpected '{p.peek()[1]}' in the expression")
    return node


def refs(node: Any) -> list[Ref]:
    if isinstance(node, Ref):
        return [node]
    if isinstance(node, BinOp):
        return refs(node.left) + refs(node.right)
    if isinstance(node, (Neg, Abs)):
        return refs(node.operand)
    return []


def to_text(node: Any) -> str:
    if isinstance(node, Num):
        return format(node.value, "f")
    if isinstance(node, Ref):
        return f"{node.side}.{node.column}"
    if isinstance(node, BinOp):
        return f"({to_text(node.left)} {node.op} {to_text(node.right)})"
    if isinstance(node, Neg):
        return f"-{to_text(node.operand)}"
    return f"abs({to_text(node.operand)})"


class DivisionByZero(Exception):
    pass


def evaluate(node: Any, get: Callable[[str], Decimal | None], on_null: list[int] | None = None) -> Decimal:
    """``get(column)`` returns the cell as a Decimal or None (blank -> 0, counted in ``on_null``)."""
    if isinstance(node, Num):
        return node.value
    if isinstance(node, Ref):
        v = get(node.column)
        if v is None:
            if on_null is not None:
                on_null.append(1)
            return Decimal(0)
        return v
    if isinstance(node, Neg):
        return -evaluate(node.operand, get, on_null)
    if isinstance(node, Abs):
        return abs(evaluate(node.operand, get, on_null))
    a, b = evaluate(node.left, get, on_null), evaluate(node.right, get, on_null)
    if node.op == "+":
        return a + b
    if node.op == "-":
        return a - b
    if node.op == "*":
        return a * b
    if b == 0:
        raise DivisionByZero()
    return a / b


def split_rule(text: str) -> tuple[str, str, str]:
    """``"a + b = c"`` -> (left, comparator, right). Exactly one comparator."""
    best: tuple[int, str] | None = None
    for cmp in _COMPARATORS:
        idx = text.find(cmp)
        if idx != -1 and (best is None or idx < best[0] or (idx == best[0] and len(cmp) > len(best[1]))):
            best = (idx, cmp)
    if best is None:
        raise ValidationError("A rule needs a comparison, e.g. 'bordereaux.a + bordereaux.b = subledger.c'")
    idx, cmp = best
    left, right = text[:idx], text[idx + len(cmp) :]
    if any(c in right for c in ("=", "<", ">")) and cmp in ("=", "==", "<", ">", "<=", ">=", "!="):
        # a second comparator in the remainder
        if re.search(r"[<>=!]", right):
            raise ValidationError("A rule can contain only one comparison")
    return left.strip(), ("=" if cmp == "==" else cmp), right.strip()


def decimal_or_none(v: Any) -> Decimal | None:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None
