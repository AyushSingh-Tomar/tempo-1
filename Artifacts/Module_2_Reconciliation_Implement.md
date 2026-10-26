# Reconciliation Module — Implementation Specification & README

> **Module:** Reconciliation
> **Platform:** Bordereaux / Claims Intelligence Platform
> **Implementation style:** Python-first, deterministic by default, targeted LLM reasoning only where ambiguity remains
> **Primary upstream dependency:** Module 1 — AI-Aided Mapping & Relationship Inference
> **Status:** Implementation-ready specification
> **Version:** 1.0

---

# 1. Module Overview & Responsibilities

## 1.1 Purpose

The Reconciliation Module compares the standardized **reported/Claims Mapping view** produced by Module 1 against one or more **Subledger sources**, determines whether the two representations reconcile, diagnoses differences, and produces an auditable reconciliation report.

Module 1 already establishes the platform's core principle:

> deterministic processing first, targeted AI reasoning second, with evidence and human review for ambiguous decisions. 

The Reconciliation Module extends that principle to financial reconciliation.

The module must answer four different questions:

1. **Do the values reconcile?**
2. **Where exactly do they differ?**
3. **What deterministic evidence explains the difference?**
4. **If deterministic checks cannot explain it, what is the most likely reason and what should a human investigate?**

The system must **not** reduce reconciliation to:

```text
PASS / FAIL
```

Instead, the output should distinguish:

```text
MATCH
VALID DIFFERENCE
INVESTIGATE
DATA ERROR
UNRESOLVED
```

This distinction is important because a technical difference is not automatically a business error. For example, different transaction dates, gross-vs-net definitions, adjustments, aggregation levels, or legitimate timing differences can produce numerical differences without either system being incorrect.

---

## 1.2 Primary Responsibilities

The module owns:

* Subledger ingestion
* Multi-subledger normalization
* Canonical subledger generation
* Source lineage preservation
* Schema inference
* Subledger relationship inference
* User-defined relationships
* Claims Mapping ↔ Subledger relationships
* Pivot/aggregation generation
* TA-report-aligned aggregation
* Reconciliation-key resolution
* Record-level reconciliation
* Aggregate reconciliation
* Control-total reconciliation
* Variance computation
* Permissible variance evaluation
* Treaty-specific rule evaluation
* Iterative adjustments
* Retro amount handling
* Reconciliation versioning
* Deterministic diagnostics
* LLM-assisted diagnostics
* AI investigation interface
* Structured exception generation
* Reconciliation reporting
* Audit and lineage

It does **not** own:

* Original raw ingestion performed by Module 1
* Claims Mapping creation itself
* General source-file standardization already completed by Module 1
* User authentication
* Enterprise identity management
* Final document delivery infrastructure

---

# 2. Design Principles

## 2.1 Deterministic First, AI Second

The core execution path is:

```text
Input
  ↓
Python standardization
  ↓
Python profiling
  ↓
Python relationships
  ↓
Python aggregation
  ↓
Python reconciliation
  ↓
Python diagnostics
  ↓
Are unresolved patterns remaining?
  │
  ├── No → Report
  │
  └── Yes
        ↓
      LLM
        ↓
   Structured JSON
        ↓
   Python validation
        ↓
      Report
```

The LLM should never be used for:

* arithmetic
* aggregation
* joins
* sorting
* duplicate detection
* row counting
* variance calculation
* threshold evaluation
* schema validation
* date parsing
* numerical statistics
* hash generation
* lineage resolution

These are deterministic operations.

The platform's existing reconciliation guidance similarly places structural, completeness, integrity, value, and distribution checks in Python, while using AI to interpret patterns rather than replace the underlying calculations. 

---

## 2.2 Raw Data Is Immutable

Never modify an uploaded subledger.

Use:

```text
RAW SUBLEDGER
      ↓
PARSED SUBLEDGER
      ↓
NORMALIZED SUBLEDGER
      ↓
CANONICAL SUBLEDGER
      ↓
ADJUSTED SUBLEDGER VIEW
      ↓
RECONCILIATION
```

Every derived artifact references the source version from which it was generated.

---

## 2.3 AI Cannot Directly Mutate Business State

The LLM may produce:

```text
recommended relationship
recommended mismatch category
recommended root cause
recommended investigation
```

It may not directly:

* modify the subledger
* approve a financial adjustment
* change a reconciliation threshold
* alter treaty rules
* mark a financial exception as resolved
* change a mapping
* overwrite reconciliation history

The execution pattern must be:

```text
LLM Proposal
    ↓
Pydantic / JSON Schema Validation
    ↓
Deterministic Evidence Validation
    ↓
Confidence / Policy Gate
    ↓
Persist as Recommendation
    ↓
Human approval where required
```

This follows the same guardrail philosophy already established in Module 1. 

---

## 2.4 Evidence Is Mandatory

Every reconciliation decision must be traceable to:

* source artifact
* source version
* source row
* standardized row
* relationship rule
* aggregation definition
* treaty rule
* adjustment
* variance calculation
* threshold
* diagnostic check
* LLM decision, if used

---

## 2.5 Reconciliation Is Versioned

A reconciliation run is immutable.

For example:

```text
Reconciliation RCN-001

Run v1
  Subledger v1
  Claims Mapping v4
  Treaty Config v2

Run v2
  Subledger v2
  Claims Mapping v4
  Treaty Config v2
  Retro Adjustment v1

Run v3
  Subledger v3
  Claims Mapping v5
  Treaty Config v3
```

Never overwrite previous runs.

---

# 3. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │      USER / TA       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Reconciliation API   │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
      Claims Mapping         Subledger Manager       Treaty Config
      from Module 1          1..N Sources            / Rules
              │                     │                     │
              │                     ▼                     │
              │             ┌──────────────┐             │
              │             │ File Adapters│             │
              │             └──────┬───────┘             │
              │                    ▼                     │
              │             ┌──────────────┐             │
              │             │Standardizer  │             │
              │             └──────┬───────┘             │
              │                    ▼                     │
              │          ┌────────────────────┐           │
              │          │ Unified Subledger  │           │
              │          └─────────┬──────────┘           │
              │                    │                      │
              └────────────┬───────┴──────────────┬───────┘
                           ▼                      ▼
                 Relationship Engine       Pivot Engine
                           │                      │
                           └──────────┬───────────┘
                                      ▼
                           ┌────────────────────┐
                           │ Reconciliation     │
                           │ Engine             │
                           └─────────┬──────────┘
                                     ▼
                           ┌────────────────────┐
                           │ Deterministic      │
                           │ Diagnostics        │
                           └─────────┬──────────┘
                                     │
                              unresolved?
                              /          \
                            NO            YES
                            │              │
                            │              ▼
                            │        ┌────────────┐
                            │        │ LLM Triage │
                            │        └─────┬──────┘
                            │              │
                            └──────┬───────┘
                                   ▼
                          ┌────────────────────┐
                          │ Findings /         │
                          │ Exceptions         │
                          └─────────┬──────────┘
                                    ▼
                          ┌────────────────────┐
                          │ Reconciliation     │
                          │ Report             │
                          └────────────────────┘
```

---

# 4. Core Components

## 4.1 Subledger Ingestion Service

Responsibilities:

* accept one or many files
* identify format
* invoke registered parser
* extract logical tables
* preserve source metadata
* generate file checksum
* create source version

Supported initial formats:

```text
CSV
TSV
XLSX
XLS
JSON
JSONL
XML
PDF
TXT
Parquet
HTML
EDI
SAS
Database extracts
```

Use the same adapter architecture established by Module 1 rather than hardcoding file extensions. 

---

## 4.2 Subledger Standardization Service

Converts heterogeneous subledgers into the canonical schema.

Example:

```text
Subledger A
  CLAIM_NO
  POST_DT
  AMT

Subledger B
  Claim_ID
  Accounting_Date
  Transaction_Amount

Subledger C
  CLM_REF
  GL_DATE
  VALUE
```

becomes:

```text
claim_id
accounting_date
transaction_amount
...
```

---

## 4.3 Unified Subledger Service

Combines all standardized subledgers.

```text
Subledger A ─┐
Subledger B ─┼──> Canonical Subledger
Subledger C ─┘
```

Every row retains:

```text
source_asset_id
source_version_id
source_file_name
source_sheet
source_row_number
source_record_id
ingestion_run_id
standardization_run_id
```

---

## 4.4 Relationship Engine

Handles:

### AI/deterministic inferred relationships

* key relationships
* composite keys
* one-to-one
* one-to-many
* many-to-one
* referential relationships
* arithmetic relationships
* ratio relationships
* temporal relationships
* hierarchical relationships
* conditional relationships

### User-defined relationships

* intra-subledger
* subledger ↔ Claims Mapping
* subledger ↔ reference data
* subledger ↔ treaty dimensions

---

## 4.5 Pivot Engine

Creates reporting-aligned aggregates.

The pivot layer must represent the **business reporting grain**, not merely reproduce the physical spreadsheet layout.

Module 1 already establishes that the finalized Claims Mapping and standardized dataset feed a pivot/aggregation artifact. 

---

## 4.6 Reconciliation Engine

Compares:

```text
Reported / Claims Mapping
          VS
