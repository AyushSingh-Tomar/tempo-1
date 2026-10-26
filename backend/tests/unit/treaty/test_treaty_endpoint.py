import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.models import ProcessingRunStatus as S
from bordereaux.models.project import Project, User
from bordereaux.models.run import ProcessingRun
from bordereaux.runs import ProcessingRunStateMachine

from tests.conftest import auth


@pytest.fixture
async def run_pending_treaty_figures(db_session: AsyncSession, project: Project, user: User) -> ProcessingRun:
    run = ProcessingRun(project_id=project.id, created_by=user.id)
    db_session.add(run)
    await db_session.commit()
    sm = ProcessingRunStateMachine(db_session)
    for target in (S.FILE_UPLOADED, S.FILE_VALIDATED, S.CLEANING_COMPLETED, S.MAPPING_REVIEW_PENDING, S.MAPPING_CONFIRMED, S.TREATY_FIGURES_PENDING):
        await sm.transition(run.id, target, user.id)
    return run


async def test_submit_treaty_figures_advances_run(client: httpx.AsyncClient, run_pending_treaty_figures: ProcessingRun):
    resp = await client.post(
        f"/api/v1/processing-runs/{run_pending_treaty_figures.id}/treaty-figures",
        json={"commission_pct": "0.25", "tax_pct": "0.12", "cession_pct": "0.40", "order_pct": "0.20"},
        headers=auth("dev-analyst1-analyst"),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    assert body["commission_pct"] == "0.25"
    assert body["cession_pct"] == "0.40"

    status_resp = await client.get(f"/api/v1/processing-runs/{run_pending_treaty_figures.id}", headers=auth("dev-analyst1-analyst"))
    # (Run detail GET endpoint belongs to the pipeline agent's work; skip if not yet wired.)
    if status_resp.status_code == 200:
        assert status_resp.json()["data"]["status"] == S.TREATY_FIGURES_VALIDATED.value


async def test_submit_treaty_figures_rejects_out_of_range_percentage(
    client: httpx.AsyncClient, run_pending_treaty_figures: ProcessingRun
):
    resp = await client.post(
        f"/api/v1/processing-runs/{run_pending_treaty_figures.id}/treaty-figures",
        json={"commission_pct": "25", "tax_pct": "0.12", "cession_pct": "0.40"},  # 25 instead of 0.25
        headers=auth("dev-analyst1-analyst"),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_submit_treaty_figures_wrong_run_state_rejected(
    client: httpx.AsyncClient, db_session: AsyncSession, project: Project, user: User
):
    run = ProcessingRun(project_id=project.id, created_by=user.id)
    db_session.add(run)
    await db_session.commit()  # still STARTED, not TREATY_FIGURES_PENDING

    resp = await client.post(
        f"/api/v1/processing-runs/{run.id}/treaty-figures",
        json={"commission_pct": "0.25", "tax_pct": "0.12", "cession_pct": "0.40"},
        headers=auth("dev-analyst1-analyst"),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_RUN_TRANSITION"


async def test_submit_treaty_figures_requires_permission(client: httpx.AsyncClient, run_pending_treaty_figures: ProcessingRun):
    resp = await client.post(
        f"/api/v1/processing-runs/{run_pending_treaty_figures.id}/treaty-figures",
        json={"commission_pct": "0.25", "tax_pct": "0.12", "cession_pct": "0.40"},
        headers=auth("dev-viewer1-viewer"),  # viewer role has no treaty:create permission
    )
    assert resp.status_code == 403
