# Requirements Specification
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09

---

## 1. Functional Requirements

### 1.1 File Ingestion (FR-ING)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-ING-01 | Support file formats: CSV, TSV, XLSX, XLS, JSON, JSONL, XML, PDF, Parquet, HTML, EDI, SAS, TXT | Must | A03 §4.1 |
| FR-ING-02 | Automatic format detection using magic bytes, MIME type, and probes | Must | A03 §4.2 |
| FR-ING-03 | FileAdapter Protocol for pluggable format parsers | Must | A03 §4.1 |
| FR-ING-04 | Generate SHA-256 checksum for every uploaded file | Must | A04 §4.1 |
| FR-ING-05 | Preserve original file as immutable artifact | Must | A03 §2.2 |
| FR-ING-06 | Multi-sheet Excel extraction with sheet identification | Should | A03 §4.1 |
| FR-ING-07 | PDF table extraction with structure inference | Should | A03 §4.1 |
| FR-ING-08 | Logical input model classification (Claims Mapping vs Subledger) | Must | A03 §5 |

### 1.2 Structure Detection (FR-STR)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-STR-01 | Detect header row position (may not be row 1) | Must | A03 §6 |
| FR-STR-02 | Handle multi-row headers with reconstruction | Should | A03 §7 |
| FR-STR-03 | Detect data region boundaries | Must | A03 §6 |
| FR-STR-04 | Identify merged cells in Excel | Should | A03 §6 |
| FR-STR-05 | Output structure detection result with confidence | Must | A03 §6 |

### 1.3 Data Profiling (FR-PRO)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-PRO-01 | Dataset-level profiling: row count, column count, file size | Must | A03 §8 |
| FR-PRO-02 | Column-level profiling: data type, null rate, distinct count | Must | A03 §8 |
| FR-PRO-03 | String feature extraction: length stats, pattern detection | Must | A03 §8 |
| FR-PRO-04 | Numeric feature extraction: min, max, mean, median, distribution | Must | A03 §8 |
| FR-PRO-05 | Date feature extraction: range, format patterns | Must | A03 §8 |
| FR-PRO-06 | Categorical value enumeration with frequency | Must | A03 §8 |
| FR-PRO-07 | Generate profile hash for caching | Should | A03 §20 |

### 1.4 Canonical Schema (FR-SCH)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-SCH-01 | Configurable canonical schema definition in YAML | Must | A03 §9 |
| FR-SCH-02 | Support Lloyd's V5.2 standard schema | Should | A02 §3 |
| FR-SCH-03 | Support ACORD standard schema | Should | A02 §3 |
| FR-SCH-04 | Custom organizational schema support | Must | A02 §3 |
| FR-SCH-05 | Schema versioning with migration support | Must | A01 §decisions |
| FR-SCH-06 | Field-level metadata: type, required, aliases, validation rules | Must | A03 §9 |

### 1.5 Mapping Engine (FR-MAP)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-MAP-01 | Alias-based candidate matching | Must | A03 §10 |
| FR-MAP-02 | Normalized name matching (case, whitespace, abbreviation) | Must | A03 §10 |
| FR-MAP-03 | Token similarity scoring | Must | A03 §10 |
| FR-MAP-04 | Semantic retrieval using embeddings | Should | A03 §10 |
| FR-MAP-05 | Type compatibility validation | Must | A03 §10 |
| FR-MAP-06 | Generate multiple candidates per source field | Must | A03 §10 |
| FR-MAP-07 | Configurable scoring weights | Should | A03 §11 |
| FR-MAP-08 | Manual mapping override API | Must | A03 §22 |
| FR-MAP-09 | Historical mapping reuse | Should | A03 §10 |
| FR-MAP-10 | Mapping version control | Must | A03 §22 |