Unified Subledger
```

at one or multiple grains.

---

## 4.7 Diagnostic Engine

Runs:

1. deterministic checks
2. pattern aggregation
3. LLM-assisted interpretation only when needed

---

## 4.8 Report Engine

Produces:

* executive summary
* reconciliation summary
* treaty breakdown
* variance analysis
* unmatched records
* diagnostics
* likely root causes
* evidence
* assumptions
* remediation recommendations
* lineage

---

# 5. Canonical Data Model

## 5.1 Source Artifact

```json
{
  "asset_id": "asset_sl_001",
  "version_id": "asset_sl_001_v3",
  "logical_role": "SUBLEDGER",
  "filename": "subledger_2026.xlsx",
  "format": "xlsx",
  "checksum_sha256": "...",
  "uploaded_at": "2026-09-30T10:00:00Z",
  "row_count": 4511,
  "status": "STANDARDIZED"
}
```

---

# 6. Unified Subledger Schema

The schema must be configurable because different organizations and treaties can require different fields.

A recommended base schema:

| Field                     | Type    |    Required | Description                 |
| ------------------------- | ------- | ----------: | --------------------------- |
| `record_id`               | string  |         Yes | Canonical record identifier |
| `claim_id`                | string  | Conditional | Claim identifier            |
| `policy_id`               | string  | Conditional | Policy identifier           |
| `treaty_id`               | string  | Conditional | Treaty identifier           |
| `account_id`              | string  | Conditional | Accounting account          |
| `transaction_id`          | string  | Conditional | Transaction identifier      |
| `transaction_type`        | string  |          No | Posting type                |
| `transaction_date`        | date    |          No | Business transaction date   |
| `posting_date`            | date    |         Yes | Accounting posting date     |
| `reporting_period`        | string  |         Yes | Canonical reporting period  |
| `currency`                | string  |         Yes | Currency                    |
| `gross_amount`            | decimal |          No | Gross amount                |
| `net_amount`              | decimal |          No | Net amount                  |
| `debit_amount`            | decimal |          No | Debit                       |
| `credit_amount`           | decimal |          No | Credit                      |
| `amount`                  | decimal |         Yes | Reconciliation amount       |
| `status`                  | string  |          No | Transaction status          |
| `source_system`           | string  |         Yes | Source system               |
| `source_asset_id`         | string  |         Yes | Source lineage              |
| `source_version_id`       | string  |         Yes | Source version              |
| `source_row_number`       | integer |         Yes | Physical row                |
| `source_record_id`        | string  |          No | Source record identifier    |
| `standardization_version` | string  |         Yes | Transformation version      |

---

# 7. Lineage Model

Every canonical row must be traceable:

```text
Report Exception
      ↓
Aggregate Row
      ↓
Canonical Subledger Rows
      ↓
Standardized Rows
      ↓
Source Rows
      ↓
Source File
```

Example:

```json
{
  "lineage_id": "lin_9001",
  "canonical_record_id": "sl_004521",
  "source_asset_id": "asset_sl_001",
  "source_version_id": "asset_sl_001_v3",
  "source_sheet": "Transactions",
  "source_row_number": 842,
  "source_record_id": "TXN-88312"
}
```

Lineage is not optional.

---

# 8. Relationship Schema

```json
{
  "relationship_id": "rel_001",
  "relationship_type": "CROSS_MODULE",
  "source_dataset": "unified_subledger",
  "source_fields": [
    "claim_id",
    "transaction_date"
  ],
  "target_dataset": "claims_mapping",
  "target_fields": [
    "claim_id",
    "transaction_date"
  ],
  "cardinality": "ONE_TO_MANY",
  "matching_strategy": "EXACT",
  "coverage": 0.992,
  "uniqueness": 0.981,
  "confidence": 0.987,
  "origin": "INFERRED",
  "approval_status": "APPROVED",
  "evidence": {
    "matched_rows": 4450,
    "eligible_rows": 4486
  },
  "created_by": "relationship_engine",
  "version": 3
}
```

---

# 9. Relationship Types

```text
INTRA_SUBLEDGER
CROSS_MODULE
REFERENCE
ARITHMETIC
RATIO
TEMPORAL
HIERARCHICAL
CONDITIONAL
COMPOSITE_KEY
```

---

# 10. AI-Inferred vs User-Defined Relationships

Every relationship must explicitly record its origin.

```text
INFERRED
USER_DEFINED
HISTORICAL
SYSTEM_DEFAULT
```

Example:

```json
{
  "relationship_id": "rel_123",
  "origin": "USER_DEFINED",
  "created_by": "user_42",
  "approved_at": "2026-09-30T11:10:00Z"
}
```

User-defined rules always take precedence over inferred relationships **when explicitly marked authoritative**.

---

# 11. Custom Relationship Configuration

```yaml
relationship:
  id: claim_to_subledger
  type: CROSS_MODULE
  source:
    dataset: claims_mapping
    fields:
      - claim_id
      - policy_id

  target:
    dataset: unified_subledger
    fields:
      - claim_id
      - policy_id

  cardinality: one_to_many

  matching:
    strategy: exact
    null_policy: exclude

  aggregation:
    required: true
    measure: amount
    function: sum

  validation:
    minimum_coverage: 0.98
    maximum_collision_rate: 0.01

  approval:
    required: true
```

---

# 12. Pivot & Aggregation Layer

## 12.1 Purpose

The pivot layer converts row-level data into the same reporting grain used by the TA team.

Example:

```text
Raw subledger
      ↓
Claim
      ↓
Treaty
      ↓
Reporting Period
      ↓
Currency
      ↓
Amount
```

The resulting aggregate can be compared directly with the TA-reported aggregate.

---

# 13. Pivot Definition Schema

```json
{
  "pivot_id": "pivot_2026_q3",
  "dataset": "unified_subledger",
  "dimensions": [
    "treaty_id",
    "reporting_period",
    "currency"
  ],
  "measures": [
    {
      "field": "amount",
      "aggregation": "SUM"
    }
  ],
  "filters": [
    {
      "field": "status",
      "operator": "IN",
      "value": ["POSTED", "SETTLED"]
    }
  ],
  "rounding": {
    "scale": 2,
    "mode": "HALF_UP"
  }
}
```

---

# 14. Pivot Inference

Pivot configuration can originate from:

```text
1. Explicit user configuration
2. Existing TA reporting template
3. Historical approved pivot
4. Deterministic inference
5. LLM-assisted inference
```

LLM inference should only receive:

```text
column profiles
business names
candidate dimensions
candidate measures
historical pivot definitions
sample aggregate structures
```

It should not receive the entire dataset.

---

# 15. Pivot Validation

Before reconciliation:

```text
Check:
    dimensions exist
    measures exist
    measure types compatible
    filters valid
    currency rules defined
    grouping grain valid
    duplicate dimensions absent
```

Hard failure:

```text
Invalid pivot definition
      ↓
STOP
```

---

# 16. Reconciliation Grain

A reconciliation must explicitly declare its grain.

Examples:

```text
Claim
Claim + Transaction
Claim + Account
Treaty + Quarter
Treaty + Quarter + Currency
Treaty + Account + Quarter
```

Never assume that matching at one grain proves matching at another.

Example:

```text
Total amount matches
BUT

Account A: +10,000
Account B: -10,000

```

The total reconciles while the detailed data does not.

---

# 17. Reconciliation Configuration

```yaml
reconciliation:
  id: treaty_2026_q3

  reported:
    dataset: claims_mapping
    version: cm_v8

  subledger:
    dataset: unified_subledger
    version: sl_v4

  grain:
    dimensions:
      - treaty_id
      - reporting_period
      - currency

  measure:
    field: amount
    aggregation: SUM

  matching:
    keys:
      - treaty_id
      - reporting_period
      - currency

  variance:
    absolute:
      enabled: true
      threshold: 100.00

    percentage:
      enabled: true
      threshold: 0.001

    evaluation: OR

  rounding:
    decimal_places: 2

  diagnostics:
    deterministic: true
    llm: true
```

---

# 18. Permissible Variance

The system must support:

### Absolute threshold

```text
|reported - subledger| <= absolute_threshold
```

Example:

```text
absolute threshold = 100
```

A difference of:

```text
₹75 → acceptable
₹125 → not acceptable
```

---

## 18.1 Percentage threshold

```text
percentage_variance =
    abs(reported - subledger)
    -------------------------
    denominator
```

Recommended default denominator:

```text
max(abs(subledger), epsilon)
```

Example:

```text
reported = 100,000
subledger = 100,050

variance = 50

percentage = 50 / 100050
           ≈ 0.049975%
```

---

## 18.2 Combined Threshold

Support:

```text
AND
OR
ABSOLUTE_FIRST
PERCENTAGE_FIRST
```

Example:

```yaml
variance:
  absolute:
    enabled: true
    threshold: 100

  percentage:
    enabled: true
    threshold: 0.001

  evaluation: OR
```

With `OR`:

```text
within absolute threshold
OR
within percentage threshold
```

means acceptable.

---

# 19. Zero-Denominator Handling

If:

```text
subledger = 0
```

percentage variance is undefined.

Use:

```text
if reported == 0:
    variance_status = MATCH
elif subledger == 0:
    variance_status = ABSOLUTE_ONLY
