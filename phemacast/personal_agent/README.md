# Phemacast Personal Agent

## Translations

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

`phemacast/personal_agent` is the standalone Phemacast personal research workbench.

## Documentation

- [Detailed User Guide](./docs/user_guide.md)
- [Current Feature Inventory](./docs/current_features.md)

The package keeps the same local-first shape:

- FastAPI serves the HTML shell and JSON APIs.
- React owns the interactive client UI.
- Plaza catalog and pulser execution still flow through backend proxy routes.
- Mock dashboard data remains available for early product development.
- The current live runtime is served from `static/personal_agent.jsx` so the rebuild works immediately in early development without waiting on a frontend bundle.

## Package Layout

- `app.py`: FastAPI entrypoint and routes
- `data.py`: dashboard snapshot access
- `plaza.py`: Plaza catalog and pulser proxy helpers
- `templates/index.html`: HTML shell that bootstraps the React app
- `static/`: live JSX runtime and CSS served by FastAPI
- `ui/`: future React + TypeScript + Vite source scaffold
- `docs/current_features.md`: full feature inventory captured from the legacy prototype

## Run Locally

From the repository root:

```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

The live app runs directly from `static/personal_agent.jsx`.

The `ui/` directory is intentionally staged for a later promotion to a bundled build. If you want to experiment with that scaffold without touching the live runtime, from inside `phemacast/personal_agent/ui` you can run:

```bash
npm install
npm run build
```

That outputs to `phemacast/personal_agent/ui/dist`.

Then open `http://127.0.0.1:8041`.
