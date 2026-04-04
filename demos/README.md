# Public Demo Guides

This folder packages public-facing demos for the FinMAS workspace. Each demo is local-first, documented step by step, and organized so a new builder can copy the config files, run the stack, and turn it into their own instance.

## Start Here

If you are choosing one demo to try first, use them in this order:

1. [`hello-plaza`](./hello-plaza/README.md): the lightest multi-agent discovery demo.
2. [`pulsers`](./pulsers/README.md): focused demos for file storage, YFinance, LLM, and ADS pulsers.
3. [`personal-research-workbench`](./personal-research-workbench/README.md): the most visual product walkthrough.
4. [`data-pipeline`](./data-pipeline/README.md): a local SQLite-backed ADS pipeline with boss UI and pulser.

## Shared Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

You will usually want 2-4 terminal windows open, because most demos start a few long-running processes.

These demo folders write their runtime state under `demos/.../storage/`. That state is ignored by git so people can experiment freely.

## Demo Catalog

### [`hello-plaza`](./hello-plaza/README.md)

- Audience: first-time builders
- Runtime: Plaza + worker + browser-facing user agent
- External services: none
- What it proves: agent registration, discovery, and a simple browser UI

### [`pulsers`](./pulsers/README.md)

- Audience: builders who want small, direct pulser examples
- Runtime: small Plaza + pulser stacks, plus an ADS pulser guide that reuses the SQLite pipeline
- External services: none for file storage, outbound internet for YFinance and OpenAI, local Ollama daemon for Ollama
- What it proves: standalone pulser packaging, testing, provider-specific pulse behavior, how analysts can publish their own structured or prompt-driven insight pulses, and how those pulses look inside personal agent from a consumer point of view

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- Audience: people who want a stronger product demo
- Runtime: React/FastAPI workbench + local Plaza + local file-storage pulser + optional YFinance pulser + optional technical-analysis pulser + seeded diagram storage
- External services: none for the storage flow, outbound internet for the YFinance chart flow and the live OHLC-to-RSI diagram flow
- What it proves: workspaces, layouts, Plaza browsing, chart rendering, and diagram-driven pulser execution from a richer UI

### [`data-pipeline`](./data-pipeline/README.md)

- Audience: builders evaluating orchestration and normalized data flows
- Runtime: ADS dispatcher + worker + pulser + boss UI
- External services: none in the demo setup
- What it proves: queued jobs, worker execution, normalized storage, re-exposure through a pulser, and the path for plugging in your own data sources

## For Public Hosting

These demos are designed to be easy to self-host after a local run succeeds. If you publish them publicly, the safest defaults are:

- make the hosted demos read-only or reset them on a schedule
- keep API-backed or paid integrations off in the first public version
- point people at the config files used by the demo so they can fork them directly
- include the exact local commands from the demo README next to the live URL
