# Demo 图表库

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

## 平台说明

此文件夹提供的是 JSON 资产，而非独立的启动器。

### macOS 与 Linux

请先启动其中一个配对的演示程序，然后将这些文件加载到 MapPhemar 或 Personal Agent：
```bash
./demos/personal-research-workbench/run-demo.sh
```

您也可以启动：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

请为配对的 demo 启动器使用原生 Windows Python 环境，例如 `py -3 -m scripts.demo_launcher analyst-insights` 与 `py -3 -m scripts.demo_launcher finance-briefings`。在堆栈运行后，如果标签页没有自动打开，请在 Windows 浏览器中打开打印出的 `guide=` URL。

## 此文件夹包含什么

这里有两组示例：

- 技术分析图表：将 OHLC 市场数据转换为指标序列
- 以 LLM 为导向的分析师图表：将原始市场新闻转换为结构化研究笔记
- 金融工作流图解析：将标准化的研究输入转换为简报、出版物及 NotebookLM 导出包

## 此文件夹中的文件

### 技术分析

- `ohlc-to-sma-20-diagram.json`: `输入 -> OHLC K线 -> SMA 20 -> 输出`
- `ohlc-to-ema-50-diagram.json`: `输入 -> OHLC K线 -> EMA 50 -> 输出`
- `ohlc-to-macd-histogram-diagram.json`: `输入 -> OHLC K线 -> MACD 柱状图 -> 输出`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `输入 -> OHLC K线 -> 布林带宽 -> 输出`
- `ohlc-to-adx-14-diagram.json`: `输入 -> OHLC K线 -> ADX 14 -> 输出`
- `ohlc-to-obv-diagram.json`: `输入 -> OHLC K线 -> OBV -> 输出`

### LLM / 分析师研究

- `analyst-news-desk-brief-diagram.json`: `输入 -> 新闻台简报 -> 输出`
- `analyst-news-monitoring-points-diagram.json`: `输入 -> 监控点 -> 输出`
- `analyst-news-client-note-diagram.json`: `输入 -> 客户笔记 -> 输出`

### 金融工作流包

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `输入 -> 准备早间背景 -> 金融步骤 Pulses -> 组装简报 -> 报告 Phema + NotebookLM 包 -> 输出`
- `finance-watchlist-check-notebooklm-diagram.json`: `输入 -> 准备自选股背景 -> 金融步骤 Pulses -> 组装简报 -> 报告 Phema + NotebookLM 包 -> 输出`
- `finance-research-roundup-notebooklm-diagram.json`: `输入 -> 准备研究背景 -> 金融步骤 Pulses -> 组装简报 -> 报告 Phema + NotebookLM 包 -> 输出`

这三个保存的 Phemas 保持独立以便编辑，但它们共享相同的 workflow-entry pulse，并通过节点 `paramsText.workflow_name` 来区分工作流。

## 运行时假设

这些图表保存了具体的本地地址，因此在预期的 demo stack 可用时，无需额外编辑即可运行。

### 技术分析图表

指标图表假设：

- Plaza 位址为 `http://127.0.0.1:8241`
- `YFinancePulser` 位址为 `http://127.0.0.1:8243`
- `TechnicalAnalysisPulser` 位址为 `http://127.0.0.1:8244`

这些图表所引用的 pulser 配置位于：

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### LLM / 分析师图表

面向 LLM 的图表假设：

- Plaza 位址为 `http://127.0.0 1:8266`
- `DemoAnalystPromptedNewsPulser` 位址为 `http://127.0.0.1:8270`

该 prompted analyst pulser 本身依赖于：

- `news-wire.pulser` 位址为 `http://127.0.0.1:8268`
- `ollama.pulser` 位址为 `http://127.0.0.1:8269`

这些 demo 文件位于：

- `demos/pulsers/analyst-insights/`

### 金融工作流图表

金融工作流图表假设：

- Plaza 位址为 `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` 位址为 `http://127.0.0.1:8271`

该 demo pulser 是一个 Attas 拥有的 `FinancialBriefingPulser`，其后端为：

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

这些图表在 MapPhemar 以及嵌入的 Personal Agent MapPhemar 路由中均可编辑，因为它们是普通的以图表为后端的 Phema JSON 文件。

## 快速入门

### 选项 1：将文件加载到 MapPhemar

1. 打开一个 MapPhemar 编辑器实例。
2. 从此文件夹中加载其中一个 JSON 文件。
3. 确认保存的 `plazaUrl` 和 pulser 地址与您的本地环境相匹配。
4. 使用下方其中一个示例 payload 运行 `Test 运行`。

如果您的服务使用了不同的端口或名称，请编辑：

- `meta.map_phemar.diagram.plazaUrl`
- 每个节点的 `pulserName`
- 每个节点的 `pulserAddress`

### 选项 2：将其作为种子文件使用

您也可以将这些 JSON 文件复制到 `phemas/` 目录下的任何 MapPhemar 池中，并像 personal-research-workbench 演示那样，通过 agent UI 进行加载。

## 示例输入

### 技术分析图表

使用如下负载：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

预期结果：

- `OHLC Bars` 步骤会获取历史 K 线序列
- 指标节点会计算 `values` 数组
- 最终输出会返回时间戳/数值对

### LLM / 分析师图表

使用如下负载：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

预期结果：

- 由 prompt 驱动的 analyst pulser 获取原始新闻
- prompt pack 将该新闻转换为结构化的 analyst 视图
- 输出返回可直接用于研究的字段，例如 `desk_note`、`mandate_now` 或 `client_note`

### 金融工作流图表

使用如下 payload：
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

预期结果：

- 工作流上下文节点种子选定的金融工作流
- 中间金融节点构建来源、引用、事实、风险、催化剂、冲突、要点、问题和摘要区块
- 组装节点构建 `attas.finance_briefing` 负载
- 报告节点将该负载转换为静态 Phema
- NotebookLM 节点从相同的负载生成导出构件
- 最终输出合并所有三个结果，以便在 MapPhemar 或 Personal Agent 中进行检查

## 当前编辑器限制

这些金融工作流在不新增节点类型的情况下，符合目前的 MapPhemar 模型。

仍适用两项重要的运行时规则：

- `Input` 必须恰好连接到一个下游形状
- 每个可执行的非分支节点必须引用一个 pulse 以及一个可达到的 pulser

这意味着工作流的分叉（fan-out）必须发生在第一个可执行节点之后，且如果您希望图表能够端到端地运行，工作流步骤仍需要作为由 pulser 托管的 pulse 来公开。

## 相关演示

如果您想要运行支持服务，而不仅仅是查看图表：

- `demos/personal-research-workbench/README.md`: 包含种子 RSI 示例的可视化图表工作流
- `demos/pulsers/analyst-insights/README.md`: LLM 导向图表所使用的提示分析师新闻堆栈
- `demos/pulsers/llm/README.md`: 用于 OpenAI 和 Ollama 的独立 `llm_chat` pulser 演示

## 验证

这些文件已包含在仓库测试中：
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

该测试套件会验证已保存的图表是否能针对模拟或参考的 pulser 流程进行端到端执行。
