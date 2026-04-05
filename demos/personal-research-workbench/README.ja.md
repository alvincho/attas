# パーソナル・リサーチ・ワークベンチ

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

## このデモのデモンストレーション内容

- ローカルで実行されるパーソナル・ワークベンチの UI
- ワークベンチが閲覧可能な Plaza
- 実際に実行可能なPulse（pulses）を備えた、ローカルおよびライブデータの pulser
- 市場データを計算された指標シリーズに変換する、図解優先の `Test Run` フロー
- 洗練されたデモからセルフホストされたインスタンスへのパス

## このフォルダ内のファイル

- `plaza.agent`: このデモ専用のローカル Plaza
- `file-storage.pulser`: ファイルシステムをバックエンドとするローカル pulser
- `yfinance.pulser`: `yfinance` Python モジュールをバックエンドとするオプションの市場データ pulser
- `technical-analysis.pulser`: OHLC データから RSI を計算するオプションのパス pulser
- `map_phemar.phemar`: 組み込みの図形エディタで使用されるデモローカルの MapPhemar 設定
- `map_phelar_pool/`: すぐに実行可能な OHLC-to-RSI マップを含む、シード済みの図形ストレージ
- `start-plaza.sh`: デモ Plaza を起動
- `start-file-storage-pulser.sh`: pulser を起動
- `start-yfinance-pulser.sh`: YFinance pulser を起動
- `start-technical-analysis-pulser.sh`: テクニカル分析 pulser を起動
- `start-workbench.sh`: React/FastAPI ワークベンチを起動

すべての実行時状態は `demos/personal-research-workbench/storage/` に書き込まれます。ランチャーは、組み込みの図形エディタをこのフォルダ内のシード済み `map_phemar.phemar` および `map_phemar_pool/` ファイルに指定します。

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
./demos/personal-research-workbench/run-demo.sh
```

これは、1つのターミナルから workbench スタックを起動し、ブラウザのガイドページを開き、メインの workbench UI とコア・ウォークスルーで使用される埋め込み `MapPhelar` ルートの両方を開きます。

ランチャーをターミナルのみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイック スタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したままにし、出力された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## クイックスタート

YFinance チャートフローと図のテスト実行フローを含む完全なデモをご希望の場合は、リポジトリのルートから 5 つのターミナルを開いてください。

### ターミナル 1: ローカルの Plaza を起動する

```bash
./demos/personal-research-workbench/start-plaza.sh
```

期待される結果:

- Plaza は `http://127.0.0.1:8241` で起動します

### ターミナル 2: ローカルファイルストレージ pulser を起動します
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

期待される結果：

- pulser が `http://127.0.0.1:8242` で起動します
- Terminal 1 から Plaza に自身を登録します

### Terminal 3: YFinance pulser を起動する
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

期待される結果：

- pulser が `http://127.0.0.1:8243` で起動します
- Terminal 1 から Plaza に自身を登録します

注意：

- このステップには外部インターネットへのアクセスが必要です。pulser が `yfinance` モジュールを通じて Yahoo Finance からライブデータを取得するためです
- Yahoo は時折リクエストのレート制限を行う可能性があるため、このフローは厳密な固定手順というよりも、ライブデモとして扱うのが最適です

### Terminal 4：テクニカル分析 pulser を起動する
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

期待される結果:

- pulser が `http://127.0.0.1:8244` で起動します
- Terminal 1 から Plaza に自身を登録します

この pulser は、入力された `ohlc_series` から `rsi` を計算するか、symbol、interval、date range のみを指定した場合には demo YFinance pulser から OHLC bars を取得します。

### Terminal 5: ワークベンチの起動
```bash
./demos/personal-research-workbench/start-workbench.sh
```

期待される結果：

- ワークベンチは `http://127.0.0.1:8041` で起動します

## 初回実行のウォークスルー

このデモには、現在3つのワークベンチフローがあります。

1. file-storage pulser を使用したローカルストレージフロー
2. YFinance pulser を使用したライブ市場データフロー
3. YFinance および technical-analysis pulsers を使用したダイアグラムテスト実行フロー

