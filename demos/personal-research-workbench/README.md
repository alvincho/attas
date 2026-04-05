# Personal Research Workbench

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

`personal-research-workbench` is the visual product demo. It pairs the React/FastAPI workbench with a local Plaza, a local file-storage pulser, an optional YFinance pulser, and an optional technical-analysis pulser so people can explore workspaces, layouts, Plaza browsing, pulser execution, chart rendering, and diagram test runs from one UI.

## What This Demo Shows

- the personal workbench UI running locally
- a Plaza that the workbench can browse
- local and live-data pulsers with real runnable pulses
- a diagram-first `Test Run` flow that turns market data into a calculated indicator series
- a path from a polished demo into a self-hosted instance

## Files In This Folder

- `plaza.agent`: local Plaza used only for this demo
- `file-storage.pulser`: local pulser backed by the filesystem
- `yfinance.pulser`: optional market-data pulser backed by the `yfinance` Python module
- `technical-analysis.pulser`: optional path pulser that computes RSI from OHLC data
- `map_phemar.phemar`: demo-local MapPhemar config used by the embedded diagram editor
- `map_phemar_pool/`: seeded diagram storage with a ready-to-run OHLC-to-RSI map
- `start-plaza.sh`: launch the demo Plaza
- `start-file-storage-pulser.sh`: launch the pulser
- `start-yfinance-pulser.sh`: launch the YFinance pulser
- `start-technical-analysis-pulser.sh`: launch the technical analysis pulser
- `start-workbench.sh`: launch the React/FastAPI workbench

All runtime state is written under `demos/personal-research-workbench/storage/`. The launcher also points the embedded diagram editor at the seeded `map_phemar.phemar` and `map_phemar_pool/` files in this folder.

## Prerequisites

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Single-Command Launch

From the repository root:

```bash
./demos/personal-research-workbench/run-demo.sh
```

This starts the workbench stack from one terminal, opens a browser guide page, then opens both the main workbench UI and the embedded `MapPhemar` route used in the core walkthrough.

Set `DEMO_OPEN_BROWSER=0` if you want the launcher to stay in the terminal only.

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro. From the repository root inside WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

If browser tabs do not auto-open from WSL, keep the launcher running and open the printed `guide=` URL in a Windows browser.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## Quickstart

Open five terminals from the repository root if you want the full demo, including the YFinance chart flow and the diagram test-run flow.

### Terminal 1: start the local Plaza

```bash
./demos/personal-research-workbench/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8241`

### Terminal 2: start the local file-storage pulser

```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8242`
- it registers itself with the Plaza from Terminal 1

### Terminal 3: start the YFinance pulser

```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8243`
- it registers itself with the Plaza from Terminal 1

Note:

- this step requires outbound internet access because the pulser fetches live data from Yahoo Finance through the `yfinance` module
- Yahoo can occasionally rate-limit requests, so this flow is best treated as a live demo rather than a strict fixture

### Terminal 4: start the technical analysis pulser

```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8244`
- it registers itself with the Plaza from Terminal 1

This pulser calculates `rsi` from an incoming `ohlc_series`, or fetches OHLC bars from the demo YFinance pulser when you only provide symbol, interval, and date range.

### Terminal 5: start the workbench

```bash
./demos/personal-research-workbench/start-workbench.sh
```

Expected result:

- the workbench starts on `http://127.0.0.1:8041`

## First Run Walkthrough

This demo now has three workbench flows:

1. local storage flow with the file-storage pulser
2. live market-data flow with the YFinance pulser
3. diagram test-run flow with the YFinance and technical-analysis pulsers

Open:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### Flow 1: browse and save local data

Then work through this short path:

1. Open the settings flow in the workbench.
2. Go to the `Connection` section.
3. Set the default Plaza URL to `http://127.0.0.1:8241`.
4. Refresh the Plaza catalog.
5. Open or create a browser window in the workbench.
6. Choose the registered file-storage pulser.
7. Run one of the built-in pulses such as `list_bucket`, `bucket_create`, or `bucket_browse`.

Suggested first interaction:

- create a public bucket named `demo-assets`
- browse that bucket
- save a small text object
- load it back again

That gives people a full loop: rich UI, Plaza discovery, pulser execution, and persisted local state.

### Flow 2: view data and draw a chart from the YFinance pulser

Use the same workbench session, then:

1. Refresh the Plaza catalog again so the YFinance pulser appears.
2. Add a new browser pane or reconfigure an existing data pane.
3. Choose the `ohlc_bar_series` pulse.
4. Choose the `DemoYFinancePulser` pulser if the workbench does not auto-select it.
5. Open `Pane Params JSON` and use a payload like this:

