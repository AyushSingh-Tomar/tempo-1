import { useEffect, useMemo, useState } from 'react';
import { EmptyState } from '../common/EmptyState';
import {
  getArchivedProjects,
  restoreArchivedProject,
  deleteArchivedProject,
  listenForArchivedProjectChanges,
} from '../../stores/archivedProjects';
import type { Project } from '../../api/types';

function formatDate(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

export function ArchivedProjectDirectory() {
  const [tick, setTick] = useState(0);
  const [query, setQuery] = useState('');
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = listenForArchivedProjectChanges(() => setTick((value) => value + 1));
    return unsubscribe;
  }, []);

  const data = useMemo<Project[]>(() => getArchivedProjects(), [tick]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return data;
    return data.filter((p) => p.name.toLowerCase().includes(q) || (p.description ?? '').toLowerCase().includes(q));
  }, [data, query]);

  function handleRestore(project: Project) {
    restoreArchivedProject(project.id);
    setMenuOpenId(null);
    setTick((value) => value + 1);
  }

  function handleDelete(project: Project) {
    deleteArchivedProject(project.id);
    setMenuOpenId(null);
    setTick((value) => value + 1);
  }

  return (
    <section id="archived-projects" aria-labelledby="archived-projects-heading" className="scroll-mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="archived-projects-heading" className="text-lg font-semibold text-slate-900">
            Archived projects
          </h2>
          <p className="text-sm text-slate-500">Projects saved here are hidden from the active directory.</p>
        </div>
      </div>

      <div className="mt-4">
        {!data || data.length === 0 ? (
          <EmptyState
            title="No archived projects"
            description="Archive a project from the active list to keep it here."
          />
        ) : (
          <>
            <div className="mb-2 flex items-center justify-between gap-3">
              <label htmlFor="archived-project-search" className="sr-only">
                Search archived projects
              </label>
              <input
                id="archived-project-search"
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search archived projects"
                className="w-full max-w-xs rounded border border-slate-300 px-2 py-1.5 text-sm"
              />
              <span className="text-xs text-slate-500">
                {visible.length} of {data.length}
              </span>
            </div>
            {visible.length === 0 ? (
              <p className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-500">
                No archived project matches “{query.trim()}”.
              </p>
            ) : (
              <div
                role="region"
                aria-label="Archived projects list"
                tabIndex={0}
                className="max-h-96 overflow-y-auto overscroll-contain rounded border border-slate-200 bg-white"
              >
                <ul aria-label="Archived projects" className="divide-y divide-slate-200">
                  {visible.map((p) => (
                    <li key={p.id} className="flex items-stretch">
                      <div className="block flex-1 px-4 py-3">
                        <p className="font-medium text-slate-900">{p.name}</p>
                        {p.description && <p className="text-sm text-slate-500">{p.description}</p>}
                        {p.created_at && <p className="mt-0.5 text-xs text-slate-400">Archived {formatDate(p.created_at)}</p>}
                      </div>
                      <div className="relative flex items-center">
                        <button
                          type="button"
                          aria-label={`Archived project actions for ${p.name}`}
                          aria-expanded={menuOpenId === p.id}
                          onClick={() => setMenuOpenId((current) => (current === p.id ? null : p.id))}
                          className="flex h-full items-center px-3 text-lg font-bold text-slate-500 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
                        >
                          ⋮
                        </button>
                        {menuOpenId === p.id && (
                          <div className="absolute right-2 top-full z-10 mt-1 min-w-40 rounded border border-slate-200 bg-white p-1 shadow-lg">
                            <button
                              type="button"
                              onClick={() => handleRestore(p)}
                              className="block w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                            >
                              Restore
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(p)}
                              className="block w-full rounded px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
