# Module Contracts
## Bordereaux Intelligence Platform

> **Version:** 1.0
> **Date:** 2026-10-09
> **Status:** Approved for MVP implementation

---

## 1. Contract Overview

This document defines the interfaces between modules. Each module must:
1. Implement its public interface completely
2. Not depend on other modules' internal implementation
3. Communicate only through defined contracts
4. Validate inputs at boundaries
5. Return well-defined outputs or errors

---

## 2. Core Module

### 2.1 Storage Service Contract

```python
from typing import Protocol, AsyncIterator
from pathlib import Path

class StorageService(Protocol):
    """Abstract storage operations for files and artifacts."""
    
    async def upload(
        self,
        path: str,
        data: bytes | AsyncIterator[bytes],
        content_type: str = "application/octet-stream"
    ) -> StorageResult:
        """Upload data to storage path. Returns storage metadata."""
        ...
    
    async def upload_file(
        self,
        path: str,
        local_path: Path
    ) -> StorageResult:
        """Upload local file to storage path."""
        ...
    
    async def download(self, path: str) -> bytes:
        """Download entire file as bytes. Raises NotFoundError if missing."""
        ...
    
    async def download_stream(self, path: str) -> AsyncIterator[bytes]:
        """Stream file contents. Raises NotFoundError if missing."""
        ...
    
    async def download_to_file(
        self,
        path: str,
        local_path: Path
    ) -> None:
        """Download to local file path."""
        ...
    
    async def exists(self, path: str) -> bool:
        """Check if path exists in storage."""
        ...
    
    async def delete(self, path: str) -> None:
        """Delete path. No-op if doesn't exist."""
        ...
    
    async def list_objects(
        self,
        prefix: str,
        max_keys: int = 1000
    ) -> list[StorageObject]:
        """List objects with given prefix."""
        ...
    
    def get_presigned_url(
        self,
        path: str,
        expiry_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """Generate presigned URL for direct access."""
        ...


@dataclass
class StorageResult:
    path: str
    size_bytes: int
    checksum: str  # SHA-256
    content_type: str
    created_at: datetime


@dataclass
class StorageObject:
    path: str
    size_bytes: int
    last_modified: datetime
```

### 2.2 Audit Service Contract

```python
class AuditService(Protocol):
    """Append-only audit logging."""
    
    async def log(
        self,
        event_type: str,
        target_type: str,
        target_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None
    ) -> AuditEvent:
        """Log an audit event. Returns created event."""
        ...
    
    async def query(
        self,
        target_type: str | None = None,
        target_id: UUID | None = None,
        actor_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        ...
```

### 2.3 Configuration Service Contract

```python
class ConfigService(Protocol):
    """Application configuration access."""
    
    def get(self, key: str, default: T = None) -> T:
        """Get configuration value."""
        ...
    
    def get_required(self, key: str) -> str:
        """Get required configuration. Raises if missing."""
        ...
    
    def get_section(self, prefix: str) -> dict[str, Any]:
        """Get all config under prefix."""
        ...
```

---

## 3. Ingestion Module

### 3.1 File Adapter Contract

```python
class FileAdapter(Protocol):
    """Parse a specific file format."""
    
    @property
    def supported_formats(self) -> list[FileFormat]:
        """List of formats this adapter handles."""
        ...
    
    def supports(self, asset: SourceAsset) -> bool:
        """Check if adapter can parse this asset."""
        ...
    
    async def parse(
        self,
        asset: SourceAsset,
        storage: StorageService,
        options: ParseOptions | None = None
    ) -> ParseResult:
        """Parse file and return structured data."""
        ...


@dataclass
class ParseOptions:
    sheet_name: str | None = None  # For Excel
    encoding: str | None = None    # Override detection
    delimiter: str | None = None   # For CSV
    skip_rows: int = 0
    max_rows: int | None = None


@dataclass
class ParseResult:
    success: bool
    data_path: str  # Path to parsed Parquet in storage
    row_count: int
    column_count: int
    columns: list[ParsedColumn]
    errors: list[ParseError]
    metadata: dict


@dataclass
class ParsedColumn:
    position: int
    raw_name: str
    normalized_name: str
    detected_type: DataType
    sample_values: list[Any]


@dataclass
class ParseError:
    row: int | None
    column: str | None
    error_type: str
    message: str
```

