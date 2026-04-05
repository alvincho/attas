# Phemacast パーソナルエージェント

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

## ドキュメント

- [詳細ユーザーガイド](./docs/user_guide.md)
- [現在の機能一覧](./docs/current_features.md)

このパッケージは、同じローカルファースト（local-first）の構成を維持しています：

- FastAPI が HTML シェルと JSON API を提供します。
- React がインタラクティブなクライアント UI を担当します。
- Plaza カタログと Pulser の実行は、引き続きバックエンドのプロキシルートを経由します。
- モックのダッシュボードデータは、初期の製品開発に引き続き利用可能です。
- 現在のライブランタイムは `static/personal_agent.jsx` から提供されるため、フロントエンドのバンドルを待つことなく、初期開発において即座にリビルドが機能します。

## パッケージ構成

- `app.py`: FastAPIのエントリポイントとルート
- `data.py`: ダッシュボードのスナップショットへのアクセス
- `plaza.py`: Plazaカタログとpulserプロキシヘルパー
- `templates/index.html`: Reactアプリを起動するためのHTMLシェル
- `static/`: FastAPIによって提供されるライブJSXランタイムとCSS
- `ui/`: 将来的なReact + TypeScript + Viteのソースコード構成
- `docs/current_features.md`: レガシープロトタイプから取得された完全な機能一覧

## ローカルでの実行

リポジトリのルートから：
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

ライブアプリは `static/personal_agent.jsx` から直接実行されます。

`ui/` ディレクトリは、後でバンドルされたビルドに昇格させることを意図して用意されています。ライブランタイムに触れることなくそのスキャフォールドを試したい場合は、`phemacast/personal_agent/ui` 内から以下を実行できます：
```bash
npm install
npm run build
```

これは `phemacast/personal_agent/ui/dist` に出力されます。

その後、`http://127.0.0.1:8041` を開きます。
