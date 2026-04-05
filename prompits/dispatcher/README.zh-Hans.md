# Prompits Dispatcher

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

## 包含的组件

- `DispatcherAgent`: 以队列为后端的任务调度器
- `DispatcherWorkerAgent`: 轮询匹配任务并汇报结果的工作器
- `DispatcherBossAgent`: 用于发布任务和检查运行时状态的浏览器 UI
- `JobCap`: 用于可插插件任务处理器的能力抽象
- 共享实践、架构、运行时助手和示例配置

## 内部数据表

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

如果 worker 为特定的 `target_table` 返回了行并提供了 schema，则 dispatcher 也可以创建并持久化该表。如果没有提供 schema，行将以通用方式存储在 `dispatcher_job_results` 中。

## 实践方法

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## 使用示例

启动 dispatcher：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

启动工作节点：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

启动 boss UI：
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

示例 worker 配置使用了来自以下内容的最小示例功能
`prompits.dispatcher.examples.job_caps`.

## 注意事项

- 套件默认使用共享的本地直接令牌，因此在配置 Plaza 认证之前，`UsePractice(...)` 调用可以在本地运行。
- 示例配置使用了 `PostlagPool`，但测试也涵盖了 SQLite。
- Worker 可以通过 `dispatcher.job_capabilities` 配置区块来宣告可调用或基于类的能力。
