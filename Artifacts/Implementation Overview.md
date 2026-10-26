# Intelligent Bordereaux & Treaty Data Platform

> **Implementation README / Product Specification / Solution Design**
>
> This specification combines the supplied Bordereaux requirements, the rough product ideas, and the supplied Databricks-inspired UX architecture reference. It is intended to be implementation-ready for an engineering/AI coding agent such as Claude, while leaving low-level implementation choices open where they do not affect product behavior.

---

## 1. Product Vision

Build an enterprise-grade **Bordereaux Intelligence Platform** that turns messy bordereaux and supporting treaty documents into trusted, standardized, reviewable, and reusable business data.

The platform is not just an Excel-cleaning tool. Its core intelligence is the ability to:

1. Detect the structure of unfamiliar bordereaux.
2. Understand source-field meaning using metadata **and actual values**.
3. Create a canonical `claims_mapping` / field-mapping artifact.
4. Resolve ambiguous financial columns using business relationships and numerical evidence.
5. Assign a confidence score to every proposed mapping.
6. Route uncertain mappings to a human reviewer.
7. Produce a standardized dataset and a pivot/aggregation output for downstream use.
8. Ingest and reconcile technical-subledger data.
9. Manage treaty versions and treaty clauses.
10. Simplify treaty/policy language and connect it to regulatory-compliance controls.
11. Preserve complete lineage, history, versions, audit evidence, and rollback.
12. Generate final reports and distribute them through integrations.
13. Expose observability, guardrails, and reusable processing procedures.

### Core product loop

```text
INGEST
  ↓
UNDERSTAND STRUCTURE
  ↓
PROFILE DATA
  ↓
MAP TO STANDARD
  ↓
REASON OVER AMBIGUITY
  ↓
SCORE CONFIDENCE
  ↓
AUTO-ACCEPT OR HUMAN REVIEW
  ↓
STANDARDIZE
  ↓
CLAIMS MAPPING + PIVOT AGGREGATION
  ↓
RECONCILE / APPLY TREATY LOGIC
  ↓
REPORT / SHARE
```

---

# 2. Source Requirements Incorporated

This specification is based on the following supplied materials:

- `Bordereaux Data Standardization.odt`
- `idea.txt`
- `databricks_ui_ux_architecture_reference(1).md`

The original requirements explicitly call for ingestion of inconsistent bordereaux, structure detection, normalization, semantic/context-aware mapping, confidence scoring, human validation, treaty-level figure extraction, standardized output, and reconciliation-ready data. The target standard is intended to align with applicable Lloyd's V5.2 and ACORD standards.

The UI reference establishes the architectural principles used here: stable global shell, hierarchical navigation, persona-aware experiences, progressive disclosure, global search, workspace/context navigation, object-centric pages, workflow build/run/observe separation, contextual inspectors, lineage, permission-aware UI, and layered complexity.

---

# 3. Product Principles

## 3.1 Do not clone Databricks

Use Databricks as a **UX architecture inspiration**, not as a visual/product clone.

Reuse the principles:

- stable application shell
- progressive disclosure
- contextual navigation
- object-centric resource pages
- technical + business hierarchies
- search-first discovery
- role/persona-aware presentation
- visual configuration + structured representation
- workflow definition separated from execution and monitoring
- deep lineage and auditability
- permission-aware actions

Do not copy:

- branding
- colors
- icons
- exact navigation labels
- exact page layouts
- product-specific terminology
- exact interactions

---

# 4. Target Users

## 4.1 Reinsurance Analyst

Primary tasks:

- upload and inspect bordereaux
- review detected structure
- review column mappings
- validate low-confidence mappings
- inspect data-quality issues
- review reconciliation differences
- create standardized outputs
- generate reports

## 4.2 Treaty / Business Specialist

Primary tasks:

- maintain treaty records
- inspect treaty clauses
- review extracted treaty figures
- compare treaty versions
- inspect policy/treaty obligations
- validate business rules

## 4.3 Reviewer / Approver

