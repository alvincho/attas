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

`attas` の目標は、世界中の金融プロフェッショナルがつながるネットワークを支えることです。各参加者は自分専用のエージェントを運用し、そのエージェントを通じて専門知識を共有しながら、知的財産を保護できます。このモデルでは、プライベートなプロンプト、ワークフロー・ロジック、アルゴリズム、その他の内部手法は、所有者のエージェントの中に残ります。他の参加者は、基盤となるロジックを直接受け取るのではなく、そこから生まれる出力やサービスを利用します。

## ステータス

このリポジトリは積極的に開発されており、現在も進化を続けています。プロジェクトの分割、安定化、またはより正式なパッケージ化に伴い、API、設定フォーマット、およびサンプルフローが変更される可能性があります。

以下の2つの領域は特に初期段階にあり、活発な開発中には急速に変化する可能性があります：

- `prompits.teamwork`
- `phemacast` `BossPulser`

公開リポジトリの目的は以下の通りです：

- ローカル開発
- 評価
- プロトタイプ・ワークフロー
- アーキテクチャの探索

まだ完成された製品や、単一のコマンドで実行できる本番環境へのデプロイメントではありません。

## 開発者にとっての `attas` の位置付け

このリポジトリには 3 つの製品レイヤーがあります。

- `prompits` は、汎用的なマルチエージェント・ランタイムおよび Plaza 調整レイヤーです。
- `phemacast` は、`prompits` 上に構築された再利用可能なコンテンツ・コラボレーション・レイヤーです。
- `attas` は、その両方の上に構築された金融アプリケーション・レイヤーです。

開発者にとって、`attas` は金融特有の作業を置くべき場所です。たとえば次のようなものが含まれます。

- 金融向け `Pulse` 定義、マッピング、カタログ、検証例
- 金融向けのエージェント設定、パーソナルエージェントのフロー、ワークフローのオーケストレーション
- アナリスト、トレジャリーチーム、投資ワークフロー向けのブリーフィング、レポートテンプレート、製品挙動
- 金融特有のブランディング、デフォルト設定、ユーザー向け概念

一般的なコンテンツ・コラボレーションとして再利用できる変更なら、`phemacast` に属する可能性が高いです。汎用的なマルチエージェント基盤であれば、`prompits` に属する可能性が高いです。再利用のために `attas` を下位レイヤーへインポートすることは避けてください。

![attas-3-layers-diagram-1.png](static/images/attas-3-layers-diagram-1.png)

## 開発者にとっての `phemacast` の位置付け

`phemacast` は、`prompits` と `attas` の間にある再利用可能なコンテンツ・コラボレーション・レイヤーです。少数のパイプライン概念を通じて、動的な入力を構造化されたコンテンツ出力へ変換します。

- `Pulse`: コンテンツ生成中に使われる動的な入力ペイロードまたはデータのスナップショットです。`phemacast` では、binding、セクション、テンプレート・スロットを埋めるデータを指します。
- `Pulser`: pulse データを取得、計算、または公開するエージェントです。提供可能な pulses を公開し、`get_pulse_data` などの practice endpoint を持ちます。
- `Phema`: 構造化されたコンテンツ・ブループリントです。何を生成するか、出力をどう構成するか、どの pulse binding が必要かを記述します。
- `Phemar`: pulsers から pulse データを集め、そのデータを `Phema` 構造に埋め込むことで、`Phema` を静的なペイロードへ解決するエージェントです。

典型的な `phemacast` の流れは次の通りです。

1. 作成者が `Phema` を定義または選択します。
2. `Pulser` がその `Phema` に必要な pulse 入力を提供します。
3. `Phemar` がそれらの pulse 値をブループリントへ組み込み、構造化された結果を生成します。
4. `Castr` または下流のレンダラーが、その結果を markdown、JSON、テキスト、ページ、スライド、その他の対象者向け形式に変換します。

開発者にとって、`phemacast` は再利用可能な pulse 駆動のコンテンツ・ワークフロー、共有レンダリング・ロジック、図ベースのコンテンツ・マッピング、そして金融に特化しないコンテンツ・エージェントに適したレイヤーです。金融データ契約、金融カタログ、金融プロダクト挙動に特化した概念は、`attas` に残すべきです。

