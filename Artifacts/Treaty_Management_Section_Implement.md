# Treaty Management Section — Implementation Specification & README

> **Module:** Treaty Management
> **Parent Module:** Reconciliation
> **Implementation style:** Python-first, deterministic, immutable, stateful, auditable
> **LLM role:** Discovery assistance only
> **Primary inputs:** Module 1 Claims Mapping + standardized data, Module 2 unified subledger + reconciliation configuration
> **Status:** Implementation-ready specification
> **Version:** 1.0

---

# 1. Overview & Responsibilities

## 1.1 Purpose

The Treaty Management Section manages treaty definitions and treaty-related configuration that can affect reconciliation outcomes.

Its primary purpose is to answer:

1. What treaty components currently exist?
2. Which clauses belong to a treaty?
3. Which parameters control those clauses?
4. Where are those components represented in the system?
5. What changed between treaty states?
6. Does a proposed treaty change explain an existing reconciliation break?
7. Does reconciliation improve when the proposed treaty state is evaluated?

The module must support **what-if treaty scenarios without modifying the original data or configuration**.

The fundamental execution model is:

```text
Original Treaty State
        │
        ├───────────────┐
        │               │
        ▼               ▼
 Baseline Run       User Proposal
                        │
                        ▼
                 Python Validation
                        │
                        ▼
                 New Treaty State
                        │
                        ▼
                Reconciliation Run
                        │
                        ▼
                 Compare Results
```

The original state remains immutable.

---

## 1.2 Relationship to Existing Reconciliation Architecture

The existing Reconciliation Module already establishes:

* deterministic processing before AI;
* immutable source artifacts;
* versioned reconciliation runs;
* configurable treaty rules;
* treaty clauses with effective dates;
* lineage from findings back to source data;
* human review for ambiguous business interpretation. 

Treaty Management adds a dedicated lifecycle around those treaty configurations:

```text
Treaty Discovery
      ↓
Treaty Manifest
      ↓
Editable Blocks
      ↓
User Change Request
      ↓
Python Validation
      ↓
New Immutable Treaty State
      ↓
Reconciliation
      ↓
State Comparison
      ↓
User Decision
      ↓
Keep / Branch / Rollback / Approve
```

---

# 2. Scope

## 2.1 In Scope

The Treaty Management Section owns:

* treaty discovery;
* treaty manifest generation;
* clause discovery;
* parameter discovery;
* treaty/source lineage;
* editable-block generation;
* treaty configuration versioning;
* patch validation;
* patch application;
* state creation;
* state history;
* state comparison;
* rollback;
* branching;
* treaty-aware reconciliation execution;
* treaty-state impact analysis;
* audit events;
* user permissions around treaty modification.

## 2.2 Out of Scope

The module does not:

* modify original raw files;
* modify original standardized datasets;
* modify the original Claims Mapping artifact;
* allow an LLM to directly edit treaty state;
* allow an LLM to approve treaty changes;
* allow an LLM to calculate reconciliation results;
* allow an LLM to decide whether a treaty change is correct;
* silently promote a what-if state to production;
* overwrite an existing treaty version.

---

# 3. Core Design Principles

## 3.1 Python Owns State Mutation

All treaty modifications must follow:

```text
User Action
    ↓
Structured Patch
    ↓
Python Schema Validation
    ↓
Business Rule Validation
    ↓
Referential Integrity Validation
    ↓
Patch Application
    ↓
New Immutable State
```

The LLM is never in this execution path.

---

## 3.2 Original State Is Immutable

Never:

```python
treaty.clauses.remove(...)
```

against the persisted treaty state.

Instead:

```text
Treaty State v1
      ↓
Patch
      ↓
Treaty State v2
```

State v1 remains available forever, subject to retention policy.

---

## 3.3 A Treaty State Is a Complete Reproducible Snapshot

A state must identify all inputs required to reproduce the treaty behavior:

```text
Treaty metadata
+
Clause set
+
Parameter values
+
Effective dates
+
Mappings
+
Rule-set references
+
Schema version
+
Parent state
+
Change set
```

---

## 3.4 What-If Changes Are First-Class

A user should be able to create:

```text
Baseline
   ├── Scenario A
   ├── Scenario B
   └── Scenario C
```

without modifying the baseline.

This supports testing competing hypotheses about why reconciliation failed.

---

## 3.5 Rollback Does Not Delete History

Rollback means:

```text
Current State v5
      ↓
select v3
      ↓
create new state v6
      ↓
v6 is equivalent to v3
```

It does **not** mean deleting v4/v5.

This preserves complete auditability.

---

# 4. High-Level Architecture

```text
                         ┌──────────────────┐
                         │      USER        │
                         └────────┬─────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
                 ▼                                 ▼
        Treaty Management UI                API / CLI
                 │                                 │
                 └────────────────┬────────────────┘
                                  ▼
                       ┌───────────────────┐
                       │ Treaty Service    │
                       └─────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
        Discovery Engine   Block Manager     State Manager
              │                  │                  │
              │                  │                  ▼
              │                  │            State Store
              │                  │
              ▼                  ▼
       Optional LLM         Patch Validator
       Discovery Aid             │
              │                  ▼
              └────────────► Manifest
                                 │
                                 ▼
                         Immutable Treaty State
                                 │
                                 ▼
                       Reconciliation Engine
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                             ▼
             Baseline Run                 Scenario Run
                  │                             │
                  └──────────────┬──────────────┘
                                 ▼
                         Python Comparison
                                 │
                                 ▼
                         Impact Report
                                 │
                                 ▼
                              Audit
```

---

# 5. Treaty Domain Model

The domain hierarchy is:

```text
Treaty
 ├── Metadata
 ├── Effective Period
 ├── Clauses
 │    ├── Clause
 │    │    ├── Parameters
 │    │    ├── Conditions
 │    │    ├── Actions
 │    │    └── Effective Period
 │    └── ...
 ├── Rule-set mappings
 ├── Reporting mappings
 └── Version history
```

Example:

```text
WST30465
│
├── SW11
│   ├── effective_from
│   ├── effective_to
│   ├── limit
│   ├── attachment_point
│   └── rate
│
├── SW7
│   ├── effective_from
│   ├── limit
│   └── rate
│
└── SW5
    ├── effective_from
    └── limit
```

---

# 6. Treaty Manifest

## 6.1 Purpose

The treaty manifest is the canonical read-only representation discovered from available treaty sources.

It does not itself modify anything.

It provides:

* treaty identity;
* treaty period;
* clauses;
* parameters;
* source locations;
* lineage;
* discovery confidence.

---

## 6.2 Manifest Schema

```json
{
  "manifest_id": "manifest_wst30465_v1",
  "treaty_id": "WST30465",
  "effective_from": "2024-01-01",
  "effective_to": "2026-12-31",
  "discovery_version": "1.0",
  "clauses": [],
  "parameters": [],
  "rule_mappings": [],
  "source_references": [],
  "discovery_metadata": {
    "method": "PYTHON_PLUS_LLM_OPTIONAL",
    "confidence": 0.94,
    "discovered_at": "2026-09-30T12:00:00Z"
  }
}
```

---

# 7. Clause Schema

```json
{
  "clause_id": "SW11",
  "name": "SW11",
  "clause_type": "LIMIT",
  "effective_from": "2024-01-01",
  "effective_to": null,
  "parameters": [],
  "conditions": [],
  "actions": [],
  "rule_set_id": "RULESET_SW11",
  "source_references": [],
  "discovery_confidence": 0.96
}
```

---

# 8. Parameter Schema

Each clause parameter must be explicitly typed.

```json
{
  "parameter_id": "SW11_LIMIT",
  "name": "limit",
  "type": "DECIMAL",
  "value": 5000000.00,
  "currency": "USD",
  "unit": "AMOUNT",
  "required": true,
  "editable": true,
  "constraints": {
    "minimum": 0
  },
  "source_references": [
    {
      "source_type": "TREATY_CONFIG",
      "artifact_id": "treaty_doc_v3",
      "path": "$.clauses[0].limit"
    }
  ]
}
```

Supported parameter types:

```text
STRING
INTEGER
DECIMAL
BOOLEAN
DATE
DATETIME
CURRENCY_AMOUNT
PERCENTAGE
ENUM
LIST
REFERENCE
EXPRESSION
```

---

# 9. Treaty Parameter Categories

The discovery and validation engine should recognize common parameter categories.

## 9.1 Dates

```text
effective_from
effective_to
start_date
end_date
renewal_date
termination_date
reporting_date
```

## 9.2 Financial Parameters

```text
limit
aggregate_limit
attachment_point
retention
deductible
premium
commission
rate
share
cap
floor
threshold
```

## 9.3 Classification Parameters

```text
claim_type
transaction_type
coverage_type
business_unit
region
currency
account
```

## 9.4 Rule Parameters

```text
include
exclude
aggregation
sign
mapping
calculation
priority
```

---

# 10. Source References and Lineage

Every discovered component should retain its origin.

Possible source types:

```text
STANDARDIZED_DATA
CLAIMS_MAPPING
SUBLEDGER
TREATY_CONFIG
EXTERNAL_DOCUMENT
DERIVED_RULE
USER_DEFINED
```

Example:

```json
{
  "source_reference_id": "src_ref_001",
  "source_type": "STANDARDIZED_DATA",
  "artifact_id": "claims_mapping_v8",
  "version_id": "cm_v8",
  "location": {
    "dataset": "claims_mapping",
    "column": "treaty_clause",
    "row_ids": ["cm_1001", "cm_1002"]
  }
}
```

For configuration:

```json
{
  "source_type": "TREATY_CONFIG",
  "artifact_id": "treaty_config_7",
  "location": {
    "path": "$.treaties.WST30465.clauses.SW11.limit"
  }
}
```

For documents:

```json
{
  "source_type": "EXTERNAL_DOCUMENT",
  "artifact_id": "treaty_document_2026",
  "location": {
    "page": 17,
    "section": "SW11"
  }
}
```

---

# 11. Discovery Confidence

Confidence is permitted **only for discovery**.

It must never be interpreted as authorization.

Example:

