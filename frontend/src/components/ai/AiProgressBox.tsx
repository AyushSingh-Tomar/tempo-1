import { useEffect, useState } from 'react';

function useElapsedSeconds(): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 250);
    return () => window.clearInterval(id);
  }, []);
  return seconds;
}

/**
 * Shown while a call to the AI model is in flight, so a slow answer never looks like a hang.
 * Mount it only while the request is pending (the timer starts on mount).
 */
export function AiProgressBox({
  title,
  detail,
  timeoutSeconds,
  model,
}: {
  title: string;
  detail?: string;
  /** The server stops waiting after this long and carries on without AI. */
  timeoutSeconds: number;
  model?: string | null;
}) {
  const elapsed = useElapsedSeconds();
  const over = elapsed >= timeoutSeconds;
  const pct = Math.min(100, Math.round((elapsed / Math.max(1, timeoutSeconds)) * 100));

  return (
    <div role="status" aria-live="polite" className="rounded-md border border-sky-200 bg-sky-50 p-4 text-sky-900">
      <div className="flex items-start gap-3">
        <span
          className="mt-0.5 h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-sky-300 border-t-sky-700"
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{title}</p>
          {detail && <p className="mt-0.5 text-sm text-sky-800">{detail}</p>}
          <div
            className="mt-3 h-1.5 overflow-hidden rounded bg-sky-100"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={timeoutSeconds}
            aria-valuenow={Math.min(elapsed, timeoutSeconds)}
            aria-label="Time waiting for the AI model"
          >
            <div className="h-full bg-sky-500 transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-xs text-sky-800">
            {over
              ? `Waited ${elapsed}s - taking longer than expected. The system gives up after about ${timeoutSeconds}s and continues without AI.`
              : `Waiting for the AI model${model ? ` (${model})` : ''}: ${elapsed}s of up to ${timeoutSeconds}s.`}
          </p>
          <p className="mt-1 text-xs text-sky-700">
            AI only adds suggestions. If it cannot answer, everything still works without it.
          </p>
        </div>
      </div>
    </div>
  );
}
