# Retis 金融智能工作区

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

此仓库是一个用于金融智能系统的多代理工作区。

更多信息请见 [retis.ai](https://retis.ai)，Attas 产品页面请见 [retis.ai/products/attas](https://retis.ai/products/attas)。

此仓库目前结合了数个彼此相关的代码库：

- `prompits`: 用于 HTTP 原生代理、Plaza 发现、数据池与远程 practice 执行的 Python 基础设施
- `phemacast`: 建立在 Prompits 之上的协作内容流水线
- `attas`: 更高层的金融导向代理模式与 Pulse 定义
- `ads`: 将规范化金融数据集输入更广泛系统的数据服务与采集组件

## 状态

此仓库正在积极开发中，且仍在不断演进。随着项目进行拆分、稳定化或更正式的封装，API、配置格式和示例流程可能会发生变化。

有两个领域目前仍处于非常早期的阶段，在积极开发期间很可能会快速变化：

- `prompits.teamwork`
- `phemacast` `BossPulser`

公开仓库旨在用于：

- 本地开发
- 评估
- 原型工作流
- 架构探索

它目前还不是一个完善的开箱即用产品，也不是一个只需单条命令即可进行生产环境部署的产品。

## 全新 Clone 快速入门

从全新的 checkout 开始：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

smoke 脚本会将已提交的 repo 状态复制到一个临时目录，创建自己的 virtualenv，安装依赖项，并运行一个针对面向公众的测试套件。这是最接近 GitHub 用户实际会拉取的状态。

如果您想测试最新的未提交本地更改，请使用：
```bash
attas_smoke --worktree
```

该模式会将当前的作业树复制到临时测试目录中，包括尚未提交的变更以及未追踪且未被忽略的文件。

从仓库根目录，您也可以执行：
```bash
bash attas_smoke
```

在仓库树状结构的任何子目录中，您都可以运行：
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

该启动器会找到仓库根目录并启动相同的冒烟测试流程。如果您将 `attas_smoke` 创建符号链接到 `PATH` 中的某个目录，您也可以在任何地方将其作为可重复使用的命令来调用，并且在仓库树之外工作时，可以选择性地设置 `FINMAS_REPO_ROOT`。

## 本地优先快速入门

目前最安全的本地路径是 Prompits 示例堆栈。它不需要 Supabase 或其他私有基础设施，并且现在针对基准桌面堆栈（baseline desk stack）具备了单条命令的本地引导流程：
```bash
python3 -m prompits.cli up desk
```

这会启动：

- Plaza 位在 `http://127.0.0.1:8211`
- 基线 worker 位在 `http://127.0.0.1:8212`
- 面向浏览器的用户 UI 位在 `http://127.0.0.1:8214/`

您也可以使用封装脚本：
```bash
bash run_plaza_local.sh
```

实用的后续指令：
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

如果您需要使用旧的手动流程来一次调试单个服务：
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

如果您想要使用较旧的以 Supabase 为后端的 Plaza 设置，请将 `PROMPITS_AGENT_CONFIG` 指向
`attas/configs/plaza.agent` 并提供必要的环境变量。

## 远程实践策略与审计

Prompits 现在支持针对远程 `UsePractice(...)` 调用 的轻量化跨代理策略与审计层。该合约存在于代理程序配置 JSON 的顶层，且仅在 `prompits` 内部使用：
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

策略说明：

- `outbound` 规则使用 `practice_id`、`target_agent_id`、`target_name`、`target_address`、`target_role` 和 `target_pit_type` 来匹配目的地。
- `inbound` 规则使用 `practice_id`、`caller_agent_id`、`caller_name`、`caller_address`、`auth_mode` 和 `plaza_url` 来匹配调用者。
- 拒绝规则优先；如果存在允许列表，远程调用必须匹配该列表，否则将被以 `403` 拒绝。
- 审计行会被记录，且当代理（agent）拥有连接池时，会附加到配置的审计表中，并使用共享的 `request 
ID` 以便在请求和结果事件之间进行关联。

## 仓库布局
```text
attas/       Finance-oriented agent, pulse, and personal-agent work
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## 入门指南

- 从 `prompits/README.md` 开始了解核心运行时模型。
- 阅读 `phemacast/README.md` 以了解内容流水线层。
- 阅读 `attas/README.md` 以了解金融网络框架与高阶概念。
- 阅读 `ads/README.md` 以了解数据服务组件。

## 组件状态

| 区域 | 当前公开状态 | 备注 |
| --- | --- | --- |
| `prompits` | 最佳起点 | 以本地优先的示例和核心运行时是最容易的公开切入点。`prompits.teamwork` 包仍处于早期阶段，且可能会快速变动。 |
| `attas` | 早期公开 | 核心概念和用户代理工作已公开，但某些未完成的组件为了避免干扰默认流程而刻意隐藏。 |
| `phemacast` | 早期公开 | 核心流水线代码已公开；部分报告/渲染组件仍在进行精简与稳定化。`BossPulser` 仍在积极开发中。 |
| `ads` | 进阶 | 对于开发和研究非常有用，但某些数据工作流需要额外设置，并非首次运行的路径。 |
| `deploy/` | 仅限示例 | 部署助手与环境相关，不应被视为成熟的公开部署方案。 |
| `mcp_servers/` | 公开源码 | 本地 MCP 服务器实现是公开源码树的一部分。 |

## 已知限制

- 部分工作流程仍假设存在可选的环境变量或第三方服务。
- `tests/storage/` 包含有用的 fixtures，但与理想的公开 fixture 集相比，它仍将确定性的测试数据与更具可变性的本地风格状态混合在一起。
- 部署脚本仅作为示例，并非受支持的生产平台。
- 仓库正在快速演变，因此某些配置和模块边界可能会发生变化。

## 路线图

短期公开路线图记录于 `docs/ROADMAP.md`。

计划中的 `prompits` 功能包括代理人之间经过身份验证与权限控制的 `UsePractice(...)` 调用，并在执行前进行成本协商与支付处理。

计划中的 `phemacast` 功能包括更丰富的人类智能 `Phemar` 表示形式、更广泛的 `Castr` 输出格式，以及根据反馈、效率与成本进行 AI 生成的 `Pulse` 优化，此外还包括 `MapPhemar` 中更广泛的图表支持。

计划中的 `attas` 功能包括更具协作性的投资与司库工作流、针对金融专业人士调优的代理人模型，以及针对供应商与服务提供者的 API 端点到 `Pulse` 的自动映射。

## 公开仓库说明

- 预期机密信息应来自环境变量和本地配置，而非提交的文件。
- 本地数据库、浏览器产物以及暂存快照均刻意排除在版本控制之外。
- 目前的代码库主要针对评估、本地开发和原型工作流程，而非精细的最终用户封装。

## 参与贡献

这目前是一个由单一主要维护者管理的公开仓库。欢迎提出 Issue 和 Pull Request，但目前路线图和合并决策仍由维护者主导。请参阅 `CONTRIBUTING.md` 以了解当前的开发流程。

## 授权条款

本仓库采用 Apache License 2.0 授权。完整文本请参阅 `LICENSE`。
