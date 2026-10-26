import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TreatyFiguresForm } from '../src/components/treaty/TreatyFiguresForm';
import type { DerivedTreatyInputs } from '../src/api/types';

const base = { source_column: null, filled_rows: 10, total_rows: 10, distinct: [], example_rows: [] };
const derived: DerivedTreatyInputs = {
  currencies: [],
  settlement_currency: null,
  has_currency_column: true,
  has_fx_column: true,
  figures: [
    { ...base, figure: 'commission_pct', status: 'UNIFORM', value: '0.25', source_column: 'Comm %' },
    {
      ...base,
      figure: 'brokerage_pct',
      status: 'VARIES',
      value: '0.0125',
      distinct: [
        { value: '0.0125', row_count: 8 },
        { value: '0.02', row_count: 2 },
      ],
      example_rows: [10, 11],
    },
    { ...base, figure: 'tax_pct', status: 'NOT_FOUND', value: null, filled_rows: 0 },
  ],
};

describe('TreatyFiguresForm derived figures', () => {
  it('pre-fills uniform values as derived from file and alerts when rows disagree', () => {
    render(<TreatyFiguresForm derived={derived} onSubmit={() => {}} submitting={false} />);
    expect((screen.getByLabelText(/Commission %/) as HTMLInputElement).value).toBe('25');
    expect(screen.getByText(/Derived from file \(Comm %\)/)).toBeTruthy();
    expect((screen.getByLabelText(/Brokerage %/) as HTMLInputElement).value).toBe('1.25');
    expect(screen.getByRole('alert').textContent).toMatch(/Not the same on all rows: 1.25% on 8 row\(s\), 2% on 2 row\(s\)/);
    expect(screen.getByText(/Not found in the file/)).toBeTruthy();
  });

  it('marks a derived value as entered by you once edited', () => {
    render(<TreatyFiguresForm derived={derived} onSubmit={() => {}} submitting={false} />);
    fireEvent.change(screen.getByLabelText(/Commission %/), { target: { value: '27' } });
    expect(screen.queryByText(/Derived from file \(Comm %\)/)).toBeNull();
    expect(screen.getAllByText('Entered by you').length).toBeGreaterThan(0);
  });
});
