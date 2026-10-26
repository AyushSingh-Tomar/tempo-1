# MVP Scope Definition
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved

---

## 1. MVP Objective

Deliver the smallest end-to-end system that proves the core product value:

> Upload a file → Inspect and profile it → Propose mappings → Review uncertain mappings → Produce standardized output → Reconcile against a subledger → Generate an evidence-backed report

---

## 2. MVP User Story

**As a** Reinsurance Analyst  
**I want to** upload Claims Mapping and Subledger files, have the system propose field mappings, review uncertain mappings, and reconcile the data  
**So that** I can identify discrepancies between reported and booked values with full evidence trail

---

## 3. MVP Feature Matrix

### 3.1 In Scope (Must Have)

| Feature | Description | Requirements |
|---------|-------------|--------------|
| **Project Management** | Create/list/view projects | FR-PRJ-01, FR-PRJ-02 |
| **File Upload** | Upload files with checksum validation | FR-ING-01, FR-ING-04, FR-ING-05 |
| **Format Detection** | Auto-detect CSV, XLSX, JSON, Parquet | FR-ING-02 |
| **File Parsing** | Parse structured formats to Parquet | FR-ING-03 |
| **Structure Detection** | Detect header row and data region | FR-STR-01, FR-STR-03 |
| **Data Profiling** | Generate column statistics and patterns | FR-PRO-01 through FR-PRO-06 |
| **Canonical Schema** | Load and validate custom schema | FR-SCH-01, FR-SCH-04, FR-SCH-06 |
| **Mapping Candidates** | Generate candidates with confidence scores | FR-MAP-01 through FR-MAP-06 |
| **Confidence Scoring** | Weighted scoring with evidence breakdown | FR-CON-01, FR-CON-04 |
| **Manual Mapping** | Override/create mappings manually | FR-MAP-08 |
| **Mapping Approval** | Approve/reject mapping candidates | FR-REV-01 through FR-REV-04 |
| **Schema Templates** | Save/apply reusable mapping templates | FR-TPL-01 through FR-TPL-05 |
| **Standardization** | Transform data to canonical schema | FR-STD-01 through FR-STD-03, FR-STD-05, FR-STD-06 |
| **Subledger Ingestion** | Ingest and standardize subledger files | FR-SUB-01, FR-SUB-02, FR-SUB-04 |
| **Basic Pivot** | Aggregate by configurable dimensions | FR-PIV-01, FR-PIV-02, FR-PIV-04 |
| **Reconciliation Engine** | Compare with variance calculation | FR-REC-01 through FR-REC-07 |
| **Variance Thresholds** | Absolute/percentage with AND/OR | FR-REC-04 through FR-REC-06 |
| **Deterministic Diagnostics** | Core diagnostic checks (20 of 33) | FR-DIA-01 through FR-DIA-05 |
| **Finding Classification** | Root-cause taxonomy | FR-DIA-07 |
| **Basic Reporting** | Summary and exception reports | FR-RPT-01 through FR-RPT-03 |
| **Lineage** | Source-to-output traceability | FR-LIN-01 through FR-LIN-05 |
| **Versioning** | Immutable artifact versions | FR-VER-01 through FR-VER-03 |
| **Audit Trail** | Log all state changes | NFR-SEC-06 |
| **Job Processing** | Async processing with status | Per OQ-10 |
| **Basic UI** | Project list, upload, mapping review, reconciliation results | Per A02, A07 |

### 3.2 Stretch Goals (Should Have if Time Permits)

| Feature | Description | Requirements |
|---------|-------------|--------------|
| **Relationship Inference** | Detect arithmetic/referential relationships | FR-REL-01 through FR-REL-04 |
| **Financial Relationships** | Gross - Commission ≈ Net detection | FR-REL-05 |
| **One-to-Many Reconciliation** | Aggregate before comparison | FR-REC-08 |
| **LLM Mismatch Classification** | AI-assisted exception classification | FR-LLM-01 |
| **Export Formats** | CSV, XLSX export | FR-RPT-06 (partial) |
| **Run Comparison** | Compare reconciliation runs | FR-RPT-07, FR-VER-05 |
| **Historical Mapping** | ~~Project-scoped mapping reuse~~ — removed (no learning from manual mappings) | FR-MAP-09 |

