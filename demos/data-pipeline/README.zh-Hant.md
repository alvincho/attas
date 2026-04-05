# 資料流水線

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

## 此示範展示了什麼

- 一個用於數據收集任務的分派隊列
- 一個正在輪詢匹配能力的 worker
- 儲存在本地 SQLite 中的標準化 ADS 表
- 一個用於發布和監控任務的 boss UI
- 一個重新展示已收集數據的 pulser
- 一條將內置的 live collectors 替換為您自己的來源適配器的路徑

## 為什麼此 Demo 在即時收集器中使用 SQLite

`ads/configs/` 中的生產級 ADS 配置旨在用於共享的 PostgreSQL 部署。

此 Demo 保留了即時收集器，但簡化了儲存端：

- SQLite 讓設置保持在本地且簡單
- worker 和 dispatcher 共用一個本地 ADS 資料庫檔案，這使得即時 SEC 批量階段與 pulser 讀取的同一個 demo 存儲保持相容
- 架構依然清晰可見，因此開發者稍後可以遷移到生產級配置
- 部分作業會調用公開網路來源，因此首次運行的耗時取決於網路條件和來源的響應速度

## 此資料夾中的檔案

- `dispatcher.agent`: 以 SQLite 為後端的 ADS dispatcher 配置
- `worker.agent`: 以 SQLite 為後端的 ADS worker 配置
- `pulser.agent`: 讀取 demo 資料儲存庫的 ADS pulser
- `boss.agent`: 用於發布作業的 boss UI 配置
- `start-dispatcher.sh`: 啟動 dispatcher
- `start-worker.sh`: 啟動 worker
- `start-pulser.sh`: 啟動 pulser
- `start-boss.sh`: 啟動 boss UI

相關的範例來源適配器 (source adapters) 與 live-demo 輔助工具位於：

- `ads/examples/custom_sources.py`: 可匯入的範例作業容量 (job caps)，用於使用者定義的新聞與價格饋送
- `ads/examples/live_data_pipeline.py`: 針對 live SEC ADS pipeline 的 demo 導向封裝器

所有執行時狀態皆寫入於 `demos/data-pipeline/storage/`。

## 前置條件

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/data-pipeline/run-demo.sh
```

這會從單個終端機啟動 dispatcher、worker、pulser 和 boss UI，開啟瀏覽器指南頁面，並自動開啟 boss plus pulser UI。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

請搭配 Ubuntu 或其他 Linux 發行版使用 WSL2。在 WSL 內的儲存庫根目錄下：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

如果瀏覽器分頁無法從 WSL 自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

原生 PowerShell / Command Prompt 封裝器尚未提交，因此目前支援的 Windows 路徑是 WSL2。

## 快速入門

從儲存庫根目錄開啟四個終端機。

### 終端機 1：啟動 dispatcher
```bash
./demos/data-pipeline/start-dispatcher.sh
```

預期結果：

- dispatcher 啟動於 `http://127.0.0.1:9060`

### 終端機 2：啟動 worker
```bash
./demos/data-pipeline/start-worker.sh
```

預期結果：

- worker 啟動於 `127.0.0.1:9061`
- 它每兩秒輪詢一次 dispatcher

### 終端機 3：啟動 pulser
```bash
./demos/data-pipeline/start-pulser.sh
```

預期結果：

- ADS pulser 啟動於 `http://127.0.0.1:9062`

### 終端機 4：啟動 boss UI
```bash
./demos/data-pipeline/start-boss.sh
```

預期結果：

- boss UI 啟動於 `http://127.0.0.1:9063`

## 首次運行指南

開啟：

- `http://127.0.0.1:9063/`

在 boss UI 中，依序提交以下作業：

1. `security_master`
   此作業會從 Nasdaq Trader 重新整理完整的美國上市股票範圍，因此不需要 symbol 負載。
2. `daily_prime`
   使用 `AAPL` 的預設負載。
3. `fundamentals`
   使用 `AAPL` 的預設負載。
4. `financial_statements`
   使用 `AAPL` 的預設負載。
5. `news`
   使用預設的 SEC、CFTC 和 BLS RSS feed 列表。

當出現時，請使用預設的負載模板。`security_master`、`daily_price` 和 `news` 通常會很快完成。第一個由 SEC 支持的 `fundamentals` 或 `financial_statements` 運行可能需要較長時間，因為它在映射請求的公司之前，會先重新整理 `demos/data-pipeline/storage/sec_edgar/` 下的 SEC 快取存檔。

接著開啟：

- `http://127.0.0.1:9062/`

這是針對相同 demo 資料儲存的 ADS pulser。它將標準化後的 ADS 表格作為 pulses 暴露出來，這是從收集/編排到下游消費之間的橋樑。

建議的首次 pulser 檢查：

