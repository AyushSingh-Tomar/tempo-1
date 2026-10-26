import { useRef, useState } from 'react';
import type { DatasetKind, EncodingInfo, ReconDataset } from '../../api/reconTypes';
import {
  useCreateReconDataset,
  useDatasetPreview,
  useDeleteReconFile,
  useEncodingCheck,
  useEncodingOptions,
  useFinalizeDataset,
  usePatchReconFile,
  useReconDataset,
  useReconDatasets,
  useSchemaSummary,
  useUploadReconFiles,
} from '../../hooks/useRecon';
import type { Aliases } from '../../utils/recon';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FileCard } from './FileCard';
import { FinalReport } from './FinalReport';
import { SchemaStep } from './SchemaStep';
import { ApiErrorBanner, MultiSelect, Section, btnPrimary, btnSecondary, inputCls } from './ui';

const COPY: Record<DatasetKind, { title: string; noun: string; help: string; placeholder: string }> = {
  BORDEREAUX: {
    title: 'Bordereaux',
    noun: 'bordereaux',
    help: 'Upload the bordereaux files received from the cedant (one or many, any mix of xlsx, csv, sas7bdat). They are combined into one standardised bordereaux.',
    placeholder: 'e.g. Bordereaux FY2023',
  },
  SUBLEDGER: {
    title: 'Subledger',
    noun: 'subledger',
    help: 'Upload the accounting subledger extracts (one or many files). They are combined into one standardised subledger to reconcile against.',
    placeholder: 'e.g. Subledger FY2023',
  },
};

const READONLY_NOTE = 'Your role is read-only for reconciliation (reviewer / viewer). You can browse but not change data.';

