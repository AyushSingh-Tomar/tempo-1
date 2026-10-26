import type { AiInteraction } from '../api/types';

export type AiTone = 'success' | 'neutral' | 'warning' | 'danger';

export interface AiStatusMeta {
  /** Short pill text. */
  label: string;
  tone: AiTone;
  /** Whether trying the same AI call again could plausibly help. */
  retriable: boolean;
}

const META: Record<string, AiStatusMeta> = {
  ok: { label: 'AI used', tone: 'success', retriable: false },
  disabled: { label: 'AI not configured', tone: 'neutral', retriable: false },
  skipped: { label: 'AI not used', tone: 'neutral', retriable: false },
  timeout: { label: 'AI timed out', tone: 'warning', retriable: true },
  rate_limited: { label: 'AI limit reached', tone: 'warning', retriable: true },
  unavailable: { label: 'AI unavailable', tone: 'warning', retriable: true },
  bad_response: { label: 'AI reply unusable', tone: 'warning', retriable: true },
  auth_error: { label: 'AI key rejected', tone: 'danger', retriable: false },
  invalid_request: { label: 'AI request rejected', tone: 'danger', retriable: false },
  error: { label: 'AI error', tone: 'danger', retriable: true },
};

export function aiStatusMeta(status: string): AiStatusMeta {
  return META[status] ?? { label: `AI: ${status}`, tone: 'neutral', retriable: false };
}

export const AI_TONE_CLASSES: Record<AiTone, { box: string; pill: string }> = {
  success: { box: 'border-emerald-200 bg-emerald-50 text-emerald-900', pill: 'bg-emerald-100 text-emerald-800' },
  neutral: { box: 'border-slate-200 bg-slate-50 text-slate-700', pill: 'bg-slate-200 text-slate-700' },
  warning: { box: 'border-amber-300 bg-amber-50 text-amber-900', pill: 'bg-amber-100 text-amber-900' },
  danger: { box: 'border-red-200 bg-red-50 text-red-800', pill: 'bg-red-100 text-red-800' },
};

export function formatLatency(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** "gpt-5-mini · 14.3 s · 5 of 18 items" - the facts shown under an AI result. */
export function describeInteraction(i: AiInteraction, itemNoun = 'items'): string {
  const parts: string[] = [];
  if (i.model) parts.push(i.model);
  if (i.latency_ms > 0) parts.push(formatLatency(i.latency_ms));
  if (i.items_sent > 0) parts.push(`${i.items_resolved} of ${i.items_sent} ${itemNoun}`);
  return parts.join(' · ');
}
