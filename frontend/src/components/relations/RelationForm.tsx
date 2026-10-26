import { useState } from 'react';
import type { MoneyRelationTerm, RelationFieldOption, TreatyFactorOption } from '../../api/types';
import { factorText, labelResolver, relationText } from '../../utils/relations';

const INPUT = 'rounded border border-slate-300 bg-white px-2 py-1 text-sm';

export interface RelationFormValue {
  label: string;
  target_field: string;
  terms: MoneyRelationTerm[];
}

function FieldSelect({
  id,
  value,
  onChange,
  fields,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  fields: RelationFieldOption[];
  placeholder: string;
}) {
  const dictionary = fields.filter((f) => f.kind === 'dictionary');
  const extra = fields.filter((f) => f.kind === 'extra');
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={`${INPUT} min-w-0 max-w-full`}>
      <option value="">{placeholder}</option>
      {dictionary.length > 0 && (
        <optgroup label="Mapped columns">
          {dictionary.map((f) => (
            <option key={f.field} value={f.field}>
              {f.label}
            </option>
          ))}
        </optgroup>
      )}
      {extra.length > 0 && (
        <optgroup label="Other numeric columns from your file">
          {extra.map((f) => (
            <option key={f.field} value={f.field}>
              {f.label}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  );
}

/** Build or edit one relation:  target = ± column × factor ± column ... */
export function RelationForm({
  fields,
  treaty,
  initial,
  saving,
  error,
  onSave,
  onCancel,
}: {
  fields: RelationFieldOption[];
  treaty: TreatyFactorOption[];
  initial?: RelationFormValue;
  saving: boolean;
  error: string | null;
  onSave: (value: RelationFormValue) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(initial?.label ?? '');
  const [target, setTarget] = useState(initial?.target_field ?? '');
  const [terms, setTerms] = useState<MoneyRelationTerm[]>(
    initial?.terms.length ? initial.terms : [{ field: '', sign: 1, factors: [] }],
  );
  const [customFactor, setCustomFactor] = useState<Record<number, string>>({});
  const labelOf = labelResolver(fields);

  function patch(i: number, change: Partial<MoneyRelationTerm>) {
    setTerms((t) => t.map((term, idx) => (idx === i ? { ...term, ...change } : term)));
  }
  function addFactor(i: number, factor: string) {
    const clean = factor.trim();
    if (!clean || terms[i].factors.includes(clean)) return;
    patch(i, { factors: [...terms[i].factors, clean] });
  }

  const complete = !!target && terms.length > 0 && terms.every((t) => !!t.field);
  const selfReference = terms.some((t) => t.field === target && t.factors.length === 0);
  const customOk = (v: string) => /^-?\d+(\.\d+)?$/.test(v.trim());

  return (
    <form
      className="space-y-3 rounded border border-slate-300 bg-white p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (complete && !selfReference) onSave({ label: label.trim(), target_field: target, terms });
      }}
    >
      <p className="text-sm font-medium text-slate-800">{initial ? 'Edit relation' : 'New relation'}</p>

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="rel-target" className="text-sm text-slate-700">
          This column
        </label>
        <FieldSelect id="rel-target" value={target} onChange={setTarget} fields={fields} placeholder="Choose the column to check…" />
        <span className="text-sm text-slate-700">should equal</span>
      </div>

      <ul className="space-y-2">
        {terms.map((term, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 rounded bg-slate-50 p-2">
            <label className="sr-only" htmlFor={`rel-sign-${i}`}>
              Add or subtract
            </label>
            <select
              id={`rel-sign-${i}`}
              value={term.sign}
              onChange={(e) => patch(i, { sign: Number(e.target.value) as 1 | -1 })}
              className={INPUT}
              aria-label={i === 0 ? 'Sign of the first term' : 'Add or subtract'}
            >
              <option value={1}>{i === 0 ? '' : '+'}</option>
              <option value={-1}>−</option>
            </select>
            <label className="sr-only" htmlFor={`rel-field-${i}`}>
              Column
            </label>
            <FieldSelect id={`rel-field-${i}`} value={term.field} onChange={(v) => patch(i, { field: v })} fields={fields} placeholder="Choose a column…" />

            {term.factors.map((f) => (
              <span key={f} className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-800">
                × {factorText(f, treaty)}
                <button
                  type="button"
                  aria-label={`Remove factor ${f}`}
                  onClick={() => patch(i, { factors: term.factors.filter((x) => x !== f) })}
                  className="text-slate-500 hover:text-slate-900"
                >
                  ×
                </button>
              </span>
            ))}
            <select
              aria-label="Multiply by a treaty figure"
              value=""
              onChange={(e) => addFactor(i, e.target.value)}
              className={`${INPUT} text-slate-600`}
            >
              <option value="">× treaty figure…</option>
              {treaty.map((t) => (
                <option key={t.name} value={t.name}>
                  {factorText(t.name, treaty)}
                  {t.value == null && t.name !== 'fx_rate' ? ' - not entered' : ''}
                </option>
              ))}
            </select>
            <input
              aria-label="Multiply by a number"
              placeholder="× number"
              value={customFactor[i] ?? ''}
              onChange={(e) => setCustomFactor((c) => ({ ...c, [i]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (customOk(customFactor[i] ?? '')) {
                    addFactor(i, customFactor[i]);
                    setCustomFactor((c) => ({ ...c, [i]: '' }));
                  }
                }
              }}
              className={`${INPUT} w-24`}
            />
            {terms.length > 1 && (
              <button
                type="button"
                onClick={() => setTerms((t) => t.filter((_, idx) => idx !== i))}
                className="ml-auto text-xs text-red-700 underline"
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={() => setTerms((t) => [...t, { field: '', sign: -1, factors: [] }])}
        disabled={terms.length >= 8}
        className="text-sm font-medium text-slate-700 underline disabled:opacity-50"
      >
        + Add another column
      </button>

      {complete && (
        <p className="rounded bg-slate-100 p-2 font-mono text-xs text-slate-800" aria-label="Relation preview">
          {relationText(target, terms, labelOf, treaty)}
        </p>
      )}
      {selfReference && <p className="text-xs text-red-700">A column cannot be defined by itself.</p>}

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="rel-label" className="text-sm text-slate-700">
          Name (optional)
        </label>
        <input id="rel-label" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={255} className={`${INPUT} w-72`} />
      </div>

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!complete || selfReference || saving}
          className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save relation'}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className="text-sm text-slate-600 underline">
          Cancel
        </button>
      </div>
    </form>
  );
}
