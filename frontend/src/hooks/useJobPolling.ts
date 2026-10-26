import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import type { JobStatus } from '../api/types';

const TERMINAL: JobStatus[] = ['SUCCEEDED', 'FAILED', 'CANCELLED'];

/** Polls a job until it reaches a terminal state. */
export function useJobPolling(jobId: string | null | undefined) {
  return useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => api.jobs.get(jobId as string),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return 2000;
      return TERMINAL.includes(job.status) ? false : 2000;
    },
  });
}
