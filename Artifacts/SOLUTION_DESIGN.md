# Bordereaux Intelligence Platform — Solution Design

This document is the implementation-oriented companion to `README.md`. It focuses on the architecture, modules, data model, processing flow, APIs, service functions, AI orchestration, UI structure, versioning, lineage, reconciliation, treaty intelligence, observability, and guardrails needed to build the product.

# 35. Suggested Backend Architecture

For the first implementation, use a **modular monolith + asynchronous worker** rather than prematurely splitting into many services.

```text
Frontend
   ↓
API Layer
   ↓
Application / Workflow Layer
   ├── Intake Module
   ├── Mapping Module
   ├── Standardization Module
   ├── Pivot Module
   ├── Reconciliation Module
   ├── Treaty Module
   ├── Compliance Module
   ├── Reporting Module
   ├── Lineage Module
   ├── Versioning Module
   ├── Review Module
   ├── Integration Module
   └── Observability Module
   ↓
Data / Storage Layer
   ├── Relational DB
   ├── Object Storage
   ├── Search Index
   └── Optional Vector Store
```

A background worker should process expensive operations:

- file profiling
- parsing
- LLM mapping
- PDF extraction
- large transformations
- pivot generation
- reconciliation
- report generation

---

# 36. Recommended Technical Stack

The exact stack can change, but a practical implementation is:

### Frontend

- React
- TypeScript
- Next.js or Vite
- component/design system
- data grid
- workflow graph/canvas
- charting library

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- async job worker

### Data

- PostgreSQL for application metadata/state
- S3/Azure Blob-compatible object storage for source/output artifacts
- Parquet for large standardized datasets
- search index for enterprise discovery
- optional vector database for semantic retrieval

### AI

- pluggable LLM provider
- embeddings for semantic retrieval
- deterministic Python rules for numeric validation
- structured JSON output

### Observability

- application logs
- traces
- metrics
- run telemetry
- audit events

The application should isolate provider-specific AI code behind an interface so models can be changed without rewriting the mapping engine.

---

# 37. AI Orchestration

Use AI for reasoning, but keep deterministic business logic outside the LLM.

```text
                Mapping Request
                      │
                      ▼
            Candidate Generator
                      │
                      ▼
            Evidence Collector
              ┌───────┼────────┐
              ▼       ▼        ▼
          Metadata   Values   Rules
              └───────┼────────┘
                      ▼
             Candidate Scorer
                      │
             ┌────────┴────────┐
             ▼                 ▼
       Deterministic       AI Reasoner
         Validation            │
             └────────┬────────┘
                      ▼
              Confidence Calibrator
                      │
             ┌────────┴────────┐
             ▼                 ▼
       Auto Process       Review Queue
```

The LLM should produce structured evidence and rationale, not directly mutate the database.

---

# 38. Mapping Prompt Contract

The mapping model should receive only the relevant context.

Example input:

```json
{
  "source_column": "Amount",
  "header_path": ["Premium Details", "Amount"],
  "data_profile": {
    "type": "decimal",
    "sample_values": [1200.5, 5000, 830.25],
    "min": 50,
    "max": 250000,
    "null_rate": 0.01
  },
  "related_columns": [
    "Premium Amt",
    "Net",
    "Commission %"
  ],
  "candidate_fields": [
    "Gross Premium",
    "Commission",
    "Net Premium",
    "Tax"
  ]
}
```

Expected structured output:

```json
{
  "selected_field": "Commission",
  "alternatives": [
    {
      "field": "Net Premium",
      "confidence": 0.31
    }
  ],
  "confidence": 0.76,
  "evidence": [
    "..."
  ],
  "needs_human_review": true
}
```

The backend validates this result against a strict schema before persistence.

---

# 39. Resource / Object Page Pattern

Every major resource should use:

```text
OBJECT HEADER
├── Name
├── Type
├── Status
├── Owner
├── Version
├── Primary Action
└── More

TABS
├── Overview
├── Data / Content
├── Activity
├── Relationships / Lineage
├── Quality
├── Review
├── Permissions
└── Settings
```

Not every resource needs every tab.

---

# 40. Mapping Studio UX

