# Retis 金融智能工作空間

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

`attas` 的目標是支持一個由全球金融專業人士組成的互聯網絡。每個參與者都可以運行自己的代理，透過該代理分享專業知識，同時保護自己的知識產權。在這種模式下，私有提示詞、工作流邏輯、演算法以及其他內部方法都保留在所有者的代理內部。其他參與者使用的是產生的輸出與服務，而不是直接取得底層邏輯。

## 狀態

此儲存庫正在積極開發中，且仍在不斷演進。隨著專案進行拆分、穩定化或更正式的封裝，API、配置格式和範例流程可能會發生變化。

以下兩個領域目前處於非常早期的階段，且在積極開發期間可能會快速變化：

- `prompits.teamwork`
- `phemacast` `BossPulser`

公開儲存庫旨在用於：

- 本地開發
- 評估
- 原型工作流
- 架構探索

它目前還不是一個完善的開箱即用產品，也不是一個只需單一指令即可進行的生產環境部署。

## `attas` 對開發者的定位

此儲存庫包含三個產品層：

- `prompits` 是通用的多代理執行環境與 Plaza 協調層。
- `phemacast` 是建立在 `prompits` 之上的可重複使用內容協作層。
- `attas` 是建立在這兩層之上的金融應用層。

對於開發者而言，`attas` 是金融特定工作應該放置的地方，包含例如：

- 金融 `Pulse` 定義、映射、目錄與驗證範例
- 面向金融的代理配置、個人代理流程與工作流編排
- 面向分析師、司庫團隊與投資工作流的簡報、報告模板與產品行為
- 金融特定的品牌、預設值與面向使用者的概念

如果某項變更對一般內容協作具有重複使用價值，它很可能屬於 `phemacast`。如果它是通用的多代理基礎設施，它很可能屬於 `prompits`。不要透過把 `attas` 匯入這些下層來解決重複使用問題。

![attas-3-layers-diagram-1.png](static/images/attas-3-layers-diagram-1.png)

## `phemacast` 對開發者的定位

`phemacast` 是位於 `prompits` 與 `attas` 之間的可重複使用內容協作層。它透過一組精簡的流水線概念，把動態輸入轉換為結構化內容輸出：

- `Pulse`：內容生成過程中使用的動態輸入負載或數據快照。在 `phemacast` 中，它是填充綁定、章節或模板槽位的數據。
- `Pulser`：負責取得、計算或公開 pulse 數據的代理。一個 pulser 會宣告它可以提供的 pulses，並公開如 `get_pulse_data` 這樣的 practice endpoint。
- `Phema`：結構化內容藍圖。它描述要產出什麼、輸出如何組織，以及需要哪些 pulse 綁定。
- `Phemar`：透過從 pulsers 收集 pulse 數據並將數據綁定到 `Phema` 結構中，把 `Phema` 解析為靜態負載的代理。

典型的 `phemacast` 流程如下：

1. 創作者定義或選擇一個 `Phema`。
2. `Pulser` 提供該 `Phema` 所需的 pulse 輸入。
3. `Phemar` 將這些 pulse 值綁定到藍圖中並生成結構化結果。
4. `Castr` 或下游渲染器把該結果轉換為 markdown、JSON、文字、頁面、投影片或其他面向受眾的格式。

對於開發者而言，`phemacast` 適合承載可重複使用的 pulse 驅動內容工作流、共享渲染邏輯、基於圖表的內容映射以及非金融特定內容代理。如果某個概念特定於金融數據契約、金融目錄或金融產品行為，請將其保留在 `attas` 中。

## 核心執行時概念

底層多代理模型位於 `prompits` 中，並由 `phemacast` 和 `attas` 重複使用。

