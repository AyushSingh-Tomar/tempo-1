import { useState } from 'react';
import type { SchemaPreview } from '../../api/reconTypes';
import { addAlias, removeAlias } from '../../utils/recon';
import type { Aliases } from '../../utils/recon';
import { TypeBadge, btnSecondary, inputCls } from './ui';

function ChipList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-xs text-slate-500">{empty}</p>;
  return (
    <ul className="flex flex-wrap gap-1">
      {items.map((c) => (
        <li key={c} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">{c}</li>
      ))}
    </ul>
  );
}

export function SchemaStep({
  preview,
  aliases,
  onAliasesChange,
  canEdit,
}: {
  preview: SchemaPreview;
  aliases: Aliases;
  onAliasesChange: (next: Aliases) => void;
  canEdit: boolean;
}) {
  const s = preview.summary;
  const tableName = (id: string) => {
    const t = s.tables.find((x) => x.id === id);
    return t ? `${t.file}${t.sheet ? ` / ${t.sheet}` : ''}` : id;
  };
  const [from, setFrom] = useState('');
  const [into, setInto] = useState('');
  const shownMerges = s.suggested_merges.filter((m) => aliases[m.columns[0]] !== m.columns[1] && aliases[m.columns[1]] !== m.columns[0]);

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        {preview.total_rows.toLocaleString()} rows across {s.tables.length} table(s).
      </p>

      <div className="grid gap-3 md:grid-cols-3">
        <div>
          <h4 className="text-xs font-semibold uppercase text-slate-500">Common to all files</h4>
          <ChipList items={s.common_columns} empty="No column appears in every file." />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase text-slate-500">In some files</h4>
          <ChipList items={s.partial_columns} empty="None." />
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase text-slate-500">Only in one file</h4>
          {s.unique_columns.length === 0 ? (
            <p className="text-xs text-slate-500">None.</p>
          ) : (
            <ul className="space-y-0.5 text-xs">
              {s.unique_columns.map((u) => (
                <li key={u.column}>
                  <span className="font-mono">{u.column}</span> <span className="text-slate-500">({tableName(u.table)})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {s.type_conflicts.length > 0 && (
        <div role="alert" className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Type conflicts</p>
          <ul className="mt-1 list-disc pl-5 text-xs">
            {s.type_conflicts.map((c) => (
              <li key={c.column}>
                <span className="font-mono">{c.column}</span>:{' '}
                {Object.entries(c.types).map(([t, ty]) => `${tableName(t)} = ${ty}`).join('; ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h4 className="text-sm font-semibold text-slate-900">Columns that may be the same</h4>
        {shownMerges.length === 0 && <p className="text-xs text-slate-500">No further suggestions.</p>}
        <ul className="mt-1 space-y-1">
          {shownMerges.map((m) => (
            <li key={m.columns.join('|')} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono">{m.columns[0]}</span> and <span className="font-mono">{m.columns[1]}</span>
              <span className="text-xs text-slate-500">({Math.round(m.score * 100)}% similar)</span>
              <button
                type="button"
                className={btnSecondary}
                disabled={!canEdit}
                onClick={() => onAliasesChange(addAlias(aliases, m.columns[1], m.columns[0]))}
              >
                Treat as the same column
              </button>
            </li>
          ))}
        </ul>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="merge-from" className="block text-xs font-medium text-slate-600">Merge column</label>
            <select id="merge-from" value={from} onChange={(e) => setFrom(e.target.value)} className={`${inputCls} mt-1`} disabled={!canEdit}>
              <option value="">Select...</option>
              {s.all_columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="merge-into" className="block text-xs font-medium text-slate-600">into column</label>
            <select id="merge-into" value={into} onChange={(e) => setInto(e.target.value)} className={`${inputCls} mt-1`} disabled={!canEdit}>
              <option value="">Select...</option>
              {s.all_columns.filter((c) => c !== from).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button
            type="button"
            className={btnSecondary}
            disabled={!canEdit || !from || !into}
            onClick={() => {
              onAliasesChange(addAlias(aliases, from, into));
              setFrom('');
              setInto('');
            }}
          >
            Merge columns
          </button>
        </div>

        {Object.keys(aliases).length > 0 && (
          <ul className="mt-3 space-y-1" aria-label="Confirmed merges">
            {Object.entries(aliases).map(([a, b]) => (
              <li key={a} className="flex items-center gap-2 text-sm">
                <span className="font-mono">{a}</span> merged into <span className="font-mono">{b}</span>
                <button type="button" className="text-xs text-slate-500 underline" disabled={!canEdit} onClick={() => onAliasesChange(removeAlias(aliases, a))}>
                  Undo
                </button>
              </li>
            ))}
          </ul>
        )}
        {Object.keys(aliases).length > 0 && (
          <p className="mt-1 text-xs text-slate-500">Click "Analyse files" again to refresh the summary with these merges applied.</p>
        )}
      </div>

      {s.tables.map((t) => (
        <details key={t.id} className="rounded border border-slate-200">
          <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
            {t.file}{t.sheet ? ` / ${t.sheet}` : ''} - {t.row_count.toLocaleString()} rows, {t.columns.length} columns
          </summary>
          <div className="overflow-x-auto px-3 pb-3">
            <table className="min-w-full text-xs">
              <caption className="sr-only">Columns of {t.file}</caption>
              <thead>
                <tr className="text-left text-slate-500">
                  <th scope="col" className="pr-3">Original</th>
                  <th scope="col" className="pr-3">Standard name</th>
                  <th scope="col" className="pr-3">Type</th>
                  <th scope="col" className="pr-3">Filled</th>
                </tr>
              </thead>
              <tbody>
                {t.columns.map((c) => (
                  <tr key={c.original} className="border-t border-slate-100">
                    <td className="pr-3">{c.original}</td>
                    <td className="pr-3 font-mono">{c.standard}</td>
                    <td className="pr-3"><TypeBadge type={c.type} /></td>
                    <td className="pr-3">{c.filled}/{c.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(preview.samples[t.id] ?? []).length > 0 && (
              <div className="mt-3 overflow-x-auto">
                <p className="text-xs font-medium text-slate-600">Sample rows</p>
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500">
                      {t.columns.map((c) => <th key={c.original} scope="col" className="pr-3">{c.original}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.samples[t.id].map((r, i) => (
                      <tr key={i} className="border-t border-slate-100">
                        {t.columns.map((c) => <td key={c.original} className="pr-3 whitespace-nowrap">{String(r[c.original] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
