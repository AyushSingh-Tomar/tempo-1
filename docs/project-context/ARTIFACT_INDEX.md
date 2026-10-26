# Artifact Index
## Bordereaux Intelligence Platform — Project Discovery

> **Discovery Date:** 2026-10-09
> **Status:** Greenfield project (no existing implementation)
> **Project Type:** Enterprise reinsurance data standardization platform

---

## Artifact Inventory

### A01 — SOLUTION_DESIGN.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/SOLUTION_DESIGN.md` |
| Type | Architecture specification |
| Purpose | High-level solution architecture, tech stack, API surface, state machine, acceptance criteria |
| Key Contributions | Backend architecture (modular monolith), API endpoints, service functions, implementation phases 1-7, MVP definition |
| Related Artifacts | A02, A03, A04 |
| Requirements Contributed | AC-01 through AC-18 acceptance criteria |

**Main Information Extracted:**
- Tech stack: React/TypeScript frontend, Python/FastAPI/Pydantic/SQLAlchemy backend
- Storage: PostgreSQL, S3-compatible, Parquet for large datasets
- Pluggable LLM provider with structured JSON outputs
- State machine: CREATED → UPLOADED → PROFILED → MAPPED → STANDARDIZED → PIVOTED → RECONCILED → REVIEWED → COMPLETED
- "Deterministic first, AI second" principle established

---

### A02 — Implementation Overview.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/Implementation Overview.md` |
| Type | Product specification |
| Purpose | Complete product vision, user personas, experience architecture, canonical schema, mapping engine, UI specifications |
| Key Contributions | Core processing loop, target users, confidence scoring formula, human review workflow, testing strategy |
| Related Artifacts | A01, A03, A04 |
| Requirements Contributed | User roles, UX rules, accessibility requirements, performance targets |

**Main Information Extracted:**
- Core loop: INGEST → UNDERSTAND → PROFILE → MAP → REASON → SCORE → REVIEW → STANDARDIZE → RECONCILE → REPORT
- Target users: Reinsurance Analyst, Treaty Specialist, Reviewer, Admin, Consumer
- Confidence scoring: semantic 30%, value 25%, context 20%, layout 10%, AI 15% (revised; exact data-dictionary term = 100%)
- 15 evidence source types for semantic mapping
- Claims Mapping artifact schema with versioning
- Ambiguous financial field resolution (Gross Premium - Commission ≈ Net Premium)

---

### A03 — Module_1_ingestion_and_renaming.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/Module_1_ingestion_and_renaming.md` |
| Type | Module implementation specification |
| Purpose | AI-Aided Mapping & Relationship Inference module — detailed implementation guide |
| Key Contributions | File adapters, format detection, profiling, candidate mapping, relationship inference, LLM integration, Python architecture |
| Related Artifacts | A01, A02, A04 |
| Requirements Contributed | 31 Definition of Done criteria, 6 implementation phases |

**Main Information Extracted:**
- Supported formats: CSV, XLSX, JSON, XML, PDF, Parquet, HTML, EDI, SAS, etc.
- FileAdapter Protocol interface pattern
- Format detection: magic bytes, MIME, probes
- 24-step end-to-end workflow
- Candidate mapping generation: alias match, normalized name, token similarity, semantic retrieval, type compatibility
- Relationship inference: arithmetic, ratio, referential, key-based
- LLM integration philosophy: compact evidence packages, structured JSON outputs, caching strategy
- Python package structure with domain-driven design

---

### A04 — Module_2_Reconciliation_Implement.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/Module_2_Reconciliation_Implement.md` |
| Type | Module implementation specification |
| Purpose | Reconciliation module — comparing Claims Mapping against Subledger sources |
| Key Contributions | Subledger ingestion, pivot/aggregation, variance computation, deterministic diagnostics, LLM-assisted diagnostics, treaty rules |
| Related Artifacts | A03, A05 |
| Requirements Contributed | 36 Definition of Done criteria, 9 implementation phases |

