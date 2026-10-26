from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from bordereaux.core.exceptions import ConflictError, IngestionError, NotFoundError, StateError, ValidationError
from bordereaux.jobs.service import JobService
from bordereaux.models import AuditEvent, Job, Project

pytestmark = pytest.mark.unit


async def _reload(session_factory, job_id) -> Job:
    """Read the job through a *separate* session to prove it was persisted (committed)."""
    async with session_factory() as s:
        job = await s.get(Job, job_id)
        assert job is not None
        return job


async def _audit_types(session_factory, job_id) -> list[str]:
    async with session_factory() as s:
        rows = (
            await s.execute(select(AuditEvent).where(AuditEvent.target_id == job_id).order_by(AuditEvent.timestamp))
        ).scalars()
        return [e.event_type for e in rows]


async def test_manual_lifecycle_success(db_session, session_factory, user, project) -> None:
    svc = JobService(db_session)
    job = await svc.create("PARSE", created_by=user.id, project_id=project.id, input={"asset_id": uuid4()})

    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "PENDING"
    assert persisted.progress["percentage"] == 0
    assert isinstance(persisted.input["asset_id"], str)  # UUID made JSON-safe
    assert persisted.started_at is None and persisted.completed_at is None

    await svc.start(job.id)
    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "RUNNING"
    assert persisted.started_at is not None and persisted.started_at.tzinfo is not None

    await svc.update_progress(job.id, 40, current_step="parsing", message="sheet 1", total_steps=3)
    assert job.progress == {"percentage": 40, "current_step": "parsing", "total_steps": 3, "message": "sheet 1"}

    await svc.complete(job.id, {"version_id": "v1"})
    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "SUCCEEDED"
    assert persisted.output == {"version_id": "v1"}
    assert persisted.progress["percentage"] == 100
    assert persisted.completed_at >= persisted.started_at
    assert persisted.error is None

    assert await _audit_types(session_factory, job.id) == ["job.created", "job.started", "job.succeeded"]


async def test_manual_lifecycle_failure(db_session, session_factory, user) -> None:
    svc = JobService(db_session)
    job = await svc.create("CLEAN", created_by=user.id)
    await svc.start(job.id)
    await svc.fail(job.id, "PARSE_FAILED", "bad header", details={"row": 1})
    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "FAILED"
    assert persisted.error == {"code": "PARSE_FAILED", "message": "bad header", "details": {"row": 1}, "traceback": None}
    assert persisted.completed_at is not None
    assert await _audit_types(session_factory, job.id) == ["job.created", "job.started", "job.failed"]


async def test_run_success_commits_handler_work(db_session, session_factory, user, project) -> None:
    svc = JobService(db_session)
    seen_progress = []

    async def handler(job, progress):
        assert job.status == "RUNNING"
        await progress(50, step="half", message="halfway")
        seen_progress.append(dict(job.progress))
        db_session.add(Project(name="created-by-handler", created_by=user.id))
        return {"rows": 10}

    job = await svc.run("STANDARDIZE", handler, created_by=user.id, project_id=project.id, input={"x": 1})
    assert job.status == "SUCCEEDED"
    assert seen_progress[0]["percentage"] == 50 and seen_progress[0]["current_step"] == "half"

    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "SUCCEEDED"
    assert persisted.output == {"rows": 10}
    async with session_factory() as s:
        n = (await s.execute(select(func.count()).where(Project.name == "created-by-handler"))).scalar_one()
        assert n == 1


async def test_run_failure_rolls_back_handler_work_but_keeps_failed_job(
    db_session, session_factory, user, project
) -> None:
    svc = JobService(db_session)

    async def handler(job, progress):
        await progress(10)
        db_session.add(Project(name="should-vanish", created_by=user.id))
        await db_session.flush()
        raise IngestionError("Sheet 'Data' not found", details={"sheet": "Data"})

    job = await svc.run("PARSE", handler, created_by=user.id, project_id=project.id)
    assert job.status == "FAILED"

    persisted = await _reload(session_factory, job.id)
    assert persisted.status == "FAILED"
    assert persisted.error["code"] == "PARSE_FAILED"
    assert persisted.error["message"] == "Sheet 'Data' not found"
    assert persisted.error["details"] == {"errors": [{"sheet": "Data"}]}
    assert "IngestionError" in persisted.error["traceback"]
    assert persisted.started_at is not None and persisted.completed_at is not None

    async with session_factory() as s:
        n = (await s.execute(select(func.count()).where(Project.name == "should-vanish"))).scalar_one()
        assert n == 0
    assert await _audit_types(session_factory, job.id) == ["job.created", "job.started", "job.failed"]


