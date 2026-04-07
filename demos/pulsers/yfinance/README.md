# YFinance Pulser Demo

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

## Files In This Folder

- `plaza.agent`: local Plaza for this demo
- `yfinance.pulser`: local demo config for `YFinancePulser`
- `start-plaza.sh`: launch the Plaza
- `start-pulser.sh`: launch the pulser
- `run-demo.sh`: launch the full demo from one terminal and open the browser guide plus pulser UI

## Single-Command Launch

From the repository root:

```bash
./demos/pulsers/yfinance/run-demo.sh
```

This starts Plaza and `YFinancePulser` from one terminal, opens a browser guide page, and opens the pulser UI automatically.

Set `DEMO_OPEN_BROWSER=0` if you want the launcher to stay in the terminal only.

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Use a native Windows Python environment. From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher yfinance
```

If browser tabs do not auto-open, keep the launcher running and open the printed `guide=` URL in a Windows browser.


## Quickstart

Open two terminals from the repository root.

### Terminal 1: start Plaza

```bash
./demos/pulsers/yfinance/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8251`

### Terminal 2: start the pulser

```bash
./demos/pulsers/yfinance/start-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8252`
- it registers itself with the Plaza on `http://127.0.0.1:8251`

Note:

- this demo requires outbound internet access because the pulser fetches live data through `yfinance`
- Yahoo Finance may rate-limit or intermittently reject requests

## Try It In The Browser

Open:

- `http://127.0.0.1:8252/`

Suggested first pulses:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

Suggested params for `last_price`:

```json
{
  "symbol": "AAPL"
}
```

Suggested params for `ohlc_bar_series`:

```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Try It With Curl

Quote request:

```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC series request:

```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## What To Point Out

- the same pulser exposes both snapshot-style and time-series-style pulses
- `ohlc_bar_series` is compatible with the workbench chart demo and the technical-analysis path pulser
- the live provider can change underneath later while the pulse contract stays the same

## Build Your Own

If you want to extend this demo:

1. copy `yfinance.pulser`
2. adjust ports and storage paths
3. change or add supported pulse definitions if you want a smaller or more specialized catalog
