import { useAiActivity } from '../../hooks/useAi';
import { describeInteraction } from '../../utils/ai';
import { AiStatusBadge } from './AiStatusBadge';

const PURPOSE_LABEL: Record<string, string> = {
  MAPPING: 'Column mapping',
  MONEY_RELATIONS: 'Money-column relations',
};

/** Transparent log of every AI call made for the run: when, for what, and whether it helped. */
export function AiActivityPanel({ runId }: { runId: string }) {
  const { data, isLoading } = useAiActivity(runId);
  if (isLoading || !data) return null;
  const items = data.interactions;

  return (
    <details className="rounded border border-slate-200 bg-white p-3 text-sm" aria-label="AI activity for this run">
      <summary className="cursor-pointer font-medium text-slate-800">
        AI activity ({items.length})
        <span className="ml-2 text-xs font-normal text-slate-500">
          {data.ai.available ? `model ${data.ai.model ?? 'default'}` : (data.ai.reason ?? 'AI not available')}
        </span>
      </summary>
      {items.length === 0 ? (
        <p className="mt-2 text-slate-500">AI has not been asked anything for this run yet.</p>
      ) : (
        <ul className="mt-2 divide-y divide-slate-100">
          {items.map((i) => (
            <li key={i.id} className="py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-800">{PURPOSE_LABEL[i.purpose] ?? i.purpose}</span>
                <AiStatusBadge status={i.status} />
                <span className="text-xs text-slate-500">{i.created_at ? new Date(i.created_at).toLocaleTimeString() : ''}</span>
              </div>
              <p className="mt-0.5 text-slate-600">{i.message}</p>
              <p className="text-xs text-slate-400">{describeInteraction(i)}</p>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
