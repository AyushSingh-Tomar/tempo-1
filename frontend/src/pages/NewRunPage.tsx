import { useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { ErrorState } from '../components/common/ErrorState';
import { FileDropZone } from '../components/upload/FileDropZone';
import { SheetPicker } from '../components/upload/SheetPicker';
import { api, sheetsFromUploadError } from '../api/endpoints';
import { isApiError } from '../api/errors';
import { rememberRun } from '../stores/recentRuns';

export function NewRunPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [sheets, setSheets] = useState<string[] | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function doUpload(sheetName?: string) {
    if (!projectId || !file) return;
    setUploading(true);
    setError(null);
    setProgress(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await api.runs.upload(projectId, file, sheetName, setProgress, controller.signal);
      if (result.kind === 'sheet_selection') {
        setSheets(result.sheets);
        setUploading(false);
        return;
      }
      rememberRun({ runId: result.run.id, projectId, filename: file.name, createdAt: new Date().toISOString() });
      navigate(`/runs/${result.run.id}`);
    } catch (err) {
      // Some backends signal "pick a worksheet" as a 400/422 with the sheet
      // list in error.details, rather than a 200 with no run created.
      if (isApiError(err)) {
        const sheetNames = sheetsFromUploadError(err.details);
        if (sheetNames) {
          setSheets(sheetNames);
          setUploading(false);
          return;
        }
      }
      setError(err);
      setUploading(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl">
        <Link to={projectId ? `/projects/${projectId}` : '/'} className="text-sm text-slate-500 hover:text-slate-700">
          &larr; Back to project
        </Link>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">Start a new processing run</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload an Excel (.xlsx) or CSV (.csv) bordereaux file. The server performs the authoritative validation;
          the workflow will not advance on a rejected upload.
        </p>

        <div className="mt-4">
          <FileDropZone
            disabled={uploading}
            onFileSelected={(f) => {
              setFile(f);
              setSheets(null);
              setError(null);
            }}
          />
        </div>

        {file && !sheets && (
          <button
            type="button"
            onClick={() => doUpload()}
            disabled={uploading}
            className="mt-4 rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
          >
            {uploading ? `Uploading... ${progress}%` : 'Upload and start run'}
          </button>
        )}

        {uploading && (
          <div className="mt-2 h-2 w-full rounded-full bg-slate-200" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2 rounded-full bg-slate-700" style={{ width: `${progress}%` }} />
          </div>
        )}

        {sheets && sheets.length > 0 && (
          <div className="mt-4">
            <SheetPicker sheets={sheets} disabled={uploading} onConfirm={(sheetName) => doUpload(sheetName)} />
          </div>
        )}

        {error ? (
          <div className="mt-4">
            <ErrorState error={error} title="Upload failed" onRetry={() => setError(null)} />
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
