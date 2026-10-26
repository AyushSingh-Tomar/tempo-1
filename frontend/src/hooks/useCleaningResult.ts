import { useQuery } from '@tanstack/react-query';
import { api } from '../api/endpoints';
import type { ProcessingRun } from '../api/types';

const SHOWS_CLEANING_RESULT: ProcessingRun['status'][] = [
  'CLEANING_COMPLETED',
  'CLEANING_REVIEW_PENDING',
  'MAPPING_REVIEW_PENDING',
  'MAPPING_CONFIRMED',
  'TREATY_FIGURES_PENDING',
  'TREATY_FIGURES_VALIDATED',
  'FINANCIAL_CHECKS_COMPLETED',
  'DISCREPANCY_REVIEW_PENDING',
  'REPORT_GENERATION_PENDING',
  'COMPLETED',
];

export function useCleaningResult(runId: string | undefined, status: ProcessingRun['status'] | undefined) {
  const enabled = !!runId && !!status && SHOWS_CLEANING_RESULT.includes(status);
  return useQuery({
    queryKey: ['cleaning-result', runId],
    queryFn: () => api.cleaning.result(runId as string),
    enabled,
  });
}
