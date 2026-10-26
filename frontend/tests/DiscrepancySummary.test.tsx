import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { DiscrepancyFinding } from '../src/api/types';
import { DiscrepancySummary } from '../src/components/discrepancies/DiscrepancySummary';
import { summarizeDiscrepancies } from '../src/utils/discrepancySummary';

function finding(overrides: Partial<DiscrepancyFinding>): DiscrepancyFinding {
  return {
    id: 'd1',
    check_id: 'MCR-A1',
    category: 'CORE_DEDUCTION',
    severity: 'WARNING',
    status: 'UNRESOLVED',
    affected_row_number: 1,
    affected_field: 'gross_amount',
    expected_value: '100.00',
    observed_value: '90.00',
    variance: '-10.00',
    message: 'Gross minus commission does not equal net.',
    evidence: null,
    ...overrides,
  };
}

describe('summarizeDiscrepancies', () => {
  it('reports a clean run distinctly from a run with findings', () => {
    expect(summarizeDiscrepancies([]).isClean).toBe(true);
    expect(summarizeDiscrepancies([finding({})]).isClean).toBe(false);
  });

  it('is not allResolved while any finding is not OVERRIDDEN', () => {
    const summary = summarizeDiscrepancies([finding({ status: 'UNRESOLVED' }), finding({ id: 'd2', status: 'OVERRIDDEN' })]);
    expect(summary.allResolved).toBe(false);
    expect(summary.unresolvedCount).toBe(1);
  });

  it('is allResolved only once every finding is OVERRIDDEN', () => {
    const summary = summarizeDiscrepancies([finding({ status: 'OVERRIDDEN' }), finding({ id: 'd2', status: 'OVERRIDDEN' })]);
    expect(summary.allResolved).toBe(true);
    expect(summary.unresolvedCount).toBe(0);
  });
});

describe('DiscrepancySummary component', () => {
  it('shows a clear "no discrepancies" state for a clean run, not a broken-looking empty page', () => {
    render(<DiscrepancySummary findings={[]} />);
    expect(screen.getByText(/no discrepancies found/i)).toBeInTheDocument();
  });

  it('never claims the run is fully reconciled while unresolved findings exist', () => {
    render(<DiscrepancySummary findings={[finding({ status: 'UNRESOLVED' })]} />);
    expect(screen.queryByText(/fully reconciled/i)).not.toBeInTheDocument();
    expect(screen.getByText(/still need review/i)).toBeInTheDocument();
  });

  it('shows a resolved (not "fully reconciled") message once every finding is overridden', () => {
    render(<DiscrepancySummary findings={[finding({ status: 'OVERRIDDEN' })]} />);
    expect(screen.queryByText(/fully reconciled/i)).not.toBeInTheDocument();
    expect(screen.getByText(/reviewed and overridden/i)).toBeInTheDocument();
  });
});
