# Implementation Plan
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09

---

## Phase Overview

| Phase | Name | Duration | Key Deliverables |
|-------|------|----------|------------------|
| 1 | Foundation | 3-4 weeks | Project structure, core models, storage, basic API |
| 2 | Ingestion & Profiling | 2-3 weeks | File adapters, structure detection, profiling |
| 3 | Mapping Engine | 3-4 weeks | Candidate generation, scoring, approval workflow |
| 4 | Standardization | 2 weeks | Transformation engine, canonical output |
| 5 | Reconciliation Core | 3-4 weeks | Subledger handling, pivot, variance engine, diagnostics |
| 6 | Treaty Management | 2-3 weeks | Discovery, state versioning, what-if |
| 7 | AI Integration | 2-3 weeks | LLM service, classification, investigation |
| 8 | Frontend Foundation | 3-4 weeks | Shell, navigation, core components |
| 9 | Feature UI | 3-4 weeks | Mapping review, reconciliation UI, reports |
| 10 | Production Hardening | 2-3 weeks | Security, monitoring, performance |

**Total estimated duration:** 25-35 weeks (6-9 months)

---

## Phase 1: Foundation (3-4 weeks)

### Objectives
- Establish project structure and conventions
- Implement core domain models
- Set up storage layer
- Create basic API infrastructure

### Deliverables

#### 1.1 Project Setup
```
backend/
├── pyproject.toml
├── alembic.ini
├── src/
│   └── bordereaux/
│       ├── __init__.py
│       ├── main.py              # FastAPI app
│       ├── config.py            # Settings
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py        # SQLAlchemy base
│       │   ├── database.py      # DB session
│       │   ├── storage.py       # S3 client
│       │   └── exceptions.py
│       ├── domain/
│       │   └── (subdomains)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py          # Dependencies
│       │   └── v1/
│       │       └── routes/
│       └── infrastructure/
│           ├── storage/
│           └── messaging/
├── tests/
├── migrations/
└── docker/
```

#### 1.2 Core Models (SQLAlchemy)
- Project
- User (stub for authentication)
- SourceAsset
- SourceVersion
- AuditEvent
- LineageRecord

#### 1.3 Storage Layer
- PostgreSQL connection with async support
- S3-compatible storage client
- File upload/download service
- Checksum calculation

#### 1.4 Base API
```
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
POST   /api/v1/projects/{id}/assets
GET    /api/v1/projects/{id}/assets
GET    /api/v1/assets/{id}
```

### Acceptance Criteria
- [ ] Project can be created via API
- [ ] File can be uploaded and stored
- [ ] File checksum is calculated and verified
- [ ] Database migrations work
- [ ] Basic health check endpoint responds

### Dependencies
- None (greenfield)

---

## Phase 2: Ingestion & Profiling (2-3 weeks)

### Objectives
- Implement file format adapters
- Build structure detection
- Implement data profiling

### Deliverables

#### 2.1 File Adapters
```python
# Protocol
class FileAdapter(Protocol):
    def supports(self, asset: SourceAsset) -> bool: ...
    def parse(self, asset: SourceAsset) -> ParseResult: ...
```

Adapters:
- CSVAdapter
- ExcelAdapter (xlsx, xls)
- JSONAdapter
- ParquetAdapter
- (Others as stretch)

#### 2.2 Format Detection
```python
class FormatDetector:
    def detect(self, file_path: str) -> FileFormat:
        # Magic bytes, MIME, probes
```

#### 2.3 Structure Detection
```python
class StructureDetector:
    def detect(self, data: DataFrame) -> StructureDetection:
        # Header row detection
        # Data region detection
        # Column type inference
```

#### 2.4 Data Profiling
```python
class DataProfiler:
    def profile(self, data: DataFrame) -> DataProfile:
        # Dataset-level stats
        # Column-level stats
        # Pattern detection
```

#### 2.5 API Extensions
```
POST   /api/v1/assets/{id}/parse
GET    /api/v1/assets/{id}/structure
POST   /api/v1/assets/{id}/profile
GET    /api/v1/versions/{id}/profile
```

### Acceptance Criteria
- [ ] CSV files parse correctly
- [ ] Excel files parse with sheet selection
- [ ] Header row detected for various layouts
- [ ] Profile statistics match manual calculation
- [ ] Profile caching works

### Dependencies
- Phase 1 complete

---

## Phase 3: Mapping Engine (3-4 weeks)

### Objectives
- Implement canonical schema management
- Build candidate mapping generation
- Implement confidence scoring
- Create approval workflow

### Deliverables