### 1.6 Confidence Scoring (FR-CON)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-CON-01 | Weighted confidence formula: semantic 20%, value 20%, context 15%, layout 5%, relationship 20%, historical 10%, AI 10% | Must | A02 §4.2 |
| FR-CON-02 | Confidence calibration against ground truth | Should | A03 §14 |
| FR-CON-03 | Hard safety gates for minimum thresholds | Must | A03 §15 |
| FR-CON-04 | Evidence breakdown per confidence component | Must | A03 §14 |

### 1.7 Relationship Inference (FR-REL)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-REL-01 | Arithmetic relationship detection (A + B ≈ C) | Must | A03 §12 |
| FR-REL-02 | Ratio relationship detection (A / B ≈ C) | Must | A03 §12 |
| FR-REL-03 | Referential relationship detection (foreign keys) | Must | A03 §12 |
| FR-REL-04 | Key-based relationship detection (primary/composite keys) | Must | A03 §12 |
| FR-REL-05 | Financial relationship inference (Gross - Commission ≈ Net) | Must | A02 §4.1 |
| FR-REL-06 | User-defined custom relationship checks | Should | A03 §23 |
| FR-REL-07 | Cross-file relationship detection | Should | A03 §24 |

### 1.8 Human Review (FR-REV)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-REV-01 | Review queue for low-confidence mappings | Must | A02 §5 |
| FR-REV-02 | Review status: PENDING, APPROVED, REJECTED, ESCALATED | Must | A02 §5 |
| FR-REV-03 | Bulk approval/rejection actions | Should | A02 §5 |
| FR-REV-04 | Review decision audit trail | Must | A02 §5 |
| FR-REV-05 | Configurable confidence threshold for auto-approval | Must | A03 §15 |

### 1.9 Schema Templates (FR-TPL)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-TPL-01 | Create template from finalized mapping set | Must | User Request |
| FR-TPL-02 | Template scope: project-level or global | Must | User Request |
| FR-TPL-03 | Automatic matching of templates to new files based on structure | Must | User Request |
| FR-TPL-04 | Apply template to generate/boost mapping candidates | Must | User Request |
| FR-TPL-05 | Template flexibility levels: strict, flexible, loose | Must | User Request |
| FR-TPL-06 | Track template usage count | Should | User Request |
| FR-TPL-07 | Deprecate/archive templates | Should | User Request |
| FR-TPL-08 | Template match score calculation | Must | User Request |
| FR-TPL-09 | Confidence boost from template application | Must | User Request |

### 1.10 Standardization (FR-STD)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-STD-01 | Apply approved mappings to transform data | Must | A03 §core |
| FR-STD-02 | Type coercion with validation | Must | A03 §core |
| FR-STD-03 | Date format normalization | Must | A06 §pre-check |
| FR-STD-04 | Currency normalization | Should | A04 §6 |
| FR-STD-05 | Preserve source lineage for every standardized row | Must | A03 §2.4 |
| FR-STD-06 | Generate standardized dataset version | Must | A03 §2.2 |

### 1.10 Subledger Management (FR-SUB)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-SUB-01 | Multiple subledger ingestion per reconciliation | Must | A04 §4.1 |
| FR-SUB-02 | Subledger standardization to canonical schema | Must | A04 §4.2 |
| FR-SUB-03 | Unified subledger generation from multiple sources | Must | A04 §4.3 |
| FR-SUB-04 | Source lineage preservation per unified row | Must | A04 §4.3 |
| FR-SUB-05 | Subledger relationship inference | Should | A04 §4.4 |

### 1.11 Pivot/Aggregation (FR-PIV)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-PIV-01 | Configurable pivot dimensions | Must | A04 §12 |
| FR-PIV-02 | Configurable measures with aggregation functions | Must | A04 §13 |
| FR-PIV-03 | Filter support in pivot definitions | Should | A04 §13 |
| FR-PIV-04 | Rounding configuration | Must | A04 §13 |
| FR-PIV-05 | Pivot inference from TA reporting templates | Should | A04 §14 |
| FR-PIV-06 | Pivot validation before reconciliation | Must | A04 §15 |