Primary tasks:

- review AI decisions
- accept/reject/correct mappings
- approve treaty changes
- review evidence
- create an auditable decision trail

## 4.4 Platform Administrator

Primary tasks:

- manage users/groups/roles
- configure thresholds and policies
- manage integrations
- manage standards and canonical schemas
- inspect platform health
- inspect audit events

## 4.5 Business Consumer

Primary tasks:

- view standardized datasets
- inspect reports/dashboards
- search published business assets
- consume approved outputs without seeing unnecessary technical complexity

---

# 5. Experience Architecture

The application should use a persistent desktop shell.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Logo │ Workspace / Project ▼ │ Global Search │ Notifications │ User ▼   │
├───────┬─────────────────┬────────────────────────────────────────────────┤
│       │                 │                                                │
│ Home  │ Context Tree    │             Primary Work Area                 │
│       │                 │                                                │
│ Intake│ Project         │                                                │
│ Map   │ ├─ Ingestion    │                                                │
│ Recon │ ├─ Dataset      │                                                │
│ Treaty│ ├─ Mapping Run  │                                                │
│ Data  │ ├─ Treaty       │                                                │
│ Report│ └─ Reports      │                                                │
│ Ops   │                 │                                                │
│ Admin │                 │                                                │
└───────┴─────────────────┴────────────────────────────────────────────────┘
```

### Navigation model

```text
ORGANIZATION
    ↓
WORKSPACE / PROJECT
    ↓
PRODUCT AREA
    ↓
RESOURCE COLLECTION
    ↓
RESOURCE
    ↓
RESOURCE SUB-VIEW
    ↓
ACTION
```

### Recommended top-level product areas

```text
HOME
DISCOVER
INTAKE
MAPPING STUDIO
RECONCILIATION
TREATIES & POLICIES
DATA
REPORTS
LINEAGE
OPERATIONS
GOVERNANCE
ADMIN
```

Do not show every technical feature to every user. Navigation and density should adapt to the user's role.

---

# 6. Homepage

The homepage is a **launchpad**, not only a dashboard.

It should contain:

```text
HOME
├── Primary action
│   └── Upload / Start Processing
├── Global search
├── Continue
│   ├── Recent ingestions
│   ├── Recent mapping runs
│   └── Recent reconciliation runs
├── Review queue
├── Data-quality alerts
├── Recent treaty changes
├── Favorite projects/assets
├── Recommended reusable procedures
└── System status / what's new
```

The most important home card should surface work requiring the user's action:

```text
12 mappings awaiting review
3 reconciliation variances require attention
2 treaty changes pending approval
1 failed ingestion
```

---

# 7. Discover and Search

Search is a first-class navigation mechanism.

Searchable objects:

- projects
- files
- ingestions
- datasets
- mapping runs
- mapping profiles
- treaties
- treaty clauses
- policies
- reconciliation runs
- reports
- pivot definitions
- audit events
- contacts
- users/groups
- connectors

Search should support:

- exact text
- prefix/fuzzy match
- type filters
- project filters
- owner filters
- status filters
- date filters
- semantic/AI-assisted search where available

Expected flow:

```text
QUERY
  ↓
IDENTIFY OBJECT TYPE
  ↓
APPLY ACCESS FILTERS
  ↓
RANK
  ↓
DISPLAY RESULT + CONTEXT
  ↓
OPEN OBJECT
```

---

# 8. Core Product Modules

## 8.1 Project / Workspace

A project is the primary unit of context and collaboration.

It groups:

- source files
- data assets
- mapping runs
- mapping profiles
- treaties
- reconciliation runs
- reports
- procedures
- audit/history

### Project actions

- create
- rename
- archive
- favorite
- share
- move
- clone
- export
- inspect activity
- manage access

---

# 9. Bordereaux Intake

## 9.1 Supported source patterns

The intake engine must support:

- CSV
- XLSX
- SAS datasets where applicable
- PDF supporting documents
- multiple files in one processing job
- inconsistent layouts
- multiple header rows
- subheaders
- metadata rows before the data
- merged/blank header cells
- inconsistent column names
- mixed data representations

### Intake workflow

```text
Upload
  ↓
