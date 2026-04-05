# Phemacast

## 翻譯版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Agent 流程

1. `CreatorAgent` 建立一個 `Phema`（內容結構 + 綁定）。
2. `PulserAgent` 為每個綁定鍵獲取動態數據。
3. `PhemarAgent` 將脈動數據綁定到 `{{binding.path}}` 模板中。
4. `CastrAgent` 以所選格式為觀看者渲染最終輸出。

支援的觀看格式：
- `json`
- `markdown`
- `text`

## 快速範例
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

## 動態綁定規則

- 模板語法：`{{binding.path}}`
- 根 `binding` 是由 `PulserAgent` 回傳的Pulse鍵 (pulse key)
- 缺失的提供者將以 `{ "status": "missing-provider" }` 回傳，以保持 casts 的韌性

## 規劃中的 Phemacast 功能

- 更多專注於呈現人類智能、判斷與結構化解讀的 `Phemar` 代理
- 更多能夠以 PDS、PPTX、網頁及多媒體等格式，從 `Phema` 產生輸出的 `Castr` 代理
- 根據人類回饋、執行效率與成本，進行 AI 生成的 `Pulse` 建立與精煉
- 在 `MapPhemar` 中提供更廣泛的圖表支援
