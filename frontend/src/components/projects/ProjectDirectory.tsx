import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { TypeToConfirmDialog } from '../common/TypeToConfirmDialog';
import { useCreateProject, useDeleteProject, useProjects } from '../../hooks/useProjects';
import { describeError, isNotAvailable } from '../../api/errors';
import { useDevRole } from '../../stores/devAuth';
import { archiveProject, isArchivedProject, listenForArchivedProjectChanges } from '../../stores/archivedProjects';
import type { Project } from '../../api/types';

function formatDate(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

/**
 * The directory of projects: search, open, create, and (project owners only,
 * after typing the project's name) delete.
 */
export function ProjectDirectory() {
  const { data, isLoading, error, refetch } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const role = useDevRole();
  const canDelete = role === 'project_owner';

  const [query, setQuery] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Project | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    const unsubscribe = listenForArchivedProjectChanges(() => setRefreshTick((value) => value + 1));
    return unsubscribe;
  }, []);

  const activeProjects = useMemo(() => (data ? data.filter((project) => !isArchivedProject(project.id)) : []), [data, refreshTick]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!activeProjects.length && !q) return [];
    if (!q) return activeProjects;
    return activeProjects.filter((p) => p.name.toLowerCase().includes(q) || (p.description ?? '').toLowerCase().includes(q));
  }, [activeProjects, query]);

  function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createProject.mutate(
      { name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: () => {
          setName('');
          setDescription('');
          setShowForm(false);
        },
      },
    );
  }

  function confirmDelete() {
    if (!toDelete) return;
    setDeleteError(null);
    deleteProject.mutate(
      { id: toDelete.id, confirmName: toDelete.name },
      {
        onSuccess: () => {
          setToDelete(null);
          setMenuOpenId(null);
        },
        onError: (err) => setDeleteError(describeError(err)),
      },
    );
  }

  function archiveProjectFromList(project: Project) {
    archiveProject(project);
    setRefreshTick((value) => value + 1);
    setMenuOpenId(null);
  }

  return (
    <section id="projects" aria-labelledby="projects-heading" className="scroll-mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="projects-heading" className="text-lg font-semibold text-slate-900">
            Projects
          </h2>
          <p className="text-sm text-slate-500">Each project holds its own processing runs and reconciliations.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          New project
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-4 space-y-3 rounded border border-slate-200 bg-white p-4">
          <div>
            <label htmlFor="project-name" className="block text-sm font-medium text-slate-800">
              Name <span className="text-red-600">*</span>
            </label>
            <input
              id="project-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </div>
          <div>
            <label htmlFor="project-description" className="block text-sm font-medium text-slate-800">
              Description
            </label>
            <textarea
              id="project-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5"
            />
          </div>
          {createProject.isError && <ErrorState error={createProject.error} title="Could not create project" />}
          <button
            type="submit"
            disabled={createProject.isPending || !name.trim()}
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {createProject.isPending ? 'Creating...' : 'Create project'}
          </button>
        </form>
      )}

      <div className="mt-4">
        {isLoading && <LoadingState label="Loading projects..." />}
        {error && !isLoading && (
          <ErrorState
            error={error}
            title={isNotAvailable(error) ? 'Projects are not available yet' : 'Could not load projects'}
            onRetry={() => refetch()}
          />
        )}
        {!isLoading && !error && (!data || activeProjects.length === 0) && (
          <EmptyState
            title="No projects yet"
            description="Create a project to start a bordereaux processing run."
            action={
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
              >
                Create your first project
              </button>
            }
          />
        )}
        {!isLoading && !error && data && activeProjects.length > 0 && (
          <>
            <div className="mb-2 flex items-center justify-between gap-3">
              <label htmlFor="project-search" className="sr-only">
                Search projects
              </label>
              <input
                id="project-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search projects"
                className="w-full max-w-xs rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
              <span className="text-xs text-slate-500">
                {visible.length} of {activeProjects.length}
              </span>
            </div>
            {visible.length === 0 ? (
              <p className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-500">
                No project matches “{query.trim()}”.
              </p>
            ) : (
              <div
                role="region"
                aria-label="Projects list"
                tabIndex={0}
                className="max-h-96 overflow-y-auto overscroll-contain rounded border border-slate-200 bg-white"
              >
                <ul aria-label="Projects" className="divide-y divide-slate-200">
                  {visible.map((p) => (
                    <li key={p.id} className="flex items-stretch">
                      <Link
                        to={`/projects/${p.id}`}
                        className="block flex-1 px-4 py-3 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                      >
                        <p className="font-medium text-slate-900">{p.name}</p>
                        {p.description && <p className="text-sm text-slate-500">{p.description}</p>}
                        {p.created_at && <p className="mt-0.5 text-xs text-slate-400">Created {formatDate(p.created_at)}</p>}
                      </Link>
                      {canDelete && (
                        <div className="relative flex items-center gap-1">
                          <button
                            type="button"
                            aria-label={`Delete project ${p.name}`}
                            onClick={() => {
                              setDeleteError(null);
                              setToDelete(p);
                              setMenuOpenId(null);
                            }}
                            className="sr-only"
                          >
                            Delete project {p.name}
                          </button>
                          <button
                            type="button"
                            aria-label={`Project actions for ${p.name}`}
                            onClick={() => setMenuOpenId((current) => (current === p.id ? null : p.id))}
                            className="flex h-full items-center px-3 text-lg font-bold text-slate-500 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                          >
                            ⋮
                          </button>
                          {menuOpenId === p.id && (
                            <div className="absolute right-2 top-full z-10 mt-1 min-w-40 rounded border border-slate-200 bg-white p-1 shadow-lg">
                              <button
                                type="button"
                                onClick={() => {
                                  setDeleteError(null);
                                  setToDelete(p);
                                  setMenuOpenId(null);
                                }}
                                className="block w-full rounded px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50"
                              >
                                Delete project
                              </button>
                              <button
                                type="button"
                                onClick={() => archiveProjectFromList(p)}
                                className="block w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                              >
                                Archive project
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!canDelete && <p className="mt-2 text-xs text-slate-400">Only a project owner can delete a project.</p>}
          </>
        )}
      </div>

      {toDelete && (
        <TypeToConfirmDialog
          title="Delete project"
          description={`This removes “${toDelete.name}” from the directory. Its runs, uploads and audit history are kept on record but can no longer be opened from here.`}
          expected={toDelete.name}
          confirmLabel="Delete project"
          busy={deleteProject.isPending}
          error={deleteError}
          onConfirm={confirmDelete}
          onCancel={() => setToDelete(null)}
        />
      )}
    </section>
  );
}