```

The system must not generate:

```text
Infinity
NaN
```

as a business result.

---

# 20. Variance Schema

```json
{
  "variance_id": "var_1001",
  "reconciliation_id": "rcn_001",
  "grain": {
    "treaty_id": "TREATY_A",
    "reporting_period": "2026-Q3",
    "currency": "USD"
  },
  "reported_value": 1000000.00,
  "subledger_value": 999850.00,
  "absolute_variance": -150.00,
  "percentage_variance": -0.015002,
  "absolute_threshold": 100.00,
  "percentage_threshold": 0.001,
  "within_absolute_threshold": false,
  "within_percentage_threshold": false,
  "status": "UNRECONCILED"
}
```

---

# 21. Reconciliation Result Schema

```json
{
  "reconciliation_id": "rcn_001",
  "run_id": "run_20260930_001",
  "status": "PARTIAL",
  "summary": {
    "groups": 1250,
    "matched": 1189,
    "within_tolerance": 31,
    "unreconciled": 30
  },
  "amounts": {
    "reported_total": 100000000.00,
    "subledger_total": 99998500.00,
    "absolute_variance": -1500.00
  },
  "exceptions": [
    "exc_1001",
    "exc_1002"
  ],
  "rules": {
    "variance_config_version": "v3",
    "treaty_config_version": "v7"
  }
}
```

---

# 22. Reconciliation Status Model

Use explicit states:

```text
MATCH
WITHIN_TOLERANCE
UNRECONCILED
VALID_DIFFERENCE
INVESTIGATE
DATA_ERROR
UNRESOLVED
```

At run level:

```text
PASSED
PASSED_WITH_EXCEPTIONS
FAILED
BLOCKED
```

---

# 23. Reconciliation Algorithm

```python
def reconcile(
    reported,
    subledger,
    keys,
    measure,
    variance_config,
    treaty_rules=None,
):
    reported_agg = aggregate(
        reported,
        keys=keys,
        measure=measure,
    )

    subledger_agg = aggregate(
        subledger,
        keys=keys,
        measure=measure,
    )

    comparison = full_outer_join(
        reported_agg,
        subledger_agg,
        on=keys,
    )

    comparison["reported_value"] = comparison[
        "reported_value"
    ].fillna(0)

    comparison["subledger_value"] = comparison[
        "subledger_value"
    ].fillna(0)

    comparison["absolute_variance"] = (
        comparison["reported_value"]
        - comparison["subledger_value"]
    )

    comparison["percentage_variance"] = calculate_percentage_variance(
        comparison
    )

    comparison["status"] = evaluate_threshold(
        comparison,
        variance_config,
    )

    if treaty_rules:
        comparison = apply_treaty_rules(
            comparison,
            treaty_rules,
        )

    return comparison
```

---

# 24. Why Full Outer Join Is Required

A reconciliation cannot only compare matched records.

It must identify:

```text
reported only
subledger only
both sides
```

Therefore:

```text
FULL OUTER JOIN
```

is the default aggregate comparison strategy.

---

# 25. Record-Level Reconciliation

Where appropriate:

```text
1. Generate exact key
2. Match exact records
3. Identify missing reported
4. Identify missing subledger
5. Detect duplicates
6. Compare fields
7. Compare amounts
8. Compare dates
9. Compare status
10. Compare normalized hashes
```

---

# 26. Composite Keys

A reconciliation key may be:

```text
claim_id
```

or:

```text
claim_id + transaction_id
```

or:

```text
claim_id + account_id + posting_date
```

The system should not assume a single universal key.

---

# 27. Key Quality Checks

Before reconciliation:

```text
null key rate
duplicate key rate
unique key ratio
collision rate
cross-source coverage
```

Example:

```json
{
  "key": [
    "claim_id",
    "transaction_id"
  ],
  "reported_unique_rate": 0.998,
  "subledger_unique_rate": 0.996,
  "coverage": 0.991,
  "collision_rate": 0.002
}
```

If the key quality is below configured limits:

```text
BLOCK RECONCILIATION
```

rather than producing misleading results.

---

# 28. One-to-Many Matching

Example:

```text
Subledger

Claim 1001 = 10,000

Claims Mapping

Claim 1001 = 4,000
Claim 1001 = 6,000
```

This should be:

```text
aggregate Claims Mapping
      ↓
10,000
      ↓
compare
      ↓
MATCH
```

not:

```text
10,000 != 4,000
```

One-to-many aggregation is a known and important reconciliation scenario. 

---

# 29. Deterministic Diagnostic Engine

Diagnostics must run **after** reconciliation identifies an exception.

The system should not run expensive diagnostics on already reconciled groups.

---

# 30. Deterministic Check Categories

## Level 1 — Structural

```text
file existence
file metadata
row count
column count
schema
data types
column presence
column naming
```

## Level 2 — Completeness

```text
row counts
distinct keys
missing keys
extra keys
partition completeness
date completeness
```

## Level 3 — Integrity

```text
duplicate keys
NULLs
blank values
referential integrity
invalid data types
invalid categorical values
```

## Level 4 — Value

```text
SUM
MIN
MAX
AVG
COUNT
control totals
amount variance
date variance
field-level comparison
hash comparison
```

## Level 5 — Distribution

```text
count by month
count by quarter
count by year
count by status
count by account
count by claim type
numeric distributions
```

These categories align with the existing reconciliation-check design for the platform. 

---

# 31. Built-In Deterministic Checks

The minimum built-in library should include:

```text
D001 Row count difference
D002 Distinct key difference
D003 Missing records
D004 Extra records
D005 Duplicate keys
D006 Null critical keys
D007 Null financial values
D008 Data type mismatch
D009 Invalid dates
D010 Date range mismatch
D011 Month distribution mismatch
D012 Quarter distribution mismatch
D013 Year distribution mismatch
D014 Currency mismatch
D015 Status distribution mismatch
D016 Account distribution mismatch
D017 Claim type distribution mismatch
D018 Amount total mismatch
D019 Debit/credit mismatch
D020 Control total mismatch
D021 Field-level mismatch
D022 Row hash mismatch
D023 Referential integrity failure
D024 Sign mismatch
D025 Rounding difference
D026 Percentage/calculation mismatch
D027 Duplicate source load
D028 Aggregation mismatch
D029 Missing partition
D030 Unexpected new code
D031 Retired code still present
D032 Timing/cutoff pattern
D033 Adjustment/reversal pattern
```

---

# 32. Structured Finding Schema

Every deterministic check returns:

```json
{
  "finding_id": "find_001",
  "check_id": "D003",
  "category": "COMPLETENESS",
  "severity": "HIGH",
  "status": "OPEN",
  "scope": {
    "treaty_id": "T001",
    "period": "2026-Q3"
  },
  "metrics": {
    "reported_rows": 4511,
    "subledger_rows": 4498,
    "missing": 13
  },
  "evidence": [
    {
      "type": "KEY_LIST",
      "reference": "artifact://exceptions/missing_keys_001"
    }
  ],
  "message": "13 reported records have no corresponding subledger key."
}
```

---

# 33. Root-Cause Taxonomy

Use a controlled taxonomy.

```text
MISSING_RECORD
EXTRA_RECORD
DUPLICATE
WRONG_MAPPING
AMOUNT_MISMATCH
DATE_MISMATCH
STATUS_MISMATCH
CODE_MISMATCH
FORMATTING
ROUNDING
TIMING_DIFFERENCE
TRANSFORMATION_DIFFERENCE
MASTER_DATA_MISMATCH
SOURCE_DATA_ISSUE
SIGN_CONVENTION
CURRENCY_CONVERSION
TREATY_RULE_DIFFERENCE
AGGREGATION_DIFFERENCE
ADJUSTMENT
REVERSAL
UNKNOWN
```

The existing project checks explicitly identify these classes as useful reconciliation exception categories. 

---

# 34. Typical Mismatch Causes

The engine should recognize patterns associated with:

### Extraction

```text
missing source records
partial file
wrong reporting period
failed extraction
truncated file
incorrect filter
late-arriving data
```

### Mapping

```text
wrong column mapping
outdated mapping
new unmapped code
incorrect account mapping
incorrect claim-type mapping
```

### Duplicates

```text
duplicate source records
duplicate load
incorrect join
many-to-many join
retry/reprocessing duplication
```

### Transformation

```text
wrong formula
wrong sign
wrong percentage
tax included/excluded
currency conversion
rounding
decimal precision
unit conversion
aggregation error
```

### Timing

```text
different extraction times
posting delay
month-end cutoff
fiscal-year difference
timezone conversion
backdated transaction
future-dated transaction
```

### Business process

```text
adjustment
reversal
refund
chargeback
write-off
cancellation
partial settlement
manual journal
```

### Master data

```text
changed account
changed customer
changed policy
changed claim ID
renamed entity
retired code
new code
```

These categories should be implemented as deterministic patterns where possible, with AI used to interpret ambiguous combinations. 

---

# 35. User-Defined Deterministic Checks

The platform should support a safe plugin interface.

## Plugin contract

```python
class ReconciliationCheck(Protocol):

    check_id: str
    version: str

    def supports(self, context: CheckContext) -> bool:
        ...

    def execute(
        self,
        context: CheckContext
    ) -> list[Finding]:
        ...
```

---

# 36. Safe Plugin Requirements

A custom check must:

* execute inside an isolated environment
* have read-only access to declared datasets
* have no unrestricted filesystem access
* have no network access by default
* have execution timeout
* have memory limit
* declare input fields
* return the standard Finding schema
* be versioned
* be auditable

Never allow user-provided reconciliation scripts to execute arbitrary production Python.

---

# 37. Example Custom Check

```python
class PaidClaimsMustHaveAmount(ReconciliationCheck):

    check_id = "CUSTOM_PAID_AMOUNT"
    version = "1.0"

    def execute(self, context):

        df = context.dataset("unified_subledger")

        invalid = df[
            (df["status"] == "PAID") &
            (df["amount"] <= 0)
        ]

        return [
            Finding(
                check_id=self.check_id,
                severity="HIGH",
                record_ids=invalid["record_id"].tolist(),
                message="Paid records contain non-positive amounts."
            )
        ]
```

---

# 38. Diagnostic Execution Order

Use this exact order:

```text
1. Reconciliation
        ↓
2. Identify exceptions
        ↓
3. Run structural checks
        ↓
4. Run completeness checks
        ↓
5. Run integrity checks
        ↓
6. Run value checks
        ↓