File validation
  ↓
Source registration
  ↓
Structure detection
  ↓
Preview
  ↓
Confirm / Edit detected structure
  ↓
Start mapping
```

## 9.2 File ingestion functions

```text
validate_file(file)
register_source(file)
detect_file_type(file)
detect_encoding(file)
detect_sheets(file)
detect_header_rows(file)
detect_data_start(file)
detect_merged_headers(file)
detect_subheaders(file)
profile_columns(file)
sample_rows(file)
create_ingestion_snapshot(file)
```

## 9.3 Ingestion UI

Show:

- file name
- file type
- size
- upload status
- detected encoding
- sheets/tables
- header candidates
- data-start candidate
- row/column counts
- warnings
- sample preview
- schema preview

The user must be able to override automatically detected header/data boundaries.

---

# 10. Structure Detection

The structure detector determines how the file should be interpreted before semantic mapping.

### Detection targets

- number of header rows
- data-start row
- repeated headers
- blank separator rows
- grouped headers
- subheaders
- footnotes/totals
- non-data metadata
- hidden sheets/columns
- candidate primary table
- multiple tables in one file

### Output

```json
{
  "source": "bordereaux_2026.xlsx",
  "sheet": "Premium",
  "header_rows": [3, 4],
  "data_start_row": 5,
  "estimated_data_end_row": 4521,
  "ignored_rows": [1, 2, 4522, 4523],
  "columns": [...]
}
```

---

# 11. Canonical Standard Schema

The platform shall maintain a configurable canonical schema rather than hard-coding business fields throughout the application.

The canonical schema should support standards/reference sets such as:

- Lloyd's V5.2
- ACORD
- organization-specific extensions

Example canonical categories:

```text
Reference
Date / Period
Currency
Policy / Contract
Insured / Risk
Sum Insured
Premium
Commission
Net Premium
Tax
Share
Claims / Loss
Treaty information
Broker / Reinsurer / MGA information
Operational metadata
```

Every canonical field should have:

```text
field_id
standard_name
business_definition
data_type
format
allowed_values
aliases
category
required/optional
validation_rules
relationship_rules
applicability
version
```

The target schema must be versioned.

---

# 12. Semantic Mapping Engine

The mapping engine must **not** rely on column-name similarity alone.

## 12.1 Evidence sources

For every source field, inspect:

1. column name
2. header hierarchy
3. column position
4. data type
5. null/non-null behavior
6. sample values
7. value ranges
8. value distributions
9. repeated patterns
10. related columns
11. mathematical relationships
12. source-file context
13. historical approved mappings
14. selected canonical schema
15. treaty context where applicable

## 12.2 Candidate generation

```text
Source Column
     ↓
Alias / semantic retrieval
     ↓
Candidate canonical fields
     ↓
Candidate evidence collection
     ↓
Evidence scoring
     ↓
Ambiguity detection
     ↓
Business-rule validation
     ↓
Final proposal
```

## 12.3 Recommended service functions

```text
generate_mapping_candidates(source_column, source_context)
build_column_evidence(source_column, profile, structure, context)
score_mapping_candidate(candidate, evidence)
detect_mapping_ambiguity(candidates)
validate_mapping_business_rules(mapping)
generate_mapping_explanation(mapping)
persist_mapping_proposal(mapping)
```

---

# 13. Claims Mapping — Primary Business Artifact

The user's most important requirement is the generation of a reusable `claims_mapping` / field-mapping artifact.

It must link source data to canonical business meaning.

### Example

```text
Source field         Canonical field          Confidence
---------------------------------------------------------
Policy Ref           Reference                0.98
Effective Dt         Date                     0.96
Premium Amt          Gross Premium            0.91
Amount               Commission               0.58
```

The mapping artifact should contain:

```text
mapping_run_id
source_asset_id
source_field
source_column_index
source_header_path
canonical_field_id
mapping_type
confidence
evidence
reasoning_summary
validation_status
reviewer
review_timestamp
mapping_version
```

### Mapping statuses

```text
PROPOSED
AUTO_ACCEPTED
REVIEW_REQUIRED
APPROVED
REJECTED
OVERRIDDEN
SUPERSEDED
```

---

# 14. Ambiguous Financial Field Resolution

This is a high-value capability and must be implemented as a dedicated subsystem.

Example ambiguity:

```text
Source: "Amount"

