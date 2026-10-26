import type {
  GroupByPair,
  NumStr,
  PreviewColumn,
  QuarterCount,
  ReconFilter,
  ReconGroup,
  ReconRunRequest,
  ReconRuleSpec,
  Tolerance,
  GroupStatus,
} from '../api/reconTypes';
import { percentInputToFraction } from './percent';

/* ------------------------------------------------------------------ */
/* Permissions                                                          */
/* ------------------------------------------------------------------ */

const RECON_CREATE_ROLES = new Set(['admin', 'project_owner', 'analyst']);

/** Mirrors the backend RECONCILIATION_CREATE permission (admin, project owner, analyst). */
export function canCreateRecon(role: string | null | undefined): boolean {
  return !!role && RECON_CREATE_ROLES.has(role);
}

/* ------------------------------------------------------------------ */
/* Expression editing                                                   */
/* ------------------------------------------------------------------ */

export interface InsertResult {
  text: string;
  cursor: number;
}

/**
 * Inserts `token` at the selection of `text` (replacing the selection),
 * padding with single spaces so `a+b` never glues to a neighbour. Returns the
 * new text and where the caret should be placed afterwards.
 */
export function insertAtCursor(text: string, selStart: number | null, selEnd: number | null, token: string): InsertResult {
  const start = Math.max(0, Math.min(selStart ?? text.length, text.length));
  const end = Math.max(start, Math.min(selEnd ?? start, text.length));
  const before = text.slice(0, start);
  const after = text.slice(end);
  const prev = before.slice(-1);
  const next = after.slice(0, 1);
  const lead = prev && !/\s/.test(prev) && prev !== '(' && token !== ')' ? ' ' : '';
  const needsTrail = token !== '(' && next !== ')' && !/^\s/.test(next);
  const trail = needsTrail ? ' ' : '';
  const result = before + lead + token + trail + after;
  const cursor = before.length + lead.length + token.length + trail.length;
  return { text: result, cursor };
}

export interface ExpressionHint {
  level: 'ok' | 'warn';
  message: string;
}

const COMPARATOR_RE = /(<=|>=|!=|==|=|<|>)/g;

/** Counts comparison signs in an expression (ignores signs inside quotes). */
export function countComparators(expr: string): number {
  const stripped = expr.replace(/'[^']*'|"[^"]*"/g, '');
  return (stripped.match(COMPARATOR_RE) ?? []).length;
}

/**
 * Light client-side sanity check. The server is the real validator; this only
 * nudges ("one comparison sign, one side per operand"). Returns null for empty input.
 */
export function expressionHint(expr: string): ExpressionHint | null {
  const text = expr.trim();
  if (!text) return null;
  const comparators = countComparators(text);
  if (comparators === 0) {
    return { level: 'warn', message: 'Add a comparison sign (=) between the bordereaux side and the subledger side.' };
  }
  if (comparators > 1) {
    return { level: 'warn', message: 'Use exactly one comparison sign in a rule.' };
  }
  const parts = text.split(/<=|>=|!=|==|=|<|>/);
  const [left = '', right = ''] = parts;
  const sides = (s: string) => ({
    b: /\bbordereaux\./i.test(s),
    s: /\bsubledger\./i.test(s),
  });
  const l = sides(left);
  const r = sides(right);
  const leftOk = l.b !== l.s;
  const rightOk = r.b !== r.s;
  if (!leftOk || !rightOk) {
    return { level: 'warn', message: 'Each side of the comparison should refer to one dataset (bordereaux.<column> or subledger.<column>).' };
  }
  if (l.b === r.b) {
    return { level: 'warn', message: 'The two sides should refer to different datasets (one bordereaux, one subledger).' };
  }
  return { level: 'ok', message: 'Looks well-formed. The server validates the expression when you run it.' };
}

/* ------------------------------------------------------------------ */
/* Column aliases (merge columns)                                        */
/* ------------------------------------------------------------------ */

export type Aliases = Record<string, string>;

/** Follows alias chains so that every key maps to its final target. */
export function resolveAlias(aliases: Aliases, column: string): string {
  let cur = column;
  const seen = new Set<string>();
  while (aliases[cur] && !seen.has(cur)) {
    seen.add(cur);
    cur = aliases[cur];
  }
  return cur;
}

/**
 * Records "treat `from` as the same column as `into`". Rejects cycles and
 * self-merges (returns the aliases unchanged). Other aliases that pointed at
 * `from` are re-pointed to `into` so no chains build up.
 */
export function addAlias(aliases: Aliases, from: string, into: string): Aliases {
  const target = resolveAlias(aliases, into);
  const source = resolveAlias(aliases, from);
  if (!from || !into || source === target) return aliases;
  const next: Aliases = {};
  for (const [k, v] of Object.entries(aliases)) next[k] = v === source ? target : v;
  next[source] = target;
  return next;
}

