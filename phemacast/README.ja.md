# Phemacast

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

## エージェントフロー

1. `CreatorAgent` が `Phema`（コンテンツ構造 + バインディング）を作成します。
2. `PulserAgent` が各バインディングキーに対して動的データを取得します。
3. `PhemarAgent` がPulseデータを `{{binding.path}}` テンプレートにバインドします。
4. `CastrAgent` が選択された形式で視聴者向けの最終出力をレンダリングします。

サポートされているビューアー形式：
- `json`
- `markdown`
- `text`

## クイック例
```python
from phemacast import PhemacastSystem, Persona

system = PhemacastSystem()

system.register_pulse_source("summary", lambda ctx: {"value": f"Market pulse for {ctx['symbol']}"})
system.register_pulse_source("price", lambda ctx: {"value": 63890.42})

phema = system.create_phema(
    title="BTC Brief",
    prompt="Creator view",
    bindings=["price"],
    default_persona=Persona(name="analyst", tone="professional", style="short"),
)

output, trace = system.cast(
    phema_id=phema.phema_id,
    viewer_format="markdown",
    context={"symbol": "BTC"},
)

print(output)
```

## 動的バインディングルール

- テンプレート構文: `{{binding.path}}`
- ルート `binding` は `PulserAgent` によって返されるPulseキーです
- プロバイダーが見つからない場合は、casts の回復力を維持するために `{ "status": "missing-provider" }` として返されます

## Phemacast の計画されている機能

- 人間の知能、判断、および構造化された解釈の表現に焦点を当てた、より多くの `Phemar` エージェント
- PDS、PPTX、ウェブページ、マルチメディアなどの形式で `Phema` から出力を生成できる、より多くの `Castr` エージェント
- 人間のフィードバック、実行効率、およびコストに基づいた、AI 生成による `Pulse` の作成と洗練
- `MapPhemar` におけるより広範な図解サポート
