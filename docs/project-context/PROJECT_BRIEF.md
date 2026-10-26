# Project Brief
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Pre-implementation specification complete

---

## Executive Summary

The Bordereaux Intelligence Platform is an enterprise reinsurance data standardization system that transforms heterogeneous insurance data (Claims Mappings, Subledgers, Treaty documents) into a unified canonical format. The platform uses AI-assisted semantic field mapping with confidence scoring while maintaining a "deterministic first, AI second" principle.

**Core Value Proposition:** Reduce the manual effort of reconciling reinsurance data from days to hours while maintaining full audit trails and human oversight for critical decisions.

---

## Problem Statement

Reinsurance operations face significant challenges with data standardization:

1. **Heterogeneous Data Sources:** Claims Mappings arrive in diverse formats (CSV, Excel, XML, PDF, EDI, SAS) with inconsistent column names and structures
2. **Manual Mapping Effort:** Analysts spend days manually mapping source fields to canonical schemas
3. **Reconciliation Complexity:** Comparing Claims Mapping views against Subledger sources requires understanding of treaty rules, timing differences, and legitimate business variations
4. **Audit Requirements:** Financial reconciliation requires complete traceability from exceptions back to source records
5. **Treaty Complexity:** Treaty clauses and parameters affect how reconciliation should be evaluated, but these rules are often implicit

---

## Solution Overview

### Core Processing Loop

```
INGEST → UNDERSTAND → PROFILE → MAP → REASON → SCORE → REVIEW → STANDARDIZE → RECONCILE → REPORT
```

### Key Capabilities

1. **Multi-Format Ingestion:** Support for 15+ file formats with automatic format detection
2. **Semantic Mapping Engine:** AI-assisted field mapping with 15 evidence source types
3. **Relationship Inference:** Automatic detection of arithmetic, ratio, referential, and key-based relationships
4. **Confidence Scoring:** Weighted scoring model (semantic 30%, value 25%, context 20%, layout 10%, AI 15% (revised; exact data-dictionary term = 100%))
5. **Human-in-the-Loop Review:** Mandatory review for low-confidence mappings
6. **Subledger Reconciliation:** Claims Mapping vs Subledger comparison with 33 built-in diagnostic checks
7. **Treaty-Aware Reconciliation:** What-if scenario testing with treaty state versioning
8. **Full Lineage:** Every derived value traceable to source artifact, row, and transformation

---

## Target Users

| Persona | Primary Tasks | Key Needs |
|---------|---------------|-----------|
| **Reinsurance Analyst** | Upload files, review mappings, configure reconciliation | Efficiency, accuracy, minimal manual work |
| **Treaty Specialist** | Configure treaty rules, review treaty-related exceptions | Treaty parameter management, impact analysis |
| **Reviewer** | Approve/reject AI recommendations, resolve exceptions | Clear evidence, decision audit trail |
| **Admin** | Manage users, configure schemas, monitor system | Platform administration, security |
| **Consumer** | View reports, dashboards | Self-service access to reconciliation results |

---

## Technical Architecture

### Architecture Pattern
Modular monolith with async workers — balances development velocity with service isolation for compute-intensive tasks.

### Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | React, TypeScript |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL |
| Object Storage | S3-compatible (MinIO for dev) |
| Large Dataset Storage | Parquet |
| LLM Integration | Pluggable provider, structured JSON outputs |
| Task Queue | Async workers (Celery/RQ) |

### Module Structure

```
backend/
├── domain/
│   ├── ingestion/         # File parsing, format detection
│   ├── profiling/         # Schema inference, statistics
│   ├── mapping/           # Field mapping engine
│   ├── relationships/     # Relationship inference
│   ├── standardization/   # Canonical transformation
│   ├── reconciliation/    # Comparison engine
│   │   ├── subledger/     # Subledger handling
│   │   ├── pivot/         # Aggregation layer
│   │   ├── diagnostics/   # Deterministic checks
│   │   └── treaties/      # Treaty management
│   ├── ai/                # LLM integration
│   ├── reporting/         # Report generation
│   └── lineage/           # Audit trail
├── api/                   # REST endpoints
├── core/                  # Shared utilities
└── infrastructure/        # Storage, messaging
```

---

## Key Design Principles

### 1. Deterministic First, AI Second
- Python handles: parsing, profiling, aggregation, joins, variance calculation, threshold evaluation
- AI handles: semantic interpretation, ambiguity resolution, pattern explanation
- AI never directly mutates business state

### 2. Raw Data Is Immutable
```
RAW → PARSED → NORMALIZED → CANONICAL → DERIVED
```
Every stage preserves source reference.

### 3. Evidence Is Mandatory
Every mapping decision, reconciliation result, or AI recommendation must cite:
- Source artifact and version
- Source row/column
- Rule or algorithm applied
- Confidence score with breakdown

