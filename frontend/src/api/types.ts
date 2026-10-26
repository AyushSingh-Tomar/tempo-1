/**
 * Hand-written types for the iteration-1 processing-run API contract.
 * Optional fields marked "assumed" are tolerated if present but not required;
 * see the integration notes in the frontend handback report.
 *
 * Decimal values (money, percentages, variances) are typed `DecimalValue`
 * because the backend serializes Python Decimals as strings to preserve
 * precision. The UI never does arithmetic on them.
 */

export type DecimalValue = string | number;

export const RUN_STATUSES = [
  'STARTED',
  'FILE_UPLOADED',
  'FILE_VALIDATED',
  'CLEANING_COMPLETED',
  'CLEANING_REVIEW_PENDING',
  'MAPPING_REVIEW_PENDING',
  'MAPPING_CONFIRMED',
  'TREATY_FIGURES_PENDING',
  'TREATY_FIGURES_VALIDATED',
  'FINANCIAL_CHECKS_COMPLETED',
  'DISCREPANCY_REVIEW_PENDING',
  'REPORT_GENERATION_PENDING',
  'COMPLETED',
  'FAILED',
] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface FormatTemplateColumn {
  name: string;
  /** Terms a source header may use to be recognised as this column. */
  terms: string[];
}

/** A saved final format in the platform-wide directory. */
export interface FormatTemplate {
  id: string;
  name: string;
  columns: FormatTemplateColumn[];
  column_count: number;
  term_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProcessingRun {
  id: string;
  project_id: string;
  status: RunStatus;
  source_asset_id: string | null;
  source_version_id: string | null;
  mapping_set_id: string | null;
  treaty_figures_id: string | null;
  created_at: string;
  updated_at?: string;
  // --- assumed optional extras -------------------------------------------
  filename?: string | null;
  original_filename?: string | null;
  file_size?: number | null;
  file_size_bytes?: number | null;
  sheet_name?: string | null;
  checksum?: string | null;
  row_count?: number | null;
  /** If the run FAILED, the status it failed from (lets the stepper mark the failing step). */
  failed_from_status?: RunStatus | null;
  previous_status?: RunStatus | null;
  failure_reason?: string | null;
  error?: { code?: string; message?: string } | null;
  /** Artifacts that actually exist for this run. */
  artifacts?: RunArtifact[] | null;
}

export type ArtifactType = 'processed_file' | 'audit_report';

export interface RunArtifact {
  artifact_type: ArtifactType | string;
  id?: string;
  format?: string;
  checksum?: string;
  generated_at?: string;
}

/** Upload response when a multi-sheet workbook needs a sheet choice (no run created). */
export interface SheetSelectionRequired {
  sheets: string[];
}

export type Transformation =
  | string
  | {
      type?: string;
      operation?: string;
      rule?: string;
      code?: string;
      description?: string;
      message?: string;
      column?: string | null;
      columns?: string[] | null;
      affected_rows?: number | null;
      affected_count?: number | null;
      count?: number | null;
      before?: unknown;
      after?: unknown;
      [key: string]: unknown;
    };

export type CleaningWarning =
  | string
  | {
      code?: string;
      type?: string;
      severity?: string;
      message?: string;
      description?: string;
      column?: string | null;
      row?: number | null;
      row_number?: number | null;
      rows?: number[] | null;
      value?: unknown;
      [key: string]: unknown;
    };

export interface CleaningResult {
  id?: string;
  attempt_number: number;
  before_row_count: number;
  before_column_count: number;
  after_row_count: number;
  after_column_count: number;
  transformations: Transformation[];
  warnings: CleaningWarning[];
  status: 'PENDING_REVIEW' | 'ACKNOWLEDGED' | 'RETRIED' | string;
  created_at?: string;
  // --- assumed optional previews ------------------------------------------
  before_preview?: PreviewTable | null;
  after_preview?: PreviewTable | null;
}

export interface PreviewTable {
  columns: string[];
  rows: unknown[][] | Record<string, unknown>[];
}

export type CandidateStatus = 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED';

export interface Evidence {
  type?: string;
  source?: string;
  description?: string;
  message?: string;
  score?: number;
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Confidence {
  total: number;
  breakdown: Record<string, number>;
}

export interface MappingCandidate {
  id: string;
  source_column: string;
  target_field: string | null;
  confidence?: Confidence | null;
  evidence: Evidence[];
  status: CandidateStatus;
  auto_approve_eligible?: boolean;
  // --- assumed optional extras -------------------------------------------
  rank?: number;
  origin?: 'APPROVED' | 'MANUAL' | 'AUTO_APPROVED' | string;
  sample_values?: unknown[];
  profile?: Record<string, unknown> | null;
  warnings?: string[];
  rejection_reason?: string | null;
}

export interface ApprovedMapping {
  id?: string;
  source_column: string;
  target_field: string;
  origin?: string;
}

export interface ApprovedMappingSummary {
  source_column: string;
  target_field: string;
}

export interface TargetField {
  name: string;
  display_name: string;
  type: string;
  required: 'mandatory' | 'optional' | string;
  category: string;
  dictionary_match?: string | null;
  /** Every term that maps a source header to this column (built-in synonyms plus any the user added). */
  recognised_terms?: string[];
  /** The terms the user supplied for this column (custom format only). */
  user_terms?: string[];
}

/** The "final columns" a run is mapped to: the built-in data dictionary or the user's own list. */
export interface TargetFormat {
  mode: 'DEFAULT' | 'CUSTOM';
  /** True once the user has explicitly chosen (default or custom). */
  selected: boolean;
  /** Set when the columns came from a saved format (a snapshot taken when it was chosen). */
  template?: { id: string; name: string } | null;
  fields: TargetField[];
}

export interface ColumnRoleSuggestion {
  source_column: string;
  suggested_field: string | null;
  is_ambiguous: boolean;
  matched_rules: string[];
}

export interface CandidateListResult {
  targetFormat: TargetFormat | null;
  candidates: MappingCandidate[];
  approvedMappings: ApprovedMappingSummary[];
  /** Required canonical fields (data.required_fields) - treaty-figure fields excluded, they're collected via the Step 6 form. */
  requiredFields: string[] | null;
  /** Count of source columns passed through untouched as `extra_<name>` (data.passthrough_count) - informational, not an error. */
  passthroughCount: number | null;
}

export interface TreatyFiguresRequest {
  commission_pct: string;
  tax_pct: string;
  cession_pct: string;
  brokerage_pct?: string | null;
  order_pct?: string | null;
  fx_rate?: string | null;
  currency?: string | null;
  settlement_currency?: string | null;
  /** Optional technical premium rate on sum insured (fraction); enables the gross-is-ceded check. */
  expected_si_rate?: string | null;
  fx_rates?: FxRateEntry[];
  effective_from?: string | null;
  effective_to?: string | null;
}

/** 1 unit of `currency` = `rate` units of the settlement currency. */
export interface FxRateEntry {
  currency: string;
  rate: string;
  source: 'FILE' | 'USER';
}

export interface DerivedCurrency {
  currency: string;
  row_count: number;
  rate: string | null;
  source: 'FILE' | null;
  conflicting_rates: string[];
}

/** One of the five treaty percentages, read from a per-row column of the mapped file. */
export interface DerivedFigure {
  figure: 'commission_pct' | 'brokerage_pct' | 'tax_pct' | 'cession_pct' | 'order_pct';
  /** UNIFORM = same on every filled row; VARIES = differs between rows; NOT_FOUND = no such column. */
  status: 'UNIFORM' | 'VARIES' | 'NOT_FOUND';
  source_column: string | null;
  /** Fraction as a string (0.25 = 25%); the most common value when VARIES. */
  value: string | null;
  filled_rows: number;
  total_rows: number;
  distinct: { value: string; row_count: number }[];
  /** Spreadsheet row numbers holding a value other than `value`. */
  example_rows: number[];
}

export interface DerivedTreatyInputs {
  figures: DerivedFigure[];
  currencies: DerivedCurrency[];
  settlement_currency: string | null;
  has_currency_column: boolean;
  has_fx_column: boolean;
}

export interface TreatyFigures {
  id: string;
  project_id: string;
  commission_pct: DecimalValue;
  brokerage_pct: DecimalValue | null;
  tax_pct: DecimalValue;
  cession_pct: DecimalValue;
  order_pct: DecimalValue | null;
  fx_rate: DecimalValue | null;
  currency: string | null;
  settlement_currency?: string | null;
  fx_rates?: FxRateEntry[];
  effective_from: string | null;
  effective_to: string | null;
  created_by?: string;
  created_at?: string;
}

export type Severity = 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
export type DiscrepancyStatus = 'CONFIRMED_ERROR' | 'VALID_DIFFERENCE' | 'WARNING' | 'UNRESOLVED' | 'OVERRIDDEN';

export interface DiscrepancyOverride {
  id: string;
  discrepancy_id: string;
  run_id?: string;
  actor_id?: string;
  actor_name?: string;
  reason: string;
  comment?: string | null;
  created_at?: string;
}

export interface DiscrepancyFinding {
  id: string;
  check_id: string;
  category: string;
  severity: Severity | string;
  status: DiscrepancyStatus | string;
  affected_row_number: number | null;
  affected_field: string | null;
  expected_value: DecimalValue | null;
  observed_value: DecimalValue | null;
  variance: DecimalValue | null;
  message: string;
  evidence: Record<string, unknown> | null;
  created_at?: string;
  // --- assumed optional: embedded override record -------------------------
  override?: DiscrepancyOverride | null;
}

export interface DiscrepancyListResult {
  findings: DiscrepancyFinding[];
  /** Relationship check on numeric columns that matched no dictionary field (runs after treaty figures). */
  columnRoleSuggestions: ColumnRoleSuggestion[];
  /** The money-column relations the user declared and the financial checks evaluated. */
  relations: MoneyRelation[];
  /** Rules executed (assumed: data.checks_performed or meta.checks_performed). */
  checksPerformed: string[] | null;
  totalRecords: number | null;
}

export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';

export interface Job {
  id: string;
  type: string;
  status: JobStatus;
  progress: { percentage?: number; current_step?: string; message?: string } | null;
  error: { code?: string; message?: string } | null;
  output?: unknown;
  created_at?: string;
  completed_at?: string | null;
}

/** One immutable, numbered version of the processed file cut to a year / quarter / month. */
export interface PeriodExtract {
  id: string;
  run_id: string;
  version_number: number;
  period_label: string;
  period_field: string;
  period_year: number;
  period_quarter: number | null;
  period_month: number | null;
  checksum: string;
  total_rows: number;
  included_rows: number;
  included_partial_dates: number;
  excluded_outside_period: number;
  excluded_undated: number;
  generated_at: string | null;
  /** false: nothing changed, so the existing latest version was returned. */
  created?: boolean;
}

export interface Report {
  id?: string;
  run_id?: string;
  status?: string;
  job_id?: string;
  artifacts?: RunArtifact[];
  [key: string]: unknown;
}

export interface Me {
  id: string;
  external_id?: string;
  email: string;
  name: string;
  role: string;
  permissions: string[];
}

export interface HealthStatus {
  status: string;
  checks?: Record<string, unknown>;
}

// --- AI transparency -------------------------------------------------------

/** `ok` = the model answered. Everything else says exactly why AI did not (fully) help. */
export type AiOutcomeStatus =
  | 'ok'
  | 'disabled'
  | 'skipped'
  | 'timeout'
  | 'rate_limited'
  | 'auth_error'
  | 'unavailable'
  | 'bad_response'
  | 'invalid_request'
  | 'error';

export interface AiStatus {
  available: boolean;
  enabled: boolean;
  provider: string | null;
  model: string | null;
  timeout_seconds: number;
  /** Why AI cannot be used, when `available` is false. */
  reason: string | null;
  /** Whose key AI calls use for the current user: their own, the server's, or none. */
  key_source?: 'user' | 'server' | 'none';
  /** The current user's own key (only its last 4 characters are ever sent to the browser). */
  user_key?: { configured: boolean; hint: string | null; validated_at: string | null };
}

export interface AiKeyTest {
  status: AiOutcomeStatus | string;
  message: string;
  model: string | null;
  latency_ms: number;
}

export interface AiKeySaveResult extends AiStatus {
  saved: boolean;
  test: AiKeyTest | null;
}

export interface AiInteraction {
  id: string;
  run_id: string;
  purpose: 'MAPPING' | 'MONEY_RELATIONS';
  status: AiOutcomeStatus | string;
  message: string;
  model: string | null;
  provider: string | null;
  latency_ms: number;
  timeout_seconds: number | null;
  items_sent: number;
  items_resolved: number;
  created_at: string | null;
}

export interface AiActivity {
  ai: AiStatus;
  interactions: AiInteraction[];
}

// --- Money-column relations ------------------------------------------------

export interface MoneyRelationTerm {
  field: string;
  sign: 1 | -1;
  /** Treaty figure names (commission_pct ...) or plain numbers. */
  factors: string[];
}

export type RelationOrigin = 'USER' | 'STANDARD' | 'AI_SUGGESTED';

export interface MoneyRelation {
  id: string;
  label: string;
  target_field: string;
  terms: MoneyRelationTerm[];
  /** Always uses field names; the UI renders column labels from `RelationWorkspace.fields`. */
  expression: string;
  origin: RelationOrigin;
  rationale: string | null;
  last_rows_evaluated: number | null;
  last_rows_failed: number | null;
  last_skipped_reason: string | null;
}

export interface RelationFieldOption {
  field: string;
  label: string;
  kind: 'dictionary' | 'extra';
  source_column: string | null;
  money_role: string | null;
  filled_rows: number;
  min: string;
  max: string;
  sample: string[];
}

export interface TreatyFactorOption {
  name: string;
  value: string | null;
}

export interface RelationWorkspace {
  editable: boolean;
  relations: MoneyRelation[];
  fields: RelationFieldOption[];
  treaty_factors: TreatyFactorOption[];
  tolerance: string;
}

export interface RelationSuggestion {
  label: string;
  target_field: string;
  terms: MoneyRelationTerm[];
  expression: string;
  rationale: string;
  confidence: number | null;
  /** Share of rows (0-1, as a decimal string) on which the data supports the relation. */
  agreement: string;
  rows_evaluated: number;
}

export interface RelationSuggestResult {
  status: AiOutcomeStatus | string;
  message: string;
  interaction: AiInteraction;
  suggestions: RelationSuggestion[];
}

export interface RelationDraft {
  label?: string;
  target_field: string;
  terms: MoneyRelationTerm[];
  origin?: 'USER' | 'AI_SUGGESTED';
  rationale?: string | null;
}

export interface RelationResult {
  id: string;
  check_id: string;
  label: string;
  expression: string;
  origin: RelationOrigin;
  rows_evaluated: number;
  rows_failed: number;
  skipped_reason: string | null;
}
