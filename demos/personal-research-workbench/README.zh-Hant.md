# 個人研究工作台

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

- 在本地運行的個人工作台 UI
- 工作台可以瀏覽的 Plaza
- 包含真實可執行Pulse（pulses）的本地與即時數據 pulsers
- 一個以圖表為導向的 `Test Run` 流程，可將市場數據轉換為計算後的指標序列
- 從精美的示範轉向自託管實例的路徑

## 此資料夾中的檔案

- `plaza.agent`: 僅用於此示範的本地 Plaza
- `file-storage.pulser`: 以檔案系統為後端的本地 pulser
- `yfinance.pulser`: 選用的市場數據 pulser，由 `yfinance` Python 模組提供支援
- `technical-analysis.pulser`: 選用的路徑 pulser，可從 OHLC 資料計算 RSI
- `map_phemar.phemar`: 嵌入式圖表編輯器使用的示範本地 MapPhemar 配置
- `map_phemar_pool/`: 包含預設 OHLC-to-RSI 映射圖的圖表儲存空間
- `start-plaza.sh`: 啟動示範 Plaza
- `start-file-storage-pulser.sh`: 啟動 pulser
- `start-yfinance-pulser.sh`: 啟動 YFinance pulser
- `start-technical-analysis-pulser.sh`: 啟動技術分析 pulser
- `start-workbench.sh`: 啟動 React/FastAPI 工作台

所有執行時狀態皆寫入於 `demos/personal-research-workbench/storage/`。啟動器也會將嵌入式圖表編輯器指向此資料夾中預設的 `map_phemar.phemar` 與 `map_phemar_pool/` 檔案。

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
./demos/personal-research-workbench/run-demo.sh
```

這會從一個終端機啟動 workbench 堆疊，開啟瀏覽器指南頁面，然後同時開啟主 workbench UI 以及核心導覽中使用的嵌入式 `MapPhemar` 路由。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

使用原生 Windows Python 環境。在 PowerShell 中從儲存庫根目錄執行：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher personal-research-workbench
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 快速入門

如果您想要完整的演示（包括 YFinance 圖表流程和圖表測試運行流程），請從儲存庫根目錄開啟五個終端機。

### 終端機 1：啟動本地 Plaza

```bash
./demos/personal-research-workbench/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8241`

### 終端機 2：啟動本地檔案儲存 pulser
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

預期結果：

- pulser 會在 `http://127.0.0.1:8242` 啟動
- 它會向 Terminal 1 的 Plaza 進行註冊

### Terminal 3：啟動 YFinance pulser
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

預期結果：

- pulser 會在 `http://127.0.0.1:8243` 啟動
- 它會向 Terminal 1 的 Plaza 進行註冊

注意：

- 此步驟需要外部網路存取權限，因為 pulser 會透過 `yfinance` 模組從 Yahoo Finance 獲取即時數據
- Yahoo 可能會偶爾對請求進行速率限制，因此此流程最好被視為即時演示，而非嚴格的固定流程

### Terminal 4：啟動技術分析 pulser
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

預期結果：

- pulser 在 `http://127.0.0.1:8244` 啟動
- 它會向 Terminal 1 的 Plaza 進行註冊

此 pulser 會從傳入的 `ohlc_series` 計算 `rsi`；或者當您僅提供 symbol、interval 和 date range 時，從 demo YFinance pulser 獲取 OHLC bars。

### Terminal 5：啟動工作台
```bash
./demos/personal-research-workbench/start-workbench.sh
```

預期結果：

- 工作台啟動於 `http://127.0.0.1:8041`

## 首次運行指南

此演示現在包含三個工作台流程：

1. 使用 file-storage pulser 的本地儲存流程
2. 使用 YFinance pulser 的即時市場數據流程
3. 使用 YFinance 和 technical-analysis pulsers 的圖表測試運行流程

打開：

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### 流程 1：瀏覽並儲存本地數據

然後按照以下簡短路徑操作：

1. 在工作台中打開設定流程。
2. 前往 `Connection` 區塊。
3. 將預設的 Plaza URL 設置為 `http://127.0.0.1:8241`。
4. 重新整理 Plaza 目錄。
5. 在工作台中打開或創建一個瀏覽器窗口。
6. 選擇已註冊的 file-storage pulser。
7. 運行其中一個內置的 pulse，例如 `list_bucket`、`bucket_create` 或 `bucket_browse`。

建議的首次交互：

- 創建一個名為 `demo-assets` 的公共 bucket
- 瀏覽該 bucket
- 儲存一個小的文本對象
- 再次將其加載回來

這為用戶提供了一個完整的閉環：豐富的 UI、Plaza 發現、pulser 執行以及持久化的本地狀態。

### 流程 2：查看數據並從 YFinance pulser 繪製圖表

使用同一個工作台會話，然後：

1. 再次重新整理 Plaza 目錄，使 YFinance pulser 出現。
2. 添加一個新的瀏覽窗格或重新配置現有的數據窗格。
3. 選擇 `ohlc_bar_series` pulse。
4. 如果工作台沒有自動選擇，請選擇 `DemoYFinancePulser` pulser。
5. 打開 `Pane Params JSON` 並使用如下 payload：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. 點擊 `Get Data`。
7. 在 `Display Fields` 中，開啟 `ohlc_series`。如果已經選取了其他欄位，請將其關閉，以便預覽直接指向時間序列本身。
8. 將 `Format` 更改為 `chart`。
9. 將 `Chart Style` 設置為 `candle`（用於 OHLC 蠟燭圖）或 `line`（用於簡單的趨勢圖）。

您應該會看到：

