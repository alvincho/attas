# Data Pipeline

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

`data-pipeline` is the advanced public demo. It runs the ADS stack locally with SQLite and mock collectors, so people can see job orchestration, worker execution, normalized storage, and a pulser on top of the collected tables without provisioning PostgreSQL or any outside APIs.

## What This Demo Shows

- a dispatcher queue for data collection jobs
- a worker polling for matching capabilities
- normalized ADS tables stored locally in SQLite
- a boss UI for issuing and monitoring jobs
- a pulser that re-exposes collected data
- a path for swapping the shipped live collectors out for your own source adapters

## Why This Demo Uses SQLite With Live Collectors

The production-style ADS configs in `ads/configs/` are aimed at a shared PostgreSQL deployment.

This demo keeps the live collectors but simplifies the storage side:

- SQLite keeps the setup local and simple
- the worker and dispatcher share one local ADS database file, which keeps the live SEC bulk stage compatible with the same demo store the pulser reads
- the same architecture is still visible, so builders can graduate to the production configs later
- some jobs call public internet sources, so first-run timings depend on network conditions and source responsiveness

## Files In This Folder

- `dispatcher.agent`: SQLite-backed ADS dispatcher config
- `worker.agent`: SQLite-backed ADS worker config
- `pulser.agent`: ADS pulser reading the demo data store
- `boss.agent`: boss UI config for issuing jobs
- `start-dispatcher.sh`: launch the dispatcher
- `start-worker.sh`: launch the worker
- `start-pulser.sh`: launch the pulser
- `start-boss.sh`: launch the boss UI

Related example source adapters and live-demo helpers live in:

- `ads/examples/custom_sources.py`: importable example job caps for user-defined news and price feeds
- `ads/examples/live_data_pipeline.py`: demo-oriented wrappers around the live SEC ADS pipeline

All runtime state is written under `demos/data-pipeline/storage/`.

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
./demos/data-pipeline/run-demo.sh
```

This starts the dispatcher, worker, pulser, and boss UI from one terminal, opens a browser guide page, and opens the boss plus pulser UIs automatically.

Set `DEMO_OPEN_BROWSER=0` if you want the launcher to stay in the terminal only.

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro. From the repository root inside WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

If browser tabs do not auto-open from WSL, keep the launcher running and open the printed `guide=` URL in a Windows browser.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## Quickstart

Open four terminals from the repository root.

### Terminal 1: start the dispatcher

```bash
./demos/data-pipeline/start-dispatcher.sh
```

Expected result:

- dispatcher starts on `http://127.0.0.1:9060`

### Terminal 2: start the worker

```bash
./demos/data-pipeline/start-worker.sh
```

Expected result:

- worker starts on `127.0.0.1:9061`
- it polls the dispatcher every two seconds

### Terminal 3: start the pulser

```bash
./demos/data-pipeline/start-pulser.sh
```

Expected result:

- ADS pulser starts on `http://127.0.0.1:9062`

### Terminal 4: start the boss UI

```bash
./demos/data-pipeline/start-boss.sh
```

Expected result:

- boss UI starts on `http://127.0.0.1:9063`

## First Run Walkthrough

Open:

- `http://127.0.0.1:9063/`

In the boss UI, submit these jobs in order:

1. `security_master`
   This refreshes the full U.S. listed universe from Nasdaq Trader, so it does not need a symbol payload.
2. `daily_price`
   Use the default payload for `AAPL`.
3. `fundamentals`
   Use the default payload for `AAPL`.
4. `financial_statements`
   Use the default payload for `AAPL`.
5. `news`
   Use the default SEC, CFTC, and BLS RSS feed list.

Use the default payload templates when they appear. `security_master`, `daily_price`, and `news` usually finish quickly. The first SEC-backed `fundamentals` or `financial_statements` run may take longer because it refreshes cached SEC archives under `demos/data-pipeline/storage/sec_edgar/` before mapping the requested company.

Then open:

- `http://127.0.0.1:9062/`

This is the ADS pulser for the same demo data store. It exposes the normalized ADS tables as pulses, which is the bridge from collection/orchestration into downstream consumption.

