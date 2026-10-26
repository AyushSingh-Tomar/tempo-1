/**
 * Pure logic describing the 12-step wizard and how a `ProcessingRun.status`
 * (one of the 14 backend-enforced states) maps onto it. Kept separate from
 * the React component so it can be unit-tested without rendering.
 */
import type { RunStatus } from '../../api/types';

export interface WizardStep {
  key: string;
  label: string;
  description: string;
  /** Backend statuses that correspond to "the run is at this step". */
  statuses: RunStatus[];
}

export const WIZARD_STEPS: WizardStep[] = [
  { key: 'upload', label: 'Upload', description: 'Upload the source file', statuses: ['STARTED', 'FILE_UPLOADED'] },
  { key: 'validate', label: 'Validate', description: 'Validate file structure', statuses: ['FILE_VALIDATED'] },
  {
    key: 'clean',
    label: 'Clean & Standardize',
    description: 'Apply deterministic cleaning rules',
    statuses: ['CLEANING_COMPLETED'],
  },
  {
    key: 'cleaning_review',
    label: 'Review Changes',
    description: 'Review and acknowledge cleaning results',
    statuses: ['CLEANING_REVIEW_PENDING'],
  },
  {
    key: 'mapping_review',
    label: 'Map Columns',
    description: 'Review proposed column mappings',
    statuses: ['MAPPING_REVIEW_PENDING'],
  },
  {
    key: 'mapping_confirmed',
    label: 'Confirm Mapping',
    description: 'Mapping confirmed, proceed to treaty figures',
    statuses: ['MAPPING_CONFIRMED'],
  },
  {
    key: 'treaty_figures',
    label: 'Treaty Figures',
    description: 'Enter treaty figures',
    statuses: ['TREATY_FIGURES_PENDING'],
  },
  {
    key: 'treaty_validated',
    label: 'Validate Figures',
    description: 'Treaty figures validated',
    statuses: ['TREATY_FIGURES_VALIDATED'],
  },
  {
    key: 'financial_checks',
    label: 'Financial Checks',
    description: 'Money-column rules applied',
    statuses: ['FINANCIAL_CHECKS_COMPLETED'],
  },
  {
    key: 'discrepancy_review',
    label: 'Review Discrepancies',
    description: 'Review and resolve discrepancies',
    statuses: ['DISCREPANCY_REVIEW_PENDING'],
  },
  {
    key: 'report_generation',
    label: 'Generate Reports',
    description: 'Generate processed file and audit report',
    statuses: ['REPORT_GENERATION_PENDING'],
  },
  { key: 'completed', label: 'Completed', description: 'Download artifacts', statuses: ['COMPLETED'] },
];

export type StepState = 'completed' | 'active' | 'upcoming' | 'failed';

/**
 * Index of the step a given status belongs to, or -1 if unknown (defensive
 * default for a status the frontend doesn't recognise yet).
 */
export function stepIndexForStatus(status: RunStatus | string | null | undefined): number {
  if (!status) return -1;
  return WIZARD_STEPS.findIndex((s) => s.statuses.includes(status as RunStatus));
}

/**
 * Resolves the "current" step index for a run. FAILED is not itself a step;
 * it fails *from* some step, so we fall back to `failedFromStatus` /
 * `previousStatus` to anchor the sidebar.
 */
export function currentStepIndex(
  status: RunStatus | string | null | undefined,
  failedFromStatus?: RunStatus | string | null,
): number {
  if (status === 'FAILED') {
    const idx = stepIndexForStatus(failedFromStatus ?? null);
    return idx === -1 ? 0 : idx;
  }
  return stepIndexForStatus(status);
}

export function stepState(index: number, currentIndex: number, isFailed: boolean): StepState {
  if (isFailed && index === currentIndex) return 'failed';
  if (index < currentIndex) return 'completed';
  if (index === currentIndex) return 'active';
  return 'upcoming';
}