#### 3.1 Canonical Schema
```python
class CanonicalSchemaService:
    def load_schema(self, schema_id: str) -> CanonicalSchema
    def validate_schema(self, schema: CanonicalSchema) -> ValidationResult
```

Schema definition in YAML with field metadata.

#### 3.2 Mapping Candidate Generation
```python
class MappingCandidateGenerator:
    def generate(
        self,
        profile: DataProfile,
        schema: CanonicalSchema
    ) -> list[CandidateMapping]:
        # Alias matching
        # Name similarity
        # Type compatibility
        # (Optional) Semantic embedding
```

#### 3.3 Confidence Scoring
```python
class ConfidenceScorer:
    def score(
        self,
        candidate: CandidateMapping,
        profile: DataProfile,
        context: MappingContext
    ) -> ConfidenceScore:
        # Weighted formula
        # Evidence breakdown
```

#### 3.4 Relationship Inference
```python
class RelationshipInferrer:
    def infer(
        self,
        profile: DataProfile,
        mappings: list[CandidateMapping]
    ) -> list[InferredRelationship]:
        # Arithmetic detection
        # Referential detection
```

#### 3.5 Approval Workflow
- Review queue service
- Manual override API
- Bulk approval

#### 3.6 API Extensions
```
GET    /api/v1/schemas
GET    /api/v1/schemas/{id}
POST   /api/v1/versions/{id}/mappings/generate
GET    /api/v1/versions/{id}/mappings/candidates
POST   /api/v1/versions/{id}/mappings/approve
POST   /api/v1/versions/{id}/mappings/manual
GET    /api/v1/versions/{id}/relationships
```

### Acceptance Criteria
- [ ] Candidates generated for all source columns
- [ ] Confidence scores calculated correctly
- [ ] High-confidence mappings can auto-approve
- [ ] Low-confidence mappings route to review
- [ ] Manual override persists correctly
- [ ] Relationships detected for financial fields

### Dependencies
- Phase 2 complete

---

## Phase 4: Standardization (2 weeks)

### Objectives
- Implement transformation engine
- Generate canonical output
- Preserve lineage

### Deliverables

#### 4.1 Transformation Engine
```python
class TransformationEngine:
    def transform(
        self,
        data: DataFrame,
        mappings: ApprovedMapping,
        schema: CanonicalSchema
    ) -> TransformationResult:
        # Type coercion
        # Date parsing
        # Validation
```

#### 4.2 Claims Mapping Generation
```python
class ClaimsMappingService:
    def create(
        self,
        source_version: SourceVersion,
        mapping: ApprovedMapping
    ) -> ClaimsMapping:
        # Transform
        # Validate
        # Store as Parquet
        # Create lineage records
```

#### 4.3 API Extensions
```
POST   /api/v1/versions/{id}/standardize
GET    /api/v1/claims-mappings
GET    /api/v1/claims-mappings/{id}
GET    /api/v1/claims-mappings/{id}/data
GET    /api/v1/claims-mappings/{id}/lineage
```

### Acceptance Criteria
- [ ] Data transforms according to mappings
- [ ] Type coercion handles edge cases
- [ ] Invalid rows tracked separately
- [ ] Lineage records created
- [ ] Output stored as Parquet

### Dependencies
- Phase 3 complete

---

## Phase 5: Reconciliation Core (3-4 weeks)

### Objectives
- Implement subledger handling
- Build pivot/aggregation engine
- Implement variance calculation
- Create deterministic diagnostics

### Deliverables

#### 5.1 Subledger Ingestion
```python
class SubledgerService:
    def ingest(self, assets: list[SourceAsset]) -> Subledger
    def unify(self, subledgers: list[Subledger]) -> Subledger
```

#### 5.2 Pivot Engine
```python
class PivotEngine:
    def pivot(
        self,
        data: DataFrame,
        config: PivotConfig
    ) -> DataFrame:
        # Dimension grouping
        # Measure aggregation
        # Filter application
```

#### 5.3 Reconciliation Engine
```python
class ReconciliationEngine:
    def reconcile(
        self,
        reported: DataFrame,
        subledger: DataFrame,
        config: ReconciliationConfig
    ) -> ReconciliationResult:
        # Full outer join
        # Variance calculation
        # Threshold evaluation
```

#### 5.4 Variance Calculation
```python
class VarianceCalculator:
    def calculate(
        self,
        reported: Decimal,
        subledger: Decimal,
        config: VarianceConfig
    ) -> VarianceRecord:
        # Absolute variance
        # Percentage variance
        # Threshold evaluation
```

#### 5.5 Deterministic Diagnostics
```python
class DiagnosticEngine:
    def run_checks(
        self,
        result: ReconciliationResult
    ) -> list[DiagnosticFinding]:
        # 33 built-in checks
```

