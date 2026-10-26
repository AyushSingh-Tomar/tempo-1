import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ArtifactType, PeriodExtract, ProcessingRun } from '../../api/types';
import { ErrorState } from '../../components/common/ErrorState';
import { ReportActions, type PeriodSelection } from '../../components/reports/ReportActions';
import { useRunAction } from '../../hooks/useRunAction';
import { api } from '../../api/endpoints';
import { useReconPermissions } from '../../hooks/useRecon';

export function ReportStep({ run }: { run: ProcessingRun }) {
  const [downloading, setDownloading] = useState<ArtifactType | null>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const generate = useRunAction(run.id, () => api.reports.generate(run.id));
  const queryClient = useQueryClient();
  const extracts = useQuery({
    queryKey: ['period-extracts', run.id],
    queryFn: () => api.reports.listPeriodExtracts(run.id),
    enabled: run.status === 'COMPLETED',
  });
  const navigate = useNavigate();
  const { canCreate } = useReconPermissions();
  // Option 1: reconcile straight from this run - its processed file becomes the final bordereaux.
  const reconcile = useMutation({
    mutationFn: () => api.recon.bordereauxFromRun(run.id),
    onSuccess: (ds) => navigate(`/projects/${run.project_id}/reconciliation?bordereaux=${ds.id}&tab=subledger&run=${run.id}`),
  });

  async function handleDownload(type: ArtifactType) {
    setDownloading(type);
    setDownloadError(null);
    try {
      await api.reports.download(run.id, type);
    } catch (err) {
      setDownloadError(err);
    } finally {
      setDownloading(null);
    }
  }

  async function handleDownloadPeriod(period: PeriodSelection) {
    setDownloading('processed_file');
    setDownloadError(null);
    try {
      const extract = await api.reports.createPeriodExtract(run.id, period);
      await api.reports.downloadPeriodExtract(run.id, extract);
      void queryClient.invalidateQueries({ queryKey: ['period-extracts', run.id] });
    } catch (err) {
      setDownloadError(err);
    } finally {
      setDownloading(null);
    }
  }

  async function handleDownloadExtract(extract: PeriodExtract) {
    setDownloadError(null);
    try {
      await api.reports.downloadPeriodExtract(run.id, extract);
    } catch (err) {
      setDownloadError(err);
    }
  }

  return (
    <div className="space-y-4">
      {generate.isError && <ErrorState error={generate.error} title="Report generation failed" />}
      {downloadError ? (
        <ErrorState error={downloadError} title="Download failed" onRetry={() => setDownloadError(null)} />
      ) : null}
      <ReportActions
        run={run}
        onGenerate={() => generate.mutate(undefined)}
        onDownload={handleDownload}
        onDownloadPeriod={handleDownloadPeriod}
        extracts={extracts.data}
        onDownloadExtract={handleDownloadExtract}
        generating={generate.isPending}
        downloading={downloading}
      />
      {run.status === 'COMPLETED' && (
        <section aria-labelledby="reconcile-heading" className="rounded-md border border-slate-200 bg-slate-50 p-4">
          <h3 id="reconcile-heading" className="text-sm font-semibold text-slate-900">
            Next: reconcile against a subledger
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Use the file you just processed as the bordereaux, then add your subledger and the rules to check.
          </p>
          {reconcile.isError && <ErrorState error={reconcile.error} title="Could not start reconciliation" />}
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <button
              type="button"
              onClick={() => reconcile.mutate()}
              disabled={reconcile.isPending || !canCreate}
              className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {reconcile.isPending ? 'Preparing...' : 'Reconcile this file with a subledger'}
            </button>
            <Link to={`/projects/${run.project_id}/reconciliation`} className="text-sm font-medium text-slate-600 underline hover:text-slate-900">
              or start with your own bordereaux and subledger files
            </Link>
          </div>
          {!canCreate && <p className="mt-2 text-xs text-slate-500">Your role can view reconciliations but not start them.</p>}
        </section>
      )}
      {run.status === 'COMPLETED' && (
        <p className="text-sm text-slate-500">
          This run's history, decisions, and lineage remain accessible at this URL for later reference.
        </p>
      )}
    </div>
  );
}
