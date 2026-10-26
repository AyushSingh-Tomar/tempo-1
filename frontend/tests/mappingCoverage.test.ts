import { describe, expect, it } from 'vitest';
import type { MappingCandidate } from '../src/api/types';
import { computeMappingCoverage } from '../src/utils/mappingCoverage';

function candidate(overrides: Partial<MappingCandidate>): MappingCandidate {
  return {
    id: 'c1',
    source_column: 'COL',
    target_field: 'claim_id',
    confidence: { total: 0.9, breakdown: {} },
    evidence: [],
    status: 'PROPOSED',
    ...overrides,
  };
}

describe('computeMappingCoverage', () => {
  it('returns null percentage when required fields are unknown', () => {
    const coverage = computeMappingCoverage([], null);
    expect(coverage.percentage).toBeNull();
    expect(coverage.isComplete).toBe(false);
  });

  it('counts only APPROVED candidates toward coverage', () => {
    const candidates = [
      candidate({ id: 'a', target_field: 'claim_id', status: 'APPROVED' }),
      candidate({ id: 'b', target_field: 'policy_id', status: 'PROPOSED' }),
    ];
    const coverage = computeMappingCoverage(candidates, ['claim_id', 'policy_id']);
    expect(coverage.mappedRequired).toBe(1);
    expect(coverage.totalRequired).toBe(2);
    expect(coverage.missingRequired).toEqual(['policy_id']);
    expect(coverage.isComplete).toBe(false);
  });

  it('ignores required fields that do not exist in the source file when deciding completion', () => {
    const candidates = [
      candidate({ id: 'a', target_field: 'claim_id', status: 'APPROVED' }),
    ];
    const coverage = computeMappingCoverage(candidates, ['claim_id', 'policy_id']);
    expect(coverage.totalRequired).toBe(1);
    expect(coverage.mappedRequired).toBe(1);
    expect(coverage.missingRequired).toEqual([]);
    expect(coverage.isComplete).toBe(true);
  });

  it('is complete once every required field has an approved mapping', () => {
    const candidates = [
      candidate({ id: 'a', target_field: 'claim_id', status: 'APPROVED' }),
      candidate({ id: 'b', target_field: 'policy_id', status: 'APPROVED' }),
    ];
    const coverage = computeMappingCoverage(candidates, ['claim_id', 'policy_id']);
    expect(coverage.isComplete).toBe(true);
    expect(coverage.percentage).toBe(1);
  });

  it('counts manual approved mappings as coverage too', () => {
    const candidates = [
      candidate({ id: 'a', target_field: 'claim_id', status: 'PROPOSED' }),
    ];
    const coverage = computeMappingCoverage(candidates, ['claim_id'], [
      { source_column: 'manual_col', target_field: 'claim_id' },
    ]);
    expect(coverage.mappedRequired).toBe(1);
    expect(coverage.isComplete).toBe(true);
    expect(coverage.missingRequired).toEqual([]);
  });

  it('treats an empty required-fields list as already complete', () => {
    const coverage = computeMappingCoverage([], []);
    expect(coverage.isComplete).toBe(true);
    expect(coverage.percentage).toBe(1);
  });
});
