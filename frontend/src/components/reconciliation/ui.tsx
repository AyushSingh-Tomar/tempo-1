import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { describeError, isApiError } from '../../api/errors';

export const btnPrimary =
  'rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700';
export const btnSecondary =
  'rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500';
export const inputCls =
  'rounded border border-slate-300 bg-white px-2 py-1.5 text-sm disabled:bg-slate-100 disabled:text-slate-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500';

/** Error banner that also lists server-provided `details` (e.g. expression validation messages). */
export function ApiErrorBanner({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  const details = isApiError(error) ? error.details.map((d) => d.message).filter(Boolean) : [];
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      {title && <p className="font-medium">{title}</p>}
      <p>{describeError(error)}</p>
      {details.length > 0 && (
        <ul className="mt-1 list-disc pl-5">
          {details.map((m, i) => (
            <li key={i}>{String(m)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Section({ title, step, children, hint }: { title: string; step?: string; children: ReactNode; hint?: string }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="rounded-md border border-slate-200 bg-white p-4">
      <h3 id={id} className="text-sm font-semibold text-slate-900">
        {step && <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{step}</span>}
        {title}
      </h3>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function TypeBadge({ type }: { type: string }) {
  const tone: Record<string, string> = {
    DATE: 'bg-purple-100 text-purple-800',
    INTEGER: 'bg-blue-100 text-blue-800',
    DECIMAL: 'bg-blue-100 text-blue-800',
    STRING: 'bg-slate-100 text-slate-700',
    EMPTY: 'bg-slate-50 text-slate-400',
  };
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${tone[type] ?? 'bg-slate-100 text-slate-700'}`}>{type}</span>;
}

/** Accessible multi-select dropdown made of a disclosure button and a checkbox list. */
export function MultiSelect({
  label,
  options,
  selected,
  onChange,
  disabled,
  placeholder = 'None selected',
}: {
  label: string;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const summary = selected.length ? selected.join(', ') : placeholder;
  return (
    <div className="relative">
      <span className="block text-xs font-medium text-slate-600">{label}</span>
      <button
        type="button"
        disabled={disabled}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`${label}: ${summary}`}
        onClick={() => setOpen((o) => !o)}
        className={`${inputCls} mt-1 w-full max-w-xs truncate text-left`}
      >
        {summary}
      </button>
      {open && (
        <div id={panelId} role="group" aria-label={label} className="absolute z-20 mt-1 max-h-60 w-72 overflow-y-auto rounded border border-slate-200 bg-white p-2 shadow-lg">
          {options.map((o) => (
            <label key={o.value} className="flex items-center gap-2 px-1 py-0.5 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(o.value)}
                onChange={(e) => onChange(e.target.checked ? [...selected, o.value] : selected.filter((v) => v !== o.value))}
              />
              {o.label}
            </label>
          ))}
          <button type="button" onClick={() => setOpen(false)} className="mt-1 text-xs text-slate-500 underline">
            Done
          </button>
        </div>
      )}
    </div>
  );
}