### 3.3 Out of Scope (Deferred to Post-MVP)

| Feature | Reason for Deferral | Requirements |
|---------|---------------------|--------------|
| **PDF Parsing** | High complexity, low MVP value | FR-ING-07 |
| **Multi-row Headers** | Edge case, manual workaround available | FR-STR-02 |
| **Semantic Embeddings** | Requires ML infrastructure | FR-MAP-04 |
| **Subledger Unification** | Complex, single subledger sufficient for MVP | FR-SUB-03 |
| **Pivot Inference** | Explicit configuration sufficient | FR-PIV-05 |
| **User-defined Checks** | Built-in checks sufficient | FR-DIA-08 |
| **All 33 Diagnostics** | Core 20 sufficient for MVP | Partial FR-DIA |
| **Full LLM Integration** | No-LLM mode proves core value | FR-LLM-02 through FR-LLM-10 |
| **Treaty Management** | Reconciliation works without treaty rules | FR-TRT-* |
| **What-if Scenarios** | Requires treaty foundation | FR-TRT-10, FR-TRT-11 |
| **Investigation Interface** | Manual review sufficient | FR-LLM-05 |
| **PDF/HTML Reports** | JSON/CSV sufficient | FR-RPT-06 (partial) |
| **Multi-tenancy** | Single-tenant MVP | Per OQ-11 |
| **SSO/OIDC** | Local auth sufficient for MVP | Per OQ-02 |
| **Mobile Optimization** | Desktop-first | Per OQ-13 |

---

## 4. MVP File Format Support

| Format | Support Level | Notes |
|--------|---------------|-------|
| CSV | Full | Primary format |
| TSV | Full | Variant of CSV |
| XLSX | Full | Modern Excel |
| XLS | Full | Legacy Excel |
| JSON | Full | Structured JSON |
| JSONL | Full | Line-delimited JSON |
| Parquet | Full | Columnar format |
| XML | Deferred | Post-MVP |
| PDF | Deferred | Post-MVP |
| HTML | Deferred | Post-MVP |
| EDI | Deferred | Post-MVP |
| SAS | Deferred | Post-MVP |

---

## 5. MVP Diagnostic Checks

### 5.1 Included (20 checks)

**Structural (5):**
- D001: Row count difference
- D002: Distinct key difference
- D005: Duplicate keys
- D006: Null critical keys
- D008: Data type mismatch

**Completeness (4):**
- D003: Missing records
- D004: Extra records
- D011: Month distribution mismatch
- D013: Year distribution mismatch

**Integrity (5):**
- D007: Null financial values
- D009: Invalid dates
- D010: Date range mismatch
- D023: Referential integrity failure
- D027: Duplicate source load

**Value (4):**
- D018: Amount total mismatch
- D020: Control total mismatch
- D024: Sign mismatch
- D025: Rounding difference

**Distribution (2):**
- D015: Status distribution mismatch
- D016: Account distribution mismatch

### 5.2 Deferred (13 checks)

- D012: Quarter distribution mismatch
- D014: Currency mismatch
- D017: Claim type distribution mismatch
- D019: Debit/credit mismatch
- D021: Field-level mismatch
- D022: Row hash mismatch
- D026: Percentage/calculation mismatch
- D028: Aggregation mismatch
- D029: Missing partition
- D030: Unexpected new code
- D031: Retired code still present
- D032: Timing/cutoff pattern
- D033: Adjustment/reversal pattern

---

## 6. MVP Canonical Schema (Minimal)

