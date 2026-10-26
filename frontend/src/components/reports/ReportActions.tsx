import { useState } from 'react';
import type { PeriodExtract, ProcessingRun } from '../../api/types';

export type PeriodSelection = { year: number; quarter?: number; field: string };

const PERIOD_FIELDS: { value: string; label: string }[] = [
  { value: 'booking_date', label: 'Booking date' },
  { value: 'inception_date', label: 'Inception date' },
  { value: 'transaction_effective_date', label: 'Transaction effective date' },
  { value: 'expiry_date', label: 'Expiry date' },
];

function artifactExists(run: ProcessingRun | undefined, type: 'processed_file' | 'audit_report'): boolean {
  if (!run?.artifacts) return run?.status === 'COMPLETED'; // fallback assumption documented in handback report
  return run.artifacts.some((a) => a.artifact_type === type);
}

export function ReportActions({
  run,
  onGenerate,
  onDownload,
  onDownloadPeriod,
  extracts,
  onDownloadExtract,
  generating,
  downloading,
}: {
  run: ProcessingRun | undefined;
  onGenerate: () => void;
  onDownload: (type: 'processed_file' | 'audit_report') => void;
  /** Creates (or reuses) the period extract and downloads it. */
  onDownloadPeriod?: (period: PeriodSelection) => void;
  extracts?: PeriodExtract[];
  onDownloadExtract?: (extract: PeriodExtract) => void;
  generating: boolean;
  downloading: 'processed_file' | 'audit_report' | null;
}) {
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [quarter, setQuarter] = useState('');
  const [field, setField] = useState('booking_date');
  const yearNumber = Number(year);
  const yearValid = Number.isInteger(yearNumber) && yearNumber >= 1900 && yearNumber <= 2200;
  const canGenerate = run?.status === 'REPORT_GENERATION_PENDING';
  const processedReady = artifactExists(run, 'processed_file');
  const auditReady = artifactExists(run, 'audit_report');
  const completed = run?.status === 'COMPLETED';

  return (
    <div className="space-y-4">
      {canGenerate && (
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {generating ? 'Generating reports...' : 'Generate processed file and audit report'}
        </button>
      )}

      {completed && (
        <div role="status" className="rounded border border-green-200 bg-green-50 p-3 text-sm text-green-900">
          This run is complete. Both artifacts have been generated from the actual run results.
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={!processedReady || downloading === 'processed_file'}
          onClick={() => onDownload('processed_file')}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading === 'processed_file' ? 'Downloading...' : 'Download processed file'}
        </button>
        <button
          type="button"
          disabled={!auditReady || downloading === 'audit_report'}
          onClick={() => onDownload('audit_report')}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading === 'audit_report' ? 'Downloading...' : 'Download audit report'}
        </button>
      </div>
      {onDownloadPeriod && (
        <fieldset className="rounded border border-slate-200 p-3">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Download one period
          </legend>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm text-slate-700">
              Year
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                className="mt-1 block w-24 rounded border border-slate-300 px-2 py-1"
              />
            </label>
            <label className="text-sm text-slate-700">
              Period
              <select
                value={quarter}
                onChange={(e) => setQuarter(e.target.value)}
                className="mt-1 block rounded border border-slate-300 px-2 py-1"
              >
                <option value="">Whole year</option>
                {[1, 2, 3, 4].map((q) => (
                  <option key={q} value={q}>{`Q${q}`}</option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-700">
              Filter on
              <select
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="mt-1 block rounded border border-slate-300 px-2 py-1"
              >
                {PERIOD_FIELDS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              disabled={!processedReady || !yearValid}
              onClick={() => onDownloadPeriod({ year: yearNumber, quarter: quarter ? Number(quarter) : undefined, field })}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Download filtered file
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Dates given only as month and year (flagged at cleaning) are included when their month falls inside the
            period. Rows with no date in the chosen column are left out. Each extract is saved as an immutable,
            numbered version.
          </p>
          {extracts && extracts.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-100 text-sm" aria-label="Saved period extracts">
              {extracts.map((e) => (
                <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5">
                  <span className="text-slate-700">
                    {e.period_label} · {e.period_field} · v{e.version_number}
                    <span className="ml-2 text-xs text-slate-500">
                      {e.included_rows} of {e.total_rows} rows
                      {e.included_partial_dates > 0 ? `, ${e.included_partial_dates} month-only date(s)` : ''}
                      {e.excluded_undated > 0 ? `, ${e.excluded_undated} without a date left out` : ''}
                    </span>
                  </span>
                  {onDownloadExtract && (
                    <button
                      type="button"
                      onClick={() => onDownloadExtract(e)}
                      className="text-xs font-medium text-slate-600 underline hover:text-slate-900"
                    >
                      Download
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </fieldset>
      )}
      {!processedReady && !auditReady && !canGenerate && !completed && (
        <p className="text-xs text-slate-500">Reports are not ready yet.</p>
      )}
    </div>
  );
}
