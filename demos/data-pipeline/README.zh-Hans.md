# 数据流水线

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

- 一个用于数据收集任务的分派队列
- 一个正在轮询匹配能力的 worker
- 存储在本地 SQLite 中的标准化 ADS 表
- 一个用于发布和监控任务的 boss UI
- 一个重新展示已收集数据的 pulser
- 一条将内置的 live collectors 替换为您自己的源适配器的路径

## 为什么此 Demo 在即时收集器中使用 SQLite

`ads/configs/` 中的生产级 ADS 配置旨在用于共享的 PostgreSQL 部署。

此 Demo 保留了即时收集器，但简化了存储端：

- SQLite 让设置保持在本地且简单
- worker 和 dispatcher 共用一个本地 ADS 数据库文件，这使得即时 SEC 批量阶段与 pulser 读取的同一个 demo 存储保持兼容
- 架构依然清晰可见，因此开发者稍后可以迁移到生产级配置
- 部分作业会调用公开网络来源，因此首次运行的耗时取决于网络条件和来源的响应速度

## 此文件夹中的文件

- `dispatcher.agent`: 以 SQLite 为后端的 ADS dispatcher 配置
- `worker.agent`: 以 SQLite 为后端的 ADS worker 配置
- `pulser.agent`: 读取 demo 数据存储的 ADS pulser
- `boss.agent`: 用于发布任务的 boss UI 配置
- `start-dispatcher.sh`: 启动 dispatcher
- `start-worker.sh`: 启动 worker
- `start-pulser.sh`: 启动 pulser
- `start-boss.sh`: 启动 boss UI

相关的示例源适配器 (source adapters) 与 live-demo 辅助工具位于：

- `ads/examples/custom_sources.py`: 可导入的示例任务容量 (job caps)，用于用户定义的新闻和价格馈送
- `ads/examples/live_data_pipeline.py`: 针对 live SEC ADS pipeline 的 demo 导向封装器

所有运行时状态均写入 `demos/data-pipeline/storage/`。

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
./demos/data-pipeline/run-demo.sh
```

这将从单个终端启动 dispatcher、worker、pulser 和 boss UI，打开浏览器指南页面，并自动打开 boss UI 和 pulser UI。

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中进入仓库根目录后执行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher data-pipeline
```

如果浏览器标签页没有自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

## 快速入门

从仓库根目录打开四个终端。

### 终端 1：启动 dispatcher
```bash
./demos/data-pipeline/start-dispatcher.sh
```

预期结果：

- dispatcher 启动于 `http://127.0.0.1:9060`

### 终端 2：启动 worker
```bash
./demos/data-pipeline/start-worker.sh
```

预期结果：

- worker 启动于 `127.0.0.1:9061`
- 它每两秒轮询一次 dispatcher

### 终端 3：启动 pulser
```bash
./demos/data-pipeline/start-pulser.sh
```

预期结果：

- ADS pulser 启动于 `http://127.0.0.1:9062`

### 终端 4：启动 boss UI
```bash
./demos/data-pipeline/start-boss.sh
```

预期结果：

- boss UI 启动于 `http://127.0.0.1:9063`

## 首次运行指南

开启：

- `http://127.0.0.1:9063/`

在 boss UI 中，按顺序提交以下作业：

1. `security_master`
   此作业会从 Nasdaq Trader 重新刷新完整的美国上市股票范围，因此不需要 symbol 负载。
2. `daily_price`
   使用 `AAPL` 的默认负载。
3. `fundamentals`
   使用 `AAPL` 的默认负载。
4. `financial_statements`
   使用 `AAPL` 的默认负载。
5. `news`
   使用默认的 SEC、CFTC 和 BLS RSS feed 列表。

出现时，请使用默认的负载模板。`security_master`、`daily_price` 和 `news` 通常会很快完成。第一个由 SEC 支持的 `fundamentals` 或 `financial_statements` 运行可能需要较长时间，因为它在映射请求的公司之前，会先刷新 `demos/data-pipeline/storage/sec_edgar/` 下的 SEC 缓存存档。

然后开启：

- `http://127.0.0.1:9062/`

这是针对相同 demo 数据存储的 ADS pulser。它将标准化后的 ADS 表格作为 pulses 暴露出来，这是从收集/编排到下游消费之间的桥梁。

建议的首次 pulser 检查：

