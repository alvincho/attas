# Pulser 演示集

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

## 从这里开始

如果您是第一次学习 pulser 模型，请按此顺序使用：

1. [`file-storage`](./file-storage/README.md)：最安全的仅限本地的 pulser 演示
2. [`analyst-insights`](./analyst-insights/README.md)：由分析师拥有并以可重复使用的洞察视图形式公开的 pulser
3. [`finance-briefings`](./finance-briefings/README.md)：以 MapPhemar 和 Personal Agent 可以执行的形式发布的金融工作流 pulses
4. [`yfinance`](./yfinance/README.md)：具有时间序列输出的实时市场数据 pulser
5. [`llm`](./llm/README.md)：本地 Oll:ma 和云端 OpenAI 对话 pulser
6. [`ads`](./ads/README.md)：作为 SQLite 流水线演示一部分的 ADS pulser

## 单指令启动器

每个可运行的 pulser demo 文件夹现在都包含一个 `run-demo.sh` 封装脚本，它可以从单个终端启动所需的本地服务，打开带有语言选择的浏览器指南页面，并自动打开主要的 demo UI 页面。

如果您希望封装脚本保持在终端中而不打开浏览器标签页，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

在仓库根目录下，先创建虚拟环境，安装依赖项，然后运行任何 pulser 封装脚本，例如 `./demos/

pulsers/file-storage/run-demo.sh`：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中从仓库根目录执行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

如果浏览器标签页没有自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

## 此演示集涵盖的内容

- pulser 如何在 Plaza 进行注册
- 如何通过浏览器或使用 `curl` 测试Pulse (pulses)
- 如何将 pulser 打包成一个小型自托管服务
- 不同 pulser 系列的行为：存储、分析师洞察、金融、LLM 与数据服务

## 公用设置

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

每个 demo 文件夹都会将本地运行时状态写入 `demos/pulsers/.../storage/` 下。

## Demo 目录

### [`file-storage`](./file-storage/README.md)

- 运行环境：Plaza + `SystemPulser`
- 外部服务：无
- 证明内容：存储桶创建、对象保存/加载，以及仅限本地的 pulser 状态

### [`analyst-insights`](./analyst-insights/README.md)

- 运行环境：Plaza + `PathPulser`
- 外部服务：结构化视图无外部服务，提示驱动的新闻流使用本地 Ollama
- 证明内容：一位分析师如何通过多个可重复使用的 pulses，同时发布固定的研究视图和由 prompt 拥定的 Ollama 输出，然后通过个人代理（personal agent）将其展示给另一位用户

### [`finance-briefings`](./finance-briefings/README.md)

- 运行环境：Plaza + `FinancialBriefingPulser`
- 外部服务：在本地 demo 路径中无外部服务
- 证明内容：Attas 拥有的 pulser 如何将金融工作流步骤发布为 pulse 可寻址的构建块，使得 MapPhemar 图表和 Personal Agent 可以存储、编辑并执行相同的 workflow 图

### [`yfinance`](./yfinance/README.md)

- 运行环境：Plaza + `YFinancePulser`
- 外部服务：连接至 Yahoo Finance 的外部网络
- 证明内容：快照 pulses、OHLC 系列 pulses 以及适合图表的输出负载

### [`llm`](./llm/README.md)

- 运行环境：配置为 OpenAI 或 Ollama 的 Plaza + `OpenAIPulser`
- 外部服务：云端模式使用 OpenAI API，本地模式使用本地 Ollama daemon
- 证明内容：`llm_chat`、共享的 pulser 编辑器 UI，以及可切换供应商的 LLM 管道

### [`ads`](./ads/README.md)

- 运行环境：ADS dispatcher + worker + pulser + boss UI
- 外部服务：在 SQLite demo 路径中无外部服务
- 证明内容：基于规范化数据表的 `ADSPulser`，以及您自己的收集器如何流入这些 pulses
