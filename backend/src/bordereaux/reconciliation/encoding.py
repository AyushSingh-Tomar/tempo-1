"""Choose, and double-check, the text encoding of CSV/TXT/SAS files.

Strategy (deterministic, no AI):

1. A byte-order mark decides outright.
2. Every candidate encoding is tried with a *strict* decode. A candidate that
   cannot decode the bytes is rejected. A candidate that decodes is scored on
   evidence of a wrong guess: replacement characters, control characters,
   and the telltale mojibake pairs that appear when UTF-8 is read as a
   single-byte encoding ("Ã©", "â€™"...).
3. The detector's own best guess (charset-normalizer) breaks near-ties.
4. **Re-check:** the two best candidates are both decoded and compared line by
   line; the lines that differ are returned so a person can see what the
   choice changes. If every candidate reads the file identically (plain ASCII)
   that is reported too.

The user can force an encoding, or restrict the search to a short list. A
forced encoding is still validated and compared; a warning is raised if it
produces suspicious text.
"""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass, field
from typing import Any

#: (value, label) shown in the "encodings to check" dropdown.
SUPPORTED_ENCODINGS: list[tuple[str, str]] = [
    ("utf-8", "UTF-8"),
    ("utf-8-sig", "UTF-8 with BOM"),
    ("utf-16", "UTF-16"),
    ("cp1252", "Windows-1252 (Western European)"),
    ("latin-1", "ISO-8859-1 (Latin-1)"),
    ("iso-8859-15", "ISO-8859-15 (Latin-9, with €)"),
    ("cp1250", "Windows-1250 (Central European)"),
    ("cp1251", "Windows-1251 (Cyrillic)"),
    ("cp437", "IBM CP437 (DOS)"),
    ("cp850", "IBM CP850 (DOS Western)"),
    ("mac-roman", "Mac Roman"),
    ("shift_jis", "Shift-JIS (Japanese)"),
    ("gb18030", "GB18030 (Chinese)"),
    ("big5", "Big5 (Traditional Chinese)"),
    ("euc-kr", "EUC-KR (Korean)"),
]

DEFAULT_CANDIDATES = ["utf-8", "cp1252", "latin-1", "iso-8859-15", "cp1250", "utf-16", "cp437", "mac-roman"]
# canonical codec names; lower = more likely a priori
_PREFERENCE = {
    "utf-8": 0, "utf-8-sig": 0, "utf-16": 1, "utf-32": 1, "cp1252": 2,
    "iso8859-15": 3, "cp1250": 3, "cp1251": 3, "iso8859-1": 4, "cp850": 6, "mac-roman": 6, "cp437": 7,
}
_MOJIBAKE = re.compile("Ã[\u0080-¿]|Â[\u0080-¿]|â€[\u0080-¿™œ‚-„†-…]|Ð[\u0080-¿]")
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_MAX_DIFFS = 10


def canonical_name(name: str) -> str:
    """Python's canonical codec name, or ``ValueError`` if unknown."""
    try:
        return codecs.lookup(name.strip()).name
    except LookupError as exc:
        raise ValueError(f"Unknown encoding {name!r}") from exc


@dataclass
class CandidateResult:
    encoding: str
    decodes_cleanly: bool
    replacement_chars: int = 0
    control_chars: int = 0
    mojibake_pairs: int = 0
    non_ascii_chars: int = 0
    score: float = 0.0
    error: str | None = None
    sample: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "encoding": self.encoding,
            "decodes_cleanly": self.decodes_cleanly,
            "replacement_chars": self.replacement_chars,
            "control_chars": self.control_chars,
            "mojibake_pairs": self.mojibake_pairs,
            "non_ascii_chars": self.non_ascii_chars,
            "score": round(self.score, 4),
            "error": self.error,
            "sample": self.sample,
        }


@dataclass
class EncodingDecision:
    chosen: str
    method: str  # BOM | USER | DETECTED
    candidates: list[CandidateResult]
    all_agree: bool
    differences: list[dict[str, Any]] = field(default_factory=list)
    compared: list[str] = field(default_factory=list)
    detector_guess: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chosen": self.chosen,
            "method": self.method,
            "all_agree": self.all_agree,
            "compared": self.compared,
            "differences": self.differences,
            "detector_guess": self.detector_guess,
            "warnings": self.warnings,
            "candidates": [c.as_dict() for c in self.candidates],
        }


def _bom_encoding(content: bytes) -> str | None:
    if content.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if content.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return "utf-32"
    if content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    return None


def _evaluate(content: bytes, encoding: str) -> CandidateResult:
    if encoding.startswith(("utf-16", "utf-32")) and _bom_encoding(content) is None:
        # Without a BOM, UTF-16 "decodes" almost any even-length byte string.
        if content.count(0) / max(1, len(content)) < 0.2:
            return CandidateResult(encoding, False, error="no BOM and no NUL-byte pattern: not UTF-16/32", score=-1.0)
    try:
        text = content.decode(encoding, errors="strict")
    except (UnicodeDecodeError, LookupError) as exc:
        return CandidateResult(encoding, False, error=str(exc)[:160], score=-1.0)
    replacement = text.count("�")
    control = len(_CONTROL.findall(text))
    mojibake = len(_MOJIBAKE.findall(text))
    non_ascii = sum(1 for ch in text if ord(ch) > 127)
    bad = replacement * 3 + control * 2 + mojibake * 2
    # Penalty is relative to how much non-ASCII text there is to judge.
    score = 1.0 - min(1.0, bad / max(1, non_ascii)) if non_ascii else 1.0
    if encoding in ("utf-8", "utf-8-sig") and non_ascii and bad == 0:
        score += 0.3  # valid multi-byte UTF-8 is very unlikely to arise by chance
    return CandidateResult(
        encoding, True, replacement, control, mojibake, non_ascii, score, None, _sample_non_ascii(text)
    )