```json
{
  "component": "SW11",
  "confidence": 0.96,
  "reason": "Matched treaty identifier and clause pattern in configuration and standardized data.",
  "requires_user_confirmation": true
}
```

The system must never interpret:

```text
confidence = 0.99
```

as:

```text
apply_change = true
```

---

# 12. Treaty Discovery Pipeline

```text
Inputs
  │
  ├── Standardized data
  ├── Claims Mapping
  ├── Unified Subledger
  ├── Treaty configuration
  └── External treaty documents
          │
          ▼
     Source Profiling
          │
          ▼
   Treaty Identifier Detection
          │
          ▼
    Clause Detection
          │
          ▼
   Parameter Detection
          │
          ▼
   Source/Lineage Linking
          │
          ▼
    Cross-source Validation
          │
          ▼
      Treaty Manifest
```

---

# 13. Treaty Identification Heuristics

The deterministic discovery engine should first inspect structured fields.

Candidate treaty identifier fields:

```text
treaty_id
treaty
treaty_code
contract_id
contract_number
agreement_id
reinsurance_contract
treaty_reference
```

Matching should be case-insensitive after normalization.

Example:

```python
TREATY_ID_CANDIDATES = {
    "treaty_id",
    "treaty",
    "treaty_code",
    "contract_id",
    "contract_number",
    "agreement_id"
}
```

---

# 14. Clause Identification Heuristics

Clause identifiers may appear as:

```text
SW11
SW7
SW5
CLAUSE_SW11
CLAUSE-11
SW 11
```

Normalize before matching:

```python
def normalize_clause_id(value: str) -> str:
    value = value.strip().upper()
    value = value.replace(" ", "")
    value = value.replace("-", "")
    return value
```

Potential clause patterns may be detected using:

```python
r"^[A-Z]{1,5}\d{1,4}$"
```

but pattern matching alone must not establish semantic meaning.

A candidate clause should be corroborated through:

* repeated occurrence;
* configuration paths;
* nearby parameter fields;
* source documents;
* historical states;
* user confirmation.

---

# 15. Parameter Discovery

## 15.1 Structured Fields

If a structured source contains:

```text
SW11_START
SW11_END
SW11_LIMIT
SW11_RATE
```

the deterministic parser can infer:

```text
clause = SW11
parameter = START
```

---

## 15.2 Nested Configuration

For:

```json
{
  "clauses": {
    "SW11": {
      "start_date": "2025-01-01",
      "limit": 5000000,
      "rate": 0.15
    }
  }
}
```

the parser directly produces:

```text
SW11
 ├── start_date
 ├── limit
 └── rate
```

---

## 15.3 Semi-Structured Fields

For text such as:

```text
SW11 applies from 01-Jan-2025 with a limit of USD 5,000,000.
```

Python may extract:

```text
SW11
2025-01-01
5000000
USD
```

The LLM may optionally assist with semantic interpretation when deterministic parsing is insufficient.

---

# 16. Cross-Source Treaty Discovery

A treaty component should be assigned a stronger evidence profile when multiple sources independently identify it.

Example:

```text
Claims Mapping:
WST30465 → SW11

Subledger:
WST30465 → SW11

Treaty configuration:
WST30465 → SW11

External document:
WST30465 → SW11
```

The manifest can record:

```json
{
  "component": "SW11",
  "sources_found": 4,
  "cross_source_consistency": "HIGH"
}
```

This is evidence for discovery, not permission to modify.

---

# 17. Editable Blocks

An editable block is the smallest safe unit of user-controlled treaty modification.

The system should expose blocks instead of allowing arbitrary object mutation.

Supported initial block types:

```text
ADD_CLAUSE
REMOVE_CLAUSE
UPDATE_CLAUSE
UPDATE_CLAUSE_DATE
UPDATE_PARAMETER
ADD_PARAMETER
REMOVE_PARAMETER
UPDATE_RULE_MAPPING
UPDATE_EFFECTIVE_PERIOD
UPDATE_CLAUSE_PRIORITY
```

---

# 18. Editable Block Schema

```json
{
  "block_id": "block_sw11_limit",
  "treaty_id": "WST30465",
  "clause_id": "SW11",
  "block_type": "UPDATE_PARAMETER",
  "path": "/clauses/SW11/parameters/limit",
  "current_value": 5000000.00,
  "allowed_type": "DECIMAL",
  "constraints": {
    "minimum": 0
  },
  "affected_reconciliation_rules": [
    "RULESET_SW11"
  ],
  "source_references": [
    "src_ref_001"
  ],
  "editable": true
}
```

---

# 19. Editable Block Safety Rules

An editable block must define:

```text
block_id
treaty_id
clause_id
path
current value
expected type
allowed operations
constraints
affected rules
source references
permission requirement
```

Example:

```json
{
  "block_type": "UPDATE_PARAMETER",
  "allowed_operations": [
    "REPLACE"
  ],
  "requires_role": "TREATY_EDITOR"
}
```

---

# 20. Safe Editable Operations

The preferred patch operations are:

```text
ADD
REMOVE
REPLACE
```

Avoid arbitrary executable expressions.

Unsafe:

```json
{
  "operation": "EXECUTE",
  "code": "..."
}
```

Safe:

```json
{
  "operation": "REPLACE",
  "path": "/clauses/SW11/parameters/limit",
  "value": 7500000
}
```

---

# 21. Patch / Change-Set Schema

```json
{
  "change_set_id": "cs_00017",
  "treaty_id": "WST30465",
  "base_state_id": "state_wst30465_v1",
  "created_by": "user_42",
  "created_at": "2026-09-30T14:00:00Z",
  "reason": "Test treaty update reported as effective from 2025-07-01",
  "operations": []
}
```

---

# 22. Patch Operation Schema

```json
{
  "operation_id": "op_001",
  "op": "REPLACE",
  "path": "/clauses/SW11/effective_from",
  "old_value": "2025-01-01",
  "value": "2025-07-01",
  "block_id": "block_sw11_effective_from"
}
```

The `old_value` should be persisted even though Python can derive it from the base state.

This makes the patch independently auditable.

---

# 23. Supported Patch Paths

Example:

```text
/treaty_id

/effective_from
/effective_to

/clauses/SW11

/clauses/SW11/effective_from
/clauses/SW11/effective_to

/clauses/SW11/parameters/limit
/clauses/SW11/parameters/rate

/rule_mappings/SW11/rule_set_id
```

Paths must be validated against the treaty schema.

---

# 24. Patch Validation

Patch validation must occur in stages.

```text
Patch received
      ↓
Authentication
      ↓
Authorization
      ↓
Schema validation
      ↓
Path validation
      ↓
Type validation
      ↓
Constraint validation
      ↓
Date validation
      ↓
Referential integrity
      ↓
Conflict validation
      ↓
Business-rule validation
      ↓
State creation
```

Any failure blocks state creation.

---

# 25. Type Validation

Example:

```python
limit = Decimal("5000000")
```

is valid.

But:

```python
limit = "five million"
```

must fail.

Similarly:

```text
effective_from → DATE
rate            → DECIMAL/PERCENTAGE
limit           → DECIMAL
include         → BOOLEAN
clause_id       → STRING
```

---

# 26. Date Validation

Minimum rules:

```text
effective_from <= effective_to
```

when both exist.

Also validate:

```text
clause effective dates within treaty period
```

unless explicitly configured otherwise.

Example invalid patch:

```json
{
  "effective_from": "2027-01-01",
  "effective_to": "2026-12-31"
}
```

Result:

```text
PATCH_REJECTED
INVALID_DATE_RANGE
```

---

# 27. Clause Referential Integrity

A rule mapping cannot reference a non-existent clause.

Invalid:

```json
{
  "rule_set_id": "RULESET_SW99",
  "clause_id": "SW11"
}
```

if `RULESET_SW99` does not exist.

Similarly:

```text
REMOVE SW11
```

must fail if another active rule requires SW11 unless the patch also explicitly updates the dependent rule mapping.

---

# 28. Remove-Clause Validation

Removing a clause requires checking:

```text
active references
rule-set mappings
reporting mappings
reconciliation configuration
historical dependencies
current-state dependencies
```

The system must distinguish:

```text
REMOVE_FROM_CURRENT_STATE
```

from:

```text
DELETE_FROM_HISTORY
```

The latter is never permitted.

---

# 29. Add-Clause Validation

A new clause must provide:

```text
clause_id
effective_from
effective_to
clause type
parameters required by type
rule-set mapping if required
```

Example:

```json
{
  "clause_id": "SW2",
  "clause_type": "LIMIT",
  "effective_from": "2025-07-01",
  "effective_to": null,
  "parameters": {
    "limit": 2500000
  },
  "rule_set_id": "RULESET_SW2"
}
```

---

# 30. Versioned State Model

A treaty state represents a complete immutable treaty configuration.

```json
{
  "state_id": "state_wst30465_v2",
  "treaty_id": "WST30465",
  "state_type": "SCENARIO",
  "parent_state_id": "state_wst30465_v1",
  "root_state_id": "state_wst30465_v1",
  "branch_id": "branch_001",
  "version_number": 2,
  "created_at": "2026-09-30T14:20:00Z",
  "created_by": "user_42",
  "reason": "Test treaty update",
  "change_set_id": "cs_00017",
  "status": "ACTIVE",
  "content_hash": "sha256:...",
  "schema_version": "treaty-schema-v1"
}
```

---

# 31. State Types

Supported:

```text
BASELINE
SCENARIO
BRANCH
ROLLBACK
APPROVED
SUPERSEDED
ARCHIVED
```

Recommended semantics:

### BASELINE

Original authoritative state.

### SCENARIO

Temporary what-if state.

### BRANCH

Independent state derived from another state.

### ROLLBACK

New state reproducing an earlier state.

### APPROVED

A state explicitly approved for operational reconciliation.

### SUPERSEDED

Retained historical state that is no longer current.

---

# 32. State Immutability

After creation, the following fields cannot change:

```text
state_id
parent_state_id
root_state_id
created_at
created_by
change_set_id
content_hash
version_number
```

The treaty content itself is also immutable.

If anything changes:

```text
new state
```

must be created.

---

# 33. State Content

A persisted state should contain or reference:

```json
{
  "state_id": "state_wst30465_v2",
  "treaty": {
    "id": "WST30465",
    "effective_from": "2024-01-01",
    "effective_to": "2026-12-31"
  },
  "clauses": {},
  "rule_mappings": {},
  "parameters": {},
  "schema_version": "treaty-schema-v1",
  "content_hash": "sha256:..."
}
```

For large configurations, immutable object storage may contain the full snapshot while the database stores the metadata and content hash.

---

# 34. State History

Example:

```text
WST30465
│
├── State v1 — BASELINE
│      │
│      └── State v2 — SCENARIO A
│             │
│             └── State v3 — SCENARIO A revision
│
└── State v4 — SCENARIO B
```

The state graph is therefore a DAG rather than merely a linear version sequence.

---

# 35. Branching

Branching is preferred for what-if analysis.

Example:

```text
                 BASELINE v1
                 /         \
                /           \
       Scenario A           Scenario B
       Remove SW7           Keep SW7
       Add SW2              Change SW11
          │                    │
          ▼                    ▼
       Run A                  Run B
```

Neither branch modifies the baseline.

---

# 36. State Fingerprint

Every state should have a deterministic fingerprint:

```python
content_hash = sha256(
    canonical_json(treaty_state)
)
```

Canonical JSON must:

* sort object keys;
* normalize dates;
* normalize decimals;
* normalize null representation;
* use deterministic encoding.

This allows exact state comparison.

---

# 37. State Diff

A state comparison should return:

```json
{
  "from_state": "state_wst30465_v1",
  "to_state": "state_wst30465_v2",
  "added": [],
  "removed": [],
  "modified": [],
  "unchanged": []
}
```

Example:

```json
{
  "added": [
    {
      "path": "/clauses/SW2",
      "value": {}
    }
  ],
  "removed": [
    {
      "path": "/clauses/SW7"
    }
  ],
  "modified": [
    {
      "path": "/clauses/SW11/effective_from",
      "before": "2025-01-01",
      "after": "2025-07-01"
    }
  ]
}
```

---

# 38. Treaty Change Lifecycle

```text
DISCOVER
   ↓
REVIEW MANIFEST
   ↓
SELECT EDITABLE BLOCK
   ↓
CREATE CHANGE REQUEST
   ↓
VALIDATE PATCH
   ↓
CREATE SCENARIO STATE
   ↓
RUN RECONCILIATION
   ↓
COMPARE WITH BASELINE
   ↓
REVIEW IMPACT
   ↓
┌───────────────┬───────────────┬───────────────┐
│ Keep Scenario │ Create Branch │ Rollback/Test │
└───────────────┴───────────────┴───────────────┘
```

---

# 39. Reconciliation Integration

Treaty Management must integrate with the existing reconciliation pipeline.

The treaty state becomes an explicit input:

```text
Claims Mapping Version
        +
Unified Subledger Version
        +
Pivot Version
        +
Reconciliation Config Version
        +
Treaty State
        ↓
Reconciliation Run
```

The treaty state must never be implicit.

---

# 40. Reconciliation Run Schema

```json
{
  "run_id": "run_20260930_0042",
  "claims_mapping_version": "cm_v8",
  "subledger_version": "sl_v4",
  "pivot_version": "pivot_v3",
  "reconciliation_config_version": "rc_v5",
  "treaty_id": "WST30465",
  "treaty_state_id": "state_wst30465_v2",
  "run_type": "SCENARIO",
  "status": "SUCCEEDED"
}
```

This follows the existing reconciliation principle that runs must record the exact versions of their source and configuration inputs. 

---

# 41. Baseline vs Scenario Runs

A baseline run:

```json
{
  "run_type": "BASELINE",
  "treaty_state_id": "state_wst30465_v1"
}
```

A scenario run:

```json
{
  "run_type": "SCENARIO",
  "treaty_state_id": "state_wst30465_v2",
  "parent_run_id": "run_baseline_001"
}
```

---

# 42. Treaty Impact Comparison

The comparison must be deterministic.

Compare:

```text
overall status
total variance
absolute variance
percentage variance
matched groups
within-tolerance groups
unreconciled groups
missing records
extra records
amount mismatches
date mismatches
treaty-specific exceptions
```

---

# 43. Reconciliation Comparison Schema

```json
{
  "comparison_id": "cmp_001",
  "baseline_run_id": "run_baseline_001",
  "scenario_run_id": "run_scenario_001",
  "baseline_state_id": "state_wst30465_v1",
  "scenario_state_id": "state_wst30465_v2",
  "metrics": {
    "baseline_absolute_variance": 250000,
    "scenario_absolute_variance": 75000,
    "baseline_unreconciled_groups": 42,
    "scenario_unreconciled_groups": 13
  },
  "changed_exceptions": [],
  "interpretation": "DETERMINISTIC_COMPARISON_ONLY"
}
```

The comparison engine must not claim that the treaty modification is the true business correction merely because reconciliation improved.

---

# 44. Improvement Metrics

Calculate:

```python
variance_delta = scenario_variance - baseline_variance

unreconciled_delta = (
    scenario_unreconciled
    - baseline_unreconciled
)
```

Also calculate:

```text
resolved exceptions
new exceptions
persistent exceptions
changed exception groups
changed affected amounts
```

Example:

```json
{
  "variance": {
    "before": 250000,
    "after": 75000,
    "delta": -175000
  },
  "exceptions": {
    "before": 42,
    "after": 13,
    "resolved": 31,
    "new": 2,
    "persistent": 11
  }
}
```

---

# 45. What the Comparison Must Not Say

The system must not automatically produce:

```text
"The new treaty state is correct."
```

or:

```text
"The treaty was definitely the root cause."
```

Instead:

```text
"The scenario reduced the absolute reconciliation variance from
$250,000 to $75,000."
```

and:

```text
"31 previously unreconciled groups no longer exceed the configured tolerance."
```

The user determines whether the treaty change represents the actual business correction.

---

# 46. Affected-Data Lineage

Every patch must identify potentially impacted records.

Example:

```json
{
  "operation_id": "op_001",
  "path": "/clauses/SW11/parameters/limit",
  "affected_scope": {
    "treaty_id": "WST30465",
    "clause_id": "SW11",
    "reporting_periods": [
      "2025-Q3",
      "2025-Q4",
      "2026-Q1"
    ]
  }
}
```

After execution, Python should resolve the actual affected rows.

---

# 47. Impacted Row Model

```json
{
  "impact_id": "impact_001",
  "state_id": "state_wst30465_v2",
  "operation_id": "op_001",
  "dataset": "unified_subledger",
  "record_ids": [
    "sl_1001",
    "sl_1002"
  ],
  "fields": [
    "amount",
    "treaty_clause"
  ],
  "impact_type": "RULE_REEVALUATION"
}
```

---

# 48. Important Distinction: Configuration vs Data

Treaty Management must not rewrite the underlying financial records.

For example:

```text
Original:

amount = 5,000,000
```

must remain:

```text
amount = 5,000,000
```

If a new treaty limit changes whether that amount qualifies, the system should produce:

```text
derived treaty evaluation
```

rather than:

```text
modified source amount
```

---

# 49. Effective Treaty View

The reconciliation input should be a derived view:

```text
Immutable Unified Subledger
          +
Immutable Treaty State
          +
Treaty Evaluation
          ↓
Effective Treaty-Aware Reconciliation View
```

This is analogous to the existing reconciliation design where the original source remains immutable and derived views incorporate treaty rules and approved adjustments. 

---

# 50. Effective-Date Evaluation

For a transaction:

```text
transaction_date = 2025-08-15
```

and clause:

```text
effective_from = 2025-07-01
effective_to = null
```

the clause is active.

Python:

```python
def is_effective(date, clause):
    if date < clause.effective_from:
        return False

    if clause.effective_to is not None:
        if date > clause.effective_to:
            return False

    return True
```

---

# 51. Date-Boundary Handling

The engine must explicitly handle:

```text
effective_from
effective_to
inclusive/exclusive boundaries
reporting period
posting date
transaction date
```

Configuration:

```yaml
date_policy:
  effective_from: INCLUSIVE
  effective_to: INCLUSIVE
  evaluation_basis: POSTING_DATE
```

---

# 52. Clause Evaluation

A clause is evaluated deterministically.

```python
def evaluate_clause(row, clause):
    if not is_effective(row["posting_date"], clause):
        return EvaluationResult.not_applicable()

    if not evaluate_conditions(row, clause.conditions):
        return EvaluationResult.not_applicable()

    return apply_actions(row, clause.actions)
```

No LLM is required.

---

# 53. Clause Evaluation Result

```json
{
  "record_id": "sl_001",
  "treaty_id": "WST30465",
  "clause_id": "SW11",
  "state_id": "state_wst30465_v2",
  "effective": true,
  "conditions_met": true,
  "actions_applied": [
    "LIMIT_APPLIED"
  ],
  "derived_values": {
    "applicable_limit": 7500000
  }
}
```

---

# 54. Rule-Set Mapping

A clause may map to an existing reconciliation rule set.

```json
{
  "clause_id": "SW11",
  "rule_set_id": "RULESET_SW11",
  "version": 4,
  "effective_from": "2025-07-01"
}
```

Editable operation:

```json
{
  "op": "REPLACE",
  "path": "/rule_mappings/SW11/rule_set_id",
  "value": "RULESET_SW11_V2"
}
```

---

# 55. Rule Mapping Validation

Before applying a mapping:

```text
Does rule set exist?
        ↓
Is rule set active?
        ↓
Is rule set compatible with clause type?
        ↓
Are required parameters available?
        ↓
Are effective dates compatible?
        ↓
Does mapping create conflicts?
```

---

# 56. Example Treaty Manifest — WST30465

