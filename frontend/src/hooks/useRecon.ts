import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import { parseDevToken, useAuthToken } from '../stores/devAuth';
import { canCreateRecon } from '../utils/recon';
import type { DatasetKind, FilePatch, FinalizeRequest, ReconRunRequest } from '../api/reconTypes';

export const reconKeys = {
  encodings: ['recon', 'encodings'] as const,
  datasets: (projectId: string | undefined, kind?: DatasetKind) => ['recon', 'datasets', projectId, kind ?? 'all'] as const,
  dataset: (id: string | undefined) => ['recon', 'dataset', id] as const,
  runs: (projectId: string | undefined) => ['recon', 'runs', projectId] as const,
  run: (id: string | undefined) => ['recon', 'run', id] as const,
};

/** Current dev identity's role and whether it may create/modify reconciliation data. */
export function useReconPermissions(): { role: string | null; canCreate: boolean } {
  const token = useAuthToken();
  const role = parseDevToken(token)?.role ?? null;
  return { role, canCreate: canCreateRecon(role) };
}

export function useEncodingOptions() {
  return useQuery({ queryKey: reconKeys.encodings, queryFn: () => api.recon.encodings(), staleTime: Infinity });
}

export function useReconDatasets(projectId: string | undefined, kind?: DatasetKind) {
  return useQuery({
    queryKey: reconKeys.datasets(projectId, kind),
    queryFn: () => api.recon.listDatasets(projectId as string, kind),
    enabled: !!projectId,
  });
}

export function useReconDataset(datasetId: string | undefined) {
  return useQuery({
    queryKey: reconKeys.dataset(datasetId),
    queryFn: () => api.recon.getDataset(datasetId as string),
    enabled: !!datasetId,
  });
}

export function useCreateReconDataset(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { kind: DatasetKind; name: string }) => api.recon.createDataset(projectId as string, body),
    onSuccess: (ds) => {
      qc.setQueryData(reconKeys.dataset(ds.id), ds);
      void qc.invalidateQueries({ queryKey: ['recon', 'datasets', projectId] });
    },
  });
}

export function useUploadReconFiles(datasetId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: {
      files: File[];
      encoding?: string;
      candidateEncodings?: string[];
      onProgress?: (pct: number) => void;
    }) =>
      api.recon.uploadFiles(
        datasetId as string,
        args.files,
        { encoding: args.encoding, candidateEncodings: args.candidateEncodings },
        args.onProgress,
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: reconKeys.dataset(datasetId) }),
  });
}

export function usePatchReconFile(datasetId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { fileId: string; patch: FilePatch }) => api.recon.patchFile(datasetId as string, args.fileId, args.patch),
    onSettled: () => qc.invalidateQueries({ queryKey: reconKeys.dataset(datasetId) }),
  });
}

export function useDeleteReconFile(datasetId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => api.recon.deleteFile(datasetId as string, fileId),
    onSettled: () => qc.invalidateQueries({ queryKey: reconKeys.dataset(datasetId) }),
  });
}

export function useEncodingCheck(datasetId: string | undefined) {
  return useMutation({
    mutationFn: (args: { fileId: string; candidates?: string[] }) =>
      api.recon.checkEncoding(datasetId as string, args.fileId, args.candidates),
  });
}

export function useSchemaSummary(datasetId: string | undefined) {
  return useMutation({
    mutationFn: (aliases: Record<string, string>) => api.recon.schemaSummary(datasetId as string, aliases),
  });
}

export function useFinalizeDataset(datasetId: string | undefined, projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: FinalizeRequest) => api.recon.finalize(datasetId as string, body),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: reconKeys.dataset(datasetId) });
      void qc.invalidateQueries({ queryKey: ['recon', 'datasets', projectId] });
    },
  });
}

export function useDatasetPreview(datasetId: string | undefined, enabled = true, limit = 25) {
  return useQuery({
    queryKey: ['recon', 'preview', datasetId, limit],
    queryFn: () => api.recon.preview(datasetId as string, limit),
    enabled: !!datasetId && enabled,
    staleTime: 60_000,
  });
}

export function useColumnValues(datasetId: string | undefined, column: string | undefined, q: string) {
  return useQuery({
    queryKey: ['recon', 'values', datasetId, column, q],
    queryFn: () => api.recon.columnValues(datasetId as string, column as string, q || undefined, 30),
    enabled: !!datasetId && !!column,
    staleTime: 60_000,
  });
}

export function useReconRuns(projectId: string | undefined) {
  return useQuery({
    queryKey: reconKeys.runs(projectId),
    queryFn: () => api.recon.listRuns(projectId as string),
    enabled: !!projectId,
  });
}

export function useReconRun(runId: string | undefined) {
  return useQuery({
    queryKey: reconKeys.run(runId),
    queryFn: () => api.recon.getRun(runId as string),
    enabled: !!runId,
  });
}

export function useCreateReconRun(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReconRunRequest) => api.recon.createRun(projectId as string, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: reconKeys.runs(projectId) }),
  });
}
