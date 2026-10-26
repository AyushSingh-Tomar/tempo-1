import type { MappingCoverage } from '../../utils/mappingCoverage';

export function MappingCoverageBar({
  coverage,
  sourceMissingFields = [],
}: {
  coverage: MappingCoverage;
  sourceMissingFields?: string[];
}) {
  if (coverage.percentage === null) {
    return <p className="text-sm text-slate-500">Required-field coverage is not reported by the server yet.</p>;
  }
  const pct = Math.round(coverage.percentage * 100);
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">
          Required fields mapped: {coverage.mappedRequired} / {coverage.totalRequired}
        </span>
        <span className="text-slate-500">{pct}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Required field mapping coverage"
        className="mt-1 h-2 w-full rounded-full bg-slate-200"
      >
        <div
          className={`h-2 rounded-full ${coverage.isComplete ? 'bg-green-600' : 'bg-amber-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {!coverage.isComplete && (
        <div className="mt-1 space-y-1 text-xs text-amber-700">
          <p>Still unmapped: {coverage.missingRequired.join(', ')}</p>
          {sourceMissingFields.length > 0 && (
            <p className="text-amber-800">
              These required fields are not present in the uploaded bordereaux and cannot be mapped until the
              source file includes them.
            </p>
          )}
        </div>
      )}
      {sourceMissingFields.length > 0 && coverage.isComplete && (
        <div className="mt-1 text-xs text-amber-800">
          {sourceMissingFields.join(', ')} are not present in the uploaded bordereaux and will be treated as source
          gaps for this run.
        </div>
      )}
    </div>
  );
}
