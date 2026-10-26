from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.cleaning.service import get_latest_cleaning_result, list_cleaning_history, rerun_cleaning, run_cleaning
from bordereaux.core.exceptions import NotFoundError
from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run
from bordereaux.models.project import Project, User
from bordereaux.storage.local import LocalStorageService

pytestmark = pytest.mark.unit

_CSV = b"A;B\n1;2\n3;4\n"  # semicolon-delimited


async def test_rerun_preserves_prior_attempt_and_creates_new_one(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", _CSV, user.id)
    run = result["run"]
    version = await validate_processing_run(db_session, storage, run.id, user.id)
    assert version.structure["detected_delimiter"] == ";"

    first = await run_cleaning(db_session, storage, run.id, user.id)
    assert first.attempt_number == 1

    second = await rerun_cleaning(db_session, storage, run.id, user.id, "please re-check dates")
    assert second.attempt_number == 2

    history = await list_cleaning_history(db_session, run.id)
    assert [h.attempt_number for h in history] == [1, 2]
    assert history[0].status == "RETRIED"
    assert history[1].status == "PENDING_REVIEW"

    latest = await get_latest_cleaning_result(db_session, run.id)
    assert latest.attempt_number == 2


async def test_cleaning_result_not_found_before_any_run(db_session: AsyncSession, project: Project, user: User):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await get_latest_cleaning_result(db_session, uuid4())
