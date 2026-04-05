# 公開デモガイド

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

最初に試すデモを一つ選ぶ場合は、以下の順序で実行してください：

1. [`hello-plaza`](./hello-plaza/README.md): 最も軽量なマルチエージェント発見デモ。
2. [`pulsers`](./pulsers/README.md): ファイルストレージ、YFinance、LLM、および ADS pulsers に焦点を当てたデモ。
3. [`personal-research-workbench`](./personal．personal-research-workbench/README.md): 最も視覚的な製品ウォークスルー。
4. [`data-pipeline`](./data-pipeline/README.md): boss UI と pulser を備えた、ローカル SQLite バックエンドの ADS パイプライン。

## シングルコマンドランチャー

各実行可能な demo フォルダには、`run-demo.sh` ラッパーが含まれるようになりました。これにより、1 つのターミナルから必要なサービスを起動し、言語選択機能付きのブラウザガイドページを開き、メインの demo UI ページを自動的に開くことができます。

ブラウザのタブを開かずにラッパーをターミナル内に留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから、仮想環境を一度作成して要件をインストールした後、`./demos/hello-plaza/run-demo.sh` などのデモラッパーを実行します。
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから、同じコマンドを実行します：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## 共有設定

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

ほとんどのデモは長時間実行されるプロセスをいくつか開始するため、通常は2〜4つのターミナルウィンドウを開いておく必要があります。

これらのデモフォルダは、その実行状態を `demos/.../storage/` に書き込みます。この状態は git によって無視されるため、自由に実験を行うことができます。

## デモカタログ

### [`hello-plaza`](./hello-plaza/README.md)

- 対象読者: 初心者開発者
- ランタイム: Plaza + worker + ブラウザ向けユーザーエージェント
- 外部サービス: なし
- 証明内容: エージェントの登録、発見、およびシンプルなブラウザUI

### [`pulsers`](./pulsers/README.md)

- 対象読者: 小規模で直接的な pulser の例を求める開発者
- ランタイム: 小規模な Plaza + pulser スタック、および SQLite パイプラインを再利用する ADS pulser ガイド
- 外部サービス: ファイルストレージ用はなし、YFinance および OpenAI 用の外部インターネット、Ollama 用のローカル Ollama デーモン
- 証明内容: スタンドアロンの pulser パッケージング、テスト、プロバイダー固有の pulse の動作、アナリストが独自の構造化された、またはプロンプト駆動のインサイト pulse を公開する方法、および消費者の視点から個人のエージェント内でそれらの pulse がどのように見えるか

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- 対象読者: より強力な製品デモを求める人
- ランタイム: React/FastAPI ワークベンチ + ローカル Plaza + ローカルファイルストレージ pulser + オプションの YFinance pulser + オプションの technical-analysis pulser + シード付き図面ストレージ
- 外部サービス: ストレージフロー用はなし、YFinance チャートフローおよびライブ OHLC-to-RSI 図面フロー用の外部インターネット
- 証明内容: ワークスペース、レイアウト、Plaza ブラウジング、チャートレンダリング、およびより豊かな UI からの図面駆動型 pulser 実行

### [`data-pipeline`](./data-pipeline/README.md)

- 対象読者: オーケストレーションと正規化されたデータフローを評価する開発者
- ランタイム: ADS dispatcher + worker + pulser + boss UI
- 外部サービス: デモ設定にはなし
- 証明内容: キューイングされたジョブ、worker の実行、正規化されたストレージ、pulser を介した再公開、および独自のデータソースをプラグインするためのパス

## 公開ホスティング用

これらのデモは、ローカルでの実行が成功した後、簡単にセルフホストできるように設計されています。公開する場合、最も安全なデフォルト設定は以下の通りです：

- ホストされているデモを読み取り専用にするか、スケジュールに従ってリセットする
- 最初の公開バージョンでは、APIベースまたは有料の統合はオフにしておいてください
- demoで使用されている設定ファイルをユーザーに案内し、直接forkできるようにします
- live URL の隣に demo README の正確なローカルコマンドを含める
