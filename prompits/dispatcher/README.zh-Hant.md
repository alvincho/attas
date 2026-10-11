# Prompits Dispatcher

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

## 包含的元件

- `DispatcherAgent`: 以佇列為後端的任務調度器
- `DispatcherWorkerAgent`: 輪詢符合任務並回報結果的工作器
- `DispatcherBossAgent`: 用於發布任務和檢查執行時狀態的瀏覽器 UI
- `JobCap`: 用於可插拔任務處理器的能力抽象
- 共享實踐、架構、執行時助手和範例設定

## 內部資料表

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

如果 worker 為特定的 `target_table` 回傳了資料列並提供了 schema，則 dispatcher 也可以建立並持久化該資料表。如果沒有提供 schema，資料列將以通用方式儲存在 `dispatcher_job_results` 中。

## 實作方法

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## 使用範例

啟動 dispatcher：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

啟動工作節點：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

啟動 boss UI：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

範例 worker 設定使用了來自以下內容的最小範例功能
`prompits.dispatcher.examples.job_caps`.

## 注意事項

- 套件預設使用共享的本地直接權杖，因此在設定 Plaza 認證之前，`UsePractice(...)` 呼叫可以在本地執行。
- 範例設定使用了 `PostgresPool`，但測試也涵蓋了 SQLite。
- Worker 可以透過 `dispatcher.job_capabilities` 設定區段來宣告可呼叫或基於類別的能力。
