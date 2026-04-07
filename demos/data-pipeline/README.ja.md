# データパイプライン

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

## このデモが示す内容

- データ収集ジョブ用のディスパッチャキュー
- 一致する機能を確認するためにポーリングを行うworker
- ローカルのSQLiteに保存された正規化されたADSテーブル
- ジョブの発行と監視を行うためのboss UI
- 収集されたデータを再公開するpulser
- 付属のlive collectorsを独自のソースアダプターに交換するためのパス

## なぜこのデモではライブコレクターにSQLiteを使用しているのか

`ads/configs/` にある本番用スタイルの ADS 設定は、共有 PostgreSQL デプロイメントを対象としています。

このデモでは、ライブコレクターは維持しつつ、ストレージ側を簡素化しています：

- SQLite により、セットアップをローカルかつシンプルに保ちます
- worker と dispatcher は 1 つのローカル ADS データベースファイルを共有します。これにより、ライブ SEC バルクステージが pulser が読み取るのと同じデモストアと互換性を保てます
- 同じアーキテクチャが引き続き確認できるため、構築者は後で本番用設定に移行できます
- 一部のジョブは公開インターネットソースを呼び出すため、初回実行の時間はネットワーク条件やソースの応答性に依存します

## このフォルダ内のファイル

- `dispatcher.agent`: SQLiteをバックエンドとするADS dispatcherの設定
- `worker.agent`: SQLiteをバックエンドとするADS workerの設定
- `pulser.agent`: デモデータストアを読み取るADS pulser
- `boss.agent`: ジョブ発行用のboss UI設定
- `start-dispatcher.sh`: dispatcherの起動
- `start-worker.sh`: workerの起動
- `start-pulser.sh`: pulserの起動
- `start-boss.sh`: boss UIの起動

関連する例示用ソースアダプターおよびlive-demoヘルパーは以下にあります：

- `ads/examples/custom_sources.py`: ユーザー定義のニュースおよび価格フィード用の、インポート可能な例示用ジョブ上限 (job caps)
- `ads/implements/live_data_pipeline.py`: live SEC ADS pipelineのデモ向けラッパー

すべての実行時状態は `demos/data-pipeline/storage/` に書き込まれます。

## 前提条件

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/data-pipeline/run-demo.sh
```

これは、1つのターミナルから dispatcher、worker、pulser、および boss UI を起動し、ブラウザのガイドページを開き、boss plus pulser UI を自動的に開きます。

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

ネイティブの Windows Python 環境を使用してください。PowerShell でリポジトリのルートから以下を実行します：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher data-pipeline
```

ブラウザのタブが自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

## クイックスタート

リポジトリのルートから4つのターミナルを開きます。

### ターミナル 1: dispatcher を起動する
```bash
./demos/data-pipeline/start-dispatcher.sh
```

期待される結果：

- dispatcher が `http://127.0.0.1:9060` で起動します

### ターミナル 2: worker を起動する
```bash
./demos/data-pipeline/start-worker.sh
```

期待される結果：

- worker が `127.0.0.1:9061` で起動します
- 2秒ごとに dispatcher をポーリングします

### ターミナル 3: pulser を起動する
```bash
./demos/data-pipeline/start-pulser.sh
```

期待される結果：

- ADS pulser は `http://127.0.0.1:9062` で起動します

### ターミナル 4: boss UI を起動する
```bash
./demos/data-pipeline/start-boss.sh
```

期待される結果：

- boss UI は `http://127.0.0.1:9063` で起動します

## 初回実行のウォークスルー

以下を開いてください：

- `http://127.0.0.1:9063/`

Boss UI で、以下のジョブを順番に送信してください：

1. `security_master`
   Nasdaq Trader から米国上場銘柄の全ユニバースを更新するため、シンボル・ペイロードは不要です。
2. `daily_price`
   `AAPL` のデフォルト・ペイロードを使用してください。
3. `fundamentals`
   `AAPL` のデフォルト・ペイロードを使用してください。
4. `financial_statements`
   `AAPL` のデフォルト・ペイロードを使用してください。
5. `news`
   デフォルトの SEC、CFTC、および BLS の RSS フィード・リストを使用してください。

テンプレートが表示された場合は、デフォルトのペイロード・テンプレートを使用してください。`security_master`、`daily_price`、`news` は通常、すぐに完了します。SEC に基づく最初の `fundamentals` または `financial</sub>financial_statements` の実行は、要求された企業をマッピングする前に `demos/data-pipeline/storage/sec_edgar/` にあるキャッシュされた SEC アーカイブを更新するため、時間がかかる場合があります。

次に、以下を開いてください：

- `http://127.0.0.1:9062/`

これは、同じデモ用データストア用の ADS pulser です。正規化された ADS テーブルを pulses として公開しており、収集/オーケストレーションからダウンストリームの消費への架け橋となります。

推奨される最初の pulser チェック：

1. `{"symbol":"AAPL","limit":1}` を指定して `security_master_lookup` を実行
2. `{"symbol":"AAPL","limit":5}` を指定して `daily_price_history` を実行
3. `{"symbol":"AAPL"}` を指定して `company_profile` を実行
4. `{"symbol":"AAPL","statement_type":"income_statement","limit":3}` を指定して `financial_statements` を実行
5. `{"number_of_articles":3}` を指定して `news_article` を実行

