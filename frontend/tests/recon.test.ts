import { describe, expect, it } from 'vitest';
import {
  addAlias,
  buildAliases,
  buildQuarterGrid,
  buildRunRequest,
  canCreateRecon,
  countComparators,
  expressionHint,
  filterAndSortGroups,
  insertAtCursor,
  quickFiltersToFilters,
  removeAlias,
  suggestGroupBy,
  toleranceFromInput,
  toleranceToInput,
} from '../src/utils/recon';
import type { ReconGroup } from '../src/api/reconTypes';

describe('insertAtCursor', () => {
  it('inserts into an empty field with trailing space', () => {
    expect(insertAtCursor('', 0, 0, 'bordereaux.gross')).toEqual({ text: 'bordereaux.gross ', cursor: 17 });
  });
  it('pads against the previous word and replaces a selection', () => {
    const r = insertAtCursor('a b', 2, 3, '+');
    expect(r.text).toBe('a + ');
  });
  it('does not pad inside parentheses', () => {
    expect(insertAtCursor('()', 1, 1, 'x').text).toBe('(x)');
    expect(insertAtCursor('(x', 2, 2, ')').text).toBe('(x) ');
  });
  it('inserts in the middle', () => {
    const r = insertAtCursor('a  b', 2, 2, '*');
    expect(r.text).toBe('a * b');
  });
});

describe('expressionHint', () => {
  it('is silent for empty input', () => expect(expressionHint('  ')).toBeNull());
  it('asks for a comparison sign', () => expect(expressionHint('bordereaux.a')?.level).toBe('warn'));
  it('flags multiple comparison signs', () => {
    expect(countComparators('a = b = c')).toBe(2);
    expect(expressionHint('bordereaux.a = subledger.b = subledger.c')?.message).toMatch(/exactly one/);
  });
  it('accepts one bordereaux side vs one subledger side', () => {
    expect(expressionHint('bordereaux.a + bordereaux.b = subledger.c')?.level).toBe('ok');
  });
  it('warns when both sides use the same dataset', () => {
    expect(expressionHint('bordereaux.a = bordereaux.b')?.level).toBe('warn');
  });
});

describe('aliases', () => {
  it('builds and chains without cycles', () => {
    expect(buildAliases([['premium', 'prem']])).toEqual({ prem: 'premium' });
    const a = addAlias({ b: 'a' }, 'c', 'b');
    expect(a).toEqual({ b: 'a', c: 'a' });
    expect(addAlias(a, 'a', 'c')).toEqual(a);
  });
  it('removes an alias', () => expect(removeAlias({ a: 'b' }, 'a')).toEqual({}));
});

describe('tolerance', () => {
  it('converts percent input to a fraction and back', () => {
    expect(toleranceFromInput({ absolute: '0.01', percentage: '0.1', evaluation: 'OR' }).value).toEqual({
      absolute: 0.01,
      percentage: 0.001,
      evaluation: 'OR',
    });
    expect(toleranceToInput({ absolute: 5, percentage: 0.001, evaluation: 'AND' })).toEqual({ absolute: '5', percentage: '0.1', evaluation: 'AND' });
  });
  it('reports errors', () => {
    expect(toleranceFromInput({ absolute: '-1', percentage: 'x', evaluation: 'OR' }).errors).toHaveProperty('absolute');
  });
});

describe('grain and filters', () => {
  it('suggests _period then same-named columns, never lineage columns', () => {
    const s = suggestGroupBy(['_period', '_source_file', 'treaty', 'a'], ['treaty', '_period', '_source_file', 'b']);
    expect(s.map((g) => g.bordereaux)).toEqual(['_period', 'treaty']);
  });
  it('turns quick chips into both-side filters', () => {
    expect(quickFiltersToFilters({ years: ['2023'], quarters: [], periods: ['2023-Q1'] })).toEqual([
      { side: 'both', column: '_year', op: 'in', values: ['2023'] },
      { side: 'both', column: '_period', op: 'in', values: ['2023-Q1'] },
    ]);
  });
  it('builds a run request, skipping empty rules', () => {
    const req = buildRunRequest({
      name: '',
      bordereauxId: 'b',
      subledgerId: 's',
      rules: [
        { key: '1', name: '', expression: ' bordereaux.a = subledger.b ', bordereaux_agg: 'SUM', subledger_agg: 'SUM' },
        { key: '2', name: 'x', expression: '', bordereaux_agg: 'SUM', subledger_agg: 'SUM' },
      ],
      groupBy: [],
      filters: [],
      tolerance: { absolute: 0, percentage: 0, evaluation: 'OR' },
    });
    expect(req.rules).toHaveLength(1);
    expect(req.rules[0].name).toBe('Rule 1');
    expect(req.rules[0].expression).toBe('bordereaux.a = subledger.b');
  });
});

describe('results helpers', () => {
  const g = (labels: string[], variance: string, status: ReconGroup['status']): ReconGroup => ({
    key: labels,
    labels,
    bordereaux_value: '1.00',
    subledger_value: '1.00',
    variance,
    variance_pct: '0',
    status,
    bordereaux_rows: 1,
    subledger_rows: 1,
  });
  const groups = [g(['2023-Q1'], '5.00', 'VARIANCE'), g(['2023-Q2'], '0.00', 'MATCHED'), g(['2024-Q1'], '-9.00', 'VARIANCE')];
  it('filters by status and search', () => {
    expect(filterAndSortGroups(groups, { status: 'VARIANCE', search: '', sortKey: null, sortDir: 'asc' })).toHaveLength(2);
    expect(filterAndSortGroups(groups, { status: 'ALL', search: '2024', sortKey: null, sortDir: 'asc' })).toHaveLength(1);
  });
  it('sorts numerically', () => {
    const out = filterAndSortGroups(groups, { status: 'ALL', search: '', sortKey: 'variance', sortDir: 'asc' });
    expect(out.map((x) => x.variance)).toEqual(['-9.00', '0.00', '5.00']);
  });
  it('builds a year x quarter grid from Q-labels', () => {
    const grid = buildQuarterGrid([
      { period: '2023-Q1', year: 2023, quarter: 'Q1', rows: 10 },
      { period: '2023-Q3', year: 2023, quarter: 'Q3', rows: 4 },
    ]);
    expect(grid.years).toEqual([2023]);
    expect(grid.cells[2023]).toEqual({ 1: 10, 3: 4 });
  });
  it('maps roles to permission', () => {
    expect(canCreateRecon('analyst')).toBe(true);
    expect(canCreateRecon('reviewer')).toBe(false);
  });
});

