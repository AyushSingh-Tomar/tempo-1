# Data Model & Migration Strategy
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Database:** PostgreSQL 15+

---

## 1. Database Design Principles

### 1.1 Core Principles

1. **Immutable artifacts** — Raw data never modified, only new versions
2. **Full lineage** — Every derived value traceable to source
3. **Audit everything** — All state changes logged
4. **Soft deletes** — Retain history, use `deleted_at`
5. **UUID primary keys** — Globally unique, no sequence leaks
6. **Timestamp consistency** — All timestamps in UTC

### 1.2 Naming Conventions

- **Tables:** `snake_case`, plural (`source_assets`)
- **Columns:** `snake_case`
- **Indexes:** `ix_{table}_{columns}`
- **Foreign keys:** `fk_{table}_{referenced_table}`
- **Constraints:** `ck_{table}_{constraint}`

---

## 2. Entity Relationship Diagram

```
┌──────────────┐     ┌────────────────┐     ┌─────────────────┐
│   projects   │────<│  source_assets │────<│ source_versions │
└──────────────┘     └────────────────┘     └─────────────────┘
       │                                            │
       │                                            │
       │                                    ┌───────┴───────┐
       │                                    │               │
       │                             ┌──────┴─────┐  ┌──────┴──────┐
       │                             │data_profiles│  │mapping_sets │
       │                             └────────────┘  └──────┬──────┘
       │                                                    │
       │                                             ┌──────┴──────┐
       │                                             │   mappings  │
       │                                             └─────────────┘
       │
       ├─────────<│ claims_mappings │
       │
       ├─────────<│   subledgers    │
       │
       └─────────<│ reconciliations │────<│ variance_records │
                          │
                          └────<│ diagnostic_findings │

┌──────────────┐     ┌────────────────┐
│    users     │     │  audit_events  │
└──────────────┘     └────────────────┘

┌──────────────┐     ┌────────────────┐
│canonical_    │     │     jobs       │
│schemas       │     └────────────────┘
└──────────────┘
```

---

## 3. Table Definitions

### 3.1 Projects

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'CREATED',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT ck_projects_status CHECK (
        status IN ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED')
    )
);