### 4. Versions Are Immutable
Once created, artifacts cannot be modified — only superseded by new versions.

### 5. Human Review Is a Normal Workflow
Low-confidence decisions route to human review queue, not silent acceptance.

---

## Canonical Schema

Configurable to support:
- Lloyd's V5.2 standard
- ACORD standards
- Custom organizational schemas

Core Claims Mapping fields:
```yaml
claim_id: string (required)
policy_id: string (conditional)
transaction_date: date
posting_date: date
gross_premium: decimal
commission: decimal
net_premium: decimal
claim_amount: decimal
currency: string
treaty_id: string
clause_id: string
status: enum
```

---

## Reconciliation Framework

### Status Model
```
MATCH              - Values reconcile exactly
WITHIN_TOLERANCE   - Difference within configured threshold
VALID_DIFFERENCE   - Explained by legitimate business reason
INVESTIGATE        - Requires human investigation
DATA_ERROR         - Confirmed data quality issue
UNRESOLVED         - Cannot be classified
```

### Three-Layer Check Architecture

**Layer A — Python/Deterministic (33 checks)**
- Structural: file existence, schema, data types
- Completeness: row counts, distinct keys, missing records
- Integrity: duplicates, nulls, referential integrity
- Value: SUM, variance, hash comparison
- Distribution: counts by period, status, account

**Layer B — AI-Assisted**
- Semantic column mapping
- Code equivalence detection
- Mismatch pattern clustering
- Root-cause classification
- Transformation error detection

**Layer C — Human Investigation**
- Business definition confirmation
- Reconciliation key validation
- Timing difference assessment
- Adjustment/reversal evaluation
- Final acceptance/rejection

---

## Treaty Management

### Capabilities
- Treaty discovery from data and configuration
- Manifest generation with clause/parameter detection
- Editable blocks for safe modification
- State versioning with branching
- What-if scenario reconciliation
- Impact analysis (baseline vs scenario)

### State Lifecycle
```
BASELINE → SCENARIO → APPROVED → ACTIVE
             ↓
          BRANCH → ROLLBACK
```

---

## Quality Gates

### Mapping Quality Gates
- Confidence threshold: configurable (default 0.85)
- Coverage requirement: configurable (default 0.95)
- Mandatory review for AI-only evidence

### Reconciliation Quality Gates
- Key collision rate: < 0.01
- Null critical fields: 0%
- Schema validation: required
- Treaty configuration: required for treaty-specific reconciliation

---

## MVP Definition (17 steps)

1. Create project
2. Upload Claims Mapping file
3. Auto-detect format and structure
4. Profile columns
5. Generate candidate mappings
6. Review/approve mappings
7. Apply standardization
8. Upload Subledger file(s)
9. Unify subledgers
10. Define reconciliation relationship
11. Configure variance thresholds
12. Run reconciliation
13. View match/mismatch summary
14. Run deterministic diagnostics
15. Review exceptions
16. Export reconciliation report
17. View lineage for any value

---

## Acceptance Criteria Summary

| ID | Criteria |
|----|----------|
| AC-01 | Multiple file formats supported (CSV, XLSX, JSON, XML, PDF, Parquet) |
| AC-02 | Automatic structure detection with header reconstruction |
| AC-03 | Column profiling with statistics and patterns |
| AC-04 | Candidate mapping with confidence scores |
| AC-05 | Human review workflow for low-confidence mappings |
| AC-06 | Relationship inference (arithmetic, referential) |
| AC-07 | Canonical schema transformation |
| AC-08 | Subledger multi-source unification |
| AC-09 | Pivot/aggregation at configurable grain |
| AC-10 | Variance computation with thresholds |
| AC-11 | Deterministic diagnostic checks |
| AC-12 | LLM-assisted mismatch classification |
| AC-13 | Treaty rule evaluation |
| AC-14 | What-if scenario comparison |
| AC-15 | Full lineage from exception to source |
| AC-16 | Audit trail for all decisions |
| AC-17 | Reconciliation report generation |
| AC-18 | Version comparison across runs |

---

## Security and Compliance

- Development uses synthetic data only
- No confidential data sent to external LLM providers unless explicitly allowed
- Sensitive field redaction before LLM calls
- Deterministic pseudonymization for relationship preservation
- Role-based access control
- Audit logging for all state changes

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Mapping accuracy (vs human baseline) | ≥ 95% |
| Time to first reconciliation | < 2 hours (was days) |
| False positive rate (valid flagged as error) | < 5% |
| Lineage completeness | 100% |
| Human review queue accuracy | ≥ 90% actionable items |

---

## Project Constraints

1. **No existing codebase** — greenfield implementation
2. **Specification-driven** — artifacts define requirements, not ad-hoc development
3. **Phased delivery** — foundation before features
4. **Token efficiency** — LLM calls minimized through deterministic pre-processing
5. **Evidence-based AI** — AI interprets evidence, does not generate facts
