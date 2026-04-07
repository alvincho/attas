# Pulser Demo Set

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

## Start Here

Use these in this order if you are learning the pulser model for the first time:

1. [`file-storage`](./file-storage/README.md): the safest local-only pulser demo
2. [`analyst-insights`](./analyst-insights/README.md): a pulser owned by an analyst and exposed as reusable insight views
3. [`finance-briefings`](./finance-briefings/README.md): finance workflow pulses published in a form MapPhemar and Personal Agent can execute
4. [`yfinance`](./yfinance/README.md): a live market-data pulser with time-series output
5. [`llm`](./llm/README.md): local Ollama and cloud OpenAI chat pulsers
6. [`ads`](./ads/README.md): the ADS pulser as part of the SQLite pipeline demo

## Single-Command Launchers

Each runnable pulser demo folder now includes a `run-demo.sh` wrapper that starts the required local services from one terminal, opens a browser guide page with language selection, and opens the primary demo UI pages automatically.

Set `DEMO_OPEN_BROWSER=0` if you want the wrapper to stay in the terminal without opening browser tabs.

## Platform Quick Start

### macOS And Linux

From the repository root, create the virtual environment once, install requirements, then run any pulser wrapper such as `./demos/pulsers/file-storage/run-demo.sh`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Use a native Windows Python environment. From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

If browser tabs do not auto-open, keep the launcher running and open the printed `guide=` URL in a Windows browser.


## What This Demo Set Covers

- how a pulser registers with Plaza
- how to test pulses from the browser or with `curl`
- how to package a pulser as a small self-hosted service
- how different pulser families behave: storage, analyst insight, finance, LLM, and data-services

## Shared Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Each demo folder writes local runtime state under `demos/pulsers/.../storage/`.

## Demo Catalog

### [`file-storage`](./file-storage/README.md)

- Runtime: Plaza + `SystemPulser`
- External services: none
- What it proves: bucket creation, object save/load, and local-only pulser state

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime: Plaza + `PathPulser`
- External services: none for the structured view, local Ollama for the prompted news flow
- What it proves: how one analyst can publish both fixed research views and prompt-owned Ollama outputs through multiple reusable pulses, then expose them to another user through personal agent

### [`finance-briefings`](./finance-briefings/README.md)

- Runtime: Plaza + `FinancialBriefingPulser`
- External services: none in the local demo path
- What it proves: how an Attas-owned pulser can publish finance workflow steps as pulse-addressable building blocks so MapPhemar diagrams and Personal Agent can store, edit, and execute the same workflow graph

### [`yfinance`](./yfinance/README.md)

- Runtime: Plaza + `YFinancePulser`
- External services: outbound internet to Yahoo Finance
- What it proves: snapshot pulses, OHLC series pulses, and chart-friendly output payloads

### [`llm`](./llm/README.md)

- Runtime: Plaza + `OpenAIPulser` configured for OpenAI or Ollama
- External services: OpenAI API for cloud mode, local Ollama daemon for local mode
- What it proves: `llm_chat`, shared pulser editor UI, and provider-swappable LLM plumbing

### [`ads`](./ads/README.md)

- Runtime: ADS dispatcher + worker + pulser + boss UI
- External services: none in the SQLite demo path
- What it proves: `ADSPulser` on top of normalized data tables and how your own collectors flow into those pulses
