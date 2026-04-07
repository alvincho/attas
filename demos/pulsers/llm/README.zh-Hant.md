# LLM Pulser 演示

## 翻譯版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 此資料夾中的檔案

- `plaza.agent`: 用於兩種 LLM pulser 變體的本地 Plaza
- `openai.pulser`: OpenAI 支援的 pulser 配置
- `ollama.pulser`: 以 Ollama 為後端的 pulser 配置
- `start-plaza.sh`: 啟動 Plaza
- `start-openai-pulser.sh`: 啟動 OpenAI demo pulser
- `start-ollama-pulser.sh`: 啟動 Ollama demo pulser
- `run-demo.sh`: 從一個終端機啟動完整演示，並打開瀏覽器指南以及所選的 pulser UI

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/pulsers/llm/run-demo.sh
```

預設情況下，當 `OPENAI_API_KEY` 存在時，封裝器會使用 OpenAI，否則會回退到 Ollama。

明確的提供者範例：
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

使用原生 Windows Python 環境。在 PowerShell 中從儲存庫根目錄執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher llm
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 快速入門

### 啟動 Plaza

從儲存庫根目錄開啟終端機：
```bash
./demos/pulsers/llm/start-plaza.sh
```

預期結果：

- Plaza 將在 `http://127.0.0.1:8261` 啟動

然後選擇一個提供者。

## 選項 1: OpenAI

請先設定您的 API 金鑰：
```bash
export OPENAI_API_KEY=your-key-here
```

然後啟動 pulser：
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

預期結果：

- pulser 會在 `http://127.0.0.1:8262` 啟動
- 它會向 `http://127.0.0.1:8261` 的 Plaza 進行註冊

建議的測試負載：
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

## 選項 2: Ollama

請確保 Ollama 正在本地運行，且配置的模型可用：
```bash
ollama serve
ollama pull qwen3:8b
```

然後啟動 pulser：
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

預期結果：

- pulser 會在 `http://127.0.0.1:8263` 啟動
- 它會向 `http://127.0.0.1:8261` 的 Plaza 進行註冊

建議的 curl 範例：
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## 在瀏覽器中嘗試

開啟任一：

- `http://127.0.0.1:8262/` 用於 OpenAI
- `http://127.0.0.1:8263/` 用於 Ollama

此 UI 讓您可以：

- 檢查 pulser 配置
- 執行 `llm_chat`
- 載入模型列表
- 使用本地提供者時檢查 Ollama 模型資訊

## 應注意的事項

- 同一個 pulse 合約可以建立在雲端或本地推論之上
- 在 OpenAI 與 Ollama 之間切換主要涉及配置，而非介面重新設計
- 這是用於解釋該儲存庫中由 pulser 支援的 LLM 工具的最簡單示範

## 打造您自己的版本

若要自訂此範例：

1. 複製 `openai.pulser` 或 `ollama.pulser`
2. 修改 `model`、`base_url`、連接埠以及儲存路徑
3. 如果其他工具或 UI 依賴它，請保持 `llm_chat` pulse 穩定
