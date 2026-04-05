# Demo Diagram Library

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

`demos/files/diagrams` contains reusable `MapPhemar` diagram-backed Phemas for financial analytics and LLM-assisted research workflows.

These files are meant to be easy to copy into another MapPhemar pool, load into the diagram editor, or use as reference payloads when building your own flows.

## Platform Notes

This folder ships JSON assets, not a standalone launcher.

### macOS And Linux

Launch one of the paired demos first, then load these files into MapPhemar or Personal Agent:

```bash
./demos/personal-research-workbench/run-demo.sh
```

You can also launch:

```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro for the paired demo launchers. After the stack is running, open the printed `guide=` URL in a Windows browser if tabs do not open automatically.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## What Is In This Folder

There are two groups of examples:

- technical-analysis diagrams that turn OHLC market data into indicator series
- LLM-oriented analyst diagrams that turn raw market news into structured research notes
- finance workflow diagrams that turn normalized research inputs into briefing, publication, and NotebookLM export bundles

## Files In This Folder

### Technical Analysis

- `ohlc-to-sma-20-diagram.json`: `Input -> OHLC Bars -> SMA 20 -> Output`
- `ohlc-to-ema-50-diagram.json`: `Input -> OHLC Bars -> EMA 50 -> Output`
- `ohlc-to-macd-histogram-diagram.json`: `Input -> OHLC Bars -> MACD Histogram -> Output`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `Input -> OHLC Bars -> Bollinger Bandwidth -> Output`
- `ohlc-to-adx-14-diagram.json`: `Input -> OHLC Bars -> ADX 14 -> Output`
- `ohlc-to-obv-diagram.json`: `Input -> OHLC Bars -> OBV -> Output`

### LLM / Analyst Research

- `analyst-news-desk-brief-diagram.json`: `Input -> News Desk Brief -> Output`
- `analyst-news-monitoring-points-diagram.json`: `Input -> Monitoring Points -> Output`
- `analyst-news-client-note-diagram.json`: `Input -> Client Note -> Output`

### Finance Workflow Pack

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `Input -> Prepare Morning Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`
- `finance-watchlist-check-notebooklm-diagram.json`: `Input -> Prepare Watchlist Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`
- `finance-research-roundup-notebooklm-diagram.json`: `Input -> Prepare Research Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

These three saved Phemas stay separate for editing, but they share the same workflow-entry pulse and distinguish the workflow with node `paramsText.workflow_name`.

## Runtime Assumptions

These diagrams are saved with concrete local addresses so they can run without extra editing when the expected demo stack is available.

### Technical Analysis Diagrams

The indicator diagrams assume:

- Plaza at `http://127.0.0.1:8011`
- `YFinancePulser` at `http://127.0.0.1:8020`
- `TechnicalAnalysisPulser` at `http://127.0.0.1:8033`

The pulser configs referenced by these diagrams live in:

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### LLM / Analyst Diagrams

The LLM-oriented diagrams assume:

- Plaza at `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` at `http://127.0.0.1:8270`

That prompted analyst pulser itself depends on:

- `news-wire.pulser` at `http://127.0.0.1:8268`
- `ollama.pulser` at `http://127.0.0.1:8269`

Those demo files live in:

- `demos/pulsers/analyst-insights/`

### Finance Workflow Diagrams

The finance workflow diagrams assume:

- Plaza at `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` at `http://127.0.0.1:8271`

That demo pulser is an Attas-owned `FinancialBriefingPulser` backed by:

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

These diagrams are editable in both MapPhemar and the embedded Personal Agent MapPhemar routes because they are ordinary diagram-backed Phema JSON files.

## Quickstart

### Option 1: Load The Files Into MapPhemar

1. Open a MapPhemar editor instance.
2. Load one of the JSON files from this folder.
3. Confirm the saved `plazaUrl` and pulser addresses match your local environment.
4. Run `Test Run` with one of the sample payloads below.

If your services use different ports or names, edit:

- `meta.map_phemar.diagram.plazaUrl`
- each node's `pulserName`
- each node's `pulserAddress`

### Option 2: Use Them As Seed Files

You can also copy these JSON files into any MapPhemar pool under a `phemas/` directory and load them through the agent UI the same way the personal-research-workbench demo does.

## Sample Inputs

### Technical Analysis Diagrams

Use a payload like:

```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

Expected result:

- the `OHLC Bars` step fetches a historical bar series
- the indicator node computes a `values` array
- the final output returns timestamp/value pairs

### LLM / Analyst Diagrams

Use a payload like:

```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Expected result:

- the prompted analyst pulser fetches raw news
- the prompt pack turns that news into a structured analyst view
- the output returns research-ready fields such as `desk_note`, `monitor_now`, or `client_note`

### Finance Workflow Diagrams

Use a payload like:

```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

Expected result:

- the workflow context node seeds the chosen finance workflow
- the intermediate finance nodes build sources, citations, facts, risks, catalysts, conflicts, takeaways, questions, and summary blocks
- the assembly node builds an `attas.finance_briefing` payload
- the report node converts that payload into a static Phema
- the NotebookLM node generates export artifacts from the same payload
- the final output merges all three results for inspection in MapPhemar or Personal Agent

## Current Editor Limits

These finance workflows fit the current MapPhemar model without adding a new node type.

Two important runtime rules still apply:

- `Input` must connect to exactly one downstream shape
- every executable non-branch node must reference a pulse plus a reachable pulser

That means workflow fan-out has to happen after the first executable node, and workflow steps still need to be exposed as pulser-hosted pulses if you want the diagram to run end to end.

## Related Demos

If you want to run the supporting services rather than only inspect the diagrams:

- `demos/personal-research-workbench/README.md`: visual diagram workflow with the seeded RSI example
- `demos/pulsers/analyst-insights/README.md`: prompted analyst news stack used by the LLM-oriented diagrams
- `demos/pulsers/llm/README.md`: standalone `llm_chat` pulser demo for OpenAI and Ollama

## Verification

These files are covered by repo tests:

```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

That test suite verifies the saved diagrams execute end to end against mocked or reference pulser flows.
