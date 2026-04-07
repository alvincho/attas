# System Pulser 演示

## 翻譯版本

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 此資料夾中的檔案

- `plaza.agent`: 此 pulser 演示的本地 Plaza
- `file-storage.pulser`: 以本地檔案系統為後端的儲存 pulser
- `start-plaza.sh`: 啟動 Plaza
- `start-pulser.sh`: 啟動 pulser
- `run-demo.sh`: 從一個終端機啟動完整演示，並打開瀏覽器指南以及 pulser UI

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/pulsers/file-storage/run-demo.sh
```

這會從單個終端機啟動 Plaza 和 `SystemPulser`，開啟瀏覽器指南頁面，並自動開啟 pulser UI。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中從儲存庫根目錄執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器正在運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 快速入門

從儲存庫根目錄開啟兩個終端機。

### 終端機 1：啟動 Plaza
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8256`

### 終端機 2：啟動 pulser
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

預期結果：

- pulser 在 `http://127.0.0.1:8257` 啟動
- 它向 `http://127.0.0.1:8256` 的 Plaza 進行註冊

## 在瀏覽器中嘗試

開啟：

- `http://127.0.0.1:8257/`

然後依序測試以下 pulses：

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

`bucket_create` 的建議參數：
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

`object_save` 的建議參數：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

建議用於 `object_load` 的參數：
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## 使用 Curl 進行測試

建立一個儲存桶：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

儲存物件：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

重新載入：
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## 重點說明

- 此 pulser 完全在本地運行，不需要雲端憑證
- 負載內容（payloads）非常簡單，無需額外工具即可理解
- 儲存後端稍後可以從檔案系統切換到其他供應商，同時保持 pulse 介面穩定

## 自行建置

如果您想要進行自定義：

1. 複製 `file-storage.pulser`
2. 修改連接埠與儲存的 `root_path`
3. 如果您希望與 workbench 及現有範例保持相容性，請保持相同的 pulse surface
