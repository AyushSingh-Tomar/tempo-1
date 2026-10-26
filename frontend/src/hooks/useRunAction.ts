import { useMutation, useQueryClient } from '@tanstack/react-query';
import { isInvalidTransition } from '../api/errors';
import { runQueryKey } from './useRun';

/**
 * Wraps any action that is supposed to advance a processing run's status.
 * Per the integration contract: never assume a transition succeeded on the
 * client. After every attempt (success OR a 409 INVALID_RUN_TRANSITION) we
 * invalidate the run query so the UI re-fetches the authoritative status
 * from the backend and re-renders accordingly.
 */
export function useRunAction<TArgs, TResult>(runId: string | undefined, mutationFn: (args: TArgs) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: (_data, error) => {
      // Refetch on both success (status advanced) and invalid-transition
      // conflicts (status is not what we assumed) - and on other errors too,
      // since the action may have partially applied server-side.
      void queryClient.invalidateQueries({ queryKey: runQueryKey(runId) });
      if (error && !isInvalidTransition(error)) {
        // Non-transition errors still get the run refreshed above; nothing
        // further to do here, but keep the branch for clarity/extension.
      }
    },
  });
}
