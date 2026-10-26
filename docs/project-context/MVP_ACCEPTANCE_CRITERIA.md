# MVP Acceptance Criteria
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved

---

## 1. Acceptance Test Structure

Each acceptance criterion follows the format:
- **Given:** Initial state/preconditions
- **When:** Action performed
- **Then:** Expected outcome
- **Evidence:** How to verify

---

## 2. Project Management Acceptance

### AC-PRJ-01: Create Project

**Given:** User is authenticated  
**When:** User creates a project with name "Q3 2026 Reconciliation"  
**Then:**
- Project is created with unique ID
- Project status is CREATED
- Project appears in project list
- Audit event logged with actor, timestamp, action

**Evidence:** API returns 201, project in list response, audit log entry

---

### AC-PRJ-02: List Projects

**Given:** User has created 3 projects  
**When:** User requests project list  
**Then:**
- All 3 projects returned
- Projects include id, name, status, created_at
- Projects ordered by created_at descending

**Evidence:** API returns 200 with array of 3 projects

---

## 3. File Ingestion Acceptance

### AC-ING-01: Upload CSV File

**Given:** User has a project  
**When:** User uploads "claims_mapping.csv" (10MB, 50K rows, 15 columns)  
**Then:**
- File stored with SHA-256 checksum
- SourceAsset created with status UPLOADED
- Original file preserved unchanged
- Asset appears in project assets

**Evidence:** API returns 201, checksum matches local calculation

---

### AC-ING-02: Upload Excel File

**Given:** User has a project  
**When:** User uploads "subledger.xlsx" with 3 sheets  
**Then:**
- File stored with checksum
- SourceAsset created
- Sheet names available in metadata

**Evidence:** API returns 201, metadata includes sheet names

---

### AC-ING-03: Detect File Format

**Given:** User uploads file without extension as "data_file"  
**When:** System processes upload  
**Then:**
- Format detected from magic bytes
- Correct parser selected
- Format recorded in asset metadata

**Evidence:** Asset metadata shows detected format

---

### AC-ING-04: Parse CSV Successfully

**Given:** User has uploaded valid CSV  
**When:** User triggers parsing  
**Then:**
- Job created with status PENDING
- Job completes with status SUCCEEDED
- SourceVersion created
- Parsed data stored as Parquet
- Row count matches source
- Column names extracted

**Evidence:** Job status SUCCEEDED, version row_count = source rows

---

### AC-ING-05: Handle Parse Errors Gracefully

**Given:** User uploads CSV with malformed rows  
**When:** System parses file  
**Then:**
- Valid rows parsed successfully
- Invalid rows recorded in errors
- Job completes (not fails)
- Error details include row numbers

**Evidence:** ParseResult includes errors array with row details

---

### AC-ING-06: Detect Structure

**Given:** CSV has 3 header rows before data  
**When:** System detects structure  
**Then:**
- header_row correctly identified
- data_start_row correctly identified
- Confidence score provided

**Evidence:** StructureDetection shows correct row numbers

---

## 4. Data Profiling Acceptance

### AC-PRO-01: Generate Column Statistics

**Given:** SourceVersion exists with 50K rows, 15 columns  
**When:** User requests profiling  
**Then:**
- Profile generated for all columns
- Each column has: type, null_count, distinct_count
- Numeric columns have min, max, mean, median
- String columns have length stats
- Profile completed in < 30 seconds

**Evidence:** DataProfile with complete column_profiles array

---

### AC-PRO-02: Detect Data Types

**Given:** CSV with mixed type columns  
**When:** System profiles data  
**Then:**
- Date columns detected as DATE
- Numeric columns detected as DECIMAL/INTEGER
- Text columns detected as STRING
- Boolean columns detected as BOOLEAN

**Evidence:** ColumnProfile.data_type matches expected

---

### AC-PRO-03: Extract Top Values

**Given:** Column with categorical values  
**When:** System profiles data  
**Then:**
- Top 10 values extracted with counts
- Values sorted by frequency descending

**Evidence:** ColumnProfile.top_values array

---

## 5. Mapping Acceptance

### AC-MAP-01: Generate Mapping Candidates

**Given:** Profile exists, canonical schema loaded  
**When:** User triggers candidate generation  
**Then:**
- Candidates generated for all source columns
- Each candidate has target_field and confidence
- Multiple candidates per source column ranked
- Generation completes in < 60 seconds

**Evidence:** CandidateMapping array with ranked candidates

---

### AC-MAP-02: Confidence Score Breakdown

**Given:** Candidate generated for "CLAIM_NO" → "claim_id"  
**When:** User views candidate  
**Then:**
- Total confidence score (0-1)
- Breakdown by evidence type
- Evidence includes: alias_match, name_similarity, type_compatibility
- Weights sum to total

