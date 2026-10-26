import { useRef, useState } from 'react';
import type { PreviewColumn } from '../../api/reconTypes';
import { expressionHint, insertAtCursor } from '../../utils/recon';
import type { RuleDraft } from '../../utils/recon';
import { TypeBadge, btnSecondary, inputCls } from './ui';

const OPERATORS = ['+', '-', '*', '/', '(', ')', '='];
const AGGS = ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX'];

export function newRuleDraft(n: number): RuleDraft {
  return { key: `rule-${Date.now()}-${n}`, name: '', expression: '', bordereaux_agg: 'SUM', subledger_agg: 'SUM' };
}

function Palette({
  side,
  datasetName,
  columns,
  onPick,
}: {
  side: 'bordereaux' | 'subledger';
  datasetName: string;
  columns: PreviewColumn[];
  onPick: (token: string) => void;
}) {
  const [q, setQ] = useState('');
  const shown = columns.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="rounded border border-slate-200 bg-white p-2">
      <h4 className="text-xs font-semibold uppercase text-slate-600">
        {side} columns <span className="font-normal normal-case text-slate-400">({datasetName || 'no dataset'})</span>
      </h4>
      <input
        aria-label={`Filter ${side} columns`}
        placeholder="Filter columns..."
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className={`${inputCls} mt-1 w-full`}
      />
      <ul className="mt-1 max-h-48 space-y-0.5 overflow-y-auto">
        {shown.length === 0 && <li className="text-xs text-slate-500">No columns.</li>}
        {shown.map((c) => (
          <li key={c.name}>
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onPick(`${side}.${c.name}`)}
              aria-label={`Insert ${side}.${c.name}`}
              className="flex w-full items-center justify-between gap-2 rounded px-1.5 py-0.5 text-left text-xs hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500"
            >
              <span className={`font-mono ${c.derived ? 'text-indigo-700' : ''}`}>{c.name}</span>
              <TypeBadge type={c.type} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Rule expression editors plus the two column palettes. Clicking a column or
 * operator inserts it at the caret of the last focused expression field.
 */
export function RulesEditor({
  rules,
  onChange,
  bordereauxColumns,
  subledgerColumns,
  bordereauxName = '',
  subledgerName = '',
  disabled,
}: {
  rules: RuleDraft[];
  onChange: (rules: RuleDraft[]) => void;
  bordereauxColumns: PreviewColumn[];
  subledgerColumns: PreviewColumn[];
  bordereauxName?: string;
  subledgerName?: string;
  disabled?: boolean;
}) {
  const refs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const [focused, setFocused] = useState<string | null>(null);

  function update(key: string, patch: Partial<RuleDraft>) {
    onChange(rules.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function insert(token: string) {
    const target = rules.find((r) => r.key === focused) ?? rules[0];
    if (!target) return;
    const el = refs.current[target.key];
    const res = insertAtCursor(target.expression, el?.selectionStart ?? null, el?.selectionEnd ?? null, token);
    update(target.key, { expression: res.text });
    setFocused(target.key);
    setTimeout(() => {
      const e = refs.current[target.key];
      if (e) {
        e.focus();
        e.setSelectionRange(res.cursor, res.cursor);
      }
    }, 0);
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <Palette side="bordereaux" datasetName={bordereauxName} columns={bordereauxColumns} onPick={insert} />
        <Palette side="subledger" datasetName={subledgerName} columns={subledgerColumns} onPick={insert} />
      </div>

      <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Operators">
        <span className="mr-1 text-xs text-slate-500">Operators:</span>
        {OPERATORS.map((op) => (
          <button
            key={op}
            type="button"
            disabled={disabled}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => insert(op)}
            aria-label={`Insert operator ${op}`}
            className={`${btnSecondary} w-9 px-0 font-mono`}
          >
            {op}
          </button>
        ))}
      </div>

      <ul className="space-y-3">
        {rules.map((r, i) => {
          const hint = expressionHint(r.expression);
          return (
            <li key={r.key} className="rounded border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-48 flex-1">
                  <label htmlFor={`${r.key}-name`} className="block text-xs font-medium text-slate-600">Rule name</label>
                  <input
                    id={`${r.key}-name`}
                    value={r.name}
                    disabled={disabled}
                    placeholder={`Rule ${i + 1}`}
                    onChange={(e) => update(r.key, { name: e.target.value })}
                    className={`${inputCls} mt-1 w-full`}
                  />
                </div>
                {(['bordereaux', 'subledger'] as const).map((side) => {
                  const field = side === 'bordereaux' ? 'bordereaux_agg' : 'subledger_agg';
                  return (
                    <div key={side}>
                      <label htmlFor={`${r.key}-${field}`} className="block text-xs font-medium text-slate-600">
                        {side === 'bordereaux' ? 'Bordereaux' : 'Subledger'} aggregation
                      </label>
                      <select
                        id={`${r.key}-${field}`}
                        value={r[field]}
                        disabled={disabled}
                        onChange={(e) => update(r.key, { [field]: e.target.value } as Partial<RuleDraft>)}
                        className={`${inputCls} mt-1`}
                      >
                        {AGGS.map((a) => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </div>
                  );
                })}
                {rules.length > 1 && (
                  <button type="button" className={btnSecondary} disabled={disabled} onClick={() => onChange(rules.filter((x) => x.key !== r.key))}>
                    Remove rule
                  </button>
                )}
              </div>
              <label htmlFor={`${r.key}-expr`} className="mt-2 block text-xs font-medium text-slate-600">Expression</label>
              <textarea
                id={`${r.key}-expr`}
                ref={(el) => { refs.current[r.key] = el; }}
                rows={2}
                value={r.expression}
                disabled={disabled}
                onFocus={() => setFocused(r.key)}
                onChange={(e) => update(r.key, { expression: e.target.value })}
                placeholder="bordereaux.column_a + bordereaux.column_b = subledger.column_xy"
                className={`${inputCls} mt-1 w-full font-mono`}
                aria-describedby={`${r.key}-hint`}
              />
              <p id={`${r.key}-hint`} className={`mt-1 text-xs ${hint?.level === 'warn' ? 'text-amber-700' : 'text-slate-500'}`}>
                {hint ? hint.message : 'Compare a bordereaux expression with a subledger expression, e.g. totals of gross premium.'}
              </p>
            </li>
          );
        })}
      </ul>
      <button type="button" className={btnSecondary} disabled={disabled} onClick={() => onChange([...rules, newRuleDraft(rules.length + 1)])}>
        Add rule
      </button>
    </div>
  );
}