### 1.12 Reconciliation Engine (FR-REC)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-REC-01 | Full outer join comparison | Must | A04 §24 |
| FR-REC-02 | Configurable reconciliation grain (dimensions) | Must | A04 §16 |
| FR-REC-03 | Composite key support | Must | A04 §26 |
| FR-REC-04 | Absolute variance calculation | Must | A04 §18 |
| FR-REC-05 | Percentage variance calculation | Must | A04 §18.1 |
| FR-REC-06 | Combined threshold policies (AND/OR) | Must | A04 §18.2 |
| FR-REC-07 | Zero-denominator handling | Must | A04 §19 |
| FR-REC-08 | One-to-many relationship aggregation | Must | A04 §28 |
| FR-REC-09 | Record-level reconciliation | Should | A04 §25 |
| FR-REC-10 | Key quality validation before reconciliation | Must | A04 §27 |

### 1.13 Reconciliation Status (FR-STA)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-STA-01 | Status model: MATCH, WITHIN_TOLERANCE, UNRECONCILED, VALID_DIFFERENCE, INVESTIGATE, DATA_ERROR, UNRESOLVED | Must | A04 §22 |
| FR-STA-02 | Run-level status: PASSED, PASSED_WITH_EXCEPTIONS, FAILED, BLOCKED | Must | A04 §22 |
| FR-STA-03 | Exception status workflow | Must | A04 §66 |

### 1.14 Deterministic Diagnostics (FR-DIA)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-DIA-01 | Level 1 — Structural checks (D001-D008) | Must | A04 §30 |
| FR-DIA-02 | Level 2 — Completeness checks (D009-D013) | Must | A04 §30 |
| FR-DIA-03 | Level 3 — Integrity checks (D014-D023) | Must | A04 §30 |
| FR-DIA-04 | Level 4 — Value checks (D024-D029) | Must | A04 §30 |
| FR-DIA-05 | Level 5 — Distribution checks (D030-D033) | Must | A04 §30 |
| FR-DIA-06 | Structured finding schema with evidence | Must | A04 §32 |
| FR-DIA-07 | Root-cause taxonomy (21 categories) | Must | A04 §33 |
| FR-DIA-08 | User-defined custom checks with sandbox | Should | A04 §35 |

### 1.15 LLM Integration (FR-LLM)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-LLM-01 | Mismatch reason classification | Should | A04 §40 |
| FR-LLM-02 | Semantic code equivalence | Should | A04 §40 |
| FR-LLM-03 | Ambiguous relationship interpretation | Should | A04 §40 |
| FR-LLM-04 | Mismatch cluster interpretation | Should | A04 §40 |
| FR-LLM-05 | AI investigation request handling | Should | A04 §40 |
| FR-LLM-06 | Structured JSON output enforcement | Must | A04 §47 |
| FR-LLM-07 | Output schema validation (Pydantic) | Must | A04 §48 |
| FR-LLM-08 | Evidence package minimization | Must | A04 §41 |
| FR-LLM-09 | Token budget enforcement | Should | A04 §45 |
| FR-LLM-10 | LLM response caching | Should | A04 §87 |
| FR-LLM-11 | No-LLM mode support | Must | A04 §89 |

### 1.16 Treaty Management (FR-TRT)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-TRT-01 | Treaty discovery from data and configuration | Should | A05 §12 |
| FR-TRT-02 | Treaty manifest generation | Should | A05 §6 |
| FR-TRT-03 | Clause and parameter discovery | Should | A05 §7-8 |
| FR-TRT-04 | Editable block generation | Should | A05 §17 |
| FR-TRT-05 | Patch validation pipeline | Should | A05 §24 |
| FR-TRT-06 | Atomic patch application | Must | A05 §59 |
| FR-TRT-07 | Treaty state versioning | Must | A05 §30 |
| FR-TRT-08 | State branching for scenarios | Should | A05 §35 |
| FR-TRT-09 | Rollback without deletion | Must | A05 §3.5 |
| FR-TRT-10 | What-if reconciliation comparison | Should | A05 §42 |
| FR-TRT-11 | Impact analysis metrics | Should | A05 §44 |

