# Attas Data Services

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

## 覆盖范围

目前的规范化数据集表格包括：

- `ads_security_master`
- `xsd_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

Dispatcher 同时也管理：

- `ads_jobs`
- `ads_worker_capabilities`

实作上使用了 `ads_` 表前缀，而非字面上的 `ads-*` 名称，因此相同的标识符可以在 SQLite、Postgres 和以 Supabase 为后端的 SQL 中顺畅地运行。

## 运行时形状

Dispatcher:

- 是一个 `prompits` agent
- 拥有共享队列与归一化存储表
- 提供 `ads-submit-job`、`arg-get-job`、`ads-register-worker` 以及 `ads-post-job-result`
- 当 worker 认领工作时，向其交付具有类型的 `JobDetail` 负载
- 接收具有类型的 `JobResult` 负载，以完成工作并持久化收集到的行及原始负载

Worker:

- 是一个 `prompits` agent
- 通过 agent 元数据与 dispatcher 能力表来宣告其功能
- 从配置中加载 `job_capabilities` 并在 Plaza 元数据上注册这些能力名称
- 使用 `JobCap` 对象作为认领工作的默认执行路径
- 可以单次运行或在轮询循环中运行，默认间隔为 10 秒
- 接受覆盖的 `process_job()` 或外部处理程序回调

Pulser:

- 是一个 `phemacast` pulser
- 从共享池中读取归一化后的 ADS 表
- 提供用于 security master、每日价格、基本面、财务报表、新闻及原始负载查询的Pulse (pulses)

## 文件

- `ads/agents.py`: 分派器与工作代理
- `ads/jobcap.py`: `JobCap` 抽象与基于可调用对象的权限加载器
- `ads/models.py`: `JobDetail` 与 `JobResult`
- `ads/pulser.py`: ADS pulser 实现
- `ads/boss.py`: boss operator UI 代理
- `ads/practices.py`: 分派器实践
- `ads/schema.py`: 共享数据表结构
- `ads/iex.py`: IEX 日终工作权限
- `ads/twse.py`: 台湾证券交易所日终工作权限
- `ads/rss_news.py`: 多源 RSS 新闻收集权限
- `ads/sec.py`: SEC EDGAR 大量原始数据导入与逐公司映射权限
- `ads/us_listed.py`: Nasdaq Trader 美国上市证券主档权限
- `ads/yfinance.py`: Yahoo Finance 日终工作权限
- `ads/runtime.py`: 归一化辅助工具
- `ads/configs/*.agent`: ADS 配置示例
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## 本地示例

随附的 ADS 配置现在假设使用共享的 PostgreSQL 数据库。在启动代理程序之前，请设置
`POSTGRES_DSN` 或 `DATABASE_URL`。您可以选择设置 `ADS_POSTGRES_SCHEMA` 以使用 `public` 以外的 schema，
并且在需要为托管的 PostgreSQL 使用 SSL 时，通过 `ADS_POSTGRES_SSLMODE` 来覆盖默认的本地友好 `disable`
行为。

启动 dispatcher：
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

启动工作节点：
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

示例 worker 配置包含一个由 `ads.us_listed:USListedSecJobCap` 支持的实时 `US Listed Sec to security master` 功能、`fundamentals`、`financial_statements` 与 `news` 的模拟处理器，并使用名为 `US Filing Bulk` 的 `ads.sec:USFilingBulkJobCap`、名为 `US Filing Mapping` 的 `ads.sec:USFilingMappingJobCap`、名为 `YFinance EOD` 的 `ads.yfinance:YFinanceEODJobCap`、名为 `YFinance US Market EOD` 的 `ads.yfinance:YFinanceUSMarketEODJobCap`，以及用于实时收盘数据收集的 `TWSE Market EOD` (`ads.twse:TWSEMarketEODJobCap`)，以及用于多源新闻收集的 `RSS News` (`ads.rss_news:RSSNewsJobCap`)。`YFinance EOD` 使用已安装的 `yfinance` 模块，不需要单独的 API 密钥。`YFinance US Market EOD` 扫描 `ads_security_master` 中的活跃 `USD` 符号，按 `metadata.yfinance.eod_at` 进行排序，逐个符号更新时间戳，并排队单符号 `YFinance EOD` 任务，以便最旧的名称优先刷新。`TWSE Market EOD` 读取官方 TWSE `MI_INDEX` 每日报价报告，并将完整的全市场报价表存储到规范化的 `ads_daily_price` 行中。当 `ads_daily_price` 为空时，默认会引导一个短期的近期窗口，而不是尝试进行多年的全市场回填；如果您需要 TWSE 历史覆盖，请使用显式的 `start_date`。`USListedSecJobCap` 读取 Nasdaq Trader 符号目录文件 `nasdaqlisted.txt` 和 `otherlisted.txt`，优先使用 Web 托管的 `https://www.nasdaqtrader.com/dynamic/SymDir/` 副本（带有 FTP 回退），过滤掉测试符号，并将当前的美国上市股票范围更新（upsert）到 `ads_security_master` 中。`RSS News` 在一个任务中拉取配置好的 SEC、CFTC 和 BLS 馈送，并将规范化的馈送条目存储在 `ads_news` 中。`US Filing Bulk` 下载每晚的 SEC EDGAR
将 `companyfacts.zip` 和 `submissions.zip` 压缩包中的原始每公司 JSON 行写入 `ads_sec_companyfacts` 和 `ads_sec_submissions` 中，并发送声明的 SEC `User-Agent` 标头。`US Filing Mapping` 从这些原始 SEC 表格中读取一家公司，并在 submissions 元数据中可用 symbol 时，将其映射到 `ads_fundamentals` 以及 `ads_financial_statements`。
启动 pulser：
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

启动 boss UI：
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

Boss UI 现在在页面顶部包含了一个即时的 Plaza 连接条，
一个 `Issue Job` 页面，一个用于浏览已排队、已领取、
已完成和失败的 ADS 作业及其原始负载记录的 `/monitor` 视图，
以及一个用于设置 boss 端调度器默认值和监控刷新
偏好的 `Settings` 页面。

## 注意事项
- 随附的示例配置使用 `PostgresPool`，因此 dispatcher、workers、pulser 和 boss 都指向同一个 ADS 数据库，而不是每个 agent 使用独立的 SQLite 文件。
- `PostgresPool` 会从 `POSTGRES_DSN`、`DATABASE_URL`、`SUPABASE_DB_URL` 或标准 libpq `PG*` 环境变量中解析连接设置。
- 当引入新的 JobCaps 时，`ads/configs/boss.agent`、`args/configs/dispatcher.agent` 和 `ads/configs/worker.agent` 应保持一致；随附的配置包含 `US Listed Sec to security master`、`US Filing Bulk`、`US Filing Mapping`、`YFinance EOD`、`YFinance US Market EOD`、`TWSE Market EOD` 以及 `RSS News`。
- Worker 配置可以通过能力名称和可调用路径（例如 `ads.examples.job_caps:mock_daily_price_cap`）来声明 `ads.job_capabilities` 条目。
- Worker 配置还可以通过 `type` 声明基于类的能力，例如 `ads.iex:IEXEODJobCap`、`ads.rss_news:RSSNewsJobCap`、`ads.sec:USFilingBulkJobCap`、`ads.sec:USFilingMappingJobCap`、`ads.twse:TWSEMarketEODJobCap`、`ads.us_listed:USListedSecJobCap` 或 `ads.yfinance:YFinanceEODJobCap`，这些能力会返回标准化行以及用于 dispatcher 持久化的原始负载。
- Worker 的 `ads.job_capabilities` 条目支持 `disabled: true`，以便在不删除配置条目的情况下暂时禁用已配置的 job cap。
- Worker 配置可以设置 `ads.yfinance_request_cooldown_sec`（默认 `120`），以便在收到 Yahoo 速率限制响应后，让 worker 暂时停止发布与 YFinance 相关的能力。
- `ads/sql/ads_tables.sql` 已包含在内，适用于 Postgres 或 Supabase 部署。
- Dispatcher 和 worker 默认使用共享的本地直接 token，因此即使在配置 Plaza 认证之前，远程 `UsePractice(...)` 调用也能在单机上运行。
- 所有三个组件都符合现有的仓库惯例，因此在配置完成后，它们仍可以参与 Plaza 注册和远程 `UsePractice(...)` 调用。
