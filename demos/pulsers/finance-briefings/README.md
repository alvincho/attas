# Finance Briefing Workflow Demo

## Translations

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## What This Demo Shows

- an Attas-owned `FinancialBriefingPulser` exposing workflow-seed pulses and finance briefing step pulses
- one workflow-entry context pulse:
  - `prepare_finance_briefing_context`
  - distinguish the workflow with `workflow_name`: `morning_desk_briefing`, `watchlist_check`, or `research_roundup`
- shared finance step pulses:
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_briefing_payload`
- downstream publication/export pulses:
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## Why This Exists

MapPhemar runs diagrams by calling pulsers and pulses. The finance briefing workflows started as plain Python functions in `attas`, but the current diagrams break those workflows into editable step nodes, so the runtime now uses an Attas-native pulser instead of a generic MCP wrapper.

The runtime surface is:

- [finance-briefings.pulser](./finance-briefings.pulser): demo config for `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): Attas-owned pulser class hosting the workflow seed and step pulses
- [briefings.py](../../../attas/workflows/briefings.py): public finance briefing step helpers consumed by the pulser

## Runtime Assumptions

- Plaza at `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` at `http://127.0.0.1:8271`

## Single-Command Launch

From the repository root:

```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

This starts the local Plaza plus the finance briefing pulser from one terminal, opens a browser guide page, and opens the pulser UI automatically.

Set `DEMO_OPEN_BROWSER=0` if you want the launcher to stay in the terminal only.

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro. From the repository root inside WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

If browser tabs do not auto-open from WSL, keep the launcher running and open the printed `guide=` URL in a Windows browser.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## Manual Launch

From the repository root:

```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## Related Diagram Files

These diagrams live in `demos/files/diagrams/`:

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

Each diagram follows the same editable structure:

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## Current MapPhemar Fit

These workflows fit inside the current MapPhemar model without adding a new node type or schema:

- executable steps are regular `rectangle` nodes
- boundaries use `pill`
- branching remains available through `branch`
- artifact fan-out is handled by multiple outgoing edges from the workflow node

Current runtime limitation:

- `Input` may connect to exactly one downstream node, so fan-out must happen after the first executable workflow node rather than directly from `Input`

No new MapPhemar node type or schema extension was needed for these stepwise finance workflows. Regular executable nodes plus the Attas pulser surface are enough for current storage, editing, and execution.
