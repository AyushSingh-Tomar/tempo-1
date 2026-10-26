from __future__ import annotations

import inspect
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import IntegrityError

from bordereaux.audit.service import AuditService, AuditServiceProtocol, serialize_audit_event
from bordereaux.core.context import request_context
from bordereaux.core.exceptions import ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import utcnow
from bordereaux.models import AppendOnlyViolation, AuditEvent

pytestmark = pytest.mark.unit


def test_service_exposes_no_mutation_methods() -> None:
    public = {name for name, _ in inspect.getmembers(AuditService) if not name.startswith("_")}
    assert public == {"log", "query"}
    forbidden = ("update", "delete", "remove", "modify", "edit", "purge", "clear", "truncate")
    for name in dir(AuditService):
        assert not any(word in name.lower() for word in forbidden), name


def test_protocol_signatures_match_contract() -> None:
    log_params = list(inspect.signature(AuditServiceProtocol.log).parameters)
    assert log_params == [
        "self", "event_type", "target_type", "target_id", "action", "actor_id",
        "actor_type", "before_state", "after_state", "metadata",
    ]  # fmt: skip
    impl_params = list(inspect.signature(AuditService.log).parameters)
    assert impl_params[: len(log_params)] == log_params
    q_params = list(inspect.signature(AuditServiceProtocol.query).parameters)
    assert list(inspect.signature(AuditService.query).parameters)[: len(q_params)] == q_params


async def test_log_and_query_round_trip(db_session, user, project) -> None:
    svc = AuditService(db_session)
    target = uuid4()
    with request_context(request_id="req_test", client_ip="10.0.0.1", user_agent="pytest"):
        event = await svc.log(
            event_type="mapping.approved",
            target_type="MappingCandidate",
            target_id=target,
            action=AuditAction.APPROVE,
            actor_id=user.id,
            actor_type=ActorType.USER,
            before_state={"status": "PROPOSED"},
            after_state={"status": "APPROVED", "confidence": Decimal("0.9100"), "at": utcnow()},
            metadata={"source_column": "GWP"},
            reason="looks right",
            project_id=project.id,
        )
    await db_session.commit()

    assert event.id is not None
    assert event.request_id == "req_test"
    assert event.actor_ip == "10.0.0.1"
    assert event.actor_user_agent == "pytest"
    assert event.after_state["confidence"] == "0.9100"  # Decimal stored exactly as string
    assert isinstance(event.after_state["at"], str)

    found = await svc.query(target_type="MappingCandidate", target_id=target)
    assert [e.id for e in found] == [event.id]
    assert found[0].metadata_ == {"source_column": "GWP"}
    assert found[0].timestamp.tzinfo is not None

    ser = serialize_audit_event(found[0])
    assert ser["event_type"] == "mapping.approved" and ser["project_id"] == str(project.id)


async def test_query_filters_and_pagination(db_session, user, project) -> None:
    svc = AuditService(db_session)
    t1, t2 = uuid4(), uuid4()
    await svc.log("project.created", "Project", t1, "CREATE", actor_id=user.id, actor_type="USER", project_id=project.id)
    await svc.log("project.updated", "Project", t1, "UPDATE", actor_id=user.id, actor_type="USER")
    await svc.log("job.started", "Job", t2, "EXECUTE")  # SYSTEM actor, no actor_id
    await db_session.commit()

    assert len(await svc.query()) == 3
    assert len(await svc.query(target_id=t1)) == 2
    assert len(await svc.query(actor_id=user.id)) == 2
    assert [e.event_type for e in await svc.query(event_type="job.started")] == ["job.started"]
    assert len(await svc.query(project_id=project.id)) == 1
    assert len(await svc.query(target_type="Job")) == 1

    now = utcnow()
    assert len(await svc.query(since=now - timedelta(minutes=5))) == 3
    assert len(await svc.query(until=now - timedelta(minutes=5))) == 0
    assert len(await svc.query(since=now + timedelta(minutes=5))) == 0

    page1 = await svc.query(limit=2)
    page2 = await svc.query(limit=2, offset=2)
    assert len(page1) == 2 and len(page2) == 1
    assert {e.id for e in page1}.isdisjoint({e.id for e in page2})
    # newest first
    ts = [e.timestamp for e in await svc.query()]
    assert ts == sorted(ts, reverse=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_type": "", "target_type": "X", "target_id": uuid4(), "action": "CREATE"},
        {"event_type": "x.y", "target_type": " ", "target_id": uuid4(), "action": "CREATE"},
        {"event_type": "x.y", "target_type": "X", "target_id": None, "action": "CREATE"},
        {"event_type": "x.y", "target_type": "X", "target_id": uuid4(), "action": "FROBNICATE"},
        {"event_type": "x.y", "target_type": "X", "target_id": uuid4(), "action": "CREATE", "actor_type": "ROBOT"},
        {"event_type": "x.y", "target_type": "X", "target_id": uuid4(), "action": "CREATE", "actor_type": "USER"},
    ],
)
async def test_log_validation(db_session, kwargs) -> None:
    with pytest.raises(ValidationError):
        await AuditService(db_session).log(**kwargs)


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (1001, 0), (10, -1)])
async def test_query_validation(db_session, limit, offset) -> None:
    with pytest.raises(ValidationError):
        await AuditService(db_session).query(limit=limit, offset=offset)


async def test_orm_rejects_update_and_delete(db_session) -> None:
    event = await AuditService(db_session).log("x.created", "X", uuid4(), "CREATE")
    await db_session.commit()

    event.event_type = "tampered"
    with pytest.raises(AppendOnlyViolation):
        await db_session.flush()
    await db_session.rollback()

    await db_session.delete(event)
    with pytest.raises(AppendOnlyViolation):
        await db_session.flush()
    await db_session.rollback()


async def test_database_triggers_reject_raw_update_and_delete(db_session) -> None:
    event = await AuditService(db_session).log("x.created", "X", uuid4(), "CREATE")
    await db_session.commit()

    with pytest.raises(IntegrityError, match="append-only"):
        await db_session.execute(update(AuditEvent).where(AuditEvent.id == event.id).values(event_type="t"))
    await db_session.rollback()
    with pytest.raises(IntegrityError, match="append-only"):
        await db_session.execute(delete(AuditEvent))
    await db_session.rollback()
    with pytest.raises(IntegrityError, match="append-only"):
        await db_session.execute(text("DELETE FROM audit_events"))
    await db_session.rollback()

    assert len(await AuditService(db_session).query()) == 1