7. Run distribution checks
        ↓
8. Run custom deterministic checks
        ↓
9. Aggregate evidence
        ↓
10. Determine unresolved questions
        ↓
11. LLM only for unresolved interpretation
```

---

# 39. LLM Integration Philosophy

The LLM is an **interpretation layer**, not a calculation engine.

The existing Module 1 architecture explicitly defines the LLM as a targeted semantic decision component rather than the mapping/transformation engine. 

---

# 40. Exact LLM Invocation Points

The Reconciliation Module should invoke an LLM only for:

## L001 — Mismatch Reason Classification

Input:

```text
deterministic findings
aggregate statistics
mismatch patterns
treaty rule metadata
```

Output:

```text
likely reason
confidence
evidence IDs
recommended next check
```

---

## L002 — Semantic Code Equivalence

Example:

```text
Subledger:
PAID
CANCEL
PEND

Reported:
Paid
Cancelled
Pending
```

LLM can suggest semantic equivalence.

Python must validate the proposal against:

* coverage
* collision rate
* frequency
* historical mappings

---

## L003 — Ambiguous Relationship Interpretation

Python may discover:

```text
A / B ≈ C
```

The LLM can interpret whether this resembles:

```text
commission / gross premium ≈ commission %
```

The numerical relationship itself remains Python-generated.

---

## L004 — Mismatch Cluster Interpretation

Python discovers:

```text
90% of mismatches occur:
2026-Q3
Account = A100
Transaction Type = ADJ
```

LLM can interpret the pattern as potentially related to:

```text
adjustment processing
```

---

## L005 — AI Investigation Request

User:

> "Check whether the unmatched amounts look like reversals."

The system converts this into a safe analytical request.

The LLM receives summarized evidence and may request deterministic checks.

---

# 41. LLM Must Not Receive Raw Data by Default

Do **not** send:

```text
entire CSV
entire Excel workbook
millions of rows
full claims mapping
raw PII
all transaction records
```

The Module 1 architecture already establishes compact evidence packages instead of full source files for LLM calls. 

---

# 42. LLM Evidence Package

Use:

```json
{
  "reconciliation_summary": {
    "reported_total": 1000000,
    "subledger_total": 998500,
    "absolute_variance": -1500,
    "percentage_variance": -0.15
  },

  "scope": {
    "treaty": "T001",
    "period": "2026-Q3",
    "currency": "USD"
  },

  "record_counts": {
    "matched": 4210,
    "missing_reported": 18,
    "missing_subledger": 7,
    "amount_mismatches": 42
  },

  "top_mismatch_clusters": [
    {
      "dimension": "transaction_type",
      "value": "ADJUSTMENT",
      "records": 31,
      "variance": -1200
    }
  ],

  "deterministic_findings": [
    {
      "id": "D025-01",
      "category": "ROUNDING",
      "count": 4,
      "total_variance": 0.04
    }
  ],

  "top_examples": [
    {
      "masked_key": "CLAIM-****123",
      "reported": 5000,
      "subledger": 5500,
      "variance": 500,
      "transaction_type": "ADJUSTMENT"
    }
  ],

  "treaty_rules": {
    "amount_basis": "NET",
    "adjustments_included": true,
    "sign_convention": "SUBLEDGER"
  }
}
```

---

# 43. Data Minimization

Before an LLM call:

```text
Raw data
  ↓
Filter to affected scope
  ↓
Aggregate
  ↓
Cluster
  ↓
Top-N evidence
  ↓
Mask identifiers
  ↓
Remove unnecessary columns
  ↓
Compact JSON
  ↓
LLM
```

---

# 44. Token Minimization Strategies

## 44.1 Profiling Summaries

Send:

```text
row_count
null_rate
distinct_count
min
max
mean
median
quantiles
top categories
```

instead of rows.

---

## 44.2 Top-N Mismatches

Default:

```text
Top 10
```

by absolute variance.

Configurable:

```yaml
llm:
  top_mismatch_examples: 10
```

---

## 44.3 Top-N Clusters

Instead of 10,000 exceptions:

```text
Top 10 mismatch clusters
```

grouped by:

```text
treaty
period
account
claim type
transaction type
status
currency
source
```

---

## 44.4 Compact Evidence Tables

Use:

```text
field
count
variance
percentage
pattern
```

rather than verbose descriptions.

---

## 44.5 Cached Profiles

Cache:

```text
schema profile
column semantics
relationship profile
treaty rule summary
historical mismatch patterns
```

---

## 44.6 Prompt Prefix Caching

Keep stable instructions and schema definitions identical across calls.

Only the compact evidence payload should change.

---

## 44.7 Deterministic Short-Circuit

Do not call the LLM when:

```text
exactly explained by deterministic check
```

Examples:

```text
variance = 0.01
threshold = 0.05
→ ROUNDING / VALID

```

No LLM required.

---

# 45. LLM Token Budgets

Recommended starting budgets:

| Operation                     | Model tier | Input target | Output target |
| ----------------------------- | ---------- | -----------: | ------------: |
| Simple classification         | fast       |      ≤ 1,500 |         ≤ 250 |
| Code equivalence              | fast       |      ≤ 2,000 |         ≤ 400 |
| Mismatch clustering           | fast       |      ≤ 3,000 |         ≤ 500 |
| Root-cause reasoning          | reasoning  |      ≤ 5,000 |         ≤ 800 |
| Complex treaty interpretation | reasoning  |      ≤ 8,000 |       ≤ 1,200 |
| AI chat investigation         | adaptive   |      ≤ 6,000 |       ≤ 1,000 |

These are **application budgets**, not model maximums.

The system should truncate or summarize evidence before exceeding them.

---

# 46. Recommended Current OpenAI Model Strategy

As of September 2026, OpenAI's current model guidance positions:

* **GPT-6 Luna** for efficient, focused, high-volume workloads
* **GPT-6 Sol / GPT-6.1 Sol** for stronger reasoning at lower cost than the flagship
* **GPT-6 Astra** for the hardest reasoning and professional workflows. ([OpenAI Developers][1])

For this reconciliation architecture:

### Default high-volume classification

**GPT-6 Luna**

Use for:

```text
root-cause category classification
code-equivalence proposals
simple mismatch clustering
short evidence interpretation
AI chat routing
```

It is currently listed at **$0.10 / 1M input tokens and $0.50 / 1M output tokens** under standard short-context pricing. ([OpenAI Developers][2])

### Default deeper reasoning

**GPT-6 Sol / GPT-6.1 Sol**

Use for:

```text
complex mismatch reasoning
multi-factor root-cause analysis
ambiguous treaty-rule interpretation
complex investigation planning
```

GPT-6 Sol is listed at $2 / 1M input and $10 / 1M output, while the newer GPT-6.1 Sol is positioned as near-Astra performance at lower cost. ([OpenAI Developers][3])

### Escalation model

**GPT-6 Astra**

Use only for:

```text
high-value unresolved investigations
complex multi-clause reasoning
difficult human-in-the-loop cases
```

Astra is the current flagship for the hardest reasoning tasks, but its standard price is substantially higher at $10 / 1M input and $50 / 1M output. ([OpenAI Developers][4])

### Recommended routing

```text
                    LLM Request
                         │
                         ▼
                Is it simple classification?
                    /          \
                  YES           NO
                  │              │
                  ▼              ▼
            GPT-6 Luna     Is reasoning complex?
                              /          \
                            NO            YES
                            │              │
                            ▼              ▼
                      GPT-6 Sol      GPT-6 Astra
```

Do not automatically send every exception to Astra.

---

# 47. Structured Output Contract

Every LLM call must use a strict JSON schema / Structured Outputs mechanism.

OpenAI's current model family supports structured outputs, making schema-constrained responses appropriate for this design. ([OpenAI Developers][4])

Example:

```json
{
  "classification": "TIMING_DIFFERENCE",
  "confidence": 0.86,
  "evidence_ids": [
    "D032-01",
    "D011-03"
  ],
  "reason": "Most unmatched records occur within one reporting boundary.",
  "recommended_checks": [
    "compare_posting_date_to_transaction_date",
    "inspect_month_end_cutoff"
  ],
  "requires_human_review": true
}
```

---

# 48. LLM Output Schema

```python
class LLMFinding(BaseModel):
    classification: Literal[
        "MISSING_RECORD",
        "EXTRA_RECORD",
        "DUPLICATE",
        "WRONG_MAPPING",
        "AMOUNT_MISMATCH",
        "DATE_MISMATCH",
        "STATUS_MISMATCH",
        "CODE_MISMATCH",
        "FORMATTING",
        "ROUNDING",
        "TIMING_DIFFERENCE",
        "TRANSFORMATION_DIFFERENCE",
        "MASTER_DATA_MISMATCH",
        "SOURCE_DATA_ISSUE",
        "SIGN_CONVENTION",
        "CURRENCY_CONVERSION",
        "TREATY_RULE_DIFFERENCE",
        "AGGREGATION_DIFFERENCE",
        "ADJUSTMENT",
        "REVERSAL",
        "UNKNOWN"
    ]

    confidence: float
    evidence_ids: list[str]
    reason: str
    recommended_checks: list[str]
    requires_human_review: bool
```

---

# 49. LLM Prompt Template — Mismatch Reason Inference

```text
SYSTEM

You are a reconciliation diagnostic classifier.

Your job is to interpret deterministic reconciliation evidence.

Rules:

1. Do not calculate values yourself.
2. Do not invent evidence.
3. Use only the supplied evidence.
4. Do not declare a financial difference valid unless the evidence supports it.
5. Distinguish technical mismatch from business-valid difference.
6. Return JSON matching the supplied schema.
7. If evidence is insufficient, return UNKNOWN.
8. Set requires_human_review=true when evidence is ambiguous.

