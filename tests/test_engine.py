from decimal import Decimal

from lease842.engine import (
    Classification,
    Lease,
    classify,
    level_payments,
    money,
    present_value,
    periodic_rate,
    rollforward,
)
from lease842.evidence import evidence_pack


def _office() -> Lease:
    return Lease(
        lease_id="HQ-3YR",
        description="36 x 1000 at 6%",
        payments=level_payments(1000, 36),
        annual_ibr=Decimal("0.06"),
        economic_life_periods=120,
        fair_value=Decimal("80000"),
    )


def test_present_value_36x1000_at_6pct() -> None:
    rate = periodic_rate(Decimal("0.06"), 12)
    pv = present_value(level_payments(1000, 36), rate)
    assert pv == Decimal("32871.02")


def test_operating_classification() -> None:
    cls, reasons = classify(_office())
    assert cls is Classification.OPERATING
    assert "no finance-lease indicator met" in reasons[0]


def test_finance_when_pv_is_substantially_all_of_fv() -> None:
    lease = Lease(
        lease_id="EQ-1",
        description="equipment",
        payments=level_payments(1000, 36),
        annual_ibr=Decimal("0.06"),
        fair_value=Decimal("33000"),
    )
    cls, reasons = classify(lease)
    assert cls is Classification.FINANCE
    assert any("PV" in r for r in reasons)


def test_short_term_exemption() -> None:
    lease = Lease(
        lease_id="ST",
        description="12 month",
        payments=level_payments(500, 12),
        annual_ibr=Decimal("0.06"),
    )
    cls, _ = classify(lease)
    assert cls is Classification.SHORT_TERM
    result = rollforward(lease)
    assert result.initial_liability == Decimal("0.00")
    assert result.schedule[0].period_expense == Decimal("500.00")


def test_month_one_rollforward() -> None:
    result = rollforward(_office())
    row = result.schedule[0]
    assert result.initial_liability == Decimal("32871.02")
    assert result.initial_rou == Decimal("32871.02")
    assert row.interest == Decimal("164.36")
    assert row.payment == Decimal("1000.00")
    assert row.principal == Decimal("835.64")
    assert row.closing_liability == Decimal("32035.38")
    # operating: SL expense equals the level payment
    assert row.period_expense == Decimal("1000.00")


def test_liability_and_rou_zero_at_term() -> None:
    result = rollforward(_office())
    last = result.schedule[-1]
    assert last.closing_liability == Decimal("0.00")
    assert last.closing_rou == Decimal("0.00")
    assert len(result.schedule) == 36


def test_evidence_pack_counts_population() -> None:
    pack = evidence_pack([rollforward(_office())], "H1 2026", "Controller")
    assert pack["population_count"] == 1
    assert pack["totals"]["operating"] == 1
    assert pack["owner_signoff"] == "Controller"
    assert pack["control_id"] == "ICFR-LEASE-842-01"
    assert pack["lock_state"] == "LOCKED"
    assert pack["is_evidence"] is True


def test_unsigned_pack_is_exploring_not_evidence() -> None:
    pack = evidence_pack([rollforward(_office())], "H1 2026", "")
    assert pack["lock_state"] == "EXPLORING"
    assert pack["is_evidence"] is False


def test_money_rounds_half_up() -> None:
    assert money("1.225") == Decimal("1.23")
    assert money("1.224") == Decimal("1.22")
