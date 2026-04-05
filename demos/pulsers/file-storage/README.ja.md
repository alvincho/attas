# System Pulser デモ

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

- `plaza.agent`: この pulser デモ用のローカル Plaza
- `file-storage.pulser`: ローカルファイルシステムをバックエンドとするストレージ pulser
- `start-plaza.sh`: Plaza を起動する
- `start-pulser.sh`: pulser を起動する
- `run-demo.sh`: 1つのターミナルからフルデモを起動し、ブラウザガイドと pulser UI を開きます

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/pulsers/file-storage/run-demo.sh
```

これは、1つのターミナルから Plaza と `SystemPulser` を起動し、ブラウザのガイドページを開き、pulser UI を自動的に開きます。

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したまま、出力された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## クイックスタート

リポジトリのルートから2つのターミナルを開きます。

### ターミナル 1: Plaza を起動
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

期待される結果:

- Plaza は `http://127.0.0.1:8256` で起動します

### ターミナル 2: pulser を起動します
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

期待される結果:

- pulser が `http://127.0.0.1:8257` で起動します
- `http://127.0.0.1:8256` の Plaza に自身を登録します

## ブラウザで試す

開く:

- `http://127.0.0.1:8257/`

次に、以下の pulses を順番にテストしてください:

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

`bucket_create` の推奨パラメータ:
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

`object_save` の推奨パラメータ：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

`object_load` の推奨パラメータ：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Curl で試す

バケットを作成します：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

オブジェクトを保存する：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

再読み込み:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## 特徴

- この pulser は完全にローカルで動作し、クラウドの認証情報は必要ありません
- ペイロードは非常にシンプルで、追加のツールなしでも理解できます
- ストレージバックエンドは、後でファイルシステムから他のプロバイダーに切り替えることができ、pulse インターフェースの安定性を維持できます

## 独自の構築

カスタマイズしたい場合は：

1. `file-storage.pulser` をコピーします
2. ポートとストレージの `root_path` を変更します
3. workbench や既存の例との互換性を維持したい場合は、同じ pulse surface を保持してください
