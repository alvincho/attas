# 分析师洞察 Pulser 演示

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

- 一个由分析师拥有的 pulser，包含多个结构化洞察 pulses
- 第二个由分析师拥有的 pulser，其建立在独立的新闻代理与本地 Ollama 代理之上
- 一种将原始来源数据与分析师撰写的 Prompits 及最终面向消费者的输出进行分离的清晰方法
- 一个个人代理导览，从另一个用户的视角展示相同的技术栈
- 分析师或 PM 若要发布自己的观点，需要编辑的确切文件

## 此文件夹中的文件

- `plaza.agent`: 用于分析师 pulser 演示的本地 Plaza
- `analyst-insights.pulper`: 定义公开 pulse 目录的 `PathPulser` 配置
- `analyst_insight_step.py`: 共享转换逻辑以及预设的分析师覆盖数据包
- `news-wire.pulser`: 发布预设 `news_article` 数据包的本地上游新闻代理
- `news_wire_step.py`: 由上游新闻代理返回的预设原始新闻数据包
- `ollama.pulser`: 用于分析师提示词演示的本地 Ollama 驱动 `llm_chat` pulser
- `analyst-news-ollama.pulser`: 组合式分析师 pulser，负责获取新闻、应用分析师专属提示词、调用 Ollama 并将结果归一化为多个 pulses
- `analyst_news_ollama_step.py`: 分析师专属提示词包加上 JSON 归一化逻辑
- `start-plaza.sh`: 启动 Plaza
- `start-pulser.sh`: 启动固定的结构化分析师 pulser
- `start-news-pulser.sh`: 启动上游预设新闻代理
- `start-ollama-pulser.sh`: 启动本地 Ollama pulser
- `start-analyst-news-pulser.sh`: 启动带有提示词的分析师 pulser
- `start-personal-agent.sh`: 启动用于消费者视角演练的个人代理 UI
- `run-demo.sh`: 从一个终端启动演示，并打开浏览器指南及主要 UI 页面

## 单一命令启动

从仓库根目录：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

该封装默认会启动轻量级结构化流程。

若要改为启动进阶的新闻 + Ollama + 个人代理流程：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

针对进阶路径：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

请搭配 Ubuntu 或其他 Linux 发行版使用 WSL2。在 WSL 内的仓库根目录下：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

对于 WSL 内的高阶路径：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

如果浏览器标签页无法从 WSL 自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

原生 PowerShell / Command Prompt 封装器尚未提交，因此目前支持的 Windows 路径是 WSL2。

## 演示 1：结构化分析师观点

这是仅限本地、不使用 LLM 的路径。

从仓库根目录打开两个终端。

### 终端 1：启动 Plaza
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8266`

### 终端 2：启动 pulser
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

预期结果：

- pulser 会在 `http://127.0.0.1:8267` 启动
- 它会向 `http://127.0.0.1:8266` 的 Plaza 进行注册

## 在浏览器中尝试

打开：

- `http://127.0.0.1:8267/`

然后使用 `NVDA` 测试以下 pulses：

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

这四个 pulses 的建议参数：
```json
{
  "symbol": "NVDA"
}
```

您应该会看到：

- `rating_summary` 返回标题判断、目标、置信度及简短摘要
- `thesis_bullets` 以列表形式返回正面论点
- `risk_watch` 返回主要风险以及需要监控的指标
- `scenario_grid` 在单一结构化负载中返回牛市、基准及熊市情境

## 使用 Curl 进行测试

标题评分：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

论文要点：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

风险监控：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## 分析师如何自定义此演示

主要有两个编辑点。

### 1. 更改实际的研究视图

编辑：

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

此文件包含预设的 `ANALYST_COVERAGE` 数据包。您可以在此处更改：

- 覆盖的股票代码
- 分析师姓名
- 评级标签
- 目标价格
- 论点要点
- 关键风险
- 牛市/基准/熊市情景

### 2. 更改公开的 Pulse 目录

编辑：

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

该文件控制：

- 存在哪些 pulses
- 每个 pulse 的名称和描述
- 输入和输出架构
- 标签和地址

如果您想添加新的洞察 pulse，请复制现有的条目之一，并将其指向新的 `insight_view`。

## 为什么此模式非常有用