def _sample_non_ascii(text: str, width: int = 40) -> str:
    for line in text.splitlines():
        if any(ord(c) > 127 for c in line):
            return line[:width * 2]
    return text[:width]


def _detector_guess(content: bytes) -> str | None:
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(content[:2_000_000]).best()
        return canonical_name(best.encoding) if best is not None else None
    except Exception:  # noqa: BLE001 - the detector is only a tie-breaker
        return None


def _compare(content: bytes, a: str, b: str) -> list[dict[str, Any]]:
    la = content.decode(a, errors="replace").splitlines()
    lb = content.decode(b, errors="replace").splitlines()
    diffs = []
    for i, (x, y) in enumerate(zip(la, lb), start=1):
        if x != y:
            diffs.append({"line": i, a: x[:200], b: y[:200]})
            if len(diffs) >= _MAX_DIFFS:
                break
    return diffs


def decide_encoding(
    content: bytes, user_encoding: str | None = None, candidates: list[str] | None = None
) -> EncodingDecision:
    """See module docstring. ``candidates`` restricts the search (dropdown
    selection); ``user_encoding`` forces the result."""
    names: list[str] = []
    for raw in candidates or DEFAULT_CANDIDATES:
        try:
            n = canonical_name(raw)
        except ValueError:
            continue
        if n not in names:
            names.append(n)
    bom = _bom_encoding(content)
    forced = canonical_name(user_encoding) if user_encoding else None
    if bom and bom not in names:
        names.insert(0, bom)
    if forced and forced not in names:
        names.append(forced)
    guess = _detector_guess(content)

    results = [_evaluate(content, n) for n in names]
    by_name = {r.encoding: r for r in results}
    warnings: list[str] = []

    def base_rank(r: CandidateResult) -> tuple:
        return (r.decodes_cleanly, round(r.score, 1), -_PREFERENCE.get(r.encoding, 9))

    def decoded(name: str) -> str:
        return content.decode(name, errors="replace")

    # The detector's pick may overtake other *common* encodings, but only when
    # it actually reads the file differently - encodings that decode the bytes
    # identically (e.g. cp1252 / cp1250 / latin-1 on "Société") are a tie, and
    # a priori likelihood decides.
    baseline = max(results, key=base_rank)
    use_guess = bool(
        guess and guess in by_name and by_name[guess].decodes_cleanly and baseline.decodes_cleanly
        and decoded(guess) != decoded(baseline.encoding)
    )

    def rank(r: CandidateResult) -> tuple:
        pref = _PREFERENCE.get(r.encoding, 9)
        if use_guess and r.encoding == guess and pref <= 5:
            pref -= 3
        return (r.decodes_cleanly, round(r.score, 1), -pref)

    ranked = sorted(results, key=rank, reverse=True)
    clean = [r for r in ranked if r.decodes_cleanly]

    if forced:
        chosen, method = forced, "USER"
        res = by_name[forced]
        if not res.decodes_cleanly:
            warnings.append(f"{forced} cannot decode this file ({res.error}).")
        elif res.score < 0.8:
            warnings.append(f"{forced} decodes the file but the text looks wrong (mojibake or control characters).")
        elif clean and clean[0].encoding != forced and clean[0].score - res.score > 0.1:
            warnings.append(f"{clean[0].encoding} reads this file noticeably better than the chosen {forced}.")
    elif bom:
        chosen, method = bom, "BOM"
    elif clean:
        chosen, method = clean[0].encoding, "DETECTED"
    else:
        chosen, method = "latin-1", "DETECTED"
        warnings.append("No candidate decoded the file cleanly; falling back to latin-1 (lossless but may be wrong).")

    # Re-check: compare the chosen reading with the best competing reading.
    others = [r for r in clean if r.encoding != chosen]
    compared = [chosen]
    differences: list[dict[str, Any]] = []
    if others:
        rival = others[0].encoding
        compared.append(rival)
        differences = _compare(content, chosen, rival)
    all_agree = bool(clean) and not differences and all(
        content.decode(r.encoding, errors="replace") == content.decode(chosen, errors="replace") for r in clean
    )
    if differences and method != "USER":
        top, runner = by_name[chosen], others[0]
        if abs(top.score - runner.score) < 0.1:
            warnings.append(
                f"{chosen} and {runner.encoding} both read the file plausibly but differ on "
                f"{len(differences)}+ line(s) - review the differences or choose the encoding yourself."
            )
    return EncodingDecision(chosen, method, ranked, all_agree, differences, compared, guess, warnings)
