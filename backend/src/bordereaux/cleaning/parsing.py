"""Safe, deterministic value parsing shared by cleaning and standardization.

Never coerces blindly: a value that doesn't parse is returned as ``None``
alongside a boolean indicating failure, so the caller can decide to warn
rather than silently losing/altering data.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_NULL_TOKENS = {"", "n/a", "na", "n.a.", "none", "null", "-", "--", "#n/a", "nil", "nan"}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%b %d, %Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d-%b-%y",
    "%d %b %y",
    "%d-%B-%Y",
    "%d %B %Y",
)

_WS_RE = re.compile(r"\s+")
# A grouped number starts with 1-3 digits and no leading zero: "0,500" is half, not five hundred.
_US_GROUPED_RE = re.compile(r"[+-]?[1-9]\d{0,2}(,\d{3})+(\.\d*)?")
_EU_GROUPED_RE = re.compile(r"[+-]?[1-9]\d{0,2}(\.\d{3})+(,\d*)?")
# One separator then exactly three digits: thousands or decimals depending on the locale.
_AMBIGUOUS_RE = re.compile(r"[+-]?[1-9]\d{0,2}([.,])\d{3}")

NumberLocale = str  # "US": 1,234.50 (comma groups, dot decimal) | "EU": 1.234,50 (dot groups, comma decimal)


def _normalize_separators(s: str, locale: NumberLocale | None = None) -> str | None:
    """Rewrite a number with thousands/decimal separators into plain ``1234.5``.

    ``1,234.50`` and ``1.234,50`` are unambiguous. A lone comma is a thousands
    separator only in a clean ``1,234`` / ``12,345,678`` grouping and a decimal
    comma otherwise (``391707,0``, ``12,5``). The one genuinely ambiguous shape -
    a single separator followed by exactly three digits (``1,234`` / ``1.234``) -
    follows ``locale`` (the column's convention; default US). ``None`` means the
    text mixes separators in a way that cannot be a number."""
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        if _US_GROUPED_RE.fullmatch(s):
            return s.replace(",", "")
        if _EU_GROUPED_RE.fullmatch(s):
            return s.replace(".", "").replace(",", ".")
        return None
    if has_comma:
        if _AMBIGUOUS_RE.fullmatch(s) and locale == "EU":
            return s.replace(",", ".")
        if _US_GROUPED_RE.fullmatch(s):
            return s.replace(",", "")
        if s.count(",") == 1:
            return s.replace(",", ".")
        return None
    if s.count(".") > 1:
        return s.replace(".", "") if _EU_GROUPED_RE.fullmatch(s) else None
    if has_dot and locale == "EU" and _AMBIGUOUS_RE.fullmatch(s):
        return s.replace(".", "")
    return s


def is_null_token(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in _NULL_TOKENS


def normalize_whitespace(text: str) -> str:
    return _WS_RE.sub(" ", text.strip())


def _number_text(value: str) -> tuple[str, bool, bool]:
    """(bare digits-and-separators text, is_negative, is_percent) of a numeric string."""
    s = value.strip()
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1].strip()
    for sym in ("$", "£", "€"):
        s = s.replace(sym, "")
    s = s.strip()
    is_percent = s.endswith("%")
    if is_percent:
        s = s[:-1].strip()
    return s, negative, is_percent


def is_ambiguous_number(value: Any) -> bool:
    """True for ``1,234`` / ``1.234``: only the column's convention says which it is."""
    if not isinstance(value, str) or is_null_token(value):
        return False
    return bool(_AMBIGUOUS_RE.fullmatch(_number_text(value)[0]))


def _separator_evidence(text: str) -> NumberLocale | None:
    """Which convention a single value proves, if it proves one."""
    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        if _US_GROUPED_RE.fullmatch(text):
            return "US"
        return "EU" if _EU_GROUPED_RE.fullmatch(text) else None
    if _AMBIGUOUS_RE.fullmatch(text):
        return None
    if has_comma:
        if _US_GROUPED_RE.fullmatch(text):
            return "US"  # 12,345,678
        return "EU" if text.count(",") == 1 else None  # 391707,0 / 12,5 / 0,500
    if has_dot:
        if text.count(".") > 1:
            return "EU" if _EU_GROUPED_RE.fullmatch(text) else None  # 1.234.567
        return "US"  # 12.5 / 1234.5
    return None


def detect_number_locale(values: list[Any]) -> NumberLocale | None:
    """The number convention a column follows, by majority of the values that prove
    one. ``None`` when nothing (or a tie) decides it - the caller then keeps the
    default and can flag ambiguous values for review."""
    votes = {"US": 0, "EU": 0}
    for v in values:
        if not isinstance(v, str) or is_null_token(v):
            continue
        evidence = _separator_evidence(_number_text(v)[0])
        if evidence:
            votes[evidence] += 1
    if votes["US"] == votes["EU"]:
        return None
    return "US" if votes["US"] > votes["EU"] else "EU"


def try_parse_decimal(value: Any, locale: NumberLocale | None = None) -> tuple[Decimal | None, bool]:
    """Returns ``(parsed_value, success)``. ``success=False`` for anything
    that doesn't deterministically parse as a number (never guesses).
    ``locale`` resolves only the ambiguous ``1,234`` / ``1.234`` shape."""
    if value is None:
        return None, False
    if isinstance(value, bool):
        return None, False
    if isinstance(value, Decimal):
        return value, True
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value)), True
        except InvalidOperation:
            return None, False
    if isinstance(value, str):
        s = value.strip()
        if not s or is_null_token(s):
            return None, False
        s, negative, is_percent = _number_text(s)
        s = _normalize_separators(s, locale)
        if not s:
            return None, False
        try:
            parsed = Decimal(s)
        except InvalidOperation:
            return None, False
        if is_percent:
            parsed = parsed / Decimal(100)
        return (-parsed if negative else parsed), True
    return None, False


