import type { ProcessingRun } from '../../api/types';
import { MoneyRelationsEditor } from '../../components/relations/MoneyRelationsEditor';

/** TREATY_FIGURES_VALIDATED: declare the money-column relations, then run the checks on exactly that set. */
export function FinancialChecksStep({ run }: { run: ProcessingRun }) {
  return <MoneyRelationsEditor run={run} />;
}
