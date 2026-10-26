import type { ProcessingRun, TreatyFiguresRequest } from '../../api/types';
import { TreatyFiguresForm } from '../../components/treaty/TreatyFiguresForm';
import { ErrorState } from '../../components/common/ErrorState';
import { fieldErrors, isApiError } from '../../api/errors';
import { useRunAction } from '../../hooks/useRunAction';
import { api } from '../../api/endpoints';
import { useQuery } from '@tanstack/react-query';
import { LoadingState } from '../../components/common/LoadingState';

/** Covers MAPPING_CONFIRMED and TREATY_FIGURES_PENDING - both show the treaty figures entry form. */
export function TreatyStep({ run }: { run: ProcessingRun }) {
  const derived = useQuery({
    queryKey: ['treaty-derived', run.id],
    queryFn: () => api.treaty.derived(run.id),
    staleTime: Infinity,
  });
  const submit = useRunAction(run.id, (body: TreatyFiguresRequest) => api.treaty.submit(run.id, body));

  return (
    <div className="space-y-4">
      {run.status === 'MAPPING_CONFIRMED' && (
        <p className="text-sm text-green-700">Mapping confirmed. Enter treaty figures to continue.</p>
      )}
      {submit.isError && !isApiError(submit.error) && <ErrorState error={submit.error} title="Submission failed" />}
      {submit.isError && isApiError(submit.error) && Object.keys(fieldErrors(submit.error)).length === 0 && (
        <ErrorState error={submit.error} title="Could not submit treaty figures" />
      )}
      {derived.isLoading ? (
        <LoadingState label="Reading currencies from the mapped file..." />
      ) : (
      <TreatyFiguresForm
        derived={derived.data ?? null}
        onSubmit={(body) => submit.mutate(body)}
        submitting={submit.isPending}
        serverFieldErrors={submit.isError ? fieldErrors(submit.error) : undefined}
      />
      )}
    </div>
  );
}
