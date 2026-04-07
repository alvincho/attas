# 分析師洞察 Pulser 演示

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

- 一個由分析師擁有的 pulser，包含多個結構化洞察 pulses
- 第二個由分析師擁有的 pulser，其建立在獨立的新聞代理與本地 Ollama 代理之上
- 一種將原始來源數據與分析師撰寫的 Prompits 及最終面向消費者的輸出進行分離的清晰方法
- 一個個人代理導覽，從另一個使用者的視角展示相同的技術棧
- 分析師或 PM 若要發布自己的觀點，需要編輯的確切檔案

## 此資料夾中的檔案

- `plaza.agent`: 用於分析師 pulser 演示的本地 Plaza
- `analyst-insights.pulser`: 定義公開 pulse 目錄的 `PathPulser` 配置
- `analyst_insight_step.py`: 共享轉換邏輯以及預設的分析師覆蓋數據包
- `news-wire.pulser`: 發布預設 `news_article` 數據包的本地上游新聞代理
- `news_wire_step.py`: 由上游新聞代理返回的預設原始新聞數據包
- `ollama.pulser`: 用於分析師提示詞演示的本地 Ollama 驅動 `llm_chat` pulser
- `analyst-news-ollama.pulser`: 組合式分析師 pulser，負責獲取新聞、應用分析師專屬提示詞、調用 Ollima 並將結果正規化為多個 pulses
- `analyst_news_ollama_step.py`: 分析師專屬提示詞包加上 JSON 正規化邏輯
- `start-plaza.sh`: 啟動 Plaza
- `start-pulser.sh`: 啟動固定的結構化分析師 pulser
- `start-news-pulser.sh`: 啟動上游預設新聞代理
- `start-ollama-pulser.sh`: 啟動本地 Ollama pulser
- `start-analyst-news-pulser.sh`: 啟動帶有提示詞的分析師 pulser
- `start-personal-agent.sh`: 啟動用於消費者視角演練的個人代理 UI
- `run-demo.sh`: 從一個終端啟動演示，並打開瀏覽器指南及主要 UI 頁面

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

該封裝預設會啟動輕量級的結構化流程。

若要改為啟動進階的新聞 + Ollama + 個人代理流程：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

針對進階路徑：
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

請使用原生 Windows Python 環境。在 PowerShell 中進入儲存庫根目錄：
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

針對進階路徑：
```powershell
$env:DEMO_ANALYST_MODE = "advanced"
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

如果瀏覽器分頁沒有自動打開，請保持啟動器運行，並在 Windows 瀏覽器中打開列印出的 `guide=` URL。

## 演示 1：結構化分析師觀點

這是僅限本地、不使用 LLM 的路徑。

從儲存庫根目錄開啟兩個終端機。

### 終端機 1：啟動 Plaza
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8266`

### 終端機 2：啟動 pulser
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

預期結果：

- pulser 會在 `http://127.0.0.1:8267` 啟動
- 它會向 `http://127.0.0.1:8266` 的 Plaza 進行註冊

## 在瀏覽器中嘗試

開啟：

- `http://127.0.0.1:8267/`

然後使用 `NVDA` 測試以下 pulses：

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

這四個 pulses 的建議參數：
```json
{
  "symbol": "NVDA"
}
```

您應該會看到：

- `rating_summary` 回傳標題判斷、目標、信心度及簡短摘要
- `thesis_bullets` 以清單形式回傳正面論點
- `risk_watch` 回傳主要風險以及需要監控的指標
- `scenario_grid` 在單一結構化負載中回傳牛市、基準及熊市情境

## 使用 Curl 進行測試

標題評分：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

論文要點：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

風險監控：
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## 分析師如何自定義此演示

主要有兩個編輯點。

### 1. 更改實際的研究視圖

編輯：

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

此文件包含種植好的 `ANALYST_COVERAGE` 封包。您可以在此處更改：

- 涵蓋的股票代碼
- 分析師姓名
- 評級標籤
- 目標價格
- 論點要點
- 關鍵風險
- 牛市/基準/熊市情景

### 2. 更改公開的 Pulse 目錄

編輯：

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

該文件控制：

- 存在哪些 pulses
- 每個 pulse 的名稱和描述
- 輸入和輸出架構
- 標籤和地址

如果您想添加新的洞察 pulse，請複製現有的條目之一，並將其指向新的 `insight_view`。

## 為什麼此模式非常有用

- 投資組合工具可以僅請求 `rating_summary`
- 報告生成器可以請求 `thesis_bullets`
- 風險儀表板可以請求 `risk_watch`
- 估值工具可以請求 `scenario_grid`

這意味著分析師只需發布一個服務，但不同的消費者可以精確地提取他們所需的數據切片。

## 下一步該往哪裡走

一旦這個本地 pulser 形狀變得合理，接下來的步驟是：

1. 向分析師覆蓋數據包中添加更多涵蓋的符號
2. 如果您想將自己的觀點與 YFinance、ADS 或 LLM 的輸出相結合，請在最後的 Python 步驟之前添加來源步驟
3. 透過共享的 Plaza 來公開 pulser，而不僅僅是透過本地的 demo Plaza

