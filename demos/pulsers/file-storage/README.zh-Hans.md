# System Pulser 演示

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

- `plaza.agent`: 此 pulser 演示的本地 Plaza
- `file-storage.pulser`: 以本地文件系统为后端的存储 pulser
- `start-plaza.sh`: 启动 Plaza
- `start-pulser.sh`: 启动 pulser
- `run-demo.sh`: 从一个终端启动完整演示，并打开浏览器指南以及 pulser UI

## 单一命令启动

从仓库根目录：
```bash
./demos/pulsers/file-storage/run-demo.sh
```

这会从单个终端启动 Plaza 和 `SystemPulser`，打开浏览器指南页面，并自动打开 pulser UI。

如果您希望启动器仅保留在终端中，请设置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入门

### macOS 与 Linux

从仓库根目录：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

请使用原生 Windows Python 环境。在 PowerShell 中从仓库根目录执行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

如果浏览器标签页没有自动打开，请保持启动器正在运行，并在 Windows 浏览器中打开打印出的 `guide=` URL。

## 快速入门

从仓库根目录打开两个终端。

### 终端 1：启动 Plaza
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

预期结果：

- Plaza 启动于 `http://127.0.0.1:8256`

### 终端 2：启动 pulser
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

预期结果：

- pulser 在 `http://127.0.0.1:8257` 启动
- 它向 `http://127.0.0.1:8256` 的 Plaza 进行注册

## 在浏览器中尝试

打开：

- `http://127.0.0.1:8257/`

然后按顺序测试以下 pulses：

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

`bucket_create` 的建议参数：
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

`object_save` 的建议参数：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

建议用于 `object_load` 的参数：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## 使用 Curl 进行测试

创建一个存储桶：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

保存对象：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

重新载入：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## 重点说明

- 此 pulser 完全在本地运行，不需要云端凭证
- 负载内容（payloads）非常简单，无需额外工具即可理解
- 存储后端稍后可以从文件系统切换到其他供应商，同时保持 pulse 接口稳定

## 自行构建

如果您想要进行自定义：

1. 复制 `file-storage.pulser`
2. 修改端口与存储的 `root_path`
3. 如果您希望与 workbench 及现有示例保持兼容性，请保持相同的 pulse surface
