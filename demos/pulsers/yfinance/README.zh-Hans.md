# YFinance Pulser 演示

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

## 此文件夹中的文件

- `plaza.agent`: 此演示使用的本地 Plaza
- `yfinance.pulser`: `YFinancePulser` 的本地演示配置
- `start-plaza.sh`: 启动 Plaza
- `start-pulser.sh`: 启动 pulser
- `run-demo.sh`: 从单个终端启动完整演示，并打开浏览器指南及 pulser UI

## 单一命令启动

从仓库根目录：
```bash
./demos/pulsers/yfinance/run-demo.sh
```

这将从单个终端启动 Plaza 和 `YFinancePulser`，打开浏览器指南页面，并自动打开 pulser UI。

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

请搭配 Ubuntu 或其他 Linux 发行版使用 WSL2。在 WSL 内的仓库根目录下执行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

如果浏览器标签页无法从 WSL 自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

原生 PowerShell / Command Prompt 封装器尚未提交，因此目前支持的 Windows 路径是 WSL2。

## 快速入门

从仓库根目录打开两个终端。

### 终端 1：启动 Plaza
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8251`

### 终端 2：启动 pulser
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

预期结果：

- pulser 启动于 `http://127.0.0.1:8252`
- 它会在 `http://127.0.0.1:8251` 向 Plaza 进行注册

注意：

- 此演示需要外部网络访问权限，因为 pulser 会通过 `yfinance` 获取实时数据
- Yahoo Finance 可能会对请求进行速率限制或间歇性拒绝

## 在浏览器中尝试

打开：

- `http://127.0.0.1:8252/`

建议的首个 pulses：

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

建议用于 `last_price` 的参数：
```json
{
  "symbol": "AAPL"
}
```

建议用于 `ohlc_bar_series` 的参数：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## 使用 Curl 进行测试

报价请求：
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC 序列请求：
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## 重点说明

- 同一个 pulser 同时提供快照式 (snapshot-style) 与时间序列式 (time-series-style) 的 pulses
- `ohlc_bar_series` 与 workbench chart demo 以及 technical-analysis path pulser 兼容
- live provider 之后可以在底层进行变更，而 pulse contract 保持不变

## 打造您自己的版本

如果您想要扩展此示例：

1. 复制 `yfinance.pulser`
2. 调整端口与存储路径
3. 如果您想要更小或更专业的目录，可以更改或新增支持的 pulse 定义
