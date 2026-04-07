# Pulser 演示集

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

## 從這裡開始

如果您是第一次學習 pulser 模型，請按此順序使用：

1. [`file-storage`](./file-storage/README.md)：最安全的僅限本地的 pulser 演示
2. [`analyst-insights`](./analyst-insights/README.md)：由分析師擁有並以可重複使用的洞察視圖形式公開的 pulser
3. [`finance-briefings`](./finance-briefings/README.md)：以 MapPhemar 和 Personal Agent 可以執行的形式發佈的金融工作流 pulses
4. [`yfinance`](./yfinance/README.md)：具有時間序列輸出的即時市場數據 pulser
5. [`llm`](./llm/README.md)：本地 Ollama 和雲端 OpenAI 對話 pulser
6. [`ads`](./ads/README.md)：作為 SQLite 流水線演示一部分的 ADS pulser

## 單指令啟動器

每個可執行的 pulser demo 資料夾現在都包含一個 `run-demo.sh` 封裝腳本，它可以從單個終端機啟動所需的本地服務，開啟帶有語言選擇的瀏覽器指南頁面，並自動開啟主要的 demo UI 頁面。

如果您希望封裝腳本保持在終端機中而不開啟瀏覽器分頁，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

在儲存庫根目錄下，先建立虛擬環境，安裝依賴項目，然後執行任何 pulser 封裝腳本，例如 `./demos/pulsers/file-storage/run-demo.sh`：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中從儲存庫根目錄執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 此示範集涵蓋的內容

- pulser 如何在 Plaza 進行註冊
- 如何透過瀏覽器或使用 `curl` 測試Pulse (pulses)
- 如何將 pulser 打包成一個小型自託管服務
- 不同 pulser 系列的行為：儲存、分析師洞察、金融、LLM與資料服務

## 共用設定

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

每個 demo 資料夾都會將本地執行時狀態寫入 `demos/pulsers/.../storage/` 下。

## Demo 目錄

### [`file-storage`](./file-storage/README.md)

- 執行環境：Plaza + `SystemPulser`
- 外部服務：無
- 證明內容：儲存桶建立、物件儲存/載入，以及僅限本地的 pulser 狀態

### [`analyst-insights`](./analyst-insights/README.md)

- 執行環境：Plaza + `PathPulser`
- 外部服務：結構化視圖無外部服務，提示驅動的新聞流使用本地 Ollama
- 證明內容：一位分析師如何透過多個可重複使用的 pulses，同時發布固定的研究視圖和由 prompt 擁有的 Ollama 輸出，然後透過個人代理（personal agent）將其展示給另一位使用者

### [`finance-briefings`](./finance-briefings/README.md)

- 執行環境：Plaza + `FinancialBriefingPulser`
- 外部服務：在本地 demo 路徑中無外部服務
- 證明內容：Attas 擁有的 pulser 如何將金融工作流步驟發布為 pulse 可定址的構建塊，使得 MapPhemar 圖表和 Personal Agent 可以儲存、編輯並執行相同的 workflow 圖

### [`yfinance`](./yfinance/README.md)

- 執行環境：Plaza + `YFinancePulser`
- 外部服務：連接至 Yahoo Finance 的外部網路
- 證明內容：快照 pulses、OHLC 系列 pulses 以及適合圖表的輸出負載

### [`llm`](./llm/README.md)

- 執行環境：配置為 OpenAI 或 Ollama 的 Plaza + `OpenAIPulser`
- 外部服務：雲端模式使用 OpenAI API，本地模式使用本地 Ollama daemon
- 證明內容：`llm_chat`、共享的 pulser 編輯器 UI，以及可切換供應商的 LLM 管道

### [`ads`](./ads/README.md)

- 執行環境：ADS dispatcher + worker + pulser + boss UI
- 外部服務：在 SQLite demo 路徑中無外部服務
- 證明內容：基於正規化數據表的 `ADSPulser`，以及您自己的收集器如何流入這些 pulses
