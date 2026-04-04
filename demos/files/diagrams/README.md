# Demo Diagram Library

`demos/files/diagrams` contains reusable `MapPhemar` diagram-backed Phemas for financial analytics and LLM-assisted research workflows.

These files are meant to be easy to copy into another MapPhemar pool, load into the diagram editor, or use as reference payloads when building your own flows.

## What Is In This Folder

There are two groups of examples:

- technical-analysis diagrams that turn OHLC market data into indicator series
- LLM-oriented analyst diagrams that turn raw market news into structured research notes

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

## Related Demos

If you want to run the supporting services rather than only inspect the diagrams:

- `demos/personal-research-workbench/README.md`: visual diagram workflow with the seeded RSI example
- `demos/pulsers/analyst-insights/README.md`: prompted analyst news stack used by the LLM-oriented diagrams
- `demos/pulsers/llm/README.md`: standalone `llm_chat` pulser demo for OpenAI and Ollama

## Verification

These files are covered by repo tests:

```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py
```

That test suite verifies the saved diagrams execute end to end against mocked or reference pulser flows.
