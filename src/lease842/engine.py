"""Deterministic ASC 842 measurement.

The engine does not decide whether a contract is a lease. That judgment stays
with the control owner. Given a confirmed lease, it classifies (finance vs
operating vs short-term), computes the initial liability as the present value
of remaining payments, builds the ROU asset, and produces a period-by-period
rollforward a tester can reperform.

Practical thresholds used for the "major part" / "substantially all" tests
are the common 75% / 90% bright lines. They are config, not statute.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Sequence


CENTS = Decimal("0.01")
MAJOR_PART = Decimal("0.75")
SUBSTANTIALLY_ALL = Decimal("0.90")


def D(value: object) -> Decimal:
    return Decimal(str(value))


def money(value: object) -> Decimal:
    return D(value).quantize(CENTS, rounding=ROUND_HALF_UP)


class Classification(str, Enum):
    FINANCE = "finance"
    OPERATING = "operating"
    SHORT_TERM = "short_term"


@dataclass(frozen=True)
class Payment:
    period: int
    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", money(self.amount))


@dataclass(frozen=True)
class Lease:
    lease_id: str
    description: str
    payments: tuple[Payment, ...]
    annual_ibr: Decimal
    payments_per_year: int = 12
    economic_life_periods: int | None = None
    fair_value: Decimal | None = None
    transfers_ownership: bool = False
    purchase_option_reasonably_certain: bool = False
    specialized_no_alternative_use: bool = False
    initial_direct_costs: Decimal = Decimal("0")
    incentives: Decimal = Decimal("0")
    prepaid: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "annual_ibr", D(self.annual_ibr))
        object.__setattr__(self, "initial_direct_costs", money(self.initial_direct_costs))
        object.__setattr__(self, "incentives", money(self.incentives))
        object.__setattr__(self, "prepaid", money(self.prepaid))
        if self.fair_value is not None:
            object.__setattr__(self, "fair_value", money(self.fair_value))


@dataclass(frozen=True)
class PeriodRow:
    period: int
    opening_liability: Decimal
    interest: Decimal
    payment: Decimal
    principal: Decimal
    closing_liability: Decimal
    rou_amortization: Decimal
    closing_rou: Decimal
    period_expense: Decimal


@dataclass(frozen=True)
class LeaseResult:
    lease: Lease
    classification: Classification
    classification_reasons: tuple[str, ...]
    periodic_rate: Decimal
    initial_liability: Decimal
    initial_rou: Decimal
    schedule: tuple[PeriodRow, ...]


def periodic_rate(annual_ibr: Decimal, payments_per_year: int) -> Decimal:
    if payments_per_year <= 0:
        raise ValueError("payments_per_year must be positive")
    return D(annual_ibr) / D(payments_per_year)


def present_value(payments: Sequence[Payment], rate: Decimal) -> Decimal:
    """PV of payments in arrears: amount_t / (1+r)^t for t = 1..n."""
    total = Decimal("0")
    one = Decimal("1")
    for pmt in payments:
        if pmt.period <= 0:
            raise ValueError("payment periods are 1-indexed")
        disc = (one + rate) ** pmt.period
        total += pmt.amount / disc
    return money(total)


def classify(lease: Lease) -> tuple[Classification, tuple[str, ...]]:
    n = len(lease.payments)
    reasons: list[str] = []
    if n == 0:
        return Classification.SHORT_TERM, ("no remaining payments",)

    max_term_short = lease.payments_per_year
    if (
        n <= max_term_short
        and not lease.purchase_option_reasonably_certain
        and not lease.transfers_ownership
    ):
        return Classification.SHORT_TERM, (
            f"term {n} periods <= 12 months and no reasonably certain purchase option",
        )

    if lease.transfers_ownership:
        reasons.append("ownership transfers at end of term (ASC 842-10-25-2a)")
    if lease.purchase_option_reasonably_certain:
        reasons.append("purchase option reasonably certain to be exercised (25-2b)")
    if lease.economic_life_periods and n / lease.economic_life_periods >= MAJOR_PART:
        reasons.append(
            f"term {n}/{lease.economic_life_periods} is major part of remaining economic life "
            f"(threshold {MAJOR_PART})"
        )
    rate = periodic_rate(lease.annual_ibr, lease.payments_per_year)
    pv = present_value(lease.payments, rate)
    if lease.fair_value and lease.fair_value != 0:
        ratio = pv / lease.fair_value
        if ratio >= SUBSTANTIALLY_ALL:
            reasons.append(
                f"PV {pv} is {ratio:.1%} of FV {lease.fair_value} "
                f"(threshold {SUBSTANTIALLY_ALL})"
            )
    if lease.specialized_no_alternative_use:
        reasons.append("specialized asset with no alternative use (25-2e)")

    if reasons:
        return Classification.FINANCE, tuple(reasons)
    return Classification.OPERATING, ("no finance-lease indicator met",)


def _level_payment_expense(lease: Lease) -> Decimal:
    total = sum((p.amount for p in lease.payments), Decimal("0"))
    n = len(lease.payments)
    return money(total / n) if n else Decimal("0.00")


def rollforward(lease: Lease) -> LeaseResult:
    classification, reasons = classify(lease)
    rate = periodic_rate(lease.annual_ibr, lease.payments_per_year)
    initial_liability = present_value(lease.payments, rate)
    initial_rou = money(
        initial_liability + lease.initial_direct_costs + lease.prepaid - lease.incentives
    )

    if classification == Classification.SHORT_TERM:
        rows = []
        expense = _level_payment_expense(lease)
        for pmt in lease.payments:
            rows.append(
                PeriodRow(
                    period=pmt.period,
                    opening_liability=Decimal("0.00"),
                    interest=Decimal("0.00"),
                    payment=pmt.amount,
                    principal=pmt.amount,
                    closing_liability=Decimal("0.00"),
                    rou_amortization=Decimal("0.00"),
                    closing_rou=Decimal("0.00"),
                    period_expense=pmt.amount if classification == Classification.SHORT_TERM else expense,
                )
            )
        return LeaseResult(
            lease=lease,
            classification=classification,
            classification_reasons=reasons,
            periodic_rate=rate,
            initial_liability=Decimal("0.00"),
            initial_rou=Decimal("0.00"),
            schedule=tuple(rows),
        )

    n = len(lease.payments)
    liab = initial_liability
    rou = initial_rou
    sl_expense = _level_payment_expense(lease)
    rows: list[PeriodRow] = []
    for i, pmt in enumerate(lease.payments):
        opening = liab
        interest = money(opening * rate)
        principal = money(pmt.amount - interest)
        # Last period: force liability to zero for residual cents.
        if i == n - 1:
            principal = opening
            interest = money(pmt.amount - principal)
        liab = money(opening - principal)
        remaining = n - i
        if classification == Classification.FINANCE:
            amort = money(rou / remaining)
            expense = money(interest + amort)
        else:
            # Operating: single SL lease expense; ROU plugs so expense = SL.
            amort = money(sl_expense - interest)
            expense = sl_expense
        rou = money(rou - amort)
        if i == n - 1:
            rou = Decimal("0.00")
            liab = Decimal("0.00")
        rows.append(
            PeriodRow(
                period=pmt.period,
                opening_liability=opening,
                interest=interest,
                payment=pmt.amount,
                principal=principal,
                closing_liability=liab,
                rou_amortization=amort,
                closing_rou=rou,
                period_expense=expense,
            )
        )

    return LeaseResult(
        lease=lease,
        classification=classification,
        classification_reasons=reasons,
        periodic_rate=rate,
        initial_liability=initial_liability,
        initial_rou=initial_rou,
        schedule=tuple(rows),
    )


def level_payments(amount: object, periods: int) -> tuple[Payment, ...]:
    amt = money(amount)
    return tuple(Payment(period=i, amount=amt) for i in range(1, periods + 1))