### 1.17 Reporting (FR-RPT)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-RPT-01 | Executive summary generation | Must | A04 §68 |
| FR-RPT-02 | Reconciliation summary with metrics | Must | A04 §69 |
| FR-RPT-03 | Exception detail report | Must | A04 §70 |
| FR-RPT-04 | Variance analysis breakdown | Must | A04 §68 |
| FR-RPT-05 | Lineage report | Must | A04 §68 |
| FR-RPT-06 | Export formats: JSON, CSV, XLSX, PDF, HTML | Should | A04 §82 |
| FR-RPT-07 | Run comparison report | Should | A04 §65 |

### 1.18 Lineage (FR-LIN)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-LIN-01 | Source artifact → standardized row traceability | Must | A04 §7 |
| FR-LIN-02 | Standardized row → canonical row traceability | Must | A04 §7 |
| FR-LIN-03 | Canonical row → aggregate row traceability | Must | A04 §7 |
| FR-LIN-04 | Aggregate row → exception traceability | Must | A04 §7 |
| FR-LIN-05 | Exception → report item traceability | Must | A04 §71 |

### 1.19 Versioning (FR-VER)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-VER-01 | Immutable artifact versions | Must | A01 §decisions |
| FR-VER-02 | Claims Mapping version tracking | Must | A03 §2.2 |
| FR-VER-03 | Reconciliation run versioning | Must | A04 §2.5 |
| FR-VER-04 | Treaty state versioning | Must | A05 §30 |
| FR-VER-05 | Version comparison APIs | Should | A04 §65 |

### 1.20 Project Management (FR-PRJ)

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-PRJ-01 | Project creation with metadata | Must | A01 §API |
| FR-PRJ-02 | Project state machine tracking | Must | A01 §state |
| FR-PRJ-03 | Asset association with projects | Must | A01 §API |
| FR-PRJ-04 | Processing profile/template reuse | Should | A02 §5.2 |

---

## 2. Non-Functional Requirements

### 2.1 Performance (NFR-PER)

| ID | Requirement | Target | Source |
|----|-------------|--------|--------|
| NFR-PER-01 | File ingestion throughput | ≥ 100MB/min | A01 |
| NFR-PER-02 | Profiling response for 100K rows | < 30 seconds | A01 |
| NFR-PER-03 | Mapping generation for 100 columns | < 60 seconds | A01 |
| NFR-PER-04 | Reconciliation for 1M row pairs | < 5 minutes | A01 |
| NFR-PER-05 | Report generation | < 30 seconds | A01 |

### 2.2 Scalability (NFR-SCA)

| ID | Requirement | Target | Source |
|----|-------------|--------|--------|
| NFR-SCA-01 | Maximum file size | 1GB | A01 |
| NFR-SCA-02 | Maximum rows per dataset | 10M | A01 |
| NFR-SCA-03 | Concurrent users | 50 | A01 |
| NFR-SCA-04 | Concurrent reconciliation jobs | 10 | A01 |

### 2.3 Reliability (NFR-REL)

| ID | Requirement | Target | Source |
|----|-------------|--------|--------|
| NFR-REL-01 | Processing idempotency | Required | A04 §86 |
| NFR-REL-02 | Checkpoint/resume for long jobs | Required | A04 §97 |
| NFR-REL-03 | Atomic transactions for state changes | Required | A05 §60 |
| NFR-REL-04 | Graceful degradation without LLM | Required | A04 §89 |

