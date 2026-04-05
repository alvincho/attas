# 个人研究工作台

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

- 在本地运行的个人工作台 UI
- 工作台可以浏览的 Plaza
- 包含真实可执行Pulse（pulses）的本地与实时数据 pulsers
- 一个以图表为导向的 `Test Run` 流程，可将市场数据转换为计算后的指标序列
- 从精美的演示转向自托管实例的路径

## 此文件夹中的文件

- `plaza.agent`: 仅用于此演示的本地 Plaza
- `file-storage.pulser`: 以文件系统为后端的本地 pulser
- `yfinance.pulser`: 可选的市场数据 pulser，由 `yfinance` Python 模块提供支持
- `technical-analysis.pulser`: 可选的路径 pulser，可从 OHLC 数据计算 RSI
- `map_phemar.phemar`: 嵌入式图表编辑器使用的演示本地 MapPhemar 配置
- `map_phemar_pool/`: 包含预设 OHLC-to-RSI 映射图的图表存储空间
- `start-plaza.sh`: 启动演示 Plaza
- `import-file-storage-pulser.sh`: 启动 pulser
- `start-yfinance-pulser.sh`: 启动 YFinance pulser
- `start-technical-analysis-pulser.sh`: 启动技术分析 pulser
- `start-workbench.sh`: 启动 React/FastAPI 工作台

所有运行时状态均写入 `demos/personal-research-workbench/storage/`。启动器还会将嵌入式图表编辑器指向此文件夹中预设的 `map_phemar.phemar` 和 `map_phemar_pool/` 文件。

## 前置条件

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 单一命令启动

从仓库根目录：
```bash
./demos/personal-research-workbench/run-demo.sh
```

这将从一个终端启动 workbench 堆栈，打开浏览器指南页面，然后同时打开主 workbench UI 以及核心导览中使用的嵌入式 `MapPhemar` 路由。

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

请搭配 Ubuntu 或其他 Linux 发行版使用 WSL2。在 WSL 内的仓库根目录下：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

如果浏览器标签页无法从 WSL 自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

原生 PowerShell / 命令提示符封装器尚未提交，因此目前支持的 Windows 路径是 WSL2。

## 快速入门

如果您想要完整的演示（包括 YFinance 图表流程和图表测试运行流程），请从仓库根目录开启五个终端机。

### 终端机 1：启动本地 Plaza

```bash
./demos/personal-research-workbench/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8241`

### 终端机 2：启动本地文件存储 pulser
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

预期结果：

- pulser 会在 `http://127.0.0.1:8242` 启动
- 它会向 Terminal 1 的 Plaza 进行注册

### Terminal 3：启动 YFinance pulser
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

预期结果：

- pulser 会在 `http://127.0.0.1:8243` 启动
- 它会向 Terminal 1 的 Plaza 进行注册

注意：

- 此步骤需要外部网络访问权限，因为 pulser 会通过 `yfinance` 模块从 Yahoo Finance 获取实时数据
- Yahoo 可能会偶尔对请求进行速率限制，因此此流程最好被视为实时演示，而非严格的固定流程

### Terminal 4：启动技术分析 pulser
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

预期结果：

- pulser 在 `http://127.0.0.1:8244` 启动
- 它会向 Terminal 1 的 Plaza 进行注册

此 pulser 会从传入的 `ohlc_series` 计算 `rsi`；或者当您仅提供 symbol、interval 和 date range 时，从 demo YFinance pulser 获取 OHLC bars。

### Terminal 5：启动工作台
```bash
./demos/personal-research-workbench/start-workbench.sh
```

预期结果：

- 工作台启动于 `http://127.0.0.1:8041`

## 首次运行指南

此演示现在包含三个工作台流程：

1. 使用 file-storage pulser 的本地存储流程
2. 使用 YFinance pulser 的实时市场数据流程
3. 使用 YFinance 和 technical-analysis pulsers 的图表测试运行流程

打开：

- `http://127.0.0.1:8041/`
- `inttp://127.0.0.1:8041/map-phemar/`

### 流程 1：浏览并保存本地数据

然后按照以下简短路径操作：

1. 在工作台中打开设置流程。
2. 前往 `Connection` 区域。
3. 将默认的 Plaza URL 设置为 `http://127.0.0.1:8241`。
4. 刷新 Plaza 目录。
5. 在工作台中打开或创建一个浏览器窗口。
6. 选择已注册的 file-storage pulser。
7. 运行其中一个内置的 pulse，例如 `list_bucket`、`bucket_create` 或 `bucket_browse`。

建议的首次交互：

- 创建一个名为 `demo-assets` 的公共 bucket
- 浏览该 bucket
- 保存一个小的文本对象
- 再次将其加载回来

这为用户提供了一个完整的闭环：丰富的 UI、Plaza 发现、pulser 执行以及持久化的本地状态。

### 流程 2：查看数据并从 YFinance pulser 绘制图表

使用同一个工作台会话，然后：

1. 再次刷新 Plaza 目录，使 YFinance pulser 出现。
2. 添加一个新的浏览器窗格或重新配置现有的数据窗格。
3. 选择 `ohlc_bar_series` pulse。
4. 如果工作台没有自动选择，请选择 `DemoYFinancePulser` pulser。
5. 打开 `Pane Params JSON` 并使用如下 payload：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. 点击 `Get Data`。
7. 在 `Display Fields` 中，开启 `ohlc_series`。如果已经选中了其他字段，请将其关闭，以便预览直接指向时间序列本身。
8. 将 `Format` 更改为 `chart`。
9. 将 `Chart Style` 设置为 `candle`（用于 OHLC 蜡烛图）或 `line`（用于简单的趋势图）。