Possible targets:
- Gross Premium
- Commission
- Net Premium
- Tax
- Share
```

The system should inspect numerical relationships.

For example:

```text
Gross Premium - Commission ≈ Net Premium
```

or:

```text
Commission / Gross Premium ≈ Commission %
```

or:

```text
Net / Gross ≈ Share %
```

## Financial reasoning engine

Functions:

```text
profile_numeric_relationships(dataset)
discover_arithmetic_relationships(columns)
test_formula_hypothesis(formula)
score_financial_semantics(candidate)
detect_outlier_rows()
produce_evidence_trace()
```

The result must contain a human-readable explanation, for example:

```text
"Amount" is proposed as Commission because:

- values are numeric currency amounts
- magnitude is materially lower than Premium Amt
- Amount + Net ≈ Gross Premium for 94.2% of sampled rows
- inferred commission ratio is within expected business range
- source context places Amount beside premium fields
```

The exact explanation must be generated from actual evidence; do not fabricate evidence.

---

# 15. Confidence Scoring

Every mapping proposal receives a confidence score.

Confidence must be a **calibrated evidence score**, not simply the LLM's self-reported confidence.

Recommended initial evidence groups:

```text
Semantic/header similarity       20%
Data-type/value evidence         20%
Header hierarchy/context         15%
Column position / layout          5%
Inter-column relationships       20%
Historical approved mappings      10%
AI semantic reasoning            10%
```

These are implementation defaults only and must be configurable and evaluated against a labeled validation set.

### Thresholds

Use configurable policy thresholds rather than hard-coding behavior.

Example demo configuration:

```text
HIGH       → auto-process
MEDIUM     → human review
LOW        → unresolved / blocked
```

The actual threshold values should be stored in configuration.

### Confidence payload

```json
{
  "confidence": 0.91,
  "band": "HIGH",
  "evidence": {
    "semantic": 0.94,
    "value": 0.91,
    "context": 0.88,
    "relationship": 0.93
  },
  "explanation": "..."
}
```

---

# 16. Human-in-the-Loop Review

Low-confidence or ambiguous mappings must be sent to an analyst.

## Review queue

Each item should show:

- source field
- proposed target
- confidence
- alternative candidates
- header context
- sample values
- statistics
- related fields
- inferred formulas
- AI explanation
- previous approved mappings
- reviewer decision controls

### Reviewer actions

```text
Accept
Reject
Select alternative
Map manually
Split / combine mapping where supported
Mark as intentionally unused
Add comment
Save as reusable rule
```

### Reviewer decisions are immutable evidence

Store:

- original proposal
- reviewer action
- prior value
- final value
- reviewer
- timestamp
- reason/comment
- mapping version

Do not overwrite review history.

---

# 17. Mapping Memory / Reusable Procedures

A key accelerator is learning from previously approved mappings.

Introduce **Reusable Processing Procedures** / **Mapping Profiles**.

Examples:

```text
ACME MGA Monthly Bordereaux
Carrier X Premium Template
Treaty Y Claims Feed
2026 Subledger Reconciliation
```

A procedure can contain:

- source detection rules
- header rules
- standard mappings
- transformations
- validation rules
- aggregation logic
- treaty rules
- report template
- notification rules

### Functions

```text
create_processing_profile()
clone_processing_profile()
apply_processing_profile()
save_approved_mapping_as_rule()
validate_profile_against_source()
publish_processing_profile()
rollback_processing_profile()
```

The system should preferentially reuse approved deterministic mappings before invoking expensive AI reasoning.

---

# 18. Standardization Engine

Once mappings are approved, transform the source into the canonical dataset.

### Standardization steps

```text
Raw Source
  ↓
