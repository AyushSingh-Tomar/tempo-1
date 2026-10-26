"""Job lifecycle service (ADR-006), **synchronous in-process** for iteration 1.

There is no queue/worker yet: ``JobService.run()`` executes the handler
immediately, inline, in the caller's coroutine. It still writes a full
``jobs`` row through the real lifecycle so that callers - and the frontend
polling ``GET /jobs/{id}`` - are already coded against the same interface a
future database-backed async worker will provide::

    PENDING --start--> RUNNING --complete--> SUCCEEDED
       |                  |------fail-----> FAILED
       |--cancel/fail-->  |-----cancel----> CANCELLED

Transaction semantics (important):
    Every lifecycle transition (create / start / complete / fail / cancel)
    **commits** the session, exactly as a separate worker process would make
    the job row durable. Inside ``run()`` this gives the right failure
    behaviour: the handler's own writes are committed together with SUCCEEDED,
    or rolled back (everything since RUNNING) before FAILED is recorded - so a
    FAILED job row always survives, and partial handler output never does.
    ``update_progress`` only flushes (committing it would commit half-done
    handler work).

    Consequence for callers: anything pending in the session *before* calling
    ``create()``/``run()`` is committed by it. Do your pre-job writes first, or
    accept that they become durable when the job is created.

Every lifecycle transition is audit-logged (``job.created``, ``job.started``,
``job.succeeded``, ``job.failed``, ``job.cancelled``) in the same transaction.
"""

from __future__ import annotations

import traceback as tb
from typing import Any, Awaitable, Callable, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import ApplicationError, ConflictError, NotFoundError, StateError, ValidationError
from bordereaux.core.models import ActorType, AuditAction, JobStatus, JobType
from bordereaux.core.utils import model_snapshot, to_jsonable, utcnow
from bordereaux.models.job import Job


class ProgressCallback(Protocol):
    async def __call__(
        self,
        percentage: int,
        step: str | None = None,
        message: str | None = None,
        total_steps: int | None = None,
    ) -> None: ...


JobHandler = Callable[[Job, ProgressCallback], Awaitable[dict[str, Any] | None]]

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.PENDING.value: {JobStatus.RUNNING.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value},
    JobStatus.RUNNING.value: {JobStatus.SUCCEEDED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value},
    JobStatus.SUCCEEDED.value: set(),
    JobStatus.FAILED.value: set(),
    JobStatus.CANCELLED.value: set(),
}

JOB_TARGET_TYPE = "Job"


class JobServiceProtocol(Protocol):
    async def create(
        self,
        job_type: JobType | str,
        created_by: UUID,
        project_id: UUID | None = None,
        input: dict[str, Any] | None = None,
    ) -> Job: ...

    async def get(self, job_id: UUID) -> Job: ...

    async def start(self, job_id: UUID) -> Job: ...

    async def update_progress(
        self,
        job_id: UUID,
        percentage: int,
        current_step: str | None = None,
        message: str | None = None,
        total_steps: int | None = None,
    ) -> Job: ...

    async def complete(self, job_id: UUID, output: dict[str, Any] | None = None) -> Job: ...

    async def fail(
        self,
        job_id: UUID,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        traceback: str | None = None,
    ) -> Job: ...

    async def cancel(self, job_id: UUID, actor_id: UUID | None = None) -> Job: ...

    async def run(
        self,
        job_type: JobType | str,
        handler: JobHandler,
        *,
        created_by: UUID,
        project_id: UUID | None = None,
        input: dict[str, Any] | None = None,
        raise_on_failure: bool = False,
    ) -> Job: ...


