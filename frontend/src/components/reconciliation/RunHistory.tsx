import { Link } from 'react-router-dom';
import { useReconRuns } from '../../hooks/useRecon';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { ReconStatusBadge } from './RunResults';

export function RunHistory({ projectId }: { projectId: string }) {
  const { data, isLoading, error, refetch } = useReconRuns(projectId);
  if (isLoading) return <LoadingState label="Loading previous runs..." />;
  if (error) return <ErrorState error={error} title="Could not load runs" onRetry={() => refetch()} />;
  if (!data || data.length === 0) {
    return <EmptyState title="No reconciliation runs yet" description="Configure rules on the Rules & Run tab and start a run." />;
  }
  return (
    <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
      {data.map((r) => (
        <li key={r.id}>
          <Link
            to={`/projects/${projectId}/reconciliation/runs/${r.id}`}
            className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500"
          >
            <span>
              <span className="font-medium text-slate-900">{r.name || 'Reconciliation'}</span>
              <span className="ml-2 text-xs text-slate-500">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</span>
            </span>
            <ReconStatusBadge value={String((r.summary as { status?: string } | null)?.status ?? r.status)} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
