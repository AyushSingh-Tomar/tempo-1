# Domain Model
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09

---

## 1. Domain Overview

The platform operates in the **Reinsurance Data Standardization** domain, bridging heterogeneous insurance data sources into a unified canonical representation for reconciliation and reporting.

### Core Subdomain Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                     PLATFORM CORE                                │
│  (Projects, Assets, Users, Audit, Lineage, Versioning)          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  INGESTION    │     │    MAPPING    │     │ RECONCILIATION│
│  & PROFILING  │────▶│   & SCORING   │────▶│   & DIAGNOSIS │
└───────────────┘     └───────────────┘     └───────────────┘
                              │                     │
                              ▼                     ▼
                      ┌───────────────┐     ┌───────────────┐
                      │ STANDARDIZATION│     │    TREATY     │
                      └───────────────┘     │  MANAGEMENT   │
                                            └───────────────┘
```

---

## 2. Core Entities

### 2.1 Project

The top-level organizational container for a reconciliation effort.

```
Project
├── id: UUID
├── name: string
├── description: string
├── status: ProjectStatus
├── created_at: datetime
├── created_by: User
├── updated_at: datetime
├── canonical_schema_version: string
└── config: ProjectConfig
```

**ProjectStatus:** `CREATED | ACTIVE | ARCHIVED`

**Relationships:**
- Has many → SourceAsset
- Has many → ClaimsMapping
- Has many → Subledger
- Has many → ReconciliationRun
- Has one → CanonicalSchema

---

### 2.2 SourceAsset

An uploaded file before any transformation.

```
SourceAsset
├── id: UUID
├── project_id: UUID
├── filename: string
├── original_filename: string
├── format: FileFormat
├── checksum_sha256: string
├── file_size_bytes: integer
├── uploaded_at: datetime
├── uploaded_by: User
├── storage_path: string
├── logical_role: LogicalRole
└── status: AssetStatus
```

**FileFormat:** `CSV | TSV | XLSX | XLS | JSON | JSONL | XML | PDF | PARQUET | HTML | EDI | SAS | TXT`

**LogicalRole:** `CLAIMS_MAPPING | SUBLEDGER | REFERENCE | TREATY_DOCUMENT`

**AssetStatus:** `UPLOADED | PARSED | PROFILED | FAILED`

**Relationships:**
- Belongs to → Project
- Has many → SourceVersion
- Has one → StructureDetection
- Has one → DataProfile

---

### 2.3 SourceVersion

An immutable version of processed source data.

```
SourceVersion
├── id: UUID
├── asset_id: UUID
├── version_number: integer
├── created_at: datetime
├── created_by: User
├── content_hash: string
├── row_count: integer
├── column_count: integer
├── structure_id: UUID
├── profile_id: UUID
└── status: VersionStatus
```

**VersionStatus:** `CREATED | MAPPED | STANDARDIZED | SUPERSEDED`

---

### 2.4 StructureDetection

Results of structure analysis for a source asset.

```
StructureDetection
├── id: UUID
├── asset_id: UUID
├── header_row: integer
├── data_start_row: integer
├── data_end_row: integer
├── detected_columns: list[DetectedColumn]
├── multi_row_header: boolean
├── header_reconstruction: string
├── confidence: decimal
└── detection_method: string
```

```
DetectedColumn
├── position: integer
├── raw_name: string
├── normalized_name: string
├── detected_type: DataType
└── nullable: boolean
```

**DataType:** `STRING | INTEGER | DECIMAL | DATE | DATETIME | BOOLEAN | UNKNOWN`

---

### 2.5 DataProfile

Statistical profile of a source version.

```
DataProfile
├── id: UUID
├── version_id: UUID
├── created_at: datetime
├── row_count: integer
├── column_count: integer
├── file_size_bytes: integer
├── column_profiles: list[ColumnProfile]
└── profile_hash: string
```

```
ColumnProfile
├── column_name: string
├── position: integer
├── data_type: DataType
├── null_count: integer
├── null_rate: decimal
├── distinct_count: integer
├── unique_rate: decimal
├── min_value: any
├── max_value: any
├── mean_value: decimal (numeric only)
├── median_value: decimal (numeric only)
├── std_dev: decimal (numeric only)
├── min_length: integer (string only)
├── max_length: integer (string only)
├── pattern_samples: list[string]
├── top_values: list[ValueCount]
└── date_range: DateRange (date only)
```

---

### 2.6 CanonicalSchema

Definition of target schema for standardization.

```
CanonicalSchema
├── id: UUID
├── name: string
├── version: string
├── standard: SchemaStandard
├── fields: list[CanonicalField]
├── created_at: datetime
└── created_by: User
```

**SchemaStandard:** `LLOYDS_V5_2 | ACORD | CUSTOM`

```
CanonicalField
├── name: string
├── display_name: string
├── type: DataType
├── required: boolean
├── aliases: list[string]
├── validation_rules: list[ValidationRule]
├── description: string
└── semantic_category: SemanticCategory
```

**SemanticCategory:** `IDENTIFIER | DATE | AMOUNT | STATUS | PARTY | LOCATION | CLASSIFICATION`

---

### 2.7 CandidateMapping

A proposed mapping from source to canonical field.

```
CandidateMapping
├── id: UUID
├── version_id: UUID
├── source_column: string
├── target_field: string
├── confidence: decimal
├── rank: integer
├── evidence: list[MappingEvidence]
├── status: MappingStatus
└── created_at: datetime
```

**MappingStatus:** `PROPOSED | APPROVED | REJECTED | AUTO_APPROVED`

```
MappingEvidence
├── type: EvidenceType
├── value: any
├── weight: decimal
└── contribution: decimal
```

**EvidenceType:** `ALIAS_MATCH | NAME_SIMILARITY | SEMANTIC_EMBEDDING | TYPE_COMPATIBILITY | VALUE_PATTERN | CONTEXT | LAYOUT | RELATIONSHIP | HISTORICAL | AI_INFERENCE`

---

### 2.8 ApprovedMapping

The finalized mapping configuration.

```
ApprovedMapping
├── id: UUID
├── version_id: UUID
├── mapping_version: integer
├── mappings: list[FieldMapping]
├── coverage: decimal
├── approved_at: datetime
├── approved_by: User
└── review_decisions: list[ReviewDecision]
```

```
FieldMapping
├── source_column: string
├── target_field: string
├── transformation: Transformation
├── confidence: decimal
└── origin: MappingOrigin
```

**MappingOrigin:** `AUTO | MANUAL | HISTORICAL`

```
Transformation
├── type: TransformationType
├── parameters: dict
└── expression: string (optional)
```

**TransformationType:** `DIRECT | TYPE_CAST | DATE_PARSE | LOOKUP | EXPRESSION`

---

### 2.9 SchemaTemplate

A reusable mapping template that users can create from approved mappings and apply to new files.

```
SchemaTemplate
├── id: UUID
├── name: string
├── description: string
├── scope: TemplateScope
├── project_id: UUID (if project-scoped)
├── source_schema_signature: SchemaSignature
├── target_schema_id: string
├── field_mappings: list[TemplateMappingRule]
├── created_at: datetime
├── created_by: User
├── updated_at: datetime
├── usage_count: integer
└── status: TemplateStatus
```

**TemplateScope:** `PROJECT | GLOBAL`

**TemplateStatus:** `ACTIVE | DEPRECATED | ARCHIVED`

```
SchemaSignature
├── column_patterns: list[ColumnPattern]
├── row_count_range: Range
├── signature_hash: string
└── flexibility: SignatureFlexibility
```

**SignatureFlexibility:** `STRICT | FLEXIBLE | LOOSE`
- `STRICT` — Column names must match exactly
- `FLEXIBLE` — Fuzzy matching with high threshold
- `LOOSE` — Type-based matching with any name

```
ColumnPattern
├── name_pattern: string (regex or exact)
├── expected_type: DataType
├── required: boolean
├── position_hint: integer (optional)
└── aliases: list[string]
```

```
TemplateMappingRule
├── source_pattern: string
├── target_field: string
├── match_strategy: MatchStrategy
├── transformation: Transformation
├── confidence_boost: decimal
└── priority: integer
```

**MatchStrategy:** `EXACT_NAME | FUZZY_NAME | TYPE_AND_POSITION | ALIAS_MATCH | REGEX`

**Use Cases:**
1. User approves mappings for "Q1_claims.csv", saves as template "Quarterly Claims Template"
2. Next quarter, uploads "Q2_claims.csv" with same structure
3. System suggests applying "Quarterly Claims Template"
4. Template rules generate high-confidence candidates automatically

**Events:**
- `TemplateCreated` — New template saved
- `TemplateApplied` — Template used on a new file
- `TemplateUpdated` — Template modified
- `TemplateDeprecated` — Template marked as outdated

---

### 2.10 InferredRelationship

Detected relationship between fields or datasets.

```
InferredRelationship
├── id: UUID
├── source_id: UUID
├── relationship_type: RelationshipType
├── source_fields: list[string]
├── target_fields: list[string]
├── cardinality: Cardinality
├── formula: string (arithmetic)
├── tolerance: decimal
├── coverage: decimal
├── confidence: decimal
├── origin: RelationshipOrigin
├── approval_status: ApprovalStatus
└── created_at: datetime
```

**RelationshipType:** `ARITHMETIC | RATIO | REFERENTIAL | KEY | TEMPORAL | HIERARCHICAL | CONDITIONAL`

**Cardinality:** `ONE_TO_ONE | ONE_TO_MANY | MANY_TO_ONE | MANY_TO_MANY`

**RelationshipOrigin:** `INFERRED | USER_DEFINED | HISTORICAL | SYSTEM_DEFAULT`

**ApprovalStatus:** `PENDING | APPROVED | REJECTED`

---

### 2.10 ClaimsMapping

A standardized claims mapping artifact.

```
ClaimsMapping
├── id: UUID
├── project_id: UUID
├── source_version_id: UUID
├── mapping_version_id: UUID
├── version_number: integer
├── row_count: integer
├── schema_version: string
├── coverage: decimal
├── created_at: datetime
├── storage_path: string
└── status: ClaimsMappingStatus
```

**ClaimsMappingStatus:** `CREATED | VALIDATED | ACTIVE | SUPERSEDED`

---

### 2.11 Subledger

A unified subledger dataset.

```
Subledger
├── id: UUID
├── project_id: UUID
├── source_version_ids: list[UUID]
├── version_number: integer
├── row_count: integer
├── schema_version: string
├── created_at: datetime
├── storage_path: string
└── status: SubledgerStatus
```

**SubledgerStatus:** `CREATED | UNIFIED | VALIDATED | ACTIVE`

---

### 2.12 ReconciliationConfig

Configuration for a reconciliation run.

```
ReconciliationConfig
├── id: UUID
├── name: string
├── grain: ReconciliationGrain
├── variance_config: VarianceConfig
├── key_fields: list[string]
├── measure_field: string
├── aggregation: AggregationType
├── treaty_state_id: UUID (optional)
└── created_at: datetime
```

```
ReconciliationGrain
├── dimensions: list[string]
└── filters: list[Filter]
```

```
VarianceConfig
├── absolute_threshold: decimal
├── absolute_enabled: boolean
├── percentage_threshold: decimal
├── percentage_enabled: boolean
├── evaluation_mode: EvaluationMode
└── rounding_precision: integer
```

**EvaluationMode:** `AND | OR | ABSOLUTE_FIRST | PERCENTAGE_FIRST`

---

### 2.13 ReconciliationRun

An immutable execution of reconciliation.

```
ReconciliationRun
├── id: UUID
├── project_id: UUID
├── claims_mapping_id: UUID
├── claims_mapping_version: integer
├── subledger_id: UUID
├── subledger_version: integer
├── config_id: UUID
├── treaty_state_id: UUID (optional)
├── run_type: RunType
├── parent_run_id: UUID (optional)
├── status: RunStatus
├── started_at: datetime
├── completed_at: datetime
├── summary: ReconciliationSummary
└── fingerprint: string
```

**RunType:** `BASELINE | SCENARIO | INCREMENTAL`

**RunStatus:** `QUEUED | RUNNING | SUCCEEDED | FAILED | BLOCKED | CANCELLED`

```
ReconciliationSummary
├── total_groups: integer
├── matched_groups: integer
├── within_tolerance_groups: integer
├── unreconciled_groups: integer
├── reported_total: decimal
├── subledger_total: decimal
├── absolute_variance: decimal
├── percentage_variance: decimal
└── exception_count: integer
```

---

### 2.14 VarianceRecord

Individual variance calculation result.

```
VarianceRecord
├── id: UUID
├── run_id: UUID
├── grain_key: dict
├── reported_value: decimal
├── subledger_value: decimal
├── absolute_variance: decimal
├── percentage_variance: decimal
├── within_absolute_threshold: boolean
├── within_percentage_threshold: boolean
├── status: VarianceStatus
└── reported_record_ids: list[UUID]
└── subledger_record_ids: list[UUID]
```

**VarianceStatus:** `MATCH | WITHIN_TOLERANCE | UNRECONCILED | VALID_DIFFERENCE | INVESTIGATE | DATA_ERROR | UNRESOLVED`

---

### 2.15 DiagnosticFinding

Result of a deterministic diagnostic check.

```
DiagnosticFinding
├── id: UUID
├── run_id: UUID
├── check_id: string
├── category: CheckCategory
├── severity: Severity
├── status: FindingStatus
├── scope: dict
├── metrics: dict
├── evidence: list[Evidence]
├── message: string
└── created_at: datetime
```

**CheckCategory:** `STRUCTURAL | COMPLETENESS | INTEGRITY | VALUE | DISTRIBUTION`

**Severity:** `INFO | LOW | MEDIUM | HIGH | CRITICAL`

**FindingStatus:** `OPEN | VALID_DIFFERENCE | CORRECTED | ACCEPTED | REJECTED | UNRESOLVED`

---

### 2.16 LLMFinding

AI-generated interpretation of exceptions.

```
LLMFinding
├── id: UUID
├── run_id: UUID
├── scope_ids: list[UUID]
├── classification: RootCauseCategory
├── confidence: decimal
├── evidence_ids: list[string]
├── reason: string
├── recommended_checks: list[string]
├── requires_human_review: boolean
├── model_id: string
├── prompt_version: string
├── input_tokens: integer
├── output_tokens: integer
├── cached: boolean
└── created_at: datetime
```

**RootCauseCategory:** `MISSING_RECORD | EXTRA_RECORD | DUPLICATE | WRONG_MAPPING | AMOUNT_MISMATCH | DATE_MISMATCH | STATUS_MISMATCH | CODE_MISMATCH | FORMATTING | ROUNDING | TIMING_DIFFERENCE | TRANSFORMATION_DIFFERENCE | MASTER_DATA_MISMATCH | SOURCE_DATA_ISSUE | SIGN_CONVENTION | CURRENCY_CONVERSION | TREATY_RULE_DIFFERENCE | AGGREGATION_DIFFERENCE | ADJUSTMENT | REVERSAL | UNKNOWN`

---

### 2.17 ReviewDecision

Human decision on a mapping or exception.

```
ReviewDecision
├── id: UUID
├── target_type: ReviewTargetType
├── target_id: UUID
├── decision: Decision
├── reason: string
├── reviewed_by: User
├── reviewed_at: datetime
└── evidence_ids: list[UUID]
```

**ReviewTargetType:** `MAPPING | VARIANCE | FINDING | TREATY_STATE`

**Decision:** `APPROVED | REJECTED | ESCALATED | VALID_DIFFERENCE | DATA_ERROR | NEEDS_INVESTIGATION`

---

### 2.18 Treaty

A reinsurance treaty definition.

```
Treaty
├── id: UUID
├── treaty_id: string
├── name: string
├── type: TreatyType
├── effective_from: date
├── effective_to: date
├── created_at: datetime
└── status: TreatyStatus
```

**TreatyType:** `QUOTA_SHARE | SURPLUS | EXCESS_OF_LOSS | STOP_LOSS | FACULTATIVE`

**TreatyStatus:** `DRAFT | ACTIVE | EXPIRED | CANCELLED`

---

### 2.19 TreatyState

An immutable snapshot of treaty configuration.

```
TreatyState
├── id: UUID
├── treaty_id: UUID
├── state_type: StateType
├── parent_state_id: UUID (optional)
├── root_state_id: UUID
├── branch_id: string (optional)
├── version_number: integer
├── content_hash: string
├── clauses: list[TreatyClause]
├── rule_mappings: list[RuleMapping]
├── created_at: datetime
├── created_by: User
├── change_set_id: UUID (optional)
├── reason: string
└── status: StateStatus
```

**StateType:** `BASELINE | SCENARIO | BRANCH | ROLLBACK | APPROVED | SUPERSEDED | ARCHIVED`

**StateStatus:** `ACTIVE | SUPERSEDED | ARCHIVED`

---

### 2.20 TreatyClause

A clause within a treaty state.

```
TreatyClause
├── clause_id: string
├── name: string
├── clause_type: ClauseType
├── effective_from: date
├── effective_to: date (optional)
├── parameters: list[ClauseParameter]
├── conditions: list[Condition]
├── actions: list[Action]
├── rule_set_id: string
├── discovery_confidence: decimal
└── source_references: list[SourceReference]
```

**ClauseType:** `LIMIT | RATE | RETENTION | DEDUCTIBLE | INCLUSION | EXCLUSION | AGGREGATION | SIGN_CONVENTION`

```
ClauseParameter
├── parameter_id: string
├── name: string
├── type: ParameterType
├── value: any
├── currency: string (optional)
├── unit: string (optional)
├── required: boolean
├── editable: boolean
└── constraints: dict
```

**ParameterType:** `STRING | INTEGER | DECIMAL | BOOLEAN | DATE | DATETIME | CURRENCY_AMOUNT | PERCENTAGE | ENUM | LIST | REFERENCE | EXPRESSION`

---

### 2.21 ChangeSet

A set of changes to apply to a treaty state.

```
ChangeSet
├── id: UUID
├── treaty_id: UUID
├── base_state_id: UUID
├── operations: list[PatchOperation]
├── created_by: User
├── created_at: datetime
├── reason: string
└── validation_status: ValidationStatus
```

```
PatchOperation
├── operation_id: UUID
├── op: OperationType
├── path: string
├── value: any (optional)
├── old_value: any (optional)
└── block_id: UUID (optional)
```

**OperationType:** `ADD | REMOVE | REPLACE`

**ValidationStatus:** `PENDING | VALID | INVALID`

---

### 2.22 AuditEvent

Immutable record of system events.

```
AuditEvent
├── id: UUID
├── event_type: EventType
├── actor_id: UUID
├── actor_type: ActorType
├── timestamp: datetime
├── target_type: string
├── target_id: UUID
├── action: string
├── before_state: dict (optional)
├── after_state: dict (optional)
├── reason: string (optional)
└── metadata: dict
```

**EventType:** `CREATE | UPDATE | DELETE | APPROVE | REJECT | EXECUTE | COMPLETE | FAIL`

**ActorType:** `USER | SYSTEM | AI`

---

### 2.23 LineageRecord

Traceability record linking derived data to sources.

```
LineageRecord
├── id: UUID
├── derived_artifact_id: UUID
├── derived_artifact_type: string
├── derived_record_id: string
├── source_artifact_id: UUID
├── source_artifact_type: string
├── source_version_id: UUID
├── source_record_id: string
├── source_row_number: integer
├── transformation_id: UUID (optional)
└── created_at: datetime
```

---

## 3. Entity Relationship Diagram

```
┌─────────┐       ┌──────────────┐       ┌────────────────┐
│ Project │──1:N──│ SourceAsset  │──1:N──│ SourceVersion  │
└────┬────┘       └──────────────┘       └───────┬────────┘
     │                                           │
     │            ┌──────────────────┐           │
     │            │ StructureDetection│◀──1:1────┤
     │            └──────────────────┘           │
     │                                           │
     │            ┌──────────────────┐           │
     │            │   DataProfile    │◀──1:1────┤
     │            └──────────────────┘           │
     │                                           │
     │            ┌──────────────────┐           │
     │            │ CandidateMapping │◀──1:N────┤
     │            └────────┬─────────┘           │
     │                     │                     │
     │                     ▼                     │
     │            ┌──────────────────┐           │
     │            │ ApprovedMapping  │◀──1:1────┤
     │            └────────┬─────────┘           │
     │                     │                     │
     │                     ▼                     │
     │            ┌──────────────────┐           │
     ├───1:N──────│  ClaimsMapping   │───────────┘
     │            └────────┬─────────┘
     │                     │
     │            ┌────────▼─────────┐
     ├───1:N──────│    Subledger     │
     │            └────────┬─────────┘
     │                     │
     │                     ▼
     │     ┌───────────────────────────┐
     │     │    ReconciliationRun      │◀──────────────┐
     │     └───────────┬───────────────┘               │
     │                 │                               │
     │      ┌──────────┼──────────┐                    │
     │      ▼          ▼          ▼                    │
     │ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
     │ │Variance │ │Diagnostic│ │  LLM    │            │
     │ │ Record  │ │ Finding │ │ Finding │            │
     │ └─────────┘ └─────────┘ └─────────┘            │
     │                                                 │
     │            ┌──────────────────┐                 │
     ├───1:N──────│     Treaty       │                 │
     │            └────────┬─────────┘                 │
     │                     │                           │
     │            ┌────────▼─────────┐                 │
     │            │   TreatyState    │─────────────────┘
     │            └────────┬─────────┘
     │                     │
     │            ┌────────▼─────────┐
     │            │  TreatyClause    │
     │            └──────────────────┘
     │
     │            ┌──────────────────┐
     └───────────▶│   AuditEvent     │
                  └──────────────────┘
