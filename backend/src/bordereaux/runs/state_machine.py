"""Processing-run state machine: the single place that enforces legal
transitions among the 14 ``ProcessingRunStatus`` values
(Initial_iteration_implementation_command.md §4). ``processing_runs.status``
must never be written anywhere else - API handlers call
``ProcessingRunStateMachine.transition(...)`` (or one of its named step
methods), never ``run.status = ...`` directly.

Resolved ambiguities (the implementation command specifies the 14 states but
not every edge transition - documenting the choices made, per its own
guidance to pick the safest non-destructive behaviour rather than invent one
silently):

1. **Cleaning rerun.** ``CLEANING_COMPLETED`` is reached by a successful
   clean job and is the state in which the before/after review is shown.
   ``CLEANING_REVIEW_PENDING`` is entered only when the user explicitly
   rejects that result and requests a rerun - it marks "a new attempt is
   being prepared" without discarding the previous ``cleaning_results`` row
   (a new row with the next ``attempt_number`` is created on the next clean).
   Acknowledging goes straight from ``CLEANING_COMPLETED`` to
   ``MAPPING_REVIEW_PENDING``; declining without requesting a rerun is simply
   not an action that changes state (the frontend keeps showing the same
   review screen).
2. **Mapping decline.** The implementation command's "if the user declines,
   return to the mapping review panel" is a no-op on the state machine - the
   run is already in ``MAPPING_REVIEW_PENDING`` and never left it (only
   ``finalize_mappings`` advances it, to ``MAPPING_CONFIRMED``).
3. **Redoing treaty figures after seeing results.** Explicitly allowed as a
   backward transition from ``FINANCIAL_CHECKS_COMPLETED`` or
   ``DISCREPANCY_REVIEW_PENDING`` back to ``TREATY_FIGURES_PENDING``, per the
   instruction to let the user "rerun the relevant processing stage ...
   while preserving prior run history" (a new ``treaty_figures`` row is
   inserted; nothing is deleted).
4. **Failure.** Any non-terminal state may transition to ``FAILED`` (an
   unrecoverable job error). ``COMPLETED`` and ``FAILED`` are terminal: no
   transitions leave them. Starting a new processing run is how the user
   retries, which also matches "preserve prior run history".
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, StateError
from bordereaux.core.models import ActorType, AuditAction, ProcessingRunStatus
from bordereaux.core.utils import model_snapshot
from bordereaux.models.run import ProcessingRun

S = ProcessingRunStatus

TERMINAL_STATES: frozenset[str] = frozenset({S.COMPLETED.value, S.FAILED.value})

_FORWARD_TRANSITIONS: dict[str, set[str]] = {
    S.STARTED.value: {S.FILE_UPLOADED.value},
    S.FILE_UPLOADED.value: {S.FILE_VALIDATED.value},
    S.FILE_VALIDATED.value: {S.CLEANING_COMPLETED.value},
    S.CLEANING_COMPLETED.value: {S.MAPPING_REVIEW_PENDING.value, S.CLEANING_REVIEW_PENDING.value},
    S.CLEANING_REVIEW_PENDING.value: {S.CLEANING_COMPLETED.value},
    S.MAPPING_REVIEW_PENDING.value: {S.MAPPING_CONFIRMED.value},
    S.MAPPING_CONFIRMED.value: {S.TREATY_FIGURES_PENDING.value},
    S.TREATY_FIGURES_PENDING.value: {S.TREATY_FIGURES_VALIDATED.value},
    S.TREATY_FIGURES_VALIDATED.value: {S.FINANCIAL_CHECKS_COMPLETED.value},
    S.FINANCIAL_CHECKS_COMPLETED.value: {S.DISCREPANCY_REVIEW_PENDING.value, S.TREATY_FIGURES_PENDING.value},
    S.DISCREPANCY_REVIEW_PENDING.value: {S.REPORT_GENERATION_PENDING.value, S.TREATY_FIGURES_PENDING.value},
    S.REPORT_GENERATION_PENDING.value: {S.COMPLETED.value},
}

# Any non-terminal state may fail.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    state: targets | ({S.FAILED.value} if state not in TERMINAL_STATES else set())
    for state, targets in _FORWARD_TRANSITIONS.items()
}
for _terminal in TERMINAL_STATES:
    ALLOWED_TRANSITIONS.setdefault(_terminal, set())

RUN_TARGET_TYPE = "ProcessingRun"


class ProcessingRunStateMachine:
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._session = session
        self._audit = audit or AuditService(session)

    async def get(self, run_id: UUID) -> ProcessingRun:
        run = await self._session.get(ProcessingRun, run_id)
        if run is None:
            raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
        return run

    async def transition(
        self,
        run_id: UUID,
        to_status: ProcessingRunStatus | str,
        actor_id: UUID | None = None,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ProcessingRun:
        """The only sanctioned way to change ``processing_runs.status``."""
        run = await self.get(run_id)
        target = ProcessingRunStatus(to_status).value
        allowed = ALLOWED_TRANSITIONS.get(run.status, set())
        if target not in allowed:
            raise StateError(
                f"Illegal processing-run transition {run.status} -> {target}",
                code="INVALID_RUN_TRANSITION",
                details={"run_id": str(run_id), "from": run.status, "to": target, "allowed": sorted(allowed)},
            )
        before = model_snapshot(run)
        run.status = target
        await self._session.flush()
        await self._audit.log(
            event_type="run.status_changed",
            target_type=RUN_TARGET_TYPE,
            target_id=run.id,
            action=AuditAction.UPDATE,
            actor_id=actor_id,
            actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
            before_state={"status": before["status"]},
            after_state={"status": run.status},
            reason=reason,
            metadata=metadata,
            project_id=run.project_id,
        )
        if commit:
            await self._session.commit()
        return run

    def can_transition(self, current_status: str, to_status: ProcessingRunStatus | str) -> bool:
        return ProcessingRunStatus(to_status).value in ALLOWED_TRANSITIONS.get(current_status, set())

    # ---------------------------------------------------------- step helpers
    # Thin, semantically-named wrappers over ``transition`` for each workflow
    # step. API handlers should prefer these over calling ``transition``
    # directly - they read as the workflow, not as raw state codes.

    async def mark_file_uploaded(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(run_id, S.FILE_UPLOADED, actor_id, reason="File uploaded")

    async def mark_file_validated(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(run_id, S.FILE_VALIDATED, actor_id, reason="File validated")

    async def complete_cleaning(self, run_id: UUID, actor_id: UUID | None = None) -> ProcessingRun:
        return await self.transition(run_id, S.CLEANING_COMPLETED, actor_id, reason="Cleaning job completed")

    async def acknowledge_cleaning(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(
            run_id, S.MAPPING_REVIEW_PENDING, actor_id, reason="User acknowledged cleaning result"
        )

    async def request_cleaning_rerun(self, run_id: UUID, actor_id: UUID, reason: str) -> ProcessingRun:
        return await self.transition(run_id, S.CLEANING_REVIEW_PENDING, actor_id, reason=reason)

    async def confirm_mapping(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(run_id, S.MAPPING_CONFIRMED, actor_id, reason="Mapping set finalized")

    async def enter_treaty_figures(self, run_id: UUID, actor_id: UUID | None = None) -> ProcessingRun:
        return await self.transition(run_id, S.TREATY_FIGURES_PENDING, actor_id, reason="Awaiting treaty figures")

    async def validate_treaty_figures(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(run_id, S.TREATY_FIGURES_VALIDATED, actor_id, reason="Treaty figures validated")

    async def complete_financial_checks(self, run_id: UUID, actor_id: UUID | None = None) -> ProcessingRun:
        return await self.transition(
            run_id, S.FINANCIAL_CHECKS_COMPLETED, actor_id, reason="Financial checks job completed"
        )

    async def enter_discrepancy_review(self, run_id: UUID, actor_id: UUID | None = None) -> ProcessingRun:
        return await self.transition(
            run_id, S.DISCREPANCY_REVIEW_PENDING, actor_id, reason="Discrepancies ready for review"
        )

    async def request_treaty_figures_redo(self, run_id: UUID, actor_id: UUID, reason: str) -> ProcessingRun:
        return await self.transition(run_id, S.TREATY_FIGURES_PENDING, actor_id, reason=reason)

    async def proceed_to_report_generation(self, run_id: UUID, actor_id: UUID) -> ProcessingRun:
        return await self.transition(
            run_id, S.REPORT_GENERATION_PENDING, actor_id, reason="User proceeded to report generation"
        )

    async def complete(self, run_id: UUID, actor_id: UUID | None = None) -> ProcessingRun:
        return await self.transition(run_id, S.COMPLETED, actor_id, reason="Report and artifacts generated")

    async def fail(
        self, run_id: UUID, actor_id: UUID | None = None, *, reason: str, metadata: dict[str, Any] | None = None
    ) -> ProcessingRun:
        return await self.transition(run_id, S.FAILED, actor_id, reason=reason, metadata=metadata)
