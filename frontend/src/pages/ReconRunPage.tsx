import { Link, useParams } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { RunResults } from '../components/reconciliation/RunResults';
import { useReconRun } from '../hooks/useRecon';

export function ReconRunPage() {
  const { projectId, runId } = useParams<{ projectId: string; runId: string }>();
  const { data, isLoading, error, refetch } = useReconRun(runId);
  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
          <Link to="/" className="hover:text-slate-700">Projects</Link> /{' '}
          <Link to={`/projects/${projectId}`} className="hover:text-slate-700">Project</Link> /{' '}
          <Link to={`/projects/${projectId}/reconciliation`} className="hover:text-slate-700">Reconciliation</Link> / <span className="text-slate-800">Results</span>
        </nav>
        <div className="mt-3">
          {isLoading && <LoadingState label="Loading results..." />}
          {error && <ErrorState error={error} title="Could not load the run" onRetry={() => refetch()} />}
          {data && <RunResults run={data} />}
        </div>
      </div>
    </AppShell>
  );
}