CREATE INDEX ix_projects_status ON projects(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_projects_created_by ON projects(created_by);
CREATE INDEX ix_projects_created_at ON projects(created_at DESC);
```

### 3.2 Users (MVP Minimal)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    CONSTRAINT ck_users_role CHECK (
        role IN ('admin', 'project_owner', 'analyst', 'reviewer', 'viewer')
    )
);

CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_external_id ON users(external_id) WHERE external_id IS NOT NULL;
```

### 3.3 Source Assets

```sql
CREATE TABLE source_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    original_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    size_bytes BIGINT NOT NULL,
    checksum VARCHAR(128) NOT NULL,
    format VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'UPLOADED',
    metadata JSONB DEFAULT '{}',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT ck_source_assets_status CHECK (
        status IN ('UPLOADED', 'PARSING', 'PARSED', 'FAILED', 'DELETED')
    ),
    CONSTRAINT ck_source_assets_format CHECK (
        format IN ('CSV', 'TSV', 'XLSX', 'XLS', 'JSON', 'JSONL', 'PARQUET')
    )
);

CREATE INDEX ix_source_assets_project_id ON source_assets(project_id);
CREATE INDEX ix_source_assets_checksum ON source_assets(checksum);
CREATE INDEX ix_source_assets_format ON source_assets(format);
```

### 3.4 Source Versions

```sql
CREATE TABLE source_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES source_assets(id),
    version_number INT NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    row_count INT NOT NULL,
    column_count INT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PARSED',
    structure JSONB NOT NULL,
    parse_errors JSONB DEFAULT '[]',
    parse_job_id UUID REFERENCES jobs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_source_versions_status CHECK (
        status IN ('PARSED', 'PROFILED', 'MAPPED', 'STANDARDIZED', 'FAILED')
    ),
    CONSTRAINT uq_source_versions_asset_version 
        UNIQUE (asset_id, version_number)
);

CREATE INDEX ix_source_versions_asset_id ON source_versions(asset_id);
CREATE INDEX ix_source_versions_status ON source_versions(status);

-- structure JSONB example:
-- {
--   "header_row": 1,
--   "data_start_row": 2,
--   "column_names": ["CLAIM_NO", "POL_REF", ...],
--   "detected_encoding": "UTF-8",
--   "detected_delimiter": ","
-- }
```

### 3.5 Data Profiles

```sql
CREATE TABLE data_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES source_versions(id),
    row_count INT NOT NULL,
    column_count INT NOT NULL,
    profile_job_id UUID REFERENCES jobs(id),
    profiled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_data_profiles_version UNIQUE (version_id)
);

CREATE TABLE column_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES data_profiles(id),
    name VARCHAR(255) NOT NULL,
    position INT NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    null_count INT NOT NULL DEFAULT 0,
    null_percentage DECIMAL(5,4) NOT NULL DEFAULT 0,
    distinct_count INT NOT NULL,
    distinct_percentage DECIMAL(5,4) NOT NULL,
    top_values JSONB DEFAULT '[]',
    numeric_stats JSONB,
    string_stats JSONB,
    date_stats JSONB,
    patterns JSONB DEFAULT '[]',
    
    CONSTRAINT ck_column_profiles_data_type CHECK (
        data_type IN ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'DATE', 'DATETIME', 'UNKNOWN')
    ),
    CONSTRAINT uq_column_profiles_position 
        UNIQUE (profile_id, position)
);

CREATE INDEX ix_column_profiles_profile_id ON column_profiles(profile_id);
CREATE INDEX ix_column_profiles_data_type ON column_profiles(data_type);
```

### 3.6 Canonical Schemas

```sql
CREATE TABLE canonical_schemas (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    standard VARCHAR(50) NOT NULL DEFAULT 'CUSTOM',
    definition JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_canonical_schemas_standard CHECK (
        standard IN ('ACORD', 'CUSTOM', 'PROPRIETARY')
    )
);

-- definition JSONB contains full schema with fields array
```

### 3.7 Schema Templates

```sql
CREATE TABLE schema_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scope VARCHAR(50) NOT NULL DEFAULT 'PROJECT',
    project_id UUID REFERENCES projects(id),
    target_schema_id VARCHAR(100) NOT NULL REFERENCES canonical_schemas(id),
    source_signature JSONB NOT NULL,
    field_mappings JSONB NOT NULL,
    flexibility VARCHAR(50) NOT NULL DEFAULT 'FLEXIBLE',
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    usage_count INT NOT NULL DEFAULT 0,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_schema_templates_scope CHECK (
        scope IN ('PROJECT', 'GLOBAL')
    ),
    CONSTRAINT ck_schema_templates_flexibility CHECK (
        flexibility IN ('STRICT', 'FLEXIBLE', 'LOOSE')
    ),
    CONSTRAINT ck_schema_templates_status CHECK (
        status IN ('ACTIVE', 'DEPRECATED', 'ARCHIVED')
    ),
    CONSTRAINT ck_schema_templates_project_scope CHECK (
        (scope = 'GLOBAL' AND project_id IS NULL) OR
        (scope = 'PROJECT' AND project_id IS NOT NULL)
    )
);

CREATE INDEX ix_schema_templates_project_id ON schema_templates(project_id);
CREATE INDEX ix_schema_templates_scope ON schema_templates(scope);
CREATE INDEX ix_schema_templates_status ON schema_templates(status);
CREATE INDEX ix_schema_templates_target_schema ON schema_templates(target_schema_id);

CREATE TABLE template_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES schema_templates(id),
    version_id UUID NOT NULL REFERENCES source_versions(id),
    mapping_set_id UUID NOT NULL REFERENCES mapping_sets(id),
    match_score DECIMAL(5,4) NOT NULL,
    applied_rules INT NOT NULL,
    total_rules INT NOT NULL,
    applied_by UUID NOT NULL REFERENCES users(id),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_template_applications_template_id ON template_applications(template_id);
CREATE INDEX ix_template_applications_version_id ON template_applications(version_id);

-- source_signature JSONB example:
-- {
--   "column_patterns": [
--     {"name_pattern": "CLAIM_NO|claim_id", "expected_type": "STRING", "required": true},
--     {"name_pattern": ".*_AMT$|amount", "expected_type": "DECIMAL", "required": false}
--   ],
--   "signature_hash": "sha256:abc123...",
--   "min_columns": 10,
--   "max_columns": 20
-- }

-- field_mappings JSONB example:
-- [
--   {
--     "source_pattern": "CLAIM_NO|claim_id|clm_ref",
--     "target_field": "claim_id",
--     "match_strategy": "REGEX",
--     "confidence_boost": 0.15,
--     "priority": 1
--   },
--   {
--     "source_pattern": "GROSS_AMT",
--     "target_field": "gross_amount",
--     "match_strategy": "EXACT_NAME",
--     "transformation": {"type": "TYPE_CAST", "parameters": {"to_type": "DECIMAL"}},
--     "confidence_boost": 0.20,
--     "priority": 2
--   }
-- ]
```

### 3.8 Mapping Sets and Mappings

```sql
CREATE TABLE mapping_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES source_versions(id),
    schema_id VARCHAR(100) NOT NULL REFERENCES canonical_schemas(id),
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT',
    coverage_required DECIMAL(5,4),
    coverage_optional DECIMAL(5,4),
    generation_job_id UUID REFERENCES jobs(id),
    finalized_by UUID REFERENCES users(id),
    finalized_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_mapping_sets_status CHECK (
        status IN ('DRAFT', 'FINALIZED', 'SUPERSEDED')
    )
);

CREATE INDEX ix_mapping_sets_version_id ON mapping_sets(version_id);
CREATE INDEX ix_mapping_sets_status ON mapping_sets(status);

CREATE TABLE mapping_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_set_id UUID NOT NULL REFERENCES mapping_sets(id),
    source_column VARCHAR(255) NOT NULL,
    target_field VARCHAR(255) NOT NULL,
    confidence_total DECIMAL(5,4) NOT NULL,
    confidence_breakdown JSONB NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(50) NOT NULL DEFAULT 'PROPOSED',
    auto_approve_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_mapping_candidates_status CHECK (
        status IN ('PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED')
    )
);

CREATE INDEX ix_mapping_candidates_set_id ON mapping_candidates(mapping_set_id);
CREATE INDEX ix_mapping_candidates_status ON mapping_candidates(status);
CREATE INDEX ix_mapping_candidates_source ON mapping_candidates(source_column);
CREATE INDEX ix_mapping_candidates_confidence 
    ON mapping_candidates(confidence_total DESC);

CREATE TABLE approved_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_set_id UUID NOT NULL REFERENCES mapping_sets(id),
    source_column VARCHAR(255) NOT NULL,
    target_field VARCHAR(255) NOT NULL,
    origin VARCHAR(50) NOT NULL,
    confidence_total DECIMAL(5,4) NOT NULL,
    transformation JSONB,
    candidate_id UUID REFERENCES mapping_candidates(id),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_approved_mappings_origin CHECK (
        origin IN ('APPROVED', 'MANUAL', 'AUTO_APPROVED')
    ),
    CONSTRAINT uq_approved_mappings_source 
        UNIQUE (mapping_set_id, source_column)
);

CREATE INDEX ix_approved_mappings_set_id ON approved_mappings(mapping_set_id);
```

### 3.8 Claims Mappings (Standardized)

```sql
CREATE TABLE claims_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    version_id UUID NOT NULL REFERENCES source_versions(id),
    mapping_set_id UUID NOT NULL REFERENCES mapping_sets(id),
    schema_id VARCHAR(100) NOT NULL REFERENCES canonical_schemas(id),
    storage_path VARCHAR(1000) NOT NULL,
    row_count INT NOT NULL,
    valid_rows INT NOT NULL,
    error_rows INT NOT NULL DEFAULT 0,
    column_list JSONB NOT NULL,
    standardization_job_id UUID REFERENCES jobs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_claims_mappings_version 
        UNIQUE (version_id, mapping_set_id)
);

CREATE INDEX ix_claims_mappings_project_id ON claims_mappings(project_id);
CREATE INDEX ix_claims_mappings_version_id ON claims_mappings(version_id);
```

### 3.9 Subledgers

```sql
CREATE TABLE subledgers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    source_asset_id UUID NOT NULL REFERENCES source_assets(id),
    storage_path VARCHAR(1000) NOT NULL,
    row_count INT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PROCESSING',
    mapping_set_id UUID REFERENCES mapping_sets(id),
    processing_job_id UUID REFERENCES jobs(id),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_subledgers_status CHECK (
        status IN ('PROCESSING', 'READY', 'FAILED')
    )
);

CREATE INDEX ix_subledgers_project_id ON subledgers(project_id);
CREATE INDEX ix_subledgers_status ON subledgers(status);
```

### 3.10 Reconciliations

```sql
CREATE TABLE reconciliations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    claims_mapping_id UUID NOT NULL REFERENCES claims_mappings(id),
    subledger_id UUID NOT NULL REFERENCES subledgers(id),
    config JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED',
    summary JSONB,
    job_id UUID REFERENCES jobs(id),
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    CONSTRAINT ck_reconciliations_status CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    )
);

CREATE INDEX ix_reconciliations_project_id ON reconciliations(project_id);
CREATE INDEX ix_reconciliations_status ON reconciliations(status);
CREATE INDEX ix_reconciliations_created_at ON reconciliations(created_at DESC);

-- config JSONB example:
-- {
--   "key_columns": ["claim_id"],
--   "measure_column": "net_amount",
--   "group_by": ["currency", "reporting_period"],
--   "variance_thresholds": {
--     "absolute": {"enabled": true, "value": 100},
--     "percentage": {"enabled": true, "value": 0.01},
--     "mode": "OR"
--   },
--   "diagnostics": {
--     "enabled": true,
--     "checks": ["D001", "D003", ...]
--   }
-- }
```

### 3.11 Variance Records

```sql
CREATE TABLE variance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reconciliation_id UUID NOT NULL REFERENCES reconciliations(id),
    key_values JSONB NOT NULL,
    group_values JSONB,
    reported_value DECIMAL(20,4),
    subledger_value DECIMAL(20,4),
    absolute_variance DECIMAL(20,4),
    percentage_variance DECIMAL(10,6),
    status VARCHAR(50) NOT NULL,
    thresholds_applied JSONB NOT NULL,
    lineage JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_variance_records_status CHECK (
        status IN ('MATCH', 'WITHIN_TOLERANCE', 'UNRECONCILED', 
                   'REPORTED_ONLY', 'SUBLEDGER_ONLY')
    )
);

CREATE INDEX ix_variance_records_reconciliation_id 
    ON variance_records(reconciliation_id);
CREATE INDEX ix_variance_records_status 
    ON variance_records(status);
CREATE INDEX ix_variance_records_variance 
    ON variance_records(ABS(absolute_variance) DESC);
CREATE INDEX ix_variance_records_key_values 
    ON variance_records USING GIN (key_values);
```

### 3.12 Diagnostic Findings

```sql
CREATE TABLE diagnostic_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reconciliation_id UUID NOT NULL REFERENCES reconciliations(id),
    check_id VARCHAR(10) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}',
    evidence JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_diagnostic_findings_category CHECK (
        category IN ('STRUCTURAL', 'COMPLETENESS', 'INTEGRITY', 
                     'VALUE', 'DISTRIBUTION')
    ),
    CONSTRAINT ck_diagnostic_findings_severity CHECK (
        severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    )
);

CREATE INDEX ix_diagnostic_findings_reconciliation_id 
    ON diagnostic_findings(reconciliation_id);
CREATE INDEX ix_diagnostic_findings_check_id 
    ON diagnostic_findings(check_id);
CREATE INDEX ix_diagnostic_findings_severity 
    ON diagnostic_findings(severity);
```

### 3.13 Jobs

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    project_id UUID REFERENCES projects(id),
    input JSONB NOT NULL DEFAULT '{}',
    output JSONB,
    progress JSONB DEFAULT '{"percentage": 0}',
    error JSONB,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    CONSTRAINT ck_jobs_type CHECK (
        type IN ('PARSE', 'PROFILE', 'GENERATE_MAPPINGS', 
                 'STANDARDIZE', 'RECONCILE', 'REPORT')
    ),
    CONSTRAINT ck_jobs_status CHECK (
        status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    )
);

