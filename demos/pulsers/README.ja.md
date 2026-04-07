# Pulser デモセット

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

## ここからスタート

pulser モデルを初めて学習する場合は、以下の順序で使用してください：

1. [`file-storage`](./file-storage/README.md): 最も安全なローカル専用の pulser デモ
2. [`analyst-insights`](./analyst-insights/README.md): アナリストが所有し、再利用可能なインサイトビューとして公開されている pulser
3. [`finance-briefings`](./finance-briefings/README.md): MapPhemar と Personal Agent が実行可能な形式で公開された金融ワークフロー pulse
4. [`yfinance`](./yfinance/README.md): 時系列出力を持つライブ市場データ pulser
5. [`llm`](./llm/README.md): ローカルの Ollama およびクラウドの OpenAI チャット pulser
6. [`ads`](./ads/README.md): SQLite パイプラインデモの一部としての ADS pulser

## シングルコマンドランチャー

実行可能な各 pulser demo フォルダには、`run-demo.sh` ラッパーが含まれるようになりました。これにより、1つのターミナルから必要なローカルサービスを起動し、言語選択が可能なブラウザのガイドページを開き、主要な demo UI ページを自動的に開くことができます。

ブラウザのタブを開かずにラッパーをターミナル内に留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから、一度仮想環境を作成して要件をインストールし、その後 `./demos/pulsers/file-storage/run-demo.sh` などの pulser ラッパーを実行します。
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

ネイティブの Windows Python 環境を使用してください。PowerShell でリポジトリのルートから実行します：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

ブラウザのタブが自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

## このデモセットの範囲

- pulser が Plaza にどのように登録されるか
- ブラウザまたは `curl` を使用してPulseをテストする方法
- pulser を小さなセルフホストサービスとしてパッケージ化する方法
- さまざまな pulser ファミリーの動作：ストレージ、アナリストのインサイト、金融、LLM、およびデータサービス

## 共有設定

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

各 demo フォルダは、ローカルのランタイム状態を `demos/pulsers/.../storage/` に書き込みます。

## デモカタログ

### [`file-storage`](./filelar-storage/README.md)

- ランタイム: Plaza + `SystemPulser`
- 外部サービス: なし
- 証明内容: バケットの作成、オブジェクトの保存/読み込み、およびローカル限定の pulser 状態

### [`analyst-insights`](./analyst-insights/README.md)

- ランタイム: Plaza + `PathPulser`
- 外部サービス: 構造化ビューにはなし、プロンプトによるニュースフローにはローカルの Ollama を使用
- 証明内容: 1人のアナリストが、複数の再利用可能な pulses を通じて、固定されたリサーチビューとプロンプト所有の Ollama 出力の両方を公開し、その後パーソナルエージェントを通じて別のユーザーに公開する方法

### [`finance-briefings`](./finance-briefings/README.md)

- ランタイム: Plaza + `FinancialBriefingPulser`
- 外部サービス: ローカルデモパスにはなし
- 証明内容: Attas 所有の pulser が、金融ワークフローのステップを pulse でアドレス可能な構成要素として公開し、MapPhemar diagrams と Personal Agent が同じワークフローグラフを保存、編集、実行できる方法

### [`yfinance`](./yfinance/README.md)

- ランタイム: Plaza + `YFinancePulser`
- 外部サービス: Yahoo Finance への外部インターネット接続
- 証明内容: スナップショット pulses、OHLC シリーズ pulses、およびチャートに適した出力ペイロード

### [`llm`](./llm/README.md)

- ランタイム: OpenAI または Ollama 用に構成された Plaza + `OpenAIPulser`
- 外部サービス: クラウドモードには OpenAI API、ローカルモードにはローカル Ollama デーモン
- 証明内容: `llm_chat`、共有 pulser エディタ UI、およびプロバイダーを切り替え可能な LLM パイプライン

### [`ads`](./ads/README.md)

- ランタイム: ADS dispatcher + worker + pulser + boss UI
- 外部サービス: SQLite デモパスにはなし
- 証明内容: 正規化されたデータテーブル上の `ADSPulser` と、独自のコレクターがそれらの pulses にどのように流れるか
