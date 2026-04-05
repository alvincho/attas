# Prompits Dispatcher

## 翻訳版

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 含まれるコンポーネント

- `DispatcherAgent`: キューベースのジョブディスパッチャ
- `DispatcherWorkerAgent`: 一致するジョブをポーリングして結果を報告するワーカー
- `DispatcherBossAgent`: ジョブの発行と実行時状態の検査を行うブラウザUI
- `JobCap`: プラグ可能なジョブハンドラーのための機能抽象化
- 共有プラクティス、スキーマ、ランタイムヘルパー、および設定例

## 内部テーブル

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

worker が特定の `target_table` の行を返し、スキーマが提供された場合、dispatcher はそのテーブルを作成して永続化することもできます。スキーマが提供されない場合、行は `dispatcher_job_results` に汎用的に保存されます。

## 実装例

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## 使用例

dispatcher を起動します：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

ワーカーを起動する:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

boss UI を起動します：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

サンプル worker 設定は、以下からの最小限の例の機能を使用しています
`prompits.dispatcher.examples.job_caps`.

## 注意事項

- このパッケージはデフォルトで共有のローカル直接トークンを使用するため、Plaza 認証が設定される前でも `UsePractice(...)` の呼び出しをローカルで実行できます。
- 例示の構成では `PostgresPool` を使用していますが、テストでは SQLite もカバーしています。
- ワーカーは `dispatcher.job_capabilities` 設定セクションを通じて、呼び出し可能またはクラスベースの機能を公開できます。
