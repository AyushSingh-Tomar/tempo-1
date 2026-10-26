import type { DiscrepancyFinding } from '../../api/types';
import { StatusBadge } from '../common/StatusBadge';

export function DiscrepancyDetailDrawer({
  finding,
  onClose,
  onOverride,
  canOverride,
}: {
  finding: DiscrepancyFinding;
  onClose: () => void;
  onOverride: () => void;
  canOverride: boolean;
}) {
  return (
    <aside
      role="complementary"
      aria-label={`Discrepancy detail: ${finding.check_id}`}
      className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-xl"
    >
      <div className="flex items-start justify-between">
        <h2 className="text-lg font-semibold text-slate-900">{finding.check_id}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close detail panel"
          className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
        >
          Close
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <StatusBadge value={finding.severity} />
        <StatusBadge value={finding.status} />
      </div>

      <p className="mt-3 text-sm text-slate-700">{finding.message}</p>

      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">Category</dt>
          <dd>{finding.category}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Affected row</dt>
          <dd>{finding.affected_row_number ?? 'n/a'}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Affected field</dt>
          <dd>{finding.affected_field ?? 'n/a'}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Expected</dt>
          <dd className="font-mono">{String(finding.expected_value ?? '-')}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Observed</dt>
          <dd className="font-mono">{String(finding.observed_value ?? '-')}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Variance</dt>
          <dd className="font-mono">{String(finding.variance ?? '-')}</dd>
        </div>
      </dl>

      {finding.evidence && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-slate-600">Evidence</h3>
          <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-xs text-slate-700">
            {JSON.stringify(finding.evidence, null, 2)}
          </pre>
        </div>
      )}

      {finding.override ? (
        <div className="mt-4 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
          <p className="font-medium text-blue-900">Overridden</p>
          <p className="mt-1 text-blue-900">Reason: {finding.override.reason}</p>
          {finding.override.comment && <p className="text-blue-900">Comment: {finding.override.comment}</p>}
          <p className="mt-1 text-xs text-blue-700">
            This decision does not delete the original finding above - both are preserved.
          </p>
        </div>
      ) : (
        canOverride && (
          <button
            type="button"
            onClick={onOverride}
            className="mt-4 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
          >
            Override this finding
          </button>
        )
      )}
    </aside>
  );
}
