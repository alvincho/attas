# Pulser Demo Set

`demos/pulsers` is a focused demo catalog for people who want to understand the repo's pulser patterns without starting the full workbench first.

## Start Here

Use these in this order if you are learning the pulser model for the first time:

1. [`file-storage`](./file-storage/README.md): the safest local-only pulser demo
2. [`analyst-insights`](./analyst-insights/README.md): a pulser owned by an analyst and exposed as reusable insight views
3. [`yfinance`](./yfinance/README.md): a live market-data pulser with time-series output
4. [`llm`](./llm/README.md): local Ollama and cloud OpenAI chat pulsers
5. [`ads`](./ads/README.md): the ADS pulser as part of the SQLite pipeline demo

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

- Runtime: Plaza + `FileStoragePulser`
- External services: none
- What it proves: bucket creation, object save/load, and local-only pulser state

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime: Plaza + `PathPulser`
- External services: none for the structured view, local Ollama for the prompted news flow
- What it proves: how one analyst can publish both fixed research views and prompt-owned Ollama outputs through multiple reusable pulses, then expose them to another user through personal agent

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
