import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import type { FormatTemplateColumn } from '../api/types';

export const formatTemplatesKey = ['format-templates'] as const;

export function useFormatTemplates() {
  return useQuery({ queryKey: formatTemplatesKey, queryFn: () => api.formats.list() });
}

/** Creates a format, or - when ``id`` is given - replaces the name and columns of an existing one. */
export function useSaveFormatTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; name: string; columns: FormatTemplateColumn[] }) =>
      v.id ? api.formats.update(v.id, { name: v.name, columns: v.columns }) : api.formats.create({ name: v.name, columns: v.columns }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: formatTemplatesKey }),
  });
}

export function useDeleteFormatTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.formats.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: formatTemplatesKey }),
  });
}