### 3.2 Format Detector Contract

```python
class FormatDetector(Protocol):
    """Detect file format from content."""
    
    async def detect(
        self,
        asset: SourceAsset,
        storage: StorageService
    ) -> FormatDetectionResult:
        """Detect format using magic bytes, extension, MIME."""
        ...


@dataclass
class FormatDetectionResult:
    format: FileFormat
    confidence: float  # 0.0 - 1.0
    mime_type: str
    encoding: str | None
    detection_method: str  # "magic", "extension", "probe"
```

### 3.3 Structure Detector Contract

```python
class StructureDetector(Protocol):
    """Detect table structure within parsed data."""
    
    async def detect(
        self,
        data_path: str,
        storage: StorageService
    ) -> StructureDetectionResult:
        """Analyze structure and return detection results."""
        ...


@dataclass
class StructureDetectionResult:
    header_row: int
    data_start_row: int
    data_end_row: int
    columns: list[DetectedColumn]
    multi_row_header: bool
    reconstructed_header: list[str] | None
    confidence: float
    detection_details: dict
```

### 3.4 Ingestion Service Contract

```python
class IngestionService(Protocol):
    """Orchestrate file ingestion pipeline."""
    
    async def ingest(
        self,
        project_id: UUID,
        file_path: Path,
        filename: str,
        logical_role: LogicalRole,
        options: IngestOptions | None = None
    ) -> SourceAsset:
        """Upload and create source asset."""
        ...
    
    async def parse(
        self,
        asset_id: UUID,
        options: ParseOptions | None = None
    ) -> SourceVersion:
        """Parse asset and create version."""
        ...
    
    async def detect_structure(
        self,
        version_id: UUID
    ) -> StructureDetection:
        """Detect structure for version."""
        ...
```

---

## 4. Profiling Module

### 4.1 Profiler Contract

```python
class DataProfiler(Protocol):
    """Generate statistical profiles of data."""
    
    async def profile(
        self,
        data_path: str,
        storage: StorageService,
        options: ProfileOptions | None = None
    ) -> DataProfile:
        """Generate comprehensive profile."""
        ...


@dataclass
class ProfileOptions:
    sample_size: int | None = None  # Limit rows for large datasets
    include_patterns: bool = True
    include_correlations: bool = False
    top_n_values: int = 10


@dataclass
class DataProfile:
    id: UUID
    version_id: UUID
    created_at: datetime
    row_count: int
    column_count: int
    file_size_bytes: int
    columns: list[ColumnProfile]
    profile_hash: str  # For caching


@dataclass
class ColumnProfile:
    name: str
    position: int
    data_type: DataType
    nullable: bool
    null_count: int
    null_rate: float
    distinct_count: int
    unique_rate: float
    
    # Type-specific stats
    numeric_stats: NumericStats | None
    string_stats: StringStats | None
    date_stats: DateStats | None
    
    # Value distribution
    top_values: list[ValueCount]
    pattern_samples: list[str]


@dataclass
class NumericStats:
    min: Decimal
    max: Decimal
    mean: Decimal
    median: Decimal
    std_dev: Decimal
    percentiles: dict[int, Decimal]  # 25, 50, 75, 90, 95, 99


@dataclass
class StringStats:
    min_length: int
    max_length: int
    avg_length: float
    empty_count: int
    patterns: list[PatternMatch]


@dataclass
class DateStats:
    min_date: date
    max_date: date
    date_format_patterns: list[str]
```

---

## 5. Mapping Module

### 5.1 Canonical Schema Service Contract

