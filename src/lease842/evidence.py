"""Evidence pack a tester can reperform without the source code."""

from __future__ import annotations

from decimal import Decimal

from control_spine import render_spine, seal
from lease842.engine import LeaseResult, money

FOUNDATION = (
    "The engine does not decide whether a contract is a lease.",
    "Incremental borrowing rate is an input, not estimated here.",
    "Major-part / substantially-all tests use 75% / 90% bright lines named as config.",
    "Short-term exemption is 12 months with no reasonably certain purchase option.",
)

ENGINE_ID = "lease842-engine"
ENGINE_VERSION = "0.1.0"


def evidence_pack(results: list[LeaseResult], period_label: str, owner: str) -> dict:
    population = len(results)
    finance = sum(1 for r in results if r.classification.value == "finance")
    operating = sum(1 for r in results if r.classification.value == "operating")
    short_term = sum(1 for r in results if r.classification.value == "short_term")
    rou = money(sum((r.initial_rou for r in results), Decimal("0")))
    liab = money(sum((r.initial_liability for r in results), Decimal("0")))
    pack = {
        "control_id": "ICFR-LEASE-842-01",
        "control_objective": "Lease population is complete, classified, and measured; ROU and liability rollforward.",
        "period": period_label,
        "population_count": population,
        "threshold": "Every lease above the short-term exemption is measured; 100% of the population is in the pack.",
        "totals": {
            "finance": finance,
            "operating": operating,
            "short_term": short_term,
            "initial_rou": str(rou),
            "initial_liability": str(liab),
        },
        "leases": [
            {
                "lease_id": r.lease.lease_id,
                "classification": r.classification.value,
                "reasons": list(r.classification_reasons),
                "periodic_rate": str(r.periodic_rate),
                "initial_liability": str(r.initial_liability),
                "initial_rou": str(r.initial_rou),
                "periods": len(r.schedule),
                "first_period_expense": str(r.schedule[0].period_expense) if r.schedule else "0.00",
            }
            for r in results
        ],
        "prepared_by": ENGINE_ID,
        "owner_signoff": owner,
        "conclusion": "Population measured. Owner must confirm completeness against the contract repository before this pack is evidence.",
    }
    return seal(
        pack,
        engine_id=ENGINE_ID,
        engine_version=ENGINE_VERSION,
        inputs={"lease_ids": [r.lease.lease_id for r in results], "period": period_label},
        foundation=FOUNDATION,
    )


def evidence_markdown(pack: dict) -> str:
    lines = [
        f"# ASC 842 evidence pack — {pack['period']}",
        "",
        *render_spine(pack),
        f"**Control:** {pack['control_id']} — {pack['control_objective']}",
        f"**Population:** {pack['population_count']} leases",
        f"**Threshold:** {pack['threshold']}",
        f"**Owner sign-off:** {pack['owner_signoff'] or '_unsigned_'}",
        f"**Prepared by:** {pack['prepared_by']} at {pack['sealed_at']}",
        "",
        "## Totals",
        "",
        f"- Finance: {pack['totals']['finance']}",
        f"- Operating: {pack['totals']['operating']}",
        f"- Short-term: {pack['totals']['short_term']}",
        f"- Initial ROU: {pack['totals']['initial_rou']}",
        f"- Initial liability: {pack['totals']['initial_liability']}",
        "",
        "## Population",
        "",
        "| Lease | Class | Liability | ROU | Reasons |",
        "|---|---|---:|---:|---|",
    ]
    for row in pack["leases"]:
        reasons = "; ".join(row["reasons"])
        lines.append(
            f"| {row['lease_id']} | {row['classification']} | {row['initial_liability']} | {row['initial_rou']} | {reasons} |"
        )
    lines += ["", "## Conclusion", "", pack["conclusion"], ""]
    return "\n".join(lines)
