# 公开演示指南

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

如果您想先尝试其中一个演示，请按以下顺序使用：

1. [`hello-plaza`](./hello-plaza/README.md)：最轻量级的多代理发现演示。
2. [`pulsers`](./pulsers/README.md)：专注于文件存储、YFinance、LLM 和 ADS pulsers 的演示。
3. [`personal-research-workbench`](./personal-research-workbench/README.md)：最具视觉化的产品导览。
4. [`data-pipeline`](./data-pipeline/README.md)：一个具有 boss UI 和 pulser 的本地 SQLite 支持 ADS 流水线。

## 单指令启动器

每个可运行的 demo 文件夹现在都包含一个 `run-demo.sh` 封装脚本，它可以从单个终端启动所需的服务，打开一个带有语言选择功能的浏览器指南页面，并自动打开主要的 demo UI 页面。

如果您希望封装脚本仅停留在终端而不打开浏览器标签页，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

在仓库根目录下，只需执行一次创建虚拟环境并安装依赖项，接着即可运行任何 demo 封装脚本，例如 `./demos/hello-arg/run-demo.sh`：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中进入仓库根目录后执行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

如果浏览器标签页没有自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

在 macOS 和 Linux 上，已提交的 `run-demo.sh` 封装器仍可作为相同 Python 启动器的便利封装器使用。

## 公用设置

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

您通常会希望开启 2-4 个终端窗口，因为大多数 demo 都会启动一些长时间运行的进程。

这些 demo 文件夹会将其运行状态写入 `demos/.../storage/`。该状态会被 git 忽略，因此大家可以自由地进行实验。

## Demo 目录

### [`hello-plaza`](./hello-plaza/README.md)

- 目标对象：初次开发者
- 运行环境：Plaza + worker + 浏览器端用户代理
- 外部服务：无
- 证明内容：代理注册、发现以及简单的浏览器 UI

### [`pulsers`](./pulsers/README.md)

- 目标对象：想要小型、直接 pulser 示例的开发者
- 运行环境：小型 Plaza + pulser 堆栈，以及一个重用 SQLite pipeline 的 ADS pulser 指南
- 外部服务：文件存储无外部服务，YFinance 与 OpenAI 需要出站网络，Ollama 使用本地 Ollama daemon
- 证明内容：独立的 pulser 打包、测试、特定提供者的 pulse 行为、分析师如何发布自己的结构化或由 prompt 驱动的洞察 pulse，以及从消费者角度看这些 pulse 在个人 agent 中的呈现方式

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- 目标对象：想要更强大的产品演示的人
- 运行环境：React/FastAPI workbench + 本地 Plaza + 本地文件存储 pulser + 可选 YFinance pulser + 可选 technical-analysis pulser + 预置图表存储
- 外部服务：存储流程无外部服务，YFinance 图表流程与实时 OHLC-to-RSI 图表流程需要出站网络
- 证明内容：工作区、布局、Plaza 浏览、图表渲染，以及从更丰富的 UI 进行图表驱动的 pulser 执行

### [`data-pipeline`](./data-pipeline/README.md)

- 目标对象：正在评估编排与归一化数据流的开发者
- 运行环境：ADS dispatcher + worker + pulser + boss UI
- 外部服务：在 demo 设置中无外部服务
- 证明内容：队列作业、worker 执行、归一化存储、通过 pulser 重新暴露，以及接入自定义数据源的路径

## 用于公开托管

这些演示旨在于本地运行成功后，易于进行自我托管。如果您公开发布它们，最安全的默认值是：

- 将托管的 demos 设置为只读，或按计划重置它们
- 在第一个公开版本中，请关闭 API 支持或付费的集成功能
- 指引人员查看 demo 使用的配置文件，以便他们可以直接进行 fork
- 在 live URL 旁边包含来自 demo README 的确切本地命令
