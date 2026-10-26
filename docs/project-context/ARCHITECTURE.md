# Architecture Specification
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved for MVP implementation

---

## 1. Architectural Overview

### 1.1 Architecture Style

**Modular Monolith** with clear domain boundaries and async worker support.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Gateway                                │
│                    (FastAPI + Authentication)                        │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────┐
│                          Application Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Project  │ │ Ingest   │ │ Mapping  │ │  Recon   │ │ Treaty   │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │ Service  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────┐
│                           Domain Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Ingestion│ │ Profiling│ │ Mapping  │ │Reconcile │ │ Treaty   │  │
│  │ Domain   │ │ Domain   │ │ Domain   │ │ Domain   │ │ Domain   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────┼───────────────────────────────────┐
│                        Infrastructure Layer                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Database │ │ Storage  │ │  Queue   │ │   LLM    │ │  Audit   │  │
│  │(Postgres)│ │ (S3/Local)│ │ (Redis)  │ │ Provider │ │ Logger   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| API | FastAPI | Async support, OpenAPI generation, Pydantic integration |
| Validation | Pydantic v2 | Type safety, serialization, schema generation |
| ORM | SQLAlchemy 2.0 | Async support, mature, well-documented |
| Migrations | Alembic | SQLAlchemy integration, version control |
| Database | PostgreSQL 15+ | JSONB support, reliability, performance |
| Object Storage | S3-compatible | Industry standard, local dev via MinIO |
| Task Queue | Celery + Redis | Proven, supports job states, retries |
| Tabular Processing | Polars / pandas | Performance (Polars), compatibility (pandas) |
| File Formats | PyArrow | Parquet read/write, cross-format support |
| Frontend | React 18 + TypeScript | Type safety, component ecosystem |
| State Management | Zustand or Redux Toolkit | Lightweight (Zustand) or feature-rich (RTK) |
| HTTP Client | TanStack Query | Caching, background refresh, optimistic updates |
| Containerization | Docker + Compose | Consistent environments, easy local setup |

### 1.3 Non-Negotiable Principles

1. **Deterministic First** — All calculations, joins, aggregations, validations are Python, never LLM
2. **Immutable Sources** — Uploaded files never modified
3. **Versioned Artifacts** — Every derived artifact has version, lineage, timestamp
4. **AI as Interpreter** — LLM output is untrusted proposal until validated
5. **Human Authority** — AI cannot approve financial decisions
6. **Explicit Contracts** — Module boundaries defined by interfaces
7. **Configurable Rules** — Business rules in configuration, not code

---

## 2. Module Architecture

### 2.1 Module Dependency Graph

```
                    ┌─────────────┐
                    │    Core     │
                    │  (Shared)   │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Ingestion   │  │    Mapping    │  │    Treaty     │
│    Module     │──▶│    Module     │  │    Module     │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │
        │                  ▼                  │
        │          ┌───────────────┐          │
        └─────────▶│Reconciliation │◀─────────┘
                   │    Module     │
                   └───────┬───────┘
                           │
                           ▼
                   ┌───────────────┐
                   │   Reporting   │
                   │    Module     │
                   └───────────────┘
```

### 2.2 Module Boundaries

| Module | Owns | Does Not Own |
|--------|------|--------------|
| **Core** | Models, storage abstraction, audit, auth, configuration | Business logic |
| **Ingestion** | File parsing, structure detection, format adapters | Semantic interpretation |
| **Profiling** | Statistics, pattern detection, type inference | Mapping decisions |
| **Mapping** | Candidate generation, scoring, approval workflow | Data transformation |
| **Standardization** | Type coercion, transformation execution | Mapping selection |
| **Reconciliation** | Variance calculation, diagnostics, comparison | Treaty rule definition |
| **Treaty** | State versioning, clause management, what-if | Reconciliation execution |
| **AI** | LLM abstraction, prompt management, caching | Business decisions |
| **Reporting** | Report generation, export formats | Data computation |

### 2.3 Dependency Rules

1. **Core** has no dependencies on other modules
2. **Domain modules** depend only on Core
3. **Application services** may compose multiple domain modules
4. **Infrastructure** is injected, never directly imported by domain
5. **Circular dependencies** are forbidden