Suggested first pulser checks:

1. Run `security_master_lookup` with `{"symbol":"AAPL","limit":1}`
2. Run `daily_price_history` with `{"symbol":"AAPL","limit":5}`
3. Run `company_profile` with `{"symbol":"AAPL"}`
4. Run `financial_statements` with `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. Run `news_article` with `{"number_of_articles":3}`

That gives people the whole ADS loop: boss UI issues jobs, worker collects rows, SQLite stores normalized data, and `ADSPulser` exposes the result through queryable pulses.

## Add Your Own Data Source To ADSPulser

The important mental model is:

- your source plugs into the worker as a `job_capability`
- the worker writes normalized rows into ADS tables
- `ADSPulser` reads those tables and exposes them through pulses

If your source fits one of the existing ADS table shapes, you usually do not need to change `ADSPulser` at all.

### The Easiest Path: write into an existing ADS table

Use one of these table-to-pulse pairings:

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### Example: add a custom press-release feed

The repo now includes an example callable here:

- `ads/examples/custom_sources.py`

To wire it into the demo worker, add a capability name and a callable-backed job cap in `demos/data-pipeline/worker.agent`.

Add this capability name:

```json
"press_release_feed"
```

Add this job-capability entry:

```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

Then restart the worker and submit a job from the boss UI with a payload like:

```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

After that job completes, open the pulser UI on `http://127.0.0.1:9062/` and run:

```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

against the `news_article` pulse.

What you should see:

- the user-defined collector writes a normalized row into `ads_news`
- the raw input is still preserved in the job raw payload
- `ADSPulser` returns the new article through the existing `news_article` pulse

### Second example: add a custom price feed

If your source is closer to prices than news, the same pattern works with:

```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

That example writes rows into `ads_daily_price`, which means the result becomes queryable through `daily_price_history` immediately.

### When you should change ADSPulser itself

Change `ads/pulser.py` only when your source does not map cleanly onto one of the existing normalized ADS tables or you need a brand-new pulse shape.

In that case, the usual path is:

1. add or choose a storage table for the new normalized rows
2. add a new supported pulse entry in the pulser config
3. extend `ADSPulser.fetch_pulse_payload()` so that pulse knows how to read and shape the stored rows

If you are still designing the schema, start by storing the raw payload and inspect it through `raw_collection_payload` first. That keeps the source integration moving while you decide what the final normalized table should look like.

## What To Point Out In A Demo Call

- Jobs are queued and completed asynchronously.
- The worker is decoupled from the boss UI.
- The stored rows land in normalized ADS tables rather than one generic blob store.
- The pulser is a second interface layer on top of the collected data.
- Bringing in a new source usually means adding one worker job cap, not rebuilding the whole ADS stack.

## Build Your Own Instance

There are two natural upgrade paths from this demo.

### Keep The Local Architecture But Swap In Your Own Collectors

Edit `worker.agent` and replace the shipped live demo job caps with your own job caps or other ADS job-cap types.

For example:

- `ads.examples.custom_sources:demo_press_release_cap` shows how to land a custom article feed into `ads_news`
- `ads.examples.custom_sources:demo_alt_price_cap` shows how to land a custom price source into `ads_daily_price`
- the production configs in `ads/configs/worker.agent` show how live capabilities are wired for SEC, YFinance, TWSE, and RSS

### Move From SQLite To Shared PostgreSQL

Once the local demo proves the workflow, compare these demo configs with the production-style configs in:

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

The main difference is the pool definition:

- this demo uses `SQLitePool`
- the production-style configs use `PostgresPool`

## Troubleshooting

### Jobs stay queued

Check these three things:

- the dispatcher terminal is still running
- the worker terminal is still running
- the job capability name in the boss UI matches one advertised by the worker

### The boss UI loads but looks empty

Make sure the boss config still points at:

- `dispatcher_address = http://127.0.0.1:9060`

### You want a clean run or need to remove old mock rows

Stop the demo processes and remove `demos/data-pipeline/storage/` before starting again.

## Stop The Demo

Press `Ctrl-C` in each terminal window.