CREATE INDEX ix_jobs_type ON jobs(type);
CREATE INDEX ix_jobs_status ON jobs(status);
CREATE INDEX ix_jobs_project_id ON jobs(project_id);
CREATE INDEX ix_jobs_created_at ON jobs(created_at DESC);
```

### 3.14 Audit Events

```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    actor_id UUID NOT NULL REFERENCES users(id),
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID NOT NULL,
    project_id UUID REFERENCES projects(id),
    before_state JSONB,
    after_state JSONB,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_audit_events_resource 
    ON audit_events(resource_type, resource_id);
CREATE INDEX ix_audit_events_actor_id 
    ON audit_events(actor_id);
CREATE INDEX ix_audit_events_project_id 
    ON audit_events(project_id);
CREATE INDEX ix_audit_events_timestamp 
    ON audit_events(timestamp DESC);
CREATE INDEX ix_audit_events_event_type 
    ON audit_events(event_type);

-- Partition by month for performance
-- CREATE TABLE audit_events_y2026m10 PARTITION OF audit_events
--     FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
```

### 3.15 Lineage Records

```sql
CREATE TABLE lineage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_type VARCHAR(100) NOT NULL,
    artifact_id UUID NOT NULL,
    source_type VARCHAR(100) NOT NULL,
    source_id UUID NOT NULL,
    source_row_number INT,
    transformation VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT ck_lineage_records_artifact_type CHECK (
        artifact_type IN ('claims_mapping_row', 'subledger_row', 
                          'variance_record', 'diagnostic_finding')
    )
);

