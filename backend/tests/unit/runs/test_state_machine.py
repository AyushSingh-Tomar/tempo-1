import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.exceptions import StateError
from bordereaux.core.models import ProcessingRunStatus as S
from bordereaux.models.project import Project, User
from bordereaux.models.run import ProcessingRun
from bordereaux.runs import ALLOWED_TRANSITIONS, TERMINAL_STATES, ProcessingRunStateMachine


@pytest.fixture
async def run(db_session: AsyncSession, project: Project, user: User) -> ProcessingRun:
    r = ProcessingRun(project_id=project.id, created_by=user.id)
    db_session.add(r)
    await db_session.commit()
    return r


async def test_happy_path_sequence(db_session: AsyncSession, run: ProcessingRun, user: User):
    sm = ProcessingRunStateMachine(db_session)
    sequence = [
        S.FILE_UPLOADED,
        S.FILE_VALIDATED,
        S.CLEANING_COMPLETED,
        S.MAPPING_REVIEW_PENDING,
        S.MAPPING_CONFIRMED,
        S.TREATY_FIGURES_PENDING,
        S.TREATY_FIGURES_VALIDATED,
        S.FINANCIAL_CHECKS_COMPLETED,
        S.DISCREPANCY_REVIEW_PENDING,
        S.REPORT_GENERATION_PENDING,
        S.COMPLETED,
    ]
    for target in sequence:
        updated = await sm.transition(run.id, target, user.id)
        assert updated.status == target.value


async def test_illegal_transition_rejected(db_session: AsyncSession, run: ProcessingRun, user: User):
    sm = ProcessingRunStateMachine(db_session)
    # STARTED -> MAPPING_CONFIRMED skips the entire pipeline.
    with pytest.raises(StateError):
        await sm.transition(run.id, S.MAPPING_CONFIRMED, user.id)
    # The run must be unaffected by the rejected attempt.
    reloaded = await sm.get(run.id)
    assert reloaded.status == S.STARTED.value


async def test_cleaning_rerun_loop_preserves_state_machine_integrity(db_session: AsyncSession, run: ProcessingRun, user: User):
    sm = ProcessingRunStateMachine(db_session)
    await sm.transition(run.id, S.FILE_UPLOADED, user.id)
    await sm.transition(run.id, S.FILE_VALIDATED, user.id)
    await sm.complete_cleaning(run.id)
    rejected = await sm.request_cleaning_rerun(run.id, user.id, reason="Dates look wrong")
    assert rejected.status == S.CLEANING_REVIEW_PENDING.value
    rerun = await sm.complete_cleaning(run.id)
    assert rerun.status == S.CLEANING_COMPLETED.value
    acknowledged = await sm.acknowledge_cleaning(run.id, user.id)
    assert acknowledged.status == S.MAPPING_REVIEW_PENDING.value


async def test_treaty_figures_redo_from_financial_checks(db_session: AsyncSession, run: ProcessingRun, user: User):
    sm = ProcessingRunStateMachine(db_session)
    for target in (
        S.FILE_UPLOADED,
        S.FILE_VALIDATED,
        S.CLEANING_COMPLETED,
        S.MAPPING_REVIEW_PENDING,
        S.MAPPING_CONFIRMED,
        S.TREATY_FIGURES_PENDING,
        S.TREATY_FIGURES_VALIDATED,
        S.FINANCIAL_CHECKS_COMPLETED,
    ):
        await sm.transition(run.id, target, user.id)
    redo = await sm.request_treaty_figures_redo(run.id, user.id, reason="Wrong commission rate entered")
    assert redo.status == S.TREATY_FIGURES_PENDING.value


@pytest.mark.parametrize("state", [s.value for s in S if s.value not in TERMINAL_STATES])
async def test_every_non_terminal_state_can_fail(db_session: AsyncSession, run: ProcessingRun, user: User, state: str):
    sm = ProcessingRunStateMachine(db_session)
    run.status = state
    await db_session.commit()
    failed = await sm.fail(run.id, user.id, reason="Simulated unrecoverable error")
    assert failed.status == S.FAILED.value


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
async def test_terminal_states_have_no_outgoing_transitions(db_session: AsyncSession, run: ProcessingRun, user: User, state: str):
    sm = ProcessingRunStateMachine(db_session)
    run.status = state
    await db_session.commit()
    assert ALLOWED_TRANSITIONS[state] == set()
    with pytest.raises(StateError):
        await sm.transition(run.id, S.FILE_UPLOADED, user.id)


async def test_transition_emits_audit_event(db_session: AsyncSession, run: ProcessingRun, user: User):
    from bordereaux.audit.service import AuditService

    sm = ProcessingRunStateMachine(db_session)
    await sm.transition(run.id, S.FILE_UPLOADED, user.id, reason="Uploaded claims.xlsx")
    events = await AuditService(db_session).query(target_type="ProcessingRun", target_id=run.id)
    assert any(e.event_type == "run.status_changed" and e.reason == "Uploaded claims.xlsx" for e in events)


def test_can_transition_helper():
    sm_targets = ALLOWED_TRANSITIONS[S.STARTED.value]
    assert S.FILE_UPLOADED.value in sm_targets
    assert S.COMPLETED.value not in sm_targets
