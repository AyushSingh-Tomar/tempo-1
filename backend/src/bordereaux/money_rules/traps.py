"""Row-level Category D trap detection for Step 8 (rule doc §5).

``engine.detect_*`` answer "is this whole *column* mislabelled?" while mapping.
Here the mapping is final and the treaty rates are known, so the same traps are
looked for on individual *rows*:

* MCR-D2 - the labelled gross already has commission deducted: commission is
  ``comm% / (1 - comm%)`` of the labelled gross rather than ``comm%``.
* MCR-D1 - the labelled gross is really the ceded figure: it is ~``cess%`` of
  the gross implied by the sum insured at the rate peers of the same class
  show. Needs peer rows and is deliberately strict, since a loose version
  would flag honest rows: a row whose own G - C - T = N holds is never
  called a ceded gross (rule doc §5.1, signal 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.rules import RuleOutcome, approx_equal, rule_a1
from bordereaux.money_rules.types import MoneyRole, MoneyRow, TreatyRates

R = MoneyRole

D1_TOLERANCE = Decimal("0.05")
MIN_CLASS_PEERS = 3
MIN_ALL_PEERS = 5


@dataclass(frozen=True)
class RowTrap:
    rule_id: str
    row_number: int
    expected_value: Decimal | None
    observed_value: Decimal | None
    message: str
    evidence: dict
    explains: tuple[str, ...] = ()
    """Ordinary rule ids whose failures on this row are a symptom of the trap."""


def detect_commission_bundles_brokerage_row(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RowTrap | None:
    """MCR-D2 (bundling form): commission ~ gross x (comm% + brok%) with the
    brokerage figure empty or zero - the brokerage has been folded into the
    commission column."""
    c_pct, b_pct = treaty.commission_pct, treaty.brokerage_pct
    gross, comm, brok = row.get(R.GROSS), row.get(R.COMMISSION), row.get(R.BROKERAGE)
    if c_pct is None or b_pct is None or b_pct == 0 or gross is None or comm is None or gross == 0:
        return None
    if brok not in (None, Decimal(0)):
        return None
    combined = gross * (c_pct + b_pct)
    if approx_equal(comm, gross * c_pct, cfg.tolerance) or not approx_equal(comm, combined, cfg.tolerance):
        return None
    return RowTrap(
        rule_id="MCR-D2",
        row_number=row.row_number,
        expected_value=gross * c_pct,
        observed_value=comm,
        message=(
            f"Commission bundles brokerage: it is {comm / gross:.2%} of gross = comm% + brok% "
            f"({c_pct + b_pct:.2%}), while the brokerage figure is empty."
        ),
        evidence={
            "commission_to_gross": str(round(comm / gross, 4)),
            "treaty_commission_plus_brokerage": str(c_pct + b_pct),
            "commission_if_unbundled": str(round(gross * c_pct, 2)),
        },
        explains=("MCR-B1", "MCR-B2"),
    )


def detect_bundled_commission(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RowTrap | None:
    return detect_gross_net_of_commission(row, treaty, cfg) or detect_commission_bundles_brokerage_row(row, treaty, cfg)


def detect_gross_net_of_commission(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RowTrap | None:
    c_pct = treaty.commission_pct
    gross, comm = row.get(R.GROSS), row.get(R.COMMISSION)
    if c_pct is None or not (0 < c_pct < 1) or gross is None or comm is None or gross == 0:
        return None
    deducted_rate = c_pct / (1 - c_pct)
    if approx_equal(comm, gross * c_pct, cfg.tolerance) or not approx_equal(comm, gross * deducted_rate, cfg.tolerance):
        return None
    corroborating: list[str] = []
    contradicting = False
    for role, pct, label in ((R.BROKERAGE, treaty.brokerage_pct, "brokerage"), (R.TAX, treaty.tax_pct, "tax")):
        value = row.get(role)
        if value is None or pct is None or value == 0:
            continue
        if approx_equal(value, gross * pct / (1 - c_pct), cfg.tolerance):
            corroborating.append(label)
        elif not approx_equal(value, gross * pct, cfg.tolerance):
            contradicting = True
    if contradicting:
        return None
    net = row.get(R.NET)
    evidence: dict = {
        "commission_to_gross": str(round(comm / gross, 4)),
        "treaty_commission_pct": str(c_pct),
        "commission_if_gross_were_pre_commission": str(round(gross * deducted_rate, 2)),
        "corroborated_by": corroborating,
    }
    if net is not None and net != 0:
        evidence["gross_to_net"] = str(round(gross / net, 4))
    return RowTrap(
        rule_id="MCR-D2",
        row_number=row.row_number,
        expected_value=gross * c_pct,
        observed_value=comm,
        message=(
            f"Gross premium appears to have commission already deducted: commission is {comm / gross:.1%} of the "
            f"labelled gross (treaty {c_pct:.1%} of the true gross)."
        ),
        evidence=evidence,
        explains=("MCR-B1", "MCR-B2", "MCR-B3", "MCR-A1", "MCR-A2", "MCR-A3", "MCR-A4", "MCR-A5"),
    )


def detect_gross_is_ceded_rows(
    rows: list[MoneyRow],
    sum_insured: dict[int, Decimal],
    groups: dict[int, str],
    treaty: TreatyRates,
    cfg: MCRConfig,
) -> list[RowTrap]:
    cess = treaty.cession_pct
    if cess is None or not (0 < cess < 1):
        return []
    expected_rate = treaty.expected_si_rate
    if expected_rate is not None and expected_rate > 0:
        return _detect_ceded_vs_expected_rate(rows, sum_insured, expected_rate, treaty, cfg)
    rates: dict[int, Decimal] = {}
    for row in rows:
        gross, si = row.get(R.GROSS), sum_insured.get(row.row_number)
        if gross is not None and gross > 0 and si is not None and si > 0:
            rates[row.row_number] = gross / si
    traps: list[RowTrap] = []
    for row in rows:
        rate = rates.get(row.row_number)
        if rate is None:
            continue
        group = groups.get(row.row_number)
        peers = [r for n, r in rates.items() if n != row.row_number and group and groups.get(n) == group]
        if len(peers) < MIN_CLASS_PEERS:
            peers = [r for n, r in rates.items() if n != row.row_number]
            if len(peers) < MIN_ALL_PEERS:
                continue
        typical = Decimal(str(median(peers)))
        ratio = rate / typical
        if not approx_equal(ratio, cess, D1_TOLERANCE):
            continue
        gross, comm = row.get(R.GROSS), row.get(R.COMMISSION)
        if comm is not None and treaty.commission_pct is not None and not approx_equal(
            comm, gross * treaty.commission_pct, cfg.tolerance
        ):
            continue  # commission anchor contradicts the ceded reading
        if rule_a1(row, treaty, cfg) is RuleOutcome.HOLDS:
            continue  # §5.1 signal 3: a ceded "gross" cannot satisfy G - C - T = N on a full-value basis
        implied = gross / ratio
        traps.append(
            RowTrap(
                rule_id="MCR-D1",
                row_number=row.row_number,
                expected_value=implied,
                observed_value=gross,
                message=(
                    f"Labelled gross is {ratio:.0%} of the gross implied by sum insured at the peer rate "
                    f"(treaty cession {cess:.0%}) - it looks like the ceded figure, not the full gross."
                ),
                evidence={"peer_rate_median": str(typical), "row_rate": str(rate), "peer_count": len(peers)},
            )
        )
    return traps


def _detect_ceded_vs_expected_rate(
    rows: list[MoneyRow], sum_insured: dict[int, Decimal], expected_rate: Decimal, treaty: TreatyRates, cfg: MCRConfig
) -> list[RowTrap]:
    """The user supplied the technical rate on sum insured, so the implied
    gross is ``SI x rate`` and a labelled gross of ~``cess%`` of it is the
    ceded figure. No peers needed."""
    cess = treaty.cession_pct
    traps: list[RowTrap] = []
    for row in rows:
        gross, si = row.get(R.GROSS), sum_insured.get(row.row_number)
        if gross is None or gross <= 0 or si is None or si <= 0:
            continue
        implied = si * expected_rate
        if not approx_equal(gross, implied * cess, D1_TOLERANCE):
            continue
        comm = row.get(R.COMMISSION)
        if comm is not None and treaty.commission_pct is not None and not approx_equal(
            comm, gross * treaty.commission_pct, cfg.tolerance
        ):
            continue  # commission anchor contradicts the ceded reading
        traps.append(
            RowTrap(
                rule_id="MCR-D1",
                row_number=row.row_number,
                expected_value=implied,
                observed_value=gross,
                message=(
                    f"Labelled gross is {gross / implied:.0%} of the gross implied by sum insured at the expected "
                    f"{expected_rate:.2%} rate (treaty cession {cess:.0%}) - it looks like the ceded figure."
                ),
                evidence={"expected_si_rate": str(expected_rate), "gross_to_sum_insured": str(round(gross / si, 6))},
            )
        )
    return traps
