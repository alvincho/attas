# Analyst Insight Pulser デモ

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

## このデモの概要

- 複数の構造化されたインサイト pulse を持つ、アナリスト所有の 1 つ目の pulser
- 別のニュースエージェントとローカルの Ollama エージェント上に構築された、アナリスト所有の 2 つ目の pulser
- 生のソースデータと、アナリストが作成した Prompits および最終的な消費者向け出力とを分離するクリーンな方法
- 別のユーザーの視点から同じスタックを示す、パーソナルエージェントのウォークスルー
- アナリストや PM が自身の見解を公開するために編集する正確なファイル

## このフォルダ内のファイル

- `plaza.agent`: アナリスト pulser デモ用のローカル Plaza
- `analyst-insights.pulser`: 公開 pulse カタログを定義する `PathPulser` 設定
- `analyst_insight_step.py`: 共有変換ロジックおよびシードされたアナリスト・カバレッジ・パケット
- `news-wire.pulser`: シードされた `news_article` パケットを公開するローカルのアップストリーム・ニュース・エージェント
- `news_wire_step.py`: アップストリーム・ニュース・エージェントから返されるシードされた生ニュース・パケット
- `ollama.pulser`: アナリスト・プロンプト・デモ用のローカルな Ollama バックエンド `llm_chat` pulser
- `analyst-news-ollama.pulser`: ニュースを取得し、アナリスト所有のプロンプトを適用し、Ollama を呼び出し、結果を複数の pulses に正規化する、構成されたアナリスト pulser
- `analyst_news_ollama_step.py`: アナリスト所有のプロンプト・パックと JSON 正規化ロジック
- `start-plaza.sh`: Plaza を起動
- `start-pulser.sh`: 固定された構造化アナリスト pulser を起動
- `start-news-pulser.sh`: アップストリームのシードされたニュース・エージェントを起動
- `start-ollama-pulser.sh`: ローカルの Ollama pulser を起動
- `start-analyst-news-pulser.sh`: プロンプト付きのアナリスト pulser を起動
- `start-personal-agent.sh`: コンシューマー・ビューのウォークスルー用のパーソナル・エージェント UI を起動
- `run-demo.sh`: 1 つのターミナルからデモを起動し、ブラウザ・ガイドとメインの UI ページを開く

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

このラッパーは、デフォルトで軽量な構造化フローを開始します。

代わりに、高度なニュース + Ollama + パーソナルエージェントのフローを起動するには：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

高度なパスの場合：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

WSL 内の高度なパスについては：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したまま、出力された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## デモ 1: 構造化されたアナリストの視点

これは、LLMを使用しないローカルのみのパスです。

リポジトリのルートから2つのターミナルを開きます。

### ターミナル 1: Plaza を起動
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

期待される結果：

- Plaza は `http://127.0.0.1:8266` で起動します

### ターミナル 2: pulser を起動する
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

期待される結果：

- pulser は `http://127.0.0.1:8267` で起動します
- `http://127.0.0.1:8266` の Plaza に自身を登録します

## ブラウザで試す

開く:

- `http://127.0.0.1:8267/`

次に、`NVDA` で以下の pulses をテストします:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

4つすべてに推奨されるパラメータ:
```json
{
  "symbol": "NVDA"
}
```

表示される内容：

- `rating_summary` は、ヘッドラインの判断、ターゲット、信頼度、および短い要約を返します
- `thesis_bullets` は、ポジティブな論点を箇条書き形式で返します
- `risk_watch` は、主なリスクと監視すべき事項を返します
- `scenario_grid` は、強気、基本、弱気のシナリオを1つの構造化されたペイロードで返します

## Curl で試す

見出しの評価：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

論文の要点：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

リスク監視:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## アナリストによるこのデモのカスタマイズ方法

主な編集箇所は2つあります。

### 1. 実際の調査ビューを変更する

編集：

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

このファイルには、シードされた `ANALYST_COVERAGE` パケットが含まれています。ここで以下を変更できます：

- 対象銘柄
- アナリスト名
- 格付けラベル
- 目標株価
- 論点の要点
- 主要なリスク
- 強気/基本/弱気シナリオ

### 2. 公開パブリック Pulse カタログを変更する

編集：

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

このファイルは以下を制御します：

- 存在する pulse
- 各 pulse の名前と説明
- 入力および出力スキーマ
- タグとアドレス

新しいインサイト pulse を追加したい場合は、既存のエントリの1つをコピーして、新しい `insight_view` を指定してください。

## このパターンが有用な理由

- ポートフォリオツールは `rating_summary` のみを要求できます
- レポートビルダーは `thesis_bullets` を要求できます
- リスクダッシュボードは `risk_watch` を要求できます
- バリュエーションツールは `scenario_grid` を要求できます

つまり、アナリストは1つのサービスを公開するだけで、異なるコンシューマーが必要な部分だけを正確に取得できるということです。

## 次のステップ

このローカルな pulser の形状が理解できたら、次のステップは以下の通りです：

1. アナリスト・カバレッジ・パケットに、より多くの対象シンボルを追加する
2. 自身の見解を YFinance、ADS、または LLM の出力と組み合わせたい場合は、最終的な Python ステップの前にソースステップを追加する
3. ローカルの demo Plaza だけでなく、共有の Plaza を通じて pulser を公開する

## デモ 2: Analyst Prompt Pack + Ollama + パーソナルエージェント

この2番目のフローは、より現実的なアナリストのセットアップを示しています：

