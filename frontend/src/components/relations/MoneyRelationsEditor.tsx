import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import { describeError } from '../../api/errors';
import type { MoneyRelation, ProcessingRun, RelationSuggestResult, RelationSuggestion } from '../../api/types';
import { aiActivityKey, useAiStatus } from '../../hooks/useAi';
import { useRunAction } from '../../hooks/useRunAction';
import { ORIGIN_LABEL, labelResolver, missingTreatyFigures, relationText } from '../../utils/relations';
import { AiProgressBox } from '../ai/AiProgressBox';
import { AiResultNotice } from '../ai/AiResultNotice';
import { AiTag } from '../ai/AiStatusBadge';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { RelationForm, type RelationFormValue } from './RelationForm';

const workspaceKey = (runId: string) => ['money-relations', runId] as const;

const BTN =
  'rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50';

function OriginBadge({ origin }: { origin: string }) {
  if (origin === 'AI_SUGGESTED') return <AiTag title="Suggested by AI, accepted by you" />;
  return <span className="text-xs text-slate-500">{ORIGIN_LABEL[origin] ?? origin}</span>;
}

function AgreementBar({ value, rows }: { value: string; rows: number }) {
  const pct = Math.round(Number(value) * 100);
  return (
    <div className="mt-1 flex items-center gap-2 text-xs text-slate-600">
      <div className="h-1.5 w-24 overflow-hidden rounded bg-slate-200" aria-hidden="true">
        <div className={`h-full ${pct >= 90 ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${pct}%` }} />
      </div>
      <span>
        Holds on {pct}% of {rows} rows in your file
      </span>
    </div>
  );
}

/**
 * Step 7: the user declares how the money columns relate to each other, optionally with
 * deterministic standard relations or AI suggestions, then runs the financial checks on exactly that set.
 * AI is never required: every action except "Get AI suggestions" works without it.
 */