開く:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### フロー 1: ローカルデータの閲覧と保存

次に、以下の短い手順を実行してください。

1. ワークベンチで設定フローを開きます。
2. `Connection` セクションに移動します。
3. デフォルトの Plaza URL を `http://127.0.0.1:8241` に設定します。
4. Plaza カタログをリフレッシュします。
5. ワークベンチでブラウザウィンドウを開くか作成します。
6. 登録されている file-storage pulser を選択します。
7. `list_bucket`、`bucket_create`、または `bucket_browse` などの組み込みの pulse のいずれかを実行します。

推奨される最初のインタラクション:

- `demo-assets` という名前のパブリック bucket を作成する
- その bucket を閲覧する
- 小さなテキストオブジェクトを保存する
- それを再度読み込む

これにより、リッチな UI、Plaza での発見、pulser の実行、および永続化されたローカル状態という、完全なループが実現します。

### フロー 2: YFinance pulser からデータを表示し、チャートを描画する

同じワークベンチセッションを使用し、次に以下を行います。

1. Plaza カタログを再度リフレッシュして、YFinance pulser を表示させます。
2. 新しいブラウザペインを追加するか、既存のデータペインを再構成します。
3. `ohlc_bar_series` pulse を選択します。
4. ワークベンチが自動的に選択しない場合は、`DemoYFinancePulser` pulser を選択します。
5. `Pane Params JSON` を開き、次のようなペイロードを使用します。
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. `Get Data` をクリックします。
7. `Display Fields` で `ohlc_series` をオンにします。他のフィールドがすでに選択されている場合は、プレビューが時系列そのものを指すように、そのフィールドをオフにしてください。
8. `Format` を `chart` に変更します。
9. `Chart Style` を、OHLCキャンドルの場合は `candle`、シンプルなトレンド表示の場合は `line` に設定します。

表示される内容：

- パネルが要求されたシンボルと日付範囲のバーデータを取得します
- プレビューが構造化データからチャートに変わります
- シンボルや日付範囲を変更しても、ワークベンチを離れることなく新しいチャートが表示されます

推奨されるバリエーション：

- `AAPL` を `MSFT` や `NVDA` に切り替える
- 日付範囲を短くして、直近の表示を詳細にする
- 同じ `ohlc_bar_series` レスポンスを使用して `line` と `candle` を比較する

### フロー 3: ダイアグラムをロードし、Test Run を使用して RSI シリーズを計算する

ダイアグラムエディタのルートを開きます：

- `http://127.0.0.1:8041/map-phemar/`

次に、以下の手順を進めます：

1. ダイアグラムエディタ内の Plaza URL が `http://127.0.0.1:8241` であることを確認します。
2. `Load Phema` をクリックします。
3. `OHLC To RSI Diagram` を選択します。
4. 初期状態のグラフを確認します。`Input -> OHLC Bars -> RSI 14 -> Output` と表示されているはずです。
5. `Test Run` をクリックします。
6. 次の入力ペイロードを使用します：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. マップを実行し、ステップの出力を展開します。

表示される内容：

- `OHLC Bars` ステップがデモの YFinance pulser を呼び出し、`ohlc_series` を返します
- `RSI 14` ステップがこれらの bars を `window: 14` を指定して technical-analysis pulser に転送します
- 最終的な `Output` ペイロードには、`timestamp` と `value` のエントリを含む計算された `values` 配列が含まれます

シードをロードする代わりに、同じ図をゼロから再構築したい場合は：

1. `OHLC Bars` という名前の丸みを帯びたノードを追加します。
2. `DemoYFinancePulser` と `ohlc_bar_series` pulse にバインドします。
3. `RSI 14` という名前の丸みを帯びたノードを追加します。
4. `DemoTechnicalAnalysisPulser` と `rsi` pulse にバインドします。
5. RSI ノードのパラメータを以下に設定します：
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. `Input -> OHLC Bars -> RSI 14 -> Output` を接続します。
7. エッジマッピングを `{}` のままにして、一致するフィールド名が自動的に流れるようにします。

## デモコールで強調すべき点

