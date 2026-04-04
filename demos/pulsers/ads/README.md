# ADS Pulser Demo

`ads` is the pulser-focused view of the SQLite ADS pipeline demo. Unlike the other pulser demos, `ADSPulser` is most useful when there is already normalized data in the backing store, so this guide intentionally reuses the full ADS stack from [`../../data-pipeline`](../../data-pipeline/README.md).

## What This Demo Covers

- how `ADSPulser` sits on top of normalized ADS tables
- how dispatcher and worker activity turns into pulser-visible data
- how your own collectors can land data into ADS tables and show up through existing pulses

## Setup

Follow the quickstart in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

That starts:

1. the ADS dispatcher
2. the ADS worker
3. the ADS pulser
4. the boss UI

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