- 面板為所請求的代碼和日期範圍獲取 K 線數據
- 預覽從結構化數據變更為圖表
- 更改代碼或日期範圍可以在不離開工作台的情況下獲得新圖表

建議的變體：

- 將 `AAPL` 切換為 `MSFT` 或 `NVDA`
- 縮短日期範圍以獲得更緊湊的近期視圖
- 使用相同的 `ohlc_bar_series` 回應來比較 `line` 和 `candle`

### 流程 3：載入圖表並使用 Test Run 計算 RSI 序列

打開圖表編輯器路由：

- `http://127.0.0.1:804:41/map-phemar/`

然後按照此路徑操作：

1. 確認圖表編輯器中的 Plaza URL 為 `http://127.0.0.1:8241`。
2. 點擊 `Load Phema`。
3. 選擇 `OHLC To RSI Diagram`。
4. 檢查預設的圖表。它應該顯示 `Input -> OHLC Bars -> RSI 14 -> Output`。
5. 點擊 `Test Run`。
6. 使用此輸入負載：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. 執行地圖並展開步驟輸出。

你應該會看到：

- `OHLC Bars` 步驟呼叫了 demo YFinance pulser 並回傳 `ohlc_series`
- `RSI 14` 步驟將這些 bars 傳遞給 technical-analysis pulser，並帶有 `window: 14`
- 最終的 `Output` 酬載包含一個計算後的 `values` 陣列，其中含有 `timestamp` 與 `value` 項目

如果你想從頭開始重新建立相同的圖表，而不是載入種子：

1. 新增一個名為 `OHLC Bars` 的圓角節點。
2. 將其綁定到 `DemoYFinancePulser` 與 `ohlc_bar_series` pulse。
3. 新增一個名為 `RSI 14` 的圓角節點。
4. 將其綁定到 `DemoTechnicalAnalysisPulser` 與 `rsi` pulse。
5. 將 RSI 節點參數設置為：
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. 連接 `Input -> OHLC Bars -> RSI 14 -> Output`。
7. 將邊緣映射保留為 `{}`，以便匹配的欄位名稱自動流轉。

## 在 Demo 展示中應重點介紹的內容

- 即使在添加任何實時連接之前，工作台仍會加載有用的模擬儀表板數據。
- Plaza 集成是可選的，並且可以指向本地或遠程環境。
- 文件存儲 pulser 僅限本地使用，這使得公開演示既安全又可重現。
- YFinance pulser 增加了第二個故事：同一個工作台可以瀏覽實時市場數據並將其渲染為圖表。
- 圖表編輯器增加了第三個故事：同一個後端可以編排多步驟流程，並通過 `Test Run` 展示每個步驟。

## 建立您自己的實例

有三種常見的自定義路徑：

### 修改預設的儀表板與工作區數據

工作台從以下位置讀取其儀表板快照：

- `attas/personal_agent/data.py`

這是替換您自己的自定義觀察列表、指標或工作區預設值最快的地方。

### 修改視覺外殼

目前的即時工作台運行時由以下文件提供：

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

如果您想重新設計 Demo 的主題或為您的受眾簡化 UI，請從這裡開始。

### 修改連接的 Plaza 與 pulsers

如果您需要不同的後端：

1. 複製 `plaza.agent`、`file-storage.pulser`、`yfinance.pulser` 和 `technical-analysis.pulser`
2. 重新命名服務
3. 更新連接埠與存儲路徑
4. 修改 `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` 中的預設圖表，或直接從工作台中建立您自己的圖表
5. 準備就緒後，將 Demo 的 pulsers 替換為您自己的 agents

## 選用工作台設定

啟動器腳本支援一些實用的環境變數：
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

在開發期間主動編輯 FastAPI 應用程式時，請使用 `PHEMACAST_PERSONAL_AGENT_RELOAD=1`。

## 疑難排解

### 工作台已載入，但 Plaza 結果為空

請檢查以下三點：

- `http://127.0.0.1:8241/health` 可正常存取
- 當您需要這些流程時，file-storage、YFinance 和 technical-analysis pulser 終端機仍處於運行狀態
- 工作台的 `Connection` 設定指向 `http://127.0.0.1:8241`

### pulser 尚未顯示任何物件

這在首次啟動時是正常的。Demo 儲存後端初始狀態為空。

### YFinance 面板未繪製圖表

請檢查以下事項：

- YFinance pulser 終端機正在運行
- 選定的 pulse 為 `ohlc_bar_series`
- `Display Fields` 包含 `ohlc_series`
- `Format` 設定為 `chart`
- `Chart Style` 為 `line` 或 `candle`

如果請求本身失敗，請嘗試另一個代碼，或在短暫等待後重新運行，因為 Yahoo 可能會間歇性地進行速率限制或拒絕請求。

### 圖表 `Test Run` 失敗

請檢查以下事項：

- `http://127.0.0.1:8241/health` 可正常存取
- YFinance pulser 正在 `http://127.0.0.1:8243` 上運行
- technical-analysis pulser 正在 `http://127.0.0.1:8244` 上運行
- 已載入的圖表為 `OHLC To RSI Diagram`
- 輸入負載包含 `symbol`、`interval`、`start_date` 和 `end_date`

如果 `OHLC Bars` 步驟首先失敗，問題通常是即時 Yahoo 存取或速率限制。如果 `RSI 14` 步驟失敗，最常見的原因是 technical-analysis pulser 未運行，或者上游 OHLC 回應未包含 `ohlc_series`。

### 您想要重置 Demo

最安全的重置方法是將 `root_path` 值指向新的資料夾名稱，或者在沒有任何 demo 程序運行時刪除 `demos/personal-research-workbench/storage/` 資料夾。

## 停止演示

在每個終端機視窗中按下 `Ctrl-C`。
