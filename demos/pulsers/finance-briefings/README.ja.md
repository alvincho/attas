# 金融ブリーフィング・ワークフローのデモ

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

## このデモの内容

- Attasが所有する`FinancialBriefingPulser`による、workflow-seed pulsesおよびfinance briefing step pulsesの公開
- ワークフローエントリコンテキストPulse：
  - `prepare_finance_briefing_context`
  - `workflow_name`によるワークフローの識別：`morning_desk_briefing`、`watchlist_check`、または`research_roundup`
- 共有される金融ステップPulse：
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_briefing_payload`
- ダウンストリームの公開/エクスポートPulse：
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## 存在理由

MapPhemar は、pulsers と pulses を呼び出すことで図を実行します。finance briefing のワークフローは、当初 `attas` 内の単純な Python 関数として始まりましたが、現在の図ではこれらのワークフローを編集可能なステップノードに分割しているため、ランタイムは現在、汎用的な MCP ラッパーではなく Attas ネイティブの pulser を使用しています。

ランタイムのインターフェースは以下の通りです：

- [finance-briefings.pulser](./finance-briefings.pulser): `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser` のデモ設定
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): ワークフローのシードとステップの pulses を保持する Attas 所有の pulser クラス
- [briefings.py](../../../attas/workflows/briefings.py): pulser によって使用される公開 finance briefing ステップヘルパー

## 実行時の前提条件

- Plaza: `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser`: `http://127.0.0.1:8271`

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

これは、1つのターミナルからローカルの Plaza と金融ブリーフィング pulser を起動し、ブラウザのガイドページを開き、pulser UI を自動的に開きます。

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

ネイティブの Windows Python 環境を使用してください。PowerShell でリポジトリのルートから以下を実行します：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher finance-briefings
```

ブラウザのタブが自動的に開かない場合は、ランチャーを実行したまま、出力された `guide=` URL を Windows のブラウザで開いてください。

## 手動起動

リポジトリのルートから：
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## 関連する図面ファイル

これらの図面は `demos/files/diagrams/` にあります：

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

各図面は同じ編集可能な構造に従っています：

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## 現在の MapPhemar への適合性

これらのワークフローは、新しいノードタイプやスキーマを追加することなく、現在の MapPhemar モデルに適合します：

- 実行可能なステップは通常の `rectangle` ノードです
- 境界には `pill` を使用します
- 分岐は `branch` を通じて利用可能です
- アーティファクトのファンアウト（fan-out）は、ワークフローノードからの複数の出力エッジによって処理されます

現在の実行時の制限：

- `Input` は正確に 1 つの下流ノードに接続できるため、ファンアウトは `Input` から直接ではなく、最初の実行可能なワークフローノードの後に発生する必要があります

これらの段階的な金融ワークフローには、新しい MapPhemar ノードタイプやスキーマの拡張は必要ありませんでした。通常の実行可能ノードと Attas pulser サーフェスがあれば、現在の保存、編集、実行には十分です。
