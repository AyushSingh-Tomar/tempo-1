"""Format detection: validate the uploaded file's *extension* against its
*actual content* (magic bytes / decodability). Mismatches are rejected with a
clear ``IngestionError``/``ValidationError`` - never silently reinterpreted.

Iteration 1 only supports CSV and XLSX (Initial_iteration_implementation_command.md
§1), not the full format list in MODULE_CONTRACTS.md.
"""

from __future__ import annotations

from pathlib import Path

from bordereaux.core.exceptions import IngestionError, ValidationError
from bordereaux.core.models import FileFormat

#: Magic bytes for a well-formed .xlsx (a ZIP archive).
_ZIP_MAGIC = b"PK\x03\x04"

SUPPORTED_EXTENSIONS: dict[str, FileFormat] = {
    ".csv": FileFormat.CSV,
    ".xlsx": FileFormat.XLSX,
}

CONTENT_TYPES: dict[FileFormat, str] = {
    FileFormat.CSV: "text/csv",
    FileFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def detect_format(filename: str, content: bytes) -> FileFormat:
    """Validate ``filename``'s extension against ``content`` and return the
    confirmed :class:`FileFormat`. Raises before any persistence happens."""
    if not filename or not filename.strip():
        raise ValidationError("A filename is required")
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            "Unsupported file type. Only .csv and .xlsx files are supported.",
            details={"filename": filename, "extension": ext},
        )
    if not content:
        raise IngestionError("Uploaded file is empty.", details={"filename": filename})

    claimed = SUPPORTED_EXTENSIONS[ext]
    if claimed is FileFormat.XLSX:
        if not content.startswith(_ZIP_MAGIC):
            raise IngestionError(
                "File has a .xlsx extension but its content is not a valid Excel (zip) file.",
                details={"filename": filename},
            )
    else:  # CSV
        if content.startswith(_ZIP_MAGIC):
            raise IngestionError(
                "File has a .csv extension but its content looks like a binary Excel file.",
                details={"filename": filename},
            )
        sample = content[:65536]
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                sample.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise IngestionError(
                "CSV file content could not be decoded as text (tried utf-8 and latin-1).",
                details={"filename": filename},
            )
    return claimed