The Mapping Studio is a critical interface.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Mapping Run: Bordereaux_2026          Status: Review Required       │
│ [Run] [Approve All Safe] [Export Mapping] [More]                    │
├───────────────┬───────────────────────────────────┬─────────────────┤
│ Source Fields │ Proposed Mapping                  │ Inspector       │
│               │                                   │                 │
│ Policy Ref    │ Reference          98%  ✓        │ Evidence        │
│ Effective Dt  │ Date               96%  ✓        │ Samples         │
│ Premium Amt   │ Gross Premium      91%  ✓        │ Relationships   │
│ Amount        │ Commission         58%  !        │ Alternatives    │
│ Net           │ Net Premium        93%  ✓        │ Explanation     │
│               │                                   │ Review actions  │
└───────────────┴───────────────────────────────────┴─────────────────┘
```

Use a right-side inspector instead of navigating away from the mapping table.

---

# 41. Reconciliation UX

The reconciliation workspace should provide both a summary and drill-down.

```text
RECONCILIATION
├── Overview
│   ├── Total source
│   ├── Total subledger
│   ├── Variance
│   └── Match rate
├── Exceptions
├── Matching Rules
├── Aggregations
├── Evidence
├── Lineage
└── History
```

Clicking a variance should open:

```text
Summary
  ↓
Matched / Unmatched records
  ↓
Field differences
  ↓
Transformation history
  ↓
Source evidence
```

---

# 42. Treaty UX

```text
TREATY
├── Overview
├── Documents
├── Clauses
├── Financial Terms
├── Regulatory Controls
├── Related Bordereaux
├── Reconciliation
├── Change History
├── Lineage
└── Permissions
```

For clause inspection:

```text
Clause list
      ↓
Selected clause
      ↓
Right inspector:
  - Original text
  - Simplified meaning
  - Extracted terms
  - Regulatory links
  - Evidence
  - Review status
```

---

# 43. Workflow Model

Complex workflows should be graph-based where dependencies matter.

Example:

```text
Upload
  ↓
Detect Structure
  ↓
Profile
  ↓
Generate Mapping
  ↓
Confidence Gate
 ├── High → Standardize
 └── Review → Human Approval
                   ↓
               Standardize
                   ↓
             Build Claims Mapping
                   ↓
               Build Pivot
                   ↓
              Reconciliation
                   ↓
                Report
```

Separate three modes:

```text
BUILD
  define steps/rules

RUN
  execute workflow

OBSERVE
  inspect history/logs/metrics/errors
```

---

# 44. API Surface

The following is a suggested REST surface. Exact naming can be adjusted, but these capabilities should exist.

## Projects

```http
POST   /api/projects
GET    /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
```

## Intake

```http
POST   /api/ingestions
GET    /api/ingestions/{ingestion_id}
GET    /api/ingestions/{ingestion_id}/preview
GET    /api/ingestions/{ingestion_id}/structure
POST   /api/ingestions/{ingestion_id}/confirm-structure
```

## Mapping

```http
POST   /api/mapping-runs
GET    /api/mapping-runs/{run_id}
GET    /api/mapping-runs/{run_id}/proposals
POST   /api/mapping-runs/{run_id}/review
POST   /api/mapping-runs/{run_id}/approve
POST   /api/mapping-runs/{run_id}/standardize
```

## Mapping profiles

```http
POST   /api/mapping-profiles
GET    /api/mapping-profiles
POST   /api/mapping-profiles/{id}/apply
POST   /api/mapping-profiles/{id}/publish
POST   /api/mapping-profiles/{id}/rollback
```

## Pivot

```http
POST   /api/pivots
POST   /api/pivots/{id}/run
GET    /api/pivots/{id}/results
```

## Reconciliation

```http
POST   /api/reconciliations
GET    /api/reconciliations/{id}
GET    /api/reconciliations/{id}/exceptions
POST   /api/reconciliations/{id}/exceptions/{exception_id}/resolve
POST   /api/reconciliations/{id}/approve
```

## Treaties

```http
POST   /api/treaties
GET    /api/treaties/{id}
POST   /api/treaties/{id}/documents
POST   /api/treaties/{id}/simplify
GET    /api/treaties/{id}/clauses
POST   /api/treaties/{id}/clauses/{clause_id}/review
GET    /api/treaties/{id}/history
POST   /api/treaties/{id}/restore
```

## Compliance

```http
POST   /api/compliance/controls
POST   /api/compliance/links
POST   /api/compliance/assessments
GET    /api/compliance/matrix
```

## Reports

```http
POST   /api/reports
POST   /api/reports/{id}/generate
GET    /api/reports/{id}
GET    /api/reports/{id}/download
```

## Search

```http
GET /api/search?q=...
```

## Lineage

```http
GET /api/lineage/{asset_id}
GET /api/lineage/{asset_id}/upstream
GET /api/lineage/{asset_id}/downstream
```

## Versioning

```http
GET  /api/{resource}/{id}/versions
GET  /api/{resource}/{id}/versions/{version}
POST /api/{resource}/{id}/restore
```

---

# 45. Service Functions

A coding agent should organize the backend around domain services rather than one giant controller.

```text
IngestionService
├── ingest_file()
├── inspect_file()
├── detect_structure()
└── confirm_structure()

