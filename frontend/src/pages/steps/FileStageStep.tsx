import type { ProcessingRun } from '../../api/types';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';

/** Covers STARTED -> FILE_UPLOADED -> FILE_VALIDATED: the linear pre-cleaning actions. */
export function FileStageStep({
  run,
  onValidate,
  onClean,
  validating,
  cleaning,
  error,
}: {
  run: ProcessingRun;
  onValidate: () => void;
  onClean: () => void;
  validating: boolean;
  cleaning: boolean;
  error: unknown;
}) {
  const filename = run.original_filename ?? run.filename ?? 'Uploaded file';

  if (run.status === 'STARTED') {
    return <LoadingState label="Processing upload..." />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded border border-slate-200 bg-white p-4">
        <p className="font-medium text-slate-900">{filename}</p>
        {typeof run.file_size === 'number' || typeof run.file_size_bytes === 'number' ? (
          <p className="text-sm text-slate-500">
            {(((run.file_size ?? run.file_size_bytes) as number) / (1024 * 1024)).toFixed(2)} MB
          </p>
        ) : null}
        {run.sheet_name && <p className="text-sm text-slate-500">Worksheet: {run.sheet_name}</p>}
      </div>

      {error ? <ErrorState error={error} title="Action failed" /> : null}

      {run.status === 'FILE_UPLOADED' && (
        <button
          type="button"
          onClick={onValidate}
          disabled={validating}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          {validating ? 'Validating...' : 'Validate file'}
        </button>
      )}

      {run.status === 'FILE_VALIDATED' && (
        <>
          <p className="text-sm text-green-700">File structure validated.</p>
          <button
            type="button"
            onClick={onClean}
            disabled={cleaning}
            className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
          >
            {cleaning ? 'Cleaning...' : 'Clean and standardize'}
          </button>
        </>
      )}
    </div>
  );
}
