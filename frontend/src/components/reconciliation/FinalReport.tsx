import type { DatasetPreview, DatasetReport } from '../../api/reconTypes';
import { buildQuarterGrid } from '../../utils/recon';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { TypeBadge } from './ui';

function countsList(title: string, m: Record<string, number> | undefined) {
  const entries = Object.entries(m ?? {}).filter(([, n]) => n > 0);
  if (!entries.length) return null;
  return (
    <li>
      {title}: {entries.map(([c, n]) => `${c} (${n})`).join(', ')}
    </li>
  );
}

export function DatasetPreviewTable({
  preview,
  isLoading,
  error,
  onRetry,
}: {
  preview: DatasetPreview | undefined;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  if (isLoading) return <LoadingState label="Loading preview..." />;
  if (error) return <ErrorState error={error} title="Could not load the preview" onRetry={onRetry} />;
  if (!preview || preview.rows.length === 0) return <p className="text-sm text-slate-500">No rows to preview.</p>;
  return (
    <div className="overflow-x-auto rounded border border-slate-200">
      <table className="min-w-full text-xs">
        <caption className="sr-only">Data preview (first {preview.rows.length} rows)</caption>
        <thead className="bg-slate-50">
          <tr>
            {preview.columns.map((c) => (
              <th
                key={c.name}
                scope="col"
                className={`px-2 py-1 text-left font-medium ${c.derived ? 'bg-indigo-50 text-indigo-800' : 'text-slate-600'}`}
                title={c.derived ? 'Derived / lineage column added by the platform' : undefined}
              >
                <span className="font-mono">{c.name}</span> <TypeBadge type={c.type} />
                {c.derived && <span className="ml-1 text-[10px] uppercase">derived</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-100">
              {preview.columns.map((c) => (
                <td key={c.name} className={`whitespace-nowrap px-2 py-1 ${c.derived ? 'bg-indigo-50/50 text-indigo-900' : ''}`}>
                  {String(r[c.name] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function FinalReport({
  report,
  preview,
  previewLoading,
  previewError,
  onRetryPreview,
}: {
  report: DatasetReport;
  preview: DatasetPreview | undefined;
  previewLoading: boolean;
  previewError: unknown;
  onRetryPreview: () => void;
}) {
  const grid = buildQuarterGrid(report.quarters ?? []);
  const warningCounts = [
    countsList('Ambiguous dates', report.ambiguous_dates),
    countsList('Unparsed dates', report.unparsed_dates),
    countsList('Unparsed numbers', report.unparsed_numbers),
  ].filter(Boolean);
  return (
    <div className="space-y-5">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ['Rows', report.row_count.toLocaleString()],
          ['Columns', String(report.column_count)],
          ['Date format', report.date_format],
          ['Period column', report.period_column ?? 'none'],
        ].map(([k, v]) => (
          <div key={k} className="rounded border border-slate-200 p-2">
            <dt className="text-xs text-slate-500">{k}</dt>
            <dd className="font-medium text-slate-900">{v}</dd>
          </div>
        ))}
      </dl>

      <div>
        <h4 className="text-sm font-semibold text-slate-900">Years: {report.years.join(', ') || 'none'}</h4>
        {grid.years.length > 0 && (
          <table className="mt-2 text-sm">
            <caption className="sr-only">Row counts by year and quarter</caption>
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th scope="col" className="pr-4">Year</th>
                {[1, 2, 3, 4].map((q) => <th key={q} scope="col" className="pr-4 text-right">Q{q}</th>)}
              </tr>
            </thead>
            <tbody>
              {grid.years.map((y) => (
                <tr key={y} className="border-t border-slate-100">
                  <th scope="row" className="pr-4 text-left font-medium">{y}</th>
                  {[1, 2, 3, 4].map((q) => (
                    <td key={q} className="pr-4 text-right tabular-nums">{grid.cells[y]?.[q]?.toLocaleString() ?? '-'}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div>
        <h4 className="text-sm font-semibold text-slate-900">Coverage per file</h4>
        <ul className="mt-1 space-y-1 text-sm">
          {report.files.map((f) => (
            <li key={f.file}>
              <span className="font-medium">{f.file}</span> - {f.rows.toLocaleString()} rows
              <span className="text-xs text-slate-500">
                {' '}
                {f.periods.length ? `periods ${f.periods[0]} to ${f.periods[f.periods.length - 1]} (${f.periods.length})` : 'no periods'}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {(report.warnings.length > 0 || report.rows_without_period > 0 || report.cross_file_duplicate_rows > 0 || warningCounts.length > 0) && (
        <div role="alert" className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Warnings</p>
          <ul className="mt-1 list-disc pl-5 text-xs">
            {report.warnings.map((w, i) => <li key={i}>{w}</li>)}
            {report.rows_without_period > 0 && <li>{report.rows_without_period} row(s) have no period.</li>}
            {report.cross_file_duplicate_rows > 0 && <li>{report.cross_file_duplicate_rows} row(s) are duplicated across files.</li>}
            {warningCounts}
          </ul>
        </div>
      )}

      <div>
        <h4 className="mb-1 text-sm font-semibold text-slate-900">Data preview</h4>
        <p className="mb-2 text-xs text-slate-500">Highlighted columns are derived or lineage columns added by the platform.</p>
        <DatasetPreviewTable preview={preview} isLoading={previewLoading} error={previewError} onRetry={onRetryPreview} />
      </div>
    </div>
  );
}
