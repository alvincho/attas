# YFinance Pulser デモ

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

## このフォルダ内のファイル

- `plaza.agent`: このデモ用のローカル Plaza
- `yfinance.pulser`: `YFinancePulser` 用のローカルデモ設定
- `start-plaza.sh`: Plaza を起動
- `start-pulser.sh`: pulser を起動
- `run-demo.sh`: 1つのターミナルからフルデモを起動し、ブラウザガイドと pulser UI を開く

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/pulsers/yfinance/run-demo.sh
```

これは、1つのターミナルから Plaza と `YFinancePulser` を起動し、ブラウザのガイドページを開き、pulser UI を自動的に開きます。

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイック スタート

### macOS および Linux

リポジトリのルートから:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

WSLからブラウザのタブが自動的に開かない場合は、ランチャーを実行したままにし、出力された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## クイックスタート

リポジトリのルートから2つのターミナルを開きます。

### ターミナル 1: Plaza を起動
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

期待される結果:

- Plaza は `http://127.0.0.1:8251` で起動します

### ターミナル 2: pulser を起動する
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

期待される結果:

- pulser は `http://127.0.0.1:8252` で起動します
- `http://127.0.0.1:8251` の Plaza に自身を登録します

注意:

- このデモには外部インターネットアクセスが必要です。pulser が `yfinance` を介してライブデータを取得するためです
- Yahoo Finance は、リクエストのレート制限を行ったり、断続的に拒否したりする場合があります

## ブラウザで試す

開く:

- `http://127.0.0.1:8252/`

推奨される最初の pulses:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

`last_price` に推奨されるパラメータ:
```json
{
  "symbol": "AAPL"
}
```

`ohlc_bar_series` の推奨パラメータ：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Curl で試す

見積依頼:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC シリーズのリクエスト:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## ポイント

- 同じ pulser がスナップショット形式 (snapshot-style) と時系列形式 (time-series-style) の両方の pulses を提供します
- `ohlc_bar_series` は workbench chart demo および technical-analysis path pulser と互換性があります
- pulse contract はそのままに、後から live provider を内部的に変更することが可能です

## 独自のものを構築する

このデモを拡張したい場合は：

1. `yfinance.pulser` をコピーします
2. ポートとストレージパスを調整します
3. より小規模またはより特化したカタログが必要な場合は、サポートされている pulse 定義を変更または追加します
