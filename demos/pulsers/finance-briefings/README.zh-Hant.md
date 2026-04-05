# 金融簡報工作流演示

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

- 一個 Attas 擁有的 `FinancialBriefingPulser`，用於公開 workflow-seed pulses 與 finance briefing step pulses
- 一個 workflow-entry context pulse：
  - `prepare_finance_briefing_context`
  - 使用 `workflow_name` 來區分工作流：`morning_desk_briefing`、`watchlist_check` 或 `research_roundup`
- 共享的 finance step pulses：
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_blieifing_payload`
- 下游發佈/匯出 pulses：
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## 為何存在此功能

MapPhemar 透過呼叫 pulsers 和 pulses 來執行圖表。finance briefing 工作流最初是 `attas` 中的純 Python 函數，但目前的圖表將這些工作流分解為可編輯的步驟節點，因此運行時現在使用 Attas 原生的 pulser，而非通用的 MCP 封裝。

運行時介面如下：

- [finance-briefings.pulser](./finance-briefings.pulser): `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser` 的 demo 配置
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): 由 Attas 擁有的 pulser 類別，負責承載工作流種子和步驟 pulses
- [briefings.py](../../../attas/workflows/briefings.py): 由 pulser 使用的公開 finance briefing 步驟輔助工具

## 執行時假設

- Plaza 位在 `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` 位在 `http://127.0.0.1:8271`

## 單一指令啟動

從儲存庫根目錄：
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

這會從單個終端機啟動本地 Plaza 以及金融簡報 pulser，開啟瀏覽器指南頁面，並自動開啟 pulser UI。

如果您希望啟動器僅保留在終端機中，請設置 `DEMO_OPEN_BROWSER=0`。

## 平台快速入門

### macOS 與 Linux

從儲存庫根目錄：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

請搭配 Ubuntu 或其他 Linux 發行版使用 WSL2。在 WSL 內的儲存庫根目錄下執行：
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

如果瀏覽器分頁無法從 WSL 自動開啟，請保持啟動器運行，並在 Windows 瀏覽器中開啟列印出的 `guide=` URL。

原生 PowerShell / 命令提示字元封裝器尚未提交，因此目前支援的 Windows 路徑是 WSL2。

## 手動啟動

從儲存庫根目錄：
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## 相關圖表檔案

這些圖表位於 `demos/files/diagrams/`：

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

每個圖表都遵循相同的可編輯結構：

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## 目前的 MapPhemar 匹配度

這些工作流可以在目前的 MapPhemar 模型中運行，無需添加新的節點類型或架構：

- 可執行步驟是常規的 `rectangle` 節點
- 邊界使用 `pill`
- 分支功能仍可透過 `branch` 使用
- 產出物的擴散（fan-out）由工作流節點的多個輸出邊（edges）處理

目前的運行限制：

- `Input` 只能連接到一個下游節點，因此擴散必須發生在第一個可執行工作流節點之後，而不是直接從 `Input` 開始

這些逐步進行的金融工作流不需要新的 MapPhemar 節點類型或架構擴展。常規的可執行節點加上 Attas pulser 介面已足以滿足目前的儲存、編輯和執行需求。
