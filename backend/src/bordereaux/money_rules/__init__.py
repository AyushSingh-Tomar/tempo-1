"""Money Column Resolution (MCR) rule engine.

Deterministic implementation of ``Initial provided Info/Money-column-resolution-rules.docx``
(categories A-G, 25 rules). This is the shared engine behind two consumers:

- Mapping (Step 4 of the processing-run workflow): resolving which canonical
  field an ambiguous money column represents, using arithmetic/treaty-ratio
  evidence (``score_candidate_meanings``).
- Financial checks (Step 8): once columns are mapped, re-running the same
  rules per row to find discrepancies (``find_discrepancies``).

Nothing here touches the database or depends on pandas - it operates on plain
``Decimal`` dicts so it is trivially unit-testable against the rule document's
own worked examples (see ``backend/tests/unit/money_rules/``).
"""

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.engine import (
    DatasetEvaluation,
    evaluate_dataset,
    find_discrepancies,
    is_ambiguous,
    rank_candidate_roles,
)
from bordereaux.money_rules.rules import RuleOutcome, RULES
from bordereaux.money_rules.types import MoneyRole, MoneyRow, RuleResult, TreatyRates

__all__ = [
    "MCRConfig",
    "DatasetEvaluation",
    "evaluate_dataset",
    "find_discrepancies",
    "rank_candidate_roles",
    "is_ambiguous",
    "RuleOutcome",
    "RULES",
    "MoneyRole",
    "MoneyRow",
    "RuleResult",
    "TreatyRates",
]
