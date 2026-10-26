"""Read CSV / TSV / TXT, XLSX and SAS7BDAT files into ``(columns, rows)``.

Every row carries ``_source_row`` (the row number in the original file) so
the combined dataset keeps lineage. Raw bytes are never modified.
"""

from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any

from bordereaux.core.exceptions import ValidationError

FORMAT_BY_EXT = {
    ".csv": "CSV",
    ".tsv": "CSV",
    ".txt": "CSV",
    ".xlsx": "XLSX",
    ".xlsm": "XLSX",
    ".sas7bdat": "SAS7BDAT",
}
TEXT_FORMATS = {"CSV"}
ENCODING_FORMATS = {"CSV", "SAS7BDAT"}  # XLSX is Unicode by definition
SINGLE_SHEET = "(whole file)"
_CELL_LIMIT_ROWS = 1_000_000


def detect_format(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext not in FORMAT_BY_EXT:
        raise ValidationError(
            f"Unsupported file type '{ext or filename}'. Upload .xlsx, .csv (or .tsv/.txt) or .sas7bdat files."
        )
    return FORMAT_BY_EXT[ext]


@dataclass
class Table:
    columns: list[str]
    rows: list[dict[str, Any]]
    header_row: int


def _unique_headers(raw: list[Any]) -> list[str]:
    out: list[str] = []
    seen: dict[str, int] = {}
    for i, h in enumerate(raw, start=1):
        name = re.sub(r"\s+", " ", str(h)).strip() if h is not None else ""
        if not name:
            name = f"unnamed_{i}"
        base, n = name, seen.get(name.lower(), 0)
        seen[name.lower()] = n + 1
        out.append(name if n == 0 else f"{base}_{n + 1}")
    return out


def list_sheets(fmt: str, content: bytes) -> list[str]:
    if fmt == "XLSX":
        import openpyxl

        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("Could not open the Excel workbook; is it corrupt or password protected?") from exc
        names = list(wb.sheetnames)
        wb.close()
        return names
    return [SINGLE_SHEET]


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _rows_to_table(grid: list[tuple[int, list[Any]]], header_row: int) -> Table:
    """``grid`` = [(source_row_number, cells)]. ``header_row`` is 1-based among
    the *source* rows; rows above it are ignored."""
    header_idx = next((i for i, (n, _) in enumerate(grid) if n >= header_row), None)
    if header_idx is None:
        return Table([], [], header_row)
    columns = _unique_headers(grid[header_idx][1])
    rows: list[dict[str, Any]] = []
    for n, cells in grid[header_idx + 1 :]:
        if all(_is_blank(c) for c in cells):
            continue
        row = {col: (cells[i] if i < len(cells) else None) for i, col in enumerate(columns)}
        row["_source_row"] = n
        rows.append(row)
    # A trailing all-blank header cell means the column is empty everywhere: keep (schema is truthful).
    return Table(columns, rows, header_row)


def read_csv(content: bytes, encoding: str, header_row: int = 1, delimiter: str | None = None) -> Table:
    text = content.decode(encoding, errors="replace")
    if text.startswith("﻿"):
        text = text[1:]
    if delimiter is None:
        sample = text[:20000]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    grid = [(i, list(r)) for i, r in enumerate(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter), start=1)]
    return _rows_to_table(grid, header_row)


def read_xlsx(content: bytes, sheet: str, header_row: int = 1) -> Table:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        if sheet not in wb.sheetnames:
            raise ValidationError(f"Sheet '{sheet}' not found in workbook.", details=[{"available_sheets": wb.sheetnames}])
        grid = [(i, list(r)) for i, r in enumerate(wb[sheet].iter_rows(values_only=True), start=1)]
    finally:
        wb.close()
    return _rows_to_table(grid, header_row)


def read_sas(content: bytes, encoding: str | None, header_row: int = 1) -> Table:
    try:
        import pyreadstat
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ValidationError("SAS files need the 'pyreadstat' package installed.") from exc
    fd, path = tempfile.mkstemp(suffix=".sas7bdat")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        try:
            data, meta = pyreadstat.read_sas7bdat(path, encoding=encoding or None, output_format="dict")
        except Exception as exc:  # noqa: BLE001 - library raises many types
            raise ValidationError(f"Could not read the SAS file: {exc}") from exc
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    columns = _unique_headers(list(getattr(meta, "column_names", None) or data.keys()))
    keys = list(data.keys())
    n = len(data[keys[0]]) if keys else 0
    rows = []
    for i in range(n):
        row = {columns[j]: data[k][i] for j, k in enumerate(keys)}
        if all(_is_blank(v) or (isinstance(v, float) and v != v) for v in row.values()):
            continue
        row = {k: (None if isinstance(v, float) and v != v else v) for k, v in row.items()}  # NaN -> None
        row["_source_row"] = i + 1
        rows.append(row)
    return Table(columns, rows, 1)


def read_table(fmt: str, content: bytes, sheet: str, encoding: str | None, header_row: int = 1) -> Table:
    if fmt == "XLSX":
        return read_xlsx(content, sheet, header_row)
    if fmt == "SAS7BDAT":
        return read_sas(content, encoding, header_row)
    return read_csv(content, encoding or "utf-8", header_row)