export function removeAlias(aliases: Aliases, from: string): Aliases {
  const next = { ...aliases };
  delete next[from];
  return next;
}

/** Builds aliases from accepted suggested merges: pairs are [keep, mergeIntoKeep]. */
export function buildAliases(pairs: Array<[string, string]>): Aliases {
  return pairs.reduce<Aliases>((acc, [a, b]) => addAlias(acc, b, a), {});
}

/* ------------------------------------------------------------------ */
/* Tolerance / run request                                              */
/* ------------------------------------------------------------------ */

export interface ToleranceInput {
  absolute: string;
  /** Percentage as users type it ("0.1" for 0.1%). */
  percentage: string;
  evaluation: 'OR' | 'AND';
}

export function toleranceFromInput(input: ToleranceInput): { value: Tolerance | null; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const absRaw = input.absolute.trim();
  const abs = absRaw === '' ? 0 : Number(absRaw);
  if (!Number.isFinite(abs) || abs < 0) errors.absolute = 'Enter an amount of 0 or more.';
  const pct = percentInputToFraction(input.percentage);
  if (pct.error) errors.percentage = pct.error;
  if (Object.keys(errors).length) return { value: null, errors };
  return { value: { absolute: abs, percentage: pct.fraction ?? 0, evaluation: input.evaluation }, errors };
}

export function toleranceToInput(t: Partial<Tolerance> | { absolute?: NumStr; percentage?: NumStr; evaluation?: string } | null | undefined): ToleranceInput {
  const pct = Number(t?.percentage ?? 0);
  return {
    absolute: String(Number(t?.absolute ?? 0)),
    percentage: String(Number((pct * 100).toFixed(6))),
    evaluation: t?.evaluation === 'AND' ? 'AND' : 'OR',
  };
}

export interface RuleDraft {
  key: string;
  name: string;
  expression: string;
  bordereaux_agg: string;
  subledger_agg: string;
}

export function ruleDraftsToSpecs(drafts: RuleDraft[]): ReconRuleSpec[] {
  return drafts
    .filter((r) => r.expression.trim())
    .map((r, i) => ({
      name: r.name.trim() || `Rule ${i + 1}`,
      expression: r.expression.trim(),
      bordereaux_agg: (r.bordereaux_agg || 'SUM') as ReconRuleSpec['bordereaux_agg'],
      subledger_agg: (r.subledger_agg || 'SUM') as ReconRuleSpec['subledger_agg'],
    }));
}

export function buildRunRequest(args: {
  name: string;
  bordereauxId: string;
  subledgerId: string;
  rules: RuleDraft[];
  groupBy: GroupByPair[];
  filters: ReconFilter[];
  tolerance: Tolerance;
}): ReconRunRequest {
  return {
    name: args.name.trim() || 'Reconciliation',
    bordereaux_dataset_id: args.bordereauxId,
    subledger_dataset_id: args.subledgerId,
    rules: ruleDraftsToSpecs(args.rules),
    group_by: args.groupBy.filter((g) => g.bordereaux && g.subledger),
    filters: args.filters.filter((f) => f.column),
    tolerance: args.tolerance,
  };
}

/* ------------------------------------------------------------------ */
/* Grain suggestions                                                    */
/* ------------------------------------------------------------------ */

const DERIVED_NOT_SUGGESTED = new Set(['_source_file', '_source_sheet', '_source_row', '_year', '_quarter']);

/** Columns present in both datasets (valid for a "both" filter). */
export function commonColumns(bordereaux: string[], subledger: string[]): string[] {
  const s = new Set(subledger);
  return bordereaux.filter((c) => s.has(c));
}

/**
 * Suggested compare-by pairs: `_period` first (when both sides have it), then
 * same-named business columns. Lineage columns are never suggested.
 */
export function suggestGroupBy(bordereaux: string[], subledger: string[]): GroupByPair[] {
  const out: GroupByPair[] = [];
  const common = commonColumns(bordereaux, subledger);
  if (common.includes('_period')) out.push({ bordereaux: '_period', subledger: '_period', label: 'period' });
  for (const c of common) {
    if (c === '_period' || DERIVED_NOT_SUGGESTED.has(c)) continue;
    out.push({ bordereaux: c, subledger: c, label: c });
  }
  return out;
}

export function labelForPair(b: string, s: string): string {
  const strip = (c: string) => c.replace(/^_/, '');
  return b === s ? strip(b) : `${strip(b)} / ${strip(s)}`;
}

/** Columns suited to a quick "treaty-like" filter, if any (e.g. treaty, treaty_ref, contract). */
export function findTreatyColumn(columns: string[]): string | null {
  return columns.find((c) => /treaty|contract|policy_ref|program/i.test(c)) ?? null;
}

