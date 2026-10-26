"""Ingestion module (Steps 1-2 of the Bordereaux Processing Accelerator workflow).

Parses CSV / XLSX uploads, detects multi-row/offset headers and multi-sheet
workbooks, and persists the immutable raw file plus a derived parsed
representation. See ``service.py`` for the orchestration entry points used by
the API routes.
"""

from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run

__all__ = ["create_processing_run_with_upload", "validate_processing_run"]