---

## 3. Data Flow Architecture

### 3.1 Primary Data Flow

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Upload  │───▶│  Parse  │───▶│ Profile │───▶│   Map   │───▶│Standard-│
│  File   │    │         │    │         │    │         │    │  ize    │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                                  │
                                                                  ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Report  │◀───│ Review  │◀───│Diagnose │◀───│Reconcile│◀───│  Pivot  │
│         │    │         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

### 3.2 Artifact Versioning Flow

```
SourceAsset (immutable)
    │
    ├── SourceVersion v1
    │       │
    │       ├── DataProfile v1
    │       │
    │       ├── CandidateMapping v1 ──▶ ApprovedMapping v1
    │       │                                  │
    │       │                                  ▼
    │       │                          ClaimsMapping v1
    │       │
    │       └── CandidateMapping v2 ──▶ ApprovedMapping v2
    │                                          │
    │                                          ▼
    │                                  ClaimsMapping v2
    │
    └── SourceVersion v2 (re-upload)
            │
            └── ...
```

### 3.3 Reconciliation Data Flow

```
ClaimsMapping v3          Subledger v2          TreatyState v1
      │                        │                      │
      └────────────┬───────────┘                      │
                   ▼                                  │
            ┌─────────────┐                           │
            │   Pivot     │                           │
            │   Engine    │                           │
            └──────┬──────┘                           │
                   │                                  │
                   ▼                                  │
            ┌─────────────┐                           │
            │   Treaty    │◀──────────────────────────┘
            │  Evaluator  │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │ Reconcile   │
            │   Engine    │
            └──────┬──────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Variance│ │Diagnos-│ │  LLM   │
   │Records │ │tics    │ │Findings│
   └────────┘ └────────┘ └────────┘
                   │
                   ▼
            ┌─────────────┐
            │Reconciliation│
            │    Run      │
            └─────────────┘
```

---

## 4. Persistence Architecture

### 4.1 Database Schema Strategy

**Metadata in PostgreSQL:**
- Project, User, Asset metadata
- Version tracking, relationships
- Configuration, audit events
- Job states, progress

**Large Data in Object Storage:**
- Original uploaded files
- Parsed data (Parquet)
- Standardized datasets (Parquet)
- Reconciliation results (Parquet)
- Reports (various formats)

### 4.2 Storage Abstraction

```python
class StorageService(Protocol):
    async def upload(self, path: str, data: bytes) -> str: ...
    async def download(self, path: str) -> bytes: ...
    async def exists(self, path: str) -> bool: ...
    async def delete(self, path: str) -> None: ...
    async def list(self, prefix: str) -> list[str]: ...
    def get_url(self, path: str, expiry: int = 3600) -> str: ...
```

**Implementations:**
- `LocalStorageService` — File system for development
- `S3StorageService` — S3-compatible for production

### 4.3 Path Conventions

```
/{project_id}/
    /sources/
        /{asset_id}/
            /original/{filename}
            /parsed/{version_id}.parquet
    /profiles/
        /{version_id}.json
    /mappings/
        /{mapping_id}.json
    /claims-mappings/
        /{cm_id}/v{version}.parquet
    /subledgers/
        /{sl_id}/v{version}.parquet
    /reconciliations/
        /{run_id}/
            /variances.parquet
            /diagnostics.json
            /report.{format}
    /treaties/
        /{treaty_id}/
            /states/{state_id}.json
```

---

## 5. API Architecture

### 5.1 API Design Principles

1. **RESTful Resources** — Standard CRUD with meaningful resource names
2. **Versioned** — `/api/v1/` prefix for breaking change management
3. **Consistent** — Same patterns across all endpoints
4. **Paginated** — List endpoints support pagination
5. **Filterable** — Query parameters for filtering
6. **HATEOAS-lite** — Include relevant links in responses

### 5.2 Standard Response Envelope

```json
{
  "data": { },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-10-09T12:00:00Z"
  },
  "links": {
    "self": "/api/v1/projects/123",
    "related": { }
  }
}
```

### 5.3 Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [
      {
        "field": "name",
        "code": "REQUIRED",
        "message": "Name is required"
      }
    ]
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-10-09T12:00:00Z"
  }
}
```

### 5.4 Error Code Structure

```
{category}_{specific}

