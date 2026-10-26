"""Step 2-3 orchestration: run cleaning, acknowledge, request a rerun.

Each cleaning attempt is persisted as a new ``cleaning_results`` row (never
overwritten) and the cleaned dataset as a new derived JSON artifact at a
path keyed by ``(run_id, attempt_number)`` - the raw/parsed source is never
touched. Acknowledging advances the run to mapping review; candidates are
generated once the user has chosen the target format.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.cleaning.rules import clean_dataset
from bordereaux.core.exceptions import NotFoundError, StateError
from bordereaux.core.models import ActorType, AuditAction, CleaningResultStatus, ProcessingRunStatus
from bordereaux.core.utils import model_snapshot, to_jsonable
from bordereaux.ingestion.service import load_parsed_dataset
from bordereaux.models.asset import SourceVersion
from bordereaux.models.cleaning import CleaningResult
from bordereaux.models.run import ProcessingRun
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.storage.service import StorageService


def cleaned_dataset_path(run_id: UUID, attempt_number: int) -> str:
    return f"runs/{run_id}/cleaning/attempt_{attempt_number}/cleaned.json"


async def _next_attempt_number(db: AsyncSession, run_id: UUID) -> int:
    count = (
        await db.execute(select(func.count(CleaningResult.id)).where(CleaningResult.run_id == run_id))
    ).scalar_one()
    return count + 1


async def run_cleaning(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID | None = None
) -> CleaningResult:
    """Execute one cleaning attempt and advance the run to
    ``CLEANING_COMPLETED`` (valid from ``FILE_VALIDATED`` or
    ``CLEANING_REVIEW_PENDING``)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status not in (ProcessingRunStatus.FILE_VALIDATED.value, ProcessingRunStatus.CLEANING_REVIEW_PENDING.value):
        raise StateError(
            f"Run must be FILE_VALIDATED or CLEANING_REVIEW_PENDING to clean (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    if run.source_version_id is None:
        raise StateError("Run has no parsed version to clean")

    version = await db.get(SourceVersion, run.source_version_id)
    if version is None:
        raise NotFoundError("Source version not found", details={"version_id": str(run.source_version_id)})

    parsed = await load_parsed_dataset(storage, version)
    outcome = clean_dataset(parsed)

    attempt_number = await _next_attempt_number(db, run_id)
    cleaned_payload = {"columns": outcome.columns, "rows": outcome.rows, "total_rows": outcome.total_rows}
    await storage.upload(
        cleaned_dataset_path(run_id, attempt_number),
        json.dumps(to_jsonable(cleaned_payload)).encode("utf-8"),
        content_type="application/json",
    )

    result = CleaningResult(
        run_id=run_id,
        attempt_number=attempt_number,
        before_row_count=outcome.before_row_count,
        before_column_count=outcome.before_column_count,
        after_row_count=outcome.after_row_count,
        after_column_count=outcome.after_column_count,
        transformations=to_jsonable(outcome.transformations),
        warnings=to_jsonable(outcome.warnings),
        status=CleaningResultStatus.PENDING_REVIEW.value,
    )
    db.add(result)
    await db.flush()

    await AuditService(db).log(
        event_type="cleaning.completed",
        target_type="CleaningResult",
        target_id=result.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
        after_state=model_snapshot(result),
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.complete_cleaning(run_id, actor_id)  # commits everything above
    return result


async def get_latest_cleaning_result(db: AsyncSession, run_id: UUID) -> CleaningResult:
    stmt = select(CleaningResult).where(CleaningResult.run_id == run_id).order_by(CleaningResult.attempt_number.desc())
    result = (await db.execute(stmt)).scalars().first()
    if result is None:
        raise NotFoundError("No cleaning result for this run yet", details={"run_id": str(run_id)})
    return result


async def list_cleaning_history(db: AsyncSession, run_id: UUID) -> list[CleaningResult]:
    stmt = select(CleaningResult).where(CleaningResult.run_id == run_id).order_by(CleaningResult.attempt_number.asc())
    return list((await db.execute(stmt)).scalars().all())


async def acknowledge_cleaning(db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID) -> ProcessingRun:
    """User acknowledges the (latest) cleaning result. Records the
    acknowledgement as an audit event (NOT as proof the data is correct),
    and advances to ``MAPPING_REVIEW_PENDING``. Mapping candidates are generated
    afterwards, once the user has chosen the target format (default dictionary
    or their own columns)."""
    latest = await get_latest_cleaning_result(db, run_id)
    latest.status = CleaningResultStatus.ACKNOWLEDGED.value
    await db.flush()

    run = await db.get(ProcessingRun, run_id)
    await AuditService(db).log(
        event_type="cleaning.acknowledged",
        target_type="CleaningResult",
        target_id=latest.id,
        action=AuditAction.APPROVE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        metadata={"note": "Acknowledgement records that the user reviewed the result, not that all data is correct."},
        project_id=run.project_id if run else None,
    )

    sm = ProcessingRunStateMachine(db)
    run = await sm.acknowledge_cleaning(run_id, actor_id)  # commits above

    return run


async def rerun_cleaning(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID, reason: str
) -> CleaningResult:
    """User rejects the cleaning result and requests another attempt. The
    previous ``cleaning_results`` row is preserved (new attempt_number)."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.CLEANING_COMPLETED.value:
        raise StateError(
            f"Run must be CLEANING_COMPLETED to request a rerun (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )
    latest = await get_latest_cleaning_result(db, run_id)
    latest.status = CleaningResultStatus.RETRIED.value
    await db.flush()

    sm = ProcessingRunStateMachine(db)
    await sm.request_cleaning_rerun(run_id, actor_id, reason=reason)

    return await run_cleaning(db, storage, run_id, actor_id)
