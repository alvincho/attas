# 金融简报工作流演示

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

## 此演示展示了什么

- 一个 Attas 拥有的 `FinancialBriefingPulser`，用于公开 workflow-seed pulses 与 finance briefing step pulses
- 一个 workflow-entry context pulse：
  - `prepare_finance_briefing_context`
  - 使用 `workflow_name` 来区分工作流：`morning_desk_briefing`、`watchlist_check` 或 `research_roundup`
- 共享的 finance step pulses：
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_blieifing_payload`
- 下游发布/导出 pulses：
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## 为何存在此功能

MapPhemar 通过调用 pulsers 和 pulses 来运行图表。finance briefing 工作流最初是 `attas` 中的纯 Python 函数，但目前的图表将这些工作流分解为可编辑的步骤节点，因此运行时现在使用 Attas 原生的 pulser，而非通用的 MCP 封装。

运行时界面如下：

- [finance-briefings.pulser](./finance-briefings.pulser): `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser` 的 demo 配置
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): 由 Attas 拥有的 pulser 类，负责承载工作流种子和步骤 pulses
- [briefings.py](../../../attas/workflows/briefings.py): 由 pulser 使用的公开 finance briefing 步骤辅助工具

## 运行时假设

- Plaza 位在 `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` 位在 `http://127.0.0.1:8271`

## 单一命令启动

从仓库根目录：
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

这将从单个终端机启动本地 Plaza 以及金融简报 pulser，打开浏览器指南页面，并自动打开 pulser UI。

如果您希望启动器仅保留在终端机中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

请搭配 Ubuntu 或其他 Linux 发行版使用 WSL2。在 WSL 内的仓库根目录下执行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

如果浏览器标签页无法从 WSL 自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

原生 PowerShell / 命令提示符封装器尚未提交，因此目前支持的 Windows 路径是 WSL2。

## 手动启动

从仓库根目录：
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## 相关图表文件

这些图表位于 `demos/files/diagrams/`：

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

每个图表都遵循相同的可编辑结构：

`Input -> Workflow

Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## 当前的 MapPhemar 匹配度

这些工作流可以在目前的 MapPhemar 模型中运行，无需添加新的节点类型或架构：

- 可执行步骤是常规的 `rectangle` 节点
- 边界使用 `pill`
- 分支功能仍可通过 `branch` 使用
- 产出物的扩散（fan-out）由工作流节点的多条输出边（edges）处理

目前的运行限制：

- `Input` 只能连接到一个下游节点，因此扩散必须发生在第一个可执行工作流节点之后，而不是直接从 `Input` 开始

这些逐步进行的金融工作流不需要新的 MapPhemar 节点类型或架构扩展。常规的可执行节点加上 Attas pulser 界面已足以满足目前的存储、编辑和执行需求。