Categories:
- VALIDATION_*  — Input validation errors
- AUTH_*        — Authentication/authorization
- RESOURCE_*    — Resource state errors
- PROCESSING_*  — Business logic errors
- SYSTEM_*      — Infrastructure errors
```

---

## 6. Job Processing Architecture

### 6.1 Job Lifecycle

```
PENDING ──▶ QUEUED ──▶ RUNNING ──▶ SUCCEEDED
                │          │
                │          ├──▶ FAILED
                │          │
                │          └──▶ CANCELLED
                │
                └──▶ CANCELLED
```

### 6.2 Job Model

```python
class Job:
    id: UUID
    type: JobType  # PARSE, PROFILE, MAP, STANDARDIZE, RECONCILE
    project_id: UUID
    status: JobStatus
    progress: int  # 0-100
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    result_id: UUID | None  # Points to created artifact
    fingerprint: str  # For idempotency
```

### 6.3 Idempotency

Jobs use fingerprinting:

```python
fingerprint = sha256(
    job_type +
    input_artifact_ids +
    input_versions +
    configuration_hash +
    engine_version
)
```

If fingerprint exists with SUCCEEDED status, return existing result.

### 6.4 Job Notifications

- WebSocket for real-time progress
- Polling endpoint as fallback
- Optional webhook callback

---

## 7. LLM Integration Architecture

### 7.1 LLM Service Abstraction

```python
class LLMService(Protocol):
    async def complete(
        self,
        operation: LLMOperation,
        context: dict,
        schema: type[BaseModel],
        options: LLMOptions | None = None
    ) -> LLMResult: ...
```

### 7.2 LLM Operations

| Operation | Purpose | Token Budget |
|-----------|---------|--------------|
| `MAPPING_DISAMBIGUATION` | Resolve ambiguous field mappings | 2,000 input / 500 output |
| `RELATIONSHIP_INTERPRETATION` | Explain detected relationships | 2,500 input / 600 output |
| `MISMATCH_CLASSIFICATION` | Classify reconciliation exceptions | 3,000 input / 500 output |
| `CLUSTER_INTERPRETATION` | Explain mismatch patterns | 3,500 input / 800 output |
| `INVESTIGATION_PLANNING` | Plan diagnostic investigation | 4,000 input / 1,000 output |

### 7.3 LLM Guardrails

1. **Evidence Package Builder** — Minimize tokens, mask PII
2. **Schema Validation** — Pydantic model for every response
3. **Timeout** — 60 seconds default, configurable
4. **Retry** — 3 attempts with exponential backoff
5. **Cost Tracking** — Log tokens per operation
6. **Cache** — Hash-based response caching
7. **Fallback** — Graceful degradation without LLM

### 7.4 No-LLM Mode

When `llm.enabled = false`:
- Mapping uses deterministic scoring only
- Low-confidence mappings route to review
- Reconciliation uses deterministic diagnostics
- Findings marked as `UNCLASSIFIED` instead of AI-classified

---

## 8. Security Architecture

### 8.1 Authentication Flow

```
┌────────┐    ┌─────────────┐    ┌─────────────┐
│ Client │───▶│  Auth       │───▶│  API        │
│        │    │  Middleware │    │  Handler    │
└────────┘    └──────┬──────┘    └─────────────┘
                     │
              ┌──────▼──────┐
              │   Auth      │
              │  Provider   │
              │  (Abstract) │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │  Local  │  │  OIDC   │  │  SAML   │
   │  Dev    │  │         │  │         │
   └─────────┘  └─────────┘  └─────────┘
