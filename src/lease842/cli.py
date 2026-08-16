"""CLI: lease842 <leases.json> [--period LABEL] [--owner NAME]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from control_spine import exit_code
from lease842.engine import Lease, Payment, money, rollforward
from lease842.evidence import evidence_markdown, evidence_pack


def _load(path: Path) -> list[Lease]:
    raw = json.loads(path.read_text())
    leases = []
    for item in raw["leases"]:
        payments = tuple(
            Payment(period=p["period"], amount=money(p["amount"])) for p in item["payments"]
        )
        leases.append(
            Lease(
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
                specialized_no_alternative_use=item.get(
                    "specialized_no_alternative_use", False
                ),
                initial_direct_costs=item.get("initial_direct_costs", 0),
                incentives=item.get("incentives", 0),
                prepaid=item.get("prepaid", 0),
            )
        )
    return leases


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ASC 842 lease measurement + evidence pack")
    p.add_argument("leases_json")
    p.add_argument("--period", default="current")
    p.add_argument("--owner", default="")
    args = p.parse_args(argv)
    results = [rollforward(lease) for lease in _load(Path(args.leases_json))]
    pack = evidence_pack(results, args.period, args.owner)
    print(evidence_markdown(pack))
    print(pack["lock_state"], file=sys.stderr)
    return exit_code(pack)


if __name__ == "__main__":
    raise SystemExit(main())