これにより、ADS ループ全体が把握できます。boss UI がジョブを発行し、worker が行を収集し、SQLite が正規化されたデータを保存し、`ADSPulser` がクエリ可能な pulses を通じて結果を公開します。

## ADSPulser に独自のデータソースを追加する

重要なメンタルモデルは以下の通りです：

- ソースは `job_capability` としてワーカーに接続されます
- ワーカーは正規化された行を ADS テーブルに書き込みます
- `ADSPulser` はそれらのテーブルを読み取り、pulse を通じて公開します

ソースが既存の ADS テーブルの形式のいずれかに適合する場合、通常 `ADSPulser` を変更する必要はありません。

### 最も簡単な方法：既存の ADS テーブルに書き込む

以下のテーブルと pulse の組み合わせのいずれかを使用してください：

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### 例：カスタムプレスリリースフィードを追加する

リポジトリには、ここに呼び出し可能な例が含まれています：

- `ads/examples/custom_sources.py`

これをデモワーカーに接続するには、`demos/data-pipeline/worker.agent` に capability 名と、callable に基づく job cap を追加します。

この capability 名を追加してください：
```json
"press_release_feed"
```

この job-capability エントリを追加します：
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

その後、worker を再起動し、次のような payload を使用して boss UI からジョブを送信します：
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

このジョブが完了したら、`http://127.0.0.1:9062/` で Pulser UI を開き、以下を実行してください：
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

`news_article` pulse に対して。

表示される内容：

- ユーザー定義のコレクターが正規化された行を `ads_news` に書き込みます
- 生の入力はジョブの raw payload に保持されたままです
- `ADSPulser` は既存の `news_article` pulse を通じて新しい記事を返します

### 第二の例：カスタム価格フィードの追加

ソースがニュースよりも価格に近い場合、同じパターンが以下でも機能します：
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

この例では、行が `ads_daily_price` に書き込まれるため、結果はすぐに `daily_price_history` を通じてクエリ可能になります。

### ADSPulser 自体を変更すべき場合

`ads/pulser.py` を変更するのは、ソースが既存の正規化された ADS テーブルのいずれかにきれいにマッピングされない場合、または全く新しいPulse形状（pulse shape）が必要な場合に限られます。

その場合の一般的な手順は以下の通りです：

1. 新しい正規化された行のための保存テーブルを追加または選択する
2. pulser 設定に新しいサポートされるPulseエントリを追加する
3. `ADSPulser.fetch_pulse_payload()` を拡張して、Pulseが保存された行をどのように読み取り、整形するかを認識できるようにする

まだスキーマを設計中の場合は、まず生のペイロードを保存し、`raw_collection_payload` を通じて最初に検査することから始めてください。これにより、最終的な正規化テーブルの構成を決定している間も、ソースの統合を進めることができます。

## デモコールで強調すべき点

- ジョブは非同期にキューに入れられ、完了します。
- ワーカーは Boss UI から切り離されています。
- 保存された行は、単一の汎用 Blob ストレージではなく、正規化された ADS テーブルに格納されます。
- Pulser は、収集されたデータの上にある第2のインターフェース層です。
- 新しいソースの導入は、通常、ADS スタック全体を再構築することなく、ワーカーのジョブ上限を1つ追加することを意味します。

## 独自のインスタンスを構築する

このデモから、2つの自然なアップグレードパスがあります。

### ローカルアーキテクチャを維持し、独自のコレクターに置き換える

`worker.agent` を編集し、付属のライブデモ用 job caps を独自の job caps または他の ADS job-cap タイプに置き換えます。

例：

- `ads.examples.custom_sources:demo_preass_release_cap` は、カスタム記事フィードを `ads_news` に取り込む方法を示します
- `ads.essentials.custom_sources:demo_alt_price_cap` は、カスタム価格ソースを `ads_daily_price` に取り込む方法を示します
- `ads/configs/worker.agent` の本番用設定は、SEC、YFinance、TWSE、および RSS のライブ機能がどのように接続されているかを示します

### SQLite から共有 PostgreSQL へ移行する

ローカルデモでワークフローが確認できたら、これらのデモ設定を以下の本番用設定と比較してください：

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

主な違いはプール（pool）の定義です：

- このデモでは `SQLitePool` を使用しています
- 本番用設定では `PostgresPool` を使用しています

## トラブルシューティング

### ジョブはキューに保持されます

次の3つの点を確認してください：

- ディスパッチャ端末はまだ実行中です
- ワーカー端末はまだ実行中です
- Boss UI のジョブ機能名が Worker によって広告されているものと一致している

### Boss UI は読み込まれますが、空に見えます

boss の設定が引き続き以下を指していることを確認してください：

- `dispatcher_address = http://127.0.0.1:9060`

### クリーンな実行を行いたい、または古いモック行を削除する必要がある場合

再度開始する前に、デモプロセスを停止し `demos/data-pipeline/storage/` を削除してください。

## デモの停止

各ターミナルウィンドウで `Ctrl-C` を押してください。
