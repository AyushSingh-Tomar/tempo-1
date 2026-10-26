"""Loads the versioned canonical-schema YAML config into a ``CanonicalSchema``
row. The schema is configuration, not code (per ARCHITECTURE.md principle 7)
- adding/editing fields never requires a code change, only a new YAML
version with a bumped ``version`` string.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.exceptions import ConflictError
from bordereaux.models.schema import CanonicalSchema

_SCHEMAS_DIR = Path(__file__).parent


class SchemaVersionError(ConflictError):
    code = "SCHEMA_VERSION_CONFLICT"
    default_message = "The dictionary changed without a version bump"

#: canonical field name -> MoneyRole value, for fields that participate in
#: the money-column-resolution engine (bordereaux.money_rules.MoneyRole).
MONEY_ROLE_BY_FIELD: dict[str, str] = {}


def load_schema_definition(filename: str = "bordereaux_pc_v1.yaml") -> dict[str, Any]:
    """Parse a schema YAML file into the dict shape stored in
    ``canonical_schemas.definition``. Side effect: populates
    ``MONEY_ROLE_BY_FIELD`` from any ``money_role`` keys found."""
    path = _SCHEMAS_DIR / filename
    with path.open("r", encoding="utf-8") as fh:
        definition: dict[str, Any] = yaml.safe_load(fh)

    for field in definition.get("fields", []):
        role = field.get("money_role")
        if role:
            MONEY_ROLE_BY_FIELD[field["name"]] = role

    return definition


async def seed_canonical_schema(session: AsyncSession, filename: str = "bordereaux_pc_v1.yaml") -> CanonicalSchema:
    """Return the stored snapshot of this YAML, creating it when needed.

    Snapshots are immutable (DATA_MODEL.md §3.6) and are what a mapping set's
    ``schema_id`` points at, so the exact dictionary a run used stays on record.
    The first version of a schema keeps the plain YAML ``id``; later versions are
    stored as ``<id>@<version>``. If the YAML changed, bump its ``version``: an
    edit under an already-stored version is rejected rather than silently
    diverging from what earlier runs were mapped against."""
    definition = load_schema_definition(filename)
    base_id, version = definition["id"], str(definition["version"])
    fingerprint = definition_fingerprint(definition)

    existing = await session.get(CanonicalSchema, base_id)
    if existing is not None and existing.version == version:
        _assert_unchanged(existing, fingerprint, base_id, version)
        return existing
    if existing is None:
        stored_id = base_id
    else:
        stored_id = f"{base_id}@{version}"
        versioned = await session.get(CanonicalSchema, stored_id)
        if versioned is not None:
            _assert_unchanged(versioned, fingerprint, base_id, version)
            return versioned

    schema = CanonicalSchema(
        id=stored_id,
        name=definition["name"],
        version=version,
        standard=definition.get("standard", "CUSTOM"),
        definition=definition,
    )
    session.add(schema)
    await session.flush()
    return schema


def definition_fingerprint(definition: dict[str, Any]) -> str:
    """Stable SHA-256 of the dictionary content (key order and YAML formatting do not matter)."""
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _assert_unchanged(stored: CanonicalSchema, fingerprint: str, base_id: str, version: str) -> None:
    if definition_fingerprint(stored.definition) != fingerprint:
        raise SchemaVersionError(
            f"The dictionary '{base_id}' changed but its version is still {version}. "
            "Bump `version` in the YAML so the change is stored as a new immutable snapshot.",
            details={"schema_id": stored.id, "version": version},
        )


def required_fields(definition: dict[str, Any]) -> list[str]:
    return [f["name"] for f in definition["fields"] if f.get("required") == "mandatory"]


def treaty_figure_fields(definition: dict[str, Any]) -> list[str]:
    return [f["name"] for f in definition["fields"] if f.get("category") == "TREATY_FIGURES"]
