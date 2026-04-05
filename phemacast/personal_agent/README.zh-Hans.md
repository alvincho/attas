# Phemacast 个人代理

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

## 文档说明

- [详细用户指南](./docs/user_guide.md)
- [当前功能清单](./docs/current_features.md)

该软件包保持相同的本地优先（local-first）结构：

- FastAPI 用于提供 HTML 外壳与 JSON APIs。
- React 负责交互式客户端 UI。
- Plaza 目录与 Pulser 执行仍通过后端代理路由进行。
- 模拟仪表板数据仍可用于早期产品开发。
- 当前的运行时从 `static/personal_agent.jsx` 提供服务，因此在早期开发中，无需等待前端打包即可立即完成重新构建。

## 包布局

- `app.py`: FastAPI 入口点与路由
- `data.py`: 仪表板快照访问
- `plaza.py`: Plaza 目录与 pulser 代理辅助程序
- `templates/index.html`: 引导 React 应用启动的 HTML 外壳
- `static/`: 由 FastAPI 提供的 live JSX 运行时与 CSS
- `ui/`: 未来的 React + TypeScript + Vite 源码脚手架
- `docs/current_features.md`: 从旧版原型获取的完整功能清单

## 本地运行

从仓库根目录：
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

Live 应用直接从 `static/personal_agent.jsx` 运行。

`ui/` 目录特意保留，以便稍后升级为打包后的构建版本。如果您想在不影响 live runtime 的情况下尝试该脚手架，可以在 `phem0cast/personal_agent/ui` 目录下执行：
```bash
npm install
npm run build
```

这会输出到 `phemacast/personal_agent/ui/dist`。

然后打开 `http://127.0.0.1:8041`。