Check categories:
- Structural (8)
- Completeness (5)
- Integrity (10)
- Value (6)
- Distribution (4)

#### 5.6 API Extensions
```
POST   /api/v1/projects/{id}/subledgers
POST   /api/v1/subledgers/unify
POST   /api/v1/pivots
POST   /api/v1/reconciliations
GET    /api/v1/reconciliations/{id}
GET    /api/v1/reconciliations/{id}/variances
GET    /api/v1/reconciliations/{id}/diagnostics
POST   /api/v1/reconciliations/{id}/diagnostics/run
```

### Acceptance Criteria
- [ ] Multiple subledgers unify correctly
- [ ] Pivot produces correct aggregates
- [ ] Variance calculation handles edge cases
- [ ] All 33 diagnostic checks implemented
- [ ] One-to-many aggregation works
- [ ] Key quality validated

### Dependencies
- Phase 4 complete

---

## Phase 6: Treaty Management (2-3 weeks)

### Objectives
- Implement treaty discovery
- Build state versioning
- Enable what-if scenarios

### Deliverables

#### 6.1 Treaty Models
- Treaty
- TreatyState
- TreatyClause
- ChangeSet

#### 6.2 Treaty Discovery
```python
class TreatyDiscoveryService:
    def discover(
        self,
        sources: list[SourceAsset]
    ) -> TreatyManifest:
        # Treaty identification
        # Clause detection
        # Parameter extraction
```

#### 6.3 State Management
```python
class TreatyStateService:
    def create_state(
        self,
        base_state: TreatyState,
        change_set: ChangeSet
    ) -> TreatyState:
        # Validate patch
        # Apply changes
        # Create immutable state
    
    def rollback(self, target_state_id: UUID) -> TreatyState
    def branch(self, base_state_id: UUID) -> TreatyState
```

#### 6.4 Treaty Evaluation
```python
class TreatyEvaluator:
    def evaluate(
        self,
        data: DataFrame,
        state: TreatyState
    ) -> DataFrame:
        # Apply treaty rules
        # Clause evaluation
```

#### 6.5 API Extensions
```
GET    /api/v1/treaties
POST   /api/v1/treaties/{id}/discover
GET    /api/v1/treaties/{id}/manifest
GET    /api/v1/treaties/{id}/states
POST   /api/v1/treaties/{id}/patches
GET    /api/v1/treaties/{id}/states/{state_id}
POST   /api/v1/treaties/{id}/states/{state_id}/rollback
GET    /api/v1/reconciliations/compare
```

