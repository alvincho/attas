# ADS Pulser 演示

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

## 此示範涵蓋的內容

- `ADSPulser` 如何建立在標準化的 ADS 表格之上
- 調度器 (dispatcher) 與工作器 (worker) 的活動如何轉化為 pulser 可見的數據
- 您自己的收集器 (collectors) 如何將數據寫入 ADS 表格，並透過現有的 pulses 呈現出來

## 設定

請參閱快速入門指南：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

或者從儲存庫根目錄使用專注於 pulser 的單一指令封裝器：
```bash
./demos/pulsers/ads/run-demo.sh
```

該封裝啟動了與 `data-pipeline` 相同的 SQLite ADS 堆疊，但會開啟一個瀏覽器指南和專注於 pulser-first 逐步操作的標籤頁。

這會啟動：

1. ADS dispatcher
2. ADS worker
3. ADS pulser
4. boss UI

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中進入儲存庫根目錄：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

如果瀏覽器分頁沒有自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

## 初步 Pulser 檢查

當範例作業完成後，請開啟：

- `http://127.0.0.1:9062/`

然後測試：

1. 使用 `{"symbol":"AAPL","limit":1}` 測試 `security_master_lookup`
2. 使用 `{"symbol":"AAPL","limit":5}` 測試 `daily_price_history`
3. 使用 `{"symbol":"AAPL"}` 測試 `company_profile`
4. 使用 `{"symbol":"AAPL","number_of_articles":3}` 測試 `news_article`

## 為什麼 ADS 與眾不同

其他的 pulser 範例大多直接從即時供應商或本地儲存後端讀取。

`ADSPulser` 則是從 ADS 流水線寫入的正規化表中讀取：

- workers 收集或轉換來源數據
- dispatcher 持久化正規化行
- `ADSPulser` 將這些行作為可查詢的 pulses 進行公開

這使其成為解釋如何添加您自己的來源適配器的理想範例。

## 新增您自己的來源

具體的逐步教學位於：

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

請參考此處的自定義範例：

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

這些範例展示了使用者定義的收集器如何寫入：

- `ads_news`，透過 `news_article` 提供使用
- `ads_daily_price`，透過 `daily_price_history` 提供使用
