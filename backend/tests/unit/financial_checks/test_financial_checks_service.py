from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.mapping.service import generate_mapping_candidates
from bordereaux.cleaning.service import acknowledge_cleaning, run_cleaning
from bordereaux.core.exceptions import NotFoundError, StateError, ValidationError
from bordereaux.financial_checks.service import list_discrepancies, override_discrepancy, run_financial_checks
from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run
from bordereaux.mapping.service import approve_candidate, finalize_mappings, list_candidates
from bordereaux.models.project import Project, User
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.storage.local import LocalStorageService
from bordereaux.treaty.schemas import TreatyFiguresRequest
from bordereaux.treaty.service import submit_treaty_figures

pytestmark = pytest.mark.unit

# Every mandatory canonical field present under an exact alias (so stage 1
# resolves the whole file in one pass) plus the money fields under test. Row
# 1 is a clean row (G=10000, C=2200, T=1100, N=6700) matching the treaty
# rates below; row 2 deliberately has the wrong net premium (6000, not 6700).
_HEADER = (
    "Line,Transaction No,Type,YOA,UMR,Risk Code,Class,Coverholder,Policy No,"
    "Insured Name,Insured Country,Risk Country,Sum Insured,SI Currency,"
    "Gross Premium,Commission,IPT,Net Premium,Final Net Premium,"
    "Original Currency,Settlement Currency,Signed/Written,Status,"
    "Sanctions Check,Reporting Period End,"
    "Inception,Expiry,Booking Date,Trans Effective Date\n"
)
def _row(n: int, gross: int, commission: int, tax: int, net: int) -> str:
    return (
        f"{n},TXN-{n},New,2024,UMR-{n},RC1,Property,Test Coverholder,POL-{n},"
        f"Insured {n},GB,GB,{gross},GBP,"
        f"{gross},{commission},{tax},{net},{net},"
        f"GBP,GBP,Signed,Live,"
        f"Pass,2024-03-31,"
        f"2024-01-01,2025-01-01,2024-01-02,2024-01-01\n"
    )


# 10 rows satisfying G-C-T=N (G=10000, C=2200, T=1100, N=6700) so the A1
# identity reaches the 90% row-agreement threshold to be "in effect" for
# this dataset, plus one deliberately-wrong row (net premium 6000, not
# 6700) that becomes the detected discrepancy.
_ROWS = "".join(_row(i, 10000, 2200, 1100, 6700) for i in range(1, 10)) + _row(10, 10000, 2200, 1100, 6000)
_CSV = (_HEADER + _ROWS).encode("utf-8")


async def _run_to_treaty_validated(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", _CSV, user.id)
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    await generate_mapping_candidates(db_session, storage, run.id, user.id)

    candidates = await list_candidates(db_session, run.id)
    for c in candidates:
        if c.status == "PROPOSED":
            await approve_candidate(db_session, c.id, user.id)

    await finalize_mappings(db_session, storage, run.id, user.id)

    payload = TreatyFiguresRequest(commission_pct="0.22", tax_pct="0.11", cession_pct="0.40")
    await submit_treaty_figures(db_session, run.id, payload, user.id)
    return run


async def test_financial_checks_detects_discrepancy(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    run = await _run_to_treaty_validated(db_session, storage, project, user)
    result = await run_financial_checks(db_session, storage, run.id, user.id)
    assert result["rows_checked"] == 10
    assert result["discrepancies_found"] >= 1

    findings = await list_discrepancies(db_session, run.id)
    # affected_row_number is the 1-indexed *source file* row (header is row
    # 1, so the 10th data row is file row 11).
    assert any(f.affected_row_number == 11 for f in findings)
    assert all(f.status == "UNRESOLVED" for f in findings)

    sm = ProcessingRunStateMachine(db_session)
    reloaded = await sm.get(run.id)
    assert reloaded.status == "DISCREPANCY_REVIEW_PENDING"


async def test_financial_checks_require_treaty_figures_validated(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", _CSV, user.id)
    run = result["run"]
    with pytest.raises(StateError):
        await run_financial_checks(db_session, storage, run.id, user.id)


async def test_override_requires_reason_and_is_idempotent_once(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _run_to_treaty_validated(db_session, storage, project, user)
    await run_financial_checks(db_session, storage, run.id, user.id)
    findings = await list_discrepancies(db_session, run.id)
    finding = findings[0]

    with pytest.raises(ValidationError):
        await override_discrepancy(db_session, finding.id, user.id, "")

    override = await override_discrepancy(db_session, finding.id, user.id, "Known rounding difference")
    assert override.reason == "Known rounding difference"

    with pytest.raises(StateError):
        await override_discrepancy(db_session, finding.id, user.id, "second try")

    [reloaded] = [f for f in await list_discrepancies(db_session, run.id) if f.id == finding.id]
    assert reloaded.status == "OVERRIDDEN"
    assert reloaded.expected_value == finding.expected_value
    assert reloaded.observed_value == finding.observed_value


async def test_override_unknown_discrepancy_not_found(db_session: AsyncSession, user: User):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await override_discrepancy(db_session, uuid4(), user.id, "reason")


async def test_discrepancy_filters(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    run = await _run_to_treaty_validated(db_session, storage, project, user)
    await run_financial_checks(db_session, storage, run.id, user.id)

    all_findings = await list_discrepancies(db_session, run.id)
    assert len(all_findings) >= 1
    filtered = await list_discrepancies(db_session, run.id, category=all_findings[0].category)
    assert all(f.category == all_findings[0].category for f in filtered)
    none_match = await list_discrepancies(db_session, run.id, status="OVERRIDDEN")
    assert none_match == []