### Acceptance Criteria
- [ ] Treaty clauses discoverable from data
- [ ] State versioning creates immutable snapshots
- [ ] Rollback creates new state (doesn't delete)
- [ ] What-if comparison shows impact
- [ ] Patches validate before application

### Dependencies
- Phase 5 complete

---

## Phase 7: AI Integration (2-3 weeks)

### Objectives
- Implement LLM service abstraction
- Build mismatch classification
- Create investigation interface

### Deliverables

#### 7.1 LLM Service
```python
class LLMService:
    def classify_mismatch(
        self,
        evidence: MismatchEvidence
    ) -> LLMFinding
    
    def interpret_cluster(
        self,
        cluster: MismatchCluster
    ) -> ClusterInterpretation
    
    def plan_investigation(
        self,
        question: str,
        context: InvestigationContext
    ) -> InvestigationPlan
```

#### 7.2 Evidence Package Builder
```python
class EvidencePackageBuilder:
    def build(
        self,
        result: ReconciliationResult,
        scope: list[UUID]
    ) -> dict:
        # Summarize evidence
        # Minimize tokens
        # Mask identifiers
```

#### 7.3 Response Validation
```python
class LLMResponseValidator:
    def validate(
        self,
        response: dict,
        schema: type[BaseModel]
    ) -> ValidationResult
```

#### 7.4 Caching
- Cache key generation
- Response caching
- Invalidation rules

#### 7.5 API Extensions
```
POST   /api/v1/reconciliations/{id}/llm/classify
POST   /api/v1/reconciliations/{id}/investigate
GET    /api/v1/reconciliations/{id}/llm-findings
```

### Acceptance Criteria
- [ ] LLM produces valid JSON
- [ ] Evidence packages minimize tokens
- [ ] Caching reduces duplicate calls
- [ ] No-LLM mode works
- [ ] PII redaction applied

### Dependencies
- Phase 5 complete (can parallel with Phase 6)

---

## Phase 8: Frontend Foundation (3-4 weeks)

### Objectives
- Establish frontend architecture
- Build shell and navigation
- Create core components

### Deliverables

#### 8.1 Project Setup
```
frontend/
├── package.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router/
│   ├── store/
│   ├── api/
│   ├── components/
│   │   ├── shell/
│   │   ├── navigation/
│   │   ├── data/
│   │   └── common/
│   ├── features/
│   │   ├── projects/
│   │   ├── assets/
│   │   ├── mapping/
│   │   └── reconciliation/
│   └── styles/
```

#### 8.2 Shell Components
- AppHeader
- Sidebar
- Breadcrumbs
- WorkspaceSwitcher
- GlobalSearch (basic)

#### 8.3 Core Components
- DataTable
- ResourceCard
- ResourceList
- StatusBadge
- ConfidenceIndicator
- EmptyState
- LoadingState
- ErrorState

#### 8.4 Project Pages
- Project list
- Project detail
- Asset upload

### Acceptance Criteria
- [ ] Shell renders correctly
- [ ] Navigation works
- [ ] Projects can be created/viewed
- [ ] Assets can be uploaded
- [ ] Responsive layout works

### Dependencies
- Phase 1 API complete

---

## Phase 9: Feature UI (3-4 weeks)

### Objectives
- Build mapping review interface
- Create reconciliation dashboard
- Implement report views

### Deliverables

#### 9.1 Mapping Review
- Candidate list with evidence
- Side-by-side comparison
- Bulk approval controls
- Confidence breakdown
- Relationship visualization

#### 9.2 Reconciliation Dashboard
- Summary metrics
- Variance chart
- Exception table
- Drill-down navigation
- Status workflow

#### 9.3 Diagnostics View
- Finding list by category
- Evidence detail
- Mismatch clustering
- AI insights panel

#### 9.4 Report Views
- Executive summary
- Exception detail
- Lineage explorer
- Export controls

#### 9.5 Treaty Management UI
- Treaty list
- State comparison
- Patch builder
- Impact analysis

### Acceptance Criteria
- [ ] Mapping review workflow complete
- [ ] Reconciliation results viewable
- [ ] Diagnostics filterable/sortable
- [ ] Reports exportable
- [ ] Treaty scenarios comparable

### Dependencies
- Phases 1-7 complete
- Phase 8 complete

---

## Phase 10: Production Hardening (2-3 weeks)

### Objectives
- Implement security controls
- Add monitoring/observability
- Performance optimization
- Documentation

### Deliverables

#### 10.1 Security
- Authentication integration
- Role-based access control
- API rate limiting
- Input validation hardening
- Secret management

#### 10.2 Observability
- Structured logging
- Metrics collection
- Distributed tracing
- Health check endpoints
- Error alerting

#### 10.3 Performance
- Database query optimization
- Caching layer
- Async task queuing
- Large file handling
- Memory optimization

#### 10.4 Documentation
- API documentation (OpenAPI)
- User guide
- Deployment guide
- Operations runbook

### Acceptance Criteria
- [ ] Authentication required on all endpoints
- [ ] RBAC enforced
- [ ] Logs structured and searchable
- [ ] Metrics dashboard available
- [ ] Performance targets met
- [ ] Documentation complete

### Dependencies
- All previous phases complete

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM API instability | No-LLM mode ensures core functionality works without AI |
| Large file performance | Async processing, chunking, Parquet optimization |
| Schema evolution | Versioned schemas with migration support |
| Scope creep | Phased delivery with clear acceptance criteria |
| Integration complexity | Contract-first API design, comprehensive tests |

---

## Quality Gates Per Phase

Each phase must pass before proceeding:

1. **Unit tests:** ≥80% coverage on new code
2. **Integration tests:** Critical paths covered
3. **API documentation:** OpenAPI spec updated
4. **Code review:** All PRs reviewed
5. **Acceptance criteria:** All items checked

---

## Parallel Work Opportunities

```
Phase 1 ──────────▶ Phase 2 ──────────▶ Phase 3 ──────────▶ Phase 4
                                                              │
                                                              ▼
                                              Phase 5 ◀──────────
                                                │
                                    ┌───────────┼───────────┐
                                    ▼                       ▼
                                 Phase 6                 Phase 7
                                    │                       │
                                    └───────────┬───────────┘
                                                ▼
Phase 8 ──────────────────────────────────▶ Phase 9
    │                                           │
    └───────────────────┬───────────────────────┘
                        ▼
                    Phase 10
```

- **Phase 6 and 7** can run in parallel after Phase 5
- **Phase 8** can start after Phase 1, running alongside backend phases
- **Phase 9** requires both backend features (1-7) and frontend foundation (8)