**Evidence:** Confidence object with breakdown dict

---

### AC-MAP-03: Auto-Approval for High Confidence

**Given:** Candidate with confidence > 0.95 and clear evidence  
**When:** System evaluates candidate  
**Then:**
- auto_approve_eligible = true
- Status can be AUTO_APPROVED if enabled

**Evidence:** CandidateMapping.auto_approve_eligible flag

---

### AC-MAP-04: Manual Mapping Override

**Given:** Source column "CLM_REF" has no good candidates  
**When:** User creates manual mapping to "claim_id"  
**Then:**
- ApprovedMapping created with origin=MANUAL
- Confidence set based on manual creation rules
- Audit event logged

**Evidence:** ApprovedMapping with origin=MANUAL

---

### AC-MAP-05: Approve Mapping Candidate

**Given:** Candidate with confidence 0.75 in PROPOSED status  
**When:** User approves candidate  
**Then:**
- Status changes to APPROVED
- ApprovedMapping created
- Audit event logged with actor

**Evidence:** CandidateMapping.status = APPROVED

---

### AC-MAP-06: Reject Mapping Candidate

**Given:** Candidate in PROPOSED status  
**When:** User rejects with reason "Incorrect semantic match"  
**Then:**
- Status changes to REJECTED
- Reason recorded
- Audit event logged

**Evidence:** CandidateMapping.status = REJECTED

---

### AC-MAP-07: Finalize Mapping Set

**Given:** All required fields have approved mappings  
**When:** User finalizes mappings  
**Then:**
- ApprovedMappingSet created and versioned
- Coverage calculated (mapped fields / total fields)
- Ready for standardization

**Evidence:** ApprovedMappingSet with coverage > 0

---

## 6. Schema Template Acceptance

### AC-TPL-01: Create Template from Mappings

**Given:** User has finalized mappings for "q1_claims.csv"  
**When:** User creates template with name "Quarterly Claims Template"  
**Then:**
- Template created with unique ID
- Source signature extracted from file structure
- Mapping rules generated from approved mappings
- Template scope set (PROJECT or GLOBAL)
- Template status is ACTIVE

**Evidence:** API returns 201, template in list response

---

### AC-TPL-02: Find Matching Templates

**Given:** Template "Quarterly Claims Template" exists with 12 column patterns  
**When:** User uploads "q2_claims.csv" with similar structure (11 matching columns)  
**Then:**
- Template detected as potential match
- Match score calculated (11/12 = 0.92)
- Recommendation: APPLY

**Evidence:** /templates/match returns template with score > 0.9

---

### AC-TPL-03: Apply Template to New File

**Given:** "Quarterly Claims Template" matches new file with score 0.92  
**When:** User applies template  
**Then:**
- Mapping candidates generated for matching columns
- Confidence scores boosted by template rules
- Candidates marked with template origin
- Application tracked (template_application record)

**Evidence:** MappingSet created with boosted confidence scores

---

### AC-TPL-04: Template Does Not Match

**Given:** Template "Quarterly Claims Template" for claims files  
**When:** User uploads "vendor_invoices.csv" with different structure  
**Then:**
- Template match score < 0.5
- Recommendation: SKIP
- Template not suggested

**Evidence:** /templates/match returns empty or low-score results

---

### AC-TPL-05: Project-Scoped Template Isolation

**Given:** Template created in Project A  
**When:** User lists templates in Project B  
**Then:**
- Project A template not visible
- Only GLOBAL templates and Project B templates shown

**Evidence:** Template list filtered by project_id

---

## 7. Standardization Acceptance

### AC-STD-01: Transform Data Successfully

**Given:** Approved mappings cover required fields  
**When:** User triggers standardization  
**Then:**
- Job created and completes
- ClaimsMapping created with canonical schema
- All mapped fields transformed
- Unmapped source columns preserved in metadata
- Output stored as Parquet

**Evidence:** ClaimsMapping with valid_rows = expected

---

### AC-STD-02: Type Coercion

**Given:** Source "amount" is string "1,234.56"  
**When:** Mapping to DECIMAL field  
**Then:**
- Value transformed to Decimal(1234.56)
- No data loss

**Evidence:** Canonical data has correct numeric value

---

### AC-STD-03: Date Parsing

**Given:** Source dates in format "15-Aug-2026"  
**When:** Mapping to DATE field  
**Then:**
- Dates parsed to ISO format (2026-08-15)
- Invalid dates recorded as errors

**Evidence:** Canonical dates in ISO format

---

### AC-STD-04: Lineage Preservation

**Given:** Standardization completed  
**When:** User queries lineage for canonical row 1000  
**Then:**
- LineageRecord shows source_asset_id
- LineageRecord shows source_version_id
- LineageRecord shows source_row_number
- Full chain traceable to original file

