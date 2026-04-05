# Phemacast

## 翻译版本

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

1. `CreatorAgent` 创建一个 `Phema`（内容结构 + 绑定）。
2. `PulserAgent` 为每个绑定键获取动态数据。
3. `PhemarAgent` 将脉动数据绑定到 `{{binding.path}}` 模板中。
4. `CastrAgent` 以所选格式为观看者渲染最终输出。

支持的观看格式：
- `json`
- `markdown`
- `text`

## 快速示例
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

## 动态绑定规则

- 模板语法：`{{binding.path}}`
- 根 `binding` 是由 `PulserAgent` 返回的Pulse键 (pulse key)
- 缺失的提供者将以 `{ "status": "missing-provider" }` 返回，以保持 casts 的韧性

## 规划中的 Phemacast 功能

- 更多专注于呈现人类智能、判断与结构化解读的 `Phemar` 代理
- 更多能够以 PDS、PPTX、网页及多媒体等格式，从 `Phema` 产生输出的 `Castr` 代理
- 根据人类反馈、运行效率与成本，进行 AI 生成的 `Pulse` 创建与精炼
- 在 `MapPhemar` 中提供更广泛的图表支持