export function sidesForColumn(column: string, bordereaux: string[], subledger: string[]): Array<'bordereaux' | 'subledger' | 'both'> {
  const inB = bordereaux.includes(column);
  const inS = subledger.includes(column);
  if (inB && inS) return ['both', 'bordereaux', 'subledger'];
  if (inB) return ['bordereaux'];
  if (inS) return ['subledger'];
  return [];
}

/* ------------------------------------------------------------------ */
/* Results helpers                                                      */
/* ------------------------------------------------------------------ */

export function toNum(v: NumStr | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function formatAmount(v: NumStr | null | undefined): string {
  const n = toNum(v);
  if (n === null) return '-';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** `variance_pct` is a fraction (0.01 = 1%). */
export function formatPct(v: NumStr | null | undefined): string {
  const n = toNum(v);
  if (n === null) return '-';
  return `${(n * 100).toLocaleString('en-US', { maximumFractionDigits: 3 })}%`;
}

export type GroupSortKey = 'label' | 'bordereaux_value' | 'subledger_value' | 'variance' | 'variance_pct' | 'status' | 'bordereaux_rows' | 'subledger_rows';

export interface GroupView {
  status: GroupStatus | 'ALL';
  search: string;
  sortKey: GroupSortKey | null;
  sortDir: 'asc' | 'desc';
}

export function filterAndSortGroups(groups: ReconGroup[], view: GroupView): ReconGroup[] {
  const q = view.search.trim().toLowerCase();
  let out = groups.filter((g) => (view.status === 'ALL' || g.status === view.status));
  if (q) out = out.filter((g) => g.labels.some((l) => String(l).toLowerCase().includes(q)));
  if (!view.sortKey) return out;
  const dir = view.sortDir === 'asc' ? 1 : -1;
  const key = view.sortKey;
  const val = (g: ReconGroup): number | string => {
    switch (key) {
      case 'label':
        return g.labels.join(' ').toLowerCase();
      case 'status':
        return g.status;
      case 'bordereaux_rows':
      case 'subledger_rows':
        return g[key];
      default:
        return toNum(g[key]) ?? Number.NEGATIVE_INFINITY;
    }
  };
  return [...out].sort((a, b) => {
    const av = val(a);
    const bv = val(b);
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
}

/* ------------------------------------------------------------------ */
/* Dataset report helpers                                               */
/* ------------------------------------------------------------------ */

export interface QuarterGrid {
  years: number[];
  cells: Record<number, Record<number, number>>;
}

/** years x Q1..Q4 matrix of row counts. */
export function buildQuarterGrid(quarters: QuarterCount[]): QuarterGrid {
  const cells: QuarterGrid['cells'] = {};
  for (const q of quarters) {
    cells[q.year] = cells[q.year] ?? {};
    const qn = Number(String(q.quarter).replace(/\D/g, ''));
    cells[q.year][qn] = (cells[q.year][qn] ?? 0) + q.rows;
  }
  const years = Object.keys(cells).map(Number).sort((a, b) => a - b);
  return { years, cells };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function columnNamesOf(columns: PreviewColumn[] | undefined, opts: { includeDerived?: boolean } = {}): string[] {
  return (columns ?? []).filter((c) => opts.includeDerived !== false || !c.derived).map((c) => c.name);
}

export function describeFilter(f: Pick<ReconFilter, 'side' | 'column' | 'op'> & { values?: unknown[] }): string {
  const vals = (f.values ?? []).map(String).join(', ');
  const opText: Record<string, string> = {
    in: 'in',
    not_in: 'not in',
    eq: '=',
    neq: '!=',
    contains: 'contains',
    between: 'between',
    gte: '>=',
    lte: '<=',
    is_blank: 'is blank',
    not_blank: 'is not blank',
  };
  const side = f.side === 'both' ? 'both' : f.side;
  return `${side}.${f.column} ${opText[f.op] ?? f.op}${vals ? ` ${vals}` : ''}`;
}


export interface QuickFilterState {
  years: string[];
  quarters: string[];
  periods: string[];
}

/** Year / quarter / period chips become filters that apply to both datasets (derived columns exist in both). */
export function quickFiltersToFilters(q: QuickFilterState): ReconFilter[] {
  const out: ReconFilter[] = [];
  if (q.years.length) out.push({ side: 'both', column: '_year', op: 'in', values: q.years });
  if (q.quarters.length) out.push({ side: 'both', column: '_quarter', op: 'in', values: q.quarters });
  if (q.periods.length) out.push({ side: 'both', column: '_period', op: 'in', values: q.periods });
  return out;
}

export function toggleValue(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}
