import { useState } from 'react';
import type { CleaningResult, Transformation, CleaningWarning } from '../../api/types';

function describeTransformation(t: Transformation): string {
  if (typeof t === 'string') return t;
  const label = t.description ?? t.message ?? t.rule ?? t.operation ?? t.type ?? t.code ?? 'Change applied';
  const scope = t.column ?? (t.columns && t.columns.length ? t.columns.join(', ') : null);
  const count = t.affected_rows ?? t.affected_count ?? t.count;
  const parts = [label];
  if (scope) parts.push(`(column: ${scope})`);
  if (typeof count === 'number') parts.push(`- ${count} row${count === 1 ? '' : 's'} affected`);
  return parts.join(' ');
}

function describeWarning(w: CleaningWarning): string {
  if (typeof w === 'string') return w;
  const label = w.message ?? w.description ?? w.type ?? w.code ?? 'Warning';
  const scope = w.column ? ` (column: ${w.column})` : '';
  const row = w.row ?? w.row_number;
  const rowPart = typeof row === 'number' ? ` [row ${row}]` : '';
  return `${label}${scope}${rowPart}`;
}

function formatCount(value: number | null | undefined): string {
  const safeValue = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return safeValue.toLocaleString();
}

export function CleaningReview({
  result,
  onAcknowledge,
  onRerun,
  isAcknowledging,
  isRerunning,
  disabled,
}: {
  result: CleaningResult;
  onAcknowledge: () => void;
  onRerun: (reason: string) => void;
  isAcknowledging: boolean;
  isRerunning: boolean;
  disabled?: boolean;
}) {
  const [rerunReason, setRerunReason] = useState('');
  const [showRerunForm, setShowRerunForm] = useState(false);
  const transformations = Array.isArray(result.transformations) ? result.transformations : [];
  const warnings = Array.isArray(result.warnings) ? result.warnings : [];

  return (
    <div className="space-y-6">
      <section aria-labelledby="before-after-heading">
        <h3 id="before-after-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Before / After
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="rounded border border-slate-200 p-3">
            <p className="text-xs text-slate-500">Rows before</p>
            <p className="text-lg font-semibold">{formatCount(result.before_row_count)}</p>
          </div>
          <div className="rounded border border-slate-200 p-3">
            <p className="text-xs text-slate-500">Rows after</p>
            <p className="text-lg font-semibold">{formatCount(result.after_row_count)}</p>
          </div>
          <div className="rounded border border-slate-200 p-3">
            <p className="text-xs text-slate-500">Columns before</p>
            <p className="text-lg font-semibold">{formatCount(result.before_column_count)}</p>
          </div>
          <div className="rounded border border-slate-200 p-3">
            <p className="text-xs text-slate-500">Columns after</p>
            <p className="text-lg font-semibold">{formatCount(result.after_column_count)}</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">Attempt #{result.attempt_number}</p>
      </section>

      <section aria-labelledby="transformations-heading">
        <h3 id="transformations-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Transformations ({transformations.length})
        </h3>
        {transformations.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No transformations were necessary.</p>
        ) : (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {transformations.map((t, i) => (
              <li key={i}>{describeTransformation(t)}</li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="warnings-heading">
        <h3 id="warnings-heading" className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          Warnings ({warnings.length})
        </h3>
        {warnings.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No warnings were raised.</p>
        ) : (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-700">
            {warnings.map((w, i) => (
              <li key={i}>{describeWarning(w)}</li>
            ))}
          </ul>
        )}
      </section>

      <div role="note" className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
        Acknowledging means you reviewed this result - it is not a claim that every value is correct.
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onAcknowledge}
          disabled={disabled || isAcknowledging}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          {isAcknowledging ? 'Acknowledging...' : 'Acknowledge and continue'}
        </button>
        <button
          type="button"
          onClick={() => setShowRerunForm((s) => !s)}
          disabled={disabled || isRerunning}
          className="rounded border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        >
          Reject and rerun
        </button>
      </div>

      {showRerunForm && (
        <div className="rounded border border-slate-200 p-3">
          <label htmlFor="rerun-reason" className="block text-sm font-medium text-slate-700">
            Why are you requesting another cleaning attempt?
          </label>
          <textarea
            id="rerun-reason"
            value={rerunReason}
            onChange={(e) => setRerunReason(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded border border-slate-300 p-2 text-sm"
          />
          <button
            type="button"
            disabled={isRerunning || rerunReason.trim() === ''}
            onClick={() => onRerun(rerunReason.trim())}
            className="mt-2 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRerunning ? 'Requesting rerun...' : 'Submit rerun request'}
          </button>
          <p className="mt-1 text-xs text-slate-500">
            This preserves attempt #{result.attempt_number} and starts a new attempt; it does not overwrite it.
          </p>
        </div>
      )}
    </div>
  );
}
