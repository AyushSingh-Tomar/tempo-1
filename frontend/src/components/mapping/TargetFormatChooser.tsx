import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import { describeError } from '../../api/errors';
import { useFormatTemplates } from '../../hooks/useFormatTemplates';

/** Splits pasted text (newlines, commas, tabs, semicolons) into unique column names. */
function parseColumnText(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of text.split(/[\r\n,;\t]+/)) {
    const name = part.trim();
    const key = name.toLowerCase();
    if (name && !seen.has(key)) {
      seen.add(key);
      out.push(name);
    }
  }
  return out;
}

export type TargetFormatChoice =
  | { mode: 'DEFAULT' }
  | { mode: 'CUSTOM'; columns: string[]; terms?: Record<string, string[]> }
  /** A saved format from the platform directory (the server loads its columns and terms). */
  | { mode: 'CUSTOM'; template_id: string };

/** One recognised term per line -> the non-empty terms for each column that is still in the list. */
export function termsPayload(columns: string[], termText: Record<string, string>): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const column of columns) {
    const lines = (termText[column] ?? '')
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length > 0) out[column] = lines;
  }
  return out;
}

/**
 * Asks the user what the source columns should be mapped *to* before any
 * mapping is proposed: the built-in data dictionary (with its built-in
 * recognised terms), or their own final column list (typed, pasted, or read
 * from a CSV/XLSX header row) together with, optionally, the terms they
 * recognise each column by.
 */
