"""Step 6/7 of the processing-run workflow: submit and validate treaty
figures. ``treaty_figures`` is append-only (DATA_MODEL conventions, enforced
by ``models.immutability``) - a resubmission always inserts a new row and
re-points ``processing_runs.treaty_figures_id`` at it; nothing is ever
updated in place, so prior figures used by a completed/failed run remain
traceable.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import model_snapshot
from bordereaux.models.run import ProcessingRun
from bordereaux.models.treaty import TreatyFigures
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.storage.service import StorageService
from bordereaux.treaty.derivation import derive_currency_rates, derive_treaty_percentages, rates_by_currency
from bordereaux.treaty.schemas import TreatyFiguresRequest

TREATY_TARGET_TYPE = "TreatyFigures"


async def submit_treaty_figures(
    db: AsyncSession,
    run_id: UUID,
    payload: TreatyFiguresRequest,
    actor_id: UUID,
    storage: StorageService | None = None,
) -> TreatyFigures:
    """Persist a new treaty-figures version for ``run``'s project, link it to
    the run, and advance ``TREATY_FIGURES_PENDING -> TREATY_FIGURES_VALIDATED``.

    The state-machine transition is the enforcement point: calling this
    while the run isn't in ``TREATY_FIGURES_PENDING`` (e.g. mapping not yet
    confirmed) raises ``StateError`` and nothing is persisted (the whole
    thing is one transaction, committed only by the transition call).
    """
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})

    if storage is not None and run.mapping_set_id is not None:
        derived = await derive_for_run(db, storage, run_id)
        known = rates_by_currency(payload.settlement_currency, [e.model_dump(mode="json") for e in payload.fx_rates])
        if payload.fx_rate is not None and payload.currency:
            known.setdefault(payload.currency.upper(), payload.fx_rate)
        missing = [c["currency"] for c in derived["currencies"] if c["currency"] not in known]
        if missing:
            raise ValidationError(
                f"Add an FX rate for: {', '.join(missing)}",
                details=[{"field": "fx_rates", "message": f"Missing FX rate for {', '.join(missing)}"}],
            )

    figures = TreatyFigures(
        project_id=run.project_id,
        commission_pct=payload.commission_pct,
        brokerage_pct=payload.brokerage_pct,
        tax_pct=payload.tax_pct,
        cession_pct=payload.cession_pct,
        order_pct=payload.order_pct,
        fx_rate=payload.fx_rate,
        currency=payload.currency,
        settlement_currency=payload.settlement_currency,
        expected_si_rate=payload.expected_si_rate,
        fx_rates=[e.model_dump(mode="json") for e in payload.fx_rates] or None,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        created_by=actor_id,
    )
    db.add(figures)
    await db.flush()

    run.treaty_figures_id = figures.id
    await db.flush()

    await AuditService(db).log(
        event_type="treaty.figures_submitted",
        target_type=TREATY_TARGET_TYPE,
        target_id=figures.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(figures),
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.validate_treaty_figures(run_id, actor_id)  # commits everything above atomically
    return figures


async def derive_for_run(db: AsyncSession, storage: StorageService, run_id: UUID) -> dict:
    """Currencies / FX rates found in the run's mapped file (see ``derivation``)."""
    from bordereaux.standardization.service import load_standardized_dataset

    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.mapping_set_id is None:
        return {**derive_currency_rates({}), "figures": []}
    from sqlalchemy import select

    from bordereaux.models.mapping import ApprovedMapping

    dataset = await load_standardized_dataset(storage, run_id)
    approved = (
        await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == run.mapping_set_id))
    ).scalars().all()
    extra_sources = {a.target_field: a.source_column for a in approved}
    return {**derive_currency_rates(dataset), "figures": derive_treaty_percentages(dataset, extra_sources)}