```json
{
  "manifest_id": "manifest_wst30465_v1",
  "treaty_id": "WST30465",
  "effective_from": "2024-01-01",
  "effective_to": "2026-12-31",
  "clauses": [
    {
      "clause_id": "SW11",
      "clause_type": "LIMIT",
      "effective_from": "2025-01-01",
      "effective_to": null,
      "parameters": [
        {
          "parameter_id": "limit",
          "type": "CURRENCY_AMOUNT",
          "value": 5000000.00,
          "currency": "USD",
          "editable": true
        },
        {
          "parameter_id": "rate",
          "type": "PERCENTAGE",
          "value": 0.15,
          "editable": true
        }
      ],
      "rule_set_id": "RULESET_SW11",
      "source_references": [
        {
          "source_type": "TREATY_CONFIG",
          "artifact_id": "treaty_config_v1",
          "path": "$.treaties.WST30465.clauses.SW11"
        },
        {
          "source_type": "CLAIMS_MAPPING",
          "artifact_id": "cm_v8",
          "column": "treaty_clause",
          "values": ["SW11"]
        }
      ],
      "discovery_confidence": 0.98
    },
    {
      "clause_id": "SW7",
      "clause_type": "LIMIT",
      "effective_from": "2024-01-01",
      "effective_to": null,
      "parameters": [
        {
          "parameter_id": "limit",
          "type": "CURRENCY_AMOUNT",
          "value": 3000000.00,
          "currency": "USD",
          "editable": true
        }
      ],
      "rule_set_id": "RULESET_SW7",
      "discovery_confidence": 0.95
    },
    {
      "clause_id": "SW5",
      "clause_type": "RATE",
      "effective_from": "2024-01-01",
      "effective_to": null,
      "parameters": [
        {
          "parameter_id": "rate",
          "type": "PERCENTAGE",
          "value": 0.10,
          "editable": true
        }
      ],
      "rule_set_id": "RULESET_SW5",
      "discovery_confidence": 0.93
    }
  ],
  "source_references": [
    {
      "source_type": "CLAIMS_MAPPING",
      "artifact_id": "cm_v8"
    },
    {
      "source_type": "UNIFIED_SUBLEDGER",
      "artifact_id": "sl_v4"
    },
    {
      "source_type": "TREATY_CONFIG",
      "artifact_id": "treaty_config_v1"
    }
  ],
  "discovery_metadata": {
    "method": "PYTHON_PLUS_LLM_OPTIONAL",
    "confidence": 0.95
  }
}
```

---

# 57. Required Example Patch — WST30465

The following scenario:

1. remove `SW7`;
2. add `SW2` effective from `2025-07-01`;
3. change `SW11` effective start date;
4. change `SW11` monetary limit.

```json
{
  "change_set_id": "cs_wst30465_001",
  "treaty_id": "WST30465",
  "base_state_id": "state_wst30465_v1",
  "created_by": "user_42",
  "created_at": "2026-09-30T15:00:00Z",
  "reason": "Test reported treaty amendment effective 2025-07-01",
  "operations": [
    {
      "operation_id": "op_001",
      "op": "REMOVE",
      "path": "/clauses/SW7",
      "old_value": {
        "clause_id": "SW7"
      }
    },
    {
      "operation_id": "op_002",
      "op": "ADD",
      "path": "/clauses/SW2",
      "value": {
        "clause_id": "SW2",
        "clause_type": "LIMIT",
        "effective_from": "2025-07-01",
        "effective_to": null,
        "parameters": {
          "limit": {
            "value": 2500000.00,
            "currency": "USD"
          }
        },
        "rule_set_id": "RULESET_SW2"
      }
    },
    {
      "operation_id": "op_003",
      "op": "REPLACE",
      "path": "/clauses/SW11/effective_from",
      "old_value": "2025-01-01",
      "value": "2025-07-01"
    },
    {
      "operation_id": "op_004",
      "op": "REPLACE",
      "path": "/clauses/SW11/parameters/limit/value",
      "old_value": 5000000.00,
      "value": 7500000.00
    }
  ]
}
```

---

# 58. Patch Application Algorithm

```python
def create_state(base_state, change_set, actor):
    validate_authorized_actor(actor)

    validate_change_set_schema(change_set)

    validate_base_state(
        change_set.base_state_id,
        base_state.state_id
    )

    working_state = deep_copy(base_state.content)

    for operation in change_set.operations:
        validate_operation_path(
            working_state,
            operation
        )

        validate_operation_type(
            working_state,
            operation
        )

        validate_operation_constraints(
            working_state,
            operation
        )

        validate_referential_integrity(
            working_state,
            operation
        )

        apply_operation(
            working_state,
            operation
        )

    validate_complete_treaty_state(working_state)

    validate_business_rules(working_state)

    return persist_new_state(
        content=working_state,
        parent_state_id=base_state.state_id,
        change_set=change_set,
        actor=actor
    )
```

---

# 59. Patch Application Must Be Atomic

A change set containing:

```text
REMOVE SW7
ADD SW2
UPDATE SW11
```

must either:

```text
ALL OPERATIONS SUCCESS
```

or:

```text
NO STATE CREATED
```

Do not create a partially modified state.

---

# 60. Transaction Boundary

Recommended:

```text
BEGIN TRANSACTION

create change_set
validate patch
create state
store state content
store state metadata
store lineage
store audit event

COMMIT
```

On failure:

```text
ROLLBACK
```

No new treaty state should remain.

---

# 61. Conflict Detection

A patch must fail if its base state is stale.

Example:

```text
User A reads State v3

User B creates State v4

User A attempts:
base_state_id = v3
```

The system should return:

```text
STATE_CONFLICT
BASE_STATE_NO_LONGER_CURRENT
```

The user must explicitly rebase or create a new branch.

---

# 62. Patch Rebase

Optional but recommended.

```text
State v3
  │
  ├── User A patch
  │
  └── State v4
```

If User A's patch does not conflict with v4:

```text
rebase patch
    ↓
State v5
```

If paths overlap:

```text
REBASE_CONFLICT
```

and require human resolution.

---

# 63. Rollback Semantics

Rollback endpoint:

```http
POST /api/v1/treaties/{treaty_id}/states/{state_id}/rollback
```

Request:

```json
{
  "reason": "Restore previously approved treaty definition for comparison"
}
```

The system creates:

```text
State v1
State v2
State v3
State v4
   ↓
rollback target = v2
   ↓
State v5
```

State v5 is a new state.

---

# 64. Rollback Example

History:

```json
[
  {
    "state_id": "state_v1",
    "parent_state_id": null,
    "type": "BASELINE"
  },
  {
    "state_id": "state_v2",
    "parent_state_id": "state_v1",
    "type": "SCENARIO"
  },
  {
    "state_id": "state_v3",
    "parent_state_id": "state_v2",
    "type": "SCENARIO"
  }
]
```

Rollback:

```json
{
  "state_id": "state_v4",
  "parent_state_id": "state_v3",
  "rollback_target_state_id": "state_v1",
  "type": "ROLLBACK"
}
```

State v4 has content equivalent to v1 but retains its own identity and history.

---

# 65. State History API Response

```json
{
  "treaty_id": "WST30465",
  "states": [
    {
      "state_id": "state_wst30465_v1",
      "version": 1,
      "type": "BASELINE",
      "created_by": "system",
      "created_at": "2026-09-01T10:00:00Z"
    },
    {
      "state_id": "state_wst30465_v2",
      "version": 2,
      "type": "SCENARIO",
      "parent_state_id": "state_wst30465_v1",
      "created_by": "user_42",
      "created_at": "2026-09-30T15:00:00Z"
    }
  ]
}
```

---

# 66. Audit Event Model

Every mutation requires an audit event.

```json
{
  "event_id": "evt_treaty_001",
  "event_type": "TREATY_STATE_CREATED",
  "actor": "user_42",
  "timestamp": "2026-09-30T15:02:00Z",
  "treaty_id": "WST30465",
  "state_id": "state_wst30465_v2",
  "parent_state_id": "state_wst30465_v1",
  "change_set_id": "cs_wst30465_001",
  "reason": "Test reported treaty amendment",
  "metadata": {
    "operations": 4
  }
}
```

---

# 67. Audit Events

Minimum events:

```text
TREATY_DISCOVERED
MANIFEST_CREATED
EDITABLE_BLOCK_CREATED
CHANGE_SET_CREATED
CHANGE_SET_VALIDATED
CHANGE_SET_REJECTED
TREATY_STATE_CREATED
TREATY_STATE_BRANCH_CREATED
TREATY_STATE_ROLLBACK_CREATED
TREATY_STATE_APPROVED
TREATY_STATE_SUPERSEDED
RECONCILIATION_RUN_STARTED
RECONCILIATION_RUN_COMPLETED
STATE_COMPARISON_CREATED
```

---

# 68. Audit Requirements

Each state-changing event must contain:

```text
actor
timestamp
action
treaty_id
state_id
parent_state_id
change_set_id
reason
before reference
after reference
validation result
```

Audit events themselves must be append-only.

---

# 69. Permission Model

Recommended roles:

```text
TREATY_VIEWER
TREATY_DISCOVERY_REVIEWER
TREATY_EDITOR
TREATY_APPROVER
TREATY_ADMIN
```

## TREATY_VIEWER

Can:

* view manifests;
* view states;
* view diffs;
* view reconciliation comparisons.

Cannot modify anything.

## TREATY_DISCOVERY_REVIEWER

Can:

* review discovered clauses;
* confirm/reject discovery suggestions.

## TREATY_EDITOR

Can:

* create change sets;
* create scenarios;
* create branches;
* run scenario reconciliation.

## TREATY_APPROVER

Can:

* approve a state for operational use.

## TREATY_ADMIN

Can:

* manage treaty permissions;
* manage lifecycle policies;
* manage configuration.

---

# 70. Separation of Duties

Recommended production rule:

```text
Editor
   ≠
Approver
```

A user who creates a production treaty modification should not automatically approve the same modification.

Scenario states may be created and tested without approval.

---

# 71. Production Promotion

A scenario must not automatically become production.

Lifecycle:

```text
SCENARIO
   ↓
RECONCILIATION TEST
   ↓
HUMAN REVIEW
   ↓
APPROVAL
   ↓
APPROVED
   ↓
ACTIVE
```

---

# 72. LLM Integration — Strict Boundary

The LLM has exactly two responsibilities.

## Allowed

### L001 — Treaty Structure Discovery

Identify likely:

```text
treaty
clause
parameter
effective date
source location
```

