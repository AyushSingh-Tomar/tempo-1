"""Request/response schemas for Step 6 (treaty figures) of the processing-run
workflow. Percentages are **fractions** (0.25, not 25) - the same convention
``bordereaux.money_rules.TreatyRates`` uses, so no conversion happens between
storage and the rule engine. Rejecting an out-of-range value here, rather
than silently reinterpreting "25" as "0.25", matches ADR-002/§5 of
OPEN_QUESTIONS.md ("do not silently accept financial differences")."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_PCT_DESCRIPTION = "Fraction between 0 and 1 (25% is entered as 0.25, not 25)."


class FxRateEntry(BaseModel):
    """1 unit of ``currency`` = ``rate`` units of the settlement currency."""

    currency: str = Field(..., min_length=3, max_length=3)
    rate: Decimal
    source: Literal["FILE", "USER"] = "USER"

    @field_validator("currency")
    @classmethod
    def _upper_alpha(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isalpha() or len(value) != 3:
            raise ValueError("currency must be a 3-letter ISO code")
        return value

    @field_validator("rate")
    @classmethod
    def _rate_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError(f"rate must be > 0, got {value}")
        return value


class TreatyFiguresRequest(BaseModel):
    commission_pct: Decimal = Field(..., description=_PCT_DESCRIPTION)
    tax_pct: Decimal = Field(..., description=_PCT_DESCRIPTION)
    cession_pct: Decimal = Field(..., description=_PCT_DESCRIPTION)
    brokerage_pct: Decimal | None = Field(None, description=_PCT_DESCRIPTION)
    order_pct: Decimal | None = Field(None, description=_PCT_DESCRIPTION)
    fx_rate: Decimal | None = Field(None, description="Settlement-currency rate; must be > 0 if provided.")
    currency: str | None = Field(None, max_length=16)
    settlement_currency: str | None = Field(None, min_length=3, max_length=3)
    expected_si_rate: Decimal | None = Field(
        None, description="Technical premium rate on sum insured as a fraction (5% = 0.05). Optional."
    )
    fx_rates: list[FxRateEntry] = Field(default_factory=list)
    effective_from: date | None = None
    effective_to: date | None = None

    @field_validator("expected_si_rate")
    @classmethod
    def _si_rate_range(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not (Decimal(0) < value < Decimal(1)):
            raise ValueError(f"Expected a fraction between 0 and 1 (e.g. 0.05 for 5%), got {value}")
        return value

    @field_validator("settlement_currency")
    @classmethod
    def _settlement_upper(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value.isalpha():
            raise ValueError("settlement_currency must be a 3-letter ISO code")
        return value

    @model_validator(mode="after")
    def _unique_currencies(self) -> "TreatyFiguresRequest":
        seen: set[str] = set()
        for entry in self.fx_rates:
            if entry.currency in seen:
                raise ValueError(f"Duplicate FX rate for {entry.currency}")
            seen.add(entry.currency)
        return self

    @field_validator("commission_pct", "tax_pct", "cession_pct", "brokerage_pct", "order_pct")
    @classmethod
    def _pct_in_range(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if not (Decimal(0) <= value <= Decimal(1)):
            raise ValueError(
                f"Expected a fraction between 0 and 1 (e.g. 0.25 for 25%), got {value}. "
                "If you meant 25%, enter 0.25."
            )
        return value

    @field_validator("fx_rate")
    @classmethod
    def _fx_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError(f"fx_rate must be > 0, got {value}")
        return value

    @model_validator(mode="after")
    def _effective_period_ordered(self) -> "TreatyFiguresRequest":
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from must be <= effective_to")
        return self