class JobService:
    def __init__(
        self,
        session: AsyncSession,
        audit: AuditService | None = None,
        max_concurrent_per_project: int = 3,
    ) -> None:
        self._session = session
        self._audit = audit or AuditService(session)
        self._max_concurrent = max_concurrent_per_project

    # ---------------------------------------------------------------- queries

    async def get(self, job_id: UUID) -> Job:
        job = await self._session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found", details={"job_id": str(job_id)})
        return job

    async def list_jobs(
        self,
        project_id: UUID | None = None,
        status: JobStatus | str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        stmt = select(Job)
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
        if status is not None:
            stmt = stmt.where(Job.status == JobStatus(status).value)
        stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_active(self, project_id: UUID) -> int:
        stmt = select(func.count(Job.id)).where(
            Job.project_id == project_id,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
        )
        return int((await self._session.execute(stmt)).scalar_one())

    # ------------------------------------------------------------- lifecycle

    async def create(
        self,
        job_type: JobType | str,
        created_by: UUID,
        project_id: UUID | None = None,
        input: dict[str, Any] | None = None,  # noqa: A002 - matches the jobs.input column
    ) -> Job:
        try:
            type_value = JobType(job_type).value
        except ValueError as exc:
            raise ValidationError(f"Unknown job type: {job_type!r}") from exc
        if project_id is not None and await self.count_active(project_id) >= self._max_concurrent:
            raise ConflictError(
                f"Maximum {self._max_concurrent} concurrent jobs per project",
                code="JOB_CONCURRENCY_LIMIT",
                details={"project_id": str(project_id)},
            )
        job = Job(
            type=type_value,
            status=JobStatus.PENDING.value,
            project_id=project_id,
            input=to_jsonable(input or {}),
            output=None,
            progress={"percentage": 0, "current_step": None, "total_steps": None, "message": None},
            error=None,
            created_by=created_by,
            created_at=utcnow(),
        )
        self._session.add(job)
        await self._session.flush()
        await self._audit.log(
            event_type="job.created",
            target_type=JOB_TARGET_TYPE,
            target_id=job.id,
            action=AuditAction.CREATE,
            actor_id=created_by,
            actor_type=ActorType.USER,
            after_state=model_snapshot(job),
            project_id=project_id,
        )
        await self._session.commit()
        return job

    async def start(self, job_id: UUID) -> Job:
        job = await self.get(job_id)
        before = model_snapshot(job)
        self._transition(job, JobStatus.RUNNING)
        job.started_at = utcnow()
        await self._log_transition(job, "job.started", AuditAction.EXECUTE, before)
        await self._session.commit()
        return job

    async def update_progress(
        self,
        job_id: UUID,
        percentage: int,
        current_step: str | None = None,
        message: str | None = None,
        total_steps: int | None = None,
    ) -> Job:
        job = await self.get(job_id)
        if job.status != JobStatus.RUNNING.value:
            raise StateError(
                "Progress can only be reported for RUNNING jobs",
                details={"job_id": str(job_id), "status": job.status},
            )
        if not isinstance(percentage, int) or isinstance(percentage, bool) or not 0 <= percentage <= 100:
            raise ValidationError("percentage must be an integer between 0 and 100")
        # Re-assign a new dict so SQLAlchemy detects the JSON change.
        job.progress = {
            "percentage": percentage,
            "current_step": current_step,
            "total_steps": total_steps,
            "message": message,
        }
        await self._session.flush()
        return job

    async def complete(self, job_id: UUID, output: dict[str, Any] | None = None) -> Job:
        job = await self.get(job_id)
        before = model_snapshot(job)
        self._transition(job, JobStatus.SUCCEEDED)
        job.output = to_jsonable(output or {})
        job.progress = {**(job.progress or {}), "percentage": 100}
        job.completed_at = utcnow()
        await self._log_transition(job, "job.succeeded", AuditAction.EXECUTE, before)
        await self._session.commit()
        return job

    async def fail(
        self,
        job_id: UUID,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        traceback: str | None = None,
    ) -> Job:
        job = await self.get(job_id)
        before = model_snapshot(job)
        self._transition(job, JobStatus.FAILED)
        job.error = {
            "code": code,
            "message": message,
            "details": to_jsonable(details) if details else None,
            "traceback": traceback,
        }
        job.completed_at = utcnow()
        await self._log_transition(
            job, "job.failed", AuditAction.EXECUTE, before, metadata={"error_code": code}
        )
        await self._session.commit()
        return job

    async def cancel(self, job_id: UUID, actor_id: UUID | None = None) -> Job:
        job = await self.get(job_id)
        before = model_snapshot(job)
        self._transition(job, JobStatus.CANCELLED)
        job.completed_at = utcnow()
        await self._log_transition(job, "job.cancelled", AuditAction.UPDATE, before, actor_id=actor_id)
        await self._session.commit()
        return job

    # ------------------------------------------------------------ execution

    async def run(
        self,
        job_type: JobType | str,
        handler: JobHandler,
        *,
        created_by: UUID,
        project_id: UUID | None = None,
        input: dict[str, Any] | None = None,  # noqa: A002
        raise_on_failure: bool = False,
    ) -> Job:
        """Create a job and execute ``handler`` inline through the full lifecycle.

        ``handler(job, progress)`` returns the job output dict (or None) and may
        ``await progress(percentage, step=..., message=...)``. Its DB writes use
        this same session and are committed atomically with SUCCEEDED.

        On handler exception the session is rolled back, the job is marked
        FAILED (error code taken from ``ApplicationError.code`` or
        ``INTERNAL_ERROR``) and the FAILED job is returned - or the original
        exception is re-raised if ``raise_on_failure=True`` (the FAILED row is
        already committed either way).
        """
        job = await self.create(job_type, created_by=created_by, project_id=project_id, input=input)
        job_id = job.id
        await self.start(job_id)

        async def progress(
            percentage: int,
            step: str | None = None,
            message: str | None = None,
            total_steps: int | None = None,
        ) -> None:
            await self.update_progress(job_id, percentage, current_step=step, message=message, total_steps=total_steps)

        try:
            output = await handler(job, progress)
        except Exception as exc:
            await self._session.rollback()
            if isinstance(exc, ApplicationError):
                code, message, details = exc.code, exc.message, {"errors": exc.details} if exc.details else None
            else:
                code, message, details = "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}", None
            failed = await self.fail(job_id, code, message, details=details, traceback=tb.format_exc())
            if raise_on_failure:
                raise
            return failed
        return await self.complete(job_id, output)

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _transition(job: Job, target: JobStatus) -> None:
        if target.value not in _ALLOWED_TRANSITIONS.get(job.status, set()):
            raise StateError(
                f"Illegal job transition {job.status} -> {target.value}",
                code="INVALID_JOB_TRANSITION",
                details={"job_id": str(job.id), "from": job.status, "to": target.value},
            )
        job.status = target.value

    async def _log_transition(
        self,
        job: Job,
        event_type: str,
        action: AuditAction,
        before: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._session.flush()
        await self._audit.log(
            event_type=event_type,
            target_type=JOB_TARGET_TYPE,
            target_id=job.id,
            action=action,
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
            before_state={"status": before["status"]},
            after_state={"status": job.status, "progress": job.progress, "error": job.error},
            metadata=metadata,
            project_id=job.project_id,
        )
