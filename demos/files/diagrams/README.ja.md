# デモ図解ライブラリ

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

## プラットフォームに関する注意

このフォルダには JSON アセットが含まれており、単体で動作するランチャーではありません。

### macOS および Linux

まずペアになっているデモのいずれかを起動し、次にこれらのファイルを MapPhemar または Personal Agent に読み込んでください：
```bash
./demos/personal-research-workbench/run-demo.sh
```

以下の方法でも起動できます：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

ペアとなる demo ランチャーには、ネイティブの Windows Python 環境を使用してください。例：`py -3 -m scripts.demo_launcher analyst-insights` および `py -3 -m scripts.demo_launcher finance-briefings`。スタックの実行後、タブが自動的に開かない場合は、表示された `guide=` URL を Windows ブラウザで開いてください。

## このフォルダの内容

2つのグループの例があります：

- テクニカル分析図：OHLC市場データをインジケーター系列に変換します
- LLM指向のアナリスト図：生の市場ニュースを構造化されたリサーチノートに変換します
- 金融ワークフロー図：正規化されたリサーチ入力を、ブリーフィング、出版、および NotebookLM エクスポート用のバンドルに変換します

## このフォルダ内のファイル

### テクニカル分析

- `ohlc-to-sma-20-diagram.json`: `入力 -> OHLCバー -> SMA 20 -> 出力`
- `ohlc-to-ema-50-diagram.json`: `入力 -> OHLCバー -> EMA 50 -> 出力`
- `ohlc-to-macd-histogram-diagram.json`: `入力 -> OHLCバー -> MACDヒストグラム -> 出力`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `入力 -> OHLCバー -> ボリンジャーバンド幅 -> 出力`
- `ohlc-to-adx-14-diagram.json`: `入力 -> OHLCバー -> ADX 14 -> 出力`
- `ohlc-to-obv-diagram.json`: `入力 -> OHLCバー -> OBV -> 出力`

### LLM / アナリスト調査

- `analyst-news-desk-brief-diagram.json`: `入力 -> ニュースデスクブリーフ -> 出力`
- `analyst-news-monitoring-points-diagram.json`: `入力 -> モニタリングポイント -> 出力`
- `analyst-news-client-note-diagram.json`: `入力 -> クライアントノート -> 出力`

### 金融ワークフローパック

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `入力 -> モーニングコンテキストの準備 -> 金融ステップ Pulse -> ブリーフィングの組み立て -> Report Phema + NotebookLM パック -> 出力`
- `finance-watchlist-check-notebooklm-diagram.json`: `入力 -> ウォッチリストコンテキストの準備 -> 金融ステップ Pulse -> ブリーフィングの組み立て -> Report Phema + NotebookLM パック -> 出力`
- `finance-research-undup-notebooklm-diagram.json`: `入力 -> リサーチコンテキストの準備 -> 金融ステップ Pulse -> ブリーフィングの組み立て -> Report Phema + NotebookLM パック -> 出力`

これら3つの保存された Phemas は、編集のために個別に保持されますが、同じ workflow-entry pulse を共有しており、ノード `paramsText.workflow_name` によってワークフローを区別します。

## 実行時の前提条件

これらの図面は具体的なローカルアドレスで保存されているため、期待されるデモスタックが利用可能な場合、追加の編集なしで実行できます。

### テクニカル分析図面

インジケーター図面は以下を前提としています：

- Plaza: `http://127.0.0.1:8011`
- `YFinancePulser`: `http://127.0.0.1:8020`
- `TechnicalAnalysisPulser`: `http://127.0.0.1:8033`

これらの図面で参照されているpulser設定は以下にあります：

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### LLM / アナリスト図面

LLM指向の図面は以下を前提としています：

- Plaza: `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser`: `http://127.0.0.1:8270`

そのprompted analyst pulser自体は以下に依存しています：

- `news-wire.pulser`: `http://127.0.0.1:8268`
- `ollama.pulser`: `http://127.0.0.1:8269`