```python
class CanonicalSchemaService(Protocol):
    """Manage canonical schema definitions."""
    
    async def get_schema(
        self,
        schema_id: str,
        version: str | None = None
    ) -> CanonicalSchema:
        """Get schema by ID and optional version."""
        ...
    
    async def list_schemas(self) -> list[SchemaSummary]:
        """List available schemas."""
        ...
    
    async def validate_schema(
        self,
        schema: CanonicalSchema
    ) -> ValidationResult:
        """Validate schema definition."""
        ...


@dataclass
class CanonicalSchema:
    id: str
    name: str
    version: str
    standard: SchemaStandard  # CUSTOM, LLOYDS_V5_2, ACORD
    fields: list[CanonicalField]
    created_at: datetime
    description: str | None


@dataclass
class CanonicalField:
    name: str
    display_name: str
    type: DataType
    required: bool
    aliases: list[str]
    validation_rules: list[ValidationRule]
    semantic_category: SemanticCategory
    description: str | None
```

### 5.2 Mapping Candidate Generator Contract

```python
class MappingCandidateGenerator(Protocol):
    """Generate mapping candidates from source to canonical."""
    
    async def generate(
        self,
        profile: DataProfile,
        schema: CanonicalSchema,
        context: MappingContext | None = None
    ) -> list[CandidateMapping]:
        """Generate candidates for all source columns."""
        ...


@dataclass
class MappingContext:
    project_id: UUID
    historical_mappings: list[ApprovedMapping] | None
    relationships: list[InferredRelationship] | None


@dataclass
class CandidateMapping:
    id: UUID
    source_column: str
    source_position: int
    target_field: str
    confidence: Confidence
    rank: int
    evidence: list[MappingEvidence]
    status: MappingStatus  # PROPOSED, APPROVED, REJECTED


@dataclass
class Confidence:
    total: float  # 0.0 - 1.0
    breakdown: dict[EvidenceType, float]
    threshold_met: bool
    auto_approve_eligible: bool


@dataclass
class MappingEvidence:
    type: EvidenceType
    value: Any
    weight: float
    contribution: float
    details: str | None
```

### 5.3 Relationship Inferrer Contract

```python
class RelationshipInferrer(Protocol):
    """Infer relationships between fields."""
    
    async def infer(
        self,
        data_path: str,
        storage: StorageService,
        columns: list[str] | None = None
    ) -> list[InferredRelationship]:
        """Detect relationships in data."""
        ...


@dataclass
class InferredRelationship:
    id: UUID
    relationship_type: RelationshipType
    source_fields: list[str]
    target_fields: list[str]
    formula: str | None  # e.g., "A + B = C"
    cardinality: Cardinality
    coverage: float  # Percentage of rows matching
    tolerance: float  # For numeric relationships
    confidence: float
    origin: RelationshipOrigin
    evidence: dict
```

### 5.4 Mapping Service Contract

```python
class MappingService(Protocol):
    """Orchestrate mapping workflow."""
    
    async def generate_candidates(
        self,
        version_id: UUID,
        schema_id: str
    ) -> list[CandidateMapping]:
        """Generate mapping candidates for version."""
        ...
    
    async def approve_mapping(
        self,
        candidate_id: UUID,
        actor_id: UUID
    ) -> ApprovedMapping:
        """Approve a candidate mapping."""
        ...
    
    async def reject_mapping(
        self,
        candidate_id: UUID,
        actor_id: UUID,
        reason: str
    ) -> CandidateMapping:
        """Reject a candidate mapping."""
        ...
    
    async def create_manual_mapping(
        self,
        version_id: UUID,
        source_column: str,
        target_field: str,
        actor_id: UUID,
        transformation: Transformation | None = None
    ) -> ApprovedMapping:
        """Create manual mapping override."""
        ...
    
    async def finalize_mappings(
        self,
        version_id: UUID,
        actor_id: UUID
    ) -> ApprovedMappingSet:
        """Finalize all mappings for standardization."""
        ...
```

### 5.5 Schema Template Service Contract

