# YFinance Pulser 演示

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

- `plaza.agent`: 此示範使用的本地 Plaza
- `yfinance.pulser`: `YFinancePulser` 的本地示範配置
- `start-plaza.sh`: 啟動 Plaza
- `start-pulser.sh`: 啟動 pulser
- `run-demo.sh`: 從單一終端機啟動完整示範，並開啟瀏覽器指南及 pulser UI

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/pulsers/yfinance/run-demo.sh
```

這會從單個終端機啟動 Plaza 和 `YFinancePulser`，開啟瀏覽器指南頁面，並自動開啟 pulser UI。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中進入儲存庫根目錄：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher yfinance
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 快速入門

從儲存庫根目錄開啟兩個終端機。

### 終端機 1：啟動 Plaza
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8251`

### 終端機 2：啟動 pulser
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

預期結果：

- pulser 啟動於 `http://127.0.0.1:8252`
- 它會在 `http://127.0.0.1:8251` 向 Plaza 進行註冊

注意：

- 此示範需要外部網路存取權限，因為 pulser 會透過 `yfinance` 獲取即時數據
- Yahoo Finance 可能會對請求進行速率限制或間歇性拒絕

## 在瀏覽器中嘗試

開啟：

- `http://127.0.0.1:8252/`

建議的首個 pulses：

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

建議用於 `last_price` 的參數：
```json
{
  "symbol": "AAPL"
}
```

建議用於 `ohlc_bar_series` 的參數：
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## 使用 Curl 進行測試

報價請求：
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC 序列請求：
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## 重點說明

- 同一個 pulser 同時提供快照式 (snapshot-style) 與時間序列式 (time-series-style) 的 pulses
- `ohlc_bar_series` 與 workbench chart demo 以及 technical-analysis path pulser 相容
- live provider 之後可以在底層進行變更，而 pulse contract 保持不變

## 打造您自己的版本

如果您想要擴展此範例：

1. 複製 `yfinance.pulser`
2. 調整連接埠與儲存路徑
3. 如果您想要更小或更專業的目錄，可以更改或新增支援的 pulse 定義