Structure Clean-up
  ↓
Column Rename / Mapping
  ↓
Type Coercion
  ↓
Date Normalization
  ↓
Currency Normalization
  ↓
Value Standardization
  ↓
Business Rule Validation
  ↓
Canonical Dataset
```

### Transformation functions

```text
normalize_column_names()
normalize_dates()
normalize_currency()
normalize_numeric_fields()
normalize_nulls()
normalize_categories()
apply_field_transform()
apply_business_rule()
validate_canonical_schema()
write_standardized_dataset()
```

---

# 19. Claims Mapping Output + Pivot Table

The canonicalized dataset should be accompanied by a generated pivot/aggregation artifact.

The pivot layer must be based on the finalized `claims_mapping` and standardized dataset, not on the raw spreadsheet layout.

## Pivot definition

A pivot definition should specify:

```text
dimensions
measures
filters
grouping
sorting
currency treatment
rounding
```

Example:

```text
Rows:
  Treaty
  Reporting Period
  Currency

Measures:
  Gross Premium
  Commission
  Net Premium
  Sum Insured
```

### Functions

```text
create_pivot_definition()
validate_pivot_definition()
execute_pivot()
preview_pivot()
save_pivot()
clone_pivot()
export_pivot()
```

### Output

```text
Standardized Dataset
       +
Claims Mapping
       +
Pivot / Aggregation
```

---

# 20. Technical Subledger Reconciliation

Reconciliation is a first-class workflow.

## Inputs

- standardized bordereaux dataset
- technical subledger
- treaty/policy rules
- selected period
- reconciliation configuration

## Workflow

```text
Ingest Subledger
  ↓
Detect / Normalize Structure
  ↓
Apply Mapping Profile
  ↓
Standardize Subledger
  ↓
Match to Bordereaux
  ↓
Aggregate Both Sides
  ↓
Compare
  ↓
Calculate Variance
  ↓
Apply Tolerance Rules
  ↓
Generate Exceptions
  ↓
Reviewer Resolution
```

## Match dimensions

Configurable by business process, for example:

```text
Reference
Policy / Contract
Treaty
Reporting Period
Currency
Risk / Claim identifiers
```

## Reconciliation result states

```text
MATCHED
MATCHED_WITH_TOLERANCE
VARIANCE
MISSING_SOURCE
MISSING_SUBLEDGER
UNRESOLVED
REVIEWED
```

### Functions

```text
create_reconciliation_run()
standardize_subledger()
build_reconciliation_keys()
aggregate_for_reconciliation()
compare_datasets()
calculate_variance()
apply_tolerance()
create_exception()
resolve_exception()
approve_reconciliation()
generate_reconciliation_report()
```

---

# 21. Treaty Management

Treaties are first-class business objects.

## Treaty object

```text
Treaty
├── Overview
├── Parties / Contacts
├── Effective Period
├── Documents
├── Clauses
├── Financial Terms
├── Regulatory Controls
├── Related Bordereaux
├── Related Reconciliations
├── Change History
├── Lineage
└── Permissions
```

---

# 22. Treaty Simplifier

Create a separate treaty/policy intelligence workspace.

### Purpose

Convert complex policy/treaty language into a structured business understanding.

### Functions

```text
ingest_treaty_document()
extract_text_and_sections()
identify_treaty_clauses()
classify_clause()
simplify_clause()
extract_business_terms()
extract_thresholds()
extract_percentages()
extract_dates()
extract_obligations()
extract_exclusions()
link_clause_to_control()
generate_clause_summary()
```

### Output example

```text
Clause
  ↓
Simplified meaning
  ↓
Business obligation
  ↓
Financial / operational implication
  ↓
Regulatory control mapping
  ↓
Evidence / source location
  ↓