```python
class SchemaTemplateService(Protocol):
    """Manage reusable mapping templates."""
    
    async def create_template(
        self,
        name: str,
        mapping_set_id: UUID,
        actor_id: UUID,
        description: str | None = None,
        scope: TemplateScope = TemplateScope.PROJECT,
        project_id: UUID | None = None,
        flexibility: SignatureFlexibility = SignatureFlexibility.FLEXIBLE,
        options: TemplateCreationOptions | None = None
    ) -> SchemaTemplate:
        """
        Create template from finalized mappings.
        Extracts patterns from source columns and builds reusable rules.
        """
        ...
    
    async def get_template(self, template_id: UUID) -> SchemaTemplate:
        """Get template by ID. Raises NotFoundError if missing."""
        ...
    
    async def list_templates(
        self,
        scope: TemplateScope | None = None,
        project_id: UUID | None = None,
        target_schema_id: str | None = None,
        status: TemplateStatus = TemplateStatus.ACTIVE
    ) -> list[SchemaTemplate]:
        """List templates matching criteria."""
        ...
    
    async def update_template(
        self,
        template_id: UUID,
        actor_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: TemplateStatus | None = None
    ) -> SchemaTemplate:
        """Update template metadata."""
        ...
    
    async def delete_template(
        self,
        template_id: UUID,
        actor_id: UUID
    ) -> None:
        """Archive template (soft delete)."""
        ...
    
    async def find_matching_templates(
        self,
        version_id: UUID,
        target_schema_id: str,
        min_match_score: float = 0.7
    ) -> list[TemplateMatch]:
        """
        Find templates that match version's structure.
        Returns sorted by match_score descending.
        """
        ...
    
    async def apply_template(
        self,
        version_id: UUID,
        template_id: UUID,
        actor_id: UUID,
        options: TemplateApplyOptions | None = None
    ) -> TemplateApplicationResult:
        """
        Apply template rules to generate/boost mapping candidates.
        Creates or merges into existing mapping set.
        """
        ...


class TemplateScope(Enum):
    PROJECT = "PROJECT"
    GLOBAL = "GLOBAL"


class TemplateStatus(Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class SignatureFlexibility(Enum):
    STRICT = "STRICT"      # Column names must match exactly
    FLEXIBLE = "FLEXIBLE"  # Fuzzy matching with high threshold
    LOOSE = "LOOSE"        # Type-based matching with any name


class MatchStrategy(Enum):
    EXACT_NAME = "EXACT_NAME"
    FUZZY_NAME = "FUZZY_NAME"
    TYPE_AND_POSITION = "TYPE_AND_POSITION"
    ALIAS_MATCH = "ALIAS_MATCH"
    REGEX = "REGEX"


@dataclass
class SchemaTemplate:
    id: UUID
    name: str
    description: str | None
    scope: TemplateScope
    project_id: UUID | None
    target_schema_id: str
    source_signature: SourceSignature
    field_mappings: list[TemplateMappingRule]
    flexibility: SignatureFlexibility
    status: TemplateStatus
    usage_count: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime


@dataclass
class SourceSignature:
    column_patterns: list[ColumnPattern]
    min_columns: int | None
    max_columns: int | None
    signature_hash: str


@dataclass
class ColumnPattern:
    name_pattern: str  # Regex or exact match
    expected_type: DataType
    required: bool
    position_hint: int | None
    aliases: list[str]


@dataclass
class TemplateMappingRule:
    source_pattern: str
    target_field: str
    match_strategy: MatchStrategy
    transformation: Transformation | None
    confidence_boost: float  # Added to base confidence (0.0 - 0.3)
    priority: int


@dataclass
class TemplateCreationOptions:
    include_transformations: bool = True
    generalize_patterns: bool = True  # Convert exact names to patterns
    include_type_hints: bool = True


@dataclass
class TemplateApplyOptions:
    auto_approve_high_confidence: bool = False
    min_confidence_for_auto: float = 0.95
    merge_with_existing: bool = True  # Add to existing candidates vs replace


@dataclass
class TemplateMatch:
    template_id: UUID
    template_name: str
    match_score: float
    matched_columns: int
    total_columns: int
    unmatched_source_columns: list[str]
    unmatched_template_rules: list[str]
    recommendation: MatchRecommendation


class MatchRecommendation(Enum):
    APPLY = "APPLY"    # High match, recommended
    REVIEW = "REVIEW"  # Moderate match, review suggested
    SKIP = "SKIP"      # Low match, likely not applicable


@dataclass
class TemplateApplicationResult:
    mapping_set_id: UUID
    applied_rules: int
    total_rules: int
    candidates_created: int
    candidates_boosted: int
    average_confidence: float
    application_id: UUID
```

