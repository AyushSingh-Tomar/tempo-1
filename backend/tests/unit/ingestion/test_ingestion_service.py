from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.exceptions import IngestionError, NotFoundError, StateError, ValidationError
from bordereaux.core.models import ProcessingRunStatus as S
from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run
from bordereaux.models.project import Project, User
from bordereaux.storage.local import LocalStorageService

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[4] / "Initial provided Info" / "Test_files"


def _csv_bytes() -> bytes:
    return b"UMR,Gross Premium,Commission\nUMR-1,1000,100\nUMR-2,2000,200\n"


async def test_upload_csv_creates_run_and_asset(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "claims.csv", _csv_bytes(), user.id)
    assert result["run"].status == S.FILE_UPLOADED.value
    assert result["asset"].format == "CSV"
    assert result["sheets"] is None
    stored = await storage.download(result["asset"].storage_path)
    assert stored == _csv_bytes()


async def test_upload_rejects_wrong_extension(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    with pytest.raises(ValidationError):
        await create_processing_run_with_upload(db_session, storage, project.id, "claims.txt", _csv_bytes(), user.id)


async def test_upload_rejects_malformed_xlsx(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    with pytest.raises(IngestionError):
        await create_processing_run_with_upload(db_session, storage, project.id, "claims.xlsx", b"not a real xlsx", user.id)


async def test_upload_rejects_empty_file(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    with pytest.raises(IngestionError):
        await create_processing_run_with_upload(db_session, storage, project.id, "claims.csv", b"", user.id)


async def test_upload_rejects_binary_disguised_as_csv(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    xlsx_bytes = (FIXTURES / "test_std_01_structural.xlsx").read_bytes() if FIXTURES.exists() else b"PK\x03\x04garbage"
    with pytest.raises(IngestionError):
        await create_processing_run_with_upload(db_session, storage, project.id, "claims.csv", xlsx_bytes, user.id)


async def test_validate_csv_detects_header_and_rows(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "claims.csv", _csv_bytes(), user.id)
    version = await validate_processing_run(db_session, storage, result["run"].id, user.id)
    assert version.row_count == 2
    assert version.column_count == 3
    assert version.structure["column_names"] == ["UMR", "Gross Premium", "Commission"]


async def test_validate_requires_file_uploaded_status(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "claims.csv", _csv_bytes(), user.id)
    await validate_processing_run(db_session, storage, result["run"].id, user.id)
    with pytest.raises(StateError):
        await validate_processing_run(db_session, storage, result["run"].id, user.id)


@pytest.mark.skipif(not FIXTURES.exists(), reason="fixture directory not present")
async def test_multi_row_header_detection(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    content = (FIXTURES / "test_std_01_structural.xlsx").read_bytes()
    result = await create_processing_run_with_upload(
        db_session, storage, project.id, "test_std_01_structural.xlsx", content, user.id, sheet_name="Bordereaux"
    )
    version = await validate_processing_run(db_session, storage, result["run"].id, user.id)
    # Title/metadata rows (rows 1-4) + blank rows precede the real header.
    assert version.structure["header_row"] >= 4
    assert "UMR" in version.structure["column_names"]


@pytest.mark.skipif(not FIXTURES.exists(), reason="fixture directory not present")
async def test_multi_sheet_requires_explicit_sheet_name(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    content = (FIXTURES / "test_std_03_multisheet.xlsx").read_bytes()
    result = await create_processing_run_with_upload(
        db_session, storage, project.id, "test_std_03_multisheet.xlsx", content, user.id
    )
    assert result["sheets"] is not None
    assert "Bordereaux Q1 2024" in result["sheets"]
    with pytest.raises(ValidationError):
        await validate_processing_run(db_session, storage, result["run"].id, user.id)

    version = await validate_processing_run(
        db_session, storage, result["run"].id, user.id, sheet_name="Bordereaux Q1 2024"
    )
    assert version.row_count == 18
    assert version.structure["sheet_name"] == "Bordereaux Q1 2024"


@pytest.mark.skipif(not FIXTURES.exists(), reason="fixture directory not present")
async def test_multi_sheet_rejects_unknown_sheet_name(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    content = (FIXTURES / "test_std_03_multisheet.xlsx").read_bytes()
    with pytest.raises(ValidationError):
        await create_processing_run_with_upload(
            db_session, storage, project.id, "f.xlsx", content, user.id, sheet_name="Does Not Exist"
        )


async def test_validate_not_found_run(db_session: AsyncSession, storage: LocalStorageService, user: User):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await validate_processing_run(db_session, storage, uuid4(), user.id)
