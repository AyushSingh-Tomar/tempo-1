import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { ProcessingRun } from '../../api/types';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { TargetFormatChooser, type TargetFormatChoice } from '../../components/mapping/TargetFormatChooser';
import { MappingReviewPanel } from '../../components/mapping/MappingReviewPanel';
import { AiActivityPanel } from '../../components/ai/AiActivityPanel';
import { AiMappingOption } from '../../components/ai/AiMappingOption';
import { AiProgressBox } from '../../components/ai/AiProgressBox';
import { AiResultNotice } from '../../components/ai/AiResultNotice';
import { aiActivityKey, useAiActivity, useAiStatus } from '../../hooks/useAi';
import { api, jobIdFrom } from '../../api/endpoints';
import { describeError, isApiError } from '../../api/errors';
import { useJobPolling } from '../../hooks/useJobPolling';
import { mappingCandidatesKey, useMappingCandidates } from '../../hooks/useMappingCandidates';
import { useRunAction } from '../../hooks/useRunAction';
import { getAuthToken, parseDevToken } from '../../stores/devAuth';

function extractMissingFields(err: unknown): string[] | null {
  if (!isApiError(err)) return null;

  const fromMissingFields = err.details
    .flatMap((detail) => {
      const value = detail.missing_fields ?? detail.source_missing_fields;
      if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
      return [];
    })
    .filter(Boolean);
  if (fromMissingFields.length > 0) return fromMissingFields;

  const fromDetails = err.details
    .map((d) => (typeof d.field === 'string' ? d.field : null))
    .filter((f): f is string => !!f);
  if (fromDetails.length > 0) return fromDetails;
  const match = /unmapped[^:]*:\s*(.+)$/i.exec(err.message);
  if (match) return match[1].split(',').map((s) => s.trim()).filter(Boolean);
  return null;
}