---

## 6. Standardization Module

### 6.1 Transformation Engine Contract

```python
class TransformationEngine(Protocol):
    """Execute data transformations."""
    
    async def transform(
        self,
        data_path: str,
        mappings: ApprovedMappingSet,
        schema: CanonicalSchema,
        storage: StorageService
    ) -> TransformationResult:
        """Transform data according to mappings."""
        ...


@dataclass
class TransformationResult:
    success: bool
    output_path: str  # Path to transformed Parquet
    row_count: int
    valid_rows: int
    invalid_rows: int
    coverage: float  # Percentage of schema fields mapped
    errors: list[TransformationError]
    lineage: list[LineageRecord]


@dataclass
class TransformationError:
    row_number: int
    source_column: str
    target_field: str
    error_type: str
    message: str
    source_value: Any
```

### 6.2 Standardization Service Contract

```python
class StandardizationService(Protocol):
    """Orchestrate standardization workflow."""
    
    async def standardize(
        self,
        version_id: UUID,
        mapping_set_id: UUID
    ) -> ClaimsMapping:
        """Create standardized Claims Mapping."""
        ...
    
    async def validate(
        self,
        claims_mapping_id: UUID
    ) -> ValidationResult:
        """Validate Claims Mapping against schema."""
        ...
```

---

## 7. Reconciliation Module

### 7.1 Subledger Service Contract

```python
class SubledgerService(Protocol):
    """Manage subledger data."""
    
    async def ingest(
        self,
        project_id: UUID,
        asset_ids: list[UUID]
    ) -> Subledger:
        """Create subledger from ingested assets."""
        ...
    
    async def unify(
        self,
        subledger_ids: list[UUID]
    ) -> Subledger:
        """Unify multiple subledgers into one."""
        ...
```

### 7.2 Pivot Engine Contract

```python
class PivotEngine(Protocol):
    """Create aggregated views for reconciliation."""
    
    async def pivot(
        self,
        data_path: str,
        config: PivotConfig,
        storage: StorageService
    ) -> PivotResult:
        """Create pivot/aggregation of data."""
        ...


@dataclass
class PivotConfig:
    dimensions: list[str]  # Group by fields
    measures: list[MeasureConfig]
    filters: list[FilterConfig] | None
    rounding: RoundingConfig | None


@dataclass
class MeasureConfig:
    field: str
    aggregation: AggregationType  # SUM, COUNT, AVG, MIN, MAX
    alias: str | None


@dataclass
class PivotResult:
    output_path: str
    row_count: int
    dimensions: list[str]
    measures: list[str]
```

### 7.3 Reconciliation Engine Contract

```python
class ReconciliationEngine(Protocol):
    """Execute reconciliation comparison."""
    
    async def reconcile(
        self,
        reported_path: str,  # Claims Mapping pivot
        subledger_path: str,  # Subledger pivot
        config: ReconciliationConfig,
        storage: StorageService
    ) -> ReconciliationResult:
        """Compare reported vs subledger data."""
        ...


@dataclass
class ReconciliationConfig:
    key_fields: list[str]
    measure_field: str
    variance_config: VarianceConfig
    treaty_state_id: UUID | None


@dataclass
class VarianceConfig:
    absolute_threshold: Decimal
    absolute_enabled: bool
    percentage_threshold: Decimal
    percentage_enabled: bool
    evaluation_mode: EvaluationMode  # AND, OR
    rounding_precision: int
    zero_denominator_handling: ZeroDenominatorHandling


@dataclass
class ReconciliationResult:
    run_id: UUID
    status: RunStatus
    summary: ReconciliationSummary
    variances_path: str  # Path to variance records
    diagnostics_path: str  # Path to diagnostic findings
```

### 7.4 Diagnostic Engine Contract

