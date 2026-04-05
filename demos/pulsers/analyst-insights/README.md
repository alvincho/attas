# Analyst Insight Pulser Demo

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

`analyst-insights` now contains two related demos:

- a simple analyst-owned pulser that publishes a fixed research view as reusable structured pulses
- an advanced analyst-owned pulser that uses the analyst's own prompt pack plus Ollama to turn raw news from another agent into audience-specific insight pulses

## What This Demo Shows

- one analyst-owned pulser with multiple structured insight pulses
- a second analyst-owned pulser that sits on top of a separate news agent and a local Ollama agent
- a clean way to separate raw source data from analyst-authored prompts and final consumer-facing outputs
- a personal-agent walkthrough that shows the same stack from another user's point of view
- the exact files an analyst or PM would edit to publish their own view

## Files In This Folder

- `plaza.agent`: local Plaza for the analyst pulser demo
- `analyst-insights.pulser`: `PathPulser` config defining the public pulse catalog
- `analyst_insight_step.py`: shared transformation logic plus the seeded analyst coverage packet
- `news-wire.pulser`: local upstream news agent that publishes seeded `news_article` packets
- `news_wire_step.py`: seeded raw news packets returned by the upstream news agent
- `ollama.pulser`: local Ollama-backed `llm_chat` pulser for the analyst prompt demo
- `analyst-news-ollama.pulser`: composed analyst pulser that fetches news, applies analyst-owned prompts, calls Ollama, and normalizes the result into multiple pulses
- `analyst_news_ollama_step.py`: the analyst-owned prompt pack plus JSON normalization logic
- `start-plaza.sh`: launch the Plaza
- `start-pulser.sh`: launch the fixed structured analyst pulser
- `start-news-pulser.sh`: launch the upstream seeded news agent
- `start-ollama-pulser.sh`: launch the local Ollama pulser
- `start-analyst-news-pulser.sh`: launch the prompted analyst pulser
- `start-personal-agent.sh`: launch the personal agent UI for the consumer-view walkthrough
- `run-demo.sh`: launch the demo from one terminal and open the browser guide plus the main UI pages

## Single-Command Launch

From the repository root:

```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

That wrapper starts the lightweight structured flow by default.

To launch the advanced news + Ollama + personal-agent flow instead:

```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Set `DEMO_OPEN_BROWSER=0` if you want the launcher to stay in the terminal only.

## Platform Quick Start

### macOS And Linux

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

For the advanced path:

```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro. From the repository root inside WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

For the advanced path inside WSL:

```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

If browser tabs do not auto-open from WSL, keep the launcher running and open the printed `guide=` URL in a Windows browser.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## Demo 1: Structured Analyst Views

This is the local-only, no-LLM path.

Open two terminals from the repository root.

### Terminal 1: start Plaza

```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8266`

### Terminal 2: start the pulser

```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8267`
- it registers itself with the Plaza on `http://127.0.0.1:8266`

## Try It In The Browser

Open:

- `http://127.0.0.1:8267/`

Then test these pulses with `NVDA`:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

Suggested params for all four:

```json
{
  "symbol": "NVDA"
}
```

What you should see:

- `rating_summary` returns the headline call, target, confidence, and short summary
- `thesis_bullets` returns the positive thesis in bullet-ready form
- `risk_watch` returns the main risks plus what to monitor
- `scenario_grid` returns bull, base, and bear cases in one structured payload

## Try It With Curl

Headline rating:

```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

Thesis bullets:

```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

Risk watch:

```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## How An Analyst Customizes This Demo

There are two main edit points.

### 1. Change the actual research view

Edit:

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

This file contains the seeded `ANALYST_COVERAGE` packet. That is where you change:

- covered symbols
- analyst name
- rating labels
- target prices
- thesis bullets
- key risks
- bull/base/bear scenarios

### 2. Change the public pulse catalog

Edit:

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

That file controls:

- which pulses exist
- each pulse name and description
- input and output schemas
- tags and addresses

If you want to add a new insight pulse, copy one of the existing entries and point it at a new `insight_view`.

## Why This Pattern Is Useful

- portfolio tools can ask only for the `rating_summary`
- report builders can ask for `thesis_bullets`
- risk dashboards can ask for `risk_watch`
- valuation tools can ask for `scenario_grid`

That means the analyst publishes one service, but different consumers can pull exactly the slice they need.

## Where To Go Next

Once this local pulser shape makes sense, the next steps are:

1. add more covered symbols to the analyst coverage packet
2. add source steps before the final Python step if you want to blend your own view with YFinance, ADS, or LLM outputs
3. expose the pulser through a shared Plaza instead of only the local demo Plaza

## Demo 2: Analyst Prompt Pack + Ollama + Personal Agent

This second flow shows a more realistic analyst setup:

- one agent publishes raw `news_article` data
- a second agent exposes `llm_chat` through Ollama
- the analyst-owned pulser uses its own prompt pack to transform that raw news into multiple reusable pulses
- personal agent consumes the finished pulses from a different user's point of view

### Prerequisites For The Prompted Flow

Make sure Ollama is running locally and the model exists:

```bash
ollama serve
ollama pull qwen3:8b
```

Then open five terminals from the repository root.

### Terminal 1: start Plaza

If Demo 1 is still running, keep using the same Plaza.

```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8266`

### Terminal 2: start the upstream news agent

```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

Expected result:

- the news pulser starts on `http://127.0.0.1:8268`
- it registers itself with the Plaza on `http://127.0.0.1:8266`

### Terminal 3: start the Ollama pulser

```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

Expected result:

- the Ollama pulser starts on `http://127.0.0.1:8269`
- it registers itself with the Plaza on `http://127.0.0.1:8266`

### Terminal 4: start the prompted analyst pulser

Start this after the news and Ollama agents are already running, because the pulser validates its sample chains during startup.

```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

Expected result:

- the prompted analyst pulser starts on `http://127.0.0.1:8270`
- it registers itself with the Plaza on `http://127.0.0.1:8266`

### Terminal 5: start personal agent

```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

Expected result:

- personal agent starts on `http://127.0.0.1:8061`

### Try The Prompted Analyst Pulser Directly

Open:

- `http://127.0.0.1:8270/`

Then test these pulses with `NVDA`:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

Suggested params:

```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

What you should see:

- `news_desk_brief` turns the upstream articles into a PM-style stance and short note
- `news_monitoring_points` turns the same raw articles into watch-items and risk flags
- `news_client_note` turns the same raw articles into a cleaner client-facing note

The important point is that the analyst controls the prompts in one file while downstream users only see stable pulse interfaces.

### Use Personal Agent From Another User's View

Open:

- `http://127.0.0.1:8061/`

Then walk through this path:

1. Open `Settings`.
2. Go to the `Connection` tab.
3. Set the Plaza URL to `http://127.0.0.1:8266`.
4. Click `Refresh Plaza Catalog`.
5. Create a `New Browser Window`.
6. Put the browser window in `edit` mode.
7. Add a first plain pane and point it at `DemoAnalystNewsWirePulser -> news_article`.
8. Use pane params:

```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. Click `Get Data` so the user can see the raw articles.
10. Add a second plain pane and point it at `DemoAnalystPromptedNewsPulser -> news_desk_brief`.
11. Reuse the same params and click `Get Data`.
12. Add a third pane with either `news_monitoring_points` or `news_client_note`.

What you should see:

- one pane shows the raw upstream news from another agent
- the next pane shows the analyst's processed view
- the third pane shows how the same analyst prompt pack can publish a different surface for a different audience

That is the key consumer story: another user does not need to know the internal chain. They just browse Plaza, pick a pulse, and consume the finished analyst output.

## How An Analyst Customizes The Prompted Flow

There are three main edit points in Demo 2.

### 1. Change the upstream news packet

Edit:

- `demos/pulsers/analyst-insights/news_wire_step.py`

That is where you change the seeded articles the upstream source agent publishes.

### 2. Change the analyst's own prompts

Edit:

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

That file contains the analyst-owned prompt pack, including:

- prompt profile names
- audience and objective
- tone and writing style
- required JSON output contract

That is the fastest way to make the same raw news produce a different research voice.

### 3. Change the public pulse catalog

Edit:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

That file controls:

- which prompted pulses exist
- which prompt profile each pulse uses
- which upstream agents it calls
- the input and output schemas shown to downstream users

## Why The Advanced Pattern Is Useful

- the upstream news agent can be swapped later for YFinance, ADS, or an internal collector
- the analyst keeps ownership of the prompt pack instead of hard-coding one-off notes in a UI
- different consumers can use different pulses without knowing the full chain behind them
- personal agent becomes a clean consumer surface instead of the place where the logic lives