これらのデモファイルは以下にあります：

- `demos/pulsers/analyst-insights/`

### 金融ワークフロー図面

金融ワークフロー図面は以下を前提としています：

- Plaza: `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser`: `http://127.0.0.1:8271`

そのデモpulserは、以下によってバックエンドが提供されるAttas所有の`FinancialBriefingPulser`です：

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

これらの図面は、通常の図面をバックエンドとするPhema JSONファイルであるため、MapPhemarと組み込まれたPersonal Agent MapPhemarルートの両方で編集可能です。

## クイックスタート

### オプション 1: ファイルを MapPhemar に読み込む

1. MapPhemar エディターのインスタンスを開きます。
2. このフォルダ内の JSON ファイルの 1 つを読み込みます。
3. 保存された `plazaUrl` と pulser アドレスがローカル環境と一致していることを確認してください。
4. 下記のサンプルペイロードの 1 つを使用して `Test Run` を実行します。

サービスで異なるポートや名前を使用している場合は、以下を編集してください：

- `meta.map_phemar.arg.plazaUrl`
- 各ノードの `pulserName`
- 各ノードの `pulserAddress`

### オプション 2: シードファイルとして使用する

これらの JSON ファイルを `phemas/` ディレクトリ内の任意の MapPhemar プールにコピーし、personal-research-workbench デモと同じ方法でエージェント UI を介して読み込むこともできます。

## 入力サンプル

### テクニカル分析図

以下のペイロードを使用してください：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

期待される結果：

- `OHLC Bars` ステップが履歴バーシリーズを取得します
- インジケーターノードが `values` 配列を計算します
- 最終的な出力はタイムスタンプ/値のペアを返します

### LLM / アナリスト図解

次のようなペイロードを使用します：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

期待される結果：

- プロンプトによる analyst pulser が生のニュースを取得します
- prompt pack がそのニュースを構造化されたアナリストビューに変換します
- 出力には `desk_note`、`monitor_now`、`client_note` などの調査にそのまま使えるフィールドが含まれます

### 金融ワークフロー図

次のようなペイロードを使用します：
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

期待される結果：

- ワークフローコンテキストノードが選択された金融ワークフローをシードします
- 中間金融ノードがソース、引用、事実、リスク、カタリスト、対立、要点、質問、および要約ブロックを構築します
- アセンブリノードが `attas.finance_briefing` ペイロードを構築します
- レポートノードがそのペイロードを静的な Phema に変換します
- NotebookLM ノードが同じペイロードからエクスポートアーティファクトを生成します
- 最終的な出力は、MapPhemar または Personal Agent での検査のために 3 つの結果すべてをマージします

## 現在のエディタの制限

これらの金融ワークフローは、新しいノードタイプを追加することなく、現在の MapPhemar モデルに適合します。

実行時に適用される重要なルールがまだ2つあります：

- `Input` は、必ず1つの下流のシェイプに接続されている必要があります
- すべての実行可能な非分岐ノードは、pulse と到達可能な pulser を参照する必要があります

つまり、ワークフローのファンアウト（fan-out）は最初の実行可能ノードの後に発生させる必要があり、図をエンドツーエンドで実行したい場合は、ワークフローのステップを pulser でホストされる pulse として公開し続ける必要があります。

## 関連デモ

図表の確認だけでなく、サポートサービスを実行したい場合は、以下を参照してください：

- `demos/personal-research-workbench/README.md`: シードされたRSIの例を用いた視覚的な図解ワークフロー
- `demos/pulsers/analyst-insights/README.md`: LLM指向の図解で使用される、プロンプト化されたアナリストニューススタック
- `demos/pulsers/llm/README.md`: OpenAIおよびOllama用のスタンドアロンな `llm_chat` pulserデモ

## 検証

これらのファイルはリポジトリのテストによってカバーされています：
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

このテストスイートは、保存された図が、モックまたはリファレンスの pulser フローに対してエンドツーエンドで実行されることを検証します。
