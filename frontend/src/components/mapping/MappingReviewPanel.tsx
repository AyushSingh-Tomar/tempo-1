import { useMemo, type ReactNode } from 'react';
import type { CandidateListResult, MappingCandidate } from '../../api/types';
import { computeMappingCoverage } from '../../utils/mappingCoverage';
import { MappingCandidateRow } from './MappingCandidateRow';
import { MappingCoverageBar } from './MappingCoverageBar';

/** Groups candidates by source column so each column's primary + alternative candidates sit together. */
function groupBySourceColumn(candidates: MappingCandidate[]): Map<string, MappingCandidate[]> {
  const map = new Map<string, MappingCandidate[]>();
  for (const c of candidates) {
    const list = map.get(c.source_column) ?? [];
    list.push(c);
    map.set(c.source_column, list);
  }
  return map;
}

export function MappingReviewPanel({
  result,
  onApprove,
  onReject,
  onManualMap,
  onReopen,
  onApproveExact,
  approvingExact,
  onChangeFormat,
  onConfirm,
  busyIds,
  confirming,
  finalizeError,
  canApproveMappings,
  aiBanner,
}: {
  result: CandidateListResult;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
  onManualMap: (sourceColumn: string, targetField: string) => void;
  onReopen: (id: string) => void;
  onApproveExact: () => void;
  approvingExact: boolean;
  onChangeFormat: () => void;
  onConfirm: () => void;
  busyIds: Set<string>;
  confirming: boolean;
  finalizeError: string[] | null;
  canApproveMappings: boolean;
  /** What the AI did (or why it did not) for this mapping, with retry; rendered above the coverage bar. */
  aiBanner?: ReactNode;
}) {
  const grouped = useMemo(() => groupBySourceColumn(result.candidates), [result.candidates]);
  const coverage = useMemo(
    () => computeMappingCoverage(result.candidates, result.requiredFields, result.approvedMappings),
    [result.candidates, result.requiredFields, result.approvedMappings],
  );
  const sourceMissingFields = useMemo(() => {
    const open = result.candidates.filter((c) => c.status === 'PROPOSED' || c.status === 'APPROVED');
    const candidateTargets = new Set(
      [...open.map((c) => c.target_field), ...result.approvedMappings.map((m) => m.target_field)].filter(
        (t): t is string => !!t,
      ),
    );
    return (result.requiredFields ?? []).filter((field) => !candidateTargets.has(field));
  }, [result.approvedMappings, result.candidates, result.requiredFields]);

  // Primary row per source column: the approved mapping, else the best open
  // proposal, else whatever is left (e.g. only rejected candidates).
  const statusRank: Record<string, number> = { APPROVED: 3, PROPOSED: 2, REJECTED: 1, SUPERSEDED: 0 };
  const rows: { primary: MappingCandidate; alternatives: MappingCandidate[] }[] = [];
  for (const [, list] of grouped) {
    const sorted = [...list].sort(
      (a, b) => (statusRank[b.status] ?? 0) - (statusRank[a.status] ?? 0) || (b.confidence?.total ?? 0) - (a.confidence?.total ?? 0),
    );
    const primary = sorted[0];
    rows.push({ primary, alternatives: sorted.filter((c) => c.id !== primary.id) });
  }
  const exactOpen = result.candidates.filter(
    (c) => c.status === 'PROPOSED' && (c.confidence?.total ?? 0) >= 1,
  ).length;
  const fields = result.targetFormat?.fields ?? [];
  const formatLabel =
    result.targetFormat?.mode === 'CUSTOM'
      ? result.targetFormat.template
        ? `Saved format “${result.targetFormat.template.name}” (${fields.length} columns)`
        : `Your own columns (${fields.length})`
      : `Default data dictionary (${fields.length} columns)`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 bg-slate-50 p-3 text-sm">
        <span>
          <span className="font-medium text-slate-700">Target format:</span> {formatLabel}
        </span>
        <span className="flex items-center gap-3">
          {exactOpen > 0 && (
            <button
              type="button"
              onClick={onApproveExact}
              disabled={approvingExact || !canApproveMappings}
              className="rounded bg-green-700 px-3 py-1 text-xs font-medium text-white hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {approvingExact ? 'Approving...' : `Approve all 100% matches (${exactOpen})`}
            </button>
          )}
          <button type="button" onClick={onChangeFormat} className="text-xs font-medium text-slate-600 underline hover:text-slate-900">
            Change target format
          </button>
        </span>
      </div>

      {aiBanner}

      <MappingCoverageBar coverage={coverage} sourceMissingFields={sourceMissingFields} />

      {!!result.passthroughCount && result.passthroughCount > 0 && (
        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          <span className="font-medium">{result.passthroughCount} column(s)</span> did not match any target
          field and will be carried through unchanged as extra columns (not an error). Numeric ones are checked
          against premium relationships after treaty figures are entered.
        </div>
      )}

      {sourceMissingFields.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {sourceMissingFields.join(', ')} are not present in the uploaded bordereaux. They will be treated as
          source gaps, and you can continue with confirmation for the mapped fields that are actually in this file.
        </div>
      )}

      {finalizeError && finalizeError.length > 0 && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <p className="font-medium">Mapping could not be finalized.</p>
          {sourceMissingFields.length > 0 && (
            <p className="mt-1">
              These required fields are not present in the uploaded bordereaux and cannot be mapped until the
              source file includes them.
            </p>
          )}
          <p className="mt-1">These required fields are still unmapped:</p>
          <ul className="mt-1 list-disc pl-5">
            {finalizeError.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <div
        role="region"
        aria-label="Mapping candidates"
        tabIndex={0}
        className="max-w-full overflow-x-auto rounded-md border border-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
      >
        <table className="w-full min-w-[1155px] table-fixed divide-y divide-slate-200 text-sm">
          <colgroup>
            <col className="w-[140px]" />
            <col className="w-[170px]" />
            <col className="w-[100px]" />
            <col className="w-[145px]" />
            <col className="w-[120px]" />
            <col className="w-[220px]" />
            <col className="w-[260px]" />
          </colgroup>
          <thead className="bg-slate-50">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Source column
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Canonical field
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Confidence
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Sample values
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Status
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Evidence
              </th>
              <th scope="col" className="px-3 py-2 text-left font-medium text-slate-600">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {rows.map(({ primary, alternatives }) => (
              <MappingCandidateRow
                key={primary.id}
                candidate={primary}
                alternatives={alternatives}
                fields={fields}
                onApprove={onApprove}
                onReject={onReject}
                onReopen={onReopen}
                onManualMap={onManualMap}
                busyIds={busyIds}
              />
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={onConfirm}
        disabled={!coverage.isComplete || confirming || !canApproveMappings}
        className="rounded bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
      >
        {confirming ? 'Confirming...' : 'Confirm mappings'}
      </button>
      {!coverage.isComplete && coverage.totalRequired > 0 && (
        <p className="text-xs text-slate-500">
          Confirm is disabled until every required field has an approved mapping.
        </p>
      )}
    </div>
  );
}