ProfilingService
├── profile_dataset()
├── profile_column()
└── analyze_relationships()

MappingService
├── generate_candidates()
├── score_candidates()
├── detect_ambiguity()
├── generate_explanation()
├── create_proposal()
├── approve_mapping()
└── persist_decision()

StandardizationService
├── apply_mapping()
├── normalize_types()
├── normalize_dates()
├── normalize_currency()
├── apply_rules()
└── validate_output()

PivotService
├── validate_definition()
├── execute()
└── persist_result()

ReconciliationService
├── prepare_sources()
├── match_records()
├── aggregate()
├── compare()
├── create_exceptions()
└── finalize()

TreatyService
├── create_treaty()
├── ingest_document()
├── extract_clauses()
├── simplify()
├── manage_clause()
└── version_treaty()

ComplianceService
├── create_control()
├── map_clause()
├── assess()
└── generate_matrix()

VersionService
├── create_snapshot()
├── compare()
└── restore()

LineageService
├── record_edge()
├── trace_upstream()
└── trace_downstream()

ReportService
├── assemble_report()
├── render_xlsx()
├── render_pdf()
└── publish()

IntegrationService
├── send_email()
├── send_teams()
├── publish_confluence()
└── sync_contacts()

AuditService
├── record_event()
├── get_history()
└── export_audit()

ObservabilityService
├── emit_metric()
├── record_run_event()
├── record_ai_call()
└── get_run_telemetry()
```

---

# 46. End-to-End State Machine

A processing job can use:

```text
CREATED
   ↓
UPLOADED
   ↓
INSPECTING
   ↓
STRUCTURE_DETECTED
   ↓
AWAITING_STRUCTURE_CONFIRMATION
   ↓
PROFILING
   ↓
MAPPING
   ↓
AWAITING_MAPPING_REVIEW
   ↓
STANDARDIZING
   ↓
MAPPING_COMPLETE
   ↓
PIVOTING
   ↓
READY_FOR_RECONCILIATION
   ↓
RECONCILING
   ↓
REPORTING
   ↓
COMPLETED
```

Failure states should be explicit and recoverable.

---

# 47. Error Handling

Errors should preserve context.

Bad:

```text
Something went wrong.
```

Better:

```text
Unable to generate standardized dataset.

Reason:
Column "Amount" has unresolved ambiguous mappings.