USER

Reconciliation scope:
{{scope}}

Deterministic reconciliation summary:
{{reconciliation_summary}}

Mismatch clusters:
{{mismatch_clusters}}

Deterministic findings:
{{deterministic_findings}}

Relevant treaty rules:
{{treaty_rules}}

Top masked examples:
{{top_examples}}

Classify the most likely mismatch reason.

Return only the required JSON object.
```

---

# 50. LLM Prompt Template — User-Requested Investigation

```text
SYSTEM

You are an investigation planner for a financial reconciliation system.

You may only recommend checks from the registered check catalog.

You cannot modify data.

You cannot approve financial adjustments.

You cannot mark an exception as resolved.

Return strict JSON.

USER

User request:
{{user_question}}

Current reconciliation:
{{reconciliation_summary}}

Available deterministic checks:
{{available_checks}}

Relevant evidence:
{{compact_evidence}}

Return:

{
  "intent": "...",
  "checks_to_run": ["..."],
  "reason": "...",
  "required_inputs": ["..."],
  "requires_human_review": true
}
```

---

# 51. AI Chat Architecture

The AI chat interface must **not** be a general-purpose database agent.

Use:

```text
User
 ↓
Intent classifier
 ↓
Allowed action planner
 ↓
Check registry
 ↓
Deterministic Python execution
 ↓
Compact result
 ↓
LLM explanation
 ↓
User
```

---

# 52. Example AI Chat

User:

> Why don't the 2026 Q3 amounts reconcile?

System:

```text
Python:
- reported = $10.2M
- subledger = $10.0M
- variance = $200K
- 84% of variance comes from adjustments
- 91% of adjustment variance occurs in Account A
- posting dates differ from transaction dates by 1–3 days
```

LLM:

```json
{
  "classification": "ADJUSTMENT",
  "confidence": 0.91,
  "evidence_ids": [
    "D018-01",
    "D032-04"
  ],
  "reason": "The majority of the variance is concentrated in adjustment transactions.",
  "recommended_checks": [
    "compare_adjustment_signs",
    "compare_adjustment_inclusion_rules"
  ],
  "requires_human_review": true
}
```

---

# 53. AI Chat Guardrails

The assistant may:

* explain findings
* request deterministic checks
* compare existing aggregates
* identify patterns
* suggest investigations
* summarize evidence

The assistant may not:

* modify data
* change thresholds
* change treaty configuration
* approve adjustments
* delete exceptions
* override reconciliation status
* execute arbitrary SQL/Python
* access unauthorized datasets

---

# 54. Treaty Configuration

Treaty logic must be **configuration-driven**.

Do not write:

```python
if treaty_type == "X":
    ...
elif treaty_type == "Y":
    ...
```

throughout the codebase.

Instead:

```text
Treaty
 ├── metadata
 ├── financial basis
 ├── included components
 ├── excluded components
 ├── sign conventions
 ├── grouping
 ├── aggregation
 ├── adjustments
 ├── timing rules
 ├── currency rules
 └── clauses
```

---

# 55. Treaty Schema

```yaml
treaty:
  id: TREATY_001
  version: 4

  type: QUOTA_SHARE

  reporting:
    dimensions:
      - reporting_period
      - currency
      - treaty_id

  financial_basis:
    premium: NET
    claims: INCURRED

  components:
    include:
      - premium
      - commission
      - claims
      - recoveries

    exclude:
      - taxes

  sign_convention:
    premium: POSITIVE
    claims: NEGATIVE
    recoveries: POSITIVE
    commission: NEGATIVE

  adjustments:
    include: true

  timing:
    basis: POSTING_DATE
    cutoff_days: 5

  aggregation:
    required: true
```

---

# 56. Treaty Clause Model

Each clause should be represented as a machine-evaluable rule.

```json
{
  "clause_id": "CL_001",
  "name": "Commission Inclusion",
  "type": "INCLUSION_RULE",
  "condition": {
    "field": "transaction_type",
    "operator": "IN",
    "value": [
      "COMMISSION"
    ]
  },
  "action": {
    "include": true
  },
  "priority": 10,
  "effective_from": "2026-01-01",
  "effective_to": null,
  "evidence": {
    "document_id": "treaty_doc_v3",
    "page": 12
  }
}
```

---

# 57. Clause Evaluation Engine

```python
def evaluate_clause(row, clause):
    condition_result = evaluate_condition(
        row,
        clause["condition"]
    )

    if condition_result:
        return apply_action(
            row,
            clause["action"]
        )

    return row
```

Rules should be evaluated in deterministic order:

```text
priority
 ↓
effective date
 ↓
specificity
 ↓
default rule
```

---

# 58. Treaty Decision Table

Example:

| Condition         | Component  |     Include? |         Sign | Group By      |
| ----------------- | ---------- | -----------: | -----------: | ------------- |
| `type=PREMIUM`    | Premium    |          Yes |            + | Treaty/Period |
| `type=COMMISSION` | Commission |          Yes |            - | Treaty/Period |
| `type=TAX`        | Tax        |           No |            — | —             |
| `type=CLAIM`      | Claim      |          Yes |            - | Treaty/Period |
| `type=RECOVERY`   | Recovery   |          Yes |            + | Treaty/Period |
| `type=ADJUSTMENT` | Adjustment | Configurable | Configurable | Treaty/Period |

This table becomes executable configuration rather than hardcoded business logic.

---

# 59. Treaty Rule Evaluation Pipeline

```text
Raw standardized row
       ↓
Determine treaty
       ↓
Load treaty version
       ↓
Load effective clauses
       ↓
Apply inclusion/exclusion
       ↓
Apply sign convention
       ↓
Apply currency rule
       ↓
Apply adjustment rule
       ↓
Assign reporting dimensions
       ↓
Aggregate
       ↓
Reconcile
```

---

# 60. Treaty Rule Versioning

A reconciliation must record:

```json
{
  "treaty_id": "T001",
  "treaty_version": 7,
  "clause_set_version": 12,
  "effective_date": "2026-01-01"
}
```

If treaty rules change:

```text
Old reconciliation
    ↓
remains reproducible

New reconciliation
    ↓
uses new rule version
```

---

# 61. Retro Amounts & Adjustments

Retro amounts must not overwrite original data.

Represent them as separate adjustment artifacts.

```json
{
  "adjustment_id": "retro_001",
  "reconciliation_id": "rcn_001",
  "type": "RETRO",
  "effective_period": "2026-Q2",
  "amount": 12500.00,
  "currency": "USD",
  "reason": "Late reported transaction",
  "source": "external_report",
  "approved_by": "user_42",
  "approved_at": "2026-09-30T12:00:00Z"
}
```

---

# 62. Adjustment Ledger

Conceptually:

```text
Original Subledger
        +
Approved Retro Adjustments
        +
Approved Corrections
        -
Reversals
        =
Reconciliation View
```

The original source remains untouched.

---

# 63. Reconciliation View

Create a derived view:

```text
canonical_subledger
        +
adjustment_layer
        +
treaty_rules
        +
reporting_filters
        ↓
effective_reconciliation_view
```

This is the dataset actually reconciled.

---

# 64. Iterative Reconciliation

Example:

```text
RUN 1
Subledger v1
No retro
Variance = $200K

       ↓

Add retro $150K

       ↓

RUN 2
Subledger v1
Retro v1
Variance = $50K

       ↓

Upload corrected subledger

       ↓

RUN 3
Subledger v2
Retro v1
Variance = $4K
```

The system must preserve all three runs.

---

# 65. Version Comparison

Provide:

```text
Run 1 → Run 2
```

with:

```text
variance changed
new exceptions
resolved exceptions
new mismatches
changed root causes
changed treaty rules
changed source data
```

Example:

```json
{
  "comparison": {
    "previous_run": "run_001",
    "current_run": "run_002",
    "variance_change": -150000,
    "exceptions_resolved": 42,
    "exceptions_added": 3,
    "exceptions_persistent": 11
  }
}
```

---

# 66. Golden Reconciliation States

Each exception should maintain:

```text
OPEN
UNDER_INVESTIGATION
VALID_DIFFERENCE
CORRECTED
ACCEPTED
REJECTED
UNRESOLVED
```

---

# 67. Human Investigation Workflow

```text
Exception
   ↓
Review evidence
   ↓
Inspect aggregate
   ↓
Inspect deterministic findings
   ↓
Inspect lineage
   ↓
Inspect source rows
   ↓
Inspect treaty rule
   ↓
Inspect adjustment history
   ↓
Classify
   ├── Valid Difference
   ├── Data Error
   ├── Needs Correction
   └── Unresolved
