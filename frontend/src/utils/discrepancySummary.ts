import type { DiscrepancyFinding } from '../api/types';

export interface DiscrepancySummary {
  total: number;
  resolvedCount: number;
  unresolvedCount: number;
  bySeverity: Record<string, number>;
  byCategory: Record<string, number>;
  isClean: boolean;
  allResolved: boolean;
}

/** A finding is considered resolved once a human has overridden it. */
function isResolved(f: DiscrepancyFinding): boolean {
  return f.status === 'OVERRIDDEN';
}

export function summarizeDiscrepancies(findings: DiscrepancyFinding[]): DiscrepancySummary {
  const bySeverity: Record<string, number> = {};
  const byCategory: Record<string, number> = {};
  let resolvedCount = 0;
  for (const f of findings) {
    bySeverity[f.severity] = (bySeverity[f.severity] ?? 0) + 1;
    byCategory[f.category] = (byCategory[f.category] ?? 0) + 1;
    if (isResolved(f)) resolvedCount += 1;
  }
  const total = findings.length;
  const unresolvedCount = total - resolvedCount;
  return {
    total,
    resolvedCount,
    unresolvedCount,
    bySeverity,
    byCategory,
    isClean: total === 0,
    allResolved: total > 0 && unresolvedCount === 0,
  };
}
