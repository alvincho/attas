# 公開演示指南

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

如果您想先嘗試其中一個演示，請按以下順序使用：

1. [`hello-plaza`](./hello-plaza/README.md)：最輕量級的多代理發現演示。
2. [`pulsers`](./pulsers/README.md)：專注於文件存儲、YFinance、LLM 和 ADS pulsers 的演示。
3. [`personal-research-workbench`](./personal-research-workbench/README.md)：最具視覺化的產品導覽。
4. [`data-pipeline`](./data-pipeline/README.md)：一個具有 boss UI 和 pulser 的本地 SQLite 支援 ADS 流水線。

## 單指令啟動器

每個可執行的 demo 資料夾現在都包含一個 `run-demo.sh` 封裝腳本，它可以從單個終端機啟動所需的服務，開啟一個帶有語言選擇功能的瀏覽器指南頁面，並自動開啟主要的 demo UI 頁面。

如果您希望封裝腳本僅停留在終端機而不開啟瀏覽器分頁，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

在儲存庫根目錄下，只需執行一次建立虛擬環境並安裝依賴項，接著即可執行任何 demo 封裝腳本，例如 `./demos/hello-plaza/run-demo.sh`：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中進入儲存庫根目錄後執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

在 macOS 和 Linux 上，已提交的 `run-demo.sh` 封裝器仍可作為相同 Python 啟動器的便利封裝器使用。

## 共用設定

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

您通常會希望開啟 2-4 個終端機視窗，因為大多數 demo 都會啟動一些長時間運行的程序。

這些 demo 資料夾會將其運行狀態寫入 `demos/.../storage/`。該狀態會被 git 忽略，因此大家可以自由地進行實驗。

## Demo 目錄

### [`hello-plaza`](./hello-plaza/README.md)

- 目標對象：初次開發者
- 執行環境：Plaza + worker + 面向瀏覽器的 用戶代理
- 外部服務：無
- 證明內容：agent 註冊、發現以及簡單的瀏覽器 UI

### [`pulsers`](./pulsers/README.md)

- 目標對象：想要小型、直接 pulser 範例的開發者
- 執行環境：小型 Plaza + pulser 堆疊，以及一個重用 SQLite pipeline 的 ADS pulser 指南
- 外部服務：檔案儲存無外部服務，YFinance 與 OpenAI 需要出站網路，Ollama 使用本地 Ollama daemon
- 證明內容：獨立的 pulser 打包、測試、特定提供者的 pulse 行為、分析師如何發布自己的結構化或由 prompt 驅動的洞察 pulse，以及從消費者角度看這些 pulse 在個人 agent 中的呈現方式

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- 目標對象：想要更強大的產品演示的人
- 執行環境：React/FastAPI workbench + 本地 Plaza + 本地檔案儲存 pulser + 選用 YFinance pulser + 選用 technical-analysis pulser + 預置圖表儲存
- 外部服務：儲存流程無外部服務，YFinance 圖表流程與即時 OHLC-to-RSI 圖表流程需要出站網路
- 證明內容：工作區、佈局、Plaza 瀏覽、圖表渲染，以及從更豐富的 UI 進行圖表驅動的 pulser 執行

### [`data-pipeline`](./data-pipeline/README.md)

- 目標對象：正在評估編排與正規化數據流的開發者
- 執行環境：ADS dispatcher + worker + pulser + boss UI
- 外部服務：在 demo 設定中無外部服務
- 證明內容：隊列作業、worker 執行、正規化儲存、透過 pulser 重新暴露，以及接入自定義數據源的路徑

## 用於公開託管

這些演示旨在於本地運行成功後，易於進行自我託管。如果您公開發布它們，最安全的預設值是：

- 將託管的 demos 設為唯讀，或按排程重置它們
- 在第一個公開版本中，請關閉 API 支援或付費的整合功能
- 指引人員查看 demo 使用的設定檔，以便他們可以直接進行 fork
- 在 live URL 旁邊包含來自 demo README 的確切本地命令