## コア・ランタイム概念

低レベルのマルチエージェント・モデルは `prompits` にあり、`phemacast` と `attas` で再利用されます。

- `Pit`: 最小のアイデンティティ単位です。名前、説明、アドレス情報などのメタデータを持ちます。実際には、ランタイム・エージェントはこのアイデンティティ・モデルを共有します。
- `Practice`: エージェントにマウントされる能力です。HTTP ルートを公開し、ローカル実行をサポートし、発見のためのメタデータを公開できます。
- `Pool`: エージェントの永続化境界です。Plaza 資格情報、発見した practice メタデータ、ローカルメモリ、その他の永続的なランタイム状態を保存します。
- `Plaza`: 調整プレーンです。エージェントは Plaza に登録し、資格情報の受け取りと更新、検索可能なカードの公開、heartbeat の送信、peer の発見、メッセージの relay を行います。

エージェント間の接続は通常、次のように動作します。

1. エージェントは 1 つ以上の pool を持って起動し、自身の practices をマウントします。
2. Plaza 自身でなければ Plaza に登録し、安定した `agent_id`、永続的な `api_key`、短時間有効な bearer token を受け取ります。
3. エージェントはそれらの資格情報をプライマリ pool に保存し、Plaza の検索可能なディレクトリに表示されます。
4. 他のエージェントは、名前、ロール、公開された practice などのフィールドで Plaza 検索を行い、そのエージェントを見つけます。
5. その後、Plaza relay と mailbox 形式の endpoint を通じてメッセージを送るか、呼び出し元検証付きで remote practice を直接呼び出すことで通信します。

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

現在、最も安全なローカルパスは Prompits のエキサンプルスタックです。Supabase やその他のプライベートなインフラストラクチャを必要とせず、ベースラインのデスクトップスタック向けに、単一コマンドでのローカルブートストラップフローが利用可能になりました。Python ランチャーは Windows、Linux、macOS でネイティブに動作します。macOS/Linux では `python3` を、Windows では `py -3` を使用してください：
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
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
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
attas/       金融アプリケーション・レイヤー: Pulse カタログ、ブリーフィング、パーソナルエージェントのフロー、金融向け設定
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
- `Pit`、`Practice`、`Pool`、`Plaza`、およびリモートのエージェント・フローの詳細については `docs/CONCEPTS_AND_CLASSES.md` を読んでください。
- コンテンツ・パイプライン・レイヤーについては `phemacast/README.md` を読んでください。
- 金融ネットワークのフレームワークと高レベルの概念については `attas/README.md` を読んでください。
- データサービス・コンポーネントについては `ads/README.md` を読んでください。

## コンポーネントのステータス

| エリア | 現在の公開ステータス | 備考 |
| --- | --- | --- |
| `prompits` | 最良の開始点 | Local-firstな例とコアランタイムが、最も簡単な公開エントリーポイントです。`prompits.teamwork` パッケージはまだ初期段階であり、急速に変更される可能性があります。 |
| `attas` | 初期公開 | コアコンセプトとユーザーエージェントの作業は公開されていますが、未完成のコンポーネントの一部は、デフォルトのフローから意図的に隠されています。 |
| `phemacast` | 初期公開 | コアパイプラインのコードは公開されています。一部のレポート/レンダリングコンポーネントは、現在整理および安定化の最中です。`BossPulser` はまだ活発に開発中です。 |
| `ads` | 上級向け | 開発や研究には有用ですが、一部のデータワークフローには追加の設定が必要であり、初回実行時のパスには含まれません。 |
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
- 現在のコードベースは、洗練されたエンドユーザー向けパッケージングよりも、ローカルの開発、評価、およびプロトタイプ作成のワークフローを主な対象としています。

## 貢献について

これは現在、単一の主要なメンテナーによる公開リポジトリです。Issue やプルリクエストは歓迎しますが、ロードマップやマージの決定は、今のところメンテナー主導となります。現在のワークフローについては `CONTRIBUTING.md` を参照してください。

## ライセンス

このリポジトリは Apache License 2.0 の下でライセンスされています。全文については `LICENSE` を参照してください。