Next:
[Open Mapping Review] [View Details]
```

Every failure should contain:

- what failed
- why
- affected resource
- severity
- retry availability
- recommended next action
- technical details for engineers

---

# 48. Audit Trail

Audit every significant action.

Events include:

```text
FILE_UPLOADED
STRUCTURE_CONFIRMED
MAPPING_GENERATED
MAPPING_REVIEWED
MAPPING_APPROVED
PROFILE_CREATED
DATA_STANDARDIZED
PIVOT_EXECUTED
RECONCILIATION_STARTED
EXCEPTION_RESOLVED
TREATY_CREATED
CLAUSE_APPROVED
TREATY_RESTORED
REPORT_GENERATED
REPORT_EXPORTED
PERMISSION_CHANGED
CONNECTOR_USED
```

Each event should include:

```text
event_id
actor
timestamp
project
resource
action
before_state/reference
after_state/reference
correlation_id
```

---

# 49. Security and Confidentiality

The source requirements explicitly recognize that production bordereaux can contain confidential information.

Implementation requirements:

- development uses synthetic data
- production access is controlled
- least-privilege authorization
- encryption in transit and at rest
- secrets stored in a secret manager
- audit access to sensitive files
- tenant/project isolation
- configurable retention
- secure temporary-file cleanup
- controlled AI-provider data flow
- no confidential data sent to external providers unless explicitly allowed by deployment policy

---

# 50. Synthetic Demo Dataset

The application should include a built-in demo mode so the complete flow can be demonstrated without confidential production data.

Demo dataset should intentionally include:

- multi-row headers
- inconsistent column names
- blank/intermediate rows
- date variations
- currency variations
- ambiguous `Amount` fields
- gross/commission/net relationships
- a small technical subledger
- a treaty PDF/document with clauses and percentages

### Demo flow

```text
Load Demo Project
  ↓
Upload Demo Bordereaux
  ↓
Detect Structure
  ↓
Generate Mapping
  ↓
Show confidence
  ↓
Review ambiguous field
  ↓
Approve
  ↓
Generate Standardized Dataset
  ↓
Generate Claims Mapping
  ↓
Generate Pivot
  ↓
Run Reconciliation
  ↓
Inspect Variances
  ↓
Open Treaty Simplifier
  ↓
Generate Final Report
  ↓
Show Lineage
  ↓
Show Run Telemetry
```

This should satisfy the requirement to **show end-to-end working**.

---

# 51. UI Component Library

Create reusable components before building individual pages.

```text
Shell
├── AppHeader
├── Sidebar
├── WorkspaceSwitcher
├── GlobalSearch

Navigation
├── Breadcrumbs
├── ContextTree
├── Tabs
├── ResourcePicker

Resources
├── ResourceHeader
├── ResourceList
├── ResourceTable
├── ResourceCard
├── VersionSelector
├── ActivityFeed

Data
├── DataPreview
├── SchemaViewer
├── DataProfiler
├── MappingGrid
├── ConfidenceBadge
├── QualityPanel
├── LineageGraph

Workflow
├── WorkflowCanvas
├── TaskNode
├── DependencyEdge
├── RunTimeline
├── RunStatus

Review
├── ReviewQueue
├── EvidencePanel
├── DecisionBar
├── CommentBox

Treaty
├── DocumentViewer
├── ClauseList
├── ClauseInspector
├── ComplianceMatrix

Reporting
├── KPI
├── FilterBar
├── PivotTable
├── ReportPreview

