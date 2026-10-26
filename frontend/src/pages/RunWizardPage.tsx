import { useState } from 'react';
import { useParams } from 'react-router-dom';
import type { ProcessingRun } from '../api/types';
import { AppShell } from '../components/shell/AppShell';
import { RunStepperSidebar } from '../components/shell/RunStepperSidebar';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { api } from '../api/endpoints';
import { useRun } from '../hooks/useRun';
import { useRunAction } from '../hooks/useRunAction';
import { WIZARD_STEPS, currentStepIndex } from '../components/shell/steps';
import { FileStageStep } from './steps/FileStageStep';
import { CleaningStep } from './steps/CleaningStep';
import { MappingStep } from './steps/MappingStep';
import { TreatyStep } from './steps/TreatyStep';
import { FinancialChecksStep } from './steps/FinancialChecksStep';
import { DiscrepancyStep } from './steps/DiscrepancyStep';
import { ReportStep } from './steps/ReportStep';
import { FailedStep } from './steps/FailedStep';

export function RunWizardPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, error, refetch } = useRun(runId);
  const [rerunReason, setRerunReason] = useState<string | undefined>();

  const validate = useRunAction(runId, () => api.runs.validate(runId as string));
  const clean = useRunAction(runId, () => api.runs.clean(runId as string));
  const acknowledge = useRunAction(runId, () => api.cleaning.acknowledge(runId as string));
  const rerun = useRunAction(runId, (reason: string) => api.cleaning.rerun(runId as string, reason));

  if (isLoading) {
    return (
      <AppShell>
        <LoadingState label="Loading processing run..." />
      </AppShell>
    );
  }

  if (error || !run) {
    return (
      <AppShell>
        <ErrorState error={error} title="Could not load this processing run" onRetry={() => refetch()} />
      </AppShell>
    );
  }

  // Rebind to a fixed-type const: nested closures below don't retain the
  // `!isLoading && !error && run` narrowing from the guard clause above.
  const currentRun: ProcessingRun = run;

  const current = currentStepIndex(currentRun.status, currentRun.failed_from_status ?? currentRun.previous_status ?? null);
  const stepLabel = WIZARD_STEPS[current]?.label ?? currentRun.status;

  function renderStepContent() {
    const run = currentRun;
    switch (run.status) {
      case 'STARTED':
      case 'FILE_UPLOADED':
      case 'FILE_VALIDATED':
        return (
          <FileStageStep
            run={run}
            onValidate={() => validate.mutate(undefined)}
            onClean={() => clean.mutate(undefined)}
            validating={validate.isPending}
            cleaning={clean.isPending}
            error={validate.error ?? clean.error}
          />
        );
      case 'CLEANING_COMPLETED':
      case 'CLEANING_REVIEW_PENDING':
        return (
          <CleaningStep
            run={run}
            onAcknowledge={() => acknowledge.mutate(undefined)}
            onRerun={(reason) => {
              setRerunReason(reason);
              rerun.mutate(reason);
            }}
            acknowledging={acknowledge.isPending}
            rerunning={rerun.isPending}
          />
        );
      case 'MAPPING_REVIEW_PENDING':
        return <MappingStep run={run} />;
      case 'MAPPING_CONFIRMED':
      case 'TREATY_FIGURES_PENDING':
        return <TreatyStep run={run} />;
      case 'TREATY_FIGURES_VALIDATED':
        return <FinancialChecksStep run={run} />;
      case 'FINANCIAL_CHECKS_COMPLETED':
      case 'DISCREPANCY_REVIEW_PENDING':
        return <DiscrepancyStep run={run} />;
      case 'REPORT_GENERATION_PENDING':
      case 'COMPLETED':
        return <ReportStep run={run} />;
      case 'FAILED':
        return <FailedStep run={run} />;
      default:
        return <p className="text-sm text-slate-500">Unrecognised run status: {run.status}</p>;
    }
  }

  return (
    <AppShell sidebar={<RunStepperSidebar run={run} />}>
      <div
        className={
          run.status === 'MAPPING_REVIEW_PENDING'
            ? 'mx-auto w-full max-w-screen-2xl min-w-0'
            : 'mx-auto max-w-4xl'
        }
      >
        <div className="mb-4">
          <p className="text-xs font-mono text-slate-400">Run {run.id}</p>
          <h1 className="text-xl font-semibold text-slate-900">{stepLabel}</h1>
        </div>
        {rerun.isError && <ErrorState error={rerun.error} title="Rerun request failed" />}
        {rerunReason !== undefined && rerun.isSuccess && (
          <p className="mb-3 text-sm text-slate-500">Rerun requested: &ldquo;{rerunReason}&rdquo;</p>
        )}
        {renderStepContent()}
      </div>
    </AppShell>
  );
}