**Evidence:** LineageRecord with complete source references

---

## 7. Reconciliation Acceptance

### AC-REC-01: Create Reconciliation Run

**Given:** ClaimsMapping and Subledger exist  
**When:** User creates reconciliation with configuration  
**Then:**
- ReconciliationRun created with status QUEUED
- Configuration recorded (keys, measure, thresholds)
- Run ID returned immediately

**Evidence:** API returns 201 with run_id

---

### AC-REC-02: Execute Reconciliation

**Given:** Reconciliation run created  
**When:** Job executes  
**Then:**
- Status progresses: QUEUED → RUNNING → SUCCEEDED
- Pivot created for both datasets
- Full outer join performed
- Variance calculated for all keys
- Summary populated

**Evidence:** Run status SUCCEEDED, summary populated

---

### AC-REC-03: Variance Calculation - Match

**Given:** Reported = 10000, Subledger = 10000  
**When:** Variance calculated  
**Then:**
- absolute_variance = 0
- percentage_variance = 0
- status = MATCH

**Evidence:** VarianceRecord with status MATCH

---

### AC-REC-04: Variance Calculation - Within Tolerance

**Given:** Reported = 10000, Subledger = 10050, threshold = 100  
**When:** Variance calculated with absolute threshold  
**Then:**
- absolute_variance = -50
- within_absolute_threshold = true
- status = WITHIN_TOLERANCE

**Evidence:** VarianceRecord with status WITHIN_TOLERANCE

---

### AC-REC-05: Variance Calculation - Unreconciled

**Given:** Reported = 10000, Subledger = 11000, threshold = 100  
**When:** Variance calculated  
**Then:**
- absolute_variance = -1000
- within_absolute_threshold = false
- status = UNRECONCILED

**Evidence:** VarianceRecord with status UNRECONCILED

---

### AC-REC-06: Percentage Variance

**Given:** Reported = 100000, Subledger = 100500, percentage_threshold = 0.1%  
**When:** Variance calculated  
**Then:**
- percentage_variance = 0.5%
- within_percentage_threshold = false

**Evidence:** VarianceRecord with correct percentage

---

### AC-REC-07: Zero Denominator Handling

**Given:** Reported = 100, Subledger = 0  
**When:** Percentage variance calculated  
**Then:**
- No division by zero error
- percentage_variance = null or handled status
- absolute_variance = 100

**Evidence:** No error, sensible handling

---

### AC-REC-08: Missing Key - Reported Only

**Given:** Key "CLM-001" in Claims Mapping, not in Subledger  
**When:** Full outer join  
**Then:**
- VarianceRecord created for key
- subledger_value = 0 or null
- Diagnostic D003 (Missing records) triggered

**Evidence:** Variance record with subledger side null/zero

---

### AC-REC-09: Missing Key - Subledger Only

**Given:** Key "CLM-999" in Subledger, not in Claims Mapping  
**When:** Full outer join  
**Then:**
- VarianceRecord created
- reported_value = 0 or null
- Diagnostic D004 (Extra records) triggered

**Evidence:** Variance record with reported side null/zero

---

## 8. Diagnostics Acceptance

### AC-DIA-01: Run Diagnostic Checks

**Given:** Reconciliation completed with exceptions  
**When:** Diagnostics executed  
**Then:**
- All enabled checks run
- Findings created for each detected issue
- Findings include severity, evidence, message

**Evidence:** DiagnosticFinding array

---

### AC-DIA-02: Row Count Difference (D001)

**Given:** Claims Mapping = 1000 rows, Subledger = 950 rows  
**When:** D001 check runs  
**Then:**
- Finding created with category STRUCTURAL
- metrics includes both counts and difference

**Evidence:** Finding with check_id = D001

---

### AC-DIA-03: Duplicate Keys (D005)

**Given:** Claims Mapping has key "CLM-001" appearing 3 times  
**When:** D005 check runs  
**Then:**
- Finding created
- Evidence includes duplicate key values
- Severity based on count

**Evidence:** Finding with duplicate details

---

### AC-DIA-04: Amount Total Mismatch (D018)

**Given:** SUM(Claims Mapping.amount) ≠ SUM(Subledger.amount)  
**When:** D018 check runs  
**Then:**
- Finding created with totals and difference
- Severity based on variance magnitude

**Evidence:** Finding with total amounts

---

## 9. Reporting Acceptance

### AC-RPT-01: Generate Summary Report

**Given:** Reconciliation completed  
**When:** User requests report  
**Then:**
- Report includes executive summary
- Report includes reconciliation metrics
- Report includes exception summary
- Report generated in < 30 seconds

**Evidence:** Report JSON with all sections

---

### AC-RPT-02: Exception Detail Report

