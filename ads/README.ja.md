# Attas Data Services

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

## カバレッジ

現在の正規化されたデータセットのテーブルは以下の通りです：

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

ディスパッチャは以下も管理します：

- `ads_jobs`
- `ads_worker_capabilities`

実装では、リテラルな `ads-*` 名ではなく `ads_` テーブルプレフィックスを使用しているため、同じ識別子が SQLite、Postgres、および Supabase バックエンドの SQL でクリーンに動作します。

## ランタイムの形状

Dispatcher:

- `prompits` エージェントです
- 共有キューと正規化されたストレージテーブルを所有します
- `ads-submit-job`、`arg-get-job`、`ads-register-worker`、および `ads-post-job-result` を公開します
- ワーカーが作業を要求した際に、型指定された `JobDetail` ペイロードを渡します
- 型指定された `JobResult` ペイロードを受け取り、ジョブを完了させ、収集された行と生のペイロードを永続化します

Worker:

- `prompits` エージェントです
- エージェントのメタデータとディスパッチャの機能テーブルを通じて、自身の機能を広告します
- 設定から `job_capabilities` を読み込み、それらの機能名を Plaza メタデータに登録します
- 要求されたジョブのデフォルトの実行パスとして `JobCap` オブジェクトを使用します
- 単発またはポーリングループで実行可能で、デフォルトのインターバルは 10 秒です
- オーバーライドされた `process_job()` または外部ハンドラーのコールバックを受け入れます

Pulser:

- `phemacast` pulser です
- 共有プールから正規化された ADS テーブルを読み取ります
- security master、日次価格、ファンダメンタルズ、財務諸表、ニュース、および生のペイロードのルックアップ用のPulse（pulses）を公開します

## ファイル

- `ads/agents.py`: ディスパッチャおよびワーカーエージェント
- `ads/jobcap.py`: `JobCap` 抽象化および callable ベースの機能ローダー
- `ads/models.py`: `JobDetail` および `JobResult`
- `ads/pulser.py`: ADS pulser 実装
- `ads/boss.py`: boss operator UI エージェント
- `ads/practices.py`: ディスパッチャの実践
- `ads/schema.py`: 共有テーブルスキーマ
- `ads/iex.py`: IEX 終値ジョブ機能
- `ads/twse.py`: 台湾証券取引所 終値ジョブ機能
- `ads/rss_news.py`: マルチフィード RSS ニュース収集機能
- `ads/sec.py`: SEC EDGAR バルク生データインポートおよび企業別マッピング機能
- `ads/us_listed.py`: Nasdaq Trader 米国上場証券マスター機能
- `ads/yfinance.py`: Yahoo Finance 終値ジョブ機能
- `ads/runtime.py`: 正規化ヘルパー
- `ads/configs/*.agent`: ADS 設定例
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## ローカルの例

同梱されている ADS 設定は、現在共有の PostgreSQL データベースを使用することを前提としています。
エージェントを開始する前に、`POSTGRES_DSN` または `DATABASE_URL` を設定してください。
オプションとして、`public` 以外のスキーマを使用するために `ADS_POSTGRES_SCHEMA` を設定したり、
マネージド PostgreSQL で SSL が必要な場合に、デフォルトのローカル向け `disable` 設定を
上書きするために `ADS_POSTGRES_SSLMODE` を設定したりできます。

ディスパッチャを起動します：
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

ワーカーを起動する:
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