### 2.4 Security (NFR-SEC)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-SEC-01 | Authentication required for all API endpoints | A01 |
| NFR-SEC-02 | Role-based access control | A05 §69 |
| NFR-SEC-03 | Sensitive field redaction before LLM calls | A04 §100 |
| NFR-SEC-04 | Deterministic pseudonymization for LLM | A04 §101 |
| NFR-SEC-05 | API key vaulting (no secrets in code/config) | A04 §103 |
| NFR-SEC-06 | Audit logging for all state changes | A04 §104 |

### 2.5 Compliance (NFR-COM)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-COM-01 | Full audit trail for financial decisions | A04 §104 |
| NFR-COM-02 | Immutable audit event storage | A05 §68 |
| NFR-COM-03 | Data residency support | A04 §103 |
| NFR-COM-04 | Retention policy support | A05 §3.5 |

### 2.6 Usability (NFR-USA)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-USA-01 | Desktop-first responsive design | A02 §6 |
| NFR-USA-02 | WCAG 2.1 AA accessibility | A02 §7 |
| NFR-USA-03 | Keyboard navigation support | A02 §7 |
| NFR-USA-04 | Progressive disclosure pattern | A07 §3 |
| NFR-USA-05 | Contextual help/documentation | A07 §2.1 |

### 2.7 Maintainability (NFR-MAI)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-MAI-01 | Domain-driven package structure | A03 §25 |
| NFR-MAI-02 | Comprehensive unit test coverage (≥80%) | A03 §30 |
| NFR-MAI-03 | Golden dataset regression tests | A04 §92 |
| NFR-MAI-04 | API versioning | A01 |
| NFR-MAI-05 | Configuration externalization | A03 §27 |

### 2.8 Observability (NFR-OBS)

| ID | Requirement | Source |
|----|-------------|--------|
| NFR-OBS-01 | Structured logging | A04 §98 |
| NFR-OBS-02 | Processing metrics (duration, row counts) | A04 §98 |
| NFR-OBS-03 | LLM call metrics (tokens, cost, cache hits) | A04 §98 |
| NFR-OBS-04 | Health check endpoints | A01 |

---

## 3. Constraints

| ID | Constraint | Source |
|----|------------|--------|
| CON-01 | Development uses synthetic data only | A01 §security |
| CON-02 | No confidential data to external LLM providers without explicit permission | A01 §security |
| CON-03 | AI cannot directly mutate business state | A03 §2.3 |
| CON-04 | Raw uploaded files must never be modified | A03 §2.2 |
| CON-05 | Versions once created cannot be modified | A01 §decisions |
| CON-06 | LLM is interpretation layer, not calculation engine | A04 §39 |

---

## 4. Assumptions

| ID | Assumption | Source |
|----|------------|--------|
| ASM-01 | Users have domain knowledge of reinsurance data | A02 §users |
| ASM-02 | Canonical schema is defined before processing | A03 §9 |
| ASM-03 | Treaty configuration exists for treaty-specific reconciliation | A04 §failure |
| ASM-04 | LLM provider API is available (fallback to no-LLM mode if not) | A04 §89 |
| ASM-05 | File formats conform to common conventions | A03 §4.1 |

---

## 5. Open Questions

| ID | Question | Impact | Resolution Required By |
|----|----------|--------|----------------------|
| OQ-01 | Which specific LLM provider(s) to support initially? | FR-LLM implementation | Phase 5 start |
| OQ-02 | What is the exact canonical schema for MVP? | FR-SCH configuration | Phase 1 start |
| OQ-03 | Are there specific regulatory requirements beyond audit trails? | NFR-COM scope | Phase 1 start |
| OQ-04 | What is the authentication/SSO strategy? | NFR-SEC implementation | Phase 1 start |
| OQ-05 | What is the deployment target (cloud provider, on-prem, hybrid)? | Infrastructure decisions | Phase 1 start |
| OQ-06 | What are the specific tolerance thresholds for financial reconciliation? | FR-REC configuration | Phase 3 start |
| OQ-07 | Which treaty types need immediate support? | FR-TRT scope | Phase 4 start |