```python
class DiagnosticEngine(Protocol):
    """Run deterministic diagnostic checks."""
    
    async def run_checks(
        self,
        result: ReconciliationResult,
        storage: StorageService,
        checks: list[str] | None = None  # Specific checks or all
    ) -> list[DiagnosticFinding]:
        """Execute diagnostic checks."""
        ...
    
    def list_checks(self) -> list[CheckDefinition]:
        """List available diagnostic checks."""
        ...


@dataclass
class CheckDefinition:
    id: str  # e.g., "D001"
    name: str
    category: CheckCategory
    description: str
    severity_default: Severity


@dataclass
class DiagnosticFinding:
    id: UUID
    check_id: str
    category: CheckCategory
    severity: Severity
    status: FindingStatus
    scope: dict  # Affected dimensions
    metrics: dict  # Quantitative results
    evidence: list[Evidence]
    message: str
```

### 7.5 Reconciliation Service Contract

```python
class ReconciliationService(Protocol):
    """Orchestrate reconciliation workflow."""
    
    async def create_run(
        self,
        project_id: UUID,
        claims_mapping_id: UUID,
        subledger_id: UUID,
        config: ReconciliationConfig,
        run_type: RunType = RunType.BASELINE
    ) -> ReconciliationRun:
        """Create and execute reconciliation run."""
        ...
    
    async def get_run(
        self,
        run_id: UUID
    ) -> ReconciliationRun:
        """Get run with summary."""
        ...
    
    async def get_variances(
        self,
        run_id: UUID,
        filters: VarianceFilters | None = None,
        page: int = 1,
        page_size: int = 100
    ) -> PaginatedResult[VarianceRecord]:
        """Get variance records with pagination."""
        ...
    
    async def get_diagnostics(
        self,
        run_id: UUID,
        filters: DiagnosticFilters | None = None
    ) -> list[DiagnosticFinding]:
        """Get diagnostic findings."""
        ...
    
    async def compare_runs(
        self,
        baseline_run_id: UUID,
        scenario_run_id: UUID
    ) -> RunComparison:
        """Compare two reconciliation runs."""
        ...
```

---

## 8. Treaty Module

### 8.1 Treaty Discovery Service Contract

```python
class TreatyDiscoveryService(Protocol):
    """Discover treaty structure from data."""
    
    async def discover(
        self,
        sources: list[DiscoverySource]
    ) -> TreatyManifest:
        """Discover treaty components."""
        ...


@dataclass
class DiscoverySource:
    source_type: SourceType  # CLAIMS_MAPPING, SUBLEDGER, CONFIG, DOCUMENT
    artifact_id: UUID
    path: str | None


@dataclass
class TreatyManifest:
    id: UUID
    treaty_id: str
    effective_from: date
    effective_to: date | None
    clauses: list[DiscoveredClause]
    parameters: list[DiscoveredParameter]
    source_references: list[SourceReference]
    confidence: float
```

### 8.2 Treaty State Service Contract

```python
class TreatyStateService(Protocol):
    """Manage treaty state versioning."""
    
    async def create_state(
        self,
        treaty_id: UUID,
        base_state_id: UUID | None,
        change_set: ChangeSet,
        actor_id: UUID
    ) -> TreatyState:
        """Create new state from change set."""
        ...
    
    async def get_state(
        self,
        state_id: UUID
    ) -> TreatyState:
        """Get state by ID."""
        ...
    
    async def list_states(
        self,
        treaty_id: UUID
    ) -> list[TreatyStateSummary]:
        """List all states for treaty."""
        ...
    
    async def rollback(
        self,
        treaty_id: UUID,
        target_state_id: UUID,
        actor_id: UUID,
        reason: str
    ) -> TreatyState:
        """Create new state equivalent to target."""
        ...
    
    async def compare_states(
        self,
        state_a_id: UUID,
        state_b_id: UUID
    ) -> StateDiff:
        """Compare two states."""
        ...
    
    async def validate_change_set(
        self,
        base_state_id: UUID,
        change_set: ChangeSet
    ) -> ValidationResult:
        """Validate change set against base state."""
        ...
```

### 8.3 Treaty Evaluator Contract

```python
class TreatyEvaluator(Protocol):
    """Evaluate treaty rules against data."""
    
    async def evaluate(
        self,
        data_path: str,
        state: TreatyState,
        storage: StorageService
    ) -> EvaluationResult:
        """Apply treaty rules to data."""
        ...


@dataclass
class EvaluationResult:
    output_path: str  # Path to evaluated data
    clauses_applied: list[ClauseApplication]
    rows_affected: int
```