```

Human review is especially important where business semantics determine whether a technical difference is legitimate. Existing project guidance explicitly calls out business definition, reconciliation key, one-to-many relationships, timing, adjustments, mapping rules, source-system changes, and historical comparison as human investigation areas. 

---

# 68. Reporting Structure

The final report should contain:

```text
1. Executive Summary
2. Reconciliation Scope
3. Input Sources
4. Source Versions
5. Reconciliation Configuration
6. Treaty Rules Applied
7. Overall Results
8. Variance Analysis
9. Matched Records
10. Missing Records
11. Extra Records
12. Field-Level Mismatches
13. Deterministic Findings
14. AI Findings
15. Human Decisions
16. Root-Cause Analysis
17. Assumptions
18. Adjustments / Retro Amounts
19. Lineage
20. Remediation Actions
21. Run Comparison
22. Audit Information
```

---

# 69. Report Summary Example

| Metric             | Result |
| ------------------ | -----: |
| Reported rows      |  4,511 |
| Subledger rows     |  4,498 |
| Matching keys      |  4,470 |
| Missing reported   |     41 |
| Extra reported     |     28 |
| Amount mismatches  |     18 |
| Date mismatches    |      9 |
| Status mismatches  |     14 |
| Duplicate keys     |      3 |
| Critical null keys |      0 |
| Overall variance   | $1,500 |
| Within tolerance   |     No |

The existing reconciliation design explicitly recommends a report structured around counts, missing/extra records, amount/date/status mismatches, duplicate keys, variances, and exception details rather than a simple PASS/FAIL result. 

---

# 70. Exception Report Example

| Key   | Finding   | Reported | Subledger | Variance | AI Category    | Status |
| ----- | --------- | -------: | --------: | -------: | -------------- | ------ |
| 10001 | Amount    |    9,500 |    10,000 |     -500 | Adjustment     | Review |
| 10002 | Date      |   16-Aug |    15-Aug |   +1 day | Timing         | Valid  |
| 10003 | Missing   |  Present |         — |        — | Missing record | Review |
| 10004 | Status    |     PAID |      Paid |        — | Formatting     | Valid  |
| 10005 | Duplicate |        2 |         1 |        — | Duplicate      | Review |

---

# 71. Evidence Model

Every report statement should point to evidence.

Example:

```json
{
  "finding_id": "F1001",
  "evidence": [
    {
      "type": "AGGREGATE",
      "artifact_id": "pivot_001",
      "row_id": "pivot_row_99"
    },
    {
      "type": "SOURCE_RECORD",
      "asset_id": "sl_001",
      "row_number": 882
    },
    {
      "type": "RULE",
      "rule_id": "CLAUSE_001"
    }
  ]
}
```

---

# 72. Assumption Registry

Every reconciliation run must maintain:

```json
{
  "assumption_id": "ASM-001",
  "type": "AGGREGATION",
  "statement": "Multiple Claims Mapping records are aggregated by claim_id before comparison.",
  "source": "user_defined",
  "approved_by": "analyst_42",
  "version": 2
}
```

Examples:

```text
reconciliation key
aggregation grain
date basis
currency basis
sign convention
adjustment treatment
excluded components
treaty interpretation
mapping assumption
relationship assumption
```

---

# 73. API Design

## 73.1 Upload Subledger

```http
POST /api/v1/subledgers
```

Example:

```json
{
  "project_id": "proj_001",
  "treaty_id": "T001",
  "logical_role": "SUBLEDGER"
}
```

File is uploaded through multipart storage.

---

# 74. Create Unified Subledger

```http
POST /api/v1/subledgers/unify
```

```json
{
  "source_versions": [
    "sl_001_v2",
    "sl_002_v4",
    "sl_003_v1"
  ],
  "schema_version": "subledger_v2"
}
```

---

# 75. Create Relationship

```http
POST /api/v1/relationships
```

```json
{
  "type": "CROSS_MODULE",
  "source": {
    "dataset": "claims_mapping",
    "fields": ["claim_id"]
  },
  "target": {
    "dataset": "unified_subledger",
    "fields": ["claim_id"]
  },
  "cardinality": "ONE_TO_MANY"
}
```

---

# 76. Create Pivot

```http
POST /api/v1/pivots
```

```json
{
  "dataset": "unified_subledger",
  "dimensions": [
    "treaty_id",
    "reporting_period",
    "currency"
  ],
  "measures": [
    {
      "field": "amount",
      "aggregation": "SUM"
    }
  ]
}
```

---

# 77. Run Reconciliation

```http
POST /api/v1/reconciliations
```

```json
{
  "claims_mapping_version": "cm_v8",
  "subledger_version": "sl_v4",
  "pivot_id": "pivot_001",
  "treaty_config_version": "treaty_v7",
  "variance_config": {
    "absolute": {
      "enabled": true,
      "threshold": 100
    },
    "percentage": {
      "enabled": true,
      "threshold": 0.001
    },
    "evaluation": "OR"
  }
}
```

---

# 78. Get Reconciliation

```http
GET /api/v1/reconciliations/{reconciliation_id}
```

---

# 79. Get Exceptions

```http
GET /api/v1/reconciliations/{reconciliation_id}/exceptions
```

Filters:

```text
status
severity
treaty
period
root_cause
account
currency
```

---

# 80. Run Diagnostics

```http
POST /api/v1/reconciliations/{id}/diagnostics
```

```json
{
  "mode": "DETERMINISTIC"
}
```

or:

```json
{
  "mode": "ALL"
}
```

---

# 81. AI Investigation API

```http
POST /api/v1/reconciliations/{id}/investigate
```

```json
{
  "question": "Check whether the unmatched amounts look like reversals."
}
```

The server should:

```text
question
 ↓
intent
 ↓
registered check selection
 ↓
Python execution
 ↓
compact evidence
 ↓
LLM interpretation
 ↓
JSON result
```

---

# 82. Report Generation

```http
POST /api/v1/reconciliations/{id}/report
```

Supported formats:

```text
JSON
CSV
XLSX
PDF
HTML
```

---

# 83. Suggested Python Package Structure

```text
backend/
└── domain/
    └── reconciliation/
        ├── __init__.py
        │
        ├── ingestion/
        │   ├── adapters/
        │   ├── detector.py
        │   └── service.py
        │
        ├── standardization/
        │   ├── schema.py
        │   ├── mapper.py
        │   └── service.py
        │
        ├── relationships/
        │   ├── inference.py
        │   ├── matching.py
        │   ├── custom.py
        │   └── validation.py
        │
        ├── pivot/
        │   ├── definition.py
        │   ├── engine.py
        │   └── validation.py
        │
        ├── reconciliation/
        │   ├── engine.py
        │   ├── matching.py
        │   ├── variance.py
        │   └── status.py
        │
        ├── diagnostics/
        │   ├── registry.py
        │   ├── deterministic/
        │   └── plugins/
        │
        ├── treaties/
        │   ├── models.py
        │   ├── evaluator.py
        │   ├── decision_table.py
        │   └── versioning.py
        │
        ├── adjustments/
        │   ├── retro.py
        │   └── corrections.py
        │
        ├── ai/
        │   ├── router.py
        │   ├── prompts.py
        │   ├── schemas.py
        │   ├── cache.py
        │   └── service.py
        │
        ├── reporting/
        │   ├── summary.py
        │   ├── exceptions.py
        │   └── renderer.py
        │
        ├── lineage/
        │   └── service.py
        │
        ├── versioning/
        │   └── service.py
        │
        └── audit/
            └── events.py
```

---

# 84. Storage Architecture

Recommended logical artifacts:

```text
/source_artifacts
    raw files

/standardized_subledgers
    canonical parquet

/claims_mapping
    mapping versions

/unified_subledger
    unified canonical dataset

/relationships
    relationship definitions

/pivots
    pivot definitions + outputs

/treaties
    treaty configs + clauses

/adjustments
    retro/correction artifacts

/reconciliations
    reconciliation runs

/findings
    deterministic + AI findings

/reports
    generated reports

/audit
    immutable audit events
```

Prefer columnar storage such as Parquet for analytical artifacts.

---

# 85. Database Entities

Minimum relational entities:

```text
projects
source_assets
source_versions
standardization_runs
subledger_datasets
relationships
relationship_versions
pivot_definitions
pivot_runs
treaties
treaty_versions
treaty_clauses
adjustments
reconciliation_configs
reconciliation_runs
variance_records
findings
llm_runs
review_decisions
report_artifacts
audit_events
```

---

# 86. Idempotency

Every processing step should be idempotent.

Use:

```text
source checksum
configuration hash
schema version
code version
input artifact versions
```

Generate:

```text
processing_fingerprint
```

Example:

```text
SHA256(
    source_version_ids
    +
    mapping_version
    +
    treaty_version
    +
    pivot_version
    +
    reconciliation_config
    +
    engine_version
)
```

If the fingerprint already exists:

```text
return existing run
```

unless `force=true`.

---

# 87. Caching Strategy

Cache deterministic artifacts:

```text
file profile
schema profile
relationship inference
pivot output
aggregate output
reconciliation result
diagnostic result
```

Cache LLM artifacts using:

```text
model
model version
prompt version
evidence hash
schema version
```

Example:

```json
{
  "cache_key": "sha256(...)",
  "model": "gpt-6-luna",
  "prompt_version": "mismatch-v3",
  "evidence_hash": "...",
  "response": {}
}
```

---

# 88. LLM Cache Rules

Cache when:

```text
same evidence
same prompt
same schema
same model version
```

Do not reuse if:

```text
treaty rules changed
evidence changed
prompt changed
output schema changed
model version changed
```

---

# 89. No-LLM Mode

The system must work without an LLM.

Configuration:

```yaml
llm:
  enabled: false
```

Behavior:

```text
deterministic checks
       ↓
rule-based classifications
       ↓
UNRESOLVED when interpretation is insufficient
       ↓
human review
```

The absence of an LLM must never cause the core reconciliation mathematics to fail.

---

# 90. Testing Strategy

## 90.1 Unit Tests

Test:

```text
absolute variance
percentage variance
zero denominator
rounding
negative values
currency
sign convention
threshold AND
threshold OR
missing values
duplicate keys
one-to-many aggregation
full outer join
```

---

# 91. Example Math Tests

```python
def test_absolute_variance():
    assert variance(1000, 950).absolute == -50
```

```python
def test_within_absolute_threshold():
    assert evaluate_variance(
        reported=1000,
        subledger=950,
        absolute_threshold=100
    ) == "WITHIN_TOLERANCE"