async def test_run_failure_generic_exception_and_reraise(db_session, session_factory, user) -> None:
    svc = JobService(db_session)

    async def handler(job, progress):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await svc.run("REPORT", handler, created_by=user.id, raise_on_failure=True)

    async with session_factory() as s:
        job = (await s.execute(select(Job).where(Job.type == "REPORT"))).scalar_one()
        assert job.status == "FAILED"
        assert job.error["code"] == "INTERNAL_ERROR"
        assert job.error["message"] == "RuntimeError: boom"


async def test_run_handler_returning_none(db_session, user) -> None:
    async def handler(job, progress):
        return None

    job = await JobService(db_session).run("VALIDATE", handler, created_by=user.id)
    assert job.status == "SUCCEEDED" and job.output == {}


async def test_illegal_transitions(db_session, user) -> None:
    svc = JobService(db_session)
    job = await svc.create("PROFILE", created_by=user.id)
    with pytest.raises(StateError):
        await svc.complete(job.id)  # PENDING -> SUCCEEDED not allowed
    with pytest.raises(StateError):
        await svc.update_progress(job.id, 10)  # not RUNNING
    await svc.start(job.id)
    with pytest.raises(StateError):
        await svc.start(job.id)  # RUNNING -> RUNNING
    await svc.complete(job.id)
    for op in (svc.start, svc.complete, svc.cancel):
        with pytest.raises(StateError):
            await op(job.id)
    with pytest.raises(StateError):
        await svc.fail(job.id, "X", "y")


async def test_cancel_pending_and_running(db_session, session_factory, user) -> None:
    svc = JobService(db_session)
    a = await svc.create("PARSE", created_by=user.id)
    await svc.cancel(a.id, actor_id=user.id)
    b = await svc.create("PARSE", created_by=user.id)
    await svc.start(b.id)
    await svc.cancel(b.id)
    assert (await _reload(session_factory, a.id)).status == "CANCELLED"
    assert (await _reload(session_factory, b.id)).status == "CANCELLED"
    async with session_factory() as s:
        ev = (
            await s.execute(
                select(AuditEvent).where(AuditEvent.target_id == a.id, AuditEvent.event_type == "job.cancelled")
            )
        ).scalar_one()
        assert ev.actor_type == "USER" and ev.actor_id == user.id


@pytest.mark.parametrize("bad", [-1, 101, 50.5, True])
async def test_progress_validation(db_session, user, bad) -> None:
    svc = JobService(db_session)
    job = await svc.create("PARSE", created_by=user.id)
    await svc.start(job.id)
    with pytest.raises(ValidationError):
        await svc.update_progress(job.id, bad)


async def test_unknown_type_and_missing_job(db_session, user) -> None:
    svc = JobService(db_session)
    with pytest.raises(ValidationError):
        await svc.create("NOT_A_TYPE", created_by=user.id)
    with pytest.raises(NotFoundError):
        await svc.get(uuid4())


async def test_concurrency_limit_per_project(db_session, user, project) -> None:
    svc = JobService(db_session, max_concurrent_per_project=2)
    j1 = await svc.create("PARSE", created_by=user.id, project_id=project.id)
    await svc.create("PARSE", created_by=user.id, project_id=project.id)
    with pytest.raises(ConflictError) as exc:
        await svc.create("PARSE", created_by=user.id, project_id=project.id)
    assert exc.value.code == "JOB_CONCURRENCY_LIMIT"
    # finishing one frees a slot
    await svc.start(j1.id)
    await svc.complete(j1.id)
    await svc.create("PARSE", created_by=user.id, project_id=project.id)
    assert await svc.count_active(project.id) == 2


async def test_list_jobs(db_session, user, project) -> None:
    svc = JobService(db_session)
    a = await svc.create("PARSE", created_by=user.id, project_id=project.id)
    await svc.create("CLEAN", created_by=user.id)
    await svc.start(a.id)
    assert len(await svc.list_jobs()) == 2
    assert [j.id for j in await svc.list_jobs(project_id=project.id)] == [a.id]
    assert [j.id for j in await svc.list_jobs(status="RUNNING")] == [a.id]


async def test_job_status_endpoint(client, app, session_factory) -> None:
    r = await client.get("/api/v1/me", headers={"Authorization": "Bearer dev-j1-analyst"})
    user_id = r.json()["data"]["id"]
    from uuid import UUID

    async with session_factory() as s:
        svc = JobService(s)

        async def handler(job, progress):
            raise RuntimeError("secret internals")

        job = await svc.run("PARSE", handler, created_by=UUID(user_id))

    r = await client.get(f"/api/v1/jobs/{job.id}", headers={"Authorization": "Bearer dev-j1-analyst"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "FAILED"
    assert "traceback" not in data["error"]

    r = await client.get(f"/api/v1/jobs/{uuid4()}", headers={"Authorization": "Bearer dev-j1-analyst"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
