"""MCP server for the lease842 engine.

Exposes the deterministic ASC 842 measurement as Model Context Protocol
tools. Thin wrapper — all measurement logic lives in ``lease842.engine`` and
``lease842.evidence`` and is reused verbatim; nothing here touches the
network, and no lease classification judgment is made by a model.

Follows the same publishing path proven by invoice-audit-engine /
codesentinel: namespace ``io.github.Cubiczan``, stdio transport, published
via the ``mcp-publisher`` CLI.

Run it:

    uvx --from lease842 lease842-mcp
    # or, from a checkout:
    python -m lease842.mcp_server
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from enum import Enum
from typing import Any

from mcp.server.fastmcp import FastMCP

from lease842.engine import Lease, Payment, money, rollforward
from lease842.evidence import evidence_pack

mcp = FastMCP(
    "lease842",
    instructions=(
        "Deterministic ASC 842 lease measurement. Supply lease terms; the "
        "tools classify (finance / operating / short-term), compute the "
        "present value of remaining payments, build the ROU / liability "
        "rollforward, and render the evidence pack a tester can reperform. "
        "The number never comes from a language model; whether a contract "
        "is a lease stays with the control owner."
    ),
)


def _lease_from_dict(item: dict[str, Any]) -> Lease:
    """Build a Lease from the CLI/JSON shape (same keys as examples/sample_leases.json)."""
    payments = tuple(
        Payment(period=p["period"], amount=money(p["amount"])) for p in item["payments"]
    )
    return Lease(
        lease_id=item["lease_id"],
        description=item.get("description", ""),
        payments=payments,
        annual_ibr=item["annual_ibr"],
        payments_per_year=item.get("payments_per_year", 12),
        economic_life_periods=item.get("economic_life_periods"),
        fair_value=item.get("fair_value"),
        transfers_ownership=item.get("transfers_ownership", False),
        purchase_option_reasonably_certain=item.get(
            "purchase_option_reasonably_certain", False
        ),
        specialized_no_alternative_use=item.get("specialized_no_alternative_use", False),
        initial_direct_costs=item.get("initial_direct_costs", 0),
        incentives=item.get("incentives", 0),
        prepaid=item.get("prepaid", 0),
    )


def _jsonify(value: Any) -> Any:
    """JSON-safe conversion: Decimals become strings so cents survive exactly."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


def _result_to_dict(result: Any) -> dict[str, Any]:
    """asdict with enums reduced to values and Decimals kept as strings."""
    return _jsonify(asdict(result))


@mcp.tool()
def measure_lease(lease: dict[str, Any]) -> dict[str, Any]:
    """Classify one lease (finance / operating / short-term) and compute its rollforward.

    Returns classification with the indicator that fired, the periodic rate,
    initial liability and ROU asset, and the period-by-period schedule.
    Amounts are returned as exact decimal strings.

    Args:
        lease: Lease terms. Expected keys mirror examples/sample_leases.json:
            lease_id, payments (list of {period, amount}), annual_ibr,
            payments_per_year, economic_life_periods, fair_value,
            transfers_ownership, purchase_option_reasonably_certain,
            specialized_no_alternative_use, initial_direct_costs, incentives,
            prepaid.
    """
    return _result_to_dict(rollforward(_lease_from_dict(lease)))


@mcp.tool()
def lease_evidence_pack(
    leases: list[dict[str, Any]],
    period_label: str = "current",
    owner: str = "",
) -> dict[str, Any]:
    """Build the evidence pack a tester can reperform without the source code.

    Aggregates measured leases into the population register (classification
    counts, ROU and liability totals) and renders the control-spine pack.

    Args:
        leases: Lease terms, same shape as measure_lease's input.
        period_label: Close period label (e.g. "H1 2026").
        owner: Named owner for sign-off. Must not be the engine.
    """
    parsed = [_lease_from_dict(item) for item in leases]
    results = [rollforward(lease) for lease in parsed]
    return _jsonify(evidence_pack(results, period_label, owner))


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
