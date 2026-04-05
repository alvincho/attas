# Retis 金融インテリジェンス・ワークスペース

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

このリポジトリは、金融インテリジェンスシステム向けのマルチエージェント・ワークスペースです。

詳しくは [retis.ai](https://retis.ai) をご覧ください。Attas の製品ページは [retis.ai/products/attas](https://retis.ai/products/attas) です。

このリポジトリは現在、相互に関連する複数のコードベースをまとめています：

- `prompits`: HTTP ネイティブなエージェント、Plaza の探索、プール、遠隔 practice 実行のための Python インフラ
- `phemacast`: Prompits 上に構築された協調型コンテンツ・パイプライン
- `attas`: より高水準の金融指向エージェントパターンと Pulse 定義
- `ads`: 正規化された金融データセットをより広いシステムに供給するデータサービスおよび収集コンポーネント

## ステータス

このリポジトリは活発に開発されており、現在も進化を続けています。プロジェクトの分割、安定化、またはより正式なパッケージ化に伴い、API、設定形式、および例のフローが変更される可能性があります。

以下の2つの領域は特に初期段階にあり、活発に開発されている間は急速に変わる可能性があります：

- `prompits.teamwork`
- `phemacast` `BossPulser`

公開リポジトリの目的は以下の通りです：

- ローカル開発
- 評価
- プロトタイプ・ワークフロー
- アーキテクチャの探索

まだ完成された製品や、単一のコマンドで実行できる本番環境へのデプロイメントではありません。

## 新規クローンのクイックスタート

新しくチェックアウトした状態から：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

smoke スクリプトは、コミットされたリポジトリの状態を一時ディレクトリにクローンし、独自の virtualenv を作成して依存関係をインストールし、公開向けのテストスイートを実行します。これは、GitHub ユーザーが実際にプルする内容に最も近い近似です。

代わりに、最新の未コミットのローカル変更をテストしたい場合は、以下を使用してください：
```bash
attas_smoke --worktree
```

このモードでは、未コミットの変更や、無視されていない未追跡のファイルを含む現在のワーキングツリーを、一時的なテストディレクトリにコピーします。

リポジトリのルートから、以下のコマンドも実行できます：
```bash
bash attas_smoke
```

リポジトリツリー内の任意のサブディレクトリから、以下を実行できます：
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

このランチャーはリポジトリのルートを見つけ、同じスモークテストフローを開始します。`attas_smoke` を `PATH` 内のディレクトリにシンボリックリンクとして作成すれば、どこからでも再利用可能なコマンドとして呼び出すことができ、リポジトリツリーの外で作業する場合は、オプションで `FINMAS_REPO_ROOT` を設定することも可能です。

## ローカルファースト・クイックスタート

現在、最も安全なローカルパスは Prompits の例スタックです。Supabase やその他のプライベートなインフラストラクチャを必要とせず、ベースラインのデスクトップスタック向けに、単一コマンドでのローカルブートストラップフローが利用可能になりました：
```bash
python3 -m prompits.cli up desk
```

以下を開始します：

- `http://127.0.0.1:8211` の Plaza
- `http://127.0.0.1:8212` のベースライン worker
- `http://127.0.0.1:8214/` のブラウザ向けユーザー UI

ラッパースクリプトを使用することもできます：
```bash
bash run_plaza_local.sh
```

便利な後続コマンド：
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

一度に1つのサービスをデバッグするための古い手動フローが必要な場合は、以下を使用してください：
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

以前の Supabase バックエンドの Plaza 設定を使用する場合は、`PROMPITS_AGENT_CONFIG` を
`attas/configs/plaza.agent` に指定し、必要な環境変数を提供してください。

## リモートプラクティス・ポリシーと監査

Prompits は、リモートの `UsePractice(...)` 呼び出しに対して、軽量なクロスエージェント・ポリシーおよび監査レイヤーをサポートするようになりました。コントラクトはエージェント設定 JSON のトップレベルに存在し、`prompits` 内でのみ使用されます：
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

ポリシーに関する注意：

- `outbound` ルールは、`practice_id`、`target_agent_id`、`target_name`、`target_address`、`target_role`、および `target_pit_type` を使用して送信先と照合します。
- `inbound` ルールは、`practice_id`、`caller_agent_id`、`caller_name`、`caller_address`、`auth_mode`、および `plaza_url` を使用して呼び出し元と照合します。
- 拒否ルールが優先されます。許可リストが存在する場合、リモートコールはそれに一致する必要があります。一致しない場合は `403` で拒否されます。
- 監査行はログに記録され、エージェントにプールがある場合は、リクエストと結果のイベント間で相関させるために、共有の `request_id` を使用して設定された監査テーブルに追加されます。

## リポジトリの構成
```text
attas/       Finance-oriented agent, pulse, and personal-agent work
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## ガイド

- コア・ランタイム・モデルについては `prompits/README.md` から始めてください。
- コンテンツ・パイプライン・レイヤーについては `phemacast/README.md` を読んでください。
- 金融ネットワークのフレームワークと高レベルの概念については `attas/README.md` を読んでください。
- データサービス・コンポーネントについては `ads/README.md` を読んでください。

## コンポーネントのステータス

| エリア | 現在の公開ステータス | 備考 |
| --- | --- | --- |
| `prompits` | 最良の開始点 | Local-firstな例とコアランタイムが、最も簡単な公開エントリーポイントです。`prompits.teamwork` パッケージはまだ初期段階であり、急速に変更される可能性があります。 |
| `attas` | 初期公開 | コアコンセプトとユーザーエージェントの作業は公開されていますが、未完成のコンポーネントの一部は、デフォルトのフローから意図的に隠されています。 |
| `phemacast` | 初期公開 | コアパイプラインのコードは公開されています。一部のレポート/レンダリングコンポーネントは、現在整理および安定化の最中です。`BossPulser` は現在も活発に開発されています。 |
| `ads` | 上級向け | 開発や研究に有用ですが、一部のデータワークフローには追加の設定が必要であり、初回実行時のパスには含まれません。 |
| `deploy/` | 例示のみ | デプロイヘルパーは環境に依存するため、洗練された公開デプロイメントストーリーとして扱うべきではありません。 |
| `mcp_servers/` | 公開ソース | ローカルのMCPサーバー実装は、公開ソースツリーの一部です。 |

## 既知の制限事項

- 一部のワークフローでは、オプションの環境変数やサードパーティサービスがまだ必要であると想定されています。
- `tests/storage/` には有用なフィクスチャが含まれていますが、理想的な公開フィクスチャセットと比較して、決定論的なテストデータと、より変更可能なローカルスタイルの状態が混在しています。
- デプロイスクリプトは例示であり、サポートされている本番用プラットフォームではありません。
- リポジトリは急速に進化しているため、一部の設定やモジュールの境界が変更される可能性があります。

## ロードマップ

短期的な公開ロードマップは `docs/ROADMAP.md` で追跡されます。

計画されている `prompits` の機能には、エージェント間での認証および権限付与された `UsePractice(...)` の呼び出しが含まれ、実行前にコスト交渉と支払い処理が行われます。

計画されている `phemacast` の機能には、より豊かな人間知能の `Phemar` 表記、より広範な `Castr` 出力形式、フィードバック、効率、コストに基づいた AI 生成の `Pulse` 精緻化、および `MapPhemar` におけるより広範な図面サポートが含まれます。

計画されている `attas` の機能には、よりコラボレーティブな投資およびトレジャリーワークフロー、金融専門家向けに調整されたエージェントモデル、およびベンダーやサービスプロバイダー向けの API エンドポイントから `Pulse` への自動マッピングが含まれます。

## 公開リポジトリの注意点

- シークレットは、コミットされたファイルではなく、環境変数やローカル設定から取得されることを想定しています。
- ローカルデータベース、ブラウザのアーティファクト、および一時的なスナップショットは、意図的にバージョン管理から除外されています。
- 現在のコードベースは、洗練されたエンドユーザー向けパッケージングよりも、評価、ローカル開発、およびプロトタイプ・ワークフローを主な対象としています。

## 貢献について

これは現在、単一の主要なメンテナーによる公開リポジトリです。Issue やプルリクエストは歓迎しますが、ロードマップやマージの決定は、今のところメンテナー主導となります。現在のワークフローについては `CONTRIBUTING.md` を参照してください。

## ライセンス

このリポジトリは Apache License 2.0 の下でライセンスされています。全文については `LICENSE` を参照してください。
