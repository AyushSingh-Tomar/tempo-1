# Agent Architecture
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Purpose:** Define the multi-agent development architecture for implementing the platform

---

## 1. Overview

This document defines how Claude Code agents will be orchestrated to implement the Bordereaux Intelligence Platform. The architecture follows a **coordinator pattern** with specialized agents for different domains.

### 1.1 Design Principles

1. **Single source of truth** — All specifications live in `docs/project-context/`
2. **Clear boundaries** — Each agent owns specific modules
3. **Contract-first** — Agents implement against defined interfaces
4. **Incremental delivery** — Each agent produces testable artifacts
5. **Context efficiency** — Agents receive only relevant specifications

---

## 2. Agent Team Structure

```
                    ┌─────────────────┐
                    │   Coordinator   │
                    │     Agent       │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   Foundation  │   │   Pipeline    │   │   Frontend    │
│     Agent     │   │    Agent      │   │     Agent     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Core Models  │   │   Ingestion   │   │   React UI    │
│  Storage      │   │   Profiling   │   │   Components  │
│  Auth         │   │   Mapping     │   │   API Client  │
│  Jobs         │   │   Reconcile   │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 2.1 Coordinator Agent

**Role:** Orchestrates other agents, maintains project state, handles cross-cutting concerns.

**Responsibilities:**
- Task assignment and tracking
- Cross-agent coordination
- Integration testing
- Release management
- Conflict resolution

**Context:**
- All specification documents
- Implementation status
- Test results

### 2.2 Foundation Agent

**Role:** Implements core infrastructure and shared services.

**Modules Owned:**
- `src/core/` — Shared kernel (models, exceptions, utils)
- `src/storage/` — File storage abstraction
- `src/auth/` — Authentication providers
- `src/jobs/` — Job queue and workers
- `src/audit/` — Audit logging

**Key Deliverables:**
1. Base SQLAlchemy models
2. Storage service (local + S3)
3. Auth provider abstraction
4. Job processing framework
5. Audit event system

**Required Context:**
- DATA_MODEL.md
- MODULE_CONTRACTS.md (StorageService, AuditService, AuthProvider)
- SECURITY_AND_AUDIT.md
- ADR-006 (Async Job Processing)

### 2.3 Pipeline Agent

**Role:** Implements the data processing pipeline from ingestion to reconciliation.

**Modules Owned:**
- `src/ingestion/` — File upload, parsing, structure detection
- `src/profiling/` — Data profiling and statistics
- `src/mapping/` — Candidate generation, confidence scoring, schema templates
- `src/standardization/` — Schema transformation
- `src/reconciliation/` — Pivot, variance, diagnostics

**Key Deliverables:**
1. File format adapters (CSV, XLSX, JSON, Parquet)
2. Structure detection algorithm
3. Data profiler
4. Mapping candidate generator
5. Confidence scoring engine
6. Schema template service (create, match, apply)
7. Transformation engine
8. Reconciliation engine
9. Diagnostic checks (D001-D025)

**Required Context:**
- MODULE_CONTRACTS.md (all pipeline interfaces)
- MVP_SCOPE.md (file formats, diagnostic checks)
- ADR-002 (Deterministic First)
- ADR-004 (Confidence Scoring)
- REQUIREMENTS.md (FR-ING-*, FR-PRO-*, FR-MAP-*, FR-REC-*)

### 2.4 Frontend Agent

**Role:** Implements the React/TypeScript user interface.

**Modules Owned:**
- `frontend/src/components/` — UI components
- `frontend/src/pages/` — Page layouts
- `frontend/src/api/` — API client
- `frontend/src/hooks/` — Custom hooks
- `frontend/src/stores/` — State management

**Key Deliverables:**
1. Project list/detail pages
2. File upload component
3. Mapping review interface
4. Reconciliation results view
5. Variance detail modal
6. Report view/download

**Required Context:**
- API_SPECIFICATION.md
- MVP_SCOPE.md (UI screens)
- MVP_ACCEPTANCE_CRITERIA.md (UI acceptance tests)

---

## 3. Agent Context Configuration

### 3.1 Context Files per Agent

```yaml
coordinator:
  always_include:
    - docs/project-context/PROJECT_BRIEF.md
    - docs/project-context/IMPLEMENTATION_PLAN.md
    - docs/project-context/MVP_SCOPE.md
    - docs/project-context/CONSISTENCY_REVIEW.md
  on_demand:
    - docs/project-context/*

foundation:
  always_include:
    - docs/project-context/DATA_MODEL.md
    - docs/project-context/SECURITY_AND_AUDIT.md
    - docs/project-context/ADR/ADR-006-async-job-processing.md
  on_demand:
    - docs/project-context/MODULE_CONTRACTS.md
    - docs/project-context/ARCHITECTURE.md

pipeline:
  always_include:
    - docs/project-context/MODULE_CONTRACTS.md
    - docs/project-context/MVP_SCOPE.md
    - docs/project-context/ADR/ADR-002-deterministic-first.md
    - docs/project-context/ADR/ADR-004-confidence-scoring.md
  on_demand:
    - docs/project-context/REQUIREMENTS.md
    - docs/project-context/DOMAIN_MODEL.md

frontend:
  always_include:
    - docs/project-context/API_SPECIFICATION.md
    - docs/project-context/MVP_SCOPE.md
  on_demand:
    - docs/project-context/MVP_ACCEPTANCE_CRITERIA.md
```

### 3.2 Context Sharing Rules

1. **No full specification dump** — Agents receive targeted context
2. **On-demand loading** — Request additional docs when needed
3. **Interface-driven** — Agents share contracts, not implementations
4. **Test-driven integration** — Coordinator validates agent outputs

---

## 4. Development Phases

### 4.1 Phase 1: Foundation (Weeks 1-3)

**Owner:** Foundation Agent

**Tasks:**
1. Project scaffolding (FastAPI, SQLAlchemy, Alembic)
2. Database models and migrations
3. Storage service implementation
4. Auth provider (dev mode)
5. Job queue framework
6. Audit event system
7. Base API structure

**Outputs:**
- `src/core/` complete
- `src/storage/` complete
- `src/auth/` complete
- `src/jobs/` complete
- `src/audit/` complete
- Database migrations 001-012
- Health endpoint working

**Success Criteria:**
```bash
# All pass:
pytest tests/unit/core/
pytest tests/unit/storage/
pytest tests/unit/jobs/
alembic upgrade head  # No errors
curl localhost:8000/health  # 200 OK
```

### 4.2 Phase 2: Ingestion & Profiling (Weeks 4-5)

**Owner:** Pipeline Agent

**Dependencies:** Phase 1 complete

**Tasks:**
1. File upload endpoint
2. Format detection
3. CSV/XLSX/JSON/Parquet adapters
4. Structure detection
5. Data profiler
6. Profile storage

**Outputs:**
- `src/ingestion/` complete
- `src/profiling/` complete
- File adapters for MVP formats
- Profile API endpoints

**Success Criteria:**
```bash
# Golden dataset uploads:
pytest tests/integration/test_ingestion.py
# Profile generation:
pytest tests/integration/test_profiling.py
# AC-ING-01 through AC-PRO-03 pass
```

### 4.3 Phase 3: Mapping (Weeks 6-7)

**Owner:** Pipeline Agent

**Dependencies:** Phase 2 complete

**Tasks:**
1. Canonical schema loader
2. Candidate generator
3. Confidence scoring engine
4. Mapping approval workflow
5. Manual mapping support
6. Mapping finalization

**Outputs:**
- `src/mapping/` complete
- Confidence scoring per ADR-004
- Mapping API endpoints

**Success Criteria:**
```bash
pytest tests/unit/mapping/
pytest tests/integration/test_mapping.py
# Golden dataset mappings match expected confidence
# AC-MAP-01 through AC-MAP-07 pass
```

### 4.4 Phase 4: Standardization (Weeks 8-9)

**Owner:** Pipeline Agent

**Dependencies:** Phase 3 complete

**Tasks:**
1. Transformation engine
2. Type coercion
3. Date parsing
4. ClaimsMapping output
5. Subledger processing
6. Lineage tracking

**Outputs:**
- `src/standardization/` complete
- Lineage records
- Standardization API endpoints

**Success Criteria:**
```bash
pytest tests/integration/test_standardization.py
# AC-STD-01 through AC-STD-04 pass
# Lineage traceable end-to-end
```

### 4.5 Phase 5: Reconciliation (Weeks 10-12)

**Owner:** Pipeline Agent

**Dependencies:** Phase 4 complete

**Tasks:**
1. Pivot generation
2. Variance calculator
3. Threshold evaluation
4. Diagnostic checks (20 MVP)
5. Finding classification
6. Report generation

**Outputs:**
- `src/reconciliation/` complete
- All 20 MVP diagnostic checks
- Reconciliation API endpoints

**Success Criteria:**
```bash
pytest tests/integration/test_reconciliation.py
pytest tests/golden/test_golden_dataset.py
# AC-REC-01 through AC-REC-09 pass
# AC-DIA-01 through AC-DIA-04 pass
# Golden dataset: 890 matched, 35 tolerance, 65 unreconciled
```

### 4.6 Phase 6: Frontend (Weeks 13-15)

**Owner:** Frontend Agent

**Dependencies:** Phases 1-5 API complete

**Tasks:**
1. Project setup (React, TypeScript, Vite)
2. API client generation
3. Project management pages
4. File upload UI
5. Mapping review interface
6. Reconciliation results
7. Report view

**Outputs:**
- `frontend/` complete
- All MVP screens
- E2E test coverage

**Success Criteria:**
```bash
npm run test
npm run e2e
# All UI acceptance criteria pass
# Manual testing of golden dataset flow
```

### 4.7 Phase 7: Integration (Weeks 16-17)

**Owner:** Coordinator Agent

**Dependencies:** All phases complete

**Tasks:**
1. End-to-end testing
2. Golden dataset validation
3. Performance testing
4. Bug fixes
5. Documentation

**Outputs:**
- All acceptance criteria pass
- Golden dataset 100% validated
- Performance within targets

### 4.8 Phase 8: Polish (Week 18)

**Owner:** Coordinator Agent

**Tasks:**
1. Final bug fixes
2. Documentation review
3. Deployment preparation

---

## 5. Inter-Agent Contracts

### 5.1 Foundation → Pipeline

```python
# Pipeline Agent depends on these from Foundation:

class StorageService(Protocol):
    async def upload(self, path: str, data: bytes) -> StorageResult: ...
    async def download(self, path: str) -> bytes: ...

class JobService(Protocol):
    async def create(self, type: JobType, input: dict) -> Job: ...
    async def update_progress(self, job_id: UUID, progress: JobProgress): ...

class AuditService(Protocol):
    async def log(self, event: AuditEvent): ...
```

### 5.2 Pipeline → Frontend

```python
# Frontend depends on Pipeline API endpoints:

# Documented in API_SPECIFICATION.md
# OpenAPI schema at /openapi.json
```

### 5.3 Shared Types

All agents use types from `src/core/models.py`:

```python
# Core types shared across all agents
from core.models import (
    UUID,
    DataType,
    JobStatus,
    VarianceStatus,
    DiagnosticCategory,
    # ... etc
)
```

---

## 6. Agent Communication Protocol

### 6.1 Task Handoff

```yaml
# Coordinator assigns task to agent:
task:
  id: "TASK-042"
  type: "implement"
  owner: "pipeline-agent"
  module: "src/reconciliation/variance_calculator.py"
  context:
    - docs/project-context/MODULE_CONTRACTS.md#VarianceCalculator
    - docs/project-context/ADR/ADR-002-deterministic-first.md
  acceptance:
    - "pytest tests/unit/reconciliation/test_variance.py passes"
    - "Matches golden dataset expected variances"
```

### 6.2 Completion Report

```yaml
# Agent reports completion:
completion:
  task_id: "TASK-042"
  status: "completed"
  artifacts:
    - src/reconciliation/variance_calculator.py
    - tests/unit/reconciliation/test_variance.py
  test_results:
    passed: 24
    failed: 0
  notes: "Implemented variance calculation per ADR-002"
```

### 6.3 Blocking Issues

```yaml
# Agent reports blocker:
blocker:
  task_id: "TASK-042"
  issue: "StorageService.download() signature changed"
  blocked_by: "foundation-agent"
  required_action: "Update interface or implementation"
```

---

## 7. Quality Gates

### 7.1 Per-Module Gates

Before marking a module complete:

1. ✅ Unit test coverage ≥ 90%
2. ✅ Integration tests pass
3. ✅ Type hints on all public functions
4. ✅ No linting errors
5. ✅ Contract compliance verified

### 7.2 Per-Phase Gates

Before starting next phase:

1. ✅ All modules in phase complete
2. ✅ Phase acceptance criteria pass
3. ✅ No blocking issues
4. ✅ Documentation updated
5. ✅ Coordinator review passed

### 7.3 Release Gate

Before MVP release:

1. ✅ All acceptance criteria (MVP_ACCEPTANCE_CRITERIA.md)
2. ✅ Golden dataset 100% validated
3. ✅ Performance targets met
4. ✅ Security review passed
5. ✅ No critical bugs

---

## 8. File Structure

### 8.1 Backend

```
src/
├── __init__.py
├── main.py                    # FastAPI app
├── config.py                  # Settings
│
├── core/                      # Foundation Agent
│   ├── __init__.py
│   ├── models.py              # Shared types/enums
│   ├── exceptions.py          # Custom exceptions
│   ├── utils.py               # Utilities
│   └── database.py            # DB session
│
├── storage/                   # Foundation Agent
│   ├── __init__.py
│   ├── service.py
│   ├── local.py
│   └── s3.py
│
├── auth/                      # Foundation Agent
│   ├── __init__.py
│   ├── service.py
│   ├── dev_provider.py
│   └── middleware.py
│
├── jobs/                      # Foundation Agent
│   ├── __init__.py
│   ├── service.py
│   ├── worker.py
│   └── handlers/
│
├── audit/                     # Foundation Agent
│   ├── __init__.py
│   └── service.py
│
├── ingestion/                 # Pipeline Agent
│   ├── __init__.py
│   ├── service.py
│   ├── adapters/
│   │   ├── csv.py
│   │   ├── excel.py
│   │   ├── json.py
│   │   └── parquet.py
│   └── structure_detector.py
│
├── profiling/                 # Pipeline Agent
│   ├── __init__.py
│   ├── service.py
│   └── profiler.py
│
├── mapping/                   # Pipeline Agent
│   ├── __init__.py
│   ├── service.py
│   ├── candidate_generator.py
│   ├── confidence_scorer.py
│   └── schemas/
│
├── standardization/           # Pipeline Agent
│   ├── __init__.py
│   ├── service.py
│   └── transformer.py
│
├── reconciliation/            # Pipeline Agent
│   ├── __init__.py
│   ├── service.py
│   ├── pivot.py
│   ├── variance_calculator.py
│   ├── diagnostics/
│   │   ├── engine.py
│   │   └── checks/
│   └── report.py
│
├── api/                       # Shared
│   ├── __init__.py
│   ├── deps.py                # Dependencies
│   ├── middleware.py
│   └── v1/
│       ├── __init__.py
│       ├── projects.py
│       ├── assets.py
│       ├── versions.py
│       ├── mappings.py
│       ├── reconciliations.py
│       ├── jobs.py
│       └── schemas.py
│
└── models/                    # SQLAlchemy models
    ├── __init__.py
    ├── base.py
    ├── project.py
    ├── asset.py
    ├── version.py
    ├── profile.py
    ├── mapping.py
    ├── claims_mapping.py
    ├── subledger.py
    ├── reconciliation.py
    └── audit.py
```

### 8.2 Frontend

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
│
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   │
│   ├── api/                   # Generated from OpenAPI
│   │   └── client.ts
│   │
│   ├── components/
│   │   ├── common/
│   │   ├── projects/
│   │   ├── assets/
│   │   ├── mappings/
│   │   └── reconciliation/
│   │
│   ├── pages/
│   │   ├── ProjectList.tsx
│   │   ├── ProjectDetail.tsx
│   │   ├── MappingReview.tsx
│   │   └── ReconciliationResults.tsx
│   │
│   ├── hooks/
│   ├── stores/
│   └── utils/
│
└── tests/
    ├── unit/
    └── e2e/
```

---

## 9. Agent Prompts

### 9.1 Foundation Agent Prompt Template

```
You are the Foundation Agent for the Bordereaux Intelligence Platform.

Your responsibility is implementing the core infrastructure:
- Database models and migrations
- Storage service (local and S3)
- Authentication provider abstraction
- Async job processing framework
- Audit event logging

Current task: {task_description}

Required context files:
- DATA_MODEL.md
- MODULE_CONTRACTS.md (relevant sections)
- SECURITY_AND_AUDIT.md
- ADR-006-async-job-processing.md

Implementation guidelines:
1. Follow the interfaces in MODULE_CONTRACTS.md exactly
2. Use Python 3.11+ features and type hints
3. Write unit tests alongside implementation
4. Use SQLAlchemy 2.0 async patterns
5. Log all state changes via AuditService

Acceptance criteria for this task:
{acceptance_criteria}
```

### 9.2 Pipeline Agent Prompt Template

```
You are the Pipeline Agent for the Bordereaux Intelligence Platform.

Your responsibility is implementing the data processing pipeline:
- File ingestion and parsing
- Data profiling and statistics
- Schema mapping with confidence scoring
- Data standardization
- Reconciliation and diagnostics

Current task: {task_description}

Required context files:
- MODULE_CONTRACTS.md (relevant sections)
- MVP_SCOPE.md
- ADR-002-deterministic-first.md
- ADR-004-confidence-scoring.md

Implementation guidelines:
1. Follow "deterministic first, AI second" principle
2. All calculations must be reproducible
3. Preserve full lineage for every derived value
4. Match the confidence scoring weights exactly
5. Handle edge cases (nulls, zeros, missing data)

Acceptance criteria for this task:
{acceptance_criteria}
```

### 9.3 Frontend Agent Prompt Template

```
You are the Frontend Agent for the Bordereaux Intelligence Platform.

Your responsibility is implementing the React/TypeScript UI:
- Project management screens
- File upload interface
- Mapping review workflow
- Reconciliation results display

Current task: {task_description}

Required context files:
- API_SPECIFICATION.md
- MVP_SCOPE.md (UI screens section)
- MVP_ACCEPTANCE_CRITERIA.md

Implementation guidelines:
1. Use React 18+ with TypeScript
2. Generate API client from OpenAPI spec
3. Implement responsive design (desktop-first)
4. Handle loading, error, and empty states
5. Follow accessibility best practices

Acceptance criteria for this task:
{acceptance_criteria}
```

---

## 10. Risk Mitigation

### 10.1 Context Overflow

**Risk:** Agents receiving too much context.

**Mitigation:**
- Targeted context per task
- On-demand document loading
- Summaries for large specifications

### 10.2 Interface Drift

**Risk:** Agents implement incompatible interfaces.

**Mitigation:**
- Contract tests at boundaries
- Coordinator validates integrations
- Shared type definitions

### 10.3 Parallel Conflicts

**Risk:** Agents modify same files.

**Mitigation:**
- Clear module ownership
- File-level task assignment
- Integration branch reviews

### 10.4 Specification Ambiguity

**Risk:** Agents interpret specs differently.

**Mitigation:**
- ADRs document decisions
- Acceptance criteria are specific
- Coordinator resolves conflicts
