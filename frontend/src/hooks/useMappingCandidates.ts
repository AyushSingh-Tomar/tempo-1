import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';

export function mappingCandidatesKey(runId: string | undefined) {
  return ['mapping-candidates', runId] as const;
}

export function useMappingCandidates(runId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: mappingCandidatesKey(runId),
    queryFn: () => api.mappings.candidates(runId as string),
    enabled: !!runId && enabled,
  });
}