1. 运行 `security_master_lookup` 并使用 `{"symbol":"AAPL","limit":1}`
2. 运行 `daily_price_history` 并使用 `{"symbol":"AAPL","limit":5}`
3. 运行 `company_profile` 并使用 `{"symbol":"AAPL"}`
4. 运行 `financial_statements` 并使用 `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. 运行 `news_article` 并使用 `{"number_of_articles":3}`

这让用户了解整个 ADS 循环：boss UI 发出作业，worker 收集行，SQLite 存储标准化数据，而 `ADSPulser` 通过可查询的 pulses 呈现结果。

## 为 ADSPulser 新增您自己的数据源

重要的心理模型是：

- 您的数据源作为 `job_capability` 接入 worker
- worker 将规范化后的行写入 ADS 表中
- `ADSPulser` 读取这些表并通过 pulses 进行公开

如果您的数据源符合现有的 ADS 表结构之一，您通常完全不需要更改 `ADSPulser`。

### 最简单的路径：写入现有的 ADS 表

使用以下表与 pulse 的配对之一：

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### 示例：添加自定义新闻稿馈送

该仓库现在包含一个可调用的示例于此：

- `ads/examples/custom_sources.py`

若要将其连接到 demo worker，请在 `demos/data-pipeline/worker.agent` 中添加一个能力名称（capability name）和一个由可调用对象支持的 job cap。

添加此能力名称：
```json
"press_release_feed"
```

新增此 job-capability 項目：
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

然后重新启动 worker，并从 boss UI 提交一个包含如下 payload 的任务：
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

该工作完成后，请打开 `http://127.0.0.1:9062/` 上的 Pulser UI 并运行：
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

针对 `news_article` pulse。

您应该会看到：

- 用户定义的收集器将归一化后的行写入 `ads_news`
- 原始输入仍保留在作业的原始负载（raw payload）中
- `ADSPulser` 通过现有的 `news_article` pulse 返回新文章

### 第二个示例：添加自定义价格馈送

如果您的数据源与价格的关联性比新闻更紧密，同样的模式也适用于：
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

该示例将数据行写入 `ads_daily_price`，这意味着结果可以立即通过 `daily_price_history` 进行查询。

### 何时您应该修改 ADSPulser 本身

仅当您的数据源无法清晰地映射到现有的 ADS 规范化表中，或者您需要一种全新的Pulse形状（pulse shape）时，才修改 `ads/pulser.py`。

在这种情况下，通常的流程是：

1. 为新的规范化行添加或选择一个存储表
2. 在 pulser 配置中添加一个新的支持的Pulse条目
3. 扩展 `ADSPulser.fetch_pulse_payload()`，使Pulse知道如何读取并塑形存储的行

如果您仍在设计 Schema，请先从存储原始 Payload 开始，并首先通过 `raw_collection_payload` 进行检查。这样可以在您决定最终规范化表的结构时，保持数据源集成的进度。

## 在 Demo 展示中应重点说明之处

- 任务以异步方式进行排队与完成。
- Worker 与 Boss UI 是解耦的。
- 存储的数据行会进入规范化的 ADS 表格，而非单一的通用 Blob 存储空间。
- Pulser 是建立在收集到的数据之上的第二层接口。
- 引入新数据源通常只需增加一个 Worker 任务上限，而不需要重建整个 ADS 堆栈。

## 构建您自己的实例

从此演示中有两条自然的升级路径。

### 保留本地架构但更换您自己的收集器

编辑 `worker.agent` 并将随附的 live demo job caps 替换为您自己的 job caps 或其他 ADS job-cap 类型。

例如：

- `ads.examples.custom_sources:demo_press_release_cap` 展示了如何将自定义文章馈送导入 `ads_news`
- `ads.essentials.custom_sources:demo_alt_price_cap` 展示了如何将自定义价格来源导入 `ads_daily_price`
- `ads/configs/worker.agent` 中的生产环境配置展示了 SEC、YFinance、TWSE 和 RSS 的 live 功能是如何连接的

### 从 SQLite 迁移到共享 PostgreSQL

一旦本地演示证明了工作流程的可行性，请将此演示配置与以下路径中的生产风格配置进行比较：

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

主要的区别在于连接池（pool）的定义：

- 此演示使用 `SQLitePool`
- 生产风格的配置使用 `PostgresPool`

## 疑难排解

### 任务保持在队列中

请检查这三件事：

- 分派器终端仍在运行
- 工作人员终端仍在运行
- Boss UI 中的工作能力名称与 Worker 广告的名称相符

### Boss UI 已加载但看起来是空的

请确保 boss 配置仍指向：

- `dispatcher_address = http://127.0.0.1:9060`

### 您想要进行一次干净的运行，或者需要移除旧的模拟数据行

在重新开始之前，请停止 demo 程序并移除 `demos/data-pipeline/storage/`。

## 停止 Demo

在每个终端窗口中按下 `Ctrl-C`。
