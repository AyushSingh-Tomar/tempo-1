import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RUN_STATUSES, type ProcessingRun } from '../src/api/types';
import { RunStepperSidebar } from '../src/components/shell/RunStepperSidebar';
import { WIZARD_STEPS, currentStepIndex } from '../src/components/shell/steps';

function makeRun(status: ProcessingRun['status'], extra: Partial<ProcessingRun> = {}): ProcessingRun {
  return {
    id: 'run_1',
    project_id: 'proj_1',
    status,
    source_asset_id: null,
    source_version_id: null,
    mapping_set_id: null,
    treaty_figures_id: null,
    created_at: '2026-01-01T00:00:00Z',
    ...extra,
  };
}

describe('RunStepperSidebar', () => {
  it.each(RUN_STATUSES.filter((s) => s !== 'FAILED'))('marks the correct step active for status %s', (status) => {
    const run = makeRun(status);
    render(<RunStepperSidebar run={run} />);
    const idx = currentStepIndex(status);
    const activeLabel = WIZARD_STEPS[idx].label;
    const activeItem = screen.getByText(activeLabel).closest('div');
    expect(activeItem).toHaveAttribute('aria-current', 'step');
  });

  it('highlights the step the run failed from, not a generic last step', () => {
    const run = makeRun('FAILED', { failed_from_status: 'MAPPING_REVIEW_PENDING' });
    render(<RunStepperSidebar run={run} />);
    expect(screen.getByText(/this run failed/i)).toBeInTheDocument();
    const failedLabel = WIZARD_STEPS[currentStepIndex('FAILED', 'MAPPING_REVIEW_PENDING')].label;
    const failedItem = screen.getByText(failedLabel).closest('div');
    expect(failedItem?.className).toMatch(/red/);
  });

  it('renders all 12 step labels', () => {
    render(<RunStepperSidebar run={makeRun('FILE_UPLOADED')} />);
    for (const step of WIZARD_STEPS) {
      expect(screen.getByText(step.label)).toBeInTheDocument();
    }
  });
});
