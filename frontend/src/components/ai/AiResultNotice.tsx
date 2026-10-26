import type { AiInteraction } from '../../api/types';
import { AI_TONE_CLASSES, aiStatusMeta, describeInteraction } from '../../utils/ai';
import { AiStatusBadge } from './AiStatusBadge';

/**
 * What happened the last time AI was asked: used, not configured, timed out, limit reached ...
 * with the exact reason, and (when a retry could help) a retry button. Always says the flow
 * can continue without AI when it did not help.
 */
export function AiResultNotice({
  interaction,
  itemNoun = 'items',
  onRetry,
  retrying = false,
  continueHint = 'You can carry on without AI.',
}: {
  interaction: AiInteraction;
  itemNoun?: string;
  onRetry?: () => void;
  retrying?: boolean;
  continueHint?: string;
}) {
  const meta = aiStatusMeta(interaction.status);
  const tone = AI_TONE_CLASSES[meta.tone];
  const facts = describeInteraction(interaction, itemNoun);
  const helped = interaction.status === 'ok';

  return (
    <div className={`rounded-md border p-3 text-sm ${tone.box}`} role={meta.tone === 'danger' ? 'alert' : 'status'}>
      <div className="flex flex-wrap items-center gap-2">
        <AiStatusBadge status={interaction.status} />
        {facts && <span className="text-xs opacity-80">{facts}</span>}
      </div>
      <p className="mt-1.5">{interaction.message}</p>
      {!helped && interaction.status !== 'skipped' && <p className="mt-1 text-xs opacity-80">{continueHint}</p>}
      {onRetry && meta.retriable && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-2 rounded border border-current bg-white/70 px-3 py-1 text-xs font-medium hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {retrying ? 'Asking AI again...' : 'Try AI again'}
        </button>
      )}
    </div>
  );
}
