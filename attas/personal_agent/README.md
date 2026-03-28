# attas Personal Agent

`attas/personal_agent` is now a standalone web application prototype for the Personal Agent concept described in the original notes.

The implementation is intentionally local-first:

- FastAPI serves the application shell and JSON endpoints.
- The UI is an editorial terminal-style dashboard built with HTML, CSS, and vanilla JavaScript.
- Dashboard data is mocked in-memory for now, so the app can run without Plaza, broker, or pulser credentials.
- The shape of the UI still follows the README direction: multi-window workspaces, pulse-driven market views, provider comparison, transaction routing, analytics monitoring, and settings surfaces.

## Files

- `app.py`: FastAPI entrypoint and routes
- `data.py`: mock dashboard payloads and workspace detail helpers
- `templates/index.html`: main HTML shell
- `static/personal_agent.css`: visual system and responsive layout
- `static/personal_agent.js`: client-side rendering and workspace/theme interactions

## Run Locally

From the repository root:

```bash
uvicorn attas.personal_agent.app:app --reload --port 8040
```

Then open `http://127.0.0.1:8040`.

You can also run:

```bash
python -m attas.personal_agent.app
```

Or from inside `attas/personal_agent`:

```bash
python3 app.py
```

If you want reload mode with direct script execution, set `ATTAS_PERSONAL_AGENT_RELOAD=1`.

## Current Scope

This version does not yet connect to live Attas plazas or external providers. It is the web UI foundation that future work can wire into:

- `prompits` BaseAgent capabilities
- Plaza discovery and `UsePractice`
- local or remote storage pools
- broker routing
- pulser, phemar, and castr integrations

## Architecture Notes

The current web app maps the original requirements this way:

- Data access: watchlist, provider bench, and pulse coverage cards
- Transactions: routing tape and broker/manual venue display
- Analytics: execution queue and status cards
- Investment management: positions ledger and P/L
- Multi-window UI: workspace deck plus focused workspace spotlight
- Settings: theme, billing, profile, and storage summary
- the tiles can be reposition or popup and dock back
- the Browser window can be docked to the workspace, a search bar at the top, and a list of bookmarks on the left

## menu bar

- File
    - New Workspace
- Window
    - New Browser Window