サンプルワーカー設定には、`ads.us_listed:USListedSecJobCap` に対応したライブな `US Listed Sec to security master` 機能、`fundamentals`、`financial_statements`、`news` 用のモックハンドラーが含まれています。また、ライブな終値収集用の `TWSE Market EOD` (`ads.twse:TWSEMarketEODJobCap`)、マルチフィードニュース収集用の `RSS News` (`ads.rss_news:RSSNewsJobCap`)、および `US Filing Bulk` (`ads.sec:USFilingBulkJobCap`)、`US Filing Mapping` (`ads.sec:USFilingMappingJobCap`)、`YFinance EOD` (`ads.yfinance:YFinanceEODJobCap`)、`YFinance US Market EOD` (`ads.yfinance:YFinanceUSMarketEODJobCap`) を使用します。`YFinance EOD` はインストール済みの `yfinance` モジュールを使用し、個別の API キーは必要ありません。`YFinance US Market EOD` は `ads_security_master` をスキャンしてアクティブな `USD` シンボルを探し、`metadata.yfinance.eod_at` でソートして、シンボルごとにタイムスタンプを更新し、シンボルごとの `YFinance EOD` ジョブをキューに入れ、最も古いシンボルから優先的に更新します。`TWSE Market EOD` は公式の TWSE `MI_INDEX` 日次株価レポートを読み取り、完全な市場全体の株価テーブルを正規化された `ads_daily_price` 行に保存します。`ads_daily_price` が空の場合、数年間にわたるフルマーケットのバックフィルを試みる代わりに、デフォルトで短い直近のウィンドウをブートストラップします。TWSE の履歴カバレッジが必要な場合は、明示的な `start_date` を使用してください。`USListedSecJobCap` は Nasdaq Trader のシンボルディレクトリファイル `nasdaqlisted.txt` と `otherlisted.txt` を読み取り、FTP フォールバックを伴う Web ホストの `https://www.nasdaqtrader.com/dynamic/SymDir/` コピーを優先し、テストシンボルを除外して、現在の米国上場銘柄を `ads_security_master` にアップサートします。`RSS News` は、設定された SEC、CFTC、BLS フィードを 1 つのジョブで取得し、正規化されたフィードエントリを `ads_news` に保存します。`US Filing Bulk` は、毎晩の SEC EDGAR をダウンロードします
`companyfacts.zip` および `submissions.zip` アーカイブから、企業ごとの生の JSON 行を `ads_sec_companyfacts` および `ads_sec_submissions` に書き込み、宣言された SEC `User-Agent` ヘッダーを送信します。`US Filing Mapping` は、これらの生の SEC テーブルから 1 社の企業を読み取り、submissions メタデータにシンボルが利用可能な場合に `ads_fundamentals` および `args_financial_statements` にマッピングします。
pulser を起動します：
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

boss UI を起動します：
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

Boss UI には、ページ上部に Plaza のライブ接続ストリップ、
キューに保留中、取得済み、完了、および失敗した ADS ジョブとその生のペイロード レコードを閲覧するための `/monitor` ビュー、
および boss 側のディスパッチャのデフォルト値とモニターの更新設定のための `Settings` ページが含まれるようになりました。

## 注意事項
<<<LANG:ja>>>
- 付属のサンプル設定は `PostgresPool` を使用しているため、dispatcher、workers、pulser、boss は、エージェントごとの SQLite ファイルではなく、すべて同じ ADS データベースを指します。
- `PostgresPool` は、`POSTGRES_DSN`、`DATABASE_URL`、`SUPABASE_DB_URL`、または標準の libpq `PG*` 環境変数から接続設定を解決します。
- 新しい JobCaps が導入された際、`ads/configs/boss.agent`、`ads/configs/dispatcher.agent`、および `ads/configs/worker.agent` は整合性を保つ必要があります。付属の設定には、`US Listed Sec to security master`、`US Filing Bulk`、`US Filing Mapping`、`YFinance EOD`、`YFinance US Market EOD`、`TWSE Market EOD`、および `RSS News` が含まれています。
- Worker 設定では、機能名と呼び出し可能なパス（例：`ads.examples.job_caps:mock_daily_price</sub>daily_price_cap`）を使用して `ads.job_capabilities` エントリを宣言できます。
- Worker 設定では、`type` を使用してクラスベースの機能を宣言することもできます（例：`ads.iex:IEXEODJobCap`、`ads.rss_news:RSSNewsJobCap`、`ads.sec:USFilingBulkJobCap`、`ads.sec:USFilingMappingJobCap`、`ads.twse:TWSEMarketEODJobCap`、`ads.us_listed:USListedSecJobCap`、または `ads.yfinance:YFinanceEODJobCap`）。これらは、dispatcher の永続化用に正規化された行と生のペイロードを返します。
- Worker の `ads.job_capabilities` エントリは、`disabled: true` をサポートしており、設定エントリを削除することなく、構成された job cap を一時的に無効にできます。
- Worker 設定では、`ads.yfinance_request_cooldown_sec`（デフォルト `120`）を設定でき、Yahoo のレート制限レスポンスの後に、worker が YFinance 関連の機能を一時的に広告停止するようにできます。
- `ads/sql/ads_tables.sql` は、Postgres または Supabase へのデプロイ用に含まれています。
- Dispatcher と worker は、デフォルトで共有のローカル直接トークンを使用するため、Plaza 認証が構成される前でも、リモートの `UsePractice(...)` 呼び出しを単一のマシンで実行できます。
- 3つのコンポーネントはすべて既存のリポジトリの慣習に適合しているため、設定次第で引き続き Plaza への登録やリモートの `UsePractice(...)` 呼び出しに参加できます。
