# Prompits 設定例

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

## ファイル

- `plaza.agent`: ローカルの `FileSystemPool` を持つ Plaza
- `worker.agent`: Plaza に自動登録される基本的な `StandbyAgent`
- `user.agent`: Plaza ブラウザ UI を公開する `UserAgent`

## 実行順序

リポジトリのルートから：
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

次に `http://127.0.0.1:8214/` にアクセスします。

## ストレージ

例の構成では、ローカルの状態を以下に書き込みます：
```text
prompits/examples/storage/
```

そのディレクトリは `FileSystemPool` によって自動的に作成されます。
