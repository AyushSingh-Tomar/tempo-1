import { Link } from 'react-router-dom';
import type { ProcessingRun } from '../../api/types';

export function FailedStep({ run }: { run: ProcessingRun }) {
  return (
    <div role="alert" className="space-y-3 rounded border border-red-200 bg-red-50 p-4 text-red-900">
      <p className="font-medium">This processing run failed.</p>
      <p className="text-sm">
        {run.failure_reason ?? run.error?.message ?? 'The server did not provide further detail about the failure.'}
      </p>
      {run.failed_from_status && <p className="text-xs text-red-700">Failed while in stage: {run.failed_from_status}</p>}
      <p className="text-sm">
        The source file and all prior decisions for this run remain preserved. Start a new run to try again.
      </p>
      <Link to={`/projects/${run.project_id}`} className="inline-block text-sm font-medium underline">
        Back to project
      </Link>
    </div>
  );
}