- `Pit`：最小的身份單元。它攜帶名稱、描述與地址資訊等元數據。在實務上，執行時代理共享這一身份模型。
- `Practice`：掛載到代理上的能力。一個 practice 可以暴露 HTTP 路由、支援本地執行，並發布用於發現的元數據。
- `Pool`：代理的持久化邊界。Pool 儲存 Plaza 憑證、已發現的 practice 元數據、本地記憶以及其他持久化執行時狀態。
- `Plaza`：協調平面。代理向 Plaza 註冊、接收並續訂憑證、發布可搜尋卡片、發送 heartbeat、發現同儕並中繼訊息。

代理之間的連接通常這樣運作：

1. 代理從一個或多個 pool 開始運行，並掛載自己的 practices。
2. 如果它本身不是 Plaza，它會向 Plaza 註冊，並獲得穩定的 `agent_id`、持久的 `api_key` 與短期 bearer token。
3. 代理將這些憑證儲存在主 pool 中，並出現在 Plaza 的可搜尋目錄裡。
4. 其他代理透過 Plaza 搜尋，按照名稱、角色或公開的 practice 等欄位找到它。
5. 接著，代理可以透過 Plaza relay 與 mailbox 風格 endpoint 傳送訊息，或在呼叫方驗證通過後直接調用遠端 practice。

## 全新 Clone 快速入門

從全新的 checkout 開始：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

smoke 腳本會將已提交的 repo 狀態複製到一個臨時目錄，建立自己的 virtualenv，安裝依賴項，並執行一個針對面向公眾的測試套件。這是最接近 GitHub 用戶實際會拉取的狀態。

如果您想測試最新的未提交本地更改，請使用：
```bash
attas_smoke --worktree
```

該模式會將目前的作業樹複製到臨時測試目錄中，包括尚未提交的變更以及未追蹤且未被忽略的檔案。

從儲存庫根目錄，您也可以執行：
```bash
bash attas_smoke
```

在儲存庫樹狀結構中的任何子目錄下，您都可以執行：
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

該啟動器會找到儲存庫根目錄並啟動相同的冒煙測試流程。如果您將 `attas_smoke` 建立符號連結到 `PATH` 中的某個目錄，您也可以在任何地方將其作為可重複使用的命令來呼叫，並且在儲存庫樹之外工作時，可以選擇性地設定 `FINMAS_REPO_ROOT`。

## 本地優先快速入門

目前最安全的本地路徑是 Prompits 範例堆疊。它不需要 Supabase 或其他私有基礎設施，且現在針對基準桌面堆疊（baseline desk stack）具備了單一指令的本地引導流程。Python 啟動器可原生運行於 Windows、Linux 和 macOS。在 macOS/Linux 上請使用 `python3`，在 Windows 上請使用 `py -3`：
```bash
python3 -m prompits.cli up desk
```

這會啟動：

- Plaza 位在 `http://127.0.0.1:8211`
- 基線 worker 位在 `http://127.0.0.1:8212`
- 面向瀏覽器的使用者 UI 位在 `http://127.0.0.1:8214/`

您也可以使用封裝腳本：
```bash
bash run_plaza_local.sh
```

實用的後續指令：
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

如果您需要使用舊的手動流程來一次除錯單個服務：
```bash
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
```

如果您想要使用較舊的以 Supabase 為後端的 Plaza 設定，請將 `PROMPITS_AGENT_CONFIG` 指向
`attas/configs/plaza.agent` 並提供必要的環境變數。

## 遠端實作策略與稽核

Prompits 現在支援針對遠端 `UsePractice(...)` 呼叫的輕量化跨代理程式策略與稽核層。該合約存在於代理程式配置 JSON 的頂層，且僅在 `prompits` 內部使用：
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

策略說明：