CREATE INDEX ix_lineage_records_artifact 
    ON lineage_records(artifact_type, artifact_id);
CREATE INDEX ix_lineage_records_source 
    ON lineage_records(source_type, source_id);
```

---

## 4. Data Types

### 4.1 Custom Types (Optional)

```sql
-- If enum types preferred over check constraints:
CREATE TYPE project_status AS ENUM ('CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED');
CREATE TYPE job_status AS ENUM ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED');
CREATE TYPE variance_status AS ENUM ('MATCH', 'WITHIN_TOLERANCE', 'UNRECONCILED', 
                                      'REPORTED_ONLY', 'SUBLEDGER_ONLY');
```

### 4.2 JSONB Schema Documentation

**variance_thresholds:**
```json
{
  "absolute": {
    "enabled": true,
    "value": 100.00
  },
  "percentage": {
    "enabled": true,
    "value": 0.01
  },
  "mode": "OR"
}
```

**confidence_breakdown:**
```json
{
  "alias_match": 0.25,
  "name_similarity": 0.20,
  "type_compatibility": 0.20,
  "pattern_match": 0.15,
  "position_hint": 0.05,
  "historical_match": 0.10
}
```

**column_profile.numeric_stats:**
```json
{
  "min": 0.0,
  "max": 500000.0,
  "mean": 15234.56,
  "median": 10000.0,
  "std_dev": 25000.0,
  "percentile_25": 5000.0,
  "percentile_75": 20000.0
}
```

---

## 5. Migration Strategy

### 5.1 Migration Tool

Using **Alembic** for SQLAlchemy-based migrations.

### 5.2 Initial Migration Structure

```
migrations/
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_users.py
    ├── 003_add_source_assets.py
    ├── 004_add_source_versions.py
    ├── 005_add_profiles.py
    ├── 006_add_mappings.py
    ├── 007_add_claims_mappings.py
    ├── 008_add_subledgers.py
    ├── 009_add_reconciliations.py
    ├── 010_add_diagnostics.py
    ├── 011_add_audit.py
    └── 012_add_indexes.py