Reviewer status
```

The UI must show the source document location for extracted statements so a reviewer can verify them.

---

# 23. Regulatory Compliance / PS2 Layer

The product should provide a configurable compliance layer rather than hard-coding one jurisdiction or regulatory interpretation.

### Model

```text
Treaty / Policy Clause
        ↓
Business Obligation
        ↓
Control
        ↓
Regulatory Requirement
        ↓
Evidence
        ↓
Compliance Status
```

### Functions

```text
create_regulatory_control()
map_clause_to_control()
evaluate_control()
attach_evidence()
flag_gap()
assign_reviewer()
approve_control_mapping()
export_compliance_matrix()
```

Compliance mappings must remain explainable and traceable to source evidence.

---

# 24. Treaty Clause Management

Users should be able to manage clauses independently from the raw document.

Each clause should support:

- title
- category
- original text
- simplified explanation
- effective date
- expiry date
- obligations
- thresholds
- financial values
- related treaty version
- related controls
- reviewer
- approval status
- source location
- history

### Clause statuses

```text
DRAFT
EXTRACTED
REVIEW_REQUIRED
APPROVED
SUPERSEDED
ARCHIVED
```

---

# 25. Treaty Change History

Every treaty change should create a version.

```text
Treaty v1
  ↓
Treaty v2
  ↓
Treaty v3
```

Show:

- what changed
- who changed it
- when
- source document
- affected clauses
- affected business rules
- affected mappings/reconciliations
- approval state

Provide a side-by-side diff view.

---

# 26. Databricks-Like Versioning and Rollback

Every important product object should be versionable where practical.

Versioned objects:

- raw ingestion snapshot
- structure detection
- canonical schema
- mapping profile
- mapping decision set
- standardized dataset
- pivot definition
- treaty
- treaty clauses
- reconciliation configuration
- report definition

### Rollback principle

Rollback should not delete history.

Instead:

```text
Current Version
      ↓
Select historical version
      ↓
Compare
      ↓
Restore as new version
```

This preserves an immutable history.

### Functions

```text
create_version()
list_versions()
compare_versions()
restore_version()
create_rollback_event()
```

---

# 27. Data Lineage

Every transformed or derived asset should have lineage.

Example:

```text
Raw Bordereaux
      ↓
Structure Detection
      ↓
Mapping Run
      ↓
Standardized Dataset
      ↓
Claims Mapping
      ↓
Pivot
      ↓
Reconciliation
      ↓
Final Report
```

And:

```text
Treaty Document
      ↓
Clause Extraction
      ↓
Treaty Rule
      ↓
Mapping / Reconciliation Rule
      ↓