Feedback
├── Toast
├── InlineError
├── EmptyState
├── LoadingState
├── ConfirmationDialog
```

---

# 52. UX Rules for Claude

When implementing the UI:

1. Do not create a flat sidebar with every function.
2. Keep the global shell persistent.
3. Keep project context visible when editing.
4. Use tabs for stable object dimensions.
5. Use a right-side inspector for selected objects.
6. Use progressive disclosure for advanced configuration.
7. Show evidence beside AI-generated decisions.
8. Make confidence visually prominent but never use color alone.
9. Make review actions easy to perform in-place.
10. Keep lineage one click away.
11. Show versions and history on important objects.
12. Never destroy historical state during rollback.
13. Prefer deterministic tables/grids for mapping and reconciliation.
14. Use visual graphs where relationships are central.
15. Surface actions that require attention on the homepage.

---

# 53. Accessibility

Minimum requirements:

- keyboard navigation
- screen-reader friendly labels
- accessible tables
- no color-only status indicators
- visible focus states
- meaningful error text
- sufficient contrast
- logical tab order
- accessible dialogs
- tooltips only as supplemental information

---

# 54. Performance Requirements

Recommended initial targets:

- file-upload feedback immediately after request acceptance
- preview should be incremental for large files
- never load a massive source dataset entirely into browser memory
- paginate large tables
- stream large exports
- long-running operations run asynchronously
- UI uses run IDs and polling/websocket updates
- cache stable metadata/search results where appropriate

---

# 55. Testing Strategy

## Unit tests

Cover:

- parsers
- structure detector
- normalizers
- mapping candidate generation
- confidence calculation
- financial relationship tests
- reconciliation math
- versioning
- lineage
- report assembly

## Golden dataset tests

Maintain labeled examples:

```text
source column → expected canonical field
```

Track:

- precision
- recall
- auto-accept accuracy
- review rate
- unresolved rate

## Integration tests

Test the full pipeline:

```text
file → structure → mapping → review → standardize → pivot → reconcile → report
```

## UI tests

Test:

- upload
- structure confirmation
- mapping review
- reconciliation exception resolution
- treaty review
- rollback
- permissions

---

# 56. Acceptance Criteria

## AC-01 — Standardization

A messy bordereaux containing multi-row headers, subheaders, and inconsistent formatting can be transformed into a clean canonical dataset.

## AC-02 — Correct mapping

Core fields such as reference, date, currency, sum insured, premium, commission, and related financial fields are mapped to the target schema.

## AC-03 — Context-aware mapping

Mapping decisions use metadata plus data evidence.

## AC-04 — Ambiguous money field

At least one ambiguous financial field is resolved using numerical relationships rather than name similarity alone.

## AC-05 — Confidence

Every mapping receives a confidence score and evidence.

## AC-06 — Human review

Low-confidence mappings enter a review queue and can be corrected.

## AC-07 — Claims mapping

The system produces a reusable `claims_mapping` artifact.

## AC-08 — Pivot

A pivot/aggregation can be generated from the standardized dataset and mapping artifact.

## AC-09 — Reconciliation

A technical subledger can be ingested, standardized, compared, and exceptioned against the bordereaux output.

## AC-10 — Treaty data

Treaty figures such as commission %, tax %, and share can be extracted or manually entered.

## AC-11 — Treaty clauses

Treaty/policy documents can be decomposed into reviewable clauses with evidence.

## AC-12 — Compliance linkage

A clause can be linked to a configurable regulatory/business control with traceable evidence.

## AC-13 — Versioning

Important objects maintain version history and can be restored without deleting previous versions.

## AC-14 — Lineage

A user can trace a final report back to the originating files and decisions.

## AC-15 — Reporting

A final report can be generated from finalized data.

## AC-16 — Observability

A processing run exposes status, timing, warnings, errors, AI calls, and outputs.

## AC-17 — Guardrails

The platform prevents unsupported AI decisions from being silently accepted.

## AC-18 — End-to-end demo

A synthetic example demonstrates the entire pipeline from raw bordereaux to report.

---

# 57. Suggested Repository Structure

```text
bordereaux-platform/
│
├── apps/
│   ├── web/
│   └── api/
│
├── backend/
│   ├── domain/
│   │   ├── ingestion/
│   │   ├── mapping/
│   │   ├── standardization/
│   │   ├── pivot/
│   │   ├── reconciliation/
│   │   ├── treaties/
│   │   ├── compliance/
│   │   ├── reporting/
│   │   ├── lineage/
│   │   ├── versioning/
│   │   ├── review/
│   │   ├── integrations/
│   │   ├── audit/
│   │   └── observability/
│   ├── api/
│   ├── workers/
│   ├── infrastructure/
│   └── tests/
│
├── frontend/
│   ├── components/
│   ├── features/
│   ├── layouts/
│   ├── pages/
│   └── lib/
│
├── schemas/
│   ├── canonical/
│   ├── api/
│   └── events/
│
├── demo/
│   ├── bordereaux/
│   ├── subledger/
│   ├── treaties/
│   └── expected_outputs/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── standards/
│   └── decisions/
│
└── README.md
```

---

# 58. Recommended Implementation Order

Do not implement every capability in parallel.

## Phase 1 — Product shell + source ingestion

Deliver:

- login/roles
- projects
- application shell
- search skeleton
- file upload
- file preview
- structure detection

## Phase 2 — Mapping intelligence

Deliver:

- canonical schema
- profiling
- candidate generation
- evidence collection
- confidence
- mapping review
- claims mapping

## Phase 3 — Standardization + pivot

Deliver:

- normalized dataset
- validation
- pivot definitions
- pivot output
- export

## Phase 4 — Subledger reconciliation

Deliver:

- subledger ingestion
- matching
- aggregation
- variance
- exceptions
- approval

## Phase 5 — Treaty intelligence

Deliver:

- treaty object
- document ingestion
- clause extraction
- simplification
- treaty figures
- change history

## Phase 6 — Compliance + reporting

Deliver:

- control model
- clause-to-control links
- compliance view
- final report generation

## Phase 7 — Enterprise capabilities

Deliver:

- lineage graph
- rollback
- Teams/email/Confluence connectors
- observability
- advanced governance
- reusable procedures
- consumer view

---

# 59. MVP Definition

The minimum useful product should prove this exact story:

```text
1. Upload messy bordereaux
2. Detect structure
3. Profile data
4. Generate canonical mappings
5. Show confidence
6. Identify one ambiguous financial mapping
7. Explain the evidence
8. Let analyst approve/correct it
9. Generate standardized dataset
10. Generate claims_mapping
11. Generate pivot
12. Ingest technical subledger
13. Reconcile
14. Show exceptions
15. Generate final report
16. Show lineage
17. Show run telemetry
```

Treaty simplification/compliance should be implemented as the next major workstream if the first demo must remain tightly scoped.

---

# 60. Important Implementation Decisions

## Decision A — deterministic first, AI second

Use rules and profiling first. Use AI where semantic ambiguity requires it.

## Decision B — versions are immutable

Never mutate history in place for a business-critical object.

## Decision C — evidence is mandatory

Every AI mapping must be explainable through stored evidence.

## Decision D — review is a product feature

Do not treat human review as an exception-only backend mechanism. It is a first-class UI and workflow.

## Decision E — mapping memory is valuable

Persist approved mappings as reusable procedures.

## Decision F — canonical schema is configurable

Do not scatter Lloyd's/ACORD field names throughout the codebase.

## Decision G — source and output are separate assets

Never overwrite raw input.

## Decision H — derived artifacts are linked

Dataset, claims mapping, pivot, reconciliation and report must remain connected through lineage.

---

# 61. Definition of Done for Claude

Claude should consider the feature complete only when:

- UI route exists
- backend API exists
- database models/migrations exist
- service-layer functions exist
- validation exists
- happy-path and error states exist
- audit events are emitted
- lineage is recorded
- version information is preserved
- tests cover the critical behavior
- demo data can exercise the flow
- the user can understand what happened without opening logs
- AI output is schema-validated
- human review can override AI output
- final outputs are downloadable

---

# 62. Final Architecture View

```text
                             USER
                              │
                 ┌────────────┴────────────┐
                 │                         │
             Persona                   Intent
                 │                         │
                 └────────────┬────────────┘
                              ▼
                     EXPERIENCE MODE
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
             Consumer      Professional     Admin
                              │
                              ▼
                       GLOBAL WORKSPACE
                              │
          ┌────────────┬─────┼─────┬────────────┐
          ▼            ▼     ▼     ▼            ▼
        Intake       Mapping  Data  Treaty   Operations
          │            │      │      │            │
          └────────────┴──────┼──────┴────────────┘
                              ▼
                         DATA ASSETS
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                 Standard  Claims     Treaty
                 Dataset   Mapping     Model
                    │         │         │
                    └────┬────┴────┬────┘
                         ▼         ▼
                     Pivot     Reconciliation
                         │         │
                         └────┬────┘
                              ▼
                           REPORT
                              │
                              ▼
                         LINEAGE / AUDIT

Cross-cutting layers:
────────────────────────────────────────────────────────
Identity & Access
Guardrails
Versioning / Rollback
Observability
Integrations
AI / Semantic Reasoning
Human Review
Search / Discovery
```

---

# 63. Product USP

The product's strongest differentiator should be presented as:

> **An evidence-driven, confidence-aware bordereaux intelligence platform that does not merely normalize files — it understands business meaning, knows when it is uncertain, asks a human at the right point, and preserves the full chain from raw source to reconciled, reportable output.**

The combination that should stand out in a demonstration is:

```text
Messy Data
   +
AI Semantic Mapping
   +
Data-Driven Financial Reasoning
   +
Human Validation
   +
Claims Mapping
   +
Pivot Aggregation
   +
Technical Subledger Reconciliation
   +
Treaty Intelligence
   +
Compliance Context
   +
Versioning / Rollback
   +
Full Lineage / Audit
   +
Operational Telemetry
```

---

