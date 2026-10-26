import { useState } from 'react';
import type { DiscrepancyFinding } from '../../api/types';

export function OverrideModal({
  finding,
  onSubmit,
  onClose,
  submitting,
  error,
}: {
  finding: DiscrepancyFinding;
  onSubmit: (reason: string, comment: string) => void;
  onClose: () => void;
  submitting: boolean;
  error?: string | null;
}) {
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="override-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-md rounded-md bg-white p-5 shadow-lg">
        <h2 id="override-modal-title" className="text-lg font-semibold text-slate-900">
          Override discrepancy
        </h2>
        <p className="mt-1 text-sm text-slate-600">{finding.message}</p>

        <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <dt className="text-slate-500">Expected</dt>
          <dd className="font-mono">{String(finding.expected_value ?? '-')}</dd>
          <dt className="text-slate-500">Observed</dt>
          <dd className="font-mono">{String(finding.observed_value ?? '-')}</dd>
        </dl>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (reason.trim()) onSubmit(reason.trim(), comment.trim());
          }}
          className="mt-4 space-y-3"
        >
          <div>
            <label htmlFor="override-reason" className="block text-sm font-medium text-slate-800">
              Reason <span className="text-red-600">*</span>
            </label>
            <textarea
              id="override-reason"
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded border border-slate-300 p-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="override-comment" className="block text-sm font-medium text-slate-800">
              Comment (optional)
            </label>
            <textarea
              id="override-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded border border-slate-300 p-2 text-sm"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !reason.trim()}
              className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Submitting...' : 'Submit override'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
