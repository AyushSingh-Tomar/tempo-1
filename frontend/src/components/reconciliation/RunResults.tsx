import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/endpoints';
import type { GroupRecords, GroupStatus, ReconGroup, ReconRun, RuleResult } from '../../api/reconTypes';
import { describeFilter, filterAndSortGroups, formatAmount, formatPct } from '../../utils/recon';
import type { GroupSortKey, GroupView } from '../../utils/recon';
import { describeError } from '../../api/errors';
import { ErrorState } from '../common/ErrorState';
import { LoadingState } from '../common/LoadingState';
import { btnSecondary, inputCls } from './ui';

const STATUS_TONE: Record<string, string> = {
  MATCHED: 'bg-green-100 text-green-800',
  VARIANCE: 'bg-red-100 text-red-800',
  ONLY_IN_BORDEREAUX: 'bg-amber-100 text-amber-800',
  ONLY_IN_SUBLEDGER: 'bg-amber-100 text-amber-800',
  RECONCILED: 'bg-green-100 text-green-800',
  UNRECONCILED: 'bg-red-100 text-red-800',
};

export function ReconStatusBadge({ value }: { value: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_TONE[value] ?? 'bg-slate-100 text-slate-700'}`}>
      {value.replace(/_/g, ' ')}
    </span>
  );
}

const STATUSES: GroupStatus[] = ['MATCHED', 'VARIANCE', 'ONLY_IN_BORDEREAUX', 'ONLY_IN_SUBLEDGER'];

function RecordsPane({ runId, ruleId, side, keys }: { runId: string; ruleId: string; side: 'bordereaux' | 'subledger'; keys: string[] }) {
  const q = useQuery<GroupRecords>({
    queryKey: ['recon', 'records', runId, ruleId, side, keys],
    queryFn: () => api.recon.records(runId, ruleId, side, keys),
  });
  if (q.isLoading) return <LoadingState label={`Loading ${side} rows...`} />;
  if (q.error) return <ErrorState error={q.error} title={`Could not load ${side} rows`} onRetry={() => q.refetch()} />;
  const d = q.data;
  if (!d || d.rows.length === 0) return <p className="text-sm text-slate-500">No {side} rows in this group.</p>;
  return (
    <div>
      <p className="text-xs text-slate-500">Showing {d.rows.length} of {d.total.toLocaleString()} rows</p>
      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-full text-xs">
          <caption className="sr-only">{side} rows behind this group</caption>
          <thead className="bg-slate-50">
            <tr>{d.columns.map((c) => <th key={c} scope="col" className="px-2 py-1 text-left font-mono font-medium text-slate-600">{c}</th>)}</tr>
          </thead>
          <tbody>
            {d.rows.map((r, i) => (
              <tr key={i} className="border-t border-slate-100">
                {d.columns.map((c) => <td key={c} className="whitespace-nowrap px-2 py-1">{String(r[c] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GroupDrawer({ runId, rule, group, onClose }: { runId: string; rule: RuleResult; group: ReconGroup; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <aside role="dialog" aria-label={`Rows behind ${group.labels.join(' / ') || 'total'}`} className="fixed inset-y-0 right-0 z-40 w-full max-w-3xl overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-xl">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{rule.name}: {group.labels.join(' / ') || '(total)'}</h2>
          <ReconStatusBadge value={group.status} />
        </div>
        <button ref={closeRef} type="button" className={btnSecondary} onClick={onClose}>Close</button>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        <div><dt className="text-xs text-slate-500">Bordereaux</dt><dd>{formatAmount(group.bordereaux_value)}</dd></div>
        <div><dt className="text-xs text-slate-500">Subledger</dt><dd>{formatAmount(group.subledger_value)}</dd></div>
        <div><dt className="text-xs text-slate-500">Variance</dt><dd>{formatAmount(group.variance)}</dd></div>
        <div><dt className="text-xs text-slate-500">Variance %</dt><dd>{formatPct(group.variance_pct)}</dd></div>
      </dl>
      {((group.null_operands ?? 0) > 0 || (group.div_by_zero_rows ?? 0) > 0) && (
        <p className="mt-2 text-xs text-amber-800">
          {group.null_operands ? `${group.null_operands} blank operand(s) treated as empty. ` : ''}
          {group.div_by_zero_rows ? `${group.div_by_zero_rows} row(s) skipped for division by zero.` : ''}
        </p>
      )}
      <h3 className="mt-4 text-sm font-semibold">Bordereaux rows ({group.bordereaux_rows})</h3>
      <RecordsPane runId={runId} ruleId={rule.rule_id} side="bordereaux" keys={group.key} />
      <h3 className="mt-4 text-sm font-semibold">Subledger rows ({group.subledger_rows})</h3>
      <RecordsPane runId={runId} ruleId={rule.rule_id} side="subledger" keys={group.key} />
    </aside>
  );
}

function SortTh({ label, k, view, onSort, right }: { label: string; k: GroupSortKey; view: GroupView; onSort: (k: GroupSortKey) => void; right?: boolean }) {
  const active = view.sortKey === k;
  return (
    <th scope="col" aria-sort={active ? (view.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'} className={`px-3 py-2 font-medium text-slate-600 ${right ? 'text-right' : 'text-left'}`}>
      <button type="button" onClick={() => onSort(k)} className="hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500">
        {label}{active ? (view.sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  );
}

function RuleCard({ runId, rule, onOpen }: { runId: string; rule: RuleResult; onOpen: (g: ReconGroup) => void }) {
  const [view, setView] = useState<GroupView>({ status: 'ALL', search: '', sortKey: null, sortDir: 'desc' });
  const rows = filterAndSortGroups(rule.groups, view);
  function sort(k: GroupSortKey) {
    setView((v) => (v.sortKey === k ? { ...v, sortDir: v.sortDir === 'asc' ? 'desc' : 'asc' } : { ...v, sortKey: k, sortDir: k === 'label' ? 'asc' : 'desc' }));
  }
  const grainLabels = rule.grain;
  return (
    <section aria-label={`Rule ${rule.name}`} className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-slate-900">{rule.name}</h3>
        <ReconStatusBadge value={rule.status} />
      </div>
      <p className="mt-1 font-mono text-xs text-slate-600">{rule.expression}</p>
      <dl className="mt-2 grid gap-2 text-xs md:grid-cols-2">
        <div><dt className="text-slate-500">Bordereaux side</dt><dd className="font-mono">{rule.bordereaux_expression}</dd></div>
        <div><dt className="text-slate-500">Subledger side</dt><dd className="font-mono">{rule.subledger_expression}</dd></div>
      </dl>
      <dl className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
        <div className="rounded border border-slate-200 p-2"><dt className="text-xs text-slate-500">Bordereaux total</dt><dd className="font-medium tabular-nums">{formatAmount(rule.totals.bordereaux)}</dd></div>
        <div className="rounded border border-slate-200 p-2"><dt className="text-xs text-slate-500">Subledger total</dt><dd className="font-medium tabular-nums">{formatAmount(rule.totals.subledger)}</dd></div>
        <div className="rounded border border-slate-200 p-2"><dt className="text-xs text-slate-500">Variance</dt><dd className="font-medium tabular-nums">{formatAmount(rule.totals.variance)}</dd></div>
        <div className="rounded border border-slate-200 p-2"><dt className="text-xs text-slate-500">Variance %</dt><dd className="font-medium tabular-nums">{formatPct(rule.totals.variance_pct)}</dd></div>
        <div className="rounded border border-slate-200 p-2"><dt className="text-xs text-slate-500">Total within tolerance</dt><dd className="font-medium">{rule.totals.within_tolerance ? 'Yes' : 'No'}</dd></div>
      </dl>

      {rule.offsetting_differences && (
        <p role="alert" className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          Offsetting differences: the grand totals are within tolerance, but individual groups are not. Differences cancel each other out, so review the groups below.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2" role="group" aria-label="Filter groups by status">
        <button type="button" aria-pressed={view.status === 'ALL'} onClick={() => setView({ ...view, status: 'ALL' })} className={`rounded-full border px-2 py-0.5 text-xs ${view.status === 'ALL' ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white'}`}>
          All ({rule.groups.length})
        </button>
        {STATUSES.map((s) => (
          <button key={s} type="button" aria-pressed={view.status === s} onClick={() => setView({ ...view, status: s })} className={`rounded-full border px-2 py-0.5 text-xs ${view.status === s ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white'}`}>
            {s.replace(/_/g, ' ')} ({rule.counts[s] ?? 0})
          </button>
        ))}
        <label className="ml-auto text-xs text-slate-600">
          <span className="sr-only">Search groups</span>
          <input type="search" placeholder="Search groups..." value={view.search} onChange={(e) => setView({ ...view, search: e.target.value })} className={`${inputCls} w-48`} />
        </label>
      </div>

      {rule.groups.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No groups: no rows were in scope for this rule.</p>
      ) : rows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">No groups match the current filter.</p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Groups for {rule.name}; select a row to see the rows behind it</caption>
            <thead className="bg-slate-50">
              <tr>
                <SortTh label={grainLabels.join(' / ')} k="label" view={view} onSort={sort} />
                <SortTh label="Bordereaux" k="bordereaux_value" view={view} onSort={sort} right />
                <SortTh label="Subledger" k="subledger_value" view={view} onSort={sort} right />
                <SortTh label="Variance" k="variance" view={view} onSort={sort} right />
                <SortTh label="Variance %" k="variance_pct" view={view} onSort={sort} right />
                <SortTh label="Status" k="status" view={view} onSort={sort} />
                <SortTh label="B rows" k="bordereaux_rows" view={view} onSort={sort} right />
                <SortTh label="S rows" k="subledger_rows" view={view} onSort={sort} right />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((g, i) => (
                <tr
                  key={`${g.key.join('|')}-${i}`}
                  tabIndex={0}
                  onClick={() => onOpen(g)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(g); } }}
                  className="cursor-pointer hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500"
                  aria-label={`Open rows for ${g.labels.join(' / ') || 'total'}`}
                >
                  <td className="px-3 py-2">{g.labels.join(' / ') || '(total)'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatAmount(g.bordereaux_value)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatAmount(g.subledger_value)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatAmount(g.variance)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatPct(g.variance_pct)}</td>
                  <td className="px-3 py-2"><ReconStatusBadge value={g.status} /></td>
                  <td className="px-3 py-2 text-right tabular-nums">{g.bordereaux_rows}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{g.subledger_rows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <span className="sr-only">{runId}</span>
    </section>
  );
}

export function RunResults({ run }: { run: ReconRun }) {
  const [open, setOpen] = useState<{ rule: RuleResult; group: ReconGroup } | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const result = run.result;
  if (!result) return <p className="text-sm text-slate-500">This run has no stored result.</p>;
  const scope = result.rows_in_scope;
  const tol = result.tolerance;
  const gb = (result.group_by as Array<{ bordereaux?: string; subledger?: string; label?: string } | string>) ?? [];

  async function doExport() {
    setExporting(true);
    setExportError(null);
    try {
      await api.recon.exportCsv(run.id);
    } catch (e) {
      setExportError(describeError(e));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className={`rounded-md border p-4 ${result.status === 'RECONCILED' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-slate-900">{run.name || 'Reconciliation'}</h2>
          <div className="flex items-center gap-2">
            <ReconStatusBadge value={result.status} />
            <button type="button" className={btnSecondary} onClick={doExport} disabled={exporting}>{exporting ? 'Exporting...' : 'Export CSV'}</button>
          </div>
        </div>
        {exportError && <p role="alert" className="mt-1 text-sm text-red-700">{exportError}</p>}
        <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">Rows in scope</dt>
            <dd>
              Bordereaux {scope.bordereaux.toLocaleString()} of {scope.bordereaux_total.toLocaleString()}; Subledger {scope.subledger.toLocaleString()} of {scope.subledger_total.toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Compared by</dt>
            <dd>{gb.length ? gb.map((g) => (typeof g === 'string' ? g : g.label ?? g.bordereaux)).join(', ') : 'Grand total only'}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Tolerance</dt>
            <dd>
              {tol ? `${formatAmount(tol.absolute)} absolute ${tol.evaluation ?? 'OR'} ${formatPct(tol.percentage)}` : 'default'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Filters applied</dt>
            <dd>{result.filters?.length ? result.filters.map((f) => describeFilter(f)).join('; ') : 'None'}</dd>
          </div>
        </dl>
      </div>

      {result.rules.map((r) => (
        <RuleCard key={r.rule_id} runId={run.id} rule={r} onOpen={(g) => setOpen({ rule: r, group: g })} />
      ))}

      <details className="rounded border border-slate-200 bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">Run configuration (as submitted)</summary>
        <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(run.config, null, 2)}</pre>
        <p className="mt-1 text-xs text-slate-500">Bordereaux dataset {run.bordereaux_dataset_id}; subledger dataset {run.subledger_dataset_id}.</p>
      </details>

      {open && <GroupDrawer runId={run.id} rule={open.rule} group={open.group} onClose={() => setOpen(null)} />}
    </div>
  );
}
