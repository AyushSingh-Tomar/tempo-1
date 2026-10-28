"""Step 11-12: generate the processed-file export and audit report from the
*actual* persisted run data, and resolve authenticated downloads through the
artifact rows (never a raw path from the client).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, StateError, StorageError, ValidationError
from bordereaux.core.models import ActorType, AuditAction, ProcessingRunStatus
from bordereaux.core.utils import utcnow
from bordereaux.models.artifact import AuditReportArtifact, PeriodExtractArtifact, ProcessedFileArtifact
from bordereaux.models.asset import SourceAsset
from bordereaux.models.cleaning import CleaningResult
from bordereaux.models.discrepancy import DiscrepancyFinding, DiscrepancyOverride
from bordereaux.models.mapping import ApprovedMapping, MappingSet
from bordereaux.models.run import ProcessingRun
from bordereaux.models.treaty import TreatyFigures
from bordereaux.reporting.period import PeriodFilter, filter_processed_csv
from bordereaux.runs.state_machine import ProcessingRunStateMachine
from bordereaux.standardization.service import load_standardized_dataset
from bordereaux.storage.service import StorageService
from bordereaux.treaty.settlement import add_settlement_columns

ARTIFACT_TYPES = ("processed_file", "audit_report")


def _processed_file_path(run_id: UUID) -> str:
    return f"runs/{run_id}/reports/processed_file.csv"


def _audit_report_path(run_id: UUID) -> str:
    return f"runs/{run_id}/reports/audit_report.json"


def _humanize_audit_value(label: str, value: Any, depth: int = 0) -> list[str]:
    indent = "  " * depth
    title = label.replace("_", " ").capitalize()
    if isinstance(value, dict):
        if not value:
            return [f"{indent}{title}: None"]
        lines = [f"{indent}{title}:"]
        for key, child in value.items():
            lines.extend(_humanize_audit_value(key, child, depth + 1))
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{indent}{title}: None"]
        lines = [f"{indent}{title}:"]
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{'  ' * (depth + 1)}-")
                for key, child in item.items():
                    lines.extend(_humanize_audit_value(key, child, depth + 2))
            else:
                rendered = "Not available" if item is None else str(item)
                lines.append(f"{'  ' * (depth + 1)}- {rendered}")
        return lines
    rendered = "Not available" if value is None else str(value)
    return [f"{indent}{title}: {rendered}"]


def _format_audit_report_text(payload: dict[str, Any]) -> bytes:
    lines = ["Audit Report", "============"]
    for key, value in payload.items():
        lines.extend(["", *_humanize_audit_value(key, value)])
    return ("\n".join(lines) + "\n").encode("utf-8")


async def _build_processed_file_csv(storage: StorageService, run_id: UUID, treaty: TreatyFigures | None = None) -> bytes:
    dataset = await load_standardized_dataset(storage, run_id)
    fields = dataset["fields"]
    rows = dataset["rows"]
    if treaty is not None:
        fields, rows = add_settlement_columns(fields, rows, treaty.settlement_currency, treaty.fx_rates)
    # Only present when some date had month precision, so a clean file's columns are unchanged.
    has_date_flags = any(r.get("_date_flags") for r in rows)
    columns = ["source_row_number", *fields, *(["date_quality_flags"] if has_date_flags else [])]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        out = {"source_row_number": row.get("_source_row_number")}
        out.update({f: row.get(f) for f in fields})
        if has_date_flags:
            out["date_quality_flags"] = ";".join(f"{k}={v}" for k, v in sorted((row.get("_date_flags") or {}).items()))
        writer.writerow(out)
    return buf.getvalue().encode("utf-8")


async def _build_audit_report(db: AsyncSession, run: ProcessingRun) -> dict[str, Any]:
    asset = await db.get(SourceAsset, run.source_asset_id) if run.source_asset_id else None

    cleaning_rows = (
        await db.execute(
            select(CleaningResult).where(CleaningResult.run_id == run.id).order_by(CleaningResult.attempt_number)
        )
    ).scalars().all()
    latest_cleaning = cleaning_rows[-1] if cleaning_rows else None

    mapping_set = await db.get(MappingSet, run.mapping_set_id) if run.mapping_set_id else None
    approved_mappings = []
    if mapping_set is not None:
        approved_mappings = list(
            (
                await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == mapping_set.id))
            ).scalars()
        )

    figures = await db.get(TreatyFigures, run.treaty_figures_id) if run.treaty_figures_id else None

    findings = list(
        (await db.execute(select(DiscrepancyFinding).where(DiscrepancyFinding.run_id == run.id))).scalars()
    )
    overrides = list(
        (await db.execute(select(DiscrepancyOverride).where(DiscrepancyOverride.run_id == run.id))).scalars()
    )
    overrides_by_finding = {o.discrepancy_id: o for o in overrides}

    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for f in findings:
        status_counts[f.status] = status_counts.get(f.status, 0) + 1
        category_counts[f.category] = category_counts.get(f.category, 0) + 1

    return {
        "run_id": str(run.id),
        "project_id": str(run.project_id),
        "generated_at": utcnow().isoformat(),
        "run_created_at": run.created_at.isoformat() if run.created_at else None,
        "run_status_at_generation": run.status,
        "source": {
            "filename": asset.original_filename if asset else None,
            "checksum": asset.checksum if asset else None,
            "format": asset.format if asset else None,
            "size_bytes": asset.size_bytes if asset else None,
        }
        if asset
        else None,
        "cleaning": {
            "attempts": len(cleaning_rows),
            "latest_attempt": latest_cleaning.attempt_number if latest_cleaning else None,
            "before_row_count": latest_cleaning.before_row_count if latest_cleaning else None,
            "after_row_count": latest_cleaning.after_row_count if latest_cleaning else None,
            "before_column_count": latest_cleaning.before_column_count if latest_cleaning else None,
            "after_column_count": latest_cleaning.after_column_count if latest_cleaning else None,
            "transformations": latest_cleaning.transformations if latest_cleaning else [],
            "warnings": latest_cleaning.warnings if latest_cleaning else [],
        },
        "mapping": {
            "mapping_set_id": str(mapping_set.id) if mapping_set else None,
            "schema_id": mapping_set.schema_id if mapping_set else None,
            "finalized_at": mapping_set.finalized_at.isoformat() if mapping_set and mapping_set.finalized_at else None,
            "approved_mappings": [
                {
                    "source_column": a.source_column,
                    "target_field": a.target_field,
                    "origin": a.origin,
                    "confidence_total": str(a.confidence_total),
                }
                for a in approved_mappings
            ],
        },
        "treaty_figures": {
            "id": str(figures.id) if figures else None,
            "commission_pct": str(figures.commission_pct) if figures else None,
            "brokerage_pct": str(figures.brokerage_pct) if figures and figures.brokerage_pct is not None else None,
            "tax_pct": str(figures.tax_pct) if figures else None,
            "cession_pct": str(figures.cession_pct) if figures else None,
            "order_pct": str(figures.order_pct) if figures and figures.order_pct is not None else None,
            "fx_rate": str(figures.fx_rate) if figures and figures.fx_rate is not None else None,
            "settlement_currency": figures.settlement_currency if figures else None,
            "fx_rates": (figures.fx_rates or []) if figures else [],
        }
        if figures
        else None,
        "financial_checks": {
            "total_findings": len(findings),
            "status_counts": status_counts,
            "category_counts": category_counts,
        },
        "discrepancies": [
            {
                "id": str(f.id),
                "check_id": f.check_id,
                "category": f.category,
                "severity": f.severity,
                "status": f.status,
                "affected_row_number": f.affected_row_number,
                "expected_value": str(f.expected_value) if f.expected_value is not None else None,
                "observed_value": str(f.observed_value) if f.observed_value is not None else None,
                "variance": str(f.variance) if f.variance is not None else None,
                "message": f.message,
                "override": (
                    {
                        "actor_id": str(overrides_by_finding[f.id].actor_id),
                        "reason": overrides_by_finding[f.id].reason,
                        "comment": overrides_by_finding[f.id].comment,
                        "created_at": overrides_by_finding[f.id].created_at.isoformat(),
                    }
                    if f.id in overrides_by_finding
                    else None
                ),
            }
            for f in findings
        ],
        "final_status": run.status,
    }


async def generate_reports(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID
) -> tuple[ProcessedFileArtifact, AuditReportArtifact]:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != ProcessingRunStatus.REPORT_GENERATION_PENDING.value:
        raise StateError(
            f"Run must be REPORT_GENERATION_PENDING to generate reports (current: {run.status})",
            code="INVALID_RUN_TRANSITION",
            details={"run_id": str(run_id), "status": run.status},
        )

    treaty = await db.get(TreatyFigures, run.treaty_figures_id) if run.treaty_figures_id else None
    csv_bytes = await _build_processed_file_csv(storage, run_id, treaty)
    csv_result = await storage.upload(_processed_file_path(run_id), csv_bytes, content_type="text/csv")
    processed_artifact = ProcessedFileArtifact(
        run_id=run_id, storage_path=csv_result.path, format="CSV", checksum=csv_result.checksum
    )
    db.add(processed_artifact)
    await db.flush()

    audit_payload = await _build_audit_report(db, run)
    # Reaching this point means both artifacts are about to be persisted
    # successfully - record the run's true final status (COMPLETED), which
    # the state-machine transition below will apply a moment later, rather
    # than the still-REPORT_GENERATION_PENDING status read moments earlier.
    audit_payload["final_status"] = ProcessingRunStatus.COMPLETED.value
    audit_bytes = json.dumps(audit_payload, default=str, indent=2).encode("utf-8")
    audit_result = await storage.upload(_audit_report_path(run_id), audit_bytes, content_type="application/json")
    audit_artifact = AuditReportArtifact(
        run_id=run_id, storage_path=audit_result.path, format="JSON", checksum=audit_result.checksum
    )
    db.add(audit_artifact)
    await db.flush()

    await AuditService(db).log(
        event_type="reports.generated",
        target_type="ProcessingRun",
        target_id=run_id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state={"processed_file_artifact_id": str(processed_artifact.id), "audit_report_artifact_id": str(audit_artifact.id)},
        project_id=run.project_id,
    )

    sm = ProcessingRunStateMachine(db)
    await sm.complete(run_id, actor_id)

    return processed_artifact, audit_artifact


async def resolve_download(
    db: AsyncSession, storage: StorageService, run_id: UUID, artifact_type: str
) -> tuple[bytes, str, str]:
    """Returns ``(content, filename, content_type)``, resolved only through
    the artifact rows (never a raw path from the client). Raises
    ``NotFoundError`` both for an unknown run and for a run with no such
    artifact yet - never leaks which case it was."""
    if artifact_type not in (*ARTIFACT_TYPES, "audit_report_human"):
        raise ValidationError(
            f"Unknown artifact_type '{artifact_type}'",
            details={"allowed": [*ARTIFACT_TYPES, "audit_report_human"]},
        )

    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Artifact not found")

    if artifact_type == "processed_file":
        stmt = select(ProcessedFileArtifact).where(ProcessedFileArtifact.run_id == run_id)
        model_cls: type = ProcessedFileArtifact
        filename = "processed_file.csv"
        content_type = "text/csv"
    else:
        stmt = select(AuditReportArtifact).where(AuditReportArtifact.run_id == run_id)
        model_cls = AuditReportArtifact
        filename = "audit_report.json" if artifact_type == "audit_report" else "audit_report.txt"
        content_type = "application/json" if artifact_type == "audit_report" else "text/plain"

    artifact = (await db.execute(stmt.order_by(model_cls.generated_at.desc()))).scalars().first()
    if artifact is None:
        raise NotFoundError("Artifact not found")

    content = await storage.download(artifact.storage_path)
    if artifact_type == "audit_report_human":
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StorageError("Stored audit report is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise StorageError("Stored audit report has an invalid structure")
        content = _format_audit_report_text(payload)
    return content, filename, content_type


# --- Period extracts ---------------------------------------------------------------


def _safe_token(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_") or "field"


def extract_filename(extract: PeriodExtractArtifact) -> str:
    return f"processed_file_{extract.period_label}_{_safe_token(extract.period_field)}_v{extract.version_number}.csv"


async def create_period_extract(
    db: AsyncSession, storage: StorageService, run_id: UUID, flt: PeriodFilter, actor_id: UUID | None
) -> tuple[PeriodExtractArtifact, bool]:
    """Cut the run's processed file down to one period and store it as the next
    immutable version for that (field, period). Returns ``(extract, created)``;
    asking again for an unchanged result returns the existing latest version
    (``created=False``) rather than piling up identical copies."""
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    processed = (
        await db.execute(
            select(ProcessedFileArtifact)
            .where(ProcessedFileArtifact.run_id == run_id)
            .order_by(ProcessedFileArtifact.generated_at.desc())
        )
    ).scalars().first()
    if processed is None:
        raise StateError("Generate the reports first: this run has no processed file to extract from")

    filtered, stats = filter_processed_csv(await storage.download(processed.storage_path), flt)
    checksum = hashlib.sha256(filtered).hexdigest()

    latest = (
        await db.execute(
            select(PeriodExtractArtifact)
            .where(
                PeriodExtractArtifact.run_id == run_id,
                PeriodExtractArtifact.period_field == flt.field,
                PeriodExtractArtifact.period_label == flt.label,
            )
            .order_by(PeriodExtractArtifact.version_number.desc())
        )
    ).scalars().first()
    if latest is not None and latest.checksum == checksum:
        return latest, False

    version = (latest.version_number if latest else 0) + 1
    path = f"runs/{run_id}/reports/extracts/{_safe_token(flt.field)}_{flt.label}_v{version}.csv"
    stored = await storage.upload(path, filtered, content_type="text/csv")
    extract = PeriodExtractArtifact(
        run_id=run_id,
        storage_path=stored.path,
        format="CSV",
        checksum=stored.checksum,
        source_artifact_id=processed.id,
        source_checksum=processed.checksum,
        period_field=flt.field,
        period_label=flt.label,
        period_year=flt.year,
        period_quarter=flt.quarter,
        period_month=flt.month,
        version_number=version,
        total_rows=stats.total_rows,
        included_rows=stats.included_rows,
        included_partial_dates=stats.included_partial_dates,
        excluded_outside_period=stats.excluded_outside_period,
        excluded_undated=stats.excluded_undated,
        generated_by=actor_id,
    )
    db.add(extract)
    await db.flush()
    await AuditService(db).log(
        event_type="reports.period_extract_generated",
        target_type="PeriodExtractArtifact",
        target_id=extract.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
        after_state={
            "run_id": str(run_id),
            "period": flt.label,
            "period_field": flt.field,
            "version_number": version,
            "checksum": stored.checksum,
            "source_checksum": processed.checksum,
            "total_rows": stats.total_rows,
            "included_rows": stats.included_rows,
            "included_partial_dates": stats.included_partial_dates,
            "excluded_outside_period": stats.excluded_outside_period,
            "excluded_undated": stats.excluded_undated,
        },
        project_id=run.project_id,
    )
    await db.commit()
    return extract, True


async def list_period_extracts(db: AsyncSession, run_id: UUID) -> list[PeriodExtractArtifact]:
    if await db.get(ProcessingRun, run_id) is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    stmt = (
        select(PeriodExtractArtifact)
        .where(PeriodExtractArtifact.run_id == run_id)
        .order_by(PeriodExtractArtifact.generated_at.desc(), PeriodExtractArtifact.version_number.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def download_period_extract(
    db: AsyncSession, storage: StorageService, run_id: UUID, extract_id: UUID, actor_id: UUID | None
) -> tuple[bytes, PeriodExtractArtifact]:
    """The stored bytes of one extract version, resolved only through its row and
    verified against the recorded checksum. Every download is audit-logged."""
    extract = await db.get(PeriodExtractArtifact, extract_id)
    if extract is None or extract.run_id != run_id:
        raise NotFoundError("Artifact not found")
    content = await storage.download(extract.storage_path)
    if hashlib.sha256(content).hexdigest() != extract.checksum:
        raise StorageError("Stored extract no longer matches its recorded checksum", details={"extract_id": str(extract.id)})
    run = await db.get(ProcessingRun, run_id)
    await AuditService(db).log(
        event_type="reports.period_extract_downloaded",
        target_type="PeriodExtractArtifact",
        target_id=extract.id,
        action=AuditAction.READ,
        actor_id=actor_id,
        actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
        metadata={"period": extract.period_label, "version_number": extract.version_number},
        project_id=run.project_id if run else None,
    )
    await db.commit()
    return content, extract
