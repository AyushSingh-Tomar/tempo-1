import { useId, useState } from 'react';
import type { Confidence } from '../../api/types';

function colorFor(total: number): string {
  if (total >= 0.8) return 'bg-green-100 text-green-800';
  if (total >= 0.5) return 'bg-amber-100 text-amber-800';
  return 'bg-red-100 text-red-800';
}

/** Shows total confidence; expandable to reveal the weighted evidence breakdown. */
export function ConfidenceBadge({ confidence }: { confidence?: Confidence | null }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const safeConfidence: Confidence = confidence ?? { total: 0, breakdown: {} };
  const pct = Math.round((safeConfidence.total ?? 0) * 100);
  const entries = Object.entries(safeConfidence.breakdown ?? {});

  return (
    <div className="inline-block">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${colorFor(safeConfidence.total ?? 0)} focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500`}
      >
        {pct}% confidence {entries.length > 0 ? (open ? '▲' : '▼') : null}
      </button>
      {open && entries.length > 0 && (
        <div id={panelId} role="tooltip" className="mt-1 w-56 rounded border border-slate-200 bg-white p-2 text-xs shadow-md">
          <table className="w-full">
            <tbody>
              {entries.map(([k, v]) => (
                <tr key={k}>
                  <td className="pr-2 text-slate-500">{k.replace(/_/g, ' ')}</td>
                  <td className="text-right font-mono text-slate-800">{Math.round(v * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