```

### 8.2 Authorization Model

**Roles:**
- `admin` — Full system access
- `project_owner` — Full project access
- `analyst` — Upload, map, reconcile, report
- `reviewer` — Review and approve
- `viewer` — Read-only access

**Permissions:**
```
project:create, project:read, project:update, project:delete
asset:upload, asset:read, asset:delete
mapping:generate, mapping:approve, mapping:reject
reconciliation:run, reconciliation:read
treaty:create, treaty:update, treaty:approve
report:generate, report:export
```

### 8.3 Data Protection

- **At Rest:** Storage encryption (cloud provider or application-level)
- **In Transit:** TLS 1.2+ required
- **PII Handling:** Redaction before LLM calls
- **Audit:** All data access logged

---

## 9. Audit Architecture

### 9.1 Audit Event Model

```python
class AuditEvent:
    id: UUID
    event_type: str  # e.g., "mapping.approved"
    actor_id: UUID
    actor_type: ActorType  # USER, SYSTEM, AI
    timestamp: datetime
    target_type: str  # e.g., "ApprovedMapping"
    target_id: UUID
    action: str  # CREATE, UPDATE, DELETE, APPROVE, REJECT
    before_state: dict | None
    after_state: dict | None
    metadata: dict
```

### 9.2 Required Audit Events

| Category | Events |
|----------|--------|
| **Project** | created, updated, archived |
| **Asset** | uploaded, deleted |
| **Mapping** | candidates_generated, approved, rejected, manual_override |
| **Reconciliation** | started, completed, failed |
| **Review** | decision_made |
| **Treaty** | state_created, state_branched, state_approved |
| **Auth** | login, logout, permission_denied |

### 9.3 Audit Storage

- Append-only table in PostgreSQL
- Retention policy configurable (default: 7 years)
- No updates or deletes allowed
- Indexed by target, actor, timestamp

---

## 10. Error Handling Architecture

### 10.1 Error Hierarchy

```
ApplicationError
├── ValidationError
│   ├── SchemaValidationError
│   ├── BusinessRuleError
│   └── ConstraintViolationError
├── AuthError
│   ├── AuthenticationError
│   └── AuthorizationError
├── ResourceError
│   ├── NotFoundError
│   ├── ConflictError
│   └── StateError
├── ProcessingError
│   ├── IngestionError
│   ├── MappingError
│   ├── ReconciliationError
│   └── LLMError
└── SystemError
    ├── StorageError
    ├── DatabaseError
    └── ExternalServiceError
```

### 10.2 Error Recovery

| Error Type | Recovery Strategy |
|------------|-------------------|
| ValidationError | Return to user, no retry |
| AuthError | Return 401/403, no retry |
| ResourceError | Return appropriate 4xx |
| ProcessingError | Retry with backoff, then fail job |
| SystemError | Retry with backoff, alert if persistent |
| LLMError | Fallback to no-LLM mode |

---

## 11. Observability Architecture

### 11.1 Logging

**Structure:**
```json
{
  "timestamp": "2026-10-09T12:00:00Z",
  "level": "INFO",
  "logger": "bordereaux.reconciliation",
  "message": "Reconciliation completed",
  "context": {
    "request_id": "req_abc123",
    "project_id": "proj_xyz",
    "run_id": "run_123",
    "duration_ms": 5432
  }
}
```

**Levels:**
- `DEBUG` — Development details
- `INFO` — Normal operations
- `WARNING` — Recoverable issues
- `ERROR` — Operation failures
- `CRITICAL` — System failures

### 11.2 Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `http_requests_total` | Counter | method, path, status |
| `http_request_duration_seconds` | Histogram | method, path |
| `job_duration_seconds` | Histogram | job_type, status |
| `job_queue_size` | Gauge | job_type |
| `llm_requests_total` | Counter | operation, provider, status |
| `llm_tokens_total` | Counter | operation, direction |
| `storage_operations_total` | Counter | operation, status |

### 11.3 Health Checks

```
GET /health
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "storage": "healthy",
    "queue": "healthy",
    "llm": "healthy"
  }
}
```

---

## 12. Deployment Architecture

### 12.1 Development Environment

```yaml
# docker-compose.yml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis, minio]
    
  worker:
    build: ./backend
    command: celery -A bordereaux.worker worker
    depends_on: [db, redis, minio]
    
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    
  db:
    image: postgres:15
    
  redis:
    image: redis:7
    
  minio:
    image: minio/minio
```

### 12.2 Production Considerations (Deferred)

- Container orchestration (Kubernetes)
- Managed database (RDS/Cloud SQL)
- Managed object storage (S3/GCS/Blob)
- Load balancing
- Auto-scaling workers
- CDN for frontend
- Secrets management
