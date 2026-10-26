/** Types for the Reconciliation workspace API (/recon/*). Mirrors backend/src/bordereaux/api/v1/routes/reconciliation.py. */

export type DatasetKind = 'BORDEREAUX' | 'SUBLEDGER';
export type DatasetStatus = 'DRAFT' | 'FINAL';
export type ReconFileFormat = 'CSV' | 'XLSX' | 'SAS7BDAT';

export interface EncodingOption {
  value: string;
  label: string;
}

export interface EncodingOptions {
  encodings: EncodingOption[];
  defaults: string[];
}

export interface EncodingCandidate {
  encoding: string;
  decodes_cleanly: boolean;
  replacement_chars: number;
  control_chars: number;
  mojibake_pairs: number;
  score: number;
  sample?: string | null;
  error?: string | null;
}

/** `differences` rows are {line, <encoding>: text, ...}. */
export type EncodingDifference = Record<string, string | number>;

export interface EncodingInfo {
  method: 'BOM' | 'USER' | 'DETECTED' | 'FILE_HEADER' | 'NOT_APPLICABLE' | string;
  chosen: string | null;
  all_agree?: boolean;
  compared?: string[];
  differences?: EncodingDifference[];
  warnings?: string[];
  detector_guess?: string | null;
  candidates?: EncodingCandidate[];
}

export interface ReconFile {
  id: string;
  filename: string;
  format: ReconFileFormat;
  size_bytes: number;
  encoding: string | null;
  encoding_info: EncodingInfo | null;
  encoding_choice: { forced?: string; candidates?: string[] } | null;
  sheets: string[];
  selected_sheets: string[];
  header_row: number;
  needs_sheet_choice: boolean;
}

export interface FilePatch {
  encoding?: string;
  candidate_encodings?: string[] | null;
  selected_sheets?: string[];
  header_row?: number;
}

export interface QuarterCount {
  period: string;
  year: number;
  /** e.g. Q1 */
  quarter: string | number;
  rows: number;
}

export interface DatasetReport {
  row_count: number;
  column_count: number;
  period_column: string | null;
  date_columns: string[];
  date_format: string;
  years: number[];
  quarters: QuarterCount[];
  files: Array<{ file: string; rows: number; periods: string[] }>;
  rows_without_period: number;
  column_types: Record<string, string>;
  unparsed_dates: Record<string, number>;
  ambiguous_dates: Record<string, number>;
  unparsed_numbers: Record<string, number>;
  cross_file_duplicate_rows: number;
  warnings: string[];
  schema?: unknown;
}

export interface ReconDataset {
  id: string;
  project_id?: string;
  kind: DatasetKind;
  name: string;
  status: DatasetStatus;
  row_count: number | null;
  column_count: number | null;
  config: Record<string, unknown> | null;
  report?: DatasetReport | null;
  files?: ReconFile[];
  finalized_at?: string | null;
  created_at?: string | null;
}

export interface SchemaColumn {
  original: string;
  standard: string;
  type: string;
  filled: number;
  total: number;
}

export interface SchemaTable {
  id: string;
  file: string;
  sheet: string | null;
  row_count: number;
  columns: SchemaColumn[];
}

export interface SuggestedMerge {
  columns: [string, string];
  tables?: string[];
  score: number;
}

export interface SchemaSummary {
  tables: SchemaTable[];
  common_columns: string[];
  partial_columns: string[];
  unique_columns: Array<{ column: string; table: string }>;
  /** types maps table id -> inferred type. */
  type_conflicts: Array<{ column: string; types: Record<string, string> }>;
  suggested_merges: SuggestedMerge[];
  all_columns: string[];
}

export interface SchemaPreview {
  summary: SchemaSummary;
  samples: Record<string, Array<Record<string, unknown>>>;
  total_rows: number;
}

export interface FinalizeRequest {
  column_aliases: Record<string, string>;
  period_column: string | null;
  day_first: boolean;
  drop_cross_file_duplicates: boolean;
}

export interface PreviewColumn {
  name: string;
  type: string;
  derived: boolean;
}

export interface DatasetPreview {
  columns: PreviewColumn[];
  rows: Array<Record<string, unknown>>;
  row_count: number;
}

export interface ColumnValues {
  column: string;
  distinct: number;
  values: Array<{ value: unknown; rows: number }>;
}

export type Aggregation = 'SUM' | 'COUNT' | 'AVG' | 'MIN' | 'MAX';
export type FilterSide = 'bordereaux' | 'subledger' | 'both';
export type FilterOp =
  | 'in'
  | 'not_in'
  | 'eq'
  | 'neq'
  | 'contains'
  | 'between'
  | 'gte'
  | 'lte'
  | 'is_blank'
  | 'not_blank';

export interface ReconRuleSpec {
  name: string;
  expression: string;
  bordereaux_agg?: Aggregation;
  subledger_agg?: Aggregation;
}

export interface GroupByPair {
  bordereaux: string;
  subledger: string;
  label: string;
}

export interface ReconFilter {
  side: FilterSide;
  column: string;
  op: FilterOp;
  values: string[];
}

export interface Tolerance {
  absolute: number;
  percentage: number;
  evaluation: 'OR' | 'AND';
}

export interface ReconRunRequest {
  name: string;
  bordereaux_dataset_id: string;
  subledger_dataset_id: string;
  rules: ReconRuleSpec[];
  group_by: GroupByPair[];
  filters: ReconFilter[];
  tolerance: Tolerance;
}

/** The engine serialises decimals as strings. */
export type NumStr = string | number;

export interface RowsInScope {
  bordereaux: number;
  subledger: number;
  bordereaux_total: number;
  subledger_total: number;
}

export type GroupStatus = 'MATCHED' | 'VARIANCE' | 'ONLY_IN_BORDEREAUX' | 'ONLY_IN_SUBLEDGER';

export interface ReconGroup {
  key: string[];
  labels: string[];
  bordereaux_value: NumStr | null;
  subledger_value: NumStr | null;
  variance: NumStr | null;
  variance_pct: NumStr | null;
  status: GroupStatus;
  bordereaux_rows: number;
  subledger_rows: number;
  null_operands?: number;
  div_by_zero_rows?: number;
}

export interface RuleResult {
  rule_id: string;
  name: string;
  expression: string;
  bordereaux_expression: string;
  subledger_expression: string;
  grain: string[];
  totals: {
    bordereaux: NumStr | null;
    subledger: NumStr | null;
    variance: NumStr | null;
    variance_pct: NumStr | null;
    within_tolerance: boolean;
  };
  counts: Partial<Record<GroupStatus, number>>;
  status: 'RECONCILED' | 'UNRECONCILED';
  offsetting_differences: boolean;
  groups: ReconGroup[];
}

export interface ReconRunResult {
  status: 'RECONCILED' | 'UNRECONCILED' | string;
  rows_in_scope: RowsInScope;
  filters: ReconFilter[];
  group_by: GroupByPair[] | string[];
  tolerance: { absolute?: NumStr; percentage?: NumStr; evaluation?: string } | null;
  rules: RuleResult[];
}

export interface ReconRun {
  id: string;
  project_id: string;
  name: string | null;
  status: string;
  bordereaux_dataset_id: string;
  subledger_dataset_id: string;
  config: Partial<Pick<ReconRunRequest, 'rules' | 'group_by' | 'filters' | 'tolerance'>> | null;
  summary: Record<string, unknown> | null;
  created_at: string | null;
  result?: ReconRunResult;
}

export interface GroupRecords {
  side: string;
  total: number;
  columns: string[];
  rows: Array<Record<string, unknown>>;
}




