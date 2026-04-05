# ADS Pulser デモ

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

## このデモの範囲

- `ADSPulser` がどのように正規化された ADS テーブル上に構築されているか
- ディスパッチャ (dispatcher) とワーカー (worker) のアクティビティが、どのように pulser で確認可能なデータに変換されるか
- 独自のコレクター (collectors) がどのように ADS テーブルにデータを格納し、既存の pulses を通じて表示されるか

## セットアップ

クイックスタートはこちらを参照してください：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

または、リポジトリのルートから pulser に特化した単一コマンドのラッパーを使用してください：
```bash
./demos/pulsers/ads/run-demo.sh
```

このラッパーは `data-pipeline` と同じ SQLite ADS スタックを起動しますが、pulser-first のウォークスルーに焦点を当てたブラウザガイドとタブを開きます。

以下が開始されます：

1. ADS dispatcher
2. ADS worker
3. ADS pulser
4. boss UI

## プラットフォーム クイック スタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## Pulser の初回確認

サンプルジョブが終了したら、以下を開いてください：

- `http://127.0.0.1:9062/`

次に、以下をテストします：

1. `{"symbol":"AAPL","limit":1}` を使用した `security_master_lookup`
2. `{"symbol":"AAPL","limit":5}` を使用した `daily_price history`
3. `{"symbol":"AAPL"}` を使用した `company_profile`
4. `{"symbol":"AAPL","number_of_articles":3}` を使用した `news_article`

## ADS が異なる理由

他の pulser デモの多くは、ライブプロバイダーまたはローカルストレージのバックエンドから直接読み取ります。

`ADSPulser` は、ADS パイプラインによって書き込まれた正規化されたテーブルから読み取ります。

- workers がソースデータを収集または変換します
- dispatcher が正規化された行を永続化します
- `ADSPulser` はそれらの行をクエリ可能な pulses として公開します

これにより、独自のソースアダプターを追加する方法を説明するための最適なデモとなります。

## 独自のソースを追加する

具体的な手順は以下にあります：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

こちらのカスタム例を使用してください：

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

これらの例では、ユーザー定義のコレクターが以下に書き込む方法を示しています：

- `ads_news`（`news_article` を通じて利用可能になります）
- `ads_daily_price`（`daily_price_history` を通じて利用可能になります）