### L002 — Editable Block Proposal

Suggest:

```text
"This looks like an editable clause block."
```

or:

```text
"SW11.limit appears to be represented at this configuration path."
```

## Not Allowed

The LLM must not:

```text
apply patches
modify treaty state
choose final values
approve changes
validate financial impact
run reconciliation
declare reconciliation improved
rollback state
promote state
```

---

# 73. LLM Boundary Architecture

```text
                    ┌─────────────────────┐
                    │ Treaty Sources      │
                    └──────────┬──────────┘
                               │
                               ▼
                    Python Profiling
                               │
                               ▼
                    Compact Evidence
                               │
                               ▼
                              LLM
                               │
                               ▼
                       Discovery Proposal
                               │
                               ▼
                       Schema Validation
                               │
                               ▼
                         Human Review
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 Reject                Confirm
                    │                     │
                    │                     ▼
                    │              Editable Block
                    │                     │
                    │                     ▼
                    │             User Explicit Edit
                    │                     │
                    │                     ▼
                    │              Python Patch Engine
                    │                     │
                    │                     ▼
                    │               New State
```

---

# 74. Exact LLM Input

The LLM should receive only compact summaries.

Example:

```json
{
  "treaty_candidates": [
    "WST30465"
  ],
  "field_profiles": [
    {
      "field": "treaty_clause",
      "type": "STRING",
      "distinct_count": 3,
      "top_values": [
        "SW11",
        "SW7",
        "SW5"
      ]
    },
    {
      "field": "clause_limit",
      "type": "DECIMAL",
      "min": 500000,
      "max": 10000000,
      "null_rate": 0.01
    }
  ],
  "candidate_paths": [
    "$.treaties.WST30465.clauses.SW11",
    "$.treaties.WST30465.clauses.SW7"
  ],
  "sample_text": [
    "SW11 applies from 01-Jan-2025..."
  ]
}
```

---

# 75. LLM Must Not Receive by Default

```text
entire raw files
entire Excel workbooks
entire subledger
entire Claims Mapping
all source rows
unmasked PII
unnecessary financial records
credentials
secrets
arbitrary executable code
```

---

# 76. LLM Structure Discovery Prompt

```text
SYSTEM

You are a treaty-structure discovery assistant.

Your only task is to identify likely treaty structures
from the supplied compact evidence.

You must NOT:
- modify any data;
- propose final treaty changes;
- choose values for treaty modifications;
- approve any treaty interpretation;
- evaluate reconciliation results;
- state that a treaty change is correct.

Return only structured JSON.

A discovery confidence score represents confidence that
the component was identified correctly. It is NOT approval
to modify the treaty.

USER

Treaty candidates:
{{treaty_candidates}}

Field profiles:
{{field_profiles}}

Configuration paths:
{{candidate_paths}}

Compact treaty text:
{{sample_text}}

Identify:
1. treaty identifiers
2. likely clauses
3. likely parameters
4. effective dates
5. source locations
6. discovery confidence
```

---

# 77. LLM Output Schema

```json
{
  "treaties": [
    {
      "treaty_id": "WST30465",
      "confidence": 0.98,
      "clauses": [
        {
          "clause_id": "SW11",
          "confidence": 0.96,
          "parameters": [
            {
              "name": "limit",
              "confidence": 0.93
            },
            {
              "name": "effective_from",
              "confidence": 0.97
            }
          ],
          "source_references": [
            {
              "source_type": "TREATY_CONFIG",
              "path": "$.treaties.WST30465.clauses.SW11"
            }
          ]
        }
      ]
    }
  ]
}
```

---

# 78. Editable Block Proposal Prompt

```text
SYSTEM

You are an assistant for identifying potentially editable treaty
configuration blocks.

Do not modify anything.

Do not propose final treaty values.

Do not determine whether a treaty change should occur.

Identify only existing configuration/data locations that appear
safe for explicit human editing.

Return strict JSON.

USER

Treaty manifest:
{{manifest}}

Available configuration paths:
{{configuration_paths}}

Known reconciliation mappings:
{{rule_mappings}}

Identify candidate editable blocks.
```

---

# 79. Editable Block Output

```json
{
  "blocks": [
    {
      "block_id": "block_001",
      "treaty_id": "WST30465",
      "clause_id": "SW11",
      "block_type": "UPDATE_PARAMETER",
      "parameter": "limit",
      "path": "/clauses/SW11/parameters/limit",
      "current_value": 5000000,
      "editable": true,
      "confidence": 0.95
    }
  ]
}
```

Python must validate every returned block before exposing it as editable.

---

# 80. LLM Output Validation

LLM output passes through:

```text
JSON parsing
      ↓
Pydantic validation
      ↓
Path existence check
      ↓
Schema compatibility
      ↓
Source reference verification
      ↓
Permission policy
      ↓
Editable block registry
```

An invalid result is discarded.

---

# 81. LLM Caching

Cache discovery results using:

```text
source artifact versions
source content hashes
profile hash
prompt version
output schema version
model version
```

Example:

```json
{
  "cache_key": "sha256(...)",
  "operation": "TREATY_DISCOVERY",
  "prompt_version": "treaty-discovery-v1",
  "schema_version": "manifest-v1",
  "model": "configured-model",
  "evidence_hash": "sha256:...",
  "response": {}
}
```

Never reuse discovery results if the underlying evidence changed.

---

# 82. LLM Token Budget

Recommended application limits:

| Operation                | Input target | Output target |
| ------------------------ | -----------: | ------------: |
| Treaty identification    |      ≤ 1,500 |         ≤ 300 |
| Clause discovery         |      ≤ 2,000 |         ≤ 500 |
| Parameter discovery      |      ≤ 2,500 |         ≤ 600 |
| Editable block discovery |      ≤ 2,500 |         ≤ 600 |

These are application-level limits.

The Python evidence generator should summarize data before the LLM call.

---

# 83. No-LLM Mode

Treaty Management must work without an LLM.

```yaml
llm:
  enabled: false
```

Behavior:

```text
Structured fields
     ↓
Python discovery
     ↓
Regex / schema heuristics
     ↓
Cross-source matching
     ↓
Manifest
     ↓
Human confirmation
```

Ambiguous components become:

```text
DISCOVERY_REVIEW_REQUIRED
```

rather than being guessed silently.

---

# 84. Reconciliation Execution with Treaty State

API:

```http
POST /api/v1/reconciliations
```

Request:

```json
{
  "claims_mapping_version": "cm_v8",
  "subledger_version": "sl_v4",
  "pivot_version": "pivot_v3",
  "reconciliation_config_version": "rc_v5",
  "treaty_state_id": "state_wst30465_v2",
  "run_type": "SCENARIO"
}
```

---

# 85. Baseline Run Example

```json
{
  "run_id": "run_baseline_001",
  "treaty_state_id": "state_wst30465_v1",
  "run_type": "BASELINE",
  "status": "SUCCEEDED",
  "summary": {
    "groups": 1000,
    "matched": 920,
    "within_tolerance": 38,
    "unreconciled": 42
  },
  "variance": {
    "absolute": 250000
  }
}
```

---

# 86. Scenario Run Example

```json
{
  "run_id": "run_scenario_001",
  "treaty_state_id": "state_wst30465_v2",
  "parent_run_id": "run_baseline_001",
  "run_type": "SCENARIO",
  "status": "SUCCEEDED",
  "summary": {
    "groups": 1000,
    "matched": 949,
    "within_tolerance": 38,
    "unreconciled": 13
  },
  "variance": {
    "absolute": 75000
  }
}
```

---

# 87. Scenario Comparison

```json
{
  "comparison_id": "cmp_wst30465_001",
  "baseline": {
    "run_id": "run_baseline_001",
    "state_id": "state_wst30465_v1",
    "absolute_variance": 250000,
    "unreconciled_groups": 42
  },
  "scenario": {
    "run_id": "run_scenario_001",
    "state_id": "state_wst30465_v2",
    "absolute_variance": 75000,
    "unreconciled_groups": 13
  },
  "delta": {
    "absolute_variance": -175000,
    "unreconciled_groups": -29
  },
  "resolved_exception_count": 31,
  "new_exception_count": 2,
  "persistent_exception_count": 11
}
```

---

# 88. State Comparison Algorithm

```python
def compare_runs(baseline, scenario):
    return {
        "variance_delta": (
            scenario.absolute_variance
            - baseline.absolute_variance
        ),
        "unreconciled_delta": (
            scenario.unreconciled_groups
            - baseline.unreconciled_groups
        ),
        "resolved": find_resolved_exceptions(
            baseline,
            scenario
        ),
        "new": find_new_exceptions(
            baseline,
            scenario
        ),
        "persistent": find_persistent_exceptions(
            baseline,
            scenario
        )
    }
```

No LLM is required.

---

# 89. Exception-Level Scenario Comparison

Each baseline exception should be classified:

```text
RESOLVED
PERSISTENT
CHANGED
NEW
```

Example:

```json
{
  "exception_id": "exc_1001",
  "baseline_status": "UNRECONCILED",
  "scenario_status": "MATCH",
  "scenario_classification": "RESOLVED",
  "affected_by": [
    "op_003",
    "op_004"
  ]
}
```

---

# 90. Causal Attribution Boundary

The system may deterministically establish:

```text
exception changed after operation X
```

It must not automatically establish:

```text
operation X is the true business cause
```

The report should therefore distinguish:

```text
Observed impact
```

from:

```text
Business explanation
```

---

# 91. Treaty Management Report

Required sections:

```text
1. Treaty Overview
2. Baseline State
3. Scenario State
4. Change Set
5. State Diff
6. Affected Data
7. Baseline Reconciliation
8. Scenario Reconciliation
9. Reconciliation Comparison
10. Resolved Exceptions
11. Persistent Exceptions
12. New Exceptions
13. Lineage
14. Validation Results
15. Audit History
16. Human Decision
```

---

# 92. Example Human Decision

```json
{
  "decision_id": "decision_001",
  "state_id": "state_wst30465_v2",
  "decision": "ACCEPT_SCENARIO",
  "actor": "treaty_approver_7",
  "timestamp": "2026-09-30T16:30:00Z",
  "reason": "Treaty amendment documentation confirms the clause changes.",
  "evidence": [
    "external_document_2026_page_17",
    "comparison_cmp_wst30465_001"
  ]
}
```

