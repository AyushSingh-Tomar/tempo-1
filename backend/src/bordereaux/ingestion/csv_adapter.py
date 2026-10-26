"""CSV file adapter: bytes -> list of rows (list[list[Any]])."""

from __future__ import annotations

import csv
import io

from bordereaux.core.exceptions import IngestionError

_CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


def parse_csv_rows(
    content: bytes, encoding: str | None = None, delimiter: str | None = None
) -> tuple[list[list[str]], str, str]:
    """Returns ``(rows, detected_encoding, detected_delimiter)``."""
    text: str | None = None
    used_encoding = encoding
    candidates = [encoding] if encoding else list(_CANDIDATE_ENCODINGS)
    for candidate in candidates:
        try:
            text = content.decode(candidate)
            used_encoding = candidate
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise IngestionError("Could not decode CSV content (tried utf-8 and latin-1).")

    used_delimiter = delimiter
    if used_delimiter is None:
        sample = text[:4096]
        try:
            used_delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            used_delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=used_delimiter)
    rows = [list(r) for r in reader]
    if not rows:
        raise IngestionError("CSV file has no rows.")
    return rows, used_encoding, used_delimiter
