# LLM Pulser Demo

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

`llm` packages the shared `OpenAIPulser` editor in two modes:

- OpenAI cloud mode
- Ollama local mode

Both expose the same `llm_chat` pulse shape, which makes this demo useful for showing provider swaps with minimal client changes.

## Files In This Folder

- `plaza.agent`: local Plaza for both LLM pulser variants
- `openai.pulser`: OpenAI-backed pulser config
- `ollama.pulser`: Ollama-backed pulser config
- `start-plaza.sh`: launch the Plaza
- `start-openai-pulser.sh`: launch the OpenAI demo pulser
- `start-ollama-pulser.sh`: launch the Ollama demo pulser
- `run-demo.sh`: launch the full demo from one terminal and open the browser guide plus the selected pulser UI

## Single-Command Launch

From the repository root:

```bash
./demos/pulsers/llm/run-demo.sh
```

By default the wrapper uses OpenAI when `OPENAI_API_KEY` is present and falls back to Ollama otherwise.

Explicit provider examples:

```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
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
./demos/pulsers/llm/run-demo.sh
```

### Windows

Use WSL2 with Ubuntu or another Linux distro. From the repository root inside WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

If browser tabs do not auto-open from WSL, keep the launcher running and open the printed `guide=` URL in a Windows browser.

Native PowerShell / Command Prompt wrappers are not checked in yet, so WSL2 is the supported Windows path today.


## Quickstart

### Start Plaza

Open a terminal from the repository root:

```bash
./demos/pulsers/llm/start-plaza.sh
```

Expected result:

- Plaza starts on `http://127.0.0.1:8261`

Then choose one provider.

## Option 1: OpenAI

Set your API key first:

```bash
export OPENAI_API_KEY=your-key-here
```

Then start the pulser:

```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8262`
- it registers itself with the Plaza on `http://127.0.0.1:8261`

Suggested test payload:

```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Curl example:

```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## Option 2: Ollama

Make sure Ollama is running locally and the configured model is available:

```bash
ollama serve
ollama pull qwen3:8b
```

Then start the pulser:

```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

Expected result:

- the pulser starts on `http://127.0.0.1:8263`
- it registers itself with the Plaza on `http://127.0.0.1:8261`

Suggested curl example:

```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## Try It In The Browser

Open either:

- `http://127.0.0.1:8262/` for OpenAI
- `http://127.0.0.1:8263/` for Ollama

The UI lets you:

- inspect the pulser config
- run `llm_chat`
- load model lists
- inspect Ollama model info when using the local provider

## What To Point Out

- the same pulse contract can sit on top of cloud or local inference
- moving between OpenAI and Ollama is mostly config, not interface redesign
- this is the simplest demo for explaining pulser-backed LLM tools in the repo

## Build Your Own

To customize the demo:

1. copy `openai.pulser` or `ollama.pulser`
2. change `model`, `base_url`, ports, and storage paths
3. keep the `llm_chat` pulse stable if other tools or UIs depend on it