```

```python
def test_zero_denominator():
    result = calculate_percentage_variance(
        reported=100,
        subledger=0
    )

    assert result is None
```

---

# 92. Golden Dataset

Create a small authoritative dataset containing:

```text
matched records
missing records
extra records
duplicates
rounding
timing differences
adjustments
reversals
wrong mapping
currency differences
sign errors
one-to-many records
```

Expected reconciliation output must be checked exactly.

---

# 93. Treaty Regression Tests

For every treaty configuration:

```text
input fixture
+
treaty version
↓
expected effective rows
↓
expected aggregates
↓
expected reconciliation
```

Changing a treaty rule must trigger regression tests.

---

# 94. AI Evaluation Dataset

Maintain labeled examples:

```text
evidence
expected category
expected confidence range
human decision
```

Metrics:

```text
classification accuracy
unknown rate
false-valid rate
false-error rate
human override rate
JSON validity
unsupported-claim rate
```

The most important safety metric is:

```text
false classification of a genuine financial difference as valid
```

---

# 95. Prompt Regression Tests

Every prompt version should be tested for:

```text
valid JSON
schema compliance
correct category
no unsupported evidence
no fabricated facts
reasonable uncertainty
```

---

# 96. Failure Modes

## Failure: Unsupported file

```text
→ mark ingestion FAILED
→ retain source artifact
→ explain parser failure
→ do not delete source
```

---

## Failure: Schema ambiguity

```text
→ create review task
→ do not silently map
```

---

## Failure: Poor reconciliation key

```text
→ BLOCK
→ explain key collision
→ request user-defined key
```

---

## Failure: Treaty configuration missing

```text
→ run generic reconciliation only if permitted
→ clearly mark treaty logic NOT APPLIED
```

For treaty-required reconciliation:

```text
→ BLOCK
```

---

## Failure: LLM unavailable

```text
→ deterministic mode
→ unresolved findings → human review
```

---

## Failure: Invalid LLM JSON

```text
LLM response
 ↓
schema validation
 ↓
FAIL
 ↓
retry once with compact repair prompt
 ↓
FAIL
 ↓
mark AI finding unavailable
```

Do not accept free-form output.

---

# 97. Recovery Strategy

Every processing stage should have status:

```text
QUEUED
RUNNING
SUCCEEDED
PARTIAL
FAILED
CANCELLED
```

Each stage should persist checkpoints.

Example:

```text
ingestion = SUCCESS
standardization = SUCCESS
relationship = SUCCESS
pivot = SUCCESS
reconciliation = SUCCESS
diagnostics = FAILED
```

The system should allow diagnostics to be rerun without repeating ingestion.

---

# 98. Observability

Record:

```text
run_id
stage
start_time
end_time
duration
rows_processed
rows_failed
warnings
errors
LLM calls
LLM tokens
LLM cost
cache hits
cache misses
output artifacts
```

Example:

```json
{
  "run_id": "run_001",
  "stage": "diagnostics",
  "llm_calls": 3,
  "cache_hits": 17,
  "input_tokens": 6200,
  "output_tokens": 1100,
  "duration_ms": 8400
}
```

---

# 99. Security & Privacy

## 99.1 Data Classification

Classify fields:

```text
PUBLIC
INTERNAL
CONFIDENTIAL
SENSITIVE
PII
FINANCIAL
```

---

# 100. LLM Redaction

Before an LLM call:

```text
Claim ID
Customer name
Email
Phone
Address
Bank information
Policy number
Other direct identifiers
```

should be masked unless genuinely necessary and explicitly permitted.

Example:

```text
CLM-2026-001234
```

becomes:

```text
CLM-****1234
```

---

# 101. Deterministic Pseudonymization

Use stable hashes:

```python
masked_id = hmac_sha256(
    secret_key,
    original_id
)
```

This lets the model recognize:

```text
same ID
```

without seeing the original value.

---

# 102. Financial Data

Financial values may often be necessary for mismatch interpretation.

However, minimize them:

```text
raw transaction rows
        ↓
aggregates
        ↓
variance
        ↓
small masked examples
```

Do not send unnecessary transaction fields.

---

# 103. LLM Network Security

Production deployment should support:

```text
private networking
approved model endpoints
data residency requirements
logging controls
retention controls
API key vaulting
```

Secrets must never be stored in:

```text
source code
configuration repository
prompt templates
logs
```

---

# 104. Audit Requirements

Audit:

```text
file upload
file replacement
mapping change
relationship change
pivot change
treaty change
variance change
adjustment creation
adjustment approval
reconciliation execution
LLM invocation
human review
exception resolution
report generation
```

Each event:

```json
{
  "event_id": "evt_001",
  "actor": "user_42",
  "timestamp": "2026-09-30T13:00:00Z",
  "action": "APPROVE_ADJUSTMENT",
  "object_id": "retro_001",
  "before": {},
  "after": {},
  "reason": "Late-arriving external amount"
}
```

---

# 105. UI Information Architecture

The existing platform UI reference recommends organizing enterprise workflows around user tasks rather than exposing raw backend entities, with progressive disclosure and contextual navigation. 

For reconciliation, use:

```text
Reconciliation
│
├── Overview
├── Inputs
│   ├── Claims Mapping
│   ├── Subledger
│   └── Treaty
│
├── Configuration
│   ├── Relationships
│   ├── Pivot
│   ├── Variance
│   └── Rules
│
├── Results
│   ├── Summary
│   ├── Variance
│   ├── Matched
│   └── Unmatched
│
├── Diagnostics
│   ├── Deterministic
│   ├── AI Findings
│   └── Investigation
│
├── Adjustments
│   ├── Retro
│   ├── Corrections
│   └── Reversals
│
├── Lineage
├── Run History
└── Report
```

---

# 106. Reconciliation Overview UI

The first screen should show:

```text
┌──────────────────────────────────────────────────────┐
│ Reconciliation: Treaty A — 2026 Q3                 │
│ Status: PARTIALLY RECONCILED                        │
├──────────────────────────────────────────────────────┤
│ Reported       $100.00M                             │
│ Subledger       $99.85M                             │
│ Variance          $0.15M                            │
│ Variance %          0.15%                           │
├──────────────────────────────────────────────────────┤
│ 1,189 MATCHED                                       │
│    31 WITHIN TOLERANCE                              │
│    30 UNRECONCILED                                  │
├──────────────────────────────────────────────────────┤
│ [Investigate] [Add Adjustment] [Rerun] [Report]      │
└──────────────────────────────────────────────────────┘
```

---

# 107. Diagnostics UI

Use progressive depth:

```text
Summary
   ↓
Mismatch Category
   ↓
Mismatch Cluster
   ↓
Individual Exception
   ↓
Source Record
   ↓
Lineage
```

Example:

```text
Amount mismatch
   42 records
   $25,000 variance
        ↓
Transaction Type = ADJUSTMENT
   31 records
   $21,000 variance
        ↓
Account = A100
   28 records
        ↓
Source rows
        ↓
Treaty clause
```

---

# 108. AI Investigation Panel

Example:

```text
┌────────────────────────────────────────────┐
│ Ask about this reconciliation              │
├────────────────────────────────────────────┤
│ Why are these records not matching?        │
│                                            │
│ [ Ask ]                                    │
├────────────────────────────────────────────┤
│ AI Investigation                           │
│                                            │
│ Likely category: Adjustment                │
│ Confidence: 86%                            │
│                                            │
│ Evidence                                   │
│ • 31/42 mismatches are adjustments         │
│ • 84% variance occurs in Account A         │
│ • Treaty allows adjustments                │
│                                            │
│ Suggested checks                           │
│ [Compare adjustment signs]                 │
│ [Inspect adjustment inclusion rule]        │
└────────────────────────────────────────────┘
```

---

# 109. Human Review UI

Each exception should expose:

```text
Exception
├── Summary
├── Reported value
├── Subledger value
├── Variance
├── Threshold
├── Deterministic findings
├── AI findings
├── Evidence
├── Source records
├── Treaty clauses
├── Lineage
├── Previous decisions
└── Actions
```

Actions:

```text
Mark Valid Difference
Mark Data Error
Create Adjustment
Request Correction
Assign
Add Comment
Keep Open
```

---

# 110. Reconciliation Run Lifecycle

```text
DRAFT
  ↓
VALIDATING
  ↓
RUNNING
  ↓
DIAGNOSTICS
  ↓
REVIEW
  ↓
FINALIZED
```

A finalized run must be immutable.

A correction creates a new run.

---

# 111. End-to-End Workflow

```text
1. Select Claims Mapping version
        ↓
2. Upload one or many subledgers
        ↓
3. Detect formats
        ↓
4. Parse sources
        ↓
5. Profile schemas
        ↓
6. Generate canonical mappings
        ↓
7. Apply historical/user mappings
        ↓
8. Infer subledger relationships
        ↓
9. Validate relationships
        ↓
10. Build unified subledger
        ↓
11. Preserve lineage
        ↓
12. Define/infer pivot
        ↓
13. Validate pivot
        ↓
14. Load treaty configuration
        ↓
15. Apply treaty rules
        ↓
16. Apply approved adjustments
        ↓
17. Build effective reconciliation views
        ↓
18. Validate reconciliation key
        ↓
19. Aggregate both sides
        ↓
20. Full outer comparison
        ↓
21. Calculate variance
        ↓
22. Apply permissible thresholds
        ↓
23. Generate reconciliation results
        ↓
24. Run deterministic checks
        ↓
25. Cluster mismatches
        ↓
26. Determine unresolved questions
        ↓
27. LLM interpretation where necessary
        ↓
28. Validate LLM JSON
        ↓