function UploadZone({
  disabled,
  progress,
  onFiles,
}: {
  disabled: boolean;
  progress: number | null;
  onFiles: (files: File[]) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        aria-label="Upload files: drag and drop or press Enter to browse"
        onClick={() => !disabled && ref.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            ref.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (!disabled && e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files));
        }}
        className={`rounded-md border-2 border-dashed p-6 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500 ${
          over ? 'border-slate-500 bg-slate-50' : 'border-slate-300'
        } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
      >
        <p className="font-medium text-slate-700">Drag and drop files here, or click to browse</p>
        <p className="mt-1 text-xs text-slate-500">Accepted: .xlsx, .csv, .sas7bdat - you can select several files</p>
        <input
          ref={ref}
          type="file"
          multiple
          accept=".xlsx,.csv,.sas7bdat"
          className="sr-only"
          aria-label="Choose files"
          disabled={disabled}
          onChange={(e) => {
            if (e.target.files?.length) onFiles(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
      </div>
      {progress !== null && (
        <div className="mt-2" role="status" aria-live="polite">
          <div className="h-2 overflow-hidden rounded bg-slate-200">
            <div className="h-full bg-slate-700" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-1 text-xs text-slate-500">Uploading... {progress}%</p>
        </div>
      )}
    </div>
  );
}

function DraftBuilder({
  projectId,
  dataset,
  canCreate,
  onStartNew,
}: {
  projectId: string;
  dataset: ReconDataset;
  canCreate: boolean;
  onStartNew: () => void;
}) {
  const id = dataset.id;
  const files = dataset.files ?? [];
  const encodings = useEncodingOptions();
  const encOptions = encodings.data?.encodings ?? [];
  const upload = useUploadReconFiles(id);
  const patch = usePatchReconFile(id);
  const remove = useDeleteReconFile(id);
  const check = useEncodingCheck(id);
  const schema = useSchemaSummary(id);
  const finalize = useFinalizeDataset(id, projectId);

  const [progress, setProgress] = useState<number | null>(null);
  const [uploadEnc, setUploadEnc] = useState('');
  const [uploadCands, setUploadCands] = useState<string[]>([]);
  const [checked, setChecked] = useState<Record<string, EncodingInfo>>({});
  const [busyFile, setBusyFile] = useState<string | null>(null);
  const [aliases, setAliases] = useState<Aliases>({});
  const [periodColumn, setPeriodColumn] = useState('');
  const [dayFirst, setDayFirst] = useState(true);
  const [dropDup, setDropDup] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const needsSheets = files.filter((f) => f.needs_sheet_choice);
  const canAnalyse = canCreate && files.length > 0 && needsSheets.length === 0;
  const dateColumns = Array.from(
    new Set(
      (schema.data?.summary.tables ?? []).flatMap((t) => t.columns.filter((c) => c.type === 'DATE').map((c) => c.standard)),
    ),
  ).sort();

  function doUpload(list: File[]) {
    setProgress(0);
    upload.mutate(
      {
        files: list,
        encoding: uploadEnc || undefined,
        candidateEncodings: uploadCands,
        onProgress: setProgress,
      },
      { onSettled: () => setProgress(null) },
    );
  }

  function recheck(fileId: string, candidates: string[]) {
    setBusyFile(fileId);
    check.mutate(
      { fileId, candidates },
      {
        onSuccess: (info) => setChecked((c) => ({ ...c, [fileId]: info })),
        onSettled: () => setBusyFile(null),
      },
    );
  }

  function applyPatch(fileId: string, p: Parameters<typeof patch.mutate>[0]['patch']) {
    setBusyFile(fileId);
    patch.mutate(
      { fileId, patch: p },
      {
        onSuccess: () => setChecked((c) => {
          const next = { ...c };
          delete next[fileId];
          return next;
        }),
        onSettled: () => setBusyFile(null),
      },
    );
  }

  return (
    <div className="space-y-4">
      {!canCreate && <p className="rounded border border-slate-200 bg-slate-50 p-2 text-sm text-slate-600">{READONLY_NOTE}</p>}

      <Section step="a" title="Upload files" hint="Optional encoding settings apply to the files you upload next; you can change them per file afterwards.">
        <div className="mb-3 flex flex-wrap items-end gap-4">
          <MultiSelect
            label="Encodings to check (upload)"
            options={encOptions}
            selected={uploadCands}
            onChange={setUploadCands}
            disabled={!canCreate}
            placeholder="Server defaults"
          />
          <div>
            <label htmlFor="upload-force-enc" className="block text-xs font-medium text-slate-600">Force encoding (upload)</label>
            <select id="upload-force-enc" value={uploadEnc} onChange={(e) => setUploadEnc(e.target.value)} disabled={!canCreate} className={`${inputCls} mt-1`}>
              <option value="">Auto-detect</option>
              {encOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>
        <UploadZone disabled={!canCreate || upload.isPending} progress={progress} onFiles={doUpload} />
        <div className="mt-2"><ApiErrorBanner error={upload.error} title="Upload failed" /></div>
      </Section>

      <Section step="b" title={`Files (${files.length})`}>
        {files.length === 0 ? (
          <p className="text-sm text-slate-500">No files yet. Upload at least one file to continue.</p>
        ) : (
          <ul className="space-y-3">
            {files.map((f) => (
              <FileCard
                key={f.id}
                file={f}
                options={encOptions}
                canEdit={canCreate}
                busy={busyFile === f.id}
                error={busyFile === f.id ? (patch.error ?? check.error) : null}
                checkedInfo={checked[f.id]}
                onPatch={(p) => applyPatch(f.id, p)}
                onRecheck={(c) => recheck(f.id, c)}
                onRemove={() => remove.mutate(f.id)}
              />
            ))}
          </ul>
        )}
        <div className="mt-2"><ApiErrorBanner error={remove.error} title="Could not remove the file" /></div>
      </Section>

      <Section step="c" title="Schema summary" hint="See how the columns line up across your files and merge columns that are really the same field.">
        <div className="flex items-center gap-3">
          <button type="button" className={btnPrimary} disabled={!canAnalyse || schema.isPending} onClick={() => schema.mutate(aliases)}>
            {schema.isPending ? 'Analysing...' : 'Analyse files'}
          </button>
          {needsSheets.length > 0 && (
            <span className="text-xs text-amber-800">Choose at least one sheet for: {needsSheets.map((f) => f.filename).join(', ')}</span>
          )}
        </div>
        <div className="mt-3 space-y-2">
          <ApiErrorBanner error={schema.error} title="Could not analyse the files" />
          {schema.isPending && <LoadingState label="Reading files..." />}
          {schema.data && <SchemaStep preview={schema.data} aliases={aliases} onAliasesChange={setAliases} canEdit={canCreate} />}
        </div>
      </Section>

      <Section step="d" title="Combine settings">
        <div className="space-y-3">
          <div>
            <label htmlFor="period-col" className="block text-xs font-medium text-slate-600">Period column</label>
            <select id="period-col" value={periodColumn} onChange={(e) => setPeriodColumn(e.target.value)} disabled={!canCreate} className={`${inputCls} mt-1`}>
              <option value="">Detect automatically</option>
              {dateColumns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <p className="mt-1 text-xs text-slate-500">
              {schema.data ? 'Date columns found in your files.' : 'Run "Analyse files" to list the date columns; otherwise the server picks one.'}
            </p>
          </div>
          <fieldset>
            <legend className="text-xs font-medium text-slate-600">Date order for ambiguous dates such as 03/04/2023</legend>
            <label className="mr-4 text-sm">
              <input type="radio" name={`dayfirst-${id}`} checked={dayFirst} disabled={!canCreate} onChange={() => setDayFirst(true)} /> Day first (03/04 = 3 April)
            </label>
            <label className="text-sm">
              <input type="radio" name={`dayfirst-${id}`} checked={!dayFirst} disabled={!canCreate} onChange={() => setDayFirst(false)} /> Month first (03/04 = March 4)
            </label>
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={dropDup} disabled={!canCreate} onChange={(e) => setDropDup(e.target.checked)} />
            Remove rows duplicated across files
          </label>
        </div>
      </Section>

      <Section step="e" title="Finalize">
        <p className="text-sm text-slate-600">Finalizing combines all files into one standardised dataset. A final dataset is immutable; to change it, start another dataset.</p>
        {!confirming ? (
          <button
            type="button"
            className={`${btnPrimary} mt-2`}
            disabled={!canCreate || files.length === 0 || needsSheets.length > 0}
            onClick={() => setConfirming(true)}
          >
            Finalize dataset...
          </button>
        ) : (
          <div role="alertdialog" aria-label="Confirm finalize" className="mt-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm">
            <p className="font-medium text-amber-900">Finalize "{dataset.name}"? It becomes read-only and cannot be edited afterwards.</p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className={btnPrimary}
                disabled={finalize.isPending}
                onClick={() =>
                  finalize.mutate(
                    { column_aliases: aliases, period_column: periodColumn || null, day_first: dayFirst, drop_cross_file_duplicates: dropDup },
                    { onSuccess: () => setConfirming(false) },
                  )
                }
              >
                {finalize.isPending ? 'Finalizing...' : 'Yes, finalize'}
              </button>
              <button type="button" className={btnSecondary} onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </div>
        )}
        <div className="mt-2"><ApiErrorBanner error={finalize.error} title="Could not finalize" /></div>
      </Section>

      <button type="button" className="text-xs text-slate-500 underline" onClick={onStartNew}>Back to dataset list</button>
    </div>
  );
}

function FinalView({ dataset }: { dataset: ReconDataset }) {
  const preview = useDatasetPreview(dataset.id, true, 25);
  if (!dataset.report) return <p className="text-sm text-slate-500">This dataset is final but has no report.</p>;
  return (
    <Section title="Final report">
      <FinalReport
        report={dataset.report}
        preview={preview.data}
        previewLoading={preview.isLoading}
        previewError={preview.error}
        onRetryPreview={() => preview.refetch()}
      />
    </Section>
  );
}

/**
 * Guided builder for one dataset kind. Selection lives in the parent so the
 * chosen dataset survives tab switches.
 */
export function DatasetBuilder({
  projectId,
  kind,
  datasetId,
  onDatasetChange,
  canCreate,
}: {
  projectId: string;
  kind: DatasetKind;
  datasetId: string | null;
  onDatasetChange: (id: string | null) => void;
  canCreate: boolean;
}) {
  const copy = COPY[kind];
  const list = useReconDatasets(projectId, kind);
  const detail = useReconDataset(datasetId ?? undefined);
  const create = useCreateReconDataset(projectId);
  const [name, setName] = useState('');

  function submitCreate() {
    if (!name.trim()) return;
    create.mutate({ kind, name: name.trim() }, { onSuccess: (ds) => { setName(''); onDatasetChange(ds.id); } });
  }

  const datasets = list.data ?? [];
  const dataset = detail.data;

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">{copy.help}</p>

      <div className="flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-white p-3">
        <div>
          <label htmlFor={`ds-switch-${kind}`} className="block text-xs font-medium text-slate-600">Existing {copy.noun} datasets</label>
          <select
            id={`ds-switch-${kind}`}
            value={datasetId ?? ''}
            onChange={(e) => onDatasetChange(e.target.value || null)}
            className={`${inputCls} mt-1 min-w-56`}
            disabled={list.isLoading}
          >
            <option value="">{datasets.length ? 'Select a dataset...' : 'None yet'}</option>
            {datasets.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.status})</option>)}
          </select>
        </div>
        <div>
          <label htmlFor={`ds-name-${kind}`} className="block text-xs font-medium text-slate-600">New dataset name</label>
          <input
            id={`ds-name-${kind}`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && canCreate) submitCreate(); }}
            placeholder={copy.placeholder}
            disabled={!canCreate}
            className={`${inputCls} mt-1 w-64`}
          />
        </div>
        <button type="button" className={btnPrimary} disabled={!canCreate || !name.trim() || create.isPending} onClick={submitCreate}>
          {create.isPending ? 'Creating...' : dataset?.status === 'FINAL' ? 'Start another dataset' : 'Create dataset'}
        </button>
        {!canCreate && <span className="text-xs text-slate-500">{READONLY_NOTE}</span>}
      </div>
      <ApiErrorBanner error={create.error} title="Could not create the dataset" />
      {list.error && <ErrorState error={list.error} title="Could not load datasets" onRetry={() => list.refetch()} />}

      {!datasetId && !list.isLoading && (
        <div className="rounded-md border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
          {datasets.length ? `Select a ${copy.noun} dataset above, or create a new one.` : `No ${copy.noun} dataset yet. Name one above to begin.`}
        </div>
      )}

      {datasetId && detail.isLoading && <LoadingState label="Loading dataset..." />}
      {datasetId && detail.error && <ErrorState error={detail.error} title="Could not load the dataset" onRetry={() => detail.refetch()} />}

      {dataset && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-slate-900">{dataset.name}</h3>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${dataset.status === 'FINAL' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
              {dataset.status}
            </span>
            {dataset.status === 'FINAL' && <span className="text-xs text-slate-500">Read-only (immutable)</span>}
          </div>
          {dataset.status === 'FINAL' ? (
            <FinalView dataset={dataset} />
          ) : (
            <DraftBuilder
              key={dataset.id}
              projectId={projectId}
              dataset={dataset}
              canCreate={canCreate}
              onStartNew={() => onDatasetChange(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}
