# Current Feature Inventory

This document captures the current feature surface of `phemacast/personal_agent` so the React implementation has an explicit parity target as it evolves.

## Product Shape

- Local-first prototype served by FastAPI.
- Browser-based personal terminal for pulses, providers, positions, transactions, analytics, and workflow cost.
- Mock in-memory dashboard data for rapid UI development.
- Plaza-aware browser and mind-map tooling that can discover pulsers and run pulse tests.

## Backend Routes

- `GET /`: HTML application shell.
- `GET /index`: redirect to root.
- `GET /api/dashboard`: dashboard bootstrap payload.
- `GET /api/workspaces/{workspace_id}`: workspace detail lookup.
- `GET /api/plaza/catalog?plaza_url=...`: normalized Plaza pulser catalog.
- `POST /api/plaza/panes/run`: proxy to Plaza pulser test execution.
- `GET /health`: health check.

## Bootstrap and Data

- Server injects initial dashboard payload into the page.
- Asset versioning is based on file modification times.
- Dashboard snapshot contains:
- meta information
- hero metrics
- coverage
- watchlist
- providers
- positions
- analytics
- transactions
- workspace summaries
- activity feed
- browser bookmarks and market views
- settings defaults

## App Shell

- Left rail with system metadata.
- Theme switcher with three themes:
- Mercury Ledger
- Signal Paper
- After Hours
- Main menu bar with File and Window groups.
- Quick actions for:
- New Workspace
- New Browser Window
- New Mind Map Window
- Settings
- Workspace dock area for docked windows.
- Floating layer for externalized windows.
- Workspace deck sidebar.
- Activity relay sidebar.

## Workspace Management

- Multiple saved workspaces plus new scratch workspaces from the File menu.
- Active workspace selection.
- Workspace metadata:
- name
- kind
- focus
- status
- owner
- description
- pane labels
- highlight notes
- Default workspace creation with starter windows.
- Docked window ordering and reordering.

## Window Model

- Two window types:
- Browser
- Mind Map
- Two window modes:
- Docked
- External popup
- Per-window metadata:
- title
- subtitle
- order
- popup position
- z-index

## Popup Windows

- Browser windows can open in separate popup windows.
- Mind-map windows can open in separate popup windows.
- Popup documents reuse the main app styling.
- Popup state stays linked to the main workspace state.
- Popup bounds are persisted.
- Popup close handling cleans up active interactions.

## Preferences and Local Persistence

- Preferences stored in localStorage.
- Workspace state stored in localStorage.
- Browser layout snapshots stored in localStorage.
- Preferences cover:
- theme
- sidebar state
- default workspace
- default market filter
- compact frontline preference
- profile fields
- payment fields
- API keys
- multiple LLM route configs
- connection defaults

## Settings Modal

- Multi-tab settings modal.
- Tabs:
- Profile
- Payment
- LLM Config
- API Keys
- Connection
- Profile fields:
- display name
- email
- desk label
- timezone
- theme choice
- Payment fields:
- plan
- billing email
- monthly budget
- current spend display
- autopay toggle
- API key fields:
- OpenAI
- Finnhub
- Alpha Vantage
- Broker token
- LLM config management:
- add/remove route configs
- default route selection
- direct API route type
- Plaza `llm_pulse` route type
- provider/model/base URL/API key/temperature editing
- Connection fields:
- connection mode
- host
- default Plaza URL
- storage choice
- refresh Plaza catalog action

## Plaza Integration

- Plaza URL normalization.
- Catalog request to `/api/plazas_status`.
- Pulser test request to `/api/pulsers/test`.
- Pulser catalog deduplication.
- Supported pulse deduplication.
- Preference for richer local loopback pulsers over stale duplicates.
- Plaza status pill and detail messaging in the UI.

## Browser Window

- Symbol search input with draft/commit behavior.
- Browser-level Plaza refresh.
- View and Edit page modes.
- Save local layout.
- Load local layout.
- Delete window.
- Dock/popup toggle.
- Add pane menu in edit mode.
- Browser window empty states.

## Browser Pane Model

- Pane types:
- Plain
- Mind Map
- Pane layout fields:
- x
- y
- w
- h
- z
- Drag and resize interactions for panes.
- Pane title and toolbar.
- Pane config dialog.
- Pane run action.
- Pane delete action.

## Browser Pane Configuration

- Pulser search filter.
- Pulser select.
- Pulse select.
- Practice selection through pulser metadata.
- Display format options:
- Plain Text
- JSON
- List
- Chart
- Chart styles:
- Bar
- Line
- Candle
- Pane params JSON editor with collapsed summary.
- Get Data action.
- Result-aware display field picker.
- Field preview renderer.
- Error and status messaging.

## Browser Layout Snapshots

- Save a named local layout snapshot for a specific browser window.
- Load a saved snapshot back into the window.
- Persist browser defaults and pane layouts.
- Restore pane layouts, defaults, and linked mind-map editors from snapshots.

## Browser Data Rendering

- Result rendering for objects, arrays, primitives, and selected field subsets.
- List rendering for array/object data.
- JSON rendering for raw payload inspection.
- Lightweight chart rendering for numeric series.

## Mind Map Window

- Dedicated mind-map window type.
- Palette/stencil for creating pulse nodes.
- Canvas with pan and zoom.
- Empty state guidance.
- Inspector panel.
- Node config modal.
- Directional links between nodes.
- Connection labels and compatibility state.
- External linked editor mode for browser mind-map panes.

## Mind Map Node Model

- Node template type:
- Pulse
- Node fields:
- title
- body/description
- x
- y
- w
- h
- pulser mode
- pulser id/name/address
- practice id
- pulse name/address
- params JSON
- input schema
- output schema

## Mind Map Behaviors

- Drag node from stencil onto canvas.
- Drag nodes within the canvas.
- Select node and edge.
- Delete node and edge.
- Start link from node connection points.
- Complete link on another node.
- Automatic anchor selection when not explicitly set.
- Shared state between pane canvas and linked full editor.

## Mind Map Catalog and Pulse Selection

- Plaza-aware pulser catalog for mind-map windows.
- Node pulser modes:
- Specified Pulser
- Dynamic Pulser
- Dynamic pulse merging across pulsers.
- Preferred market pulse defaults.
- Node pulse selection updates:
- description
- input schema
- output schema
- sample params
- title fallback

## Mind Map Compatibility Checks

- Schema-aware edge validation between source output and target input.
- Warning when a linked node is missing.
- Warning for missing required input fields.
- Warning for field type mismatch.
- Compatible state when source output covers target input.

## Legacy Constraints and Gaps

- The original prototype is large and highly imperative.
- Most UI state lives in one global client object.
- Rendering is string-template based.
- Interaction code for panes, popups, and mind maps is tightly coupled.
- The React rebuild should preserve the behaviors above while replacing the old rendering model with component state and typed modules.
