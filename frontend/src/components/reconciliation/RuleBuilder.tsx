import { useEffect, useMemo, useState } from 'react';
import type { GroupByPair, ReconFilter } from '../../api/reconTypes';
import {
  useCreateReconRun,
  useDatasetPreview,
  useReconDataset,
  useReconDatasets,
} from '../../hooks/useRecon';
import {
  buildRunRequest,
  findTreatyColumn,
  labelForPair,
  quickFiltersToFilters,
  suggestGroupBy,
  toggleValue,
  toleranceFromInput,
} from '../../utils/recon';
import type { QuickFilterState, RuleDraft, ToleranceInput } from '../../utils/recon';
import { LoadingState } from '../common/LoadingState';
import { EmptyState } from '../common/EmptyState';
import { FilterEditor, ValueInput } from './FilterEditor';
import { RulesEditor, newRuleDraft } from './RulesEditor';
import { ApiErrorBanner, Section, btnPrimary, btnSecondary, inputCls } from './ui';

function Chips({
  label,
  options,
  selected,
  onToggle,
  disabled,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (v: string) => void;
  disabled?: boolean;
}) {
  if (options.length === 0) return null;
  return (
    <div role="group" aria-label={label} className="flex flex-wrap items-center gap-1">
      <span className="mr-1 text-xs font-medium text-slate-600">{label}</span>
      {options.map((o) => {
        const on = selected.includes(o);
        return (
          <button
            key={o}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => onToggle(o)}
            className={`rounded-full border px-2 py-0.5 text-xs ${on ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}`}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}

export function RuleBuilder({
  projectId,
  preferredBordereauxId,
  preferredSubledgerId,
  canCreate,
  onRunCreated,
}: {
  projectId: string;
  preferredBordereauxId: string | null;
  preferredSubledgerId: string | null;
  canCreate: boolean;
  onRunCreated: (runId: string) => void;
}) {
  const bList = useReconDatasets(projectId, 'BORDEREAUX');
  const sList = useReconDatasets(projectId, 'SUBLEDGER');
  const finalB = (bList.data ?? []).filter((d) => d.status === 'FINAL');
  const finalS = (sList.data ?? []).filter((d) => d.status === 'FINAL');

  const [bId, setBId] = useState('');
  const [sId, setSId] = useState('');
  // Follow the datasets picked on the previous tabs while the user has not chosen explicitly here.
  useEffect(() => {
    if (preferredBordereauxId && finalB.some((d) => d.id === preferredBordereauxId)) setBId(preferredBordereauxId);
    else if (!bId && finalB.length === 1) setBId(finalB[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferredBordereauxId, bList.data]);
  useEffect(() => {
    if (preferredSubledgerId && finalS.some((d) => d.id === preferredSubledgerId)) setSId(preferredSubledgerId);
    else if (!sId && finalS.length === 1) setSId(finalS[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferredSubledgerId, sList.data]);

  const bDs = useReconDataset(bId || undefined);
  const sDs = useReconDataset(sId || undefined);
  const bPrev = useDatasetPreview(bId || undefined, true, 1);
  const sPrev = useDatasetPreview(sId || undefined, true, 1);
  const bCols = useMemo(() => bPrev.data?.columns ?? [], [bPrev.data]);
  const sCols = useMemo(() => sPrev.data?.columns ?? [], [sPrev.data]);
  const bNames = useMemo(() => bCols.map((c) => c.name), [bCols]);
  const sNames = useMemo(() => sCols.map((c) => c.name), [sCols]);

  const [name, setName] = useState('');
  const [rules, setRules] = useState<RuleDraft[]>(() => [newRuleDraft(1)]);
  const [groupBy, setGroupBy] = useState<GroupByPair[]>([]);
  const [filters, setFilters] = useState<ReconFilter[]>([]);
  const [quick, setQuick] = useState<QuickFilterState>({ years: [], quarters: [], periods: [] });
  const [treaty, setTreaty] = useState<string[]>([]);
  const [tol, setTol] = useState<ToleranceInput>({ absolute: '0.01', percentage: '0.1', evaluation: 'OR' });
  const [pairB, setPairB] = useState('');
  const [pairS, setPairS] = useState('');
  const [seededFor, setSeededFor] = useState('');

  const run = useCreateReconRun(projectId);

  // Pre-suggest the compare-by pairs once per dataset pair (the user can edit freely afterwards).
  const pairKey = `${bId}:${sId}`;
  useEffect(() => {
    if (bNames.length && sNames.length && seededFor !== pairKey) {
      const suggested = suggestGroupBy(bNames, sNames);
      setGroupBy(suggested.filter((g) => g.bordereaux === '_period'));
      setSeededFor(pairKey);
    }
  }, [bNames, sNames, pairKey, seededFor]);

  const suggestions = suggestGroupBy(bNames, sNames).filter(
    (s) => !groupBy.some((g) => g.bordereaux === s.bordereaux && g.subledger === s.subledger),
  );
  const treatyB = findTreatyColumn(bNames);
  const treatyS = findTreatyColumn(sNames);
  const reportB = bDs.data?.report;
  const reportS = sDs.data?.report;
  const years = Array.from(new Set([...(reportB?.years ?? []), ...(reportS?.years ?? [])])).sort().map(String);
  const quarters = ['Q1', 'Q2', 'Q3', 'Q4'];
  const periods = Array.from(new Set([...(reportB?.quarters ?? []), ...(reportS?.quarters ?? [])].map((q) => q.period))).sort();

  const treatyFilters: ReconFilter[] = treaty.length
    ? treatyB && treatyS && treatyB === treatyS
      ? [{ side: 'both', column: treatyB, op: 'in', values: treaty }]
      : [
          ...(treatyB ? [{ side: 'bordereaux' as const, column: treatyB, op: 'in' as const, values: treaty }] : []),
          ...(treatyS ? [{ side: 'subledger' as const, column: treatyS, op: 'in' as const, values: treaty }] : []),
        ]
    : [];
  const allFilters = [...quickFiltersToFilters(quick), ...treatyFilters, ...filters];

  const tolResult = toleranceFromInput(tol);
  const hasExpression = rules.some((r) => r.expression.trim());
  const ready = canCreate && !!bId && !!sId && hasExpression && !!tolResult.value;

  function submit() {
    if (!ready || !tolResult.value) return;
    const body = buildRunRequest({
      name,
      bordereauxId: bId,
      subledgerId: sId,
      rules,
      groupBy,
      filters: allFilters,
      tolerance: tolResult.value,
    });
    run.mutate(body, { onSuccess: (r) => onRunCreated(r.id) });
  }

  if (bList.isLoading || sList.isLoading) return <LoadingState label="Loading datasets..." />;
  if (finalB.length === 0 || finalS.length === 0) {
    return (
      <EmptyState
        title="Finalize a bordereaux and a subledger first"
        description={`Rules run against final datasets only. Still needed: ${[finalB.length === 0 ? 'a final bordereaux' : '', finalS.length === 0 ? 'a final subledger' : ''].filter(Boolean).join(' and ')}.`}
      />
    );
  }

  return (
    <div className="space-y-4">
      {!canCreate && (
        <p className="rounded border border-slate-200 bg-slate-50 p-2 text-sm text-slate-600">
          Your role is read-only for reconciliation, so you cannot start a run. You can still review previous results.
        </p>
      )}

      <Section step="1" title="Datasets">
        <div className="flex flex-wrap gap-4">
          <div>
            <label htmlFor="rb-b" className="block text-xs font-medium text-slate-600">Bordereaux (final)</label>
            <select id="rb-b" value={bId} onChange={(e) => setBId(e.target.value)} className={`${inputCls} mt-1 min-w-56`}>
              <option value="">Select...</option>
              {finalB.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="rb-s" className="block text-xs font-medium text-slate-600">Subledger (final)</label>
            <select id="rb-s" value={sId} onChange={(e) => setSId(e.target.value)} className={`${inputCls} mt-1 min-w-56`}>
              <option value="">Select...</option>
              {finalS.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="rb-name" className="block text-xs font-medium text-slate-600">Run name</label>
            <input id="rb-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q1 premium check" className={`${inputCls} mt-1 w-64`} />
          </div>
        </div>
        <ApiErrorBanner error={bPrev.error ?? sPrev.error} title="Could not load dataset columns" />
      </Section>

      <Section step="2" title="Rules" hint="Click a column to insert it where your cursor is in the focused expression.">
        {bPrev.isLoading || sPrev.isLoading ? (
          <LoadingState label="Loading columns..." />
        ) : (
          <RulesEditor
            rules={rules}
            onChange={setRules}
            bordereauxColumns={bCols}
            subledgerColumns={sCols}
            bordereauxName={bDs.data?.name}
            subledgerName={sDs.data?.name}
            disabled={!canCreate}
          />
        )}
      </Section>

      <Section step="3" title="Compare by (grain)" hint="Totals are compared per combination of these column pairs. Leave empty to compare one grand total.">
        {groupBy.length > 0 && (
          <ul className="mb-2 space-y-1" aria-label="Compare-by pairs">
            {groupBy.map((g, i) => (
              <li key={`${g.bordereaux}|${g.subledger}`} className="flex items-center gap-2 text-sm">
                <span className="font-mono">bordereaux.{g.bordereaux}</span> &harr; <span className="font-mono">subledger.{g.subledger}</span>
                <button type="button" className="text-xs text-slate-500 underline" disabled={!canCreate} onClick={() => setGroupBy(groupBy.filter((_, j) => j !== i))}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        {groupBy.length === 0 && <p className="mb-2 text-xs text-slate-500">No grain selected: one total per rule.</p>}
        {suggestions.length > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-1">
            <span className="text-xs text-slate-600">Suggested:</span>
            {suggestions.map((s) => (
              <button key={s.bordereaux} type="button" className={`${btnSecondary} px-2 py-0.5 text-xs`} disabled={!canCreate} onClick={() => setGroupBy([...groupBy, s])}>
                + {s.bordereaux}
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="gb-b" className="block text-xs font-medium text-slate-600">Bordereaux column</label>
            <select id="gb-b" value={pairB} onChange={(e) => setPairB(e.target.value)} className={`${inputCls} mt-1`} disabled={!canCreate}>
              <option value="">Select...</option>
              {bNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="gb-s" className="block text-xs font-medium text-slate-600">Subledger column</label>
            <select id="gb-s" value={pairS} onChange={(e) => setPairS(e.target.value)} className={`${inputCls} mt-1`} disabled={!canCreate}>
              <option value="">Select...</option>
              {sNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <button
            type="button"
            className={btnSecondary}
            disabled={!canCreate || !pairB || !pairS}
            onClick={() => {
              setGroupBy([...groupBy, { bordereaux: pairB, subledger: pairS, label: labelForPair(pairB, pairS) }]);
              setPairB('');
              setPairS('');
            }}
          >
            Add pair
          </button>
        </div>
      </Section>

      <Section step="4" title="Filters" hint="Only rows matching every filter are reconciled.">
        <div className="space-y-2">
          <Chips label="Year" options={years} selected={quick.years} onToggle={(v) => setQuick({ ...quick, years: toggleValue(quick.years, v) })} disabled={!canCreate} />
          <Chips label="Quarter" options={quarters} selected={quick.quarters} onToggle={(v) => setQuick({ ...quick, quarters: toggleValue(quick.quarters, v) })} disabled={!canCreate} />
          <Chips label="Period" options={periods} selected={quick.periods} onToggle={(v) => setQuick({ ...quick, periods: toggleValue(quick.periods, v) })} disabled={!canCreate} />
          {(treatyB || treatyS) && (
            <div>
              <span className="text-xs font-medium text-slate-600">Treaty ({[treatyB && `bordereaux.${treatyB}`, treatyS && `subledger.${treatyS}`].filter(Boolean).join(', ')})</span>
              <ValueInput datasetId={treatyB ? bId : sId} column={(treatyB ?? treatyS) as string} values={treaty} onChange={setTreaty} max={null} label="Treaty values" />
            </div>
          )}
        </div>
        <div className="mt-3">
          <FilterEditor
            filters={filters}
            onChange={setFilters}
            bordereauxId={bId || undefined}
            subledgerId={sId || undefined}
            bordereauxColumns={bNames}
            subledgerColumns={sNames}
            disabled={!canCreate}
          />
        </div>
      </Section>

      <Section step="5" title="Tolerance" hint="A group matches when its variance is within the absolute amount OR/AND the percentage.">
        <div className="flex flex-wrap items-start gap-4">
          <div>
            <label htmlFor="tol-abs" className="block text-xs font-medium text-slate-600">Absolute amount</label>
            <input id="tol-abs" inputMode="decimal" value={tol.absolute} disabled={!canCreate} onChange={(e) => setTol({ ...tol, absolute: e.target.value })} className={`${inputCls} mt-1 w-32`} aria-invalid={!!tolResult.errors.absolute} />
            {tolResult.errors.absolute && <p role="alert" className="text-xs text-red-700">{tolResult.errors.absolute}</p>}
          </div>
          <div>
            <label htmlFor="tol-pct" className="block text-xs font-medium text-slate-600">Percentage (%)</label>
            <input id="tol-pct" inputMode="decimal" value={tol.percentage} disabled={!canCreate} onChange={(e) => setTol({ ...tol, percentage: e.target.value })} className={`${inputCls} mt-1 w-32`} aria-invalid={!!tolResult.errors.percentage} />
            {tolResult.errors.percentage && <p role="alert" className="text-xs text-red-700">{tolResult.errors.percentage}</p>}
          </div>
          <div>
            <label htmlFor="tol-eval" className="block text-xs font-medium text-slate-600">Combine with</label>
            <select id="tol-eval" value={tol.evaluation} disabled={!canCreate} onChange={(e) => setTol({ ...tol, evaluation: e.target.value as 'OR' | 'AND' })} className={`${inputCls} mt-1`}>
              <option value="OR">OR (either is enough)</option>
              <option value="AND">AND (both must hold)</option>
            </select>
          </div>
        </div>
      </Section>

      <ApiErrorBanner error={run.error} title="The server could not run this reconciliation" />
      <div className="flex items-center gap-3">
        <button type="button" className={btnPrimary} disabled={!ready || run.isPending} onClick={submit}>
          {run.isPending ? 'Running...' : 'Run reconciliation'}
        </button>
        {!canCreate && <span className="text-xs text-slate-500">Read-only role: running is disabled.</span>}
        {canCreate && !ready && <span className="text-xs text-slate-500">Choose both datasets and enter at least one rule.</span>}
      </div>
    </div>
  );
}
