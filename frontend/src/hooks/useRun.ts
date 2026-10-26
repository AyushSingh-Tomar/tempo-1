import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import type { ProcessingRun } from '../api/types';

export function runQueryKey(runId: string | undefined) {
  return ['run', runId] as const;
}

/**
 * The single source of truth for a run's state in the UI. Every mutation
 * hook invalidates this query instead of optimistically mutating the run,
 * per the rule that the UI must reflect the backend's actual status.
 */
export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: runQueryKey(runId),
    queryFn: () => api.runs.get(runId as string),
    enabled: !!runId,
    // Statuses that mean "a background job may still be mutating this run"
    // are refetched periodically; otherwise there is no point polling.
    refetchInterval: (query) => {
      const run = query.state.data as ProcessingRun | undefined;
      if (!run) return false;
      return run.status === 'STARTED' ? 1500 : false;
    },
  });
}

export function useInvalidateRun(runId: string | undefined) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: runQueryKey(runId) });
}
