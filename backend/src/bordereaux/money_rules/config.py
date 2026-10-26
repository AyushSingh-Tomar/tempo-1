"""Configurable MCR thresholds (rule doc §1.4). Not hardcoded in rule logic -
every call site takes an ``MCRConfig`` instance so tolerances can be re-tuned
without touching the rules themselves."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MCRConfig:
    """Default values are the rule document's own defaults (§1.4)."""

    tolerance: Decimal = Decimal("0.005")
    """±0.5%. Relative tolerance applied against the larger of the two
    compared magnitudes - absorbs rounding differences between figures that
    are supposed to represent the same thing."""

    row_agreement_threshold: Decimal = Decimal("0.90")
    """A rule is only treated as "in effect" for a column/dataset once it
    holds on at least this proportion of evaluated rows."""

    ambiguity_margin: Decimal = Decimal("0.05")
    """If the top two candidate meanings for a column score within this many
    percentage points of each other, the column is ambiguous - don't guess."""

    min_rows_for_resolution: int = 5
    """Below this row count there isn't enough data to resolve meaning with
    confidence; defer to human review instead."""

    discrepancy_agreement_threshold: Decimal = Decimal("0.50")
    """Reporting threshold for Step 8 findings. Once mapping is final and the
    treaty rates are user-entered, a treaty-anchored rule that holds on at
    least this share of rows is authoritative enough to flag the rows that
    break it. Lower than ``row_agreement_threshold`` (which gates *inferring
    what a column means*) so a file with many bad rows is not silently
    exempted by its own bad rows."""