```

### 5.3 Migration Example

```python
# 001_initial_schema.py
"""Initial schema - projects and users"""

from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
depends_on = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('name', sa.String(255)),
        sa.Column('role', sa.String(50), nullable=False, default='analyst'),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.String(50), nullable=False, default='CREATED'),
        sa.Column('created_by', sa.UUID(), 
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )
    
    op.create_index('ix_projects_status', 'projects', ['status'])
    op.create_index('ix_projects_created_by', 'projects', ['created_by'])

def downgrade():
    op.drop_table('projects')
    op.drop_table('users')
```

### 5.4 Migration Commands

```bash
# Create new migration
alembic revision -m "description"

# Auto-generate from model changes
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Show current revision
alembic current

# Show history
alembic history
```

### 5.5 Migration Best Practices

1. **One table per migration** for MVP simplicity
2. **Always test downgrade** before merging
3. **Never modify existing migrations** after deployment
4. **Use transactions** for atomic changes
5. **Add indexes in separate migrations** for large tables

---

## 6. Storage Strategy

### 6.1 What's Stored Where

| Data | Storage | Reason |
|------|---------|--------|
| Metadata | PostgreSQL | Queryable, relationships |
| Raw files | S3/Object Storage | Immutable, large |
| Parsed data | Parquet files | Columnar, efficient |
| Profiles | PostgreSQL | Queryable |
| Reports | S3/Object Storage | Large JSON |

### 6.2 File Organization

```
storage/
├── raw/
│   └── {project_id}/
│       └── {asset_id}/
│           └── {checksum}.{ext}
├── parsed/
│   └── {project_id}/
│       └── {version_id}/
│           └── data.parquet
├── standardized/
│   └── {project_id}/
│       └── {claims_mapping_id}/
│           └── data.parquet
├── subledgers/
│   └── {project_id}/
│       └── {subledger_id}/
│           └── data.parquet
└── reports/
    └── {project_id}/
        └── {reconciliation_id}/
            └── {report_id}.json