1. 執行 `security_master_lookup` 並使用 `{"symbol":"AAPL","limit":1}`
2. 執行 `daily_price_history` 並使用 `{"symbol":"AAPL","limit":5}`
3. 執行 `company_profile` 並使用 `{"symbol":"AAPL"}`
4. 執行 `financial_statements` 並使用 `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. 執行 `news_article` 並使用 `{"number_of_articles":3}`

這讓使用者了解整個 ADS 迴圈：boss UI 發出作業，worker 收集行，SQLite 儲存標準化數據，而 `ADSPulser` 透過可查詢的 pulses 呈現結果。

## 為 ADSPulser 新增您自己的資料來源

重要的心理模型是：

- 您的來源作為 `job_capability` 接入 worker
- worker 將正規化後的列寫入 ADS 表格中
- `ADSPulser` 讀取這些表格並透過 pulses 進行公開

如果您的來源符合現有的 ADS 表格結構之一，您通常完全不需要更改 `ADSPulser`。

### 最簡單的路徑：寫入現有的 ADS 表格

使用以下表格與 pulse 的配對之一：

- `ads_security_can_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### 範例：新增自定義新聞稿饋送

該儲存庫現在包含一個可呼叫的範例於此：

- `ads/examples/custom_sources.py`

若要將其連接到 demo worker，請在 `demos/data-pipeline/worker.agent` 中新增一個能力名稱（capability name）和一個由可呼叫物件支援的 job cap。

新增此能力名稱：
```json
"press_release_feed"
```

新增此 job-capability 項目：
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

然後重新啟動 worker，並從 boss UI 提交一個包含如下 payload 的任務：
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

該工作完成後，請開啟 `http://127.0.0.1:9062/` 上的 Pulser UI 並執行：
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

針對 `news_article` pulse。

您應該會看到：

- 使用者定義的收集器將正規化後的列寫入 `ads_news`
- 原始輸入仍保留在作業的原始酬載（raw payload）中
- `ADSPulser` 透過現有的 `news_article` pulse 回傳新文章

### 第二個範例：新增自定義價格饋送

如果您的來源與價格的關聯性比新聞更近，同樣的模式也適用於：
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

該範例將資料列寫入 `ads_daily_price`，這意味著結果可以立即透過 `daily_price_history` 進行查詢。

### 何時您應該修改 ADSPulser 本身

僅當您的來源無法清晰地映射到現有的 ADS 正規化資料表中，或者您需要一種全新的Pulse形狀（pulse shape）時，才修改 `ads/pulser.py`。

在這種情況下，通常的流程是：

1. 為新的正規化資料列新增或選擇一個儲存表
2. 在 pulser 配置中新增一個支援的Pulse條目
3. 擴展 `ADSPulser.fetch_pulse_payload()`，使Pulse能夠知道如何讀取並塑形儲存的資料列

如果您仍在設計 Schema，請先從儲存原始 Payload 開始，並首先透過 `raw_collection_payload` 進行檢查。這樣可以在您決定最終正規化資料表的結構時，保持來源整合的進度。

## 在 Demo 展示中應重點說明之處

- 工作任務以非同步方式進行排隊與完成。
- Worker 與 Boss UI 是解耦的。
- 儲存的資料列會進入正規化的 ADS 表格，而非單一的通用 Blob 儲存空間。
- Pulser 是建立在收集到的資料之上的第二層介面。
- 引入新來源通常只需增加一個 Worker 任務上限，而不需要重建整個 ADS 堆疊。

## 建立您自己的實例

從此示範中有兩條自然的升級路徑。

### 保留本地架構但更換您自己的收集器

編輯 `worker.agent` 並將隨附的 live demo job caps 替換為您自己的 job caps 或其他 ADS job-cap 類型。

例如：

- `ads.examples.custom_sources:demo_press_release_cap` 展示了如何將自定義文章饋送匯入 `ads_news`
- `ads.essentials.custom_sources:demo_alt_price_cap` 展示了如何將自定義價格來源匯入 `ads_daily_price`
- `ads/configs/worker.agent` 中的生產環境配置展示了 SEC、YFinance、TWSE 和 RSS 的 live 功能是如何連接的

### 從 SQLite 遷移到共享 PostgreSQL

一旦本地示範證明了工作流程的可行性，請將此示範配置與以下路徑中的生產風格配置進行比較：

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

主要的區別在於連接池（pool）的定義：

- 此示範使用 `SQLitePool`
- 生產風格的配置使用 `PostgresPool`

## 疑難排解

### 工作保持在隊列中

請檢查這三件事：

- 分派器終端仍在運行
- 工作人員終端仍在運行
- Boss UI 中的工作能力名稱與 Worker 廣告的名稱相符

### Boss UI 已載入但看起來是空的

請確保 boss 配置仍指向：

- `dispatcher_address = http://127.0.0.1:9060`

### 您想要進行一次乾淨的執行，或者需要移除舊的模擬資料列

在重新開始之前，請停止 demo 程序並移除 `demos/data-pipeline/storage/`。

## 停止 Demo

在每個終端機視窗中按下 `Ctrl-C`。