**Given:** Reconciliation has 50 exceptions  
**When:** User requests exception report  
**Then:**
- All exceptions listed with details
- Each exception has: key, reported, subledger, variance
- Diagnostic findings linked

**Evidence:** Report with 50 exception entries

---

## 10. Lineage Acceptance

### AC-LIN-01: Trace Exception to Source

**Given:** Exception for key "CLM-12345"  
**When:** User queries lineage  
**Then:**
- Path from exception to variance record
- Path from variance to canonical row
- Path from canonical to source row
- Source file name and row number visible

**Evidence:** Complete lineage chain

---

## 11. Audit Acceptance

### AC-AUD-01: Log All State Changes

**Given:** User performs various operations  
**When:** Audit log queried  
**Then:**
- Project creation logged
- Asset upload logged
- Mapping approval/rejection logged
- Reconciliation execution logged
- Each event has actor, timestamp, before/after

**Evidence:** AuditEvent records for all operations

---

## 12. Golden Dataset Specification

### 12.1 Claims Mapping Test File

**File:** `golden_claims_mapping.csv`  
**Rows:** 1,000  
**Columns:** 12

| Column | Type | Notes |
|--------|------|-------|
| CLAIM_NO | String | Unique identifier CLM-00001 to CLM-01000 |
| POL_REF | String | Policy reference |
| TXN_DATE | Date | YYYY-MM-DD format |
| POST_DATE | Date | YYYY-MM-DD format |
| GROSS_AMT | Decimal | Gross amount |
| COMMISSION | Decimal | Commission amount |
| NET_AMT | Decimal | Net amount (GROSS - COMMISSION) |
| CURRENCY | String | USD, EUR, GBP |
| STATUS | String | PAID, PENDING, REJECTED |
| TXN_TYPE | String | PREMIUM, CLAIM, ADJUSTMENT |
| ACCOUNT | String | Account code |
| PERIOD | String | 2026-Q3 |

**Test Scenarios Embedded:**
- 50 records with intentional mapping ambiguity
- 10 records with date format variations
- 5 records with null values in non-required fields

### 12.2 Subledger Test File

**File:** `golden_subledger.csv`  
**Rows:** 980 (20 fewer than Claims Mapping)  
**Columns:** 10

| Column | Type | Notes |
|--------|------|-------|
| claim_id | String | Same IDs as Claims Mapping (mostly) |
| policy_id | String | Same as POL_REF |
| transaction_date | Date | ISO format |
| amount | Decimal | Net amount |
| currency | String | Currency code |
| status | String | Different casing (paid vs PAID) |
| account_code | String | Account |
| period | String | Reporting period |
| source_system | String | GL, AP |
| posting_date | Date | ISO format |

**Test Scenarios Embedded:**
- 20 missing records (not in Subledger)
- 10 extra records (not in Claims Mapping)
- 30 records with amount differences (various magnitudes)
- 15 records with rounding differences (< $1)
- 10 records with timing differences (date mismatch)
- 5 records with status differences (casing)

### 12.3 Expected Reconciliation Results

**Summary:**
- Total groups: 990 (980 common + 20 missing + 10 extra - 20 overlap)
- Matched: 890
- Within tolerance (< $100): 35
- Unreconciled: 65

**Expected Diagnostics:**
- D001: Row count difference (1000 vs 980)
- D003: 20 missing records identified
- D004: 10 extra records identified  
- D015: Status distribution mismatch (casing)
- D018: Amount total mismatch
- D025: 15 rounding differences

### 12.4 Expected Mappings

| Source Column | Expected Target | Expected Confidence |
|---------------|-----------------|---------------------|
| CLAIM_NO | claim_id | > 0.95 |
| POL_REF | policy_id | > 0.90 |
| TXN_DATE | transaction_date | > 0.90 |
| POST_DATE | posting_date | > 0.90 |
| GROSS_AMT | gross_amount | > 0.90 |
| COMMISSION | commission | > 0.95 |
| NET_AMT | net_amount | > 0.90 |
| CURRENCY | currency | > 0.95 |
| STATUS | status | > 0.95 |
| TXN_TYPE | transaction_type | > 0.85 |
| ACCOUNT | account | > 0.85 |
| PERIOD | reporting_period | > 0.80 |

---

## 13. Test Execution Checklist

### 13.1 Pre-Implementation

- [ ] Golden dataset files created
- [ ] Expected results documented
- [ ] Test environment configured

### 13.2 During Implementation

- [ ] Unit tests written alongside code
- [ ] Integration tests for API endpoints
- [ ] Golden dataset automated tests

### 13.3 MVP Completion

- [ ] All acceptance criteria verified
- [ ] Golden dataset passes 100%
- [ ] No critical bugs open
- [ ] Documentation complete