```

---

## 7. Performance Considerations

### 7.1 Indexing Strategy

- **Primary keys:** UUID with B-tree
- **Foreign keys:** Always indexed
- **Status columns:** Partial indexes for active records
- **JSONB columns:** GIN indexes for key queries
- **Timestamps:** Descending for recent-first queries

### 7.2 Partitioning (Post-MVP)

```sql
-- Partition audit_events by month
ALTER TABLE audit_events 
    PARTITION BY RANGE (timestamp);

-- Partition variance_records by reconciliation
ALTER TABLE variance_records 
    PARTITION BY LIST (reconciliation_id);
```

### 7.3 Query Optimization

- Use `EXPLAIN ANALYZE` for slow queries
- Limit JSONB queries on large tables
- Prefer specific columns over `SELECT *`
- Use pagination for list endpoints

---

## 8. Data Retention

### 8.1 Retention Policies

| Data | Retention | Reason |
|------|-----------|--------|
| Projects | Indefinite | User data |
| Raw files | 7 years | Compliance |
| Parsed data | 2 years | Performance |
| Audit events | 7 years | Compliance |
| Jobs | 90 days | Operational |

### 8.2 Archival Strategy (Post-MVP)

```sql
-- Archive old audit events
CREATE TABLE audit_events_archive (LIKE audit_events);

INSERT INTO audit_events_archive
SELECT * FROM audit_events
WHERE timestamp < NOW() - INTERVAL '1 year';

DELETE FROM audit_events
WHERE timestamp < NOW() - INTERVAL '1 year';
```

---

## 9. Backup Strategy

### 9.1 PostgreSQL Backups

- **Full backup:** Daily via `pg_dump`
- **Incremental:** WAL archiving for point-in-time recovery
- **Retention:** 30 days of daily backups

### 9.2 Object Storage Backups

- **Cross-region replication** for raw files
- **Versioning enabled** on buckets
- **Lifecycle policies** for cold storage transition

---

## 10. SQLAlchemy Models

### 10.1 Base Model

```python
# models/base.py

from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, 
                        onupdate=datetime.utcnow)

class UUIDMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
```

### 10.2 Project Model

```python
# models/project.py

from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, UUIDMixin

class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = 'projects'
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False, default='CREATED')
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), 
                        nullable=False)
    deleted_at = Column(DateTime(timezone=True))
    
    creator = relationship('User', back_populates='projects')
    assets = relationship('SourceAsset', back_populates='project')
    reconciliations = relationship('Reconciliation', back_populates='project')
```
