import { useEffect, useRef, useState } from 'react';

/**
 * A destructive-action dialog that only enables its confirm button once the
 * user has typed ``expected`` exactly (surrounding spaces ignored).
 */
export function TypeToConfirmDialog({
  title,
  description,
  expected,
  confirmLabel,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  expected: string;
  confirmLabel: string;
  busy: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const matches = typed.trim() === expected.trim();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && !busy) onCancel();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-md rounded-md bg-white p-5 shadow-lg">
        <h2 id="confirm-dialog-title" className="text-lg font-semibold text-slate-900">
          {title}
        </h2>
        <p className="mt-1 text-sm text-slate-600">{description}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (matches && !busy) onConfirm();
          }}
          className="mt-4 space-y-3"
        >
          <div>
            <label htmlFor="confirm-name" className="block text-sm font-medium text-slate-800">
              Type <span className="font-mono font-semibold">{expected}</span> to confirm
            </label>
            <input
              id="confirm-name"
              ref={inputRef}
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
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
              onClick={onCancel}
              disabled={busy}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!matches || busy}
              className="rounded bg-red-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? 'Deleting...' : confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