您应该会看到：

- 面板为所请求的代号和日期范围获取 K 线数据
- 预览从结构化数据变为图表
- 更改代号或日期范围可以在不离开工作台的情况下获得新图表

建议的变体：

- 将 `AAPL` 切换为 `MSCA` 或 `NVDA`
- 缩短日期范围以获得更紧凑的近期视图
- 使用相同的 `ohlc_bar_series` 响应来比较 `line` 和 `candle`

### 流程 3：加载图表并使用 Test Run 计算 RSI 序列

打开图表编辑器路由：

- `http://127.0.0.1:8041/map-phemar/`

然后按照此路径操作：

1. 确认图表编辑器中的 Plaza URL 为 `http://127.0.0.1:8241`。
2. 点击 `Load Phema`。
3. 选择 `OHLC To RSI Diagram`。
4. 检查预设的图表。它应该显示 `Input -> OHLC Bars -> RSI 14 -> Output`。
5. 点击 `Test Run`。
6. 使用此输入负载：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. 执行地图并展开步骤输出。

你应该会看到：

- `OHLC Bars` 步骤调用了 demo YFinance pulser 并返回 `ohlc_series`
- `RSI 14` 步骤将这些 bars 传递给 technical-analysis pulser，并带有 `window: 14`
- 最终的 `Output` 负载包含一个计算后的 `values` 数组，其中含有 `timestamp` 与 `value` 条目

如果你想从头开始重新构建相同的图表，而不是加载种子：

1. 添加一个名为 `OHLC Bars` 的圆角节点。
2. 将其绑定到 `DemoYFinancePulser` 与 `ohlc_bar_series` pulse。
3. 添加一个名为 `RSI 14` 的圆角节点。
4. 将其绑定到 `DemoTechnicalAnalysisPulser` 与 `rsi` pulse。
5. 将 RSI 节点参数设置为：
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. 连接 `Input -> OHLC Bars -> RSI 14 -> Output`。
7. 将边缘映射保留为 `{}`，以便匹配的字段名称自动流转。

## 在 Demo 展示中应重点介绍的内容

- 即使在添加任何实时连接之前，工作台仍会加载有用的模拟仪表板数据。
- Plaza 集成是可选的，并且可以指向本地或远程环境。
- 文件存储 pulser 仅限本地使用，这使得公开演示既安全又可重现。
- YFinance pulser 增加了第二个故事：同一个工作台可以浏览实时市场数据并将其渲染为图表。
- 图表编辑器增加了第三个故事：同一个后端可以编排多步骤流程，并通过 `Test Run` 展示每个步骤。

## 构建您自己的实例

有三种常见的自定义路径：

### 修改预设的仪表板与工作区数据

工作台从以下位置读取其仪表板快照：

- `attas/personal_arg/data.py`

这是替换您自己的自定义观察列表、指标或工作区默认值最快的地方。

### 修改视觉外壳

当前的实时工作台运行时由以下文件提供：

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

如果您想重新设计 Demo 的主题或为您的受众简化 UI，请从这里开始。

### 修改连接的 Plaza 与 pulsers

如果您需要不同的后端：

1. 复制 `plaza.agent`、`file-storage.pulser`、`yfinance.pulser` 和 `technical-analysis.pulser`
2. 重命名服务
3. 更新端口与存储路径
4. 修改 `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` 中的预设图表，或直接从工作台中创建您自己的图表
5. 准备就绪后，将 Demo 的 pulsers 替换为您自己的 agents

## 可选工作台设置

启动器脚本支持一些实用的环境变量：
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

在開發期间主动编辑 FastAPI 应用程式时，请使用 `PHEMACAST_PERSONAL_AGENT_RELOAD=1`。

## 疑难排解

### 工作台已加载，但 Plaza 结果为空

请检查以下三点：

- `http://127.0.0.1:8241/health` 可正常访问
- 当您需要这些流程时，file-storage、YFinance 和 technical-analysis pulser 终端仍在运行
- 工作台的 `Connection` 设置指向 `http://127.0.0.1:8241`

### pulser 尚未显示任何对象

这在首次启动时是正常的。Demo 存储后端初始状态为空。

### YFinance 面板未绘制图表

请检查以下事项：

- YFinance pulser 终端正在运行
- 所选的 pulse 为 `ohlca_bar_series`
- `Display Fields` 包含 `ohlc_series`
- `Format` 设置为 `chart`
- `Chart Style` 为 `line` 或 `candle`

如果请求本身失败，请尝试另一个代码，或在短暂等待后重新运行，因为 Yahoo 可能会间歇性地进行速率限制或拒绝请求。

### 图表 `Test Run` 失败

请检查以下事项：

- `http://127.0.0.1:8241/health` 可正常访问
- YFinance pulser 正在 `http://127.0.0.1:8243` 上运行
- technical-analysis pulser 正在 `http://127.0.0.1:8244` 上运行
- 已加载的图表为 `OHLC To RSI Diagram`
- 输入负载包含 `symbol`、`interval`、`start_date` 和 `end_date`

如果 `OHLC Bars` 步骤首先失败，问题通常是实时 Yahoo 访问或速率限制。如果 `RSI 14` 步骤失败，最常见的原因是 technical-analysis pulser 未运行，或者上游 OHLC 响应未包含 `ohlc_series`。

### 您想要重置 Demo

最安全的重置方法是将 `root_path` 值指向新的文件夹名称，或者在没有任何 demo 进程运行时删除 `demos/personal-research-workbench/storage/` 文件夹。

## 停止演示

在每个终端窗口中按下 `Ctrl-C`。