export function MoneyRelationsEditor({ run }: { run: ProcessingRun }) {
  const queryClient = useQueryClient();
  const aiStatus = useAiStatus();
  const aiTimeout = aiStatus.data?.timeout_seconds ?? 60;
  const workspace = useQuery({ queryKey: workspaceKey(run.id), queryFn: () => api.moneyRelations.workspace(run.id) });

  const [editing, setEditing] = useState<MoneyRelation | 'new' | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [standardNote, setStandardNote] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<RelationSuggestResult | null>(null);
  const [added, setAdded] = useState<Set<string>>(new Set());

  const refresh = () => void queryClient.invalidateQueries({ queryKey: workspaceKey(run.id) });

  const save = useMutation({
    mutationFn: (v: RelationFormValue) =>
      editing && editing !== 'new'
        ? api.moneyRelations.update(run.id, editing.id, { ...v, label: v.label || undefined })
        : api.moneyRelations.create(run.id, { ...v, label: v.label || undefined, origin: 'USER' }),
    onSuccess: () => {
      setEditing(null);
      setFormError(null);
      refresh();
    },
    onError: (err) => setFormError(describeError(err)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.moneyRelations.remove(run.id, id),
    onSuccess: refresh,
    onError: (err) => setActionError(describeError(err)),
  });
  const standard = useMutation({
    mutationFn: () => api.moneyRelations.addStandard(run.id),
    onSuccess: (r) => {
      setActionError(null);
      setStandardNote(
        r.added > 0
          ? `Added ${r.added} standard relation(s) for the columns in your file.`
          : 'The standard relations that fit your columns are already declared.',
      );
      if (r.skipped.length > 0) {
        setStandardNote(
          (n) => `${n} Left out (treaty figure missing): ${r.skipped.map((s) => s.expression).join('; ')}.`,
        );
      }
      refresh();
    },
    onError: (err) => setActionError(describeError(err)),
  });
  const suggest = useMutation({
    mutationFn: () => api.moneyRelations.aiSuggest(run.id),
    onSuccess: (r) => {
      setSuggestions(r);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: aiActivityKey(run.id) });
    },
    onError: (err) => setActionError(describeError(err)), // only a network-level failure; AI problems arrive as a result
  });
  const addSuggestion = useMutation({
    mutationFn: (s: RelationSuggestion) =>
      api.moneyRelations.create(run.id, {
        label: s.label,
        target_field: s.target_field,
        terms: s.terms,
        origin: 'AI_SUGGESTED',
        rationale: s.rationale,
      }),
    onSuccess: (_r, s) => {
      setAdded((a) => new Set(a).add(`${s.target_field}|${JSON.stringify(s.terms)}`));
      setActionError(null);
      refresh();
    },
    onError: (err) => setActionError(describeError(err)),
  });
  const runChecks = useRunAction(run.id, () => api.financialChecks.run(run.id));

  if (workspace.isLoading) return <LoadingState label="Reading the money columns of your file..." />;
  if (workspace.error || !workspace.data) {
    return <ErrorState error={workspace.error} title="Could not load the money columns" onRetry={() => workspace.refetch()} />;
  }

  const ws = workspace.data;
  const labelOf = labelResolver(ws.fields);
  const relations = ws.relations;
  const editable = ws.editable;

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm text-green-700">Treaty figures validated.</p>
        <h2 className="mt-1 text-base font-semibold text-slate-900">How do your money columns relate?</h2>
        <p className="mt-1 text-sm text-slate-600">
          Tell the system the relationships that should hold row by row, for example{' '}
          <span className="font-mono text-xs">Net = Gross − Commission − Tax</span> or{' '}
          <span className="font-mono text-xs">Commission = Gross × commission %</span>. The financial checks then test exactly
          these relations (tolerance ±{(Number(ws.tolerance) * 100).toFixed(1)}%) and list every row that breaks one in the
          discrepancy review. You can use columns from your file that matched no dictionary field.
        </p>
      </div>

      {/* ---- declared relations */}
      <section aria-labelledby="declared-heading" className="space-y-2">
        <h3 id="declared-heading" className="text-sm font-semibold text-slate-800">
          Declared Money Column Rules ({relations.length})
        </h3>
        {relations.length === 0 ? (
          <p className="rounded border border-dashed border-slate-300 p-3 text-sm text-slate-500">
            None yet. Add the standard relations, ask AI for suggestions, or declare your own. If you declare none, the
            built-in standard checks run instead.
          </p>
        ) : (
          <ul className="space-y-2">
            {relations.map((r) => {
              const missing = missingTreatyFigures(r.terms, ws.treaty_factors);
              return (
                <li key={r.id} className="rounded border border-slate-200 bg-white p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="break-words font-mono text-sm text-slate-900">
                        {relationText(r.target_field, r.terms, labelOf, ws.treaty_factors)}
                      </p>
                      <p className="mt-0.5 flex items-center gap-2">
                        <OriginBadge origin={r.origin} />
                        {r.rationale && <span className="text-xs text-slate-500">{r.rationale}</span>}
                      </p>
                      {missing.length > 0 && (
                        <p className="mt-1 text-xs text-amber-800">
                          Needs {missing.join(', ')}, which was not entered - this relation will be skipped. Redo the
                          treaty figures to add it.
                        </p>
                      )}
                    </div>
                    {editable && (
                      <div className="flex shrink-0 gap-3 text-xs">
                        <button
                          type="button"
                          onClick={() => {
                            setFormError(null);
                            setEditing(r);
                          }}
                          className="font-medium text-slate-700 underline"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => remove.mutate(r.id)}
                          disabled={remove.isPending}
                          className="font-medium text-red-700 underline disabled:opacity-50"
                        >
                          Remove
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ---- editor */}
      {editing && (
        <RelationForm
          key={editing === 'new' ? 'new' : editing.id}
          fields={ws.fields}
          treaty={ws.treaty_factors}
          initial={
            editing === 'new' ? undefined : { label: editing.label, target_field: editing.target_field, terms: editing.terms }
          }
          saving={save.isPending}
          error={formError}
          onSave={(v) => save.mutate(v)}
          onCancel={() => setEditing(null)}
        />
      )}

      {/* ---- actions */}
      {editable && !editing && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={BTN}
            onClick={() => {
              setFormError(null);
              setEditing('new');
            }}
          >
            + Declare a Money Column Rule
          </button>
          <button type="button" className={BTN} onClick={() => standard.mutate()} disabled={standard.isPending}>
            {/* {standard.isPending ? 'Adding...' : 'Add standard Money Column Rules'} */}
            {standard.isPending ? 'Viewing...' : 'View standard Money Column Rules'}
          </button>
          <button
            type="button"
            className={`${BTN} border-violet-300 text-violet-900 hover:bg-violet-50`}
            onClick={() => {
              setSuggestions(null);
              suggest.mutate();
            }}
            disabled={suggest.isPending || aiStatus.data?.available === false}
            title={aiStatus.data?.available === false ? (aiStatus.data.reason ?? 'AI is not available') : undefined}
          >
            {suggest.isPending ? 'Asking AI...' : 'Get AI suggestions'}
          </button>
        </div>
      )}
      {aiStatus.data && !aiStatus.data.available && (
        <p className="text-xs text-slate-500">
          AI suggestions are unavailable ({aiStatus.data.reason ?? 'not configured'}). Declaring relations and running the
          checks work exactly the same without it.
        </p>
      )}
      {standardNote && <p className="text-sm text-slate-600">{standardNote}</p>}
      {actionError && (
        <p role="alert" className="text-sm text-red-700">
          {actionError}
        </p>
      )}

      {/* ---- AI suggestions */}
      {suggest.isPending && (
        <AiProgressBox
          title="Asking the AI which of your money columns relate to each other"
          detail="It is shown the column names, your treaty figures and a sample of rows. Each proposal is then re-checked against all rows by the system."
          timeoutSeconds={aiTimeout}
          model={aiStatus.data?.model}
        />
      )}
      {suggestions && (
        <section aria-labelledby="ai-heading" className="space-y-2">
          <h3 id="ai-heading" className="text-sm font-semibold text-slate-800">
            AI suggestions
          </h3>
          <AiResultNotice
            interaction={suggestions.interaction}
            itemNoun="relations"
            onRetry={() => {
              setSuggestions(null);
              suggest.mutate();
            }}
            continueHint="Declare relations yourself or add the standard ones - the checks do not need AI."
          />
          {suggestions.suggestions.length > 0 && (
            <ul className="space-y-2">
              {suggestions.suggestions.map((s) => {
                const key = `${s.target_field}|${JSON.stringify(s.terms)}`;
                const done = added.has(key);
                return (
                  <li key={key} className="rounded border border-violet-200 bg-violet-50/50 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words font-mono text-sm text-slate-900">
                          <AiTag /> {relationText(s.target_field, s.terms, labelOf, ws.treaty_factors)}
                        </p>
                        {s.rationale && <p className="mt-0.5 text-xs text-slate-600">{s.rationale}</p>}
                        <AgreementBar value={s.agreement} rows={s.rows_evaluated} />
                      </div>
                      <button
                        type="button"
                        className={BTN}
                        disabled={done || addSuggestion.isPending}
                        onClick={() => addSuggestion.mutate(s)}
                      >
                        {done ? 'Added' : 'Add to my relations'}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {/* ---- run */}
      <div className="border-t border-slate-200 pt-4">
        {runChecks.isError && <ErrorState error={runChecks.error} title="Financial checks failed to run" />}
        <p className="mb-2 text-sm text-slate-600">
          {relations.length === 0
            ? 'No relations declared: the built-in standard checks will run.'
            : `${relations.length} relation(s) will be checked against every row. Findings go to the discrepancy review.`}
        </p>
        <button
          type="button"
          onClick={() => runChecks.mutate(undefined)}
          disabled={runChecks.isPending || !!editing}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
        >
          {runChecks.isPending ? 'Running financial checks...' : 'Run financial checks'}
        </button>
      </div>
    </div>
  );
}