**Main Information Extracted:**
- Reconciliation status model: MATCH, WITHIN_TOLERANCE, UNRECONCILED, VALID_DIFFERENCE, INVESTIGATE, DATA_ERROR, UNRESOLVED
- 33 built-in deterministic checks (D001-D033)
- Root-cause taxonomy with 21 categories
- Variance computation: absolute and percentage thresholds with combined policies
- LLM invocation points: mismatch classification, semantic code equivalence, relationship interpretation, cluster interpretation, investigation requests
- Token budgets per operation type
- Reconciliation run lifecycle: DRAFT → VALIDATING → RUNNING → DIAGNOSTICS → REVIEW → FINALIZED
- Retro amounts and iterative adjustments handling

---

### A05 — Treaty_Management_Section_Implement.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/Treaty_Management_Section_Implement.md` |
| Type | Module implementation specification |
| Purpose | Treaty management — discovery, versioning, what-if scenarios, reconciliation impact analysis |
| Key Contributions | Treaty manifest, editable blocks, patch validation, state versioning, branching, rollback |
| Related Artifacts | A04 |
| Requirements Contributed | Treaty state lifecycle, permission model, audit requirements |

**Main Information Extracted:**
- Treaty manifest schema with discovery confidence
- Editable block types: ADD_CLAUSE, REMOVE_CLAUSE, UPDATE_CLAUSE, UPDATE_PARAMETER, etc.
- Patch operations: ADD, REMOVE, REPLACE with validation pipeline
- State types: BASELINE, SCENARIO, BRANCH, ROLLBACK, APPROVED, SUPERSEDED
- What-if analysis: baseline vs scenario reconciliation comparison
- LLM boundary: discovery assistance only, cannot mutate state
- Permission model: TREATY_VIEWER, TREATY_DISCOVERY_REVIEWER, TREATY_EDITOR, TREATY_APPROVER, TREATY_ADMIN

---

### A06 — Checks_to_perform.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/Checks_to_perform.md` |
| Type | Reconciliation framework guide |
| Purpose | Detailed check taxonomy for Claims Mapping vs Subledger reconciliation |
| Key Contributions | Three-layer check architecture (Python/AI/Human), normalization requirements, root-cause library |
| Related Artifacts | A04 |
| Requirements Contributed | Pre-reconciliation normalization, check categories, exception report format |

**Main Information Extracted:**
- Three-layer architecture: Layer A (Python/deterministic), Layer B (AI-assisted), Layer C (Human investigation)
- 5 Python check levels: Structural, Completeness, Integrity, Value, Distribution
- 10 AI check categories: semantic column mapping, equivalent values, explain mismatches, pattern detection, transformation errors, field shifts, business rule inconsistencies, suspicious clusters, fuzzy matching, root-cause classification
- 10 Human investigation areas: business definition, reconciliation key, one-to-many relationships, timing, adjustments, mapping rules, source-system changes, historical comparison, individual tracing, acceptance determination
- Root-cause library: 8 categories (extraction, mapping, duplicates, transformation, timing, business process, formatting, master data)

---

### A07 — databricks_ui_reference.md
| Attribute | Value |
|-----------|-------|
| Path | `Artifacts/databricks_ui_reference.md` |
| Type | UX/UI design reference |
| Purpose | Enterprise data platform UI architecture principles and patterns |
| Key Contributions | Navigation philosophy, persona segmentation, progressive disclosure, component hierarchy |
| Related Artifacts | A02 (UI specifications) |
| Requirements Contributed | UI design principles, shell architecture, persona-based experiences |

**Main Information Extracted:**
- Five organizational dimensions: user persona, user intent, current object, interaction depth, technical complexity
- Shell pattern: one stable shell, multiple experiences
- Three-layer navigation: Workspace → Product Area → Object
- Persona modes: Data Engineer, Data Analyst, Business User, Administrator
- Progressive disclosure principle
- Inspector pattern for complex configuration
- 12 recommended design rules
- Component hierarchy: Shell, Navigation, Objects, Data, Workflow, Analytics, Governance, Feedback

