"""Column types, CHECK constraints, uniqueness and immutability of the iteration-1 tables."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from bordereaux.models import (
    AppendOnlyViolation,
    AuditReportArtifact,
    CanonicalSchema,
    CleaningResult,
    DiscrepancyFinding,
    DiscrepancyOverride,
    MoneyColumnResolution,
    ProcessedFileArtifact,
    ProcessingRun,
    TreatyFigures,
)
from bordereaux.models.types import ExactDecimal, UTCDateTime

pytestmark = pytest.mark.unit


@pytest.fixture
async def run(db_session, user, project) -> ProcessingRun:
    r = ProcessingRun(project_id=project.id, created_by=user.id)
    db_session.add(r)
    await db_session.commit()
    return r


async def _expect_integrity_error(session, obj) -> None:
    session.add(obj)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_run_defaults_and_status_check(db_session, user, project, run) -> None:
    assert run.status == "STARTED"
    assert run.created_at.tzinfo is not None and run.updated_at.tzinfo is not None
    await _expect_integrity_error(db_session, ProcessingRun(project_id=project.id, created_by=user.id, status="BOGUS"))


async def test_foreign_keys_are_enforced(db_session, user) -> None:
    await _expect_integrity_error(db_session, ProcessingRun(project_id=uuid4(), created_by=user.id))


async def test_treaty_figures_exact_decimals_and_immutability(db_session, user, project) -> None:
    tf = TreatyFigures(
        project_id=project.id,
        commission_pct=Decimal("27.5"),
        brokerage_pct=0.1,  # float accepted, stored via repr -> exact "0.1"
        tax_pct="1.2",
        cession_pct=Decimal("0.123456"),
        fx_rate=Decimal("1.23456789"),
        currency="USD/GBP",
        effective_from=date(2026, 1, 1),
        created_by=user.id,
    )
    db_session.add(tf)
    await db_session.commit()

    raw = (await db_session.execute(text("SELECT commission_pct, brokerage_pct, fx_rate FROM treaty_figures"))).one()
    assert tuple(raw) == ("27.5", "0.1", "1.23456789")

    db_session.expunge_all()
    loaded = (await db_session.execute(select(TreatyFigures))).scalar_one()
    assert loaded.commission_pct == Decimal("27.5") and isinstance(loaded.commission_pct, Decimal)
    assert loaded.brokerage_pct == Decimal("0.1")
    assert loaded.tax_pct == Decimal("1.2")
    assert loaded.order_pct is None
    assert loaded.effective_from == date(2026, 1, 1)

    loaded.tax_pct = Decimal("2")
    with pytest.raises(AppendOnlyViolation):
        await db_session.flush()
    await db_session.rollback()
    with pytest.raises(IntegrityError, match="append-only"):
        await db_session.execute(update(TreatyFigures).values(tax_pct="9"))
    await db_session.rollback()


async def test_run_points_at_treaty_figures(db_session, user, project, run) -> None:
    tf = TreatyFigures(
        project_id=project.id, commission_pct=1, tax_pct=1, cession_pct=1, created_by=user.id
    )
    db_session.add(tf)
    await db_session.flush()
    run.treaty_figures_id = tf.id
    run.status = "TREATY_FIGURES_VALIDATED"
    await db_session.commit()
    assert run.updated_at >= run.created_at


async def test_cleaning_results_multiple_attempts(db_session, run) -> None:
    run_id = run.id  # capture: `run` is expired after the rollbacks below

    def attempt(n, status="PENDING_REVIEW"):
        return CleaningResult(
            run_id=run_id,
            attempt_number=n,
            before_row_count=100,
            before_column_count=52,
            after_row_count=98,
            after_column_count=52,
            transformations=[{"rule": "trim_whitespace", "count": 12}],
            warnings=["2 blank rows removed"],
            status=status,
        )

    db_session.add_all([attempt(1, "RETRIED"), attempt(2)])
    await db_session.commit()
    rows = (await db_session.execute(select(CleaningResult).where(CleaningResult.run_id == run_id))).scalars().all()
    assert sorted(r.attempt_number for r in rows) == [1, 2]
    await _expect_integrity_error(db_session, attempt(2))  # duplicate attempt number
    await _expect_integrity_error(db_session, attempt(3, "WHATEVER"))


async def test_money_column_resolution(db_session, run) -> None:
    db_session.add(
        MoneyColumnResolution(
            run_id=run.id,
            source_column="Net Prem",
            resolved_canonical_field="net_premium",
            resolution_stage="SEMANTIC_ARITHMETIC",
            matched_rules=[{"rule_id": "MCR-A1", "row_agreement": "0.97"}],
            is_ambiguous=False,
            evidence={"tol": "0.005"},
        )
    )
    await db_session.commit()
    m = (await db_session.execute(select(MoneyColumnResolution))).scalar_one()
    assert m.matched_rules[0]["rule_id"] == "MCR-A1"
    await _expect_integrity_error(
        db_session, MoneyColumnResolution(run_id=run.id, source_column="x", resolution_stage="GUESS")
    )


async def test_discrepancy_and_single_append_only_override(db_session, user, run) -> None:
    finding = DiscrepancyFinding(
        run_id=run.id,
        check_id="MCR-D1",
        category="TRAP",
        severity="ERROR",
        status="CONFIRMED_ERROR",
        affected_row_number=7,
        affected_field="gross_premium",
        expected_value=Decimal("10000.00"),
        observed_value=Decimal("2500.00"),
        variance=Decimal("-7500.000001"),
        evidence={"rule": "gross-is-ceded"},
        message="Gross appears to be ceded share",
    )
    db_session.add(finding)
    await db_session.flush()
    override = DiscrepancyOverride(discrepancy_id=finding.id, run_id=run.id, actor_id=user.id, reason="Agreed with broker")
    db_session.add(override)
    await db_session.commit()

    db_session.expunge_all()
    f = await db_session.get(DiscrepancyFinding, finding.id)
    assert f.variance == Decimal("-7500.000001") and f.status == "CONFIRMED_ERROR"

    await _expect_integrity_error(
        db_session, DiscrepancyOverride(discrepancy_id=finding.id, run_id=run.id, actor_id=user.id, reason="again")
    )
    await _expect_integrity_error(
        db_session, DiscrepancyOverride(discrepancy_id=finding.id, run_id=run.id, actor_id=user.id, reason=None)
    )

    o = (await db_session.execute(select(DiscrepancyOverride))).scalar_one()
    await db_session.delete(o)
    with pytest.raises(AppendOnlyViolation):
        await db_session.flush()
    await db_session.rollback()

    for bad in ({"category": "NOPE"}, {"severity": "FATAL"}, {"status": "MAYBE"}):
        kwargs = dict(run_id=run.id, check_id="MCR-A1", category="CORE_DEDUCTION", severity="INFO",
                      status="WARNING", evidence={}, message="m")  # fmt: skip
        kwargs.update(bad)
        await _expect_integrity_error(db_session, DiscrepancyFinding(**kwargs))


async def test_artifacts_and_canonical_schema(db_session, run) -> None:
    db_session.add_all(
        [
            ProcessedFileArtifact(run_id=run.id, storage_path="p/runs/r/processed/a.xlsx", format="xlsx", checksum="ab"),
            AuditReportArtifact(run_id=run.id, storage_path="p/runs/r/reports/b.pdf", format="pdf", checksum="cd"),
            CanonicalSchema(id="bordereaux-pc-v1", name="P&C Bordereaux", version="1", definition={"fields": []}),
        ]
    )
    await db_session.commit()
    art = (await db_session.execute(select(ProcessedFileArtifact))).scalar_one()
    assert art.generated_at.tzinfo is not None
    schema = await db_session.get(CanonicalSchema, "bordereaux-pc-v1")
    assert schema.standard == "CUSTOM" and schema.definition == {"fields": []}


class _Dialect:
    def __init__(self, name: str) -> None:
        self.name = name

    def type_descriptor(self, t):
        return t


def test_exact_decimal_type_behaviour() -> None:
    t = ExactDecimal(12, 6)
    sqlite, pg = _Dialect("sqlite"), _Dialect("postgresql")
    assert t.process_bind_param(None, sqlite) is None
    assert t.process_bind_param(Decimal("1.50"), sqlite) == "1.50"
    assert t.process_bind_param(Decimal("1E+3"), sqlite) == "1000"
    assert t.process_bind_param(5, sqlite) == "5"
    assert t.process_bind_param(Decimal("1.5"), pg) == Decimal("1.5")
    for bad in ("abc", Decimal("NaN"), float("inf")):
        with pytest.raises(ValueError):
            t.process_bind_param(bad, sqlite)
    assert t.process_result_value(None, sqlite) is None
    assert t.process_result_value("0.1", sqlite) == Decimal("0.1")
    assert t.process_result_value(Decimal("2"), pg) == Decimal("2")
    assert t.load_dialect_impl(sqlite).__class__.__name__ == "String"
    assert t.load_dialect_impl(pg).__class__.__name__ == "Numeric"
    assert repr(t) == "ExactDecimal(precision=12, scale=6)"


def test_utc_datetime_type_behaviour() -> None:
    t = UTCDateTime()
    sqlite, pg = _Dialect("sqlite"), _Dialect("postgresql")
    plus2 = timezone(timedelta(hours=2))
    aware = datetime(2026, 1, 1, 12, 0, tzinfo=plus2)
    assert t.process_bind_param(None, sqlite) is None
    assert t.process_bind_param(aware, sqlite) == datetime(2026, 1, 1, 10, 0)
    assert t.process_bind_param(aware, pg) is aware
    naive = datetime(2026, 1, 1, 10, 0)
    assert t.process_bind_param(naive, sqlite) is naive
    assert t.process_result_value(None, sqlite) is None
    assert t.process_result_value(naive, sqlite) == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert t.process_result_value(aware, pg) == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
