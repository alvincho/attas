# LLM Pulser Demo

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