The decision is a human action, not an LLM output.

---

# 93. CLI Interface

Recommended commands:

```bash
treaty list
```

```bash
treaty manifest WST30465
```

```bash
treaty discover WST30465
```

```bash
treaty blocks WST30465
```

```bash
treaty state list WST30465
```

```bash
treaty state show state_wst30465_v1
```

```bash
treaty patch validate patch.json
```

```bash
treaty patch apply patch.json
```

```bash
treaty state rollback state_wst30465_v1
```

```bash
treaty reconcile \
  --treaty-state state_wst30465_v2 \
  --subledger sl_v4 \
  --claims-mapping cm_v8
```

```bash
treaty compare \
  --baseline run_baseline_001 \
  --scenario run_scenario_001
```

---

# 94. REST API

## List Treaties

```http
GET /api/v1/treaties
```

## Get Treaty

```http
GET /api/v1/treaties/{treaty_id}
```

## Discover Treaty

```http
POST /api/v1/treaties/{treaty_id}/discover
```

## Get Manifest

```http
GET /api/v1/treaties/{treaty_id}/manifest
```

## Get Editable Blocks

```http
GET /api/v1/treaties/{treaty_id}/editable-blocks
```

## Propose Editable Blocks

```http
POST /api/v1/treaties/{treaty_id}/editable-blocks/propose
```

## Validate Patch

```http
POST /api/v1/treaties/{treaty_id}/patches/validate
```

## Apply Patch

```http
POST /api/v1/treaties/{treaty_id}/patches
```

## List States

```http
GET /api/v1/treaties/{treaty_id}/states
```

## Get State

```http
GET /api/v1/treaties/{treaty_id}/states/{state_id}
```

## Rollback

```http
POST /api/v1/treaties/{treaty_id}/states/{state_id}/rollback
```

## Compare States

```http
GET /api/v1/treaties/{treaty_id}/states/compare?from={state_a}&to={state_b}
```

## Run Reconciliation

```http
POST /api/v1/reconciliations
```

## Compare Runs

```http
GET /api/v1/reconciliations/compare?baseline={run_a}&scenario={run_b}
```

---

# 95. Apply Patch API Example

```http
POST /api/v1/treaties/WST30465/patches
```

```json
{
  "base_state_id": "state_wst30465_v1",
  "reason": "Test reported treaty amendment",
  "operations": [
    {
      "op": "REMOVE",
      "path": "/clauses/SW7"
    },
    {
      "op": "ADD",
      "path": "/clauses/SW2",
      "value": {
        "clause_id": "SW2",
        "clause_type": "LIMIT",
        "effective_from": "2025-07-01",
        "parameters": {
          "limit": {
            "value": 2500000,
            "currency": "USD"
          }
        },
        "rule_set_id": "RULESET_SW2"
      }
    },
    {
      "op": "REPLACE",
      "path": "/clauses/SW11/effective_from",
      "value": "2025-07-01"
    },
    {
      "op": "REPLACE",
      "path": "/clauses/SW11/parameters/limit/value",
      "value": 7500000
    }
  ]
}
```

---

# 96. Response

```json
{
  "status": "CREATED",
  "state_id": "state_wst30465_v2",
  "parent_state_id": "state_wst30465_v1",
  "change_set_id": "cs_wst30465_001",
  "content_hash": "sha256:...",
  "validation": {
    "schema": "PASS",
    "types": "PASS",
    "dates": "PASS",
    "references": "PASS",
    "business_rules": "PASS"
  }
}
```

---

# 97. Failure Response

```json
{
  "status": "REJECTED",
  "error_code": "INVALID_PATCH",
  "errors": [
    {
      "operation_id": "op_004",
      "path": "/clauses/SW11/parameters/limit/value",
      "code": "VALUE_BELOW_MINIMUM",
      "message": "Limit must be >= 0."
    }
  ],
  "state_created": false
}
```

---

# 98. Python Package Structure

Add Treaty Management as a dedicated package under the reconciliation domain.

```text
backend/
└── domain/
    └── reconciliation/
        ├── treaties/
        │   ├── __init__.py
        │   ├── models.py
        │   ├── manifest.py
        │   ├── discovery.py
        │   ├── heuristics.py
        │   ├── parameters.py
        │   ├── clauses.py
        │   ├── editable_blocks.py
        │   ├── patches.py
        │   ├── validator.py
        │   ├── applier.py
        │   ├── evaluator.py
        │   ├── effective_view.py
        │   ├── diff.py
        │   ├── state.py
        │   ├── branching.py
        │   ├── rollback.py
        │   ├── comparison.py
        │   ├── lineage.py
        │   ├── permissions.py
        │   ├── audit.py
        │   └── llm_discovery.py
        │
        ├── reconciliation/
        │   ├── engine.py
        │   ├── variance.py
        │   └── status.py
        │
        ├── diagnostics/
        └── reporting/
```

---

# 99. Core Python Models

```python
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel
from typing import Literal


class TreatyState(BaseModel):
    state_id: str
    treaty_id: str
    state_type: Literal[
        "BASELINE",
        "SCENARIO",
        "BRANCH",
        "ROLLBACK",
        "APPROVED",
        "SUPERSEDED"
    ]
    parent_state_id: str | None
    root_state_id: str
    version_number: int
    created_at: datetime
    created_by: str
    change_set_id: str | None
    reason: str
    content_hash: str
    schema_version: str
```

---

# 100. Patch Models

```python
class PatchOperation(BaseModel):
    operation_id: str
    op: Literal["ADD", "REMOVE", "REPLACE"]
    path: str
    value: object | None = None
    old_value: object | None = None
    block_id: str | None = None


class ChangeSet(BaseModel):
    change_set_id: str
    treaty_id: str
    base_state_id: str
    created_by: str
    created_at: datetime
    reason: str
    operations: list[PatchOperation]
```

---

# 101. State Creation Service

```python
class TreatyStateService:

    def create_state(
        self,
        base_state_id: str,
        change_set: ChangeSet,
        actor: str,
    ) -> TreatyState:

        base = self.store.get_state(base_state_id)

        self.permissions.require_editor(actor)

        self.validator.validate_change_set(
            base,
            change_set
        )

        working_copy = deepcopy(base.content)

        for operation in change_set.operations:
            self.applier.apply(
                working_copy,
                operation
            )

        self.validator.validate_complete_state(
            working_copy
        )

        return self.store.persist_new_state(
            parent=base,
            content=working_copy,
            change_set=change_set,
            actor=actor
        )
```

---

# 102. Treaty Evaluation Service

```python
class TreatyEvaluationService:

    def evaluate(
        self,
        dataset,
        treaty_state
    ):
        result = []

        for row in dataset:
            treaty = self.resolve_treaty(
                row,
                treaty_state
            )

            clauses = self.active_clauses(
                treaty,
                row
            )

            evaluated = self.evaluate_clauses(
                row,
                clauses
            )

            result.append(evaluated)

        return result
```

---

# 103. Effective View Construction

```python
def build_effective_view(
    unified_subledger,
    treaty_state,
    reconciliation_config
):
    treaty_evaluation = evaluate_treaty(
        unified_subledger,
        treaty_state
    )

    return apply_reporting_rules(
        treaty_evaluation,
        reconciliation_config
    )
```

The returned view is derived and immutable.

---

# 104. State Comparison Service

```python
class TreatyComparisonService:

    def compare_states(self, state_a, state_b):
        return diff_json(
            state_a.content,
            state_b.content
        )

    def compare_runs(self, baseline, scenario):
        return {
            "variance_delta": (
                scenario.absolute_variance
                - baseline.absolute_variance
            ),
            "resolved": self.resolved(
                baseline,
                scenario
            ),
            "new": self.new(
                baseline,
                scenario
            ),
            "persistent": self.persistent(
                baseline,
                scenario
            )
        }
```

---

# 105. Database Model

Minimum relational entities:

```text
treaties
treaty_manifests
treaty_clauses
treaty_parameters
treaty_rule_mappings
treaty_editable_blocks
treaty_change_sets
treaty_change_operations
treaty_states
treaty_state_artifacts
treaty_state_lineage
treaty_state_comparisons
treaty_reconciliation_runs
treaty_decisions
treaty_audit_events
```

Existing reconciliation entities remain responsible for:

```text
reconciliation_runs
findings
variance_records
reports
```

---

# 106. Recommended Treaty Tables

## `treaties`

```text
treaty_id
name
status
created_at
created_by
```

## `treaty_states`

```text
state_id
treaty_id
parent_state_id
root_state_id
state_type
version_number
content_hash
schema_version
created_at
created_by
reason
status
```

## `treaty_change_sets`

```text
change_set_id
treaty_id
base_state_id
created_by
created_at
reason
status
```

## `treaty_change_operations`

```text
operation_id
change_set_id
operation
path
old_value
new_value
block_id
validation_status
```

## `treaty_state_comparisons`

```text
comparison_id
baseline_state_id
scenario_state_id
baseline_run_id
scenario_run_id
created_at
created_by
```

---

# 107. State Storage

Recommended logical storage:

```text
/treaties
    /WST30465
        /manifests
        /states
            /state_v1
            /state_v2
            /state_v3
        /change_sets
        /comparisons
        /audit
```

The full state snapshot may be stored as:

```text
JSON
YAML
Parquet
database JSONB
```

depending on deployment requirements.

The database must retain:

```text
state metadata
parent relationships
hashes
audit references
```

---

# 108. Idempotency

State creation should use:

```text
base_state_id
+
canonical change_set
+
schema_version
+
engine_version
```

to produce a deterministic operation fingerprint.

Example:

```python
fingerprint = sha256(
    canonical_json({
        "base_state": base_state_id,
        "change_set": change_set,
        "schema_version": schema_version,
        "engine_version": engine_version
    })
)
```

If the same request has already succeeded:

```text
return existing state
```

instead of creating a duplicate.

---

# 109. Security

Treaty configuration should be classified as at least:

