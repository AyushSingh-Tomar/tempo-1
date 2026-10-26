import type { DiscrepancyFinding } from '../../api/types';
import { summarizeDiscrepancies } from '../../utils/discrepancySummary';

/**
 * Must look intentional (not accidentally empty) for a clean run, and must
 * never claim "fully reconciled" while unresolved findings exist.
 */
export function DiscrepancySummary({ findings }: { findings: DiscrepancyFinding[] }) {
  const summary = summarizeDiscrepancies(findings);

  if (summary.isClean) {
    return (
      <div role="status" className="rounded-md border border-green-200 bg-green-50 p-4 text-green-900">
        <p className="font-medium">No discrepancies found</p>
        <p className="mt-1 text-sm">
          The financial checks ran against this run's data and treaty figures and found zero discrepancies.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div
        role="status"
        className={`rounded-md border p-4 ${
          summary.allResolved ? 'border-blue-200 bg-blue-50 text-blue-900' : 'border-amber-200 bg-amber-50 text-amber-900'
        }`}
      >
        <p className="font-medium">
          {summary.allResolved
            ? `All ${summary.total} discrepancies have been reviewed and overridden.`
            : `${summary.unresolvedCount} of ${summary.total} discrepancies still need review.`}
        </p>
        <p className="mt-1 text-sm">
          {summary.allResolved
            ? 'Every finding has a recorded human decision; the original findings remain visible below.'
            : 'This run has findings that are not yet overridden. It is not reconciled until each is reviewed.'}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded border border-slate-200 p-3">
          <p className="text-xs text-slate-500">Total</p>
          <p className="text-lg font-semibold">{summary.total}</p>
        </div>
        <div className="rounded border border-slate-200 p-3">
          <p className="text-xs text-slate-500">Resolved</p>
          <p className="text-lg font-semibold">{summary.resolvedCount}</p>
        </div>
        <div className="rounded border border-slate-200 p-3">
          <p className="text-xs text-slate-500">Unresolved</p>
          <p className="text-lg font-semibold">{summary.unresolvedCount}</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">By severity</p>
          <ul className="mt-1 text-sm text-slate-700">
            {Object.entries(summary.bySeverity).map(([k, v]) => (
              <li key={k}>
                {k}: {v}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">By category</p>
          <ul className="mt-1 text-sm text-slate-700">
            {Object.entries(summary.byCategory).map(([k, v]) => (
              <li key={k}>
                {k}: {v}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