```

---

## 4. Aggregate Boundaries

### Aggregate 1: Source Processing
- **Root:** SourceAsset
- **Contains:** SourceVersion, StructureDetection, DataProfile
- **Invariant:** Versions are immutable once created

### Aggregate 2: Mapping
- **Root:** ApprovedMapping
- **Contains:** CandidateMapping, FieldMapping, MappingEvidence
- **Invariant:** Approved mappings require minimum confidence or human approval

### Aggregate 3: Claims Mapping
- **Root:** ClaimsMapping
- **Contains:** Standardized row data (external storage)
- **Invariant:** Must reference valid mapping version

### Aggregate 4: Reconciliation
- **Root:** ReconciliationRun
- **Contains:** VarianceRecord, DiagnosticFinding, LLMFinding
- **Invariant:** Run is immutable; changes create new runs

### Aggregate 5: Treaty
- **Root:** Treaty
- **Contains:** TreatyState, TreatyClause, ChangeSet
- **Invariant:** States are immutable; changes create new states

---

## 5. Domain Events

```
SourceAssetUploaded
SourceVersionCreated
ProfileCompleted
MappingCandidatesGenerated
MappingApproved
MappingRejected
ClaimsMappingCreated
SubledgerUnified
ReconciliationStarted
ReconciliationCompleted
ReconciliationFailed
DiagnosticsCompleted
LLMAnalysisCompleted
ExceptionCreated
ExceptionResolved
TreatyDiscovered
TreatyStateCreated
TreatyStateBranched
TreatyStateRolledBack
ReviewDecisionMade
```

---

## 6. Value Objects

```
Confidence
├── value: decimal (0.0 - 1.0)
├── breakdown: dict[EvidenceType, decimal]
└── threshold_met: boolean

Money
├── amount: decimal
├── currency: string
└── precision: integer

DateRange
├── start: date
├── end: date
└── inclusive: boolean

Grain
├── dimensions: frozenset[string]
└── hash: string

Fingerprint
├── value: string (SHA-256)
└── inputs: list[string]
```