```text
CONFIDENTIAL
```

and potentially:

```text
FINANCIAL
```

depending on content.

Security controls:

```text
authentication
authorization
role-based access
audit logging
encryption at rest
encryption in transit
secret management
immutable audit storage
```

---

# 110. Sensitive Data Handling

Treaty discovery should minimize sensitive data.

Before LLM use:

```text
Raw data
   ↓
Relevant treaty scope
   ↓
Column profiling
   ↓
Identifier masking
   ↓
Compact evidence
   ↓
LLM
```

Stable pseudonyms may be used when relationships between identifiers matter.

---

# 111. Auditability Requirements

The system must answer:

```text
Who changed the treaty?
When?
Why?
From which state?
What exactly changed?
Which clauses changed?
Which parameters changed?
Which records were affected?
Which reconciliation runs used the state?
What was the reconciliation result before?
What was the reconciliation result after?
Who approved the change?
```

If any answer cannot be reconstructed from persisted artifacts, the implementation is incomplete.

---

# 112. Reproducibility

A reconciliation run must be reproducible from:

```text
Claims Mapping version
+
Unified Subledger version
+
Pivot version
+
Reconciliation configuration version
+
Treaty state ID
+
Adjustment state
+
Engine version
```

Example:

```json
{
  "reproducibility": {
    "claims_mapping": "cm_v8",
    "subledger": "sl_v4",
    "pivot": "pivot_v3",
    "reconciliation_config": "rc_v5",
    "treaty_state": "state_wst30465_v2",
    "adjustment_state": "adj_v2",
    "engine_version": "recon-1.4.0"
  }
}
```

---

# 113. Testing Strategy

## 113.1 Unit Tests

Test:

```text
manifest parsing
treaty identification
clause identification
parameter extraction
date validation
type validation
referential integrity
patch ADD
patch REMOVE
patch REPLACE
state creation
state hashing
state diff
branching
rollback
conflict detection
effective-date evaluation
clause evaluation
```

---

# 114. Patch Tests

### Add Clause

```python
def test_add_clause():
    state = apply_patch(
        base_state,
        add_sw2_patch
    )

    assert "SW2" in state.clauses
```

### Remove Clause

```python
def test_remove_clause():
    state = apply_patch(
        base_state,
        remove_sw7_patch
    )

    assert "SW7" not in state.clauses
```

### Update Parameter

```python
def test_update_limit():
    state = apply_patch(
        base_state,
        update_sw11_limit_patch
    )

    assert (
        state.clauses["SW11"]
        .parameters["limit"]
        == Decimal("7500000")
    )
```

---

# 115. Immutability Tests

```python
def test_base_state_is_unchanged():
    before = store.get_state("state_v1")

    create_state(
        base_state_id="state_v1",
        change_set=patch
    )

    after = store.get_state("state_v1")

    assert before.content_hash == after.content_hash
```

---

# 116. Rollback Tests

```python
def test_rollback_creates_new_state():
    rollback = rollback_to("state_v1")

    assert rollback.state_id != "state_v1"

    assert (
        rollback.content_hash
        == store.get_state("state_v1").content_hash
    )
```

---

# 117. Branching Tests

```python
def test_scenarios_do_not_mutate_parent():
    scenario_a = create_state(
        base_state_id="state_v1",
        change_set=patch_a
    )

    scenario_b = create_state(
        base_state_id="state_v1",
        change_set=patch_b
    )

    assert scenario_a.parent_state_id == "state_v1"
    assert scenario_b.parent_state_id == "state_v1"
    assert scenario_a.content_hash != scenario_b.content_hash
```

---

# 118. Reconciliation Regression Tests

For each treaty fixture:

```text
Baseline State
      +
Expected Scenario State
      ↓
Effective View
      ↓
Expected Aggregate
      ↓
Expected Reconciliation
```

Changing treaty logic must not silently alter previously approved historical runs.

---

# 119. WST30465 Regression Fixture

```json
{
  "treaty_id": "WST30465",
  "baseline_state": "state_v1",
  "scenario": {
    "remove_clause": "SW7",
    "add_clause": "SW2",
    "sw2_effective_from": "2025-07-01",
    "sw11_effective_from": "2025-07-01",
    "sw11_limit": 7500000
  },
  "expected": {
    "baseline_run_exists": true,
    "scenario_run_exists": true,
    "baseline_unchanged": true,
    "scenario_has_new_state": true
  }
}
```

---

# 120. LLM Evaluation

The LLM is evaluated only for:

```text
treaty identification
clause identification
parameter identification
editable block identification
source-reference accuracy
JSON validity
```

Do not evaluate it as a reconciliation engine.

Important metrics:

```text
JSON validity
schema compliance
component identification accuracy
source-location accuracy
false editable-block rate
unsupported-claim rate
human override rate
```

---

# 121. LLM Safety Tests

Test that the LLM cannot:

```text
return a patch
claim a patch was applied
change a value
approve a clause
state that reconciliation improved
request arbitrary code execution
invent a source reference
invent a clause
```

If the output violates the discovery schema:

```text
discard response
```

---

# 122. Failure Modes

## Unknown Treaty

```text
Discovery
   ↓
No reliable treaty identifier
   ↓
DISCOVERY_REVIEW_REQUIRED
```

No state modification is permitted.

---

## Ambiguous Clause

```text
Possible SW11
Possible SWII
```

Return:

```text
AMBIGUOUS_COMPONENT
```

and request human confirmation.

---

## Invalid Patch

```text
PATCH_REJECTED
```

No state created.

---

## Missing Rule Set

```text
RULE_SET_NOT_FOUND
```

No state created if the mapping is mandatory.

---

## Invalid Effective Date

```text
INVALID_EFFECTIVE_DATE
```

No state created.

---

## State Conflict

```text
BASE_STATE_STALE
```

No state created.

---

## Reconciliation Failure

The treaty state remains valid.

The reconciliation run is marked:

```text
FAILED
```

and can be retried without recreating the treaty state.

---

# 123. Recovery

Each stage should be independently recoverable.

```text
Discovery
    ↓
Manifest
    ↓
State
    ↓
Effective View
    ↓
Reconciliation
    ↓
Comparison
```

If reconciliation fails:

```text
reuse treaty state
```

If comparison fails:

```text
reuse baseline/scenario runs
```

If LLM discovery fails:

```text
continue with deterministic discovery
```

---

# 124. UI Information Architecture

Recommended placement:

```text
Reconciliation
│
├── Overview
│
├── Inputs
│   ├── Claims Mapping
│   ├── Subledger
│   └── Treaty
│
├── Treaty Management
│   ├── Manifest
│   ├── Clauses
│   ├── Parameters
│   ├── Editable Blocks
│   ├── Change Sets
│   ├── States
│   ├── Scenarios
│   └── History
│
├── Reconciliation
│   ├── Baseline
│   ├── Scenario Runs
│   ├── Comparison
│   └── Exceptions
│
└── Audit
```

---

# 125. Treaty Manifest UI

Example:

```text
┌─────────────────────────────────────────────────────┐
│ Treaty: WST30465                                    │
│ Effective: 01-Jan-2024 → 31-Dec-2026               │
├─────────────────────────────────────────────────────┤
│ Clauses                                             │
│                                                     │
│ SW11     LIMIT       5,000,000 USD      [Edit]     │
│ SW7      LIMIT       3,000,000 USD      [Edit]     │
│ SW5      RATE        10%                 [Edit]     │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [Create Scenario] [View History] [Compare States]  │
└─────────────────────────────────────────────────────┘
```

---

# 126. Editable Block UI

When selecting SW11:

```text
SW11
────────────────────────────────────────

Effective From
Current: 01-Jan-2025
[ Change ]

Limit
Current: USD 5,000,000
[ Change ]

Rate
Current: 15%
[ Change ]

Rule Set
RULESET_SW11
[ Change ]

Source
Treaty Config v1
Path: $.clauses.SW11
```

The user must explicitly submit each modification.

---

# 127. Scenario Builder

```text
Create Treaty Scenario
──────────────────────────────────────

Base State:
[ WST30465 v1 ]

Reason:
[ Test reported amendment ]

Changes:

[x] Remove SW7

[x] Add SW2
    Effective: 01-Jul-2025
    Limit: USD 2,500,000

[x] Update SW11
    Effective: 01-Jul-2025
    Limit: USD 7,500,000

[Validate Changes]

[Create Scenario]
```

---

# 128. Validation Preview

Before creating the state:

```text
Change Validation
────────────────────────────────────────

REMOVE SW7                         PASS
ADD SW2                            PASS
SW2 effective date                PASS
SW11 effective date               PASS
SW11 limit                        PASS
Rule references                   PASS
Date consistency                 PASS
Permission                       PASS

Result:
4 operations valid

[Create Immutable Scenario]
```

---

# 129. Scenario Comparison UI

```text
WST30465 — Treaty Impact
────────────────────────────────────────

                    Baseline      Scenario
State               v1            v2

Variance             $250,000      $75,000
Unreconciled             42           13
Matched                  920          949

Resolved exceptions                    31
New exceptions                           2
Persistent exceptions                  11

Changed clauses:
- SW7 removed
- SW2 added
- SW11 effective date changed
- SW11 limit changed

[View Resolved] [View Persistent] [View New]
```

---

# 130. History UI

```text
WST30465 State History

v1   BASELINE
     Created by System
     01-Sep-2026

     │
     ├── v2   SCENARIO
     │         User: user_42
     │         Remove SW7
     │         Add SW2
     │
     └── v3   SCENARIO
               User: user_51
               Update SW11
```

---

# 131. Human Approval UI

```text
Scenario: WST30465 v2

Changes:
✓ SW7 removed
✓ SW2 added
✓ SW11 start date changed
✓ SW11 limit changed

Reconciliation impact:
Variance: $250K → $75K
Unreconciled groups: 42 → 13

Evidence:
[View Treaty Source]
[View State Diff]
[View Lineage]
[View Reconciliation Comparison]

Decision:

[Approve State]
[Reject State]
[Keep as Scenario]
```

---

# 132. End-to-End Workflow