- 1つのエージェントが生の `news_article` データを公開します
- 2番目のエージェントが Ollama を介して `llm_chat` を公開します
- アナリストが所有する pulser は、独自の prompt pack を使用して、その生のニュースを複数の再利用可能な pulses に変換します
- パーソナルエージェントが、異なるユーザーの視点から完了した pulses を消費します

### プロンプトフローの前提条件

Ollama がローカルで実行されており、モデルが存在することを確認してください：

```bash
ollama serve
ollama pull qwen3:8b
```

次に、リポジトリのルートから5つのターミナルを開きます。

### ターミナル 1: Plaza を起動

Demo 1 がまだ実行中の場合は、同じ Plaza をそのまま使用してください。
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

期待される結果：

- Plaza は `http://127.0.0.1:8266` で起動します

### ターミナル 2：アップストリーム・ニュースエージェントの起動
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

期待される結果:

- news pulser が `http://127.0.0.1:8268` で起動します
- `http://127.0.0.1:8266` の Plaza に自身を登録します

### ターミナル 3: Ollama pulser を起動します
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

期待される結果:

- Ollama pulser が `http://120.0.0.1:8269` で起動します
- `http://127.0.0.1:8266` の Plaza に自身を登録します

### ターミナル 4: prompted analyst pulser の起動

ニュースおよび Ollama エージェントが既に実行されていることを確認してから、これを起動してください。起動時に pulser がサンプルチェーンの検証を行うためです。
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

期待される結果:

- プロンプトされたアナリスト pulser は `http://127.0.0.1:8270` で起動します
- `http://127.0.0.1:8266` の Plaza に自身を登録します

### ターミナル 5: パーソナルエージェントの起動
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

期待される結果:

- パーソナルエージェントが `http://127.0.0.1:8061` で起動します

### Prompted Analyst Pulser を直接試す

開く:

- `http://127.0.0.1:8270/`

次に、`NVDA` で以下の pulses をテストします:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

推奨パラメータ:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

表示される内容：

- `news_desk_brief` は、アップストリームの記事を PM スタイルの見解と短いノートに変換します
- `news_monitoring_points` は、同じ生の記事を監視項目とリスクフラグに変換します
- `news_client_note` は、同じ生の記事をよりクリーンなクライアント向けノートに変換します

重要な点は、アナリストが 1 つのファイルで Prompits を制御し、ダウンストリームのユーザーは安定した pulse インターフェースのみを表示することです。

### 他のユーザーの視点からパーソナルエージェントを使用する

開く：

- `http://127.0.0.1:8061/`

その後、以下のパスを進みます：

1. `Settings` を開きます。
2. `Connection` タブに移動します。
3. Plaza URL を `http://127.0.0.1:8266` に設定します。
4. `Refresh Plaza Catalog` をクリックします。
5. `New Browser Window` を作成します。
6. ブラウザウィンドウを `edit` モードにします。
7. 最初の plain pane を追加し、`DemoAnalystNewsWirePulser -> news_article` を指定します。
8. pane params を使用します：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. `Get Data` をクリックして、ユーザーが生のニュース記事を確認できるようにします。
10. 2つ目のプレーンペインを追加し、`DemoAnalystPromptedNewsPulser -> news_desk_brief` を指定します。
11. 同じパラメータを再利用して `Get Data` をクリックします。
12. `news_monitoring_points` または `news_client_note` を使用して、3つ目のペインを追加します。

表示される内容：

- 1つのペインには、別のエージェントからの生のアップストリームニュースが表示されます
- 次のペインには、アナリストによって処理されたビューが表示されます
- 3つ目のペインには、同じアナリスト用プロンプトパックが、異なるオーディエンスに対して異なるサーフェスを公開できることが示されます

これが主要なコンシューマー・ストーリーです。他のユーザーは内部のチェーンを知る必要はありません。単に Plaza を閲覧し、pulse を選択して、完成したアナリストの出力を消費するだけです。

## アナリストがプロンプトフローをカスタマイズする方法

デモ2には、主に3つの編集ポイントがあります。

### 1. アップストリームのニュースパケットを変更する

編集箇所:

- `demos/pulsers/analyst-insights/news_wire_step.py`

ここでは、アップストリームのソースエージェントが公開するシード記事を変更します。

### 2. アナリスト自身のプロンプトを変更する

編集箇所:

- `demosের/pulsers/analyst-insights/analyst_news_ollama_step.py`

このファイルには、以下を含むアナリスト所有のプロンプトパックが含まれています。

- プロンプトプロファイル名
- 対象読者と目的
- トーンと執筆スタイル
- 必要なJSON出力コントラクト

これは、同じ生ニュースから異なる調査の語り口を生み出すための最も速い方法です。

### 3. 公開Pulseカタログを変更する

編集箇所:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

このファイルは、以下を制御します。

- どの prompted pulses が存在するか
- 各 pulse がどのプロンプトプロファイルを使用するか
- どのアップストリームエージェントを呼び出すか
- ダウンストリームユーザーに表示される入力および出力スキーマ

## なぜこの高度なパターンが有用なのか

- 上流のニュースエージェントは、後で YFinance、ADS、または内部のコレクターに交換可能です
- アナリストは、UI に単発のメモをハードコーディングするのではなく、プロンプトパックの所有権を保持します
- 異なるコンシューマーは、背後にある完全なチェーンを知ることなく、異なる pulses を使用できます
- パーソナルエージェントは、ロジックが格納される場所ではなく、クリーンなコンシューマー・サーフェスになります