export function MappingStep({ run }: { run: ProcessingRun }) {
  const queryClient = useQueryClient();
  const [generateJobId, setGenerateJobId] = useState<string | null>(null);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [finalizeMissing, setFinalizeMissing] = useState<string[] | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [useAi, setUseAi] = useState(true);

  const aiStatus = useAiStatus();
  const aiActivity = useAiActivity(run.id);
  const aiTimeout = aiStatus.data?.timeout_seconds ?? 60;
  const latestMappingAi = aiActivity.data?.interactions.find((i) => i.purpose === 'MAPPING');

  const devIdentity = parseDevToken(getAuthToken());
  const canApproveMappings = !!devIdentity && ['admin', 'project_owner', 'reviewer'].includes(devIdentity.role);

  const candidatesQuery = useMappingCandidates(run.id, true);
  const jobQuery = useJobPolling(generateJobId);

  const [changingFormat, setChangingFormat] = useState(false);

  // Choosing the target format (default dictionary or the user's own columns)
  // always precedes candidate generation; switching formats regenerates.
  const generate = useMutation({
    mutationFn: async (choice: TargetFormatChoice) => {
      await api.mappings.targetFormat.set(run.id, choice);
      return api.mappings.generate(run.id, { useAi });
    },
    onSuccess: (data) => {
      setChangingFormat(false);
      setActionError(null);
      void queryClient.invalidateQueries({ queryKey: aiActivityKey(run.id) });
      void queryClient.invalidateQueries({ queryKey: ['target-format', run.id] });
      const jobId = jobIdFrom(data);
      if (jobId) {
        setGenerateJobId(jobId);
      } else {
        void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) });
      }
    },
    onError: (err) => setActionError(describeError(err)),
  });

  // Once a generate job succeeds, refresh the candidate list.
  useEffect(() => {
    if (jobQuery.data?.status === 'SUCCEEDED' && generateJobId) {
      void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) });
      setGenerateJobId(null);
    }
  }, [jobQuery.data?.status, generateJobId, queryClient, run.id]);

  function withBusy<T>(id: string, fn: () => Promise<T>) {
    setBusyIds((s) => new Set(s).add(id));
    return fn().finally(() => {
      setBusyIds((s) => {
        const next = new Set(s);
        next.delete(id);
        return next;
      });
    });
  }

  const approve = useMutation({
    mutationFn: (id: string) => withBusy(id, () => api.mappings.approve(id)),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) }),
  });
  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => withBusy(id, () => api.mappings.reject(id, reason)),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) }),
  });
  const reopen = useMutation({
    mutationFn: (id: string) => withBusy(id, () => api.mappings.reopen(id)),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) }),
  });
  const approveExact = useMutation({
    mutationFn: () => api.mappings.approveExact(run.id),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) }),
  });
  const manual = useMutation({
    mutationFn: ({ sourceColumn, targetField }: { sourceColumn: string; targetField: string }) =>
      api.mappings.manual(run.id, { source_column: sourceColumn, target_field: targetField }),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) }),
  });
  // Re-ask the AI about the still-unresolved columns (e.g. after a timeout). A failure is a result, not an error.
  const retryAi = useMutation({
    mutationFn: () => api.mappings.aiAssist(run.id),
    onError: (err) => setActionError(describeError(err)),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: mappingCandidatesKey(run.id) });
      void queryClient.invalidateQueries({ queryKey: aiActivityKey(run.id) });
    },
  });
  const finalize = useRunAction(run.id, () => api.mappings.finalize(run.id));

  function handleFinalize() {
    setFinalizeMissing(null);
    setActionError(null);
    if (!canApproveMappings) {
      setActionError('You cannot confirm mappings with the current role. Switch to admin, project_owner, or reviewer to finalize mapping decisions.');
      return;
    }
    finalize.mutate(undefined, {
      onError: (err) => {
        setFinalizeMissing(extractMissingFields(err));
        setActionError(describeError(err));
      },
      onSuccess: () => {
        setFinalizeMissing(null);
        setActionError(null);
      },
    });
  }

  if (candidatesQuery.isLoading) return <LoadingState label="Loading mapping candidates..." />;
  if (candidatesQuery.error) {
    return <ErrorState error={candidatesQuery.error} title="Could not load mapping candidates" onRetry={() => candidatesQuery.refetch()} />;
  }

  const result = candidatesQuery.data;
  if (!result || result.candidates.length === 0 || changingFormat) {
    return (
      <>
        {actionError && (
          <div className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
            {actionError}
          </div>
        )}
        {generate.isPending && useAi && aiStatus.data?.available && (
          <div className="mb-4">
            <AiProgressBox
              title="Mapping columns - asking the AI about the ambiguous ones"
              detail="The rule-based mapping is computed first; the AI model is then asked about the columns the rules could not settle."
              timeoutSeconds={aiTimeout}
              model={aiStatus.data.model}
            />
          </div>
        )}
        <TargetFormatChooser
          runId={run.id}
          busy={generate.isPending || !!generateJobId}
          onConfirm={(choice) => generate.mutate(choice)}
          onCancel={changingFormat ? () => setChangingFormat(false) : undefined}
          aiOption={
            <AiMappingOption
              status={aiStatus.data}
              loading={aiStatus.isLoading}
              checked={useAi}
              onChange={setUseAi}
              disabled={generate.isPending}
            />
          }
        />
      </>
    );
  }

  return (
    <>
      {!canApproveMappings && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          This role cannot approve or finalize mappings. Switch to admin, project_owner, or reviewer to make changes.
        </div>
      )}
      {actionError && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
          {actionError}
        </div>
      )}
      <MappingReviewPanel
        result={result}
        onApprove={(id) => {
          if (!canApproveMappings) {
            setActionError('You cannot approve mappings with the current role. Switch to admin, project_owner, or reviewer.');
            return;
          }
          setActionError(null);
          approve.mutate(id);
        }}
        onReject={(id, reason) => {
          if (!canApproveMappings) {
            setActionError('You cannot reject mappings with the current role. Switch to admin, project_owner, or reviewer.');
            return;
          }
          setActionError(null);
          reject.mutate({ id, reason });
        }}
        onManualMap={(sourceColumn, targetField) => {
          setActionError(null);
          manual.mutate({ sourceColumn, targetField });
        }}
        onReopen={(id) => {
          setActionError(null);
          reopen.mutate(id);
        }}
        onApproveExact={() => {
          setActionError(null);
          approveExact.mutate();
        }}
        approvingExact={approveExact.isPending}
        onChangeFormat={() => setChangingFormat(true)}
        onConfirm={handleFinalize}
        busyIds={busyIds}
        confirming={finalize.isPending}
        finalizeError={finalizeMissing}
        canApproveMappings={canApproveMappings}
        aiBanner={
          retryAi.isPending ? (
            <AiProgressBox
              title="Asking the AI about the unresolved columns again"
              timeoutSeconds={aiTimeout}
              model={aiStatus.data?.model}
            />
          ) : (
            <div className="space-y-2">
              {latestMappingAi && (
                <AiResultNotice
                  interaction={latestMappingAi}
                  itemNoun="columns"
                  onRetry={canApproveMappings ? () => retryAi.mutate() : undefined}
                  retrying={retryAi.isPending}
                  continueHint="Review and approve the mapping below as usual - nothing depends on AI."
                />
              )}
              <AiActivityPanel runId={run.id} />
            </div>
          )
        }
      />
    </>
  );
}
