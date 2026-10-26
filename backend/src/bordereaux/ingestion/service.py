"""Steps 1-2: upload (``create_processing_run_with_upload``) and parse/validate
(``validate_processing_run``) of a bordereaux file.

Design notes (resolved ambiguities, documented per the implementation
command's instruction to pick the safest non-destructive behaviour):

- Upload persists the raw file immutably and advances the run to
  ``FILE_UPLOADED`` *regardless* of whether sheet selection is still needed -
  the raw bytes are a fact independent of how we interpret them. Multi-sheet
  resolution happens at ``/validate`` time, which is also where the real
  parse + header detection occurs. This means ``/validate`` must be called
  with a ``sheet_name`` for multi-sheet workbooks when the upload didn't
  already supply one; if it still can't resolve the sheet, it raises
  ``ValidationError`` with the sheet list in ``details`` rather than parsing
  the wrong sheet.
- Re-validating (e.g. after a failed first attempt with the wrong sheet) is
  allowed to happen multiple times only while the run is still
  ``FILE_UPLOADED`` - once ``FILE_VALIDATED``, re-parsing goes through the
  normal state machine (not implemented as a distinct endpoint in iteration 1
  since nothing downstream of validate needs re-parsing other than the
  cleaning rerun loop, which operates on the already-parsed version).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, StateError, ValidationError
from bordereaux.core.models import (
    ActorType,
    AuditAction,
    FileFormat,
    ProcessingRunStatus,
    SourceAssetStatus,
    SourceVersionStatus,
)
from bordereaux.core.utils import model_snapshot, sha256_hex, to_jsonable
from bordereaux.ingestion.csv_adapter import parse_csv_rows
from bordereaux.ingestion.detection import CONTENT_TYPES, detect_format
from bordereaux.ingestion.structure import detect_structure
from bordereaux.ingestion.xlsx_adapter import list_sheet_names, parse_xlsx_rows
from bordereaux.models.asset import SourceAsset, SourceVersion
from bordereaux.models.project import Project
from bordereaux.models.run import ProcessingRun
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.storage.service import StorageService


async def create_processing_run_with_upload(
    db: AsyncSession,
    storage: StorageService,
    project_id: UUID,
    filename: str,
    content: bytes,
    actor_id: UUID,
    sheet_name: str | None = None,
) -> dict[str, Any]:
    """Validate + persist the raw upload, create the ``ProcessingRun`` +
    ``SourceAsset``, advance to ``FILE_UPLOADED``. Returns
    ``{"run": ProcessingRun, "asset": SourceAsset, "sheets": list[str] | None}``
    - ``sheets`` is populated when the workbook has multiple sheets and
    ``sheet_name`` was not supplied, so the caller can choose one at
    ``/validate`` time."""
    file_format = detect_format(filename, content)  # raises before any persistence
    project = await db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise NotFoundError("Project not found", details={"project_id": str(project_id)})
    checksum = sha256_hex(content)

    sheets_info: list[str] | None = None
    if file_format is FileFormat.XLSX:
        sheets = list_sheet_names(content)
        if sheet_name is not None and sheet_name not in sheets:
            raise ValidationError(
                f"Sheet '{sheet_name}' not found in workbook.", details={"available_sheets": sheets}
            )
        if sheet_name is None and len(sheets) > 1:
            sheets_info = sheets

    run = ProcessingRun(project_id=project_id, created_by=actor_id)
    db.add(run)
    await db.flush()

    ext = Path(filename).suffix.lower()
    asset = SourceAsset(
        project_id=project_id,
        name=filename,
        original_filename=filename,
        storage_path=f"assets/{run.id}/original{ext}",
        size_bytes=len(content),
        checksum=checksum,
        format=file_format.value,
        status=SourceAssetStatus.UPLOADED.value,
        created_by=actor_id,
        metadata_={"sheet_name": sheet_name} if sheet_name else {},
    )
    db.add(asset)
    await db.flush()

    await storage.upload(asset.storage_path, content, content_type=CONTENT_TYPES[file_format])

    run.source_asset_id = asset.id
    await db.flush()

    await AuditService(db).log(
        event_type="asset.uploaded",
        target_type="SourceAsset",
        target_id=asset.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(asset),
        project_id=project_id,
    )

    sm = ProcessingRunStateMachine(db)
    run = await sm.mark_file_uploaded(run.id, actor_id)  # commits everything above

    return {"run": run, "asset": asset, "sheets": sheets_info}


async def validate_processing_run(
    db: AsyncSession,
    storage: StorageService,
    run_id: UUID,
    actor_id: UUID,
    sheet_name: str | None = None,
) -> SourceVersion:
    """Step 2 (first half): parse the raw file, detect header/structure, and
    persist the result as a new ``SourceVersion``. Advances
    ``FILE_UPLOADED -> FILE_VALIDATED``."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.FILE_UPLOADED.value:
        raise StateError(
            f"Run must be FILE_UPLOADED to validate (current status: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    if run.source_asset_id is None:
        raise StateError("Run has no uploaded asset to validate")

    asset = await db.get(SourceAsset, run.source_asset_id)
    if asset is None:
        raise NotFoundError("Source asset not found", details={"asset_id": str(run.source_asset_id)})

    content = await storage.download(asset.storage_path)
    file_format = FileFormat(asset.format)

    chosen_sheet: str | None = sheet_name or (asset.metadata_ or {}).get("sheet_name")
    encoding: str | None = None
    delimiter: str | None = None

    if file_format is FileFormat.XLSX:
        sheets = list_sheet_names(content)
        if chosen_sheet is None:
            if len(sheets) > 1:
                raise ValidationError(
                    "This workbook has multiple sheets; sheet_name is required.",
                    details={"available_sheets": sheets},
                )
            chosen_sheet = sheets[0]
        elif chosen_sheet not in sheets:
            raise ValidationError(
                f"Sheet '{chosen_sheet}' not found in workbook.", details={"available_sheets": sheets}
            )
        rows = parse_xlsx_rows(content, chosen_sheet)
    else:
        rows, encoding, delimiter = parse_csv_rows(content)
        chosen_sheet = None

    structure = detect_structure(rows)
    column_names = structure.column_names

    data_rows: list[dict[str, Any]] = []
    for r_idx in range(structure.data_start_row, structure.data_end_row + 1):
        raw_row = list(rows[r_idx]) if r_idx < len(rows) else []
        if len(raw_row) < len(column_names):
            raw_row = raw_row + [None] * (len(column_names) - len(raw_row))
        values = dict(zip(column_names, raw_row[: len(column_names)]))
        data_rows.append({"row_number": r_idx + 1, "values": values})  # 1-indexed, matches the source file

    parsed_payload = {"columns": column_names, "rows": data_rows}
    parsed_bytes = json.dumps(to_jsonable(parsed_payload)).encode("utf-8")

    version_count = (
        await db.execute(select(func.count(SourceVersion.id)).where(SourceVersion.asset_id == asset.id))
    ).scalar_one()
    version_number = version_count + 1
    version_path = f"assets/{asset.id}/versions/{version_number}/parsed.json"
    # A failed validation can leave this file behind; the retry (e.g. another sheet) rewrites it.
    await storage.upload(version_path, parsed_bytes, content_type="application/json", overwrite=True)

    version = SourceVersion(
        asset_id=asset.id,
        version_number=version_number,
        storage_path=version_path,
        row_count=len(data_rows),
        column_count=len(column_names),
        status=SourceVersionStatus.PARSED.value,
        structure={
            "header_row": structure.header_row,
            "data_start_row": structure.data_start_row,
            "data_end_row": structure.data_end_row,
            "column_names": column_names,
            "detected_encoding": encoding,
            "detected_delimiter": delimiter,
            "sheet_name": chosen_sheet,
        },
        parse_errors=[],
    )
    db.add(version)
    await db.flush()

    asset.status = SourceAssetStatus.PARSED.value
    run.source_version_id = version.id
    await db.flush()

    await AuditService(db).log(
        event_type="asset.parsed",
        target_type="SourceVersion",
        target_id=version.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(version),
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.mark_file_validated(run_id, actor_id)  # commits everything above

    return version


async def load_parsed_dataset(storage: StorageService, version: SourceVersion) -> dict[str, Any]:
    """Download and decode the JSON parsed dataset for a ``SourceVersion``."""
    raw = await storage.download(version.storage_path)
    return json.loads(raw)
