# Hello Plaza

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

## 此示範展示了什麼

- 在本地運行的 Plaza 註冊表
- 自動向 Plaza 註冊的代理程式
- 連接到該 Plaza 的瀏覽器端使用者介面
- 開發者可以複製到自己專案中的最小化配置集

## 此資料夾中的檔案

- `plaza.agent`: Plaza 設定範例
- `worker.agent`: worker 設定範例
- `user.agent`: 用戶代理 設定範例
- `start-plaza.sh`: 啟動 Plaza
- `start-worker.sh`: 啟動 worker
- `start-user.sh`: 啟動面向瀏覽器的 用戶代理

所有執行時狀態皆寫入於 `demos/hello-plaza/storage/`。

## 前置條件

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/hello-plaza/run-demo.sh
```

這會從單一終端機啟動 Plaza、工作器（worker）和使用者 UI，開啟瀏覽器指南頁面，並自動開啟使用者 UI。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中從儲存庫根目錄執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 快速入門

從儲存庫根目錄開啟三個終端機。

### 終端機 1：啟動 Plaza
```bash
./demos/hello-plaza/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` 回傳健康狀態

### 終端機 2：啟動 worker
```bash
./demos/hello-plaza/start-worker.sh
```

預期結果：

- worker 啟動於 `127.0.0.1:8212`
- it 會自動向 Terminal 1 的 Plaza 進行註冊

### 終端機 3：啟動使用者 UI

```bash
./demos/hello-plaza/start-user.sh
```

預期結果：

- 面向瀏覽器的使用者代理程式啟動於 `http://127.0.0.1:8214/`

## 驗證堆疊

在第四個終端機中，或在服務啟動後：
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

您應該會看到：

- 第一個指令回傳了健康的 Plaza 回應
- 第二個指令顯示了本地的 Plaza 以及已註冊的 `demo-worker`

接著開啟：

- `http://127.0.0.1:8214/`

這是用於在本地演示或螢幕錄製中分享的公開演示 URL。

## 在 Demo 展示中應重點說明的内容

- Plaza 是探索層。
- Worker 可以獨立啟動，且仍會顯示在共享目錄中。
- 面向使用者的 UI 不需要對 Worker 有硬編碼的認知。它透過 Plaza 進行探索。

## 建立您自己的實例

將此轉換為您自己實例的最簡單方法是：

1. 將 `plaza.agent`、`worker.agent` 和 `user.agent` 複製到一個新資料夾中。
2. 重新命名這些 agents。
3. 如果需要，更改連接埠。
4. 將每個 `root_path` 指向您自己的儲存位置。
5. 如果您更改了 Plaza 的 URL 或連接埠，請更新 `worker.agent` 和 `user.agent` 中的 `plaza_url`。

最需要自定義的三個重要欄位是：

- `name`：agent 作為其身份進行廣告的名稱
- `port`：HTTP 服務監聽的位置
- `root_path`：本地狀態儲存的位置

當檔案配置正確後，請執行：
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## 疑難排解

### 埠號已被佔用

編輯相關的 `.agent` 檔案並選擇一個空閒的埠號。如果您將 Plaza 移動到新的埠號，請更新兩個相依設定中的 `plaza_url`。

### 使用者 UI 顯示 Plaza 目錄為空

請檢查以下三點：

- Plaza 正在 `http://127.0.0.1:8211` 上執行
- worker 終端機仍在運行中
- `worker.agent` 仍指向 `http://127.0.0.1:8211`

### 您想要一個全新的 Demo 狀態

最安全的重置方法是將 `root_path` 的值指向一個新的資料夾名稱，而不是直接刪除現有的資料。

## 停止 Demo

在每個終端機視窗中按下 `Ctrl-C`。
