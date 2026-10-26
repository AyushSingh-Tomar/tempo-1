import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';

export function discrepanciesKey(runId: string | undefined) {
  return ['discrepancies', runId] as const;
}

export function useDiscrepancies(runId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: discrepanciesKey(runId),
    queryFn: () => api.discrepancies.list(runId as string),
    enabled: !!runId && enabled,
  });
}
