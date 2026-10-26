"""Financial checks module (Step 8-9): deterministic MCR discrepancy
detection against the treaty figures, reusing ``bordereaux.money_rules``."""

from bordereaux.financial_checks.service import (
    list_discrepancies,
    override_discrepancy,
    proceed_to_report_generation,
    run_financial_checks,
)

__all__ = [
    "run_financial_checks",
    "list_discrepancies",
    "override_discrepancy",
    "proceed_to_report_generation",
]
