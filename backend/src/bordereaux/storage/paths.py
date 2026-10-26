"""Storage path conventions (ARCHITECTURE.md §4.3, adapted for processing runs).

All paths are relative, forward-slash separated, and rooted at ``{project_id}/``::

    {project_id}/sources/{asset_id}/original/{filename}
    {project_id}/sources/{asset_id}/parsed/{version_id}.parquet
    {project_id}/profiles/{version_id}.json
    {project_id}/mappings/{mapping_set_id}.json
    {project_id}/runs/{run_id}/cleaned/attempt-{n}.{ext}
    {project_id}/runs/{run_id}/processed/{artifact_id}.{ext}
    {project_id}/runs/{run_id}/reports/{report_id}.{ext}

Always build paths through these helpers - never from client-supplied input.
"""

from __future__ import annotations

import re
from uuid import UUID

_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from a user filename."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = _UNSAFE.sub("_", name).strip(". ")
    return name or "file"


def _ext(ext: str) -> str:
    ext = ext.lstrip(".").lower()
    if not ext or not ext.isalnum():
        raise ValueError(f"Invalid extension: {ext!r}")
    return ext


def raw_source_path(project_id: UUID, asset_id: UUID, filename: str) -> str:
    return f"{project_id}/sources/{asset_id}/original/{safe_filename(filename)}"


def parsed_version_path(project_id: UUID, asset_id: UUID, version_id: UUID) -> str:
    return f"{project_id}/sources/{asset_id}/parsed/{version_id}.parquet"


def profile_path(project_id: UUID, version_id: UUID) -> str:
    return f"{project_id}/profiles/{version_id}.json"


def mapping_set_path(project_id: UUID, mapping_set_id: UUID) -> str:
    return f"{project_id}/mappings/{mapping_set_id}.json"


def cleaned_data_path(project_id: UUID, run_id: UUID, attempt_number: int, ext: str = "parquet") -> str:
    return f"{project_id}/runs/{run_id}/cleaned/attempt-{int(attempt_number)}.{_ext(ext)}"


def processed_artifact_path(project_id: UUID, run_id: UUID, artifact_id: UUID, ext: str) -> str:
    return f"{project_id}/runs/{run_id}/processed/{artifact_id}.{_ext(ext)}"


def report_artifact_path(project_id: UUID, run_id: UUID, report_id: UUID, ext: str) -> str:
    return f"{project_id}/runs/{run_id}/reports/{report_id}.{_ext(ext)}"
