# LLM Pulser 演示

## 翻译版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 此文件夹中的文件

- `plaza.agent`: 用于两种 LLM pulser 变体的本地 Plaza
- `openai.pulser`: OpenAI 支援的 pulser 配置
- `ollama.pulser`: 以 Ollama 为后端的 pulser 配置
- `start-plaza.sh`: 启动 Plaza
- `start-openai-pulser.sh`: 启动 OpenAI demo pulser
- `start-ollama-pulser.sh`: 启动 Ollama demo pulser
- `run-demo.sh`: 从一个终端机启动完整演示，并打开浏览器指南以及所选的 pulser UI

## 单一命令启动

从仓库根目录：
```bash
./demos/pulsers/llm/run-demo.sh
```

默认情况下，当 `OPENAI_API_KEY` 存在时，封装器将使用 OpenAI，否则将回退到 Ollama。

明确的提供者示例：
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

请搭配 Ubuntu 或其他 Linux 发行版使用 WSL2。在 WSL 内的仓库根目录下执行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

如果浏览器标签页无法从 WSL 自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

原生 PowerShell / Command Prompt 封装器尚未提交，因此目前支持的 Windows 路径是 WSL2。

## 快速入门

### 启动 Plaza

从仓库根目录打开终端：
```bash
./demos/pulsers/llm/start-plaza.sh
```

预期结果：

- Plaza 将在 `http://127.0.0.1:8261` 启动

然后选择一个提供者。

## 选项 1: OpenAI

请先设置您的 API 密钥：
```bash
export OPENAI_API_KEY=your-key-here
```

然后启动 pulser：
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

预期结果：

- pulser 会在 `http://127.0.0.1:8262` 启动
- 它会向 `http://127.0.0.1:8261` 的 Plaza 进行注册

建议的测试负载：
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Curl 範例：
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## 选项 2: Ollama

请确保 Ollama 正在本地运行，且配置的模型可用：
```bash
ollama serve
ollama pull qwen3:8b
```

然后启动 pulser：
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

预期结果：

- pulser 会在 `http://127.0.0.1:8263` 启动
- 它会向 `http://127.0.0.1:8261` 的 Plaza 进行注册

建议的 curl 示例：
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## 在浏览器中尝试

打开任一：

- `http://127.0.0.1:8262/` 用于 OpenAI
- `http://127.0.0.1:8263/` 用于 Ollama

此 UI 让您可以：

- 检查 pulser 配置
- 运行 `llm_chat`
- 加载模型列表
- 使用本地提供者时检查 Ollama 模型信息

## 应当注意的事项

- 同一个 pulse 合约可以建立在云端或本地推理之上
- 在 OpenAI 与 Ollama 之间切换主要涉及配置，而非界面重新设计
- 这是用于解释该仓库中由 pulser 支持的 LLM 工具的最简单演示

## 打造您自己的版本

若要自定义此示例：

1. 复制 `openai.pulser` 或 `ollama.pulser`
2. 修改 `model`、`base_url`、端口以及儲存路徑
3. 如果其他工具或 UI 依赖它，请保持 `llm_chat` pulse 稳定