## 演示 2：分析師 Prompt Pack + Ollama + 個人代理

這個第二個流程展示了一個更符合現實的分析師設置：

- 一個代理發佈原始 `news_article` 數據
- 第二個代理透過 Ollama 暴露 `llm_chat`
- 分析師擁有的 pulser 使用其專屬的 prompt pack 將原始新聞轉換為多個可重複使用的 pulses
- 個人代理從不同使用者的視角來消耗完成的 pulses

### 提示流程的前置條件

請確保 Ollama 正在本地運行且模型已存在：

```bash
ollama serve
ollama pull qwen3:8b
```

然後從儲存庫根目錄開啟五個終端機。

### 終端機 1：啟動 Plaza

如果 Demo 1 仍在執行，請繼續使用同一個 Plaza。
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

預期結果：

- Plaza 啟動於 `http://127.0.0.1:8266`

### 終端機 2：啟動上游新聞代理程式
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

預期結果：

- news pulser 會在 `http://127.0.0.1:8268` 啟動
- 它會向 `http://127.0.0.1:8266` 的 Plaza 進行註冊

### 終端機 3：啟動 Ollama pulser
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

預期結果：

- Ollama pulser 啟動於 `http://127.0.0.1:8269`
- 它會在 `http://127.0.0.1:8266` 向 Plaza 進行註冊

### 終端機 4：啟動 prompted analyst pulser

請在新聞與 Ollama agents 已經運行後再啟動此項，因為 pulser 會在啟動期間驗證其樣本鏈。
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

預期結果：

- 提示的分析師 pulser 啟動於 `http://127.0.0.1:8270`
- 它會在 `http://127.0.0.1:8266` 向 Plaza 進行註冊

### 終端機 5：啟動個人代理
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

預期結果：

- 個人代理程式啟動於 `http://127.0.0.1:8061`

### 直接嘗試 Prompted Analyst Pulser

開啟：

- `http://127.0.0.1:8270/`

然後使用 `NVDA` 測試以下 pulses：

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

建議參數：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

您應該會看到：

- `news_desk_brief` 將上游文章轉換為 PM 風格的立場說明與簡短筆記
- `news_monitoring_points` 將相同的原始文章轉換為觀察項目與風險標記
- `news_client_note` 將相同的原始文章轉換為更整潔的面向客戶的筆記

重點在於分析師在單一文件中控制 Prompits，而下游使用者僅會看到穩定的 pulse 介面。

### 從另一個使用者的視角使用個人代理

開啟：

- `http://12:0.0.1:8061/`

然後按照以下路徑操作：

1. 開啟 `Settings`。
2. 前往 `Connection` 標籤頁。
3. 將 Plaza URL 設定為 `http://127.0.0.1:8266`。
4. 點擊 `Refresh Plaza Catalog`。
5. 建立一個 `New Browser Window`。
6. 將瀏覽器視窗切換至 `edit` 模式。
7. 新增第一個 plain pane 並將其指向 `DemoAnalystNewsWirePulser -> news_article`。
8. 使用 pane params：
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. 點擊 `Get Data` 以便使用者查看原始文章。
10. 新增第二個純文字窗格，並將其指向 `DemoAnalystPromptedNewsPulser -> news_desk_brief`。
11. 重用相同的參數並點擊 `Get Data`。
12. 新增第三個窗格，使用 `news_monitoring_points` 或 `news_client_note`。

您應該會看到：

- 一個窗格顯示來自另一個代理程式的原始上游新聞
- 下一個窗格顯示分析師處理後的視圖
- 第三個窗格顯示相同的分析師提示包如何為不同的受眾發布不同的介面

這就是關鍵的消費者故事：另一個使用者不需要了解內部的鏈路。他們只需瀏覽 Plaza，選擇一個 pulse，然後消費完成後的分析輸出。

## 分析師如何自定義提示流

在 Demo 2 中有三個主要的編輯點。

### 1. 更改上游新聞封包

編輯：

- `demos/pulsers/analyst-insights/news_wire_step.py`

這是在您更改上游來源代理所發布的種子文章的地方。

### 2. 更改分析師自己的提示

編輯：

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

該文件包含分析師擁有的提示包，包括：

- 提示設定檔名稱
- 受眾與目標
- 語氣與寫作風格
- 要求的 JSON 輸出合約

這是讓相同的原始新聞產生不同研究口吻的最快方法。

### 3. 更改公開的 Pulse 目錄

編輯：

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

該文件控制：

- 存在哪些提示的 pulses
- 每個 pulse 使用哪個提示設定檔
- 它調用了哪些上游代理
- 向下游用戶展示的輸入與輸出架構

## 為什麼此進階模式非常有用

- 上游新聞代理後續可以替換為 YFinance、ADS 或內部收集器
- 分析師保有提示詞包（prompt pack）的所有權，而不是在 UI 中硬編碼一次性的筆記
- 不同的消費者可以使用不同的 pulses，而無需了解背後的完整鏈條
- 個人代理（personal agent）成為一個乾淨的消費者介面，而不是邏輯存放的地方
