import type { ApprovedMappingSummary, MappingCandidate } from '../api/types';

export interface MappingCoverage {
  mappedRequired: number;
  totalRequired: number;
  /** 0-1, or null if required fields are unknown (backend hasn't reported them). */
  percentage: number | null;
  missingRequired: string[];
  isComplete: boolean;
}

/**
 * A canonical field counts as "mapped" when some candidate or manual mapping
 * targeting it has been approved.
 */
export function computeMappingCoverage(
  candidates: MappingCandidate[],
  requiredFields: string[] | null,
  approvedMappings: ApprovedMappingSummary[] = [],
): MappingCoverage {
  if (!requiredFields) {
    return { mappedRequired: 0, totalRequired: 0, percentage: null, missingRequired: [], isComplete: false };
  }

  // Rejected / superseded candidates no longer count as "present in the file".
  const open = candidates.filter((c) => c.status === 'PROPOSED' || c.status === 'APPROVED');
  const candidateTargets = new Set(
    [...open.map((c) => c.target_field), ...approvedMappings.map((m) => m.target_field)].filter(
      (t): t is string => !!t,
    ),
  );
  const presentRequired = requiredFields.filter((field) => candidateTargets.has(field));
  const approvedTargets = new Set(
    [
      ...candidates.filter((c) => c.status === 'APPROVED').map((c) => c.target_field),
      ...approvedMappings.map((m) => m.target_field),
    ].filter((t): t is string => !!t),
  );
  const missingRequired = presentRequired.filter((field) => !approvedTargets.has(field));
  const totalRequired = presentRequired.length;
  const mappedRequired = totalRequired - missingRequired.length;

  return {
    mappedRequired,
    totalRequired,
    percentage: totalRequired > 0 ? mappedRequired / totalRequired : 1,
    missingRequired,
    isComplete: missingRequired.length === 0,
  };
}
