import type { ProcessingRun } from '../../api/types';
import { WIZARD_STEPS, currentStepIndex, stepState } from './steps';

/**
 * Persistent sidebar reflecting `run.status`. Completed steps are checked,
 * the current step is highlighted, future steps are dimmed. Never assumes
 * progress - entirely derived from the run object re-fetched from the API.
 */
export function RunStepperSidebar({ run }: { run: ProcessingRun | undefined }) {
  const isFailed = run?.status === 'FAILED';
  const current = currentStepIndex(run?.status, run?.failed_from_status ?? run?.previous_status ?? null);

  return (
  <nav
    aria-label="Processing run progress"
    className="
      sticky top-12
      h-[calc(100vh-3rem)]
      w-64 shrink-0 self-start
      overflow-y-auto
      border-r border-slate-200
      bg-slate-50/70
      p-4
    "
  >
    <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
      Run steps
    </h2>

    <ol className="space-y-1">
      {WIZARD_STEPS.map((step, index) => {
        const state = stepState(index, current, isFailed);

        return (
          <li key={step.key}>
            <div
              aria-current={
                state === "active" ? "step" : undefined
              }
              className={[
                "flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm transition-colors",
                state === "active"
                  ? "bg-slate-900 text-white font-medium shadow-sm"
                  : "",
                state === "completed"
                  ? "text-slate-700"
                  : "",
                state === "upcoming"
                  ? "text-slate-400"
                  : "",
                state === "failed"
                  ? "bg-red-50 text-red-700 font-medium"
                  : "",
              ].join(" ")}
            >
              <span
                aria-hidden="true"
                className="mt-0.5 w-4 shrink-0 text-center"
              >
                {state === "completed" && "✓"}
                {state === "failed" && "✕"}
                {state === "active" && "●"}
                {state === "upcoming" && "○"}
              </span>

              <span>
                {step.label}
                {state === "completed" && (
                  <span className="sr-only"> (completed)</span>
                )}
                {state === "active" && (
                  <span className="sr-only"> (current step)</span>
                )}
                {state === "failed" && (
                  <span className="sr-only"> (failed here)</span>
                )}
              </span>
            </div>
          </li>
        );
      })}
    </ol>

    {isFailed && (
      <div
        role="alert"
        className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800"
      >
        This run failed. See the error details in the main panel.
      </div>
    )}
  </nav>
);
}


// -------Previous Nav Bar -------------------------//
// return (
//     <nav
//       aria-label="Processing run progress"
//       className="sticky top-12 max-h-[calc(100vh-3rem)] w-64 shrink-0 self-start overflow-y-auto border-r border-slate-200 bg-white p-4"
//     >
//       <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Run steps</h2>
//       <ol className="space-y-1">
//         {WIZARD_STEPS.map((step, index) => {
//           const state = stepState(index, current, isFailed);
//           return (
//             <li key={step.key}>
//               <div
//                 aria-current={state === 'active' ? 'step' : undefined}
//                 className={[
//                   'flex items-start gap-2 rounded px-2 py-1.5 text-sm',
//                   state === 'active' ? 'bg-slate-900 text-white font-medium' : '',
//                   state === 'completed' ? 'text-slate-700' : '',
//                   state === 'upcoming' ? 'text-slate-400' : '',
//                   state === 'failed' ? 'bg-red-50 text-red-700 font-medium' : '',
//                 ].join(' ')}
//               >
//                 <span aria-hidden="true" className="mt-0.5 w-4 shrink-0 text-center">
//                   {state === 'completed' && '✓'}
//                   {state === 'failed' && '✕'}
//                   {state === 'active' && '●'}
//                   {state === 'upcoming' && '○'}
//                 </span>
//                 <span>
//                   {step.label}
//                   {state === 'completed' && <span className="sr-only"> (completed)</span>}
//                   {state === 'active' && <span className="sr-only"> (current step)</span>}
//                   {state === 'failed' && <span className="sr-only"> (failed here)</span>}
//                 </span>
//               </div>
//             </li>
//           );
//         })}
//       </ol>
//       {isFailed && (
//         <div role="alert" className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-xs text-red-800">
//           This run failed. See the error details in the main panel.
//         </div>
//       )}
//     </nav>
//   );