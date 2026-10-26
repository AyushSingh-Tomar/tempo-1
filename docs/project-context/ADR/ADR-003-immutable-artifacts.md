# ADR-003: Immutable Artifacts with Versioning

## Status
**Accepted**

## Date
2026-10-09

## Context

The platform processes financial data where audit trails and reproducibility are critical. We need a strategy for handling data mutations while maintaining full lineage.

### Requirements

- Trace any output value to source file and row
- Reproduce any historical reconciliation result
- Support rollback to previous states
- Maintain compliance-ready audit trail

## Decision

All artifacts are **immutable once created**. Changes create new versions.

### Artifact Lifecycle

```
Upload → Raw Asset (immutable)
              ↓
         Parse (creates SourceVersion v1)
              ↓
         Profile (attached to version)
              ↓
         Approve Mappings (creates MappingSet v1)
              ↓
         Standardize (creates ClaimsMapping v1)
              ↓
         Reconcile (creates ReconciliationRun, VarianceRecords)
```

### Versioning Rules

1. **Raw files** — Stored with SHA-256 checksum, never modified
2. **Parsed data** — New version on re-parse, old versions retained
3. **Profiles** — Attached to specific version, immutable
4. **Mappings** — MappingSet versions, can be superseded
5. **Standardized output** — New version per mapping set change
6. **Reconciliation** — Each run is a new record with full config

### Data Model

```python
class SourceVersion:
    id: UUID
    asset_id: UUID
    version_number: int  # Monotonic
    storage_path: str    # Points to immutable Parquet
    row_count: int
    status: VersionStatus

class MappingSet:
    id: UUID
    version_id: UUID
    version_number: int
    status: Literal["DRAFT", "FINALIZED", "SUPERSEDED"]
```

### Lineage Chain

Every derived value maintains backward references:

```
VarianceRecord
  ├── reported_lineage: ClaimsMappingRow → SourceVersionRow → RawFile:Row
  └── subledger_lineage: SubledgerRow → SourceVersionRow → RawFile:Row
```

## Consequences

### Positive

- **Full auditability** — Complete history preserved
- **Reproducibility** — Re-run any historical state
- **Compliance ready** — No hidden mutations
- **Debug-friendly** — Compare versions easily
- **Rollback support** — Revert to any previous version

### Negative

- **Storage growth** — Multiple versions consume space
- **Query complexity** — Must filter by version/status
- **Cleanup needed** — Retention policies required

### Mitigation

- Retention policies for old versions (keep 7 years for compliance)
- Efficient storage with Parquet columnar format
- Soft deletes with `deleted_at` timestamps
- Archive cold versions to cheaper storage

## Implementation

### Creating New Version

```python
async def create_new_version(asset_id: UUID, parsed_data: DataFrame) -> SourceVersion:
    # Get latest version number
    latest = await repo.get_latest_version(asset_id)
    new_number = (latest.version_number + 1) if latest else 1
    
    # Store immutably
    path = f"parsed/{asset_id}/v{new_number}/data.parquet"
    await storage.write_parquet(path, parsed_data)
    
    # Create version record
    return await repo.create_version(
        asset_id=asset_id,
        version_number=new_number,
        storage_path=path,
        row_count=len(parsed_data)
    )
```

### Querying with Versions

```python
# Get latest finalized mapping set
mapping_set = await repo.get_mapping_set(
    version_id=version_id,
    status=MappingStatus.FINALIZED
)

# Get specific historical version
historical = await repo.get_mapping_set_by_version(
    version_id=version_id,
    version_number=3
)
```

## References

- Artifact: Module_2_Reconciliation_Implement.md (lineage requirements)
- REQUIREMENTS.md (FR-LIN-*, FR-VER-*)
- ANSWERING_OPEN_QUESTION.md (OQ-08)
