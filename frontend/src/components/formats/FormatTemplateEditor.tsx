import { useRef, useState } from 'react';
import { api } from '../../api/endpoints';
import { describeError } from '../../api/errors';
import type { FormatTemplate, FormatTemplateColumn } from '../../api/types';

type Row = { key: number; name: string; terms: string };

/** Case-, spacing- and punctuation-insensitive key, mirroring how the server compares column names. */
export function looseKey(name: string): string {
  return name.toLowerCase().replace(/[\W_]+/g, '');
}

/** One term per line -> the distinct, non-empty terms. */
export function splitTerms(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const term = line.trim().replace(/\s+/g, ' ');
    const key = looseKey(term);
    if (term && key && !seen.has(key)) {
      seen.add(key);
      out.push(term);
    }
  }
  return out;
}

/**
 * Checks a format before it is sent. Blank rows are ignored; a row with terms but no name,
 * no columns at all, a missing format name and duplicate column names are errors.
 */
export function validateFormat(
  name: string,
  rows: { name: string; terms: string }[],
): { errors: string[]; columns: FormatTemplateColumn[] } {
  const errors: string[] = [];
  if (!name.trim()) errors.push('Give the format a name.');
  const active = rows.filter((r) => r.name.trim() || r.terms.trim());
  if (active.some((r) => !r.name.trim())) errors.push('Every column needs a name.');
  const named = active.filter((r) => r.name.trim());
  if (named.length === 0) errors.push('Add at least one column.');
  const seen = new Map<string, string>();
  const duplicates: string[] = [];
  for (const r of named) {
    const key = looseKey(r.name);
    if (!key) errors.push(`“${r.name.trim()}” is not a usable column name.`);
    else if (seen.has(key)) duplicates.push(r.name.trim());
    else seen.set(key, r.name.trim());
  }
  if (duplicates.length > 0) errors.push(`Column names must be unique: ${[...new Set(duplicates)].join(', ')}.`);
  return { errors, columns: named.map((r) => ({ name: r.name.trim().replace(/\s+/g, ' '), terms: splitTerms(r.terms) })) };
}

/**
 * Create or change a saved final format: its name, its columns (add, remove, rename)
 * and the recognised terms of each column - typed, or read from a CSV/Excel file whose
 * headers are the columns and whose cells below are their terms.
 */
export function FormatTemplateEditor({
  initial,
  busy,
  error,
  onSave,
  onCancel,
}: {
  initial?: FormatTemplate | null;
  busy: boolean;
  error?: unknown;
  onSave: (body: { name: string; columns: FormatTemplateColumn[] }) => void;
  onCancel: () => void;
}) {
  const counter = useRef(0);
  const nextKey = () => ++counter.current;
  const [name, setName] = useState(initial?.name ?? '');
  const [rows, setRows] = useState<Row[]>(() =>
    initial && initial.columns.length > 0
      ? initial.columns.map((c) => ({ key: nextKey(), name: c.name, terms: c.terms.join('\n') }))
      : [{ key: nextKey(), name: '', terms: '' }],
  );
  const [touched, setTouched] = useState(false);
  const [reading, setReading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileNote, setFileNote] = useState<string | null>(null);

  const { errors, columns } = validateFormat(name, rows);
  const editing = !!initial;

  function update(key: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  async function onFile(file: File | undefined) {
    if (!file) return;
    setFileError(null);
    setFileNote(null);
    setReading(true);
    try {
      const parsed = await api.formats.parseFile(file);
      if (parsed.columns.length === 0) {
        setFileError('No column headers were found in that file.');
        return;
      }
      setRows(parsed.columns.map((c) => ({ key: nextKey(), name: c, terms: (parsed.terms[c] ?? []).join('\n') })));
      const terms = Object.values(parsed.terms).reduce((n, t) => n + t.length, 0);
      setFileNote(
        `Loaded ${parsed.columns.length} column(s) and ${terms} recognised term(s) from the file` +
          (parsed.skipped_terms > 0 ? `; ${parsed.skipped_terms} term(s) under an empty header were ignored.` : '.'),
      );
    } catch (err) {
      setFileError(describeError(err));
    } finally {
      setReading(false);
    }
  }

  return (
    <form
      aria-label={editing ? `Edit format ${initial?.name}` : 'New format'}
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (errors.length === 0 && !busy) onSave({ name: name.trim().replace(/\s+/g, ' '), columns });
      }}
      className="space-y-4 rounded border border-slate-300 bg-white p-4"
    >
      <h3 className="text-base font-semibold text-slate-900">{editing ? 'Change format' : 'New format'}</h3>

      <div>
        <label htmlFor="format-name" className="block text-sm font-medium text-slate-800">
          Format name <span className="text-red-600">*</span>
        </label>
        <input
          id="format-name"
          value={name}
          maxLength={100}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 w-full max-w-md rounded border border-slate-300 px-2 py-1.5"
        />
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-slate-800">Final columns and the terms that identify them</p>
          <label className="cursor-pointer rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100">
            {reading ? 'Reading file...' : 'Load from CSV/Excel'}
            <input
              type="file"
              accept=".csv,.tsv,.xlsx,.xlsm"
              className="sr-only"
              aria-label="Load columns and recognised terms from a file"
              disabled={reading}
              onChange={(e) => {
                void onFile(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
          </label>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          A file&apos;s first row lists the columns and the cells below each one are its recognised terms; loading one
          replaces the columns below. A source column named like any recognised term is mapped to that column at 100%.
        </p>
        {fileError && (
          <p role="alert" className="mt-1 text-sm text-red-700">
            {fileError}
          </p>
        )}
        {fileNote && (
          <p role="status" className="mt-1 text-sm text-green-800">
            {fileNote}
          </p>
        )}

        <ul className="mt-3 space-y-2">
          {rows.map((r, i) => {
            const label = r.name.trim() || `column ${i + 1}`;
            return (
              <li key={r.key} className="grid gap-2 sm:grid-cols-[14rem_1fr_auto] sm:items-start">
                <input
                  aria-label={`Column name ${i + 1}`}
                  value={r.name}
                  placeholder="Column name"
                  onChange={(e) => update(r.key, { name: e.target.value })}
                  className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                />
                <textarea
                  aria-label={`Recognised terms for ${label}`}
                  value={r.terms}
                  rows={2}
                  placeholder={'Recognised terms, one per line'}
                  onChange={(e) => update(r.key, { terms: e.target.value })}
                  className="rounded border border-slate-300 px-2 py-1 font-mono text-xs"
                />
                <button
                  type="button"
                  aria-label={`Remove column ${label}`}
                  onClick={() => setRows((prev) => (prev.length > 1 ? prev.filter((x) => x.key !== r.key) : [{ ...r, name: '', terms: '' }]))}
                  className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Remove
                </button>
              </li>
            );
          })}
        </ul>
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, { key: nextKey(), name: '', terms: '' }])}
          className="mt-2 rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
        >
          Add column
        </button>
      </div>

      {touched && errors.length > 0 && (
        <ul role="alert" className="list-disc space-y-0.5 pl-5 text-sm text-red-700">
          {errors.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {error ? (
        <p role="alert" className="text-sm text-red-700">
          {describeError(error)}
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? 'Saving...' : editing ? 'Save changes' : 'Save format'}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className="text-sm text-slate-600 underline hover:text-slate-900">
          Cancel
        </button>
        <span className="text-xs text-slate-500">
          {columns.length} column(s), {columns.reduce((n, c) => n + c.terms.length, 0)} term(s)
        </span>
      </div>
    </form>
  );
}