_ISO_DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?")


def try_parse_date(value: Any) -> tuple[date | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return value.date(), True
    if isinstance(value, date):
        return value, True
    if isinstance(value, str):
        s = value.strip()
        if not s or is_null_token(s):
            return None, False
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date(), True
            except ValueError:
                continue
        # An Excel date cell reaches us as "2024-03-20T00:00:00" (see to_jsonable).
        if _ISO_DATETIME_RE.fullmatch(s):
            try:
                return datetime.fromisoformat(s).date(), True
            except ValueError:
                pass
        return None, False
    return None, False


def looks_numeric(value: Any) -> bool:
    _, ok = try_parse_decimal(value)
    return ok


def looks_date(value: Any) -> bool:
    _, ok = try_parse_date(value)
    return ok


# Month + year with no day. Two-digit years are not accepted ("Mar-24" is as
# likely 24 March), and neither is a bare year ("2024" is indistinguishable
# from a number).
_PARTIAL_DATE_FORMATS = (
    "%Y-%m", "%Y/%m", "%m/%Y", "%m-%Y",
    "%b %Y", "%b-%Y", "%b/%Y", "%b, %Y", "%B %Y", "%B-%Y", "%B/%Y", "%B, %Y",
)
_PARTIAL_ISO_RE = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


def try_parse_partial_date(value: Any) -> tuple[int, int] | None:
    """``(year, month)`` for a month-and-year value with no day ("Mar-2024",
    "03/2024", "2024-03"); ``None`` for anything else, including a full date."""
    if not isinstance(value, str) or try_parse_date(value)[1]:
        return None
    s = value.strip()
    for fmt in _PARTIAL_DATE_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return parsed.year, parsed.month
    return None


def format_partial_date(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def parse_partial_iso(text: Any) -> tuple[int, int] | None:
    """Inverse of ``format_partial_date`` (``"2024-03"``)."""
    if not isinstance(text, str):
        return None
    m = _PARTIAL_ISO_RE.fullmatch(text.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def looks_partial_date(value: Any) -> bool:
    return try_parse_partial_date(value) is not None
