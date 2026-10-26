import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/endpoints';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => api.projects.list(),
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: () => api.projects.get(projectId as string),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) => api.projects.create(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; confirmName: string }) => api.projects.remove(v.id, v.confirmName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
}

/** Best-effort: the iteration-1 contract doesn't guarantee this endpoint exists yet. */
export function useProjectRuns(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'runs'],
    queryFn: () => api.projects.listRuns(projectId as string),
    enabled: !!projectId,
    retry: false,
  });
}
