import { useEffect, useState } from 'react';
import type { EncodingInfo, EncodingOption, FilePatch, ReconFile } from '../../api/reconTypes';
import { formatBytes } from '../../utils/recon';
import { ApiErrorBanner, MultiSelect, btnSecondary, inputCls } from './ui';

/** Detected encoding, method, comparison of candidates and a table of differing lines. */
export function EncodingPanel({
  file,
  info,
  options,
  canEdit,
  busy,
  error,
  onApply,
  onRecheck,
}: {
  file: ReconFile;
  info: EncodingInfo | null;
  options: EncodingOption[];
  canEdit: boolean;
  busy?: boolean;
  error?: unknown;
  onApply: (patch: FilePatch) => void;
  onRecheck: (candidates: string[]) => void;
}) {
  const [candidates, setCandidates] = useState<string[]>(file.encoding_choice?.candidates ?? []);
  const [forced, setForced] = useState<string>(file.encoding_choice?.forced ?? '');
  useEffect(() => {
    setCandidates(file.encoding_choice?.candidates ?? []);
    setForced(file.encoding_choice?.forced ?? '');
  }, [file.id, file.encoding_choice]);

  if (file.format === 'XLSX') {
    return <p className="text-xs text-slate-500">Encoding: not applicable to Excel workbooks.</p>;
  }
  const compared = info?.compared ?? [];
  const differences = info?.differences ?? [];
  const candidateRows = info?.candidates ?? [];
  return (
    <div className="space-y-3 rounded border border-slate-200 bg-slate-50 p-3" aria-label={`Encoding for ${file.filename}`}>
      <p className="text-sm">
        Encoding: <strong>{info?.chosen ?? file.encoding ?? 'unknown'}</strong>
        {info?.method && <span className="ml-2 rounded bg-white px-1.5 py-0.5 text-xs text-slate-600">{info.method.replace(/_/g, ' ')}</span>}
        {info?.detector_guess && <span className="ml-2 text-xs text-slate-500">detector guess: {info.detector_guess}</span>}
      </p>

      {(info?.warnings ?? []).map((w, i) => (
        <p key={i} role="alert" className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
          {w}
        </p>
      ))}

      {compared.length > 1 && (
        <div>
          <p className="text-xs text-slate-600">
            Compared: {compared.join(' vs ')} -{' '}
            {info?.all_agree ? 'all candidates decode the sample identically.' : 'candidates disagree on the lines below.'}
          </p>
          {differences.length > 0 && (
            <div className="mt-1 overflow-x-auto">
              <table className="min-w-full text-xs">
                <caption className="sr-only">Lines that decode differently</caption>
                <thead>
                  <tr className="text-left text-slate-500">
                    <th scope="col" className="pr-3">Line</th>
                    {compared.map((c) => (
                      <th key={c} scope="col" className="pr-3">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {differences.slice(0, 10).map((d, i) => (
                    <tr key={i} className="border-t border-slate-200">
                      <td className="pr-3 font-mono">{String(d.line)}</td>
                      {compared.map((c) => (
                        <td key={c} className="pr-3 font-mono">{String(d[c] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {candidateRows.length > 0 && (
        <table className="min-w-full text-xs">
          <caption className="sr-only">Quality per candidate encoding</caption>
          <thead>
            <tr className="text-left text-slate-500">
              <th scope="col" className="pr-3">Encoding</th>
              <th scope="col" className="pr-3">Decodes cleanly</th>
              <th scope="col" className="pr-3">Replacement chars</th>
              <th scope="col" className="pr-3">Mojibake</th>
              <th scope="col" className="pr-3">Score</th>
            </tr>
          </thead>
          <tbody>
            {candidateRows.map((c) => (
              <tr key={c.encoding} className="border-t border-slate-200">
                <td className="pr-3 font-mono">{c.encoding}</td>
                <td className="pr-3">{c.decodes_cleanly ? 'yes' : `no${c.error ? ` (${c.error})` : ''}`}</td>
                <td className="pr-3">{c.replacement_chars}</td>
                <td className="pr-3">{c.mojibake_pairs}</td>
                <td className="pr-3">{c.score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="flex flex-wrap items-end gap-4">
        <MultiSelect
          label="Encodings to check"
          options={options}
          selected={candidates}
          onChange={setCandidates}
          disabled={!canEdit}
          placeholder="Server defaults"
        />
        <div>
          <label htmlFor={`force-${file.id}`} className="block text-xs font-medium text-slate-600">
            Force encoding
          </label>
          <select
            id={`force-${file.id}`}
            value={forced}
            disabled={!canEdit}
            onChange={(e) => setForced(e.target.value)}
            className={`${inputCls} mt-1`}
          >
            <option value="">Auto-detect</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <button type="button" className={btnSecondary} disabled={busy} onClick={() => onRecheck(candidates)}>
          Re-check encoding
        </button>
        <button
          type="button"
          className={btnSecondary}
          disabled={!canEdit || busy}
          onClick={() => onApply({ encoding: forced, candidate_encodings: candidates.length ? candidates : null })}
        >
          Apply encoding settings
        </button>
      </div>
      <ApiErrorBanner error={error} />
    </div>
  );
}

/** Multi-sheet checkbox picker, flagged when no sheet has been chosen. */
export function SheetChoice({
  file,
  canEdit,
  onChange,
}: {
  file: ReconFile;
  canEdit: boolean;
  onChange: (sheets: string[]) => void;
}) {
  if (file.sheets.length <= 1) return null;
  return (
    <fieldset className={`rounded border p-3 ${file.needs_sheet_choice ? 'border-amber-300 bg-amber-50' : 'border-slate-200'}`}>
      <legend className="px-1 text-xs font-medium text-slate-700">Worksheets to include</legend>
      {file.needs_sheet_choice && (
        <p role="alert" className="mb-2 text-xs font-medium text-amber-900">
          Choose at least one sheet - this workbook has {file.sheets.length} sheets.
        </p>
      )}
      <div className="flex flex-wrap gap-4">
        {file.sheets.map((s) => (
          <label key={s} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={file.selected_sheets.includes(s)}
              onChange={(e) =>
                onChange(e.target.checked ? [...file.selected_sheets, s] : file.selected_sheets.filter((x) => x !== s))
              }
            />
            {s}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function FileCard({
  file,
  options,
  canEdit,
  busy,
  error,
  checkedInfo,
  onPatch,
  onRecheck,
  onRemove,
}: {
  file: ReconFile;
  options: EncodingOption[];
  canEdit: boolean;
  busy?: boolean;
  error?: unknown;
  checkedInfo?: EncodingInfo | null;
  onPatch: (patch: FilePatch) => void;
  onRecheck: (candidates: string[]) => void;
  onRemove: () => void;
}) {
  const [header, setHeader] = useState(String(file.header_row));
  useEffect(() => setHeader(String(file.header_row)), [file.header_row]);
  const headerNum = Number(header);
  const headerValid = Number.isInteger(headerNum) && headerNum >= 1;
  return (
    <li className="space-y-3 rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{file.filename}</p>
          <p className="text-xs text-slate-500">
            {file.format} - {formatBytes(file.size_bytes)}
          </p>
        </div>
        <button type="button" className={btnSecondary} disabled={!canEdit} onClick={onRemove} aria-label={`Remove ${file.filename}`}>
          Remove
        </button>
      </div>

      <EncodingPanel
        file={file}
        info={checkedInfo ?? file.encoding_info}
        options={options}
        canEdit={canEdit}
        busy={busy}
        error={error}
        onApply={onPatch}
        onRecheck={onRecheck}
      />

      <SheetChoice file={file} canEdit={canEdit} onChange={(sheets) => onPatch({ selected_sheets: sheets })} />

      <div className="flex items-end gap-2">
        <div>
          <label htmlFor={`hdr-${file.id}`} className="block text-xs font-medium text-slate-600">
            Header row number
          </label>
          <input
            id={`hdr-${file.id}`}
            type="number"
            min={1}
            value={header}
            disabled={!canEdit}
            onChange={(e) => setHeader(e.target.value)}
            className={`${inputCls} mt-1 w-24`}
          />
        </div>
        <button
          type="button"
          className={btnSecondary}
          disabled={!canEdit || !headerValid || headerNum === file.header_row}
          onClick={() => onPatch({ header_row: headerNum })}
        >
          Set header row
        </button>
      </div>
    </li>
  );
}