---

## Cross-Artifact Relationships

```
A01 (SOLUTION_DESIGN)
 ├── defines architecture for → A03, A04, A05
 └── references → A02 (product vision)

A02 (Implementation Overview)
 ├── provides requirements for → A03, A04
 ├── UI specs align with → A07
 └── testing strategy covers → A03, A04, A05

A03 (Module 1 - Ingestion/Mapping)
 ├── produces artifacts for → A04 (Reconciliation)
 └── shares design principles with → A04, A05

A04 (Module 2 - Reconciliation)
 ├── consumes from → A03 (Claims Mapping)
 ├── uses → A05 (Treaty rules)
 └── implements checks from → A06

A05 (Treaty Management)
 ├── integrates with → A04 (reconciliation runs)
 └── follows principles from → A03 (immutability, versioning)

A06 (Checks_to_perform)
 └── provides detailed taxonomy for → A04

A07 (UI Reference)
 └── provides design patterns for → A02 (experience architecture)
```

---

## Key Design Decisions Across Artifacts

| Decision | Source | Rationale |
|----------|--------|-----------|
| Deterministic first, AI second | A01, A03, A04 | Rules/profiling before LLM ensures reproducibility and auditability |
| Raw data immutable | A03, A04, A05 | Preserves source lineage and enables version comparison |
| AI cannot mutate business state | A03, A04, A05 | AI produces recommendations, humans approve changes |
| Evidence mandatory | A03, A04 | Every mapping/reconciliation decision traceable to source |
| Versions immutable | A01, A04, A05 | Once created, artifacts cannot be modified, only superseded |
| Configurable canonical schema | A02, A03 | Lloyd's V5.2, ACORD standards, or custom schema |
| Pluggable LLM provider | A01 | Avoid vendor lock-in, support multiple providers |
| Modular monolith + async workers | A01 | Balance between microservices complexity and monolith simplicity |

---

## Technology Stack Summary

| Layer | Technology | Source |
|-------|------------|--------|
| Frontend | React, TypeScript | A01, A02 |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy | A01, A03 |
| Database | PostgreSQL | A01 |
| Object Storage | S3-compatible | A01 |
| Large Datasets | Parquet | A01, A04 |
| LLM | Pluggable provider, structured JSON outputs | A01, A03, A04 |
| Task Queue | Async workers (implementation TBD) | A01 |

---

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    Platform Core                             │
│  (Auth, Projects, Storage, Versioning, Audit, Lineage)      │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Module 1    │ │   Module 2    │ │    Treaty     │
│   Ingestion   │─▶│ Reconciliation│◀─│  Management   │
│   & Mapping   │ │               │ │               │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                 ┌───────────────┐
                 │   Reporting   │
                 │   & Export    │
                 └───────────────┘
```

---

## Implementation Priority (from artifacts)

### Phase 1 — Foundation (A01, A03)
- File ingestion and format detection
- Structure detection and profiling
- Canonical schema definition
- Basic storage and versioning

### Phase 2 — Mapping Engine (A03)
- Candidate mapping generation
- Deterministic scoring
- Relationship inference
- Manual mapping API

### Phase 3 — Reconciliation Core (A04, A06)
- Subledger ingestion and unification
- Pivot/aggregation engine
- Variance computation
- Deterministic diagnostics

### Phase 4 — Treaty Management (A05)
- Treaty discovery and manifest
- State versioning and branching
- What-if reconciliation

### Phase 5 — AI Integration (A03, A04)
- LLM-assisted mapping disambiguation
- Mismatch classification
- Investigation interface

### Phase 6 — UI/UX (A02, A07)
- Desktop shell with sidebar
- Project management
- Review workflows
- Reporting dashboards

### Phase 7 — Production Hardening (A01)
- Performance optimization
- Security and compliance
- Monitoring and observability
