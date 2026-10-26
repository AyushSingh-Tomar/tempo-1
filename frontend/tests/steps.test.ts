import { describe, expect, it } from 'vitest';
import { RUN_STATUSES } from '../src/api/types';
import { WIZARD_STEPS, currentStepIndex, stepIndexForStatus, stepState } from '../src/components/shell/steps';

describe('wizard step mapping', () => {
  it('maps every non-FAILED status to exactly one step', () => {
    for (const status of RUN_STATUSES) {
      if (status === 'FAILED') continue;
      const idx = stepIndexForStatus(status);
      expect(idx, `status ${status} should map to a known step`).toBeGreaterThanOrEqual(0);
      expect(WIZARD_STEPS[idx].statuses).toContain(status);
    }
  });

  it('is a strictly increasing sequence through the lifecycle', () => {
    const order = RUN_STATUSES.filter((s) => s !== 'FAILED');
    let lastIndex = -1;
    for (const status of order) {
      const idx = stepIndexForStatus(status);
      expect(idx).toBeGreaterThanOrEqual(lastIndex);
      lastIndex = idx;
    }
  });

  it('resolves FAILED to the step it failed from', () => {
    expect(currentStepIndex('FAILED', 'MAPPING_REVIEW_PENDING')).toBe(stepIndexForStatus('MAPPING_REVIEW_PENDING'));
    expect(currentStepIndex('FAILED', null)).toBe(0);
  });

  it('derives completed/active/upcoming/failed step states correctly', () => {
    const current = 5;
    expect(stepState(2, current, false)).toBe('completed');
    expect(stepState(5, current, false)).toBe('active');
    expect(stepState(8, current, false)).toBe('upcoming');
    expect(stepState(5, current, true)).toBe('failed');
  });
});
