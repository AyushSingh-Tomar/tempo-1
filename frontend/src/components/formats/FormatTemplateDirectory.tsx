import { useState } from 'react';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { FormatTemplateEditor } from './FormatTemplateEditor';
import { useDeleteFormatTemplate, useFormatTemplates, useSaveFormatTemplate } from '../../hooks/useFormatTemplates';
import { describeError } from '../../api/errors';
import { useDevRole } from '../../stores/devAuth';
import type { FormatTemplate } from '../../api/types';

const WRITE_ROLES = ['admin', 'project_owner', 'analyst'];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString();
}

/**
 * The directory of saved final formats. Anyone can read it; analysts, project owners and
 * admins can add a format, change one (rename it, add/remove/rename columns, change
 * recognised terms) or remove one. Runs that already used a format keep their own copy.
 */
export function FormatTemplateDirectory() {
  const { data, isLoading, error, refetch } = useFormatTemplates();
  const save = useSaveFormatTemplate();
  const remove = useDeleteFormatTemplate();
  const role = useDevRole();
  const canWrite = !!role && WRITE_ROLES.includes(role);

  const [editing, setEditing] = useState<FormatTemplate | 'new' | null>(null);
  const [toDelete, setToDelete] = useState<FormatTemplate | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function startEditing(target: FormatTemplate | 'new') {
    save.reset();
    setEditing(target);
  }

  return (
    <section id="formats" aria-labelledby="formats-heading" className="scroll-mt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="formats-heading" className="text-lg font-semibold text-slate-900">
            Final formats
          </h2>
          <p className="text-sm text-slate-500">
            Saved lists of final columns and the terms that identify them. Pick one when you map a file.
          </p>
        </div>
        {canWrite && (
          <button
            type="button"
            onClick={() => startEditing('new')}
            disabled={editing !== null}
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            New format
          </button>
        )}
      </div>

      {editing !== null && (
        <div className="mt-4">
          <FormatTemplateEditor
            key={editing === 'new' ? 'new' : editing.id}
            initial={editing === 'new' ? null : editing}
            busy={save.isPending}
            error={save.isError ? save.error : null}
            onCancel={() => setEditing(null)}
            onSave={(body) =>
              save.mutate({ id: editing === 'new' ? undefined : editing.id, ...body }, { onSuccess: () => setEditing(null) })
            }
          />
        </div>
      )}

      <div className="mt-4">
        {isLoading && <LoadingState label="Loading formats..." />}
        {error && !isLoading && <ErrorState error={error} title="Could not load formats" onRetry={() => refetch()} />}
        {!isLoading && !error && (!data || data.length === 0) && editing === null && (
          <EmptyState
            title="No saved formats yet"
            description={
              canWrite
                ? 'Add a format to reuse the same final columns and recognised terms on every file.'
                : 'Nothing has been saved yet.'
            }
            action={
              canWrite ? (
                <button
                  type="button"
                  onClick={() => startEditing('new')}
                  className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                >
                  Add your first format
                </button>
              ) : undefined
            }
          />
        )}
        {!isLoading && !error && data && data.length > 0 && (
          <div
            role="region"
            aria-label="Final formats list"
            tabIndex={0}
            className="max-h-96 overflow-y-auto overscroll-contain rounded border border-slate-200 bg-white"
          >
            <ul aria-label="Final formats" className="divide-y divide-slate-200">
              {data.map((t) => (
                <li key={t.id} className="px-4 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-slate-900">{t.name}</p>
                      <p className="text-xs text-slate-500">
                        {t.column_count} column(s) · {t.term_count} recognised term(s)
                        {t.updated_at ? ` · updated ${formatDate(t.updated_at)}` : ''}
                      </p>
                    </div>
                    {canWrite && (
                      <div className="flex items-center gap-3 text-sm">
                        <button
                          type="button"
                          aria-label={`Change format ${t.name}`}
                          onClick={() => startEditing(t)}
                          className="font-medium text-slate-700 underline hover:text-slate-900"
                        >
                          Change
                        </button>
                        <button
                          type="button"
                          aria-label={`Remove format ${t.name}`}
                          onClick={() => {
                            setDeleteError(null);
                            setToDelete(t);
                          }}
                          className="font-medium text-red-700 underline hover:text-red-900"
                        >
                          Remove
                        </button>
                      </div>
                    )}
                  </div>
                  <details className="mt-1 text-xs text-slate-600">
                    <summary className="cursor-pointer font-medium">Show columns and terms</summary>
                    <ul className="mt-1 space-y-0.5">
                      {t.columns.map((c) => (
                        <li key={c.name}>
                          <span className="font-medium text-slate-800">{c.name}</span>
                          {c.terms.length > 0 && <span className="text-slate-500"> — {c.terms.join(', ')}</span>}
                        </li>
                      ))}
                    </ul>
                  </details>
                  {toDelete?.id === t.id && (
                    <div role="alertdialog" aria-label={`Remove ${t.name}?`} className="mt-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                      <p>
                        Remove <span className="font-medium">{t.name}</span> from the directory? Runs that already used it keep
                        their own copy and are not affected.
                      </p>
                      {deleteError && (
                        <p role="alert" className="mt-1">
                          {deleteError}
                        </p>
                      )}
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          disabled={remove.isPending}
                          onClick={() =>
                            remove.mutate(t.id, {
                              onSuccess: () => {
                                setToDelete(null);
                                if (editing !== null && editing !== 'new' && editing.id === t.id) setEditing(null);
                              },
                              onError: (err) => setDeleteError(describeError(err)),
                            })
                          }
                          className="rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800 disabled:opacity-50"
                        >
                          {remove.isPending ? 'Removing...' : 'Remove format'}
                        </button>
                        <button
                          type="button"
                          disabled={remove.isPending}
                          onClick={() => setToDelete(null)}
                          className="rounded border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                        >
                          Keep it
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {!canWrite && data && data.length > 0 && (
          <p className="mt-2 text-xs text-slate-400">Your role can use saved formats but not change them.</p>
        )}
      </div>
    </section>
  );
}
