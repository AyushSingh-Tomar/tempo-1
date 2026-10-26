import { AI_TONE_CLASSES, aiStatusMeta } from '../../utils/ai';

export function AiStatusBadge({ status }: { status: string }) {
  const meta = aiStatusMeta(status);
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${AI_TONE_CLASSES[meta.tone].pill}`}>
      {meta.label}
    </span>
  );
}

/** Small "AI" marker for items that came from (or were influenced by) the model. */
export function AiTag({ title = 'Suggested by AI' }: { title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700"
    >
      AI
    </span>
  );
}
