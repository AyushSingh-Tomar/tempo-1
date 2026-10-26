import { Link, useParams } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { EmptyState } from '../components/common/EmptyState';
import { StatusBadge } from '../components/common/StatusBadge';
import { useProject, useProjectRuns } from '../hooks/useProjects';
import { recentRunsForProject } from '../stores/recentRuns';
import { isNotAvailable } from '../api/errors';

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, error, refetch } = useProject(projectId);
  const { data: serverRuns, error: runsError } = useProjectRuns(projectId);

  const localRuns = projectId ? recentRunsForProject(projectId) : [];
  // Prefer the server's list when available; otherwise fall back to the
  // browser's locally-remembered runs for this project (see recentRuns.ts).
  const runs =
    serverRuns && !runsError
      ? serverRuns.map((r) => ({ runId: r.id, status: r.status as string | undefined }))
      : localRuns.map((r) => ({ runId: r.runId, filename: r.filename, status: undefined as string | undefined }));

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
          &larr; All projects
        </Link>

        {isLoading && <LoadingState label="Loading project..." />}
        {error && !isLoading && (
          <ErrorState error={error} title={isNotAvailable(error) ? 'Project not available' : 'Could not load project'} onRetry={() => refetch()} />
        )}

        {!isLoading && !error && project && (
          <>
            <div className="mt-2 flex items-center justify-between">
              <div>
                <h1 className="text-xl font-semibold text-slate-900">{project.name}</h1>
                {project.description && <p className="text-sm text-slate-500">{project.description}</p>}
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/projects/${project.id}/reconciliation`}
                  className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                >
                  Reconciliation
                </Link>
                <Link
                  to={`/projects/${project.id}/new-run`}
                  className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
                >
                  New processing run
                </Link>
              </div>
            </div>

            <section className="mt-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Processing runs</h2>
              {runs.length === 0 ? (
                <div className="mt-2">
                  <EmptyState
                    title="No processing runs yet"
                    description="Start a new run to upload a bordereaux file and work through the wizard."
                    action={
                      <Link
                        to={`/projects/${project.id}/new-run`}
                        className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                      >
                        Start a processing run
                      </Link>
                    }
                  />
                </div>
              ) : (
                <ul className="mt-2 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
                  {runs.map((r) => (
                    <li key={r.runId}>
                      <Link
                        to={`/runs/${r.runId}`}
                        className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                      >
                        <span className="font-mono text-sm text-slate-700">{r.runId}</span>
                        {r.status && <StatusBadge value={r.status} />}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