```yaml
schema:
  id: "mvp-claims-v1"
  name: "MVP Claims Mapping Schema"
  version: "1.0.0"
  standard: CUSTOM
  
  fields:
    # Identifiers
    - name: claim_id
      type: STRING
      required: true
      aliases: ["claim_number", "claim_no", "clm_id", "claim_ref"]
      category: IDENTIFIER
      
    - name: policy_id
      type: STRING
      required: false
      aliases: ["policy_number", "policy_no", "pol_id"]
      category: IDENTIFIER
      
    - name: transaction_id
      type: STRING
      required: false
      aliases: ["txn_id", "trans_id"]
      category: IDENTIFIER
    
    # Dates
    - name: transaction_date
      type: DATE
      required: false
      aliases: ["txn_date", "trans_date", "date"]
      category: DATE
      
    - name: posting_date
      type: DATE
      required: false
      aliases: ["post_date", "accounting_date"]
      category: DATE
      
    - name: reporting_period
      type: STRING
      required: false
      aliases: ["period", "report_period"]
      category: DATE
    
    # Amounts
    - name: gross_amount
      type: DECIMAL
      required: false
      aliases: ["gross", "gross_premium", "gross_amt"]
      category: AMOUNT
      
    - name: net_amount
      type: DECIMAL
      required: false
      aliases: ["net", "net_premium", "net_amt"]
      category: AMOUNT
      
    - name: commission
      type: DECIMAL
      required: false
      aliases: ["comm", "commission_amt"]
      category: AMOUNT
      
    - name: claim_amount
      type: DECIMAL
      required: false
      aliases: ["amount", "amt", "claim_amt"]
      category: AMOUNT
    
    # Classification
    - name: currency
      type: STRING
      required: false
      aliases: ["ccy", "curr"]
      category: CLASSIFICATION
      
    - name: status
      type: STRING
      required: false
      aliases: ["claim_status", "stat"]
      category: CLASSIFICATION
      
    - name: transaction_type
      type: STRING
      required: false
      aliases: ["txn_type", "type"]
      category: CLASSIFICATION
      
    - name: account
      type: STRING
      required: false
      aliases: ["account_code", "acct"]
      category: CLASSIFICATION
```

---

## 7. MVP API Endpoints

### 7.1 Core Endpoints

```
# Projects
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}

# Assets
POST   /api/v1/projects/{id}/assets
GET    /api/v1/projects/{id}/assets
GET    /api/v1/assets/{id}
DELETE /api/v1/assets/{id}

# Versions
GET    /api/v1/assets/{id}/versions
GET    /api/v1/versions/{id}
GET    /api/v1/versions/{id}/profile

# Mappings
POST   /api/v1/versions/{id}/mappings/generate
GET    /api/v1/versions/{id}/mappings/candidates
POST   /api/v1/mappings/{id}/approve
POST   /api/v1/mappings/{id}/reject
POST   /api/v1/versions/{id}/mappings/manual
POST   /api/v1/versions/{id}/mappings/finalize

# Standardization
POST   /api/v1/versions/{id}/standardize
GET    /api/v1/claims-mappings/{id}
GET    /api/v1/claims-mappings/{id}/data

# Subledgers
POST   /api/v1/projects/{id}/subledgers
GET    /api/v1/subledgers/{id}

# Reconciliation
POST   /api/v1/reconciliations
GET    /api/v1/reconciliations/{id}
GET    /api/v1/reconciliations/{id}/variances
GET    /api/v1/reconciliations/{id}/diagnostics
POST   /api/v1/reconciliations/{id}/report

# Jobs
GET    /api/v1/jobs/{id}
GET    /api/v1/projects/{id}/jobs

# Schemas
GET    /api/v1/schemas
GET    /api/v1/schemas/{id}

# Lineage
GET    /api/v1/lineage/{artifact_type}/{artifact_id}

# Health
GET    /health
```

### 7.2 Deferred Endpoints

```
# Relationships (stretch)
GET    /api/v1/versions/{id}/relationships

# LLM (stretch)
POST   /api/v1/reconciliations/{id}/classify
POST   /api/v1/reconciliations/{id}/investigate

# Treaty (post-MVP)
*      /api/v1/treaties/*

# Run comparison (stretch)
GET    /api/v1/reconciliations/compare
```

---

## 8. MVP UI Screens

### 8.1 Required Screens

