import type { ProcessingRun } from '../../api/types';
import { CleaningReview } from '../../components/cleaning/CleaningReview';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingState } from '../../components/common/LoadingState';
import { useCleaningResult } from '../../hooks/useCleaningResult';

export function CleaningStep({
  run,
  onAcknowledge,
  onRerun,
  acknowledging,
  rerunning,
}: {
  run: ProcessingRun;
  onAcknowledge: () => void;
  onRerun: (reason: string) => void;
  acknowledging: boolean;
  rerunning: boolean;
}) {
  const { data, isLoading, error, refetch } = useCleaningResult(run.id, run.status);

  if (isLoading) return <LoadingState label="Loading cleaning result..." />;
  if (error) return <ErrorState error={error} title="Could not load cleaning result" onRetry={() => refetch()} />;
  if (!data) return <LoadingState label="Waiting for cleaning result..." />;

  const alreadyAcknowledged = data.status === 'ACKNOWLEDGED';

  return (
    <CleaningReview
      result={data}
      onAcknowledge={onAcknowledge}
      onRerun={onRerun}
      isAcknowledging={acknowledging}
      isRerunning={rerunning}
      disabled={alreadyAcknowledged}
    />
  );
}
