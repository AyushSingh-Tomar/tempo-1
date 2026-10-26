import { useEffect, useState } from 'react';
import type { FilterOp, FilterSide, ReconFilter } from '../../api/reconTypes';
import { useColumnValues } from '../../hooks/useRecon';
import { sidesForColumn } from '../../utils/recon';
import { btnSecondary, inputCls } from './ui';

const OPS: Array<{ value: FilterOp; label: string; max: number | null }> = [
  { value: 'in', label: 'is one of', max: null },
  { value: 'not_in', label: 'is not one of', max: null },
  { value: 'eq', label: 'equals', max: 1 },
  { value: 'neq', label: 'does not equal', max: 1 },
  { value: 'contains', label: 'contains', max: 1 },
  { value: 'between', label: 'is between', max: 2 },
  { value: 'gte', label: 'is at least', max: 1 },
  { value: 'lte', label: 'is at most', max: 1 },
  { value: 'is_blank', label: 'is blank', max: 0 },
  { value: 'not_blank', label: 'is not blank', max: 0 },
];

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Chips + typeahead populated from /columns/{col}/values. */
export function ValueInput({
  datasetId,
  column,
  values,
  onChange,
  max,
  label,
}: {
  datasetId: string | undefined;
  column: string;
  values: string[];
  onChange: (v: string[]) => void;
  max: number | null;
  label: string;
}) {
  const [text, setText] = useState('');
  const q = useDebounced(text);
  const { data } = useColumnValues(datasetId, column || undefined, q);
  const listId = `vals-${label.replace(/\W+/g, '-')}`;
  function add(v: string) {
    const val = v.trim();
    if (!val || values.includes(val)) return;
    const next = max === 1 ? [val] : [...values, val];
    onChange(max && next.length > max ? next.slice(-max) : next);
    setText('');
  }
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1">
        {values.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs">
            {v}
            <button type="button" aria-label={`Remove value ${v}`} onClick={() => onChange(values.filter((x) => x !== v))}>
              x
            </button>
          </span>
        ))}
        <input
          aria-label={label}
          list={listId}
          value={text}
          placeholder="Type or pick a value"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              add(text);
            }
          }}
          onBlur={() => text && add(text)}
          className={`${inputCls} w-44`}
        />
        <datalist id={listId}>
          {(data?.values ?? []).map((v) => (
            <option key={String(v.value)} value={String(v.value)}>
              {v.rows} rows
            </option>
          ))}
        </datalist>
      </div>
    </div>
  );
}

export function FilterEditor({
  filters,
  onChange,
  bordereauxId,
  subledgerId,
  bordereauxColumns,
  subledgerColumns,
  disabled,
}: {
  filters: ReconFilter[];
  onChange: (f: ReconFilter[]) => void;
  bordereauxId: string | undefined;
  subledgerId: string | undefined;
  bordereauxColumns: string[];
  subledgerColumns: string[];
  disabled?: boolean;
}) {
  const all = Array.from(new Set([...bordereauxColumns, ...subledgerColumns])).sort();
  const [column, setColumn] = useState('');
  const sides = column ? sidesForColumn(column, bordereauxColumns, subledgerColumns) : [];
  const [side, setSide] = useState<FilterSide>('both');
  const [op, setOp] = useState<FilterOp>('in');
  const [values, setValues] = useState<string[]>([]);
  const opDef = OPS.find((o) => o.value === op) ?? OPS[0];
  const effSide = sides.includes(side) ? side : sides[0];
  const valueDataset = effSide === 'subledger' ? subledgerId : bordereauxId;
  const valid = !!column && !!effSide && (opDef.max === 0 || values.length > 0) && (op !== 'between' || values.length === 2);

  function add() {
    if (!valid || !effSide) return;
    onChange([...filters, { side: effSide, column, op, values: opDef.max === 0 ? [] : values }]);
    setColumn('');
    setValues([]);
  }

  return (
    <div className="space-y-3">
      {filters.length > 0 && (
        <ul className="space-y-1" aria-label="Custom filters">
          {filters.map((f, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{f.side}</span>
              <span className="font-mono">{f.column}</span> {OPS.find((o) => o.value === f.op)?.label ?? f.op} {f.values.join(', ')}
              <button type="button" className="text-xs text-slate-500 underline" disabled={disabled} onClick={() => onChange(filters.filter((_, j) => j !== i))}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <fieldset className="flex flex-wrap items-end gap-3 rounded border border-slate-200 p-3">
        <legend className="px-1 text-xs font-medium text-slate-600">Add filter on any column</legend>
        <div>
          <label htmlFor="flt-col" className="block text-xs font-medium text-slate-600">Column</label>
          <select id="flt-col" value={column} disabled={disabled} onChange={(e) => { setColumn(e.target.value); setValues([]); }} className={`${inputCls} mt-1`}>
            <option value="">Select...</option>
            {all.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="flt-side" className="block text-xs font-medium text-slate-600">Applies to</label>
          <select id="flt-side" value={effSide ?? ''} disabled={disabled || sides.length < 2} onChange={(e) => setSide(e.target.value as FilterSide)} className={`${inputCls} mt-1`}>
            {sides.length === 0 && <option value="">-</option>}
            {sides.map((s) => <option key={s} value={s}>{s === 'both' ? 'both datasets' : s}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="flt-op" className="block text-xs font-medium text-slate-600">Condition</label>
          <select id="flt-op" value={op} disabled={disabled} onChange={(e) => { setOp(e.target.value as FilterOp); setValues([]); }} className={`${inputCls} mt-1`}>
            {OPS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {opDef.max !== 0 && column && (
          <div>
            <span className="block text-xs font-medium text-slate-600">{op === 'between' ? 'Two values (from, to)' : 'Value'}</span>
            <ValueInput datasetId={valueDataset} column={column} values={values} onChange={setValues} max={opDef.max} label={`Filter value for ${column}`} />
          </div>
        )}
        <button type="button" className={btnSecondary} disabled={disabled || !valid} onClick={add}>Add filter</button>
      </fieldset>
      <p className="text-xs text-slate-500">
        "Both datasets" is only offered for columns that exist in both (for example _year, _quarter, _period); otherwise add one filter per side.
      </p>
    </div>
  );
}