---

## 9. AI Module

### 9.1 LLM Service Contract

```python
class LLMService(Protocol):
    """Abstract LLM operations."""
    
    async def complete(
        self,
        operation: LLMOperation,
        context: dict,
        schema: type[BaseModel],
        options: LLMOptions | None = None
    ) -> LLMResult[T]:
        """Execute LLM completion with structured output."""
        ...
    
    async def is_available(self) -> bool:
        """Check if LLM service is available."""
        ...


@dataclass
class LLMOptions:
    timeout_seconds: int = 60
    max_retries: int = 3
    temperature: float = 0.0
    max_tokens: int | None = None
    cache_enabled: bool = True


@dataclass
class LLMResult(Generic[T]):
    success: bool
    data: T | None
    error: str | None
    cached: bool
    usage: LLMUsage


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int
```

### 9.2 Evidence Package Builder Contract

```python
class EvidencePackageBuilder(Protocol):
    """Build minimal evidence packages for LLM."""
    
    async def build_mismatch_evidence(
        self,
        run_id: UUID,
        variance_ids: list[UUID],
        storage: StorageService
    ) -> dict:
        """Build evidence for mismatch classification."""
        ...
    
    async def build_cluster_evidence(
        self,
        run_id: UUID,
        cluster_dimension: str,
        storage: StorageService
    ) -> dict:
        """Build evidence for cluster interpretation."""
        ...
```

### 9.3 LLM Finding Service Contract

```python
class LLMFindingService(Protocol):
    """Manage LLM-generated findings."""
    
    async def classify_mismatches(
        self,
        run_id: UUID,
        variance_ids: list[UUID]
    ) -> list[LLMFinding]:
        """Classify variance records."""
        ...
    
    async def interpret_clusters(
        self,
        run_id: UUID
    ) -> list[ClusterInterpretation]:
        """Interpret mismatch clusters."""
        ...
    
    async def plan_investigation(
        self,
        run_id: UUID,
        question: str
    ) -> InvestigationPlan:
        """Plan investigation from user question."""
        ...
```

---

## 10. Reporting Module

### 10.1 Report Generator Contract

```python
class ReportGenerator(Protocol):
    """Generate reconciliation reports."""
    
    async def generate(
        self,
        run_id: UUID,
        format: ReportFormat,
        options: ReportOptions | None = None
    ) -> ReportResult:
        """Generate report for reconciliation run."""
        ...


@dataclass
class ReportOptions:
    include_sections: list[ReportSection] | None  # All if None
    include_evidence: bool = True
    include_lineage: bool = True
    max_exceptions: int = 1000


@dataclass
class ReportResult:
    report_path: str
    format: ReportFormat
    size_bytes: int
    generated_at: datetime
    sections: list[str]
```

### 10.2 Export Service Contract

```python
class ExportService(Protocol):
    """Export data in various formats."""
    
    async def export_variances(
        self,
        run_id: UUID,
        format: ExportFormat,
        filters: VarianceFilters | None = None
    ) -> ExportResult:
        """Export variance records."""
        ...
    
    async def export_diagnostics(
        self,
        run_id: UUID,
        format: ExportFormat
    ) -> ExportResult:
        """Export diagnostic findings."""
        ...
```

---

## 11. Cross-Cutting Contracts

### 11.1 Pagination

```python
@dataclass
class PaginatedResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
```

### 11.2 Validation

```python
@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]


@dataclass
class ValidationError:
    field: str | None
    code: str
    message: str


@dataclass
class ValidationWarning:
    field: str | None
    code: str
    message: str
```

### 11.3 Lineage

```python
@dataclass
class LineageRecord:
    id: UUID
    derived_type: str
    derived_id: UUID
    derived_record_id: str | None
    source_type: str
    source_id: UUID
    source_version_id: UUID
    source_record_id: str | None
    source_row_number: int | None
    transformation_id: UUID | None
    created_at: datetime
```
