# Hello Plaza

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

## このデモのデモンストレーション内容

- ローカルで実行されている Plaza レジストリ
- Plaza に自動登録されるエージェント
- その Plaza に接続されたブラウザ向けユーザー UI
- ビルダーが自身のプロジェクトにコピーできる最小限の構成セット

## このフォルダ内のファイル

- `plaza.agent`: Plaza 設定デモ
- `worker.agent`: worker 設定デモ
- `user.agent`: ユーザーエージェント 設定デモ
- `start-plaza.sh`: Plaza を起動
- `start-worker.sh`: worker を起動
- `start-user.sh`: ブラウザ向け ユーザーエージェント を起動

すべての実行時状態は `demos/hello-plaza/storage/` に書き込まれます。

## 前提条件

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/hello-plaza/run-demo.sh
```

これは、1つのターミナルから Plaza、worker、およびユーザー UI を起動し、ブラウザのガイドページを開き、ユーザー UI を自動的に開きます。

ランチャーをターミナルのみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Ubuntu またはその他の Linux ディストリビューションとともに WSL2 を使用してください。WSL 内のリポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

ブラウザのタブがWSLから自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

ネイティブの PowerShell / Command Prompt ラッパーはまだチェックインされていないため、現在の Windows でサポートされているパスは WSL2 です。

## クイックスタート

リポジトリのルートから3つのターミナルを開きます。

### ターミナル 1: Plaza を起動
```bash
./demos/hello-plaza/start-plaza.sh
```

期待される結果:

- Plaza は `http://127.0.0.1:8211` で起動します
- `http://127.0.0.1:8211/health` は正常なステータスを返します

### ターミナル 2: ワーカーを起動する
```bash
./demos/hello-plaza/start-worker.sh
```

期待される結果：

- worker は `127.0.0.1:8212` で起動します
- it は Terminal 1 から Plaza に自動的に登録されます

### ターミナル 3: ユーザー UI を起動します

```bash
./demos/hello-plaza/start-user.sh
```

期待される結果：

- ブラウザ側のユーザーエージェントが `http://127.0.0.1:8214/` で起動します

## スタックの検証

4番目のターミナル、またはサービスが起動した後に：
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

表示される内容：

- 最初のコマンドは、正常な Plaza のレスポンスを返します
- 2 番目のコマンドは、ローカルの Plaza と登録された `demo-worker` を表示します

次に、以下を開きます：

- `http://127.0.0.1:8214/`

これは、ローカルのウォークスルーや画面録画で共有するための公開デモ URL です。

## デモコールで強調すべき点

- Plaza はディスカバリー層です。
- Worker は独立して起動でき、共有ディレクトリにも表示されます。
- ユーザー向け UI は Worker についてハードコードされた知識を必要としません。Plaza を通じて Worker を検出します。

## 独自のインスタンスを作成する

これを独自のインスタンスに変換する最も簡単な方法は次のとおりです。

1. `plaza.agent`、`worker.agent`、`user.agent` を新しいフォルダにコピーします。
2. エージェントの名前を変更します。
3. 必要に応じてポートを変更します。
4. 各 `root_path` を独自のストレージ場所に指定します。
5. Plaza の URL またはポートを変更した場合は、`worker.agent` と `agent.agent` の `plaza_url` を更新してください。

カスタマイズすべき最も重要な3つのフィールドは次のとおりです。

- `name`: エージェントが自身のアイデンティティとして宣伝するもの
- `port`: HTTP サービスがリッスンする場所
- `root_path`: ローカルの状態が保存される場所

ファイルの設定が正しくなったら、以下を実行します。
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## トラブルシューティング

### ポートが既に使用されています

関連する `.agent` ファイルを編集し、空いているポートを選択してください。Plaza を新しいポートに移動する場合は、依存する両方の設定の `plaza_url` を更新してください。

### ユーザー UI に Plaza ディレクトリが空で表示される

以下の 3 点を確認してください：

- Plaza が `http://127.0.0.1:8211` で実行されている
- worker ターミナルがまだ実行中である
- `worker.agent` が依然として `http://127.0.0.1:8211` を指している

### デモの状態をリセットしたい

最も安全なリセット方法は、既存のデータを削除するのではなく、`root_path` の値を新しいフォルダ名に向けることです。

## デモの停止

各ターミナルウィンドウで `Ctrl-C` を押してください。
