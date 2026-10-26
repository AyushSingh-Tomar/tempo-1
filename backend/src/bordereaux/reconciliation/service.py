"""Orchestration for the reconciliation workspace (DB + storage around the
pure modules): build a final bordereaux / subledger from many files, then
run user-defined reconciliation rules between the two."""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import NotFoundError, StateError, ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import sha256_hex, to_jsonable, utcnow
from bordereaux.models.project import Project
from bordereaux.models.recon import ReconDataset, ReconFile, ReconRun
from bordereaux.reconciliation import engine
from bordereaux.reconciliation.combine import combine_tables
from bordereaux.reconciliation.encoding import SUPPORTED_ENCODINGS, canonical_name, decide_encoding
from bordereaux.reconciliation.readers import ENCODING_FORMATS, SINGLE_SHEET, detect_format, list_sheets, read_table
from bordereaux.reconciliation.schema import RESERVED, build_schema_summary, infer_type
from bordereaux.storage.service import StorageService

MAX_FILES_PER_DATASET = 50
_PREVIEW_ROWS = 25
_DRILLDOWN_LIMIT = 200


def _file_path(dataset_id: UUID, file_id: UUID, filename: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return f"recon/{dataset_id}/files/{file_id}/{safe}"


def _final_path(dataset_id: UUID) -> str:
    return f"recon/{dataset_id}/final.json"


def _result_path(run_id: UUID) -> str:
    return f"recon/runs/{run_id}/result.json"


# --- datasets & files -----------------------------------------------------------


async def create_dataset(db: AsyncSession, project_id: UUID, kind: str, name: str, actor_id: UUID) -> ReconDataset:
    kind = kind.upper()
    if kind not in ("BORDEREAUX", "SUBLEDGER"):
        raise ValidationError("kind must be BORDEREAUX or SUBLEDGER")
    if not name.strip():
        raise ValidationError("A dataset needs a name")
    project = await db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise NotFoundError("Project not found", details={"project_id": str(project_id)})
    ds = ReconDataset(project_id=project_id, kind=kind, name=name.strip(), config={}, created_by=actor_id)
    db.add(ds)
    await db.flush()
    await AuditService(db).log(
        event_type="recon.dataset_created", target_type="ReconDataset", target_id=ds.id, action=AuditAction.CREATE,
        actor_id=actor_id, actor_type=ActorType.USER, after_state={"kind": kind, "name": ds.name},
    )
    await db.commit()
    return ds


async def get_dataset(db: AsyncSession, dataset_id: UUID) -> ReconDataset:
    ds = await db.get(ReconDataset, dataset_id)
    if ds is None:
        raise NotFoundError("Dataset not found", details={"dataset_id": str(dataset_id)})
    return ds


async def list_datasets(db: AsyncSession, project_id: UUID, kind: str | None = None) -> list[ReconDataset]:
    stmt = select(ReconDataset).where(ReconDataset.project_id == project_id).order_by(ReconDataset.created_at.desc())
    if kind:
        stmt = stmt.where(ReconDataset.kind == kind.upper())
    return list((await db.execute(stmt)).scalars().all())


async def list_files(db: AsyncSession, dataset_id: UUID) -> list[ReconFile]:
    stmt = select(ReconFile).where(ReconFile.dataset_id == dataset_id).order_by(ReconFile.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


def _assert_draft(ds: ReconDataset) -> None:
    if ds.status != "DRAFT":
        raise StateError("This dataset is final and cannot be changed; create a new dataset instead.", code="DATASET_FINAL")


def _apply_encoding(f: ReconFile, content: bytes) -> None:
    if f.format not in ENCODING_FORMATS:
        f.encoding_info, f.encoding = {"method": "NOT_APPLICABLE", "note": "Excel workbooks are Unicode."}, None
        return
    if f.format == "SAS7BDAT":
        forced = (f.encoding_choice or {}).get("forced")
        f.encoding = canonical_name(forced) if forced else None
        f.encoding_info = {"method": "USER" if forced else "FILE_HEADER", "chosen": f.encoding,
                           "note": "SAS files declare their own encoding in the header; override it only if text is garbled."}
        return
    choice = f.encoding_choice or {}
    try:
        decision = decide_encoding(content, choice.get("forced"), choice.get("candidates"))
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    f.encoding_info, f.encoding = decision.as_dict(), decision.chosen


async def add_files(
    db: AsyncSession, storage: StorageService, ds: ReconDataset, uploads: list[tuple[str, bytes]], actor_id: UUID,
    max_bytes: int, encoding_choice: dict[str, Any] | None = None,
) -> list[ReconFile]:
    _assert_draft(ds)
    existing = len(await list_files(db, ds.id))
    if existing + len(uploads) > MAX_FILES_PER_DATASET:
        raise ValidationError(f"At most {MAX_FILES_PER_DATASET} files per dataset")
    added: list[ReconFile] = []
    for filename, content in uploads:
        if not content:
            raise ValidationError(f"'{filename}' is empty")
        if len(content) > max_bytes:
            raise ValidationError(f"'{filename}' exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
        fmt = detect_format(filename)
        sheets = list_sheets(fmt, content)
        f = ReconFile(
            dataset_id=ds.id, filename=filename, format=fmt, size_bytes=len(content), checksum=sha256_hex(content),
            storage_path="", encoding_choice=encoding_choice or {}, sheets=sheets,
            selected_sheets=sheets if len(sheets) == 1 else [],
        )
        db.add(f)
        await db.flush()
        f.storage_path = _file_path(ds.id, f.id, filename)
        await storage.upload(f.storage_path, content)  # raw file stored untouched
        _apply_encoding(f, content)
        added.append(f)
    await AuditService(db).log(
        event_type="recon.files_added", target_type="ReconDataset", target_id=ds.id, action=AuditAction.UPDATE,
        actor_id=actor_id, actor_type=ActorType.USER, after_state={"files": [f.filename for f in added]},
    )
    await db.commit()
    return added


async def get_file(db: AsyncSession, ds: ReconDataset, file_id: UUID) -> ReconFile:
    f = await db.get(ReconFile, file_id)
    if f is None or f.dataset_id != ds.id:
        raise NotFoundError("File not found in this dataset", details={"file_id": str(file_id)})
    return f


async def update_file(
    db: AsyncSession, storage: StorageService, ds: ReconDataset, f: ReconFile, changes: dict[str, Any], actor_id: UUID
) -> ReconFile:
    """``changes`` may hold: ``encoding`` (force; ``""`` clears), ``candidate_encodings`` (restrict the
    search), ``selected_sheets``, ``header_row``."""
    _assert_draft(ds)
    choice = dict(f.encoding_choice or {})
    redo_encoding = False
    if "encoding" in changes:
        choice["forced"] = changes["encoding"] or None
        redo_encoding = True
    if "candidate_encodings" in changes:
        choice["candidates"] = changes["candidate_encodings"] or None
        redo_encoding = True
    if redo_encoding:
        f.encoding_choice = choice
        _apply_encoding(f, await storage.download(f.storage_path))
    if "selected_sheets" in changes:
        unknown = [s for s in changes["selected_sheets"] if s not in f.sheets]
        if unknown:
            raise ValidationError(f"Unknown sheet(s): {', '.join(unknown)}", details=[{"available_sheets": f.sheets}])
        f.selected_sheets = list(changes["selected_sheets"])
    if "header_row" in changes:
        if int(changes["header_row"]) < 1:
            raise ValidationError("header_row must be >= 1")
        f.header_row = int(changes["header_row"])
    await AuditService(db).log(
        event_type="recon.file_updated", target_type="ReconFile", target_id=f.id, action=AuditAction.UPDATE,
        actor_id=actor_id, actor_type=ActorType.USER, after_state=to_jsonable(changes),
    )
    await db.commit()
    return f


async def remove_file(db: AsyncSession, storage: StorageService, ds: ReconDataset, f: ReconFile, actor_id: UUID) -> None:
    _assert_draft(ds)
    await storage.delete(f.storage_path)
    await db.delete(f)
    await AuditService(db).log(
        event_type="recon.file_removed", target_type="ReconDataset", target_id=ds.id, action=AuditAction.DELETE,
        actor_id=actor_id, actor_type=ActorType.USER, before_state={"file": f.filename},
    )
    await db.commit()


async def encoding_check(storage: StorageService, f: ReconFile, candidates: list[str] | None) -> dict[str, Any]:
    """Re-run the multi-encoding comparison with a different candidate list, without saving anything."""
    if f.format != "CSV":
        return {"method": "NOT_APPLICABLE"}
    return decide_encoding(await storage.download(f.storage_path), None, candidates).as_dict()


# --- building tables -------------------------------------------------------------


async def _read_tables(db: AsyncSession, storage: StorageService, ds: ReconDataset) -> list[dict[str, Any]]:
    files = await list_files(db, ds.id)
    if not files:
        raise ValidationError("Upload at least one file first")
    tables: list[dict[str, Any]] = []
    for f in files:
        if not f.selected_sheets:
            raise ValidationError(
                f"Choose at least one sheet of '{f.filename}'", details=[{"file": f.filename, "available_sheets": f.sheets}]
            )
        content = await storage.download(f.storage_path)
        for sheet in f.selected_sheets:
            try:
                t = read_table(f.format, content, sheet, f.encoding, f.header_row)
            except ValidationError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise ValidationError(f"Could not read '{f.filename}' ({sheet}): {exc}") from exc
            tables.append(
                {"id": f"{f.id}:{sheet}", "file": f.filename, "sheet": sheet if sheet != SINGLE_SHEET else "", "columns": t.columns, "rows": t.rows}
            )
    return tables


async def schema_preview(
    db: AsyncSession, storage: StorageService, ds: ReconDataset, aliases: dict[str, str] | None
) -> dict[str, Any]:
    tables = await _read_tables(db, storage, ds)
    summary = build_schema_summary(tables, aliases)
    samples = {
        t["id"]: [{c: _jsonable(r.get(c)) for c in t["columns"]} for r in t["rows"][:5]] for t in tables
    }
    return {"summary": summary, "samples": samples, "total_rows": sum(len(t["rows"]) for t in tables)}


def _jsonable(v: Any) -> Any:
    return to_jsonable(v) if not isinstance(v, (str, int, float, type(None))) else v


async def finalize_dataset(
    db: AsyncSession, storage: StorageService, ds: ReconDataset, options: dict[str, Any], actor_id: UUID
) -> ReconDataset:
    _assert_draft(ds)
    tables = await _read_tables(db, storage, ds)
    combined = combine_tables(
        tables,
        aliases=options.get("column_aliases") or None,
        period_column=options.get("period_column") or None,
        day_first=bool(options.get("day_first", True)),
        drop_cross_file_duplicates=bool(options.get("drop_cross_file_duplicates", False)),
    )
    payload = {"columns": combined["columns"], "rows": combined["rows"]}
    result = await storage.upload(
        _final_path(ds.id), json.dumps(to_jsonable(payload)).encode("utf-8"), "application/json", overwrite=True
    )  # a dataset can be re-finalised after its inputs change
    report = combined["report"]
    report["checksum"] = result.checksum
    ds.config = {
        **(ds.config or {}),  # keeps provenance such as source_run_id
        "column_aliases": options.get("column_aliases") or {},
        "period_column": report["period_column"],
        "day_first": report["day_first"],
        "drop_cross_file_duplicates": bool(options.get("drop_cross_file_duplicates", False)),
    }
    ds.report, ds.storage_path = to_jsonable(report), result.path
    ds.row_count, ds.column_count = report["row_count"], report["column_count"]
    ds.status, ds.finalized_at = "FINAL", utcnow()
    await AuditService(db).log(
        event_type="recon.dataset_finalized", target_type="ReconDataset", target_id=ds.id, action=AuditAction.APPROVE,
        actor_id=actor_id, actor_type=ActorType.USER,
        after_state={"rows": ds.row_count, "columns": ds.column_count, "years": report["years"], "checksum": result.checksum},
    )
    await db.commit()
    return ds


async def load_final(storage: StorageService, ds: ReconDataset) -> dict[str, Any]:
    if ds.status != "FINAL" or not ds.storage_path:
        raise StateError("Dataset is not final yet", code="DATASET_NOT_FINAL")
    return json.loads(await storage.download(ds.storage_path))


async def dataset_preview(storage: StorageService, ds: ReconDataset, limit: int = _PREVIEW_ROWS) -> dict[str, Any]:
    data = await load_final(storage, ds)
    cols = data["columns"]
    return {
        "columns": [
            {"name": c, "type": (ds.report or {}).get("column_types", {}).get(c) or infer_type([r.get(c) for r in data["rows"][:500]]),
             "derived": c in RESERVED}
            for c in cols
        ],
        "rows": data["rows"][:limit],
        "row_count": len(data["rows"]),
    }


async def column_values(storage: StorageService, ds: ReconDataset, column: str, q: str | None, limit: int) -> dict[str, Any]:
    data = await load_final(storage, ds)
    column = column.lower()
    if column not in data["columns"]:
        raise NotFoundError("Unknown column", details={"column": column})
    counts: dict[str, int] = {}
    for r in data["rows"]:
        v = r.get(column)
        if v is None or v == "":
            continue
        s = str(v)
        if q and q.lower() not in s.lower():
            continue
        counts[s] = counts.get(s, 0) + 1
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"column": column, "distinct": len(items), "values": [{"value": v, "rows": n} for v, n in items[:limit]]}


# --- reconciliation runs ----------------------------------------------------------


async def run_reconciliation(
    db: AsyncSession, storage: StorageService, project_id: UUID, spec: dict[str, Any], actor_id: UUID
) -> ReconRun:
    b_ds = await get_dataset(db, UUID(str(spec["bordereaux_dataset_id"])))
    s_ds = await get_dataset(db, UUID(str(spec["subledger_dataset_id"])))
    for ds, kind in ((b_ds, "BORDEREAUX"), (s_ds, "SUBLEDGER")):
        if ds.kind != kind or ds.project_id != project_id:
            raise ValidationError(f"The {kind.lower()} dataset must be a {kind} dataset of this project")
    b, s = await load_final(storage, b_ds), await load_final(storage, s_ds)
    columns = {"bordereaux": set(b["columns"]), "subledger": set(s["columns"])}
    result = engine.reconcile(
        b["rows"], s["rows"], columns, spec.get("rules") or [], spec.get("group_by"), spec.get("filters"), spec.get("tolerance")
    )
    run = ReconRun(
        project_id=project_id,
        name=(spec.get("name") or "Reconciliation").strip() or "Reconciliation",
        bordereaux_dataset_id=b_ds.id,
        subledger_dataset_id=s_ds.id,
        config={k: spec.get(k) for k in ("rules", "group_by", "filters", "tolerance")},
        summary={},
        status=result["status"],
        created_by=actor_id,
    )
    db.add(run)
    await db.flush()
    run.result_path = _result_path(run.id)
    await storage.upload(run.result_path, json.dumps(to_jsonable(result)).encode("utf-8"), "application/json")
    run.summary = to_jsonable(
        {
            "status": result["status"],
            "rows_in_scope": result["rows_in_scope"],
            "rules": [
                {"rule_id": r["rule_id"], "name": r["name"], "expression": r["expression"], "status": r["status"],
                 "counts": r["counts"], "totals": r["totals"], "offsetting_differences": r["offsetting_differences"]}
                for r in result["rules"]
            ],
        }
    )
    await AuditService(db).log(
        event_type="recon.run_completed", target_type="ReconRun", target_id=run.id, action=AuditAction.EXECUTE,
        actor_id=actor_id, actor_type=ActorType.USER, after_state={"status": run.status, "rules": len(result["rules"])},
    )
    await db.commit()
    return run


async def get_run(db: AsyncSession, run_id: UUID) -> ReconRun:
    run = await db.get(ReconRun, run_id)
    if run is None:
        raise NotFoundError("Reconciliation run not found", details={"run_id": str(run_id)})
    return run


async def list_runs(db: AsyncSession, project_id: UUID) -> list[ReconRun]:
    stmt = select(ReconRun).where(ReconRun.project_id == project_id).order_by(ReconRun.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def run_result(storage: StorageService, run: ReconRun) -> dict[str, Any]:
    return json.loads(await storage.download(run.result_path))


async def group_records(
    db: AsyncSession, storage: StorageService, run: ReconRun, rule_id: str, key: list[str], side: str
) -> dict[str, Any]:
    """Source rows behind one reconciliation group (same filters/grain as the run)."""
    if side not in ("bordereaux", "subledger"):
        raise ValidationError("side must be bordereaux or subledger")
    ds = await get_dataset(db, run.bordereaux_dataset_id if side == "bordereaux" else run.subledger_dataset_id)
    data = await load_final(storage, ds)
    cfg = run.config
    flt = engine.normalize_filters(cfg.get("filters"))
    rows = engine.apply_filters(data["rows"], flt, side)
    group_by = cfg.get("group_by") or []
    cols = [g[side].lower() for g in group_by]
    if len(cols) != len(key):
        raise ValidationError("Group key does not match the run's grain")
    matched = [r for r in rows if all(engine.key_text(r.get(c)) == engine.key_text(k) for c, k in zip(cols, key))]
    return {"side": side, "total": len(matched), "columns": data["columns"], "rows": matched[:_DRILLDOWN_LIMIT]}


async def export_csv(storage: StorageService, run: ReconRun) -> bytes:
    result = await run_result(storage, run)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rule_id", "rule", "expression", "grain", "group", "bordereaux_value", "subledger_value", "variance", "variance_pct", "status", "bordereaux_rows", "subledger_rows"])
    for r in result["rules"]:
        for g in r["groups"]:
            w.writerow([r["rule_id"], r["name"], r["expression"], " | ".join(r["grain"]), " | ".join(g["labels"]) or "(total)",
                        g["bordereaux_value"], g["subledger_value"], g["variance"], g["variance_pct"], g["status"],
                        g["bordereaux_rows"], g["subledger_rows"]])
    return buf.getvalue().encode("utf-8")


def encoding_options() -> list[dict[str, str]]:
    return [{"value": v, "label": label} for v, label in SUPPORTED_ENCODINGS]


async def bordereaux_from_run(
    db: AsyncSession, storage: StorageService, run_id: UUID, actor_id: UUID, max_bytes: int
) -> tuple[ReconDataset, bool]:
    """Turn a completed processing run's *processed file* into a FINAL
    bordereaux dataset for reconciliation, without re-uploading anything.
    Idempotent: a run yields one dataset; calling again returns it
    (``created`` is False)."""
    from bordereaux.models.artifact import ProcessedFileArtifact
    from bordereaux.models.run import ProcessingRun

    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.status != "COMPLETED":
        raise StateError(
            f"Reports must be generated first (run status: {run.status})", code="RUN_NOT_COMPLETED",
            details={"run_id": str(run_id), "status": run.status},
        )
    for ds in await list_datasets(db, run.project_id, "BORDEREAUX"):
        if (ds.config or {}).get("source_run_id") == str(run_id) and ds.status == "FINAL":
            return ds, False
    artifact = (
        await db.execute(
            select(ProcessedFileArtifact).where(ProcessedFileArtifact.run_id == run_id).order_by(ProcessedFileArtifact.generated_at.desc())
        )
    ).scalars().first()
    if artifact is None:
        raise NotFoundError("This run has no processed file yet", details={"run_id": str(run_id)})
    content = await storage.download(artifact.storage_path)

    ds = await create_dataset(db, run.project_id, "BORDEREAUX", f"Processed run {str(run_id)[:8]}", actor_id)
    ds.config = {"source_run_id": str(run_id), "source": "PROCESSED_FILE"}
    await db.commit()
    await add_files(db, storage, ds, [(f"processed_{run_id}.csv", content)], actor_id, max_bytes)
    header = content.split(b"\n", 1)[0].decode("utf-8", errors="replace").lower()
    period = "booking_date" if "booking_date" in header.split(",") else None
    ds = await finalize_dataset(db, storage, ds, {"period_column": period, "day_first": False}, actor_id)
    return ds, True
