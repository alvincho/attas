# ADS Pulser 演示

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

## 此演示涵盖的内容

- `ADSPulser` 如何构建在标准化的 ADS 表格之上
- 调度器 (dispatcher) 与工作器 (worker) 的活动如何转化为 pulser 可见的数据
- 您自己的收集器 (collectors) 如何将数据写入 ADS 表格，并通过现有的 pulses 呈现出来

## 设置

请参阅快速入门指南：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

或者从仓库根目录使用专注于 pulser 的单条命令封装器：
```bash
./demos/pulsers/ads/run-demo.sh
```

该封装启动了与 `data-pipeline` 相同的 SQLite ADS 堆栈，但会打开一个浏览器指南和专注于 pulser-first 逐步操作的标签页。

这会启动：

1. ADS dispatcher
2. ADS worker
3. ADS pulser
4. boss UI

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中进入仓库根目录：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

如果浏览器标签页没有自动打开，请保持启动器运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

## 初步 Pulser 检查

当示例作业完成后，请打开：

- `http://127.0.0.1:9062/`

然后测试：

1. 使用 `{"symbol":"AAPL","limit":1}` 测试 `security_master_lookup`
2. 使用 ` {"symbol":"AAPL","limit":5}` 测试 `daily_price_history`
3. 使用 `{"symbol":"AAPL"}` 测试 `company_profile`
4. 使用 `{"symbol":"AAPL","number_of_articles":3}` 测试 `news_article`

## 为什么 ADS 与众不同

其他的 pulser 示例大多直接从实时供应商或本地存储后端读取。

`ADSPulser` 则是从 ADS 流水线写入的规范化表中读取：

- workers 收集或转换源数据
- dispatcher 持久化规范化行
- `ADSPulser` 将这些行作为可查询的 pulses 进行公开

这使其成为解释如何添加您自己的源适配器的理想示例。

## 新增您自己的来源

具体的逐步教学位于：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

请参考此处的自定义示例：

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

这些示例展示了用户定义的收集器如何写入：

- `ads_news`，通过 `news_article` 提供使用
- `args_daily_price`，通过 `daily_price_history` 提供使用
