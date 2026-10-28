import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportActions } from '../src/components/reports/ReportActions';
import type { ProcessingRun } from '../src/api/types';

const run = { id: 'r1', status: 'COMPLETED' } as unknown as ProcessingRun;

function setup(onDownloadPeriod = vi.fn()) {
  render(
    <ReportActions
      run={run}
      onGenerate={() => {}}
      onDownload={() => {}}
      onDownloadPeriod={onDownloadPeriod}
      generating={false}
      downloading={null}
    />,
  );
  return onDownloadPeriod;
}

describe('ReportActions period download', () => {
  it('offers JSON and human-readable audit report downloads', () => {
    const onDownload = vi.fn();
    render(
      <ReportActions
        run={run}
        onGenerate={() => {}}
        onDownload={onDownload}
        generating={false}
        downloading={null}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Download audit report (JSON)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Download human-readable audit report' }));
    expect(onDownload).toHaveBeenNthCalledWith(1, 'audit_report');
    expect(onDownload).toHaveBeenNthCalledWith(2, 'audit_report_human');
  });

  it('sends the chosen year, quarter and date column', () => {
    const onDownloadPeriod = setup();
    fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2024' } });
    fireEvent.change(screen.getByLabelText('Period'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Filter on'), { target: { value: 'inception_date' } });
    fireEvent.click(screen.getByRole('button', { name: 'Download filtered file' }));
    expect(onDownloadPeriod).toHaveBeenCalledWith({ year: 2024, quarter: 2, field: 'inception_date' });
  });

  it('downloads a whole year when no quarter is chosen', () => {
    const onDownloadPeriod = setup();
    fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2023' } });
    fireEvent.click(screen.getByRole('button', { name: 'Download filtered file' }));
    expect(onDownloadPeriod).toHaveBeenCalledWith({ year: 2023, quarter: undefined, field: 'booking_date' });
  });

  it('refuses an invalid year', () => {
    setup();
    fireEvent.change(screen.getByLabelText('Year'), { target: { value: '12' } });
    expect(screen.getByRole('button', { name: 'Download filtered file' })).toBeDisabled();
  });

  it('lists saved extract versions and downloads the chosen one', () => {
    const extract = {
      id: 'e1', run_id: 'r1', version_number: 2, period_label: '2024Q1', period_field: 'booking_date',
      period_year: 2024, period_quarter: 1, period_month: null, checksum: 'x', total_rows: 7, included_rows: 3,
      included_partial_dates: 2, excluded_outside_period: 3, excluded_undated: 1, generated_at: null,
    };
    const onDownloadExtract = vi.fn();
    render(
      <ReportActions
        run={run}
        onGenerate={() => {}}
        onDownload={() => {}}
        onDownloadPeriod={() => {}}
        extracts={[extract]}
        onDownloadExtract={onDownloadExtract}
        generating={false}
        downloading={null}
      />,
    );
    const list = screen.getByRole('list', { name: 'Saved period extracts' });
    expect(list.textContent).toContain('2024Q1');
    expect(list.textContent).toContain('v2');
    expect(list.textContent).toContain('3 of 7 rows, 2 month-only date(s), 1 without a date left out');
    fireEvent.click(screen.getByRole('button', { name: 'Download' }));
    expect(onDownloadExtract).toHaveBeenCalledWith(extract);
  });
});