```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. Click `Get Data`.
7. In `Display Fields`, turn on `ohlc_series`. If another field is already selected, turn it off so the preview points at the time series itself.
8. Change `Format` to `chart`.
9. Set `Chart Style` to `candle` for OHLC candles or `line` for a simple trend view.

What you should see:

- the pane fetches bar data for the requested symbol and date range
- the preview changes from structured data into a chart
- changing the symbol or date range gives you a new chart without leaving the workbench

Recommended variations:

- switch `AAPL` to `MSFT` or `NVDA`
- shorten the date range for a tighter recent view
- compare `line` and `candle` using the same `ohlc_bar_series` response

### Flow 3: load a diagram and use Test Run to calculate an RSI series

Open the diagram editor route:

- `http://127.0.0.1:8041/map-phemar/`

Then work through this path:

1. Confirm the Plaza URL in the diagram editor is `http://127.0.0.1:8241`.
2. Click `Load Phema`.
3. Choose `OHLC To RSI Diagram`.
4. Inspect the seeded graph. It should show `Input -> OHLC Bars -> RSI 14 -> Output`.
5. Click `Test Run`.
6. Use this input payload:

```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. Run the map and expand the step outputs.

What you should see:

- the `OHLC Bars` step calls the demo YFinance pulser and returns `ohlc_series`
- the `RSI 14` step forwards those bars to the technical-analysis pulser with `window: 14`
- the final `Output` payload contains a calculated `values` array with `timestamp` and `value` entries

If you want to rebuild the same diagram from scratch instead of loading the seed:

1. Add one rounded node named `OHLC Bars`.
2. Bind it to `DemoYFinancePulser` and the `ohlc_bar_series` pulse.
3. Add one rounded node named `RSI 14`.
4. Bind it to `DemoTechnicalAnalysisPulser` and the `rsi` pulse.
5. Set the RSI node params to:

```json
{
  "window": 14,
  "price_field": "close"
}
```

6. Connect `Input -> OHLC Bars -> RSI 14 -> Output`.
7. Leave the edge mappings as `{}` so matching field names flow through automatically.

## What To Point Out In A Demo Call

- The workbench still loads useful mock dashboard data even before any live connections are added.
- Plaza integration is opt-in and can point at a local or remote environment.
- The file-storage pulser is local-only, which makes the public demo safe and reproducible.
- The YFinance pulser adds a second story: the same workbench can browse live market data and render it as a chart.
- The diagram editor adds a third story: the same backend can orchestrate multi-step flows and expose each step through `Test Run`.

## Build Your Own Instance

There are three common customization paths:

### Change the seeded dashboard and workspace data

The workbench reads its dashboard snapshot from:

- `attas/personal_agent/data.py`

That is the fastest place to swap in your own watchlists, metrics, or workspace defaults.

### Change the visual shell

The current live workbench runtime is served from:

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

If you want to re-theme the demo or simplify the UI for your audience, start there.

### Change the connected Plaza and pulsers

If you want a different backend:

1. copy `plaza.agent`, `file-storage.pulser`, `yfinance.pulser`, and `technical-analysis.pulser`
2. rename the services
3. update ports and storage paths
4. edit the seeded diagram in `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` or create your own from the workbench
5. replace the demo pulsers with your own agents when ready

## Optional Workbench Settings

The launcher script supports a couple of useful environment variables:

```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

Use `PHEMACAST_PERSONAL_AGENT_RELOAD=1` when actively editing the FastAPI app during development.

## Troubleshooting

### The workbench loads, but Plaza results are empty

Check these three things:

- `http://127.0.0.1:8241/health` is reachable
- the file-storage, YFinance, and technical-analysis pulser terminals are still running when you need those flows
- the workbench `Connection` settings point at `http://127.0.0.1:8241`

### The pulser does not show any objects yet

That is normal on first boot. The demo storage backend starts empty.

### The YFinance pane does not draw a chart

Check these things:

- the YFinance pulser terminal is running
- the selected pulse is `ohlc_bar_series`
- `Display Fields` includes `ohlc_series`
- `Format` is set to `chart`
- `Chart Style` is `line` or `candle`

If the request itself fails, try another symbol or rerun it after a short wait because Yahoo can rate-limit or reject requests intermittently.

### The diagram `Test Run` fails

Check these things:

- `http://127.0.0.1:8241/health` is reachable
- the YFinance pulser is running on `http://127.0.0.1:8243`
- the technical-analysis pulser is running on `http://127.0.0.1:8244`
- the loaded diagram is `OHLC To RSI Diagram`
- the input payload includes `symbol`, `interval`, `start_date`, and `end_date`

If the `OHLC Bars` step fails first, the issue is usually live Yahoo access or rate limiting. If the `RSI 14` step fails, the most common cause is that the technical-analysis pulser is not running or the upstream OHLC response did not include `ohlc_series`.

### You want to reset the demo

The safest reset is to point `root_path` values at a new folder name, or remove the `demos/personal-research-workbench/storage/` folder when no demo processes are running.

## Stop The Demo

Press `Ctrl-C` in each terminal window.
