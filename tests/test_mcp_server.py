"""The MCP server registers the engine's deterministic measurement as callable tools.

Pins the README's canonical number (36 x 1,000 at 6% = 32,871.02) through the
MCP tool path. Skipped cleanly when the optional ``mcp`` SDK is not installed.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp")

from lease842 import mcp_server  # noqa: E402


def _tool_names() -> set[str]:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    return {t.name for t in tools}


def _office() -> dict:
    return {
        "lease_id": "HQ-3YR",
        "description": "36 x 1000 at 6%",
        "payments": [{"period": p, "amount": 1000} for p in range(1, 37)],
        "annual_ibr": "0.06",
        "economic_life_periods": 120,
        "fair_value": "80000",
    }


def test_expected_tools_registered() -> None:
    assert _tool_names() >= {"measure_lease", "lease_evidence_pack"}


def test_measure_lease_pins_the_readme_number() -> None:
    result = mcp_server.measure_lease(_office())
    assert result["classification"] == "operating"
    assert result["initial_liability"] == "32871.02"


def test_evidence_pack_totals_population() -> None:
    pack = mcp_server.lease_evidence_pack([_office()], period_label="H1 2026", owner="Controller")
    assert pack["population_count"] == 1
