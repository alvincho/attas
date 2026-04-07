# LLM Pulser デモ

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

- `plaza.agent`: 両方の LLM pulser バリアント用のローカル Plaza
- `openai.pulser`: OpenAI がサポートする pulser 設定
- `ollama.pulser`: Ollamaをバックエンドとするpulser設定
- `start-plaza.sh`: Plaza を起動する
- `start-openai-pulser.sh`: OpenAI demo pulser を起動します
- `start-ollama-pulser.sh`: Ollama デモ pulser を起動します
- `run-demo.sh`: 1つのターミナルからフルデモを起動し、ブラウザガイドと選択した pulser UI を開きます

## 単一コマンドでの起動

リポジトリのルートから：
```bash
./demos/pulsers/llm/run-demo.sh
```

デフォルトでは、`OPENAI_API_KEY` が存在する場合に OpenAI を使用し、それ以外の場合は Ollama にフォールバックします。

明示的なプロバイダーの例：
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

ランチャーをターミナル内のみに留めたい場合は、`DEMO_OPEN_BROWSER=0` を設定してください。

## プラットフォーム クイックスタート

### macOS および Linux

リポジトリのルートから：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

ネイティブの Windows Python 環境を使用してください。PowerShell でリポジトリのルートから実行します：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher llm
```

ブラウザのタブが自動的に開かない場合は、ランチャーを実行したまま、表示された `guide=` URL を Windows のブラウザで開いてください。

## クイックスタート

### Plaza の起動

リポジトリのルートからターミナルを開きます：
```bash
./demos/pulsers/llm/start-plaza.sh
```

期待される結果：

- Plaza は `http://127.0.0.1:8261` で起動します

次に、プロバイダーを 1 つ選択してください。

## オプション 1: OpenAI

まず API キーを設定してください：
```bash
export OPENAI_API_KEY=your-key-here
```

次に pulser を起動します：
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

期待される結果:

- pulser は `http://127.0.0.1:8262` で起動します
- `http://127.0.0.1:8261` の Plaza に自身を登録します

推奨されるテストペイロード:
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Curl の例:
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## オプション 2: Ollama

Ollama がローカルで実行されており、設定されたモデルが利用可能であることを確認してください：
```bash
ollama serve
ollama pull qwen3:8b
```

次に pulser を起動します：
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

期待される結果:

- pulser は `http://127.0.0.1:8263` で起動します
- `http://127.0.0.1:8261` の Plaza に自身を登録します

推奨される curl 例:
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## ブラウザで試す

以下のいずれかを開いてください：

- OpenAI 用: `http://127.0.0.1:8262/`
- Ollama 用: `http://127.0.0.1:8263/`

UI では以下の操作が可能です：

- pulser 設定の確認
- `llm_chat` の実行
- モデルリストの読み込み
- ローカルプロバイダー使用時の Ollama モデル情報の確認

## 注意すべき点

- 同じ pulse コントラクトをクラウドまたはローカルの推論上で実行できます
- OpenAI と Ollama の切り替えは、主に設定の問題であり、インターフェースの再設計ではありません
- これは、リポジトリ内の pulser を使用した LLM ツールを説明するための最もシンプルなデモです

## 独自のものを構築する

デモをカスタマイズするには：

1. `openai.pulser` または `ollama.pulser` をコピーします
2. `model`、`base_url`、ポート、およびストレージパスを変更する
3. 他のツールや UI がこれに依存している場合は、`llm_chat` pulse を安定させてください