- 投资组合工具可以仅请求 `rating_summary`
- 报告生成器可以请求 `thesis_bullets`
- 风险仪表板可以请求 ` `risk_watch`
- 估值工具可以请求 `scenario_grid`

这意味着分析师只需发布一个服务，但不同的消费者可以精确地提取他们所需的数据切片。

## 下一步该往哪里走

一旦这个本地 pulser 形状变得合理，接下来的步骤是：

1. 向分析师覆盖数据包中添加更多涵盖的符号
2. 如果您想将自己的观点与 YFinance、ADS 或 LLM 的输出相结合，请在最后的 Python 步骤之前添加来源步骤
3. 通过共享的 Plaza 来公开 pulser，而不仅仅是通过本地的 demo Plaza

## 演示 2：分析师 Prompt Pack + Ollama + 个人代理

这个第二个流程展示了一个更符合现实的分析师设置：

- 一个代理发布原始 `news_article` 数据
- 第二个代理通过 Ollama 暴露 `llm_chat`
- 分析师拥有的 pulser 使用其专属的 prompt pack 将原始新闻转换为多个可重复使用的 pulses
- 个人代理从不同用户的视角来消耗完成的 pulses

### 提示流程的前置条件

请确保 Ollama 正在本地运行且模型已存在：

```bash
ollama serve
ollama pull qwen3:8b
```

然后从仓库根目录打开五个终端。

### 终端 1：启动 Plaza

如果 Demo 1 仍在运行，请继续使用同一个 Plaza。
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8266`

### 终端 2：启动上游新闻代理程序
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

预期结果：

- news pulser 会在 `http://127.0.0.1:8268` 启动
- 它会向 `http://127.0.0.1:8266` 的 Plaza 进行注册

### 终端机 3：启动 Ollama pulser
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

预期结果：

- Ollama pulser 启动于 `http://127.0.0.1:8269`
- 它会在 `http://127.0.0.1:8266` 向 Plaza 进行注册

### 终端机 4：启动 prompted analyst pulser

请在新闻与 Ollama agents 已经运行后再启动此项，因为 pulser 会在启动期间验证其样本链。
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

预期结果：

- 提示的分析师 pulser 启动于 `http://12:0.0.1:8270`
- 它会在 `http://127.0.0.1:8266` 向 Plaza 进行注册

### 终端机 5：启动个人代理
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

预期结果：

- 个人代理程序启动于 `http://127.0.0.1:8061`

### 直接尝试 Prompted Analyst Pulser

打开：

- `http://127.0.0.1:8270/`

然后使用 `NVDA` 测试以下 pulses：

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

建议参数：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

您应该会看到：

- `news_desk_brief` 将上游文章转换为 PM 风格的立场说明与简短笔记
- `news_monitoring_points` 将相同的原始文章转换为观察项目与风险标记
- `news_client_note` 将相同的原始文章转换为更整洁的面向客户的笔记

重点在于分析师在单一文件中控制 Prompits，而下游用户仅会看到稳定的 pulse 界面。

### 从另一个用户的视角使用个人代理

打开：

- `http://127.0.0.1:8061/`

然后按照以下路径操作：

1. 打开 `Settings`。
2. 前往 `Connection` 标签页。
3. 将 Plaza URL 设置为 `http://127.0.0.1:82 66`。
4. 点击 `Refresh Plaza Catalog`。
5. 创建一个 `New Browser Window`。
6. 将浏览器窗口切换至 `edit` 模式。
7. 添加第一个 plain pane 并将其指向 `DemoAnalystNewsWirePulser -> news_article`。
8. 使用 pane params：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. 点击 `Get Data` 以便用户查看原始文章。
10. 新增第二个纯文本窗格，并将其指向 `DemoAnalystPromptedNewsPulser -> news_desk_brief`。
11. 重用相同的参数并点击 `Get Data`。
12. 新增第三个窗格，使用 `news_monitoring_points` 或 `news_client_note`。

您应该会看到：

- 一个窗格显示来自另一个代理程序的原始上游新闻
- 下一个窗格显示分析师处理后的视图
- 第三个窗格显示相同的分析师提示包如何为不同的受众发布不同的界面

这就是关键的消费者故事：另一个用户不需要了解内部的链条。他们只需浏览 Plaza，选择一个 pulse，然后消费完成后的分析输出。

## 分析师如何自定义提示流

在 Demo 2 中有三个主要的编辑点。

### 1. 更改上游新闻封包

编辑：

- `demos/pulsers/analyst-insights/news_wire_step.py`

这是在您更改上游来源代理所发布的种子文章的地方。

### 2. 更改分析师自己的提示

编辑：

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

该文件包含分析师拥有的提示包，包括：

- 提示配置文件名称
- 受众与目标
- 语气与写作风格
- 要求的 JSON 输出合约

这是让相同的原始新闻产生不同研究口吻的最快方法。

### 3. 更改公开的 Pulse 目录

编辑：

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

该文件控制：

- 存在哪些提示的 pulses
- 每个 pulse 使用哪个提示配置文件
- 它调用了哪些上游代理
- 向下游用户展示的输入与输出架构

## 为什么此进阶模式非常有用

- 上游新闻代理后续可以替换为 YFinance、ADS 或内部收集器
- 分析师保有提示词包（prompt pack）的所有拥有权，而不是在 UI 中硬编码一次性的笔记
- 不同的消费者可以使用不同的 pulses，而无需了解背后的完整链条
- 个人代理（personal agent）成为一个干净的消费者界面，而不是逻辑存放的地方
