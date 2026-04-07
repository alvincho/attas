# ADS Pulser Demo

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

## What This Demo Covers

- how `ADSPulser` sits on top of normalized ADS tables
- how dispatcher and worker activity turns into pulser-visible data
- how your own collectors can land data into ADS tables and show up through existing pulses

## Setup

Follow the quickstart in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Or use the pulser-focused single-command wrapper from the repository root:

```bash
./demos/pulsers/ads/run-demo.sh
```

That wrapper launches the same SQLite ADS stack as `data-pipeline`, but opens a browser guide and tabs that focus on the pulser-first walkthrough.

That starts:

1. the ADS dispatcher
2. the ADS worker
3. the ADS pulser
4. the boss UI

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Use a native Windows Python environment. From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

If browser tabs do not auto-open, keep the launcher running and open the printed `guide=` URL in a Windows browser.


## First Pulser Checks

Once the sample jobs finish, open:

- `http://127.0.0.1:9062/`

Then test:

1. `security_master_lookup` with `{"symbol":"AAPL","limit":1}`
2. `daily_price_history` with `{"symbol":"AAPL","limit":5}`
3. `company_profile` with `{"symbol":"AAPL"}`
4. `news_article` with `{"symbol":"AAPL","number_of_articles":3}`

## Why ADS Is Different

The other pulser demos mostly read from a live provider or a local storage backend directly.

`ADSPulser` instead reads from the normalized tables written by the ADS pipeline:

- workers collect or transform source data
- the dispatcher persists normalized rows
- `ADSPulser` exposes those rows as queryable pulses

That makes it the right demo for explaining how to add your own source adapters.

## Add Your Own Source

The concrete walkthrough lives in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Use the custom examples here:

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

Those examples show how a user-defined collector can write into:

- `ads_news`, which becomes available through `news_article`
- `ads_daily_price`, which becomes available through `daily_price_history`
