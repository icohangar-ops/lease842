# lease842

> **Cubiczan stack** — [CHP](https://github.com/Cubiczan/consensus-hardening-protocol) · [control-spine](https://github.com/Cubiczan/control-spine) · **You are here:** `lease842`

**Deterministic ASC 842 measurement.** Classification, present value, ROU / liability rollforward, and an evidence pack a tester can reperform. The number never comes from a language model.

Built for any listed company whose lease-accounting control cannot be reperformed from the close file. It measures leases. It does not decide whether a contract is a lease — that judgment stays with the control owner.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What it produces

| Artefact | What a tester samples |
|---|---|
| Lease population register | Completeness vs the contract repository |
| Classification checklist | Finance / operating / short-term, with the indicator that fired |
| PV of remaining payments | Recomputable from the payment schedule and IBR |
| Period rollforward | Opening liability, interest, payment, principal, ROU amort, expense |
| Evidence pack | Population, threshold, owner sign-off slot |

## What it does not do

- Identify embedded leases in a vendor contract.
- Choose the incremental borrowing rate.
- Substitute for a signed technical memo on a novel arrangement.
- Shorten the operating period an auditor needs before concluding remediation.

## Quick start

```bash
pip install -e ".[dev]"
pytest -q
lease842 examples/sample_leases.json --period "H1 2026" --owner "Controller"
```

36 monthly payments of 1,000 at a 6% IBR measure at **32,871.02**. Month-one interest is 164.36. The tests pin both numbers; re-run them before you trust a close.

## Classification

Finance if any ASC 842-10-25-2 indicator is met. The "major part" / "substantially all" tests use the common 75% / 90% bright lines and are named as such in the evidence pack. Short-term exemption: term of 12 months or less and no reasonably certain purchase option — no ROU or liability is recognized; payments hit expense.

Operating leases take a single straight-line expense; the ROU plug is interest minus that straight line so the P&L is level when payments are level.

## Compliance spine

Every pack is sealed by a vendored copy of `control-spine` (canonical source: the `control-spine` repo). Unsigned output is `EXPLORING` and is **not evidence**. A named owner who is not the engine, plus a non-empty population and committed foundation assumptions, reaches `LOCKED`. The engine cannot countersign itself. SHA-256 of the inputs and of the spine envelope travel with the pack.

## MCP server

`src/lease842/mcp_server.py` publishes the engine over Model Context Protocol: a thin wrapper in the `io.github.Cubiczan` namespace (stdio transport) whose tools — `measure_lease` and `lease_evidence_pack` — call `lease842.engine` and `lease842.evidence` verbatim. All classification and measurement logic lives in the engine module; the wrapper adds no logic, touches no network, and makes no lease-judgment calls a human owns. Evidence packs built through MCP are always unsigned — the tool takes no owner, so the spine renders `EXPLORING` and `is_evidence: false`; a named human signs via the CLI (`--owner`), never through MCP.

MCP access is opt-in, keeping the deterministic core zero-dependency: the engine and CLI install with no runtime dependencies, and the MCP server ships behind the `mcp` extra (`pip install 'lease842[mcp]'`) — chosen over a hard dependency after prelint review, since a default install must stay dependency-free. CI installs `.[dev,mcp]` so the MCP tests still run.

```bash
uvx --from 'lease842[mcp]' lease842-mcp
# or from a checkout:
uv run --with 'mcp<2' --with . python -m lease842.mcp_server
```