- ライブ接続を追加する前でも、ワークベンチには有用なモック・ダッシュボード・データがロードされます。
- Plaza の統合はオプションであり、ローカルまたはリモートの環境を指すことができます。
- ファイルストレージ pulser はローカル専用であるため、公開デモは安全かつ再現可能です。
- YFinance pulser は、同じワークベンチでライブ市場データを閲覧し、チャートとして描画できるという、2つ目のストーリーを追加します。
- ダイアグラムエディタは、3つ目のストーリーを追加します。同じバックエンドでマルチステップのフローをオーケストレートし、`Test ກ Test Run` を通じて各ステップを公開できます。

## 独自のインスタンスを構築する

一般的なカスタマイズパスは3つあります：

### シードされたダッシュボードとワークスペースのデータを変更する

ワークベンチは以下の場所からダッシュボードのスナップショットを読み込みます：

- `attas/personal_agent/data.py`

ここが、独自のウォッチリスト、メトリクス、またはワークスペースのデフォルト値を入れ替える最も速い方法です。

### ビジュアルシェルを変更する

現在のライブワークベンチのランタイムは以下から提供されます：

- `pshmecast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

デモのテーマを再設定したり、視聴者向けにUIを簡素化したりしたい場合は、ここから始めてください。

### 接続されている Plaza と pulsers を変更する

異なるバックエンドを使用したい場合：

1. `plaza.agent`、`file-storage.pulser`、`yfinance.pulser`、および `technical-analysis.pulser` をコピーします
2. サービス名を変更します
3. ポートとストレージパスを更新します
4. `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` 内のシード図面を編集するか、ワークベンチから独自の図面を作成します
5. 準備ができたら、デモの pulsers を独自の agents に置き換えます

## オプションのWorkbench設定

ランチャースクリプトは、いくつかの便利な環境変数に対応しています：
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

開発中に FastAPI アプリをアクティブに編集する場合は、`PHEMACAST_PERSONAL_AGENT_RELOAD=1` を使用してください。

## トラブルシューティング

### ワークベンチは読み込まれますが、Plaza の結果が空です

以下の3点を確認してください：

- `http://127.0.0.1:8241/health` にアクセス可能であること
- これらのフローが必要なときに、file-storage、YFinance、および technical-analysis pulser ターミナルがまだ実行中であること
- ワークベンチの `Connection` 設定が `http://127.0.0.1:8241` を指していること

### pulser にまだオブジェクトが表示されません

これは初回起動時には正常です。デモのストレージバックエンドは空の状態で開始されます。

### YFinance パネルにチャートが描画されません

以下の点を確認してください：

- YFinance pulser ターミナルが実行中であること
- 選択された pulse が `ohlc_bar_series` であること
- `Display Fields` に `ohlc_series` が含まれていること
- `Format` が `chart` に設定されていること
- `Chart Style` が `line` または `candle` であること

リクエスト自体が失敗する場合は、別のシンボルを試すか、少し待ってから再実行してください。Yahoo は断続的にレート制限を行ったり、リクエストを拒否したりすることがあります。

### ダイアグラムの `Test Run` が失敗します

以下の点を確認してください：

- `http://12</strong>0.0.1:8241/health` にアクセス可能であること
- YFinance pulser が `http://127.0.0.1:8243` で実行中であること
- technical-analysis pulser が `http://127.0.0.1:8244` で実行中であること
- 読み込まれたダイアグラムが `OHLC To RSI Diagram` であること
- 入力ペイロードに `symbol`、`interval`、`start_date`、`end_date` が含まれていること

`OHLC Bars` ステップが最初に失敗する場合、問題は通常、Yahoo へのライブアクセスまたはレート制限です。`RSI 14` ステップが失敗する場合、最も一般的な原因は、technical-analysis pulser が実行されていないか、上流の OHLC レスポンスに `ohlc_series` が含まれていないことです。

### デモをリセットしたい場合

最も安全なリセット方法は、`root_path` の値を新しいフォルダ名に向けるか、デモプロセスが実行されていないときに `demos/personal-research-workbench/storage/` フォルダを削除することです。

## デモを停止する

各ターミナルウィンドウで `Ctrl-C` を押してください。
