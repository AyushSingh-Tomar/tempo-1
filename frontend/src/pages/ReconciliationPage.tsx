import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/shell/AppShell';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { DatasetBuilder } from '../components/reconciliation/DatasetBuilder';
import { RuleBuilder } from '../components/reconciliation/RuleBuilder';
import { RunHistory } from '../components/reconciliation/RunHistory';
import { useProject } from '../hooks/useProjects';
import { useReconDataset, useReconPermissions } from '../hooks/useRecon';
import type { DatasetKind } from '../api/reconTypes';

type TabId = 'bordereaux' | 'subledger' | 'rules' | 'results';
const TABS: Array<{ id: TabId; label: string }> = [
  { id: 'bordereaux', label: '1 Bordereaux' },
  { id: 'subledger', label: '2 Subledger' },
  { id: 'rules', label: '3 Rules & Run' },
  { id: 'results', label: '4 Results' },
];

function StatusChip({ kind, datasetId }: { kind: DatasetKind; datasetId: string | null }) {
  const { data } = useReconDataset(datasetId ?? undefined);
  const label = kind === 'BORDEREAUX' ? 'Bordereaux' : 'Subledger';
  let text = 'not started';
  let tone = 'bg-slate-100 text-slate-600';
  if (data?.status === 'DRAFT') {
    text = `draft (${data.files?.length ?? 0} file(s))`;
    tone = 'bg-amber-100 text-amber-800';
  } else if (data?.status === 'FINAL') {
    const years = data.report?.years ?? [];
    text = `FINAL - ${(data.row_count ?? 0).toLocaleString()} rows${years.length ? `, ${years[0]}${years.length > 1 ? `-${years[years.length - 1]}` : ''}` : ''}`;
    tone = 'bg-green-100 text-green-800';
  }
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${tone}`}>
      {label}: {text}
    </span>
  );
}

export function ReconciliationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const project = useProject(projectId);
  const { canCreate, role } = useReconPermissions();
  // Arriving from a finished processing run preselects its processed file as the bordereaux.
  const [params] = useSearchParams();
  const fromRun = params.get('run');
  const requestedTab = params.get('tab');
  const [tab, setTab] = useState<TabId>(TABS.some((t) => t.id === requestedTab) ? (requestedTab as TabId) : 'bordereaux');
  const [bId, setBId] = useState<string | null>(params.get('bordereaux'));
  const [sId, setSId] = useState<string | null>(null);

  if (!projectId) return null;

  function onKey(e: React.KeyboardEvent, idx: number) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const next = (idx + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length;
    setTab(TABS[next].id);
    (document.getElementById(`recon-tab-${TABS[next].id}`) as HTMLElement | null)?.focus();
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
          <Link to="/" className="hover:text-slate-700">Projects</Link> /{' '}
          <Link to={`/projects/${projectId}`} className="hover:text-slate-700">{project.data?.name ?? 'Project'}</Link> / <span className="text-slate-800">Reconciliation</span>
        </nav>
        <h1 className="mt-2 text-xl font-semibold text-slate-900">Reconciliation</h1>
        {fromRun && bId && (
          <p role="status" className="mt-2 rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            The processed file from{' '}
            <Link to={`/runs/${fromRun}`} className="font-medium underline">
              processing run {fromRun.slice(0, 8)}
            </Link>{' '}
            is ready as your final bordereaux. Add a subledger, then define the rules. You can still switch to a different
            bordereaux on the Bordereaux tab.
          </p>
        )}
        {project.isLoading && <LoadingState label="Loading project..." />}
        {project.error && <ErrorState error={project.error} title="Could not load project" onRetry={() => project.refetch()} />}

        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Dataset status">
          <StatusChip kind="BORDEREAUX" datasetId={bId} />
          <StatusChip kind="SUBLEDGER" datasetId={sId} />
          {!canCreate && <span className="text-xs text-slate-500">Read-only access ({role ?? 'unknown role'})</span>}
        </div>

        <div role="tablist" aria-label="Reconciliation steps" className="mt-4 flex gap-1 border-b border-slate-200">
          {TABS.map((t, i) => (
            <button
              key={t.id}
              id={`recon-tab-${t.id}`}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              aria-controls={`recon-panel-${t.id}`}
              tabIndex={tab === t.id ? 0 : -1}
              onClick={() => setTab(t.id)}
              onKeyDown={(e) => onKey(e, i)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-500 ${
                tab === t.id ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* All panels stay mounted so in-progress input survives tab switches. */}
        <div id="recon-panel-bordereaux" role="tabpanel" aria-labelledby="recon-tab-bordereaux" hidden={tab !== 'bordereaux'} className="mt-4">
          <DatasetBuilder projectId={projectId} kind="BORDEREAUX" datasetId={bId} onDatasetChange={setBId} canCreate={canCreate} />
        </div>
        <div id="recon-panel-subledger" role="tabpanel" aria-labelledby="recon-tab-subledger" hidden={tab !== 'subledger'} className="mt-4">
          <DatasetBuilder projectId={projectId} kind="SUBLEDGER" datasetId={sId} onDatasetChange={setSId} canCreate={canCreate} />
        </div>
        <div id="recon-panel-rules" role="tabpanel" aria-labelledby="recon-tab-rules" hidden={tab !== 'rules'} className="mt-4">
          <RuleBuilder
            projectId={projectId}
            preferredBordereauxId={bId}
            preferredSubledgerId={sId}
            canCreate={canCreate}
            onRunCreated={(runId) => navigate(`/projects/${projectId}/reconciliation/runs/${runId}`)}
          />
        </div>
        <div id="recon-panel-results" role="tabpanel" aria-labelledby="recon-tab-results" hidden={tab !== 'results'} className="mt-4">
          <RunHistory projectId={projectId} />
        </div>
      </div>
    </AppShell>
  );
}