```text
1. Load Claims Mapping
       ↓
2. Load Unified Subledger
       ↓
3. Load Treaty Sources
       ↓
4. Discover Treaty
       ↓
5. Generate Manifest
       ↓
6. Validate Manifest
       ↓
7. Generate Editable Blocks
       ↓
8. User selects treaty change
       ↓
9. Create structured Change Set
       ↓
10. Validate Change Set
       ↓
11. Apply patch in Python
       ↓
12. Create immutable Treaty State
       ↓
13. Record audit event
       ↓
14. Build treaty-aware effective view
       ↓
15. Run baseline reconciliation
       ↓
16. Run scenario reconciliation
       ↓
17. Compare reconciliation results
       ↓
18. Inspect changed exceptions
       ↓
19. Human reviews treaty evidence
       ↓
20. Approve / reject / retain scenario
       ↓
21. Persist decision
```

---

# 133. Reference End-to-End Service

```python
class TreatyManagementService:

    def discover(self, sources):
        profiles = self.discovery.profile(sources)

        manifest = self.discovery.detect(
            profiles
        )

        return manifest

    def propose_blocks(self, manifest, sources):
        deterministic = (
            self.block_discovery.find(manifest)
        )

        if deterministic:
            return deterministic

        if not self.llm.enabled:
            return []

        evidence = self.llm_builder.build(
            manifest,
            sources
        )

        proposal = self.llm.discover_blocks(
            evidence
        )

        return self.validator.validate_blocks(
            proposal,
            manifest
        )

    def apply_change_set(
        self,
        base_state_id,
        change_set,
        actor
    ):
        return self.state_service.create_state(
            base_state_id=base_state_id,
            change_set=change_set,
            actor=actor
        )

    def rollback(
        self,
        current_state_id,
        target_state_id,
        actor,
        reason
    ):
        return self.state_service.rollback(
            current_state_id=current_state_id,
            target_state_id=target_state_id,
            actor=actor,
            reason=reason
        )

    def compare(
        self,
        baseline_run,
        scenario_run
    ):
        return self.comparison.compare_runs(
            baseline_run,
            scenario_run
        )
```

---

# 134. Complete Reconciliation Integration

```python
def run_treaty_scenario(request):

    claims_mapping = load_claims_mapping(
        request.claims_mapping_version
    )

    unified_subledger = load_subledger(
        request.subledger_version
    )

    treaty_state = treaty_manager.get_state(
        request.treaty_state_id
    )

    effective_view = treaty_manager.build_effective_view(
        unified_subledger,
        treaty_state
    )

    result = reconciliation_engine.reconcile(
        reported=claims_mapping,
        subledger=effective_view,
        config=request.reconciliation_config
    )

    findings = diagnostics.run(
        result=result,
        deterministic_only=True
    )

    return persist_run(
        result=result,
        findings=findings,
        treaty_state_id=treaty_state.state_id
    )
```

---

# 135. Important Architectural Separation

The implementation should maintain four distinct concepts:

```text
1. Treaty Definition
2. Treaty State
3. Treaty Evaluation
4. Reconciliation Result
```

They must not be collapsed into one object.

### Treaty Definition

What the treaty says.

### Treaty State

Which version of the treaty configuration is being tested.

### Treaty Evaluation

How that state applies to specific records.

### Reconciliation Result

What happened when the evaluated data was reconciled.

---

# 136. Example Lifecycle for WST30465

```text
BASELINE
WST30465 v1

Clauses:
SW11
SW7
SW5

        │
        │ user proposes amendment
        ▼

SCENARIO
WST30465 v2

Clauses:
SW11
SW5
SW2

SW11:
start = 01-Jul-2025
limit = 7.5M

SW2:
start = 01-Jul-2025
limit = 2.5M

        │
        ▼

RECONCILIATION

Before:
variance = $250K

After:
variance = $75K

        │
        ▼

COMPARISON

29 fewer unreconciled groups
31 exceptions resolved
2 new exceptions
11 persistent
```

The final interpretation remains subject to human confirmation and supporting treaty evidence.

---

# 137. Definition of Done

## Discovery

* [ ] Treaty identifiers can be discovered.
* [ ] Effective periods can be discovered.
* [ ] Clauses can be discovered.
* [ ] Parameters can be discovered.
* [ ] Source references are retained.
* [ ] Discovery confidence is retained.
* [ ] Discovery confidence cannot authorize changes.

## Editable Blocks

* [ ] Add clause supported.
* [ ] Remove clause supported.
* [ ] Update clause supported.
* [ ] Update effective dates supported.
* [ ] Update numeric parameters supported.
* [ ] Update rule mappings supported.
* [ ] Editable paths are schema validated.

## Versioning

* [ ] Original state is immutable.
* [ ] Every change creates a new state.
* [ ] Parent state is recorded.
* [ ] Change set is recorded.
* [ ] State content hash is recorded.
* [ ] Branching is supported.
* [ ] Rollback creates a new state.
* [ ] Historical states remain available.

## Python Change Engine

* [ ] Patch schema validation.
* [ ] Type validation.
* [ ] Date validation.
* [ ] Referential-integrity validation.
* [ ] Business-rule validation.
* [ ] Atomic patch application.
* [ ] Conflict detection.
* [ ] Full lineage.

## Reconciliation

* [ ] Baseline state can be reconciled.
* [ ] Scenario state can be reconciled.
* [ ] State ID is persisted in every run.
* [ ] Run comparison is deterministic.
* [ ] Variance changes are calculated.
* [ ] Resolved exceptions are identified.
* [ ] Persistent exceptions are identified.
* [ ] New exceptions are identified.
* [ ] Affected rows can be traced.

## LLM

* [ ] LLM limited to discovery.
* [ ] LLM receives summaries only.
* [ ] LLM cannot apply patches.
* [ ] LLM cannot approve changes.
* [ ] LLM cannot evaluate reconciliation outcomes.
* [ ] LLM output is strict JSON.
* [ ] LLM output is schema validated.
* [ ] LLM results are cached.
* [ ] No-LLM mode works.

## Audit & Security

* [ ] Every mutation is audited.
* [ ] Every state has an actor.
* [ ] Every state has a reason.
* [ ] Every state has a parent.
* [ ] Every reconciliation records treaty state.
* [ ] Editor/approver separation is supported.
* [ ] Audit history is append-only.
* [ ] Source data remains immutable.

---

# 138. Final Architecture

```text
                              USER
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
              ▼                                   ▼
      Treaty Management UI                 Reconciliation UI
              │                                   │
              ▼                                   ▼
      ┌───────────────┐                 ┌──────────────────┐
      │ Treaty API    │                 │ Reconciliation   │
      └───────┬───────┘                 │ API              │
              │                         └────────┬─────────┘
              ▼                                  │
      ┌───────────────┐                          │
      │ Discovery     │                          │
      └───────┬───────┘                          │
              │                                  │
       ┌──────┴──────┐                           │
       ▼             ▼                           │
   Python        Optional LLM                    │
   Discovery     Discovery Aid                   │
       │             │                           │
       └──────┬──────┘                           │
              ▼                                  │
        Treaty Manifest                           │
              │                                  │
              ▼                                  │
       Editable Blocks                            │
              │                                  │
              ▼                                  │
       User Change Set                            │
              │                                  │
              ▼                                  │
      Python Validation                           │
              │                                  │
              ▼                                  │
       Patch Application                           │
              │                                  │
              ▼                                  │
       Immutable State                            │
              │                                  │
       ┌──────┴───────────────┐                  │
       │                      │                  │
       ▼                      ▼                  ▼
   Baseline                Scenario       Unified Subledger
    State                    State              │
       │                      │                 │
       └──────────┬───────────┘                 │
                  ▼                             │
          Effective Treaty View ◄───────────────┘
                  │
                  ▼
          Reconciliation Engine
                  │
                  ▼
         Deterministic Results
                  │
                  ▼
          State Comparison
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   Improved / Changed    Persistent
        │                   │
        └─────────┬─────────┘
                  ▼
             Human Review
                  │
       ┌──────────┼───────────┐
       ▼          ▼           ▼
    Approve     Reject      Scenario
       │
       ▼
 Active Treaty State
       │
       ▼
 Reproducible Future
 Reconciliation Runs
```

---

# 139. Final Engineering Rules

1. **Treaty states are immutable.**
2. **Original treaty configuration is never overwritten.**
3. **Every edit is represented as a structured change set.**
4. **Every change set is applied by Python.**
5. **Every state has a parent state.**
6. **Rollback creates a new state rather than deleting history.**
7. **Branching is the preferred mechanism for what-if scenarios.**
8. **Treaty clauses and parameters are independently addressable.**
9. **Effective dates are evaluated deterministically.**
10. **Treaty rule mappings are explicitly versioned.**
11. **The original financial data is never modified by treaty changes.**
12. **Treaty changes produce derived evaluation views.**
13. **Every affected record retains lineage to its source.**
14. **Every reconciliation run explicitly references a treaty state.**
15. **Baseline and scenario runs are independently immutable.**
16. **State-to-state and run-to-run comparisons are deterministic Python operations.**
17. **A reduction in reconciliation variance is an observed result, not automatic proof that the treaty change is correct.**
18. **The LLM is restricted to treaty structure and editable-block discovery.**
19. **The LLM never applies treaty modifications.**
20. **The LLM never decides which treaty modification should be made.**
21. **The LLM never validates reconciliation improvement.**
22. **The LLM never approves or promotes treaty states.**
23. **LLM inputs are compact evidence packages, not complete datasets.**
24. **All LLM outputs are schema validated.**
25. **No-LLM execution remains fully functional.**
26. **All treaty mutations require authorization.**
27. **Production promotion requires explicit human approval.**
28. **Audit events are append-only.**
29. **Every state is reproducible from its recorded inputs and configuration versions.**
30. **The Treaty Management Section is a state-management and controlled what-if layer, not an AI decision engine.**

The resulting Treaty Management Section therefore provides a controlled lifecycle for **discovering treaty structure, defining explicit user changes, creating immutable treaty states, testing those states against reconciliation, comparing their deterministic financial impact, and preserving a complete audit/rollback history** while keeping the LLM strictly outside the business-state mutation and reconciliation-decision path.
