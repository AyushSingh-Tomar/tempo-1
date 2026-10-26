import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import { useAuthToken } from '../stores/devAuth';

export const aiStatusKey = ['ai-status'] as const;
export const aiActivityKey = (runId: string | undefined) => ['ai-activity', runId] as const;

/** Whether AI is usable for the current user (their own key, the shared key, or none) and with which model. */
export function useAiStatus() {
  // Keyed by identity: the active key, and so availability, is per user.
  const token = useAuthToken();
  return useQuery({ queryKey: [...aiStatusKey, token], queryFn: () => api.ai.status(), staleTime: 60_000 });
}

/** Every AI call made for this run (status, reason, timing), newest first. */
export function useAiActivity(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: aiActivityKey(runId),
    queryFn: () => api.ai.activity(runId as string),
    enabled: !!runId && enabled,
  });
}