| Screen | Purpose | Priority |
|--------|---------|----------|
| **Project List** | View/create projects | P0 |
| **Project Detail** | View project with assets | P0 |
| **File Upload** | Upload with progress | P0 |
| **Asset Detail** | View parsed structure, profile | P0 |
| **Mapping Review** | Review/approve candidates | P0 |
| **Claims Mapping Detail** | View standardized data | P0 |
| **Reconciliation Create** | Configure and start reconciliation | P0 |
| **Reconciliation Results** | Summary, variances, diagnostics | P0 |
| **Variance Detail** | Individual variance with evidence | P0 |
| **Report View/Download** | View and export report | P0 |

### 8.2 Deferred Screens

| Screen | Reason |
|--------|--------|
| Dashboard | Analytics, not core workflow |
| User Management | Single-user MVP |
| Settings | Minimal configuration |
| Treaty Management | Post-MVP feature |
| Investigation | Post-MVP LLM feature |
| Historical Comparison | Stretch goal |

---

## 9. MVP Non-Functional Requirements

### 9.1 Required

| Requirement | Target | Notes |
|-------------|--------|-------|
| File size | Up to 100MB | Larger files post-MVP |
| Row count | Up to 1M rows | Per reconciliation |
| Response time | < 2s for UI interactions | Excluding jobs |
| Job status | Real-time updates | WebSocket or polling |
| Concurrent jobs | 3 per project | Queue excess |
| Uptime | Development SLA | No production SLA |

### 9.2 Deferred

| Requirement | Reason |
|-------------|--------|
| 500MB+ files | Infrastructure complexity |
| 5M+ rows | Performance optimization |
| Horizontal scaling | Single-node MVP |
| Rate limiting | Single-user MVP |
| Caching layer | Premature optimization |

---

## 10. MVP Success Criteria

### 10.1 Functional Acceptance

- [ ] User can create a project
- [ ] User can upload CSV and Excel files
- [ ] System detects file format and structure
- [ ] System generates data profile with statistics
- [ ] System generates mapping candidates with confidence
- [ ] User can approve/reject mapping candidates
- [ ] User can create manual mappings
- [ ] System produces standardized Claims Mapping
- [ ] User can upload subledger file
- [ ] System reconciles Claims Mapping vs Subledger
- [ ] System calculates variance with thresholds
- [ ] System runs diagnostic checks
- [ ] System generates reconciliation report
- [ ] User can trace any value to source
- [ ] All state changes are audited

### 10.2 Quality Acceptance

- [ ] Unit test coverage ≥ 80%
- [ ] Integration tests for critical paths
- [ ] No critical security vulnerabilities
- [ ] API documented in OpenAPI
- [ ] Error messages are actionable
- [ ] UI is functional on desktop browsers

### 10.3 Golden Dataset Validation

- [ ] Synthetic dataset with known mappings
- [ ] Expected reconciliation results defined
- [ ] All diagnostic findings verified
- [ ] Lineage verified end-to-end

---

## 11. MVP Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1-3 | Foundation | Project setup, core models, storage, basic API |
| 4-5 | Ingestion | File adapters, parsing, structure detection |
| 6-7 | Profiling & Mapping | Profiler, candidate generation, scoring |
| 8-9 | Standardization | Transformation engine, Claims Mapping |
| 10-12 | Reconciliation | Pivot, variance, diagnostics |
| 13-15 | Frontend | Core UI screens |
| 16-17 | Integration | End-to-end testing, golden dataset |
| 18 | Polish | Bug fixes, documentation |

**Total: ~18 weeks for MVP**

---

## 12. Post-MVP Roadmap

### Phase 2: Enhanced Reconciliation
- Subledger unification
- One-to-many reconciliation
- Full 33 diagnostic checks
- Run comparison

### Phase 3: AI Integration
- LLM mismatch classification
- Cluster interpretation
- Investigation interface

### Phase 4: Treaty Management
- Treaty discovery
- State versioning
- What-if scenarios

### Phase 5: Enterprise Features
- SSO/OIDC integration
- Multi-tenancy
- Advanced reporting
- Performance optimization