- `outbound` 規則使用 `practice_id`、`target_agent_id`、`target_name`、`target_address`、`target_role` 和 `target_pit_type` 來比對目的地。
- `inbound` 規則使用 `practice_id`、`caller_agent_id`、`caller_name`、`caller_address`、`auth_mode` 和 `plaza_url` 來比對呼叫者。
- 拒絕規則優先；如果存在允許清單，遠端呼叫必須符合該清單，否則將被以 `403` 拒絕。
- 稽核列會被記錄，且當代理程式（agent）擁有連接池時，會附加到配置的稽核表中，並使用共享的 `request_id` 以便在請求與結果事件之間進行關聯。

## 儲存庫佈局
```text
attas/       金融應用層：Pulse 目錄、簡報、個人代理流程以及面向金融的配置
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## 入門指南

- 從 `prompits/README.md` 開始了解核心執行模型。
- 閱讀 `docs/CONCEPTS_AND_CLASSES.md` 以了解 `Pit`、`Practice`、`Pool`、`Plaza` 以及遠端代理流程的細節。
- 閱讀 `phemacast/README.md` 以了解內容流水線層。
- 閱讀 `attas/README.md` 以了解金融網路框架與高階概念。
- 閱讀 `ads/README.md` 以了解數據服務組件。

## 組件狀態

| 區域 | 目前公開狀態 | 備註 |
| --- | --- | --- |
| `prompits` | 最佳起點 | 以本地優先的範例和核心運行時是最容易的公開進入點。`prompits.teamwork` 套件仍處於早期階段，可能會快速變動。 |
| `attas` | 早期公開 | 核心概念和 用戶代理 工作已公開，但某些未完成的組件為了避免干擾預設流程而刻意隱藏。 |
| `phemacast` | 早期公開 | 核心流水線代碼已公開；部分報告/渲染組件仍在進行精簡與穩定化。`BossPulser` 仍處於積極開發中。 |
| `ads` | 進階 | 對於開發和研究非常有用，但某些數據工作流需要額外設置，並非首次運行的路徑。 |
| `deploy/` | 僅限範例 | 部署助手與環境相關，不應被視為成熟的公開部署方案。 |
| `mcp_servers/` | 公開源碼 | 本地 MCP 伺服器實作是公開源碼樹的一部分。 |

## 已知限制

- 部分工作流程仍假設存在選用的環境變數或第三方服務。
- `tests/storage/` 包含有用的 fixtures，但與理想的公開 fixture 集相比，它仍將確定性的測試數據與更具可變性的本地風格狀態混合在一起。
- 部署腳本僅作為範例，並非受支援的生產平台。
- 儲存庫正在快速演進，因此某些配置和模組邊界可能會發生變化。

## 路線圖

短期公開路線圖記錄於 `docs/ROADMAP.md`。

計畫中的 `prompits` 功能包括代理人之間經過身分驗證與權限控管的 `UsePractice(...)` 調用，並在執行前進行成本協商與支付處理。

計畫中的 `phemacast` 功能包括更豐富的人類智慧 `Phemar` 表示形式、更廣泛的 `Castr` 輸出格式，以及根據回饋、效率與成本進行 AI 生成的 `Pulse` 優化，此外還包括 `MapPhemar` 中更廣泛的圖表支援。

計畫中的 `attas` 功能包括更具協作性的投資與司庫工作流、針對金融專業人士調優的代理人模型，以及針對供應商與服務提供者的 API 端點到 `Pulse` 的自動映射。

## 公開儲存庫說明

- 預期機密資訊應來自環境變數與本地配置，而非提交的檔案。
- 本地資料庫、瀏覽器產生的產物以及暫存快照皆刻意排除在版本控制之外。
- 目前的程式碼庫主要針對本地開發、評估與原型工作流程，而非精緻的最終用戶封裝。

## 參與貢獻

這目前是一個由單一主要維護者管理的公開儲存庫。歡迎提出 Issue 和 Pull Request，但目前路線圖和合併決策仍由維護者主導。請參閱 `CONTRIBUTING.md` 以了解目前的開發流程。

## 授權條款

本專案採用 Apache License 2.0 授權。完整文本請參閱 `LICENSE`。
