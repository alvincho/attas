# Demo 圖表函式庫

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

## 平台說明

此資料夾提供的是 JSON 資產，而非獨立的啟動器。

### macOS 與 Linux

請先啟動其中一個配對的示範程式，然後將這些檔案載入至 MapPhemar 或 Personal Agent：
```bash
./demos/personal-research-workbench/run-demo.sh
```

您也可以啟動：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

請為配對的 demo 啟動器使用原生 Windows Python 環境，例如 `py -3 -m scripts.demo_launcher analyst-insights` 與 `py -3 -m scripts.demo_launcher finance-briefings`。在堆疊運行後，如果分頁沒有自動開啟，請在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 此資料夾包含什麼

這裡有兩組範例：

- 技術分析圖表：將 OHLC 市場數據轉換為指標序列
- 以 LLM 為導向的分析師圖表：將原始市場新聞轉換為結構化研究筆記
- 金融工作流圖表：將標準化的研究輸入轉換為簡報、出版物及 NotebookLM 匯出套件

## 此資料夾中的檔案

### 技術分析

- `ohlc-to-sma-20-diagram.json`: `輸入 -> OHLC K線 -> SMA 20 -> 輸出`
- `ohlc-to-ema-50-diagram.json`: `輸入 -> OHLC K線 -> EMA 50 -> 輸出`
- `ohlc-to-macd-histogram-diagram.json`: `輸入 -> OHLC K線 -> MACD 柱狀圖 -> 輸出`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `輸入 -> OHLC K線 -> 布林帶寬 -> 輸出`
- `ohlc-to-adx-14-diagram.json`: `輸入 -> OHLC K線 -> ADX 14 -> 輸出`
- `ohlc-to-obv-diagram.json`: `輸入 -> OHLC K線 -> OBV -> 輸出`

### LLM / 分析師研究

- `analyst-news-desk-brief-diagram.json`: `輸入 -> 新聞台簡報 -> 輸出`
- `analyst-news-monitoring-points-diagram.json`: `輸入 -> 監控點 -> 輸出`
- `analyst-news-client-note-diagram.json`: `輸入 -> 客戶筆記 -> 輸出`

### 金融工作流套件

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `輸入 -> 準備早間背景 -> 金融步驟 Pulses -> 組裝簡報 -> 報告 Phema + NotebookLM 套件 -> 輸出`
- `finance-watchlist-check-notebooklm-diagram.json`: `輸入 -> 準備自選股背景 -> 金融步驟 Pulses -> 組裝簡報 -> 報告 Phema + NotebookLM 套件 -> 輸出`
- `finance-research-roundup-notebooklm-diagram.json`: `輸入 -> 準備研究背景 -> 金融步驟 Pulses -> 組裝簡報 -> 報告 Phema + NotebookLM 套件 -> 輸出`

這三個儲存的 Phemas 保持獨立以便編輯，但它們共享相同的 workflow-entry pulse，並透過節點 `paramsText.workflow_name` 來區分工作流。

## 執行時假設

這些圖表保存了具體的本地位址，因此在預期的 demo stack 可用時，無需額外編輯即可運行。

### 技術分析圖表

指標圖表假設：

- Plaza 位址為 `http://127.0.0.1:8241`
- `YFinancePulser` 位址為 `http://127.0.0.1:8243`
- `TechnicalAnalysisPulser` 位址為 `http://127.0.0.1:8244`

這些圖表所引用的 pulser 配置位於：

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.hyper`

### LLM / 分析師圖表

面向 LLM 的圖表假設：

- Plaza 位址為 `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` 位址為 `http://127.0.0.1:8270`

該 prompted analyst pulser 本身依賴於：

- `news-wire.pulser` 位址為 `http://127.0.0.1:8268`
- `ollama.pulser` 位址為 `http://127.0.0.1:8269`

這些 demo 檔案位於：

- `demos/pulsers/analyst-insights/`

### 金融工作流圖表

金融工作流圖表假設：

- Plaza 位址為 `127.0.0.1:8266`
- `DemoFinancialBriefingPulser` 位址為 `http://127.0.0.1:8271`

該 demo pulser 是一個 Attas 擁有的 `FinancialBriefingPulser`，其後端為：

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

這些圖表在 MapPhemar 以及嵌入的 Personal Agent MapPhemar 路由中均可編輯，因為它們是普通的以圖表為後端的 Phema JSON 檔案。

## 快速入門

### 選項 1：將檔案載入 MapPhemar

1. 開啟一個 MapPhemar 編輯器實例。
2. 從此資料夾中載入其中一個 JSON 檔案。
3. 確認儲存的 `plazaUrl` 與 pulser 位址與您的本地環境相符。
4. 使用下方其中一個範例 payload 執行 `Test Run`。

如果您的服務使用了不同的連接埠或名稱，請編輯：

- `meta.map_phemar.diagram.plazaUrl`
- 每個節點的 `pulserName`
- 每個節點的 `pulserAddress`

### 選項 2：將其作為種子檔案使用

您也可以將這些 JSON 檔案複製到 `phemas/` 目錄下的任何 MapPhemar 池中，並像 personal-research-workbench 範例一樣，透過 agent UI 進行載入。

## 範例輸入

### 技術分析圖表

使用如下負載：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

預期結果：

- `OHLC Bars` 步驟會擷取歷史 K 線序列
- 指標節點會計算 `values` 陣列
- 最終輸出會回傳時間戳記/數值對

### LLM / 分析師圖表

使用如下酬載：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

預期結果：

- 由 prompt 驅動的 analyst pulser 獲取原始新聞
- prompt pack 將該新聞轉換為結構化的 analyst 視圖
- 輸出返回可直接用於研究的欄位，例如 `desk_note`、`monitor_now` 或 `client_note`

### 金融工作流圖表

使用如下 payload：
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

預期結果：

- 工作流上下文節點種子選定的金融工作流
- 中間金融節點構建來源、引用、事實、風險、催化劑、衝突、要點、問題和摘要區塊
- 組裝節點構建 `attas.finance_briefing` 負載
- 報告節點將該負載轉換為靜態 Phema
- NotebookLM 節點從相同的負載生成導出構件
- 最終輸出合併所有三個結果，以便在 MapPhemar 或 Personal Agent 中進行檢查

## 目前編輯器限制

這些金融工作流在不新增節點類型的情況下，符合目前的 MapPhemar 模型。

仍適用兩項重要的執行時規則：

- `Input` 必須恰好連接到一個下游形狀
- 每個可執行的非分支節點必須引用一個 pulse 以及一個可達到的 pulser

這意味著工作流的分叉（fan-out）必須發生在第一個可執行節點之後，且如果您希望圖表能夠端到端地運行，工作流步驟仍需要作為由 pulser 託管的 pulse 來公開。

## 相關演示

如果您想要運行支援服務，而不僅僅是查看圖表：

- `demos/personal-research-workbench/README.md`: 包含種子 RSI 範例的可視化圖表工作流
- `demos/pulsers/analyst-insights/README.md`: LLM 導向圖表所使用的提示分析師新聞堆疊
- `demos/pulsers/llm/README.md`: 用於 OpenAI 和 Ollama 的獨立 `llm_chat` pulser 演示

## 驗證

這些檔案已包含在儲存庫測試中：
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

該測試套件會驗證已儲存的圖表是否能針對模擬或參考的 pulser 流程進行端到端執行。