export function TargetFormatChooser({
  runId,
  busy,
  onConfirm,
  onCancel,
  aiOption,
}: {
  runId: string;
  busy: boolean;
  onConfirm: (choice: TargetFormatChoice) => void;
  onCancel?: () => void;
  /** The "use AI for ambiguous columns" control, rendered just above the submit button. */
  aiOption?: ReactNode;
}) {
  const [mode, setMode] = useState<'DEFAULT' | 'SAVED' | 'CUSTOM'>('DEFAULT');
  const [savedId, setSavedId] = useState('');
  const [text, setText] = useState('');
  const [termText, setTermText] = useState<Record<string, string>>({});
  const [fileError, setFileError] = useState<string | null>(null);
  const [fileNote, setFileNote] = useState<string | null>(null);
  const [reading, setReading] = useState(false);

  const format = useQuery({
    queryKey: ['target-format', runId],
    queryFn: () => api.mappings.targetFormat.get(runId),
  });

  const customColumns = parseColumnText(text);
  const saved = useFormatTemplates();
  const savedFormats = saved.data ?? [];
  const selectedSaved = savedFormats.find((t) => t.id === savedId);
  const canSubmit =
    !busy &&
    (mode === 'DEFAULT' || (mode === 'SAVED' && !!selectedSaved) || (mode === 'CUSTOM' && customColumns.length > 0));
  const defaultFields = format.data?.mode === 'DEFAULT' ? format.data.fields : [];

  async function onFile(file: File | undefined) {
    if (!file) return;
    setFileError(null);
    setFileNote(null);
    setReading(true);
    try {
      const cols = await api.mappings.targetFormat.parseFile(runId, file);
      if (cols.length === 0) setFileError('No column names were found in that file.');
      else setText(cols.join('\n'));
    } catch (err) {
      setFileError(describeError(err));
    } finally {
      setReading(false);
    }
  }

  async function onTermsFile(file: File | undefined) {
    if (!file) return;
    setFileError(null);
    setFileNote(null);
    setReading(true);
    try {
      const parsed = await api.mappings.targetFormat.parseTermsFile(runId, file);
      if (parsed.columns.length === 0) {
        setFileError('No column headers were found in that file.');
        return;
      }
      setText(parsed.columns.join('\n'));
      setTermText(Object.fromEntries(Object.entries(parsed.terms).map(([col, terms]) => [col, terms.join('\n')])));
      const count = Object.values(parsed.terms).reduce((n, t) => n + t.length, 0);
      setFileNote(
        `Read ${parsed.columns.length} column(s) and ${count} recognised term(s)` +
          (parsed.skipped_terms > 0 ? `; ${parsed.skipped_terms} term(s) under an empty header were ignored.` : '.'),
      );
    } catch (err) {
      setFileError(describeError(err));
    } finally {
      setReading(false);
    }
  }

  function confirm() {
    if (mode === 'DEFAULT') return onConfirm({ mode: 'DEFAULT' });
    if (mode === 'SAVED') return selectedSaved ? onConfirm({ mode: 'CUSTOM', template_id: selectedSaved.id }) : undefined;
    const terms = termsPayload(customColumns, termText);
    onConfirm({ mode: 'CUSTOM', columns: customColumns, ...(Object.keys(terms).length > 0 ? { terms } : {}) });
  }

  return (
    <section className="space-y-4 rounded-md border border-slate-200 bg-white p-4" aria-labelledby="target-format-heading">
      <div>
        <h2 id="target-format-heading" className="text-base font-semibold text-slate-900">
          Which columns do you want in the final file?
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Source columns are mapped to this target format. A source column whose name is a recognised term for a
          target column maps to it at 100% confidence.
        </p>
      </div>

      <fieldset className="space-y-3">
        <legend className="sr-only">Target format</legend>
        <label className="flex items-start gap-2 text-sm">
          <input type="radio" name="target-format" checked={mode === 'DEFAULT'} onChange={() => setMode('DEFAULT')} className="mt-1" />
          <span>
            <span className="font-medium text-slate-900">Use the default data dictionary</span>
            <span className="block text-slate-600">
              The standard P&amp;C premium bordereaux format
              {defaultFields.length > 0 ? ` (${defaultFields.length} columns)` : ''}.
            </span>
          </span>
        </label>
        {mode === 'DEFAULT' && defaultFields.length > 0 && (
          <details className="ml-6 text-xs text-slate-600">
            <summary className="cursor-pointer font-medium">Show default columns</summary>
            <p className="mt-1 text-slate-500">
              Each column is recognised by its built-in terms (hover a column to see them).
            </p>
            <ul className="mt-2 grid max-h-48 grid-cols-2 gap-x-4 gap-y-0.5 overflow-y-auto sm:grid-cols-3">
              {defaultFields.map((f) => (
                <li key={f.name} className="truncate" title={f.recognised_terms?.length ? f.recognised_terms.join(', ') : f.name}>
                  {f.display_name}
                  {f.required === 'mandatory' && <span className="text-red-600"> *</span>}
                </li>
              ))}
            </ul>
          </details>
        )}

        <label className="flex items-start gap-2 text-sm">
          <input type="radio" name="target-format" checked={mode === 'SAVED'} onChange={() => setMode('SAVED')} className="mt-1" />
          <span>
            <span className="font-medium text-slate-900">Use a saved format</span>
            <span className="block text-slate-600">
              Pick one of the final formats already saved on the platform, with its recognised terms.
            </span>
          </span>
        </label>
        {mode === 'SAVED' && (
          <div className="ml-6 space-y-2">
            {saved.isLoading && <p className="text-sm text-slate-500">Loading saved formats...</p>}
            {saved.isError && (
              <p role="alert" className="text-sm text-red-700">
                {describeError(saved.error)}
              </p>
            )}
            {!saved.isLoading && !saved.isError && savedFormats.length === 0 && (
              <p className="text-sm text-slate-600">
                No saved formats yet.{' '}
                <a href="/#formats" target="_blank" rel="noreferrer" className="font-medium underline hover:text-slate-900">
                  Add one in the formats directory
                </a>
                , or use one of the other options.
              </p>
            )}
            {savedFormats.length > 0 && (
              <>
                <label htmlFor="saved-format" className="sr-only">
                  Saved format
                </label>
                <select
                  id="saved-format"
                  value={savedId}
                  onChange={(e) => setSavedId(e.target.value)}
                  className="w-full max-w-md rounded border border-slate-300 px-2 py-1.5 text-sm"
                >
                  <option value="">Select a saved format…</option>
                  {savedFormats.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.column_count} columns)
                    </option>
                  ))}
                </select>
                {selectedSaved && (
                  <details open className="text-xs text-slate-600">
                    <summary className="cursor-pointer font-medium">
                      {selectedSaved.column_count} column(s), {selectedSaved.term_count} recognised term(s)
                    </summary>
                    <ul aria-label="Columns in the selected format" className="mt-1 max-h-48 space-y-0.5 overflow-y-auto">
                      {selectedSaved.columns.map((c) => (
                        <li key={c.name}>
                          <span className="font-medium text-slate-800">{c.name}</span>
                          {c.terms.length > 0 && <span className="text-slate-500"> — {c.terms.join(', ')}</span>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <p className="text-xs text-slate-500">
                  The format is copied into this run, so changing it later does not affect this run.{' '}
                  <a href="/#formats" target="_blank" rel="noreferrer" className="underline hover:text-slate-900">
                    Manage saved formats
                  </a>
                </p>
              </>
            )}
          </div>
        )}

        <label className="flex items-start gap-2 text-sm">
          <input type="radio" name="target-format" checked={mode === 'CUSTOM'} onChange={() => setMode('CUSTOM')} className="mt-1" />
          <span>
            <span className="font-medium text-slate-900">Provide my own final columns</span>
            <span className="block text-slate-600">
              Type or paste column names, or upload a CSV/Excel file whose first row is the header.
            </span>
          </span>
        </label>
        {mode === 'CUSTOM' && (
          <div className="ml-6 space-y-2">
            <label htmlFor="custom-columns" className="sr-only">
              Target column names
            </label>
            <textarea
              id="custom-columns"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              placeholder={'One column per line (or comma-separated), e.g.\nUMR\nGross Premium\nCommission\nNet Premium'}
              className="w-full rounded border border-slate-300 px-2 py-1.5 font-mono text-sm"
            />
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="cursor-pointer rounded border border-slate-300 px-2 py-1 font-medium text-slate-700 hover:bg-slate-100">
                {reading ? 'Reading file...' : 'Upload header from file'}
                <input
                  type="file"
                  accept=".csv,.xlsx,.xlsm,.txt,.tsv"
                  className="sr-only"
                  disabled={reading}
                  onChange={(e) => {
                    void onFile(e.target.files?.[0]);
                    e.target.value = '';
                  }}
                />
              </label>
              <span className="text-slate-500">{customColumns.length} column(s)</span>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="cursor-pointer rounded border border-slate-300 px-2 py-1 font-medium text-slate-700 hover:bg-slate-100">
                {reading ? 'Reading file...' : 'Upload columns and recognised terms (CSV/Excel)'}
                <input
                  type="file"
                  accept=".csv,.tsv,.xlsx,.xlsm"
                  className="sr-only"
                  disabled={reading}
                  aria-label="Upload columns and recognised terms"
                  onChange={(e) => {
                    void onTermsFile(e.target.files?.[0]);
                    e.target.value = '';
                  }}
                />
              </label>
              <span className="text-xs text-slate-500">
                First row: your final columns. Below each one: the terms you recognise it by.
              </span>
            </div>
            {fileError && (
              <p role="alert" className="text-sm text-red-700">
                {fileError}
              </p>
            )}
            {fileNote && (
              <p role="status" className="text-sm text-green-800">
                {fileNote}
              </p>
            )}
            {customColumns.length > 0 && (
              <details open={Object.keys(termsPayload(customColumns, termText)).length > 0} className="rounded border border-slate-200 p-2">
                <summary className="cursor-pointer text-sm font-medium text-slate-800">
                  Recognised terms for each column (optional)
                </summary>
                <p className="mt-1 text-xs text-slate-500">
                  A source column whose name is one of these terms maps to that column at 100% confidence. One term per
                  line. Terms are kept with the column name above, so rename a column before adding its terms.
                </p>
                <ul className="mt-2 space-y-2">
                  {customColumns.map((col) => (
                    <li key={col} className="grid gap-1 sm:grid-cols-[12rem_1fr] sm:items-start">
                      <span className="truncate pt-1 text-sm font-medium text-slate-700" title={col}>
                        {col}
                      </span>
                      <textarea
                        aria-label={`Recognised terms for ${col}`}
                        value={termText[col] ?? ''}
                        onChange={(e) => setTermText((prev) => ({ ...prev, [col]: e.target.value }))}
                        rows={2}
                        placeholder={'One term per line, e.g.\nGWP'}
                        className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs"
                      />
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <p className="text-xs text-slate-500">
              Columns matching a standard term keep their meaning (so financial checks still work); any others are
              treated as plain text columns. The standard terms still apply to columns that match the dictionary.
            </p>
          </div>
        )}
      </fieldset>

      {aiOption}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={confirm}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? 'Generating...' : 'Use this format and generate mappings'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} disabled={busy} className="text-sm text-slate-600 underline hover:text-slate-900">
            Cancel
          </button>
        )}
      </div>
    </section>
  );
}