29. Human review
        ↓
30. Finalize reconciliation
        ↓
31. Generate report
        ↓
32. Persist lineage/audit
```

---

# 112. Recommended Implementation Phases

## Phase 1 — Subledger Foundation

Implement:

* file ingestion
* format detection
* parser registry
* profiling
* canonical subledger schema
* lineage
* versioning

**No LLM required.**

---

## Phase 2 — Relationships

Implement:

* exact keys
* composite keys
* one-to-many relationships
* arithmetic relationships
* relationship scoring
* user-defined relationships

**LLM optional.**

---

## Phase 3 — Pivot

Implement:

* pivot definitions
* aggregation
* filters
* dimensions
* measures
* validation
* saved pivot profiles

**No LLM required for MVP.**

---

## Phase 4 — Core Reconciliation

Implement:

* reconciliation keys
* full outer matching
* aggregate comparison
* variance
* absolute tolerance
* percentage tolerance
* combined thresholds
* result schema

**No LLM required.**

---

## Phase 5 — Deterministic Diagnostics

Implement all built-in checks:

```text
structural
completeness
integrity
value
distribution
```

**No LLM required.**

---

## Phase 6 — Treaty Engine

Implement:

* treaty schema
* clause model
* decision tables
* inclusion/exclusion
* sign convention
* date rules
* grouping
* effective dates
* versioning

**LLM should not evaluate numeric rules.**

---

## Phase 7 — LLM Diagnostics

Implement:

* compact evidence generation
* LLM router
* structured outputs
* caching
* classification
* mismatch reasoning
* AI investigation

---

## Phase 8 — Iterative Adjustments

Implement:

* retro amounts
* corrections
* reversals
* adjustment approval
* run comparison
* audit trail

---

## Phase 9 — Reporting

Implement:

* executive summary
* exception report
* evidence
* lineage
* remediation
* XLSX/PDF/HTML/JSON outputs

---

# 113. MVP Definition

The minimum useful Reconciliation Module should support:

```text
1. Upload two or more subledgers
2. Standardize them
3. Combine them
4. Preserve source lineage
5. Load Claims Mapping
6. Define reconciliation relationship
7. Generate pivot
8. Define tolerance
9. Reconcile
10. Detect missing/extra records
11. Detect duplicates
12. Compare amounts
13. Compare dates
14. Compare status
15. Run deterministic checks
16. Display exceptions
17. Add a retro adjustment
18. Rerun reconciliation
19. Compare runs
20. Generate report
```

Then add:

```text
21. Treaty rules
22. LLM mismatch classification
23. AI investigation
24. Advanced relationship inference
```

---

# 114. Definition of Done

The module is complete when:

* [ ] Multiple subledgers can be uploaded
* [ ] Multiple formats are supported
* [ ] Subledgers can be unified
* [ ] Canonical schema is versioned
* [ ] Every row retains lineage
* [ ] Claims Mapping can be consumed from Module 1
* [ ] Relationships can be inferred
* [ ] Relationships can be manually defined
* [ ] Cross-module relationships work
* [ ] Intra-subledger relationships work
* [ ] Pivot definitions are versioned
* [ ] TA reporting grain can be represented
* [ ] Reconciliation keys are configurable
* [ ] One-to-many relationships are supported
* [ ] Absolute variance is supported
* [ ] Percentage variance is supported
* [ ] Combined variance policies are supported
* [ ] Treaty rules are configurable
* [ ] Treaty clauses are versioned
* [ ] Retro adjustments are supported
* [ ] Reconciliation runs are immutable
* [ ] Run-to-run comparison works
* [ ] Deterministic checks are implemented
* [ ] User-defined checks are sandboxed
* [ ] LLM calls happen only after deterministic checks
* [ ] LLM receives summarized evidence
* [ ] LLM output is schema-validated
* [ ] LLM calls are cached
* [ ] No-LLM mode works
* [ ] AI chat can trigger registered checks
* [ ] Human review exists
* [ ] Lineage is exposed
* [ ] Audit events are recorded
* [ ] Final reports are generated
* [ ] Golden datasets pass
* [ ] Treaty regression tests pass
* [ ] LLM evaluation tests pass

---

# 115. Reference Implementation Pattern

The central service should look conceptually like:

```python
class ReconciliationService:

    def run(self, request):

        claims_mapping = self.claims_mapping.load(
            request.claims_mapping_version
        )

        subledgers = self.subledger.ingest(
            request.subledger_sources
        )

        unified = self.subledger.standardize_and_unify(
            subledgers
        )

        relationships = self.relationships.resolve(
            claims_mapping=claims_mapping,
            subledger=unified,
            user_rules=request.relationship_rules,
        )

        pivot = self.pivot.build(
            dataset=unified,
            definition=request.pivot_definition,
        )

        treaty_view = self.treaty.apply(
            dataset=unified,
            config=request.treaty_config,
        )

        effective_view = self.adjustments.apply(
            treaty_view,
            request.adjustments,
        )

        result = self.engine.reconcile(
            reported=claims_mapping,
            subledger=effective_view,
            config=request.reconciliation_config,
        )

        findings = self.diagnostics.run(
            result=result,
            deterministic_only=True,
        )

        unresolved = self.diagnostics.unresolved(findings)

        if unresolved and request.llm_enabled:
            ai_findings = self.ai.investigate(
                result=result,
                findings=findings,
                scope=unresolved,
            )
            findings.extend(ai_findings)

        report = self.reporting.generate(
            result=result,
            findings=findings,
            lineage=True,
        )

        self.audit.record_run(
            request=request,
            result=result,
        )

        return report
```

---

# 116. Key Architectural Rule

The most important implementation rule for the entire module is:

```text
                 PYTHON
                   │
       ┌───────────┼────────────┐
       │           │            │
    Parse       Calculate     Validate
       │           │            │
   Aggregate     Match       Reconcile
       │           │            │
   Diagnose     Compare      Apply Rules
       │           │            │
       └───────────┼────────────┘
                   │
                   ▼
             EVIDENCE PACKAGE
                   │
             only if needed
                   │
                   ▼
                  LLM
                   │
                   ▼
             INTERPRETATION
                   │
                   ▼
              HUMAN REVIEW
```

The LLM should therefore be treated as an **evidence interpreter**, not the reconciliation engine.

---

# 117. Final Architecture

```text
                                  USER
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
              CONFIGURATION                  AI CHAT
                    │                             │
                    ▼                             ▼
            ┌───────────────┐             ┌───────────────┐
            │ Reconciliation│             │ Investigation │
            │ API            │             │ Gateway       │
            └───────┬───────┘             └───────┬───────┘
                    │                             │
        ┌───────────┼─────────────┐               │
        ▼           ▼             ▼               │
   Claims Map   Subledgers      Treaty             │
        │           │             │               │
        │           ▼             │               │
        │    Standardization      │               │
        │           │             │               │
        │           ▼             │               │
        │    Unified Subledger    │               │
        │           │             │               │
        └───────────┼─────────────┘               │
                    ▼                             │
             Relationships                       │
                    │                             │
                    ▼                             │
               Pivot Layer                        │
                    │                             │
                    ▼                             │
            Treaty / Adjustments                  │
                    │                             │
                    ▼                             │
             Reconciliation                      │
                    │                             │
                    ▼                             │
          Deterministic Diagnostics               │
                    │                             │
                    ├───────────────┐             │
                    │               │             │
                    ▼               ▼             │
                 Resolved       Unresolved        │
                    │               │             │
                    │               ▼             │
                    │          LLM Router ◄───────┘
                    │               │
                    │               ▼
                    │        Structured JSON
                    │               │
                    └───────┬───────┘
                            ▼
                     Human Review
                            │
                            ▼
                    Final Reconciliation
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          Report          Lineage         Audit
```

---

# 118. Final Design Principles

The implementation should preserve these principles throughout the codebase:

1. **Python calculates; AI interprets.**
2. **Raw sources are immutable.**
3. **Every derived result has lineage.**
4. **Every reconciliation run is versioned.**
5. **Every variance is calculated deterministically.**
6. **Every tolerance is explicit and auditable.**
7. **Treaty logic is configuration, not scattered code.**
8. **User relationships can override inferred relationships explicitly.**
9. **One-to-many and aggregation differences are first-class cases.**
10. **A technical mismatch is not automatically a data error.**
11. **Deterministic diagnostics always run before LLM diagnostics.**
12. **LLMs receive compact evidence, never entire datasets by default.**
13. **All LLM responses are strict machine-readable JSON.**
14. **LLM recommendations cannot silently mutate financial state.**
15. **Human review is a normal workflow, not a failure mode.**
16. **No-LLM mode must remain fully functional.**
17. **Every AI conclusion must reference evidence.**
18. **Every adjustment must be separately versioned and approved.**
19. **Every final report must be reproducible from its recorded versions.**
20. **The system should optimize for explainability before automation.**

The resulting platform is therefore not merely a comparison script. It is a **versioned reconciliation engine with deterministic financial controls, configurable treaty logic, lineage, controlled AI diagnostics, iterative adjustment support, and human-auditable investigation workflows**.

[1]: https://developers.openai.com/api/docs/models?utm_source=chatgpt.com "Models | OpenAI API"
[2]: https://developers.openai.com/api/docs/pricing?tab=suite&utm_source=chatgpt.com "Pricing | OpenAI API"
[3]: https://developers.openai.com/api/docs/models/compare?utm_source=chatgpt.com "Compare models | OpenAI API"
[4]: https://developers.openai.com/api/docs/models/gpt-6-astra?utm_source=chatgpt.com "GPT-6 Astra Model | OpenAI API"