Report
```

The UI should expose both:

- upstream lineage
- downstream lineage

### Lineage functions

```text
create_lineage_edge()
get_upstream_lineage()
get_downstream_lineage()
get_asset_impact()
trace_field_lineage()
trace_report_evidence()
```

---

# 28. Reports

The platform should generate a final report at the end of important workflows.

## Standard report sections

```text
Executive Summary
Input Files
Processing Summary
Mapping Summary
Confidence Summary
Human Review Summary
Data Quality Findings
Claims Mapping
Pivot / Aggregation
Reconciliation Summary
Exceptions
Treaty / Clause Findings
Regulatory / Control Findings
Lineage
Audit Evidence
Version Information
```

### Export formats

At minimum:

- XLSX
- CSV for tabular outputs
- PDF for business reports

Report generation must use approved/finalized data only.

---

# 29. Communications and Integrations

The system should use an integration framework rather than hard-coding one provider.

## Connector categories

```text
Storage
Email
Teams
Confluence
CRM / Contacts
External APIs
Identity / SSO
```

### Teams

Possible actions:

- send review notification
- publish completed report
- notify reconciliation exceptions
- notify treaty approval request

### Email

Possible actions:

- generate review emails
- send final reports
- send exception notifications
- send approval requests

### Confluence

Use as an optional knowledge/evidence destination:

- publish approved procedure documentation
- publish review decisions/evidence
- publish final business documentation
- link to source/run/version

### Contact integration

Support a contact/party directory for:

- reinsurer
- MGA
- broker
- treaty owner
- reviewer
- business stakeholder

---

# 30. API / Connector Architecture

Create an adapter interface:

```text
Connector
├── authenticate()
├── test_connection()
├── list_resources()
├── read()
├── write()
└── send()
```

Each external integration implements the adapter.

Do not put provider-specific code inside business services.

---

# 31. Observability / Telemetry

Provide an **Operations / Observability** workspace.

## Platform metrics

- ingestion success/failure rate
- processing latency
- mapping success rate
- review rate
- unresolved mapping rate
- reconciliation match rate
- report generation failures
- connector errors
- AI call latency
- AI cost/token telemetry where available

## Run-level telemetry

Each processing run should expose:

```text
Run status
Start / end time
Files processed
Rows processed
Columns mapped
Mappings auto-accepted
Mappings reviewed
Mappings rejected
Warnings
Errors
AI calls
Processing latency
Output assets
```

### Operational states

```text
QUEUED
RUNNING
WAITING_FOR_REVIEW
SUCCEEDED
PARTIALLY_SUCCEEDED
FAILED
CANCELLED
```

---

# 32. Guardrails

Guardrails are mandatory because the platform handles financially sensitive business data and AI-assisted decisions.

## Input guardrails

- validate file size/type
- reject corrupt files
- detect unsupported structures
- detect suspicious formulas/macros where relevant
- scan documents for unsafe/injected instructions before passing content to an LLM
- enforce access control

## AI guardrails

- structured output only
- schema validation
- evidence required for mapping decisions
- no silent high-confidence acceptance without deterministic checks
- deterministic numeric validation for financial logic
- configurable thresholds
- human review for uncertainty
- prevent source text from becoming executable instructions
- log model/provider/configuration used

## Output guardrails

- validate target schema
- validate required fields
- validate data types
- validate business constraints
- detect duplicate/conflicting mappings
- maintain lineage
- preserve previous versions

---

# 33. Permission and Governance Model

Use permission-aware UI.

Possible roles:

```text
ADMIN
ANALYST
REVIEWER
TREATY_MANAGER
BUSINESS_CONSUMER
AUDITOR
```

Permissions should exist at resource scope:

```text
Project
File
Dataset
Mapping Profile
Treaty
Report
Reconciliation
Connector
```

Actions:

```text
VIEW
CREATE
EDIT
REVIEW
APPROVE
EXPORT
SHARE
DELETE
ADMIN
```

The UI should hide or disable unauthorized actions and provide a request-access path where appropriate.

---

# 34. Core Data Model

Recommended relational entities:

```text
User
Group
Role
Project
ProjectMember

DataAsset
DataAssetVersion
IngestionRun
SourceFile
SourceSheet
SourceSchema
SourceColumn
DataProfile

CanonicalSchema
CanonicalField
CanonicalFieldVersion

MappingRun
MappingProposal
MappingEvidence
MappingDecision
MappingProfile
MappingRule

StandardizedDataset
StandardizedDatasetVersion

PivotDefinition
PivotRun
PivotResult

ReconciliationRun
ReconciliationRule
ReconciliationMatch
ReconciliationException

Treaty
TreatyVersion
TreatyDocument
TreatyClause
TreatyClauseVersion
TreatyRule

RegulatoryControl
ClauseControlLink
ComplianceAssessment

Report
ReportVersion

LineageEdge
AuditEvent
ReviewTask

Connector
ConnectorCredentialReference
Notification
ProcessingProcedure
```

Credentials/secrets must never be stored as plain database fields.

---

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

# 64. One-Sentence Product Definition

**A Databricks-inspired enterprise workspace for intelligent bordereaux standardization, treaty intelligence, reconciliation, and governed reporting — built around confidence-aware AI mapping, human validation, reusable procedures, and end-to-end lineage.**
