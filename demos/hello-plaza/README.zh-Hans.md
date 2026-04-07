# Hello Plaza

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

- 在本地运行的 Plaza 注册表
- 自动向 Plaza 注册的代理程序
- 连接到该 Plaza 的浏览器端用户界面
- 开发者可以复制到自己项目中的最小化配置集

## 此文件夹中的文件

- `plaza.agent`: Plaza 配置示例
- `worker.agent`: worker 配置示例
- `user.agent`: 用户代理配置示例
- `start-plaza.sh`: 启动 Plaza
- `start-worker.sh`: 启动 worker
- `start-user.sh`: 启动浏览器端用户代理

所有运行时状态均写入 `demos/hello-plaza/storage/`。

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
./demos/hello-plaza/run-demo.sh
```

这将从单个终端启动 Plaza、工作器（worker）和用户 UI，打开浏览器指南页面，并自动打开用户 UI。

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中从仓库根目录执行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

如果浏览器标签页没有自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

## 快速入门

从仓库根目录打开三个终端。

### 终端 1：启动 Plaza
```bash
./demos/hello-plaza/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` 返回健康状态

### 终端 2：启动 worker
```bash
./demos/hello-plaza/start-worker.sh
```

预期结果：

- worker 启动于 `127.0.0.1:8212`
- 它会自动向终端 1 中的 Plaza 注册

### 终端 3：启动用户 UI

```bash
./demos/hello-plaza/start-user.sh
```

预期结果：

- 浏览器端用户代理启动于 `http://127.0.0.1:8214/`

## 验证堆栈

在第四个终端中，或在服务启动后：
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

您应该会看到：

- 第一个命令返回了健康的 Plaza 响应
- 第二个命令显示了本地的 Plaza 以及已注册的 `demo-worker`

接着打开：

- `http://127.0.0.1:8214/`

这是用于在本地演示或屏幕录制中分享的公开演示 URL。

## 在 Demo 展示中应重点说明的内容

- Plaza 是探索层。
- Worker 可以独立启动，且仍会显示在共享目录中。
- 面向用户的 UI 不需要对 Worker 有硬编码的认知。它通过 Plaza 进行探索。

## 建立您自己的实例

将此转换为您自己的实例最简单的方法是：

1. 将 `plaza.agent`、`worker.agent` 和 `user.agent` 复制到一个新文件夹中。
2. 重命名这些 agents。
3. 如果需要，更改端口。
4. 将每个 `root_path` 指向您自己的存储位置。
5. 如果您更改了 Plaza 的 URL 或端口，请更新 `worker.agent` 和 `user.agent` 中的 `plaza_url`。

最需要自定义的三个重要字段是：

- `name`：agent 作为其身份进行广告的名称
- `cap`：HTTP 服务监听的位置
- `root_path`：本地状态存储的位置

当文件配置正确后，请执行：
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## 疑难排解

### 端口已被占用

编辑相关的 `.agent` 文件并选择一个空闲的端口。如果您将 Plaza 移动到新的端口，请更新两个依赖配置中的 `plaza_url`。

### 用户 UI 显示 Plaza 目录为空

请检查以下三点：

- Plaza 正在 `http://127.0.0.1:8211` 上运行
- worker 终端仍在运行中
- `worker.agent` 仍指向 `http://127.0.0.1:8211`

### 您想要一个全新的 Demo 状态

最安全的重置方法是将 `root_path` 的值指向一个新的文件夹名称，而不是直接删除现有数据。

## 停止 Demo

在每个终端窗口中按下 `Ctrl-C`。
