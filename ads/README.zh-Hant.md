# Attas Data Services

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

## 涵蓋範圍

目前的正規化資料集表格包括：

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

Dispatch 程式同時也管理：

- `ads_jobs`
- `ads_worker_capabilities`

實作上使用了 `ads_` 資料表前綴，而非字面上的 `ads-*` 名稱，因此相同的識別碼可以在 SQLite、Postgres 和以 Supabase 為後端的 SQL 中順暢地運作。

## 執行時形狀

Dispatcher:

- 是一個 `prompits` agent
- 擁有共享隊列與正規化存儲表
- 提供 `ads-submit-job`、`ads-get-job`、`ads-register-worker` 以及 `ads-post-job-result`
- 當 worker 認領工作時，向其交付具備類型的 `JobDetail` 負載
- 接收具備類型的 `JobResult` 負載，以完成工作並持久化收集到的行及原始負載

Worker:

- 是一個 `prompits` agent
- 透過 agent 元數據與 dispatcher 能力表來宣告其功能
- 從配置中載入 `job_capabilities` 並在 Plaza 元數據上註冊這些能力名稱
- 使用 `JobCap` 對象作為認領工作的預設執行路徑
- 可以單次運行或在輪詢循環中運行，預設間隔為 10 秒
- 接受覆寫的 `process_job()` 或外部處理程序回調

Pulser:

- 是一個 `phemacast` pulser
- 從共享池中讀取正規化的 ADS 表
- 提供用於 security master、每日價格、基本面、財務報表、新聞及原始負載查詢的Pulse (pulses)

## 檔案

- `ads/agents.py`: 分派器與工作代理
- `ads/jobcap.py`: `JobCap` 抽象與基於可呼叫對象的權限載入器
- `ads/models.py`: `JobDetail` 與 `JobResult`
- `ads/pulser.py`: ADS pulser 實作
- `ads/boss.py`: boss operator UI 代理
- `ads/practices.py`: 分派器實務
- `ads/schema.py`: 共用資料表結構
- `ads/iex.py`: IEX 日終工作權限
- `ads/twse.py`: 台灣證券交易所日終工作權限
- `ads/rss_news.py`: 多來源 RSS 新聞收集權限
- `ads/sec.py`: SEC EDGAR 大量原始資料匯入與逐公司映射權限
- `ads/us_listed.py`: Nasdaq Trader 美國上市證券主檔權限
- `args/yfinance.py`: Yahoo Finance 日終工作權限
- `ads/runtime.py`: 正規化輔助工具
- `ads/configs/*.agent`: ADS 配置範例
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## 本地範例

隨附的 ADS 配置現在假設使用共用的 PostgreSQL 資料庫。在啟動代理程式之前，請設定
`POSTGRES_DSN` 或 `DATABASE_URL`。您可以選擇設定 `ADS_POSTGRES_SCHEMA` 以使用 `public` 以外的 schema，
並且在需要為託管的 PostgreSQL 使用 SSL 時，透過 `ADS_POSTGRES_SSLMODE` 來覆寫預設的本地友善 `disable`
行為。

啟動 dispatcher：
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

啟動工作節點：
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

範例 worker 配置包含一個由 `ads.us_listed:USListedSecJobCap` 支援的實時 `US Listed Sec to security master` 功能、`fundamentals`、`financial_statements` 與 `news` 的模擬處理程序，並使用名為 `US Filing Bulk` 的 `ads.sec:USFilingBulkJobCap`、名為 `US Filing Mapping` 的 `ads.sec:USFilingMappingJobCap`、名為 `YFinance EOD` 的 `ads.yfinance:YFinanceEODJobCap`、名為 `YFinance US Market EOD` 的 `ads.yfinance:YFinanceUSMarketEODJobCap`，以及用於實時收盤數據收集的 `TWSE Market EOD` (`ads.twse:TWSEMarketEODJobCap`)，以及用於多來源新聞收集的 `RSS News` (`ads.rss_news:RSSNewsJob
將 `companyfacts.zip` 和 `submissions.zip` 壓縮檔中的原始每公司 JSON 列寫入 `ads_sec_companyfacts` 和 `ads_sec_submissions` 中，並發送宣告的 SEC `User-Agent` 標頭。`US Filing Mapping` 從這些原始 SEC 表格中讀取一家公司，並在 submissions 元數據中可用 symbol 時，將其映射到 `ads_fundamentals` 以及 `ads_financial_statements`。
啟動 pulser：
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

啟動 boss UI：
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

Boss UI 現在在頁面頂部包含了一個即時的 Plaza 連線條，
一個 `Issue Job` 頁面，一個用於瀏覽已排隊、已領取、
已完成和失敗的 ADS 作業及其原始酬載紀錄的 `/monitor` 視圖，
以及一個用於設定 boss 端調度器預設值和監控刷新
偏好的 `Settings` 頁面。

## 注意事項
- 隨附的範例配置使用 `PostgresPool`，因此 dispatcher、workers、pulser 和 boss 都指向同一個 ADS 資料庫，而不是每個 agent 使用獨立的 SQLite 檔案。
- `PostgresPool` 會從 `POSTGRES_DSN`、`DATABASE_URL`、`SUPABASE_DB_URL` 或標準 libpq `PG*` 環境變數中解析連線設定。
- 當引入新的 JobCaps 時，`ads/configs/boss.agent`、`ads/configs/dispatcher.agent` 和 `ads/configs/worker.agent` 應保持一致；隨附的配置包含 `US Listed Sec to security master`、`US Filing Bulk`、`US Filing Mapping`、`YFinance EOD`、`YFinance US Market EOD`、`TWSE Market EOD` 以及 `RSS News`。
- Worker 配置可以透過能力名稱和可呼叫路徑（例如 `ads.examples.job_caps:mock_daily_price_cap`）來宣告 `ads.job_capabilities` 項目。
- Worker 配置也可以透過 `type` 宣告基於類別的能力，例如 `ads.iex:IEXEODJobCap`、`ads.rss_news:RSSNewsJobCap`、`ads.sec:USFilingBulkJobCap`、`ads.sec:USFilingMappingJobCap`、`ads.twse:TWSEMarketEODJobCap`、`ads.us_listed:USListedSecJobCap` 或 `ads.yfinance:YFinanceEODJobCap`，這些能力會回傳標準化行以及用於 dispatcher 持久化的原始負載。
- Worker 的 `ads.job_capabilities` 項目支援 `disabled: true`，以便在不刪除配置項目的情況下暫時停用已配置的 job cap。
- Worker 配置可以設定 `ads.yfinance_request_cooldown_sec`（預設為 `120`），以便在收到 Yahoo 速率限制回應後，讓 worker 暫時停止廣告與 YFinance 相關的能力。
- `ads/sql/ads_tables.sql` 已包含在內，適用於 Postgres 或 Supabase 部署。
- Dispatcher 和 worker 預設使用共享的本地直接 token，因此即使在配置 Plaza 認證之前，遠端 `UsePractice(...)` 調用也能在單機上運作。
- 所有三個組件都符合現有的儲存庫慣例，因此在配置完成時，它們仍可以參與 Plaza 註冊和遠端 `UsePractice(...)` 調用。
