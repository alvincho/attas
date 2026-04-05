# Phemacast 個人代理

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

## 文件說明

- [詳細用戶指南](./docs/user_guide.md)
- [目前功能清單](./docs/current_features.md)

此套件保持相同的本地優先（local-first）結構：

- FastAPI 用於提供 HTML 外殼與 JSON APIs。
- React 負責互動式用戶端 UI。
- Plaza 目錄與 Pulser 執行仍透過後端代理路由進行。
- 模擬儀表板數據仍可用於早期產品開發。
- 目前的運行時從 `static/personal_agent.jsx` 提供服務，因此在早期開發中，無需等待前端打包即可立即完成重新構建。

## 套件佈局

- `app.py`: FastAPI 入口點與路由
- `data.py`: 儀表板快照存取
- `plaza.py`: Plaza 目錄與 pulser 代理輔助程式
- `templates/index.html`: 引導 React 應用程式啟動的 HTML 外殼
- `static/`: 由 FastAPI 提供的 live JSX 執行環境與 CSS
- `ui/`: 未來的 React + TypeScript + Vite 原始碼腳手架
- `docs/current_features.md`: 從舊版原型擷取的完整功能清單

## 本地執行

從儲存庫根目錄：
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

Live 應用程式直接從 `static/personal_agent.jsx` 執行。

`ui/` 目錄刻意保留，以便稍後升級為打包後的構建版本。如果您想在不影響 live runtime 的情況下嘗試該腳手架，可以在 `phem0cast/personal_agent/ui` 目錄內執行：
```bash
npm install
npm run build
```

這會輸出到 `phemacast/personal_agent/ui/dist`。

然後開啟 `http://127.0.0.1:8041`。
