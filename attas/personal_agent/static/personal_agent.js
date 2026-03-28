const state = {
  dashboard: window.__ATTAS_BOOTSTRAP__ || null,
  assetVersion: window.__ATTAS_ASSET_VERSION__ || "dev",
  activeFilter: "All",
  activeWorkspaceId: null,
  workspaces: [],
  menuOpen: null,
  settingsOpen: false,
  settingsTab: "profile",
  nextWorkspaceIndex: 1,
  nextWindowIndex: 1,
  nextZ: 200,
  dragWindowId: null,
  paneInteraction: null,
  popupRefs: {},
  preferences: null,
};

const SETTINGS_STORAGE_KEY = "attas.personal_agent.preferences.v1";
const THEME_OPTIONS = [
  { id: "mercury", label: "Mercury Ledger" },
  { id: "paper", label: "Signal Paper" },
  { id: "after-hours", label: "After Hours" },
];
const FILTER_OPTIONS = ["All", "Stock", "FX", "Crypto", "Commodity"];
const SETTINGS_TABS = [
  { id: "profile", label: "Profile", detail: "Identity, theme, and desk defaults" },
  { id: "payment", label: "Payment", detail: "Plan, billing, and budget controls" },
  { id: "api_keys", label: "API Keys", detail: "Locally stored provider credentials" },
  { id: "connection", label: "Connection", detail: "Workspace, storage, and local runtime" },
];
const DEFAULT_BROWSER_PANE_LAYOUT = {
  zCounter: 5,
  panes: {
    monitor: { x: 0, y: 0, w: 39, h: 43, z: 1 },
    feed: { x: 40.5, y: 0, w: 26.5, h: 43, z: 2 },
    story: { x: 68.5, y: 0, w: 31.5, h: 43, z: 3 },
    tool: { x: 0, y: 45, w: 33, h: 55, z: 4 },
    tape: { x: 34.5, y: 45, w: 65.5, h: 55, z: 5 },
  },
};
const BROWSER_PANE_MIN = { w: 22, h: 20 };

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

function currency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 100 ? 2 : 4,
  }).format(value);
}

function percent(value) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function formatMarketPrice(item) {
  if (item.asset_class === "FX") {
    return item.price.toFixed(4);
  }
  return currency(item.price);
}

function sparkline(points) {
  const width = 240;
  const height = 42;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const spread = Math.max(max - min, 1);
  const line = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((point - min) / spread) * (height - 6) - 3;
      return `${x},${y}`;
    })
    .join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="spark-gradient" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="currentColor"></stop>
          <stop offset="100%" stop-color="transparent"></stop>
        </linearGradient>
      </defs>
      <polygon class="spark-fill" points="${area}"></polygon>
      <polyline points="${line}"></polyline>
    </svg>
  `;
}

function matchesQuery(query, fields) {
  if (!query) {
    return true;
  }
  const haystack = fields.join(" ").toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function getThemeLabel(themeId) {
  return THEME_OPTIONS.find((option) => option.id === themeId)?.label || "Mercury Ledger";
}

function getPreferenceDefaults() {
  return {
    theme: "mercury",
    sidebarCollapsed: false,
    defaultWorkspaceId: state.workspaces[0]?.id || null,
    defaultFilter: "All",
    compactFrontline: true,
    profileDisplayName: state.dashboard?.settings?.profile_name || "attas User",
    profileEmail: "user@local.attas",
    profileDesk: state.dashboard?.meta?.profile || "Personal research desk",
    profileTimezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
    paymentPlan: state.dashboard?.settings?.billing_plan || "attas Personal Pro",
    paymentEmail: "billing@local.attas",
    paymentBudget: "500",
    paymentAutopay: true,
    apiKeyOpenAI: "",
    apiKeyFinnhub: "",
    apiKeyAlphaVantage: "",
    apiKeyBroker: "",
    connectionMode: "Local simulation workspace",
    connectionHost: window.location.origin,
    connectionStorage: state.dashboard?.settings?.active_storage || state.dashboard?.meta?.storage_pool || "Filesystem + SQLite edge cache",
  };
}

function normalizePreferences(candidate = {}) {
  const defaults = getPreferenceDefaults();
  const normalized = {
    ...defaults,
    ...candidate,
  };

  if (!THEME_OPTIONS.some((option) => option.id === normalized.theme)) {
    normalized.theme = defaults.theme;
  }

  if (!FILTER_OPTIONS.includes(normalized.defaultFilter)) {
    normalized.defaultFilter = defaults.defaultFilter;
  }

  if (!state.workspaces.some((workspace) => workspace.id === normalized.defaultWorkspaceId)) {
    normalized.defaultWorkspaceId = defaults.defaultWorkspaceId;
  }

  normalized.sidebarCollapsed = Boolean(normalized.sidebarCollapsed);
  normalized.compactFrontline = Boolean(normalized.compactFrontline);
  normalized.paymentAutopay = Boolean(normalized.paymentAutopay);
  return normalized;
}

function loadPreferences() {
  let saved = {};

  try {
    saved = JSON.parse(window.localStorage.getItem(SETTINGS_STORAGE_KEY) || "{}");
  } catch (error) {
    saved = {};
  }

  state.preferences = normalizePreferences(saved);
  state.activeFilter = state.preferences.defaultFilter;
  if (state.preferences.defaultWorkspaceId) {
    state.activeWorkspaceId = state.preferences.defaultWorkspaceId;
  }
  applyPreferences();
}

function savePreferences() {
  try {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(state.preferences));
  } catch (error) {
    // Local persistence is best-effort only.
  }
}

function applyPreferences() {
  if (!state.preferences) {
    return;
  }

  document.body.dataset.theme = state.preferences.theme;
  document.body.dataset.sidebar = state.preferences.sidebarCollapsed ? "collapsed" : "expanded";
  document.body.dataset.frontline = state.preferences.compactFrontline ? "compact" : "expanded";
}

function updatePreference(key, value) {
  if (!state.preferences) {
    return;
  }

  state.preferences[key] = value;
  state.preferences = normalizePreferences(state.preferences);
  if (key === "defaultWorkspaceId" && state.preferences.defaultWorkspaceId) {
    state.activeWorkspaceId = state.preferences.defaultWorkspaceId;
  }
  if (key === "defaultFilter") {
    state.activeFilter = state.preferences.defaultFilter;
  }
  applyPreferences();
  savePreferences();
  renderAll();
}

function resetPreferences() {
  state.preferences = getPreferenceDefaults();
  state.activeFilter = state.preferences.defaultFilter;
  state.activeWorkspaceId = state.preferences.defaultWorkspaceId;
  applyPreferences();
  savePreferences();
  renderAll();
}

function toggleSidebar() {
  updatePreference("sidebarCollapsed", !state.preferences?.sidebarCollapsed);
}

function openSettings() {
  state.settingsOpen = true;
  renderSettingsDialog();
}

function closeSettings() {
  state.settingsOpen = false;
  renderSettingsDialog();
}

function setSettingsTab(tabId) {
  if (!SETTINGS_TABS.some((tab) => tab.id === tabId)) {
    return;
  }
  state.settingsTab = tabId;
  renderSettingsDialog();
}

function maskSecret(secret) {
  if (!secret) {
    return "Not configured";
  }

  if (secret.length <= 6) {
    return "Configured";
  }

  return `Configured ••••${secret.slice(-4)}`;
}

function countConfiguredKeys() {
  return [
    state.preferences?.apiKeyOpenAI,
    state.preferences?.apiKeyFinnhub,
    state.preferences?.apiKeyAlphaVantage,
    state.preferences?.apiKeyBroker,
  ].filter(Boolean).length;
}

function cloneBrowserPaneLayout() {
  return {
    zCounter: DEFAULT_BROWSER_PANE_LAYOUT.zCounter,
    panes: Object.fromEntries(
      Object.entries(DEFAULT_BROWSER_PANE_LAYOUT.panes).map(([paneId, layout]) => [
        paneId,
        { ...layout },
      ]),
    ),
  };
}

function getBrowserPaneLayoutState(windowItem, viewId) {
  if (!windowItem.browserPaneLayouts) {
    windowItem.browserPaneLayouts = {};
  }

  if (!windowItem.browserPaneLayouts[viewId]) {
    windowItem.browserPaneLayouts[viewId] = cloneBrowserPaneLayout();
  }

  return windowItem.browserPaneLayouts[viewId];
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeBrowserPaneLayout(layout) {
  layout.w = clamp(layout.w, BROWSER_PANE_MIN.w, 100);
  layout.h = clamp(layout.h, BROWSER_PANE_MIN.h, 100);
  layout.x = clamp(layout.x, 0, 100 - layout.w);
  layout.y = clamp(layout.y, 0, 100 - layout.h);
}

function applyBrowserPaneStyle(element, layout) {
  if (!element || !layout) {
    return;
  }

  element.style.left = `${layout.x}%`;
  element.style.top = `${layout.y}%`;
  element.style.width = `${layout.w}%`;
  element.style.height = `${layout.h}%`;
  element.style.zIndex = String(layout.z);
}

function focusBrowserPane(windowItem, viewId, paneId) {
  const layoutState = getBrowserPaneLayoutState(windowItem, viewId);
  layoutState.zCounter += 1;
  layoutState.panes[paneId].z = layoutState.zCounter;
}

function resetBrowserPaneLayout(windowId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const view = getBrowserView(located.windowItem);
  if (!view) {
    return;
  }

  located.windowItem.browserPaneLayouts[view.id] = cloneBrowserPaneLayout();
  renderWindowSurfaces();
}

function createWindow(type, title, subtitle, order, overrides = {}) {
  return {
    id: `window-${state.nextWindowIndex++}`,
    type,
    title,
    subtitle,
    order,
    mode: overrides.mode || "docked",
    x: overrides.x ?? 80 + order * 18,
    y: overrides.y ?? 96 + order * 16,
    z: state.nextZ++,
    searchQuery: overrides.searchQuery || "",
    selectedBookmarkId: overrides.selectedBookmarkId || null,
    selectedBrowserViewId: overrides.selectedBrowserViewId || null,
    selectedSymbolId: overrides.selectedSymbolId || null,
    browserPaneLayouts: overrides.browserPaneLayouts || {},
  };
}

function createDefaultWindows() {
  const browser = state.dashboard.browser || { query: "", bookmarks: [], views: [] };
  const defaultView =
    browser.views.find((view) => view.id === browser.default_view) ||
    browser.views[0] ||
    { id: "browser", symbols: [] };
  const defaultSymbol = defaultView.symbols?.[0] || null;
  const firstBookmark = browser.bookmarks[0]?.id || null;

  return [
    createWindow("browser", "Research Browser", "Docked search and bookmarks surface", 0, {
      searchQuery: browser.query || "",
      selectedBookmarkId: firstBookmark,
      selectedBrowserViewId: defaultView.id,
      selectedSymbolId: defaultSymbol?.id || null,
    }),
    createWindow("watchlist", "Pulse Tape", "Repositionable multi-asset market board", 1),
    createWindow("positions", "Position Ledger", "Holdings, cost basis, and live P/L", 2),
    createWindow("providers", "Provider Bench", "Latency, quality, and cost comparison", 3),
    createWindow("analytics", "Analytics Queue", "Scheduled and on-demand agent workloads", 4),
    createWindow("transactions", "Routing Tape", "Orders, imports, and network events", 5),
  ];
}

function createWorkspaceState(workspace, index) {
  return {
    ...workspace,
    windows: createDefaultWindows(index),
  };
}

function initializeState(payload) {
  state.dashboard = payload;
  if (state.workspaces.length > 0) {
    return;
  }

  state.workspaces = payload.workspaces.map((workspace, index) => createWorkspaceState(workspace, index));
  state.nextWorkspaceIndex = state.workspaces.length + 1;
  state.activeWorkspaceId = state.workspaces[0]?.id || null;
  loadPreferences();
}

function getActiveWorkspace() {
  return state.workspaces.find((workspace) => workspace.id === state.activeWorkspaceId) || null;
}

function findWindowById(windowId) {
  for (const workspace of state.workspaces) {
    const found = workspace.windows.find((windowItem) => windowItem.id === windowId);
    if (found) {
      return { workspace, windowItem: found };
    }
  }
  return null;
}

function sortDockedWindows(workspace) {
  return workspace.windows
    .filter((windowItem) => windowItem.mode === "docked")
    .sort((left, right) => left.order - right.order);
}

function sortExternalWindows(workspace) {
  return workspace.windows
    .filter((windowItem) => windowItem.mode === "external")
    .sort((left, right) => left.z - right.z);
}

function sortFloatingWindows(workspace) {
  return sortExternalWindows(workspace);
}

function bringWindowToFront(windowItem) {
  windowItem.z = state.nextZ++;
}

function renderSystemMeta(payload) {
  const metaItems = [
    ["Mode", payload.meta.mode],
    ["Plaza", payload.meta.plaza_url],
    ["Storage", payload.meta.storage_pool],
    ["Last Sync", payload.meta.last_sync],
  ];

  byId("system-meta").innerHTML = metaItems
    .map(([label, value]) => `
      <li>
        <strong>${escapeHtml(label)}</strong>
        <span>${escapeHtml(value)}</span>
      </li>
    `)
    .join("");
}

function renderCoverage(payload) {
  byId("coverage-stack").innerHTML = payload.coverage
    .map((item) => `
      <article class="coverage-card">
        <strong>${escapeHtml(item.value)}</strong>
        <span>${escapeHtml(item.label)}</span>
        <p>${escapeHtml(item.detail)}</p>
      </article>
    `)
    .join("");
}

function renderSettings(payload) {
  const defaultWorkspace =
    state.workspaces.find((workspace) => workspace.id === state.preferences?.defaultWorkspaceId) ||
    getActiveWorkspace();

  byId("settings-card").innerHTML = `
    <div class="compact-grid">
      <div>
        <strong>Profile</strong>
        <p>${escapeHtml(state.preferences?.profileDisplayName || payload.settings.profile_name)}</p>
      </div>
      <div>
        <strong>Payment</strong>
        <p>${escapeHtml(state.preferences?.paymentPlan || payload.settings.billing_plan)}</p>
      </div>
      <div>
        <strong>API Keys</strong>
        <p>${countConfiguredKeys()} configured</p>
      </div>
      <div>
        <strong>Connection</strong>
        <p>${escapeHtml(state.preferences?.connectionMode || "Local simulation workspace")}</p>
      </div>
    </div>
  `;
}

function renderMenuState() {
  document.querySelectorAll("[data-menu-group]").forEach((group) => {
    const isOpen = group.dataset.menuGroup === state.menuOpen;
    group.classList.toggle("is-open", isOpen);
  });
}

function renderThemeState() {
  document.querySelectorAll("[data-theme-target]").forEach((button) => {
    button.classList.toggle("is-active", document.body.dataset.theme === button.dataset.themeTarget);
  });
}

function renderSidebarState() {
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    const isRailButton = Boolean(button.closest(".rail"));
    const collapsed = Boolean(state.preferences?.sidebarCollapsed);
    button.textContent = isRailButton
      ? (collapsed ? "Expand" : "Collapse")
      : (collapsed ? "Show Sidebar" : "Hide Sidebar");
  });
}

function renderFrontline(payload, workspace) {
  const dockedCount = sortDockedWindows(workspace).length;
  const externalCount = sortExternalWindows(workspace).length;
  const featuredWatchlist = [...payload.watchlist]
    .sort((left, right) => Math.abs(right.change_pct) - Math.abs(left.change_pct))
    .slice(0, state.preferences?.compactFrontline ? 4 : 5);
  const realizedPnl = payload.positions.reduce((sum, item) => sum + item.pnl, 0);
  const providerSpend = payload.providers.reduce((sum, item) => sum + item.monthly_cost, 0);
  const runningAnalytics = payload.analytics.filter((item) => item.status !== "Complete").length;

  byId("frontline-heading").textContent = workspace.name;
  byId("frontline-summary").textContent = `${workspace.description} Last sync ${payload.meta.last_sync}.`;
  byId("market-pulse").innerHTML = `
    <span class="status-pill">${escapeHtml(workspace.kind)}</span>
    <span class="status-pill">${escapeHtml(workspace.focus)}</span>
    <span class="status-pill">${escapeHtml(workspace.status)}</span>
    <span class="status-pill">${dockedCount} docked / ${externalCount} popped</span>
  `;

  byId("frontline-grid").innerHTML = `
    <article class="frontline-summary-card">
      <p class="section-label">Session Pulse</p>
      <div class="frontline-summary-grid">
        <div>
          <strong>${escapeHtml(payload.meta.connection)}</strong>
          <span>Connection</span>
        </div>
        <div>
          <strong>${currency(providerSpend)}</strong>
          <span>Provider spend</span>
        </div>
        <div>
          <strong>${currency(realizedPnl)}</strong>
          <span>Open P/L</span>
        </div>
        <div>
          <strong>${String(runningAnalytics).padStart(2, "0")}</strong>
          <span>Live queues</span>
        </div>
      </div>
    </article>
    ${featuredWatchlist.map((item) => `
      <article class="frontline-ticker-card">
        <div class="frontline-ticker-top">
          <div>
            <strong>${escapeHtml(item.symbol)}</strong>
            <span>${escapeHtml(item.name)}</span>
          </div>
          <span class="pill">${escapeHtml(item.asset_class)}</span>
        </div>
        ${sparkline(item.spark)}
        <div class="frontline-ticker-bottom">
          <strong>${formatMarketPrice(item)}</strong>
          <span class="${item.change_pct >= 0 ? "positive" : "negative"}">${percent(item.change_pct)}</span>
        </div>
        <p>${escapeHtml(item.note)}</p>
      </article>
    `).join("")}
  `;

  byId("workspace-title").textContent = workspace.name;
  byId("workspace-summary").textContent = workspace.description;
  byId("connection-pill").textContent = `${payload.meta.connection} / ${payload.meta.profile}`;
  byId("workspace-pane-list").innerHTML = workspace.panes
    .map((pane) => `<span class="pane-pill">${escapeHtml(pane)}</span>`)
    .join("");

  byId("menu-status").innerHTML = `
    <span class="status-pill">drag to reorder</span>
    <span class="status-pill">real popup windows</span>
    <span>${dockedCount} docked, ${externalCount} popped out</span>
  `;
}

function renderSettingsDialog() {
  const modal = byId("settings-modal");
  modal.hidden = !state.settingsOpen;
  modal.classList.toggle("is-open", state.settingsOpen);
  byId("settings-identity").innerHTML = `
    <div class="settings-identity-mark">A</div>
    <div>
      <strong>${escapeHtml(state.preferences?.profileDisplayName || state.dashboard.settings.profile_name)}</strong>
      <span>${escapeHtml(state.preferences?.profileEmail || "user@local.attas")}</span>
      <p>${escapeHtml(state.preferences?.profileDesk || state.dashboard.meta.profile)}</p>
    </div>
  `;
  byId("settings-tab-list").innerHTML = SETTINGS_TABS.map((tab) => `
    <button
      type="button"
      class="settings-tab ${state.settingsTab === tab.id ? "is-active" : ""}"
      data-settings-tab="${escapeHtml(tab.id)}"
    >
      <strong>${escapeHtml(tab.label)}</strong>
      <span>${escapeHtml(tab.detail)}</span>
    </button>
  `).join("");
  byId("settings-summary").innerHTML = `
    <div class="settings-summary-stack">
      <div>
        <strong>Plan</strong>
        <p>${escapeHtml(state.preferences?.paymentPlan || state.dashboard.settings.billing_plan)}</p>
      </div>
      <div>
        <strong>Keys</strong>
        <p>${countConfiguredKeys()} of 4 configured</p>
      </div>
      <div>
        <strong>Connection</strong>
        <p>${escapeHtml(state.dashboard.meta.connection)}</p>
      </div>
      <div>
        <strong>Storage</strong>
        <p>${escapeHtml(state.preferences?.connectionStorage || state.dashboard.settings.active_storage)}</p>
      </div>
    </div>
  `;
  byId("settings-panel-content").innerHTML = renderSettingsPanelContent();
}

function renderSettingsPanelContent() {
  const workspaceOptions = state.workspaces.map((workspace) => `
    <option value="${escapeHtml(workspace.id)}" ${state.preferences?.defaultWorkspaceId === workspace.id ? "selected" : ""}>${escapeHtml(workspace.name)}</option>
  `).join("");
  const filterOptions = FILTER_OPTIONS.map((filter) => `
    <option value="${escapeHtml(filter)}" ${state.preferences?.defaultFilter === filter ? "selected" : ""}>${escapeHtml(filter === "All" ? "All Markets" : filter)}</option>
  `).join("");

  if (state.settingsTab === "profile") {
    return `
      <section class="settings-section">
        <div class="settings-section-head">
          <div>
            <p class="section-label">User Profile</p>
            <h3>Identity and Workspace Defaults</h3>
          </div>
          <span class="window-pill">Saved locally</span>
        </div>
        <div class="settings-fields">
          <label class="settings-field">
            <span>Display Name</span>
            <input type="text" value="${escapeHtml(state.preferences?.profileDisplayName || "")}" data-setting-field="profileDisplayName">
          </label>
          <label class="settings-field">
            <span>Email</span>
            <input type="email" value="${escapeHtml(state.preferences?.profileEmail || "")}" data-setting-field="profileEmail">
          </label>
          <label class="settings-field">
            <span>Desk Label</span>
            <input type="text" value="${escapeHtml(state.preferences?.profileDesk || "")}" data-setting-field="profileDesk">
          </label>
          <label class="settings-field">
            <span>Timezone</span>
            <input type="text" value="${escapeHtml(state.preferences?.profileTimezone || "")}" data-setting-field="profileTimezone">
          </label>
        </div>
      </section>
      <section class="settings-section">
        <p class="section-label">Appearance</p>
        <div class="theme-switcher" id="settings-theme-switcher">
          ${THEME_OPTIONS.map((option) => `
            <button
              type="button"
              class="theme-chip ${state.preferences?.theme === option.id ? "is-active" : ""}"
              data-theme-target="${escapeHtml(option.id)}"
            >
              ${escapeHtml(option.label)}
            </button>
          `).join("")}
        </div>
      </section>
    `;
  }

  if (state.settingsTab === "payment") {
    return `
      <section class="settings-section">
        <div class="settings-section-head">
          <div>
            <p class="section-label">Payment</p>
            <h3>Billing and Spending Controls</h3>
          </div>
          <span class="window-pill">${escapeHtml(state.dashboard.meta.connection)}</span>
        </div>
        <div class="settings-fields">
          <label class="settings-field">
            <span>Plan</span>
            <input type="text" value="${escapeHtml(state.preferences?.paymentPlan || "")}" data-setting-field="paymentPlan">
          </label>
          <label class="settings-field">
            <span>Billing Email</span>
            <input type="email" value="${escapeHtml(state.preferences?.paymentEmail || "")}" data-setting-field="paymentEmail">
          </label>
          <label class="settings-field">
            <span>Monthly Budget (USD)</span>
            <input type="number" min="0" step="1" value="${escapeHtml(state.preferences?.paymentBudget || "0")}" data-setting-field="paymentBudget">
          </label>
          <label class="settings-field">
            <span>Current Spend</span>
            <input type="text" value="${escapeHtml(currency(state.dashboard.providers.reduce((sum, item) => sum + item.monthly_cost, 0)))}" readonly>
          </label>
        </div>
        <div class="settings-toggles">
          <label class="settings-toggle">
            <input type="checkbox" ${state.preferences?.paymentAutopay ? "checked" : ""} data-setting-field="paymentAutopay">
            <span>Enable automatic renewal</span>
          </label>
        </div>
      </section>
    `;
  }

  if (state.settingsTab === "api_keys") {
    return `
      <section class="settings-section">
        <div class="settings-section-head">
          <div>
            <p class="section-label">API Keys</p>
            <h3>Provider Credentials</h3>
          </div>
          <span class="window-pill">${countConfiguredKeys()} configured</span>
        </div>
        <div class="settings-key-grid">
          <label class="settings-field settings-field--secret">
            <span>OpenAI</span>
            <input type="password" value="${escapeHtml(state.preferences?.apiKeyOpenAI || "")}" placeholder="sk-..." data-setting-field="apiKeyOpenAI">
            <p>${escapeHtml(maskSecret(state.preferences?.apiKeyOpenAI || ""))}</p>
          </label>
          <label class="settings-field settings-field--secret">
            <span>Finnhub</span>
            <input type="password" value="${escapeHtml(state.preferences?.apiKeyFinnhub || "")}" placeholder="Enter Finnhub key" data-setting-field="apiKeyFinnhub">
            <p>${escapeHtml(maskSecret(state.preferences?.apiKeyFinnhub || ""))}</p>
          </label>
          <label class="settings-field settings-field--secret">
            <span>Alpha Vantage</span>
            <input type="password" value="${escapeHtml(state.preferences?.apiKeyAlphaVantage || "")}" placeholder="Enter Alpha Vantage key" data-setting-field="apiKeyAlphaVantage">
            <p>${escapeHtml(maskSecret(state.preferences?.apiKeyAlphaVantage || ""))}</p>
          </label>
          <label class="settings-field settings-field--secret">
            <span>Broker Token</span>
            <input type="password" value="${escapeHtml(state.preferences?.apiKeyBroker || "")}" placeholder="Simulation broker token" data-setting-field="apiKeyBroker">
            <p>${escapeHtml(maskSecret(state.preferences?.apiKeyBroker || ""))}</p>
          </label>
        </div>
        <div class="settings-note-card">
          <strong>Local-only storage</strong>
          <p>Keys are stored in this browser only and are not sent to Plaza or any remote settings service.</p>
        </div>
      </section>
    `;
  }

  return `
    <section class="settings-section">
      <div class="settings-section-head">
        <div>
          <p class="section-label">Connection</p>
          <h3>Local Runtime and Workspace Routing</h3>
        </div>
        <span class="window-pill">${escapeHtml(state.dashboard.meta.mode)}</span>
      </div>
      <div class="settings-fields">
        <label class="settings-field">
          <span>Connection Mode</span>
          <input type="text" value="${escapeHtml(state.preferences?.connectionMode || "")}" data-setting-field="connectionMode">
        </label>
        <label class="settings-field">
          <span>Local Host</span>
          <input type="text" value="${escapeHtml(state.preferences?.connectionHost || "")}" data-setting-field="connectionHost">
        </label>
        <label class="settings-field">
          <span>Default Workspace</span>
          <select data-setting-field="defaultWorkspaceId">${workspaceOptions}</select>
        </label>
        <label class="settings-field">
          <span>Default Market Filter</span>
          <select data-setting-field="defaultFilter">${filterOptions}</select>
        </label>
        <label class="settings-field">
          <span>Storage Backend</span>
          <input type="text" value="${escapeHtml(state.preferences?.connectionStorage || "")}" data-setting-field="connectionStorage">
        </label>
        <label class="settings-field">
          <span>Connection Status</span>
          <input type="text" value="${escapeHtml(state.dashboard.meta.connection)}" readonly>
        </label>
      </div>
      <div class="settings-toggles">
        <label class="settings-toggle">
          <input type="checkbox" ${state.preferences?.sidebarCollapsed ? "checked" : ""} data-setting-field="sidebarCollapsed">
          <span>Collapse left sidebar by default</span>
        </label>
        <label class="settings-toggle">
          <input type="checkbox" ${state.preferences?.compactFrontline ? "checked" : ""} data-setting-field="compactFrontline">
          <span>Use compact market frontline cards</span>
        </label>
      </div>
    </section>
  `;
}

function renderWorkspaceSidebar() {
  const activeWorkspace = getActiveWorkspace();

  byId("workspace-list").innerHTML = state.workspaces
    .map((workspace) => {
      const dockedCount = sortDockedWindows(workspace).length;
      const externalCount = sortExternalWindows(workspace).length;
      return `
        <article class="workspace-switch-card ${workspace.id === activeWorkspace.id ? "is-active" : ""}">
          <div class="workspace-card-top">
            <div>
              <strong>${escapeHtml(workspace.name)}</strong>
              <p>${escapeHtml(workspace.kind)}</p>
            </div>
            <span class="pill">${escapeHtml(workspace.status)}</span>
          </div>
          <p>${escapeHtml(workspace.description)}</p>
          <div class="workspace-switch-meta">
            <span>Focus</span><span>${escapeHtml(workspace.focus)}</span>
            <span>Windows</span><span>${dockedCount} docked / ${externalCount} popped out</span>
          </div>
          <button type="button" class="workspace-launch ${workspace.id === activeWorkspace.id ? "is-active" : ""}" data-workspace-switch="${workspace.id}">
            ${workspace.id === activeWorkspace.id ? "Active Workspace" : "Open Workspace"}
          </button>
        </article>
      `;
    })
    .join("");

  byId("activity-list").innerHTML = state.dashboard.activity
    .map((item) => `
      <article class="activity-card">
        <div class="activity-top">
          <strong>${escapeHtml(item.headline)}</strong>
          <span class="pill">${escapeHtml(item.time)}</span>
        </div>
        <p>${escapeHtml(item.detail)}</p>
      </article>
    `)
    .join("");
}

function getBrowserCatalog() {
  return state.dashboard.browser || { menus: [], bookmarks: [], views: [] };
}

function getBrowserView(windowItem) {
  const browser = getBrowserCatalog();
  const view =
    browser.views.find((item) => item.id === windowItem.selectedBrowserViewId) ||
    browser.views.find((item) => item.id === browser.default_view) ||
    browser.views[0] ||
    null;

  if (view && windowItem.selectedBrowserViewId !== view.id) {
    windowItem.selectedBrowserViewId = view.id;
  }

  return view;
}

function getBrowserSymbol(windowItem, view) {
  if (!view) {
    return null;
  }

  const selected =
    view.symbols.find((item) => item.id === windowItem.selectedSymbolId) ||
    view.symbols[0] ||
    null;

  if (selected && windowItem.selectedSymbolId !== selected.id) {
    windowItem.selectedSymbolId = selected.id;
  }

  return selected;
}

function renderBrowserTable(columns, rows, classes = "") {
  return `
    <div class="browser-table-shell ${classes}">
      <table class="browser-table">
        <thead>
          <tr>
            ${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              ${columns.map((column) => {
                const rawValue = row[column.id] ?? "";
                const stringValue = String(rawValue);
                const className =
                  stringValue.startsWith("+") ? "positive" :
                    stringValue.startsWith("-") || stringValue.startsWith("▼") ? "negative" :
                      "";
                return `<td class="${className}">${escapeHtml(stringValue)}</td>`;
              }).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderBrowserPane(windowItem, viewId, paneId, label, detail, body, layout) {
  return `
    <article
      class="browser-terminal-panel browser-terminal-panel--${escapeHtml(paneId)}"
      data-browser-pane-window-id="${escapeHtml(windowItem.id)}"
      data-browser-pane-view-id="${escapeHtml(viewId)}"
      data-browser-pane-id="${escapeHtml(paneId)}"
      style="left:${layout.x}%; top:${layout.y}%; width:${layout.w}%; height:${layout.h}%; z-index:${layout.z};"
    >
      <div
        class="browser-pane-bar"
        data-browser-pane-handle="${escapeHtml(windowItem.id)}"
        data-pane-id="${escapeHtml(paneId)}"
        title="Drag pane"
      >
        <div class="browser-pane-bar-copy">
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(detail)}</span>
        </div>
        <span class="browser-pane-hint">Drag</span>
      </div>
      <div class="browser-terminal-panel-body">
        ${body}
      </div>
      <button
        type="button"
        class="browser-pane-resize"
        data-browser-pane-resize="${escapeHtml(windowItem.id)}"
        data-pane-id="${escapeHtml(paneId)}"
        aria-label="Resize ${escapeHtml(label)} pane"
        title="Resize pane"
      ></button>
    </article>
  `;
}

function renderBrowserWindow(windowItem) {
  const browser = getBrowserCatalog();
  const searchQuery = windowItem.searchQuery || "";
  const selectedView = getBrowserView(windowItem);
  const selectedSymbol = getBrowserSymbol(windowItem, selectedView);

  const filteredBookmarks = browser.bookmarks.filter((bookmark) => matchesQuery(searchQuery, [
    bookmark.label,
    bookmark.url,
    bookmark.summary,
    bookmark.category,
    bookmark.view_id || "",
  ]));
  const selectedBookmark =
    browser.bookmarks.find((bookmark) => bookmark.id === windowItem.selectedBookmarkId) ||
    filteredBookmarks[0] ||
    browser.bookmarks[0] ||
    null;

  if (selectedBookmark && windowItem.selectedBookmarkId !== selectedBookmark.id) {
    windowItem.selectedBookmarkId = selectedBookmark.id;
  }

  const filteredSymbols = (selectedView?.symbols || []).filter((item) => matchesQuery(searchQuery, [
    item.ticker,
    item.name,
    item.note,
    item.story_title,
    item.story_summary,
  ]));
  const visibleSymbols = filteredSymbols.length > 0 ? filteredSymbols : selectedView?.symbols || [];
  const activeSymbol =
    visibleSymbols.find((item) => item.id === windowItem.selectedSymbolId) ||
    selectedSymbol ||
    visibleSymbols[0] ||
    null;

  if (activeSymbol && windowItem.selectedSymbolId !== activeSymbol.id) {
    windowItem.selectedSymbolId = activeSymbol.id;
  }

  const filteredFeed = (selectedView?.feed || []).filter((item) => matchesQuery(searchQuery, [
    item.source,
    item.headline,
  ]));
  const visibleFeed = filteredFeed.length > 0 ? filteredFeed : selectedView?.feed || [];

  if (!selectedView || !activeSymbol) {
    return `
      <div class="browser-frame">
        <div class="browser-empty">
          <strong>Browser data unavailable</strong>
          <p class="muted">This browser window needs a local asset view definition before it can render.</p>
        </div>
      </div>
    `;
  }

  const paneLayoutState = getBrowserPaneLayoutState(windowItem, selectedView.id);
  const paneBodies = {
    monitor: `
      <div class="window-subhead">
        <div>
          <p class="section-label">${escapeHtml(selectedView.market_label)}</p>
          <strong>${escapeHtml(selectedView.monitor_title)}</strong>
        </div>
        <span class="window-pill">${escapeHtml(selectedView.subtitle)}</span>
      </div>
      ${renderBrowserTable(selectedView.monitor_columns, selectedView.monitor_rows, "browser-table-shell--monitor")}
    `,
    feed: `
      <div class="window-subhead">
        <div>
          <p class="section-label">Most Recent</p>
          <strong>News Feed</strong>
        </div>
        <span class="window-pill">${visibleFeed.length} items</span>
      </div>
      <div class="browser-news-list">
        ${visibleFeed.map((item) => `
          <article class="browser-news-item">
            <span class="browser-news-time">${escapeHtml(item.time)}</span>
            <div>
              <span class="browser-news-source">${escapeHtml(item.source)}</span>
              <p>${escapeHtml(item.headline)}</p>
            </div>
          </article>
        `).join("")}
      </div>
    `,
    story: `
      <div class="browser-story-card">
        <div class="browser-story-meta">
          <span class="pill">${escapeHtml(activeSymbol.ticker)}</span>
          <span class="browser-url">${escapeHtml(selectedBookmark?.url || "attas://workspace/browser")}</span>
        </div>
        <h3>${escapeHtml(activeSymbol.story_title)}</h3>
        <p class="muted">${escapeHtml(activeSymbol.story_summary)}</p>
        <div class="browser-quote-strip">
          <div>
            <span class="browser-quote-label">Last</span>
            <strong>${escapeHtml(activeSymbol.display_price)}</strong>
          </div>
          <div>
            <span class="browser-quote-label">Bid/Ask</span>
            <strong>${escapeHtml(activeSymbol.bid)} / ${escapeHtml(activeSymbol.ask)}</strong>
          </div>
          <div>
            <span class="browser-quote-label">Move</span>
            <strong class="${activeSymbol.change_pct >= 0 ? "positive" : "negative"}">${percent(activeSymbol.change_pct)}</strong>
          </div>
        </div>
        <ul class="browser-story-points">
          ${activeSymbol.story_points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
        </ul>
      </div>
    `,
    tool: `
      <div class="window-subhead">
        <div>
          <p class="section-label">Calculator</p>
          <strong>${escapeHtml(activeSymbol.tool_title)}</strong>
        </div>
        <span class="window-pill">${escapeHtml(activeSymbol.ticker)}</span>
      </div>
      <div class="browser-metric-grid">
        ${activeSymbol.tool_metrics.map((metric) => `
          <div class="browser-metric-card">
            <span>${escapeHtml(metric.label)}</span>
            <strong>${escapeHtml(metric.value)}</strong>
          </div>
        `).join("")}
      </div>
      ${renderBrowserTable(
        [
          { id: "tenor", label: "Term" },
          { id: "value_date", label: "Reference" },
          { id: "swap_points", label: "Value" },
          { id: "outright", label: "Comment" },
        ],
        activeSymbol.tool_rows,
        "browser-table-shell--tool",
      )}
    `,
    tape: `
      <div class="window-subhead">
        <div>
          <p class="section-label">Trade Log</p>
          <strong>${escapeHtml(activeSymbol.tape_title)}</strong>
        </div>
        <span class="window-pill">${escapeHtml(activeSymbol.tape_rows.length)} prints</span>
      </div>
      ${renderBrowserTable(activeSymbol.tape_columns, activeSymbol.tape_rows, "browser-table-shell--tape")}
    `,
  };

  return `
    <div class="browser-frame browser-frame--${escapeHtml(selectedView.id)}">
      <div class="browser-chrome">
        <div class="browser-brandline">
          <span class="browser-app-badge">${escapeHtml(browser.workspace_label || "WS")}</span>
          <span class="browser-layout-title">${escapeHtml(browser.layout_name || browser.title)}</span>
        </div>
        <div class="browser-actions">
          <span class="window-pill">${escapeHtml(selectedView.market_label)}</span>
          <span class="window-pill">${escapeHtml(selectedView.workspace_tag)}</span>
        </div>
      </div>
      <div class="browser-menu-strip">
        ${browser.menus.map((menu) => `<span class="browser-menu-item">${escapeHtml(menu)}</span>`).join("")}
      </div>
      <div class="browser-toolbar">
        <div class="browser-nav-cluster">
          <span class="browser-nav-button">⌂</span>
          <span class="browser-nav-button">‹</span>
          <span class="browser-nav-button">›</span>
        </div>
        <input
          type="search"
          class="browser-search"
          data-browser-search="${escapeHtml(windowItem.id)}"
          value="${escapeHtml(searchQuery)}"
          placeholder="${escapeHtml(selectedView.symbol_prompt || "Search workspace")}"
        >
        <div class="browser-toolbar-actions">
          <span class="browser-view-title">${escapeHtml(browser.title)}</span>
          <button type="button" class="window-command" data-browser-reset-layout="${escapeHtml(windowItem.id)}">Reset Layout</button>
          <button type="button" class="window-command" data-browser-clear="${escapeHtml(windowItem.id)}">Clear</button>
        </div>
      </div>
      <div class="browser-view-strip">
        ${browser.views.map((view) => `
          <button
            type="button"
            class="browser-view-button ${view.id === selectedView.id ? "is-active" : ""}"
            data-browser-view="${escapeHtml(windowItem.id)}"
            data-view-id="${escapeHtml(view.id)}"
          >
            ${escapeHtml(view.label)}
          </button>
        `).join("")}
      </div>
      <div class="browser-shell">
        <aside class="browser-left-rail">
          <div class="bookmark-list">
            <p class="section-label">Bookmarks</p>
            <div class="browser-bookmarks">
              ${filteredBookmarks.map((bookmark) => `
                <button
                  type="button"
                  class="bookmark-button ${selectedBookmark && selectedBookmark.id === bookmark.id ? "is-active" : ""}"
                  data-browser-bookmark="${escapeHtml(windowItem.id)}"
                  data-bookmark-id="${escapeHtml(bookmark.id)}"
                >
                  <strong>${escapeHtml(bookmark.label)}</strong>
                  <span>${escapeHtml(bookmark.url)}</span>
                </button>
              `).join("")}
            </div>
          </div>
          <div class="bookmark-list">
            <p class="section-label">${escapeHtml(selectedView.label)} Symbols</p>
            <div class="browser-symbol-list">
              ${visibleSymbols.map((symbol) => `
              <button
                type="button"
                class="browser-symbol-button ${activeSymbol && activeSymbol.id === symbol.id ? "is-active" : ""}"
                data-browser-symbol="${escapeHtml(windowItem.id)}"
                data-symbol-id="${escapeHtml(symbol.id)}"
              >
                <strong>${escapeHtml(symbol.ticker)}</strong>
                <span>${escapeHtml(symbol.name)}</span>
                <span class="${symbol.change_pct >= 0 ? "positive" : "negative"}">${percent(symbol.change_pct)}</span>
              </button>
              `).join("")}
            </div>
          </div>
        </aside>
        <div class="browser-terminal-grid browser-terminal-grid--${escapeHtml(selectedView.id)}" data-browser-pane-canvas="${escapeHtml(windowItem.id)}" data-browser-pane-view-id="${escapeHtml(selectedView.id)}">
          ${renderBrowserPane(
            windowItem,
            selectedView.id,
            "monitor",
            "Monitor",
            selectedView.monitor_title,
            paneBodies.monitor,
            paneLayoutState.panes.monitor,
          )}
          ${renderBrowserPane(
            windowItem,
            selectedView.id,
            "feed",
            "Feed",
            `${visibleFeed.length} live headlines`,
            paneBodies.feed,
            paneLayoutState.panes.feed,
          )}
          ${renderBrowserPane(
            windowItem,
            selectedView.id,
            "story",
            "Story",
            activeSymbol.ticker,
            paneBodies.story,
            paneLayoutState.panes.story,
          )}
          ${renderBrowserPane(
            windowItem,
            selectedView.id,
            "tool",
            "Tool",
            activeSymbol.tool_title,
            paneBodies.tool,
            paneLayoutState.panes.tool,
          )}
          ${renderBrowserPane(
            windowItem,
            selectedView.id,
            "tape",
            "Tape",
            activeSymbol.tape_title,
            paneBodies.tape,
            paneLayoutState.panes.tape,
          )}
        </div>
      </div>
    </div>
  `;
}

function renderWatchlistWindow() {
  const watchlist = state.activeFilter === "All"
    ? state.dashboard.watchlist
    : state.dashboard.watchlist.filter((item) => item.asset_class === state.activeFilter);

  return `
    <div class="watchlist-shell">
      <div class="window-subhead">
        <p class="section-label">Docked market board</p>
        <div class="segmented">
          ${FILTER_OPTIONS.map((filter) => `
            <button type="button" class="segment ${state.activeFilter === filter ? "is-active" : ""}" data-filter="${escapeHtml(filter)}">
              ${escapeHtml(filter === "Stock" ? "Stocks" : filter)}
            </button>
          `).join("")}
        </div>
      </div>
      <div class="compact-grid">
        ${watchlist.map((item) => `
          <article class="watch-card">
            <div class="watch-top">
              <div>
                <span class="watch-symbol">${escapeHtml(item.symbol)}</span>
                <span class="watch-name">${escapeHtml(item.name)}</span>
              </div>
              <span class="pill">${escapeHtml(item.asset_class)}</span>
            </div>
            ${sparkline(item.spark)}
            <div class="watch-bottom">
              <span class="watch-price">${formatMarketPrice(item)}</span>
              <span class="watch-price ${item.change_pct >= 0 ? "positive" : "negative"}">${percent(item.change_pct)}</span>
            </div>
            <p class="muted">${escapeHtml(item.note)}</p>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function handleBrowserPanePointerDown(targetDocument, event) {
  const resizeHandle = event.target.closest("[data-browser-pane-resize]");
  const dragHandle = event.target.closest("[data-browser-pane-handle]");
  const trigger = resizeHandle || dragHandle;
  if (!trigger || event.button !== 0) {
    return;
  }

  const paneElement = trigger.closest("[data-browser-pane-id]");
  const canvasElement = trigger.closest("[data-browser-pane-canvas]");
  if (!paneElement || !canvasElement) {
    return;
  }

  const windowId = paneElement.dataset.browserPaneWindowId;
  const viewId = paneElement.dataset.browserPaneViewId;
  const paneId = paneElement.dataset.browserPaneId;
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const layoutState = getBrowserPaneLayoutState(located.windowItem, viewId);
  const layout = layoutState.panes[paneId];
  if (!layout) {
    return;
  }

  focusBrowserPane(located.windowItem, viewId, paneId);
  applyBrowserPaneStyle(paneElement, layout);

  const pointerTarget = resizeHandle || dragHandle;
  if (pointerTarget.setPointerCapture) {
    pointerTarget.setPointerCapture(event.pointerId);
  }

  state.paneInteraction = {
    documentRef: targetDocument,
    windowId,
    viewId,
    paneId,
    mode: resizeHandle ? "resize" : "drag",
    startX: event.clientX,
    startY: event.clientY,
    canvasRect: canvasElement.getBoundingClientRect(),
    startLayout: { ...layout },
    paneElement,
  };
  paneElement.classList.add("is-interacting");
  targetDocument.body.classList.add("is-pane-interacting");
  event.preventDefault();
}

function handleBrowserPanePointerMove(targetDocument, event) {
  if (!state.paneInteraction || state.paneInteraction.documentRef !== targetDocument) {
    return;
  }

  const interaction = state.paneInteraction;
  const located = findWindowById(interaction.windowId);
  if (!located) {
    return;
  }

  const layoutState = getBrowserPaneLayoutState(located.windowItem, interaction.viewId);
  const layout = layoutState.panes[interaction.paneId];
  const deltaX = ((event.clientX - interaction.startX) / interaction.canvasRect.width) * 100;
  const deltaY = ((event.clientY - interaction.startY) / interaction.canvasRect.height) * 100;

  if (interaction.mode === "drag") {
    layout.x = interaction.startLayout.x + deltaX;
    layout.y = interaction.startLayout.y + deltaY;
  } else {
    layout.w = interaction.startLayout.w + deltaX;
    layout.h = interaction.startLayout.h + deltaY;
  }

  normalizeBrowserPaneLayout(layout);
  applyBrowserPaneStyle(interaction.paneElement, layout);
  event.preventDefault();
}

function stopBrowserPaneInteraction(targetDocument, shouldRender = true) {
  if (!state.paneInteraction || state.paneInteraction.documentRef !== targetDocument) {
    return;
  }

  state.paneInteraction.paneElement?.classList.remove("is-interacting");
  targetDocument.body.classList.remove("is-pane-interacting");
  state.paneInteraction = null;

  if (shouldRender) {
    renderWindowSurfaces();
  }
}

function bindBrowserPaneInteractions(targetDocument) {
  if (targetDocument.__attasPaneBound) {
    return;
  }

  targetDocument.__attasPaneBound = true;

  targetDocument.addEventListener("pointerdown", (event) => {
    handleBrowserPanePointerDown(targetDocument, event);
  });

  targetDocument.addEventListener("pointermove", (event) => {
    handleBrowserPanePointerMove(targetDocument, event);
  });

  targetDocument.addEventListener("pointerup", () => {
    stopBrowserPaneInteraction(targetDocument, true);
  });

  targetDocument.addEventListener("pointercancel", () => {
    stopBrowserPaneInteraction(targetDocument, true);
  });
}

function renderPositionsWindow() {
  return `
    <div class="compact-table-shell">
      <table class="compact-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Qty</th>
            <th>Avg</th>
            <th>Last</th>
            <th>P/L</th>
            <th>Alloc</th>
            <th>Thesis</th>
          </tr>
        </thead>
        <tbody>
          ${state.dashboard.positions.map((item) => `
            <tr>
              <td><strong>${escapeHtml(item.symbol)}</strong></td>
              <td>${escapeHtml(item.quantity)}</td>
              <td>${currency(item.avg_cost)}</td>
              <td>${currency(item.last_price)}</td>
              <td class="${item.pnl >= 0 ? "positive" : "negative"}">${currency(item.pnl)}</td>
              <td>${item.allocation.toFixed(1)}%</td>
              <td class="muted">${escapeHtml(item.thesis)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderProvidersWindow() {
  return `
    <div class="provider-shell">
      <div class="compact-grid">
        ${state.dashboard.providers.map((item) => `
          <article class="compact-card">
            <div class="mini-row">
              <div>
                <strong>${escapeHtml(item.name)}</strong>
                <p>${escapeHtml(item.category)}</p>
              </div>
              <span class="pill">${escapeHtml(item.quality)}</span>
            </div>
            <div class="mini-ledger">
              <span>Coverage</span><span>${escapeHtml(item.coverage)}</span>
              <span>Latency</span><span>${escapeHtml(`${item.latency_ms} ms`)}</span>
              <span>Monthly</span><span>${currency(item.monthly_cost)}</span>
              <span>Reliability</span><span>${escapeHtml(item.reliability)}</span>
            </div>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function renderAnalyticsWindow() {
  return `
    <div class="analytics-shell">
      <div class="event-list">
        ${state.dashboard.analytics.map((item) => `
          <article class="compact-card">
            <div class="mini-row">
              <div>
                <strong>${escapeHtml(item.title)}</strong>
                <p>${escapeHtml(item.owner)}</p>
              </div>
              <span class="pill">${escapeHtml(item.status)}</span>
            </div>
            <div class="mini-ledger">
              <span>Schedule</span><span>${escapeHtml(item.schedule)}</span>
              <span>Runtime</span><span>${escapeHtml(item.runtime)}</span>
            </div>
            <p>${escapeHtml(item.impact)}</p>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function renderTransactionsWindow() {
  return `
    <div class="transactions-shell">
      <article class="compact-panel">
        <div class="window-subhead">
          <p class="section-label">Transactions</p>
          <span class="window-pill">${state.dashboard.transactions.length} active</span>
        </div>
        <div class="event-list">
          ${state.dashboard.transactions.map((item) => `
            <article class="compact-card">
              <div class="mini-row">
                <div>
                  <strong>${escapeHtml(`${item.side} ${item.symbol}`)}</strong>
                  <p>${escapeHtml(`${item.quantity} units via ${item.venue}`)}</p>
                </div>
                <span class="pill">${escapeHtml(item.status)}</span>
              </div>
              <p>${escapeHtml(item.time)}</p>
            </article>
          `).join("")}
        </div>
      </article>
      <article class="compact-panel">
        <div class="window-subhead">
          <p class="section-label">Relay</p>
          <span class="window-pill">${state.dashboard.activity.length} events</span>
        </div>
        <div class="event-list">
          ${state.dashboard.activity.slice(0, 3).map((item) => `
            <article class="compact-card">
              <div class="mini-row">
                <strong>${escapeHtml(item.headline)}</strong>
                <span class="pill">${escapeHtml(item.time)}</span>
              </div>
              <p>${escapeHtml(item.detail)}</p>
            </article>
          `).join("")}
        </div>
      </article>
    </div>
  `;
}

function renderWindowBody(windowItem) {
  switch (windowItem.type) {
    case "browser":
      return renderBrowserWindow(windowItem);
    case "watchlist":
      return renderWatchlistWindow();
    case "positions":
      return renderPositionsWindow();
    case "providers":
      return renderProvidersWindow();
    case "analytics":
      return renderAnalyticsWindow();
    case "transactions":
      return renderTransactionsWindow();
    default:
      return `<p class="muted">Unknown window type.</p>`;
  }
}

function windowModeCommand(windowItem) {
  return windowItem.mode === "docked"
    ? { action: "popout", label: "Pop Out" }
    : { action: "dock", label: "Dock Back" };
}

function renderWindow(windowItem) {
  const modeCommand = windowModeCommand(windowItem);
  const body = renderWindowBody(windowItem);

  return `
    <article
      class="workspace-window workspace-window--${escapeHtml(windowItem.type)} workspace-window--docked"
      data-window-id="${escapeHtml(windowItem.id)}"
      data-dock-window-id="${escapeHtml(windowItem.id)}"
      draggable="true"
    >
      <header class="window-bar">
        <div class="window-signals" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="window-title">
          <strong>${escapeHtml(windowItem.title)}</strong>
          <span>${escapeHtml(windowItem.subtitle)}</span>
        </div>
        <div class="window-actions">
          <button type="button" class="window-command" data-window-action="${modeCommand.action}" data-window-id="${escapeHtml(windowItem.id)}">
            ${escapeHtml(modeCommand.label)}
          </button>
        </div>
      </header>
      <div class="window-body window-scroll">
        ${body}
      </div>
    </article>
  `;
}

function renderPopupWindow(windowItem) {
  const modeCommand = windowModeCommand(windowItem);
  return `
    <section class="popup-shell popup-shell--${escapeHtml(windowItem.type)}">
      <header class="popup-header">
        <div class="window-signals" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <div class="popup-title">
          <strong>${escapeHtml(windowItem.title)}</strong>
          <span>${escapeHtml(windowItem.subtitle)}</span>
        </div>
        <div class="popup-actions">
          <span class="status-pill">Independent Window</span>
          <button
            type="button"
            class="window-command"
            data-window-action="${escapeHtml(modeCommand.action)}"
            data-window-id="${escapeHtml(windowItem.id)}"
          >
            ${escapeHtml(modeCommand.label)}
          </button>
        </div>
      </header>
      <div class="popup-body ${windowItem.type === "browser" ? "popup-body--browser" : ""}">
        ${renderWindowBody(windowItem)}
      </div>
    </section>
  `;
}

function renderWorkspaceWindows() {
  const workspace = getActiveWorkspace();
  if (!workspace) {
    return;
  }

  byId("workspace-canvas").innerHTML = sortDockedWindows(workspace).map(renderWindow).join("");
  byId("floating-layer").innerHTML = "";
}

function getPopupBaseLeft() {
  return typeof window.screenX === "number" ? window.screenX : window.screenLeft || 40;
}

function getPopupBaseTop() {
  return typeof window.screenY === "number" ? window.screenY : window.screenTop || 40;
}

function getPopupGeometry(windowItem) {
  const width = windowItem.type === "browser" ? 1360 : 760;
  const height = windowItem.type === "browser" ? 900 : 620;
  return {
    width,
    height,
    left: Math.max(24, Math.round(windowItem.x || getPopupBaseLeft() + 120)),
    top: Math.max(24, Math.round(windowItem.y || getPopupBaseTop() + 120)),
  };
}

function getPopupFeatures(windowItem) {
  const geometry = getPopupGeometry(windowItem);
  return [
    "popup=yes",
    "resizable=yes",
    "scrollbars=yes",
    "toolbar=no",
    "menubar=no",
    "location=no",
    "status=no",
    `width=${geometry.width}`,
    `height=${geometry.height}`,
    `left=${geometry.left}`,
    `top=${geometry.top}`,
  ].join(",");
}

function getPopupDocumentMarkup(windowItem) {
  const stylesheetUrl = `${window.location.origin}/static/personal_agent.css?v=${encodeURIComponent(state.assetVersion)}`;
  const theme = escapeHtml(document.body.dataset.theme || "mercury");
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(windowItem.title)} · attas Personal Agent</title>
  <link rel="stylesheet" href="${stylesheetUrl}">
</head>
<body class="popup-window-body" data-theme="${theme}">
  <div class="backdrop"></div>
  <div class="grain"></div>
  <div class="popup-root" id="popup-root"></div>
</body>
</html>`;
}

function persistPopupBounds(windowId, popup) {
  const located = findWindowById(windowId);
  if (!located || !popup || popup.closed) {
    return;
  }

  if (typeof popup.screenX === "number") {
    located.windowItem.x = popup.screenX;
  }
  if (typeof popup.screenY === "number") {
    located.windowItem.y = popup.screenY;
  }
}

function bindPopupWindow(windowId, popup) {
  if (!popup || popup.__attasBound) {
    return;
  }

  popup.__attasBound = true;
  bindBrowserPaneInteractions(popup.document);

  popup.document.addEventListener("click", (event) => {
    const windowAction = event.target.closest("[data-window-action]");
    if (windowAction) {
      const targetWindowId = windowAction.dataset.windowId;
      if (windowAction.dataset.windowAction === "dock") {
        dockWindow(targetWindowId);
      }
      if (windowAction.dataset.windowAction === "popout") {
        popOutWindow(targetWindowId);
      }
      return;
    }

    const bookmarkButton = event.target.closest("[data-browser-bookmark]");
    if (bookmarkButton) {
      setBrowserBookmark(bookmarkButton.dataset.browserBookmark, bookmarkButton.dataset.bookmarkId);
      return;
    }

    const browserViewButton = event.target.closest("[data-browser-view]");
    if (browserViewButton) {
      setBrowserView(browserViewButton.dataset.browserView, browserViewButton.dataset.viewId);
      return;
    }

    const browserSymbolButton = event.target.closest("[data-browser-symbol]");
    if (browserSymbolButton) {
      setBrowserSymbol(browserSymbolButton.dataset.browserSymbol, browserSymbolButton.dataset.symbolId);
      return;
    }

    const clearButton = event.target.closest("[data-browser-clear]");
    if (clearButton) {
      clearBrowserSearch(clearButton.dataset.browserClear);
      return;
    }

    const resetLayoutButton = event.target.closest("[data-browser-reset-layout]");
    if (resetLayoutButton) {
      resetBrowserPaneLayout(resetLayoutButton.dataset.browserResetLayout);
      return;
    }

    const resetLayoutButton = event.target.closest("[data-browser-reset-layout]");
    if (resetLayoutButton) {
      resetBrowserPaneLayout(resetLayoutButton.dataset.browserResetLayout);
      return;
    }

    const filterButton = event.target.closest("[data-filter]");
    if (filterButton) {
      state.activeFilter = filterButton.dataset.filter;
      renderWindowSurfaces();
    }
  });

  popup.document.addEventListener("input", (event) => {
    const browserSearch = event.target.closest("[data-browser-search]");
    if (!browserSearch) {
      return;
    }

    syncBrowserSearch(
      browserSearch.dataset.browserSearch,
      browserSearch.value,
      browserSearch.selectionStart ?? browserSearch.value.length,
    );
  });

  popup.addEventListener("beforeunload", () => {
    if (popup.__attasClosing) {
      return;
    }

    stopBrowserPaneInteraction(popup.document, false);
    persistPopupBounds(windowId, popup);
    delete state.popupRefs[windowId];

    const located = findWindowById(windowId);
    if (!located || located.windowItem.mode !== "external") {
      return;
    }

    located.windowItem.mode = "docked";
    located.windowItem.order = sortDockedWindows(located.workspace).length;
    renderAll();
  });
}

function ensurePopupWindow(windowItem) {
  const existing = state.popupRefs[windowItem.id];
  if (existing && !existing.closed) {
    return existing;
  }

  const popup = window.open("", `attas_personal_agent_${windowItem.id}`, getPopupFeatures(windowItem));
  if (!popup) {
    return null;
  }

  popup.document.open();
  popup.document.write(getPopupDocumentMarkup(windowItem));
  popup.document.close();
  popup.document.title = `${windowItem.title} · attas Personal Agent`;

  bindPopupWindow(windowItem.id, popup);
  state.popupRefs[windowItem.id] = popup;
  popup.focus();
  return popup;
}

function closePopupWindow(windowId) {
  const popup = state.popupRefs[windowId];
  if (!popup) {
    return;
  }

  persistPopupBounds(windowId, popup);

  if (!popup.closed) {
    popup.__attasClosing = true;
    popup.close();
  }

  delete state.popupRefs[windowId];
}

function pruneClosedPopups() {
  let changed = false;

  Object.entries(state.popupRefs).forEach(([windowId, popup]) => {
    if (popup && !popup.closed) {
      return;
    }

    delete state.popupRefs[windowId];
    const located = findWindowById(windowId);
    if (!located || located.windowItem.mode !== "external") {
      return;
    }

    located.windowItem.mode = "docked";
    located.windowItem.order = sortDockedWindows(located.workspace).length;
    changed = true;
  });

  return changed;
}

function renderExternalPopups() {
  const liveExternalWindowIds = new Set();

  state.workspaces.forEach((workspace) => {
    sortExternalWindows(workspace).forEach((windowItem) => {
      const popup = ensurePopupWindow(windowItem);
      if (!popup) {
        return;
      }

      liveExternalWindowIds.add(windowItem.id);
      popup.document.body.dataset.theme = document.body.dataset.theme || "mercury";
      popup.document.title = `${windowItem.title} · attas Personal Agent`;
      persistPopupBounds(windowItem.id, popup);

      const root = popup.document.getElementById("popup-root");
      if (root) {
        root.innerHTML = renderPopupWindow(windowItem);
      }
    });
  });

  Object.keys(state.popupRefs).forEach((windowId) => {
    if (!liveExternalWindowIds.has(windowId)) {
      closePopupWindow(windowId);
    }
  });
}

function renderWindowSurfaces() {
  if (pruneClosedPopups()) {
    renderAll();
    return;
  }

  renderWorkspaceWindows();
  renderExternalPopups();
}

function focusBrowserSearch(windowId, caretPosition) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const scope = located.windowItem.mode === "external"
    ? state.popupRefs[windowId]?.document
    : document;

  const input = scope?.querySelector(`[data-browser-search="${windowId}"]`);
  if (!input) {
    return;
  }

  input.focus();
  const safePosition = Math.min(caretPosition ?? input.value.length, input.value.length);
  input.setSelectionRange(safePosition, safePosition);
}

function renderAll() {
  const payload = state.dashboard;
  if (!payload) {
    return;
  }

  pruneClosedPopups();

  const workspace = getActiveWorkspace();
  if (!workspace) {
    return;
  }

  renderSystemMeta(payload);
  renderCoverage(payload);
  renderSettings(payload);
  renderThemeState();
  renderSidebarState();
  renderMenuState();
  renderFrontline(payload, workspace);
  renderWorkspaceSidebar();
  renderSettingsDialog();
  renderWindowSurfaces();
}

function popOutWindow(windowId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const { workspace, windowItem } = located;
  if (windowItem.mode === "external") {
    state.popupRefs[windowId]?.focus();
    return;
  }

  const externalCount = sortExternalWindows(workspace).length;
  windowItem.mode = "external";
  windowItem.x = getPopupBaseLeft() + 120 + externalCount * 28;
  windowItem.y = getPopupBaseTop() + 120 + externalCount * 22;

  const popup = ensurePopupWindow(windowItem);
  if (!popup) {
    windowItem.mode = "docked";
    return;
  }

  renderAll();
  popup.focus();
}

function dockWindow(windowId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const { workspace, windowItem } = located;
  if (windowItem.mode === "docked") {
    return;
  }

  closePopupWindow(windowId);
  windowItem.mode = "docked";
  windowItem.order = sortDockedWindows(workspace).length;
  renderAll();
}

function reorderDockedWindows(workspace, sourceId, targetId = null) {
  const docked = sortDockedWindows(workspace);
  const sourceIndex = docked.findIndex((windowItem) => windowItem.id === sourceId);
  if (sourceIndex === -1) {
    return;
  }

  const [moved] = docked.splice(sourceIndex, 1);
  if (!targetId) {
    docked.push(moved);
  } else {
    const targetIndex = docked.findIndex((windowItem) => windowItem.id === targetId);
    docked.splice(targetIndex === -1 ? docked.length : targetIndex, 0, moved);
  }

  docked.forEach((windowItem, index) => {
    windowItem.order = index;
  });
}

function createNewWorkspace() {
  const workspaceNumber = String(state.nextWorkspaceIndex).padStart(2, "0");
  const workspace = {
    id: `workspace-${state.nextWorkspaceIndex}`,
    name: `New Workspace ${workspaceNumber}`,
    kind: "Scratch Workspace",
    focus: "Cross-asset sandbox",
    status: "Draft",
    owner: "attas-user",
    description: "A fresh workspace for arranging docked and popped-out browser, market, and routing windows.",
    panes: ["Browser", "Pulse tape", "Ledger", "Notes"],
    highlights: [
      "Workspace created from the File menu.",
      "Drag docked windows to reorder the workspace surface.",
    ],
    windows: createDefaultWindows(),
  };

  state.nextWorkspaceIndex += 1;
  state.workspaces.unshift(workspace);
  state.activeWorkspaceId = workspace.id;
  renderAll();
}

function createNewBrowserWindow() {
  const workspace = getActiveWorkspace();
  if (!workspace) {
    return;
  }

  const browser = getBrowserCatalog();
  const defaultView =
    browser.views.find((view) => view.id === browser.default_view) ||
    browser.views[0] ||
    { id: "browser", symbols: [] };
  const browserCount = workspace.windows.filter((windowItem) => windowItem.type === "browser").length + 1;
  const bookmarkId = browser.bookmarks[0]?.id || null;
  const newWindow = createWindow(
    "browser",
    browserCount === 1 ? "Research Browser" : `Research Browser ${browserCount}`,
    "Independent search and bookmarks surface",
    workspace.windows.length,
    {
      mode: "external",
      x: getPopupBaseLeft() + 140 + browserCount * 30,
      y: getPopupBaseTop() + 140 + browserCount * 24,
      searchQuery: browser.query || "",
      selectedBookmarkId: bookmarkId,
      selectedBrowserViewId: defaultView.id,
      selectedSymbolId: defaultView.symbols?.[0]?.id || null,
    },
  );

  workspace.windows.push(newWindow);
  const popup = ensurePopupWindow(newWindow);
  if (!popup) {
    newWindow.mode = "docked";
  }
  renderAll();
  popup?.focus();
}

function syncBrowserSearch(windowId, value, caretPosition) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  located.windowItem.searchQuery = value;
  renderWindowSurfaces();
  focusBrowserSearch(windowId, caretPosition ?? value.length);
}

function setBrowserBookmark(windowId, bookmarkId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const bookmark = getBrowserCatalog().bookmarks.find((item) => item.id === bookmarkId);
  located.windowItem.selectedBookmarkId = bookmarkId;
  if (bookmark?.view_id) {
    located.windowItem.selectedBrowserViewId = bookmark.view_id;
  }
  if (bookmark?.symbol_id) {
    located.windowItem.selectedSymbolId = bookmark.symbol_id;
  }
  renderWindowSurfaces();
}

function setBrowserView(windowId, viewId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  const browser = getBrowserCatalog();
  const view = browser.views.find((item) => item.id === viewId);
  if (!view) {
    return;
  }

  located.windowItem.selectedBrowserViewId = view.id;
  located.windowItem.selectedSymbolId = view.symbols?.[0]?.id || null;
  renderWindowSurfaces();
}

function setBrowserSymbol(windowId, symbolId) {
  const located = findWindowById(windowId);
  if (!located) {
    return;
  }

  located.windowItem.selectedSymbolId = symbolId;
  renderWindowSurfaces();
}

function clearBrowserSearch(windowId) {
  syncBrowserSearch(windowId, "", 0);
}

function toggleMenu(menuName) {
  state.menuOpen = state.menuOpen === menuName ? null : menuName;
  renderMenuState();
}

function clearDropTargets() {
  document.querySelectorAll(".workspace-window.is-drop-target").forEach((element) => {
    element.classList.remove("is-drop-target");
  });
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const sidebarToggle = event.target.closest("[data-sidebar-toggle]");
    if (sidebarToggle) {
      toggleSidebar();
      return;
    }

    const menuTrigger = event.target.closest("[data-menu-trigger]");
    if (menuTrigger) {
      toggleMenu(menuTrigger.dataset.menuTrigger);
      return;
    }

    const menuAction = event.target.closest("[data-menu-action]");
    if (menuAction) {
      state.menuOpen = null;
      renderMenuState();
      if (menuAction.dataset.menuAction === "new-workspace") {
        createNewWorkspace();
      }
      if (menuAction.dataset.menuAction === "new-browser-window") {
        createNewBrowserWindow();
      }
      if (menuAction.dataset.menuAction === "open-settings") {
        openSettings();
      }
      return;
    }

    const settingsClose = event.target.closest("[data-settings-close]");
    if (settingsClose) {
      closeSettings();
      return;
    }

    const settingsTab = event.target.closest("[data-settings-tab]");
    if (settingsTab) {
      setSettingsTab(settingsTab.dataset.settingsTab);
      return;
    }

    const settingsReset = event.target.closest("[data-settings-reset]");
    if (settingsReset) {
      resetPreferences();
      return;
    }

    const workspaceSwitch = event.target.closest("[data-workspace-switch]");
    if (workspaceSwitch) {
      state.activeWorkspaceId = workspaceSwitch.dataset.workspaceSwitch;
      renderAll();
      return;
    }

    const windowAction = event.target.closest("[data-window-action]");
    if (windowAction) {
      const windowId = windowAction.dataset.windowId;
      if (windowAction.dataset.windowAction === "popout") {
        popOutWindow(windowId);
      }
      if (windowAction.dataset.windowAction === "dock") {
        dockWindow(windowId);
      }
      return;
    }

    const bookmarkButton = event.target.closest("[data-browser-bookmark]");
    if (bookmarkButton) {
      setBrowserBookmark(bookmarkButton.dataset.browserBookmark, bookmarkButton.dataset.bookmarkId);
      return;
    }

    const browserViewButton = event.target.closest("[data-browser-view]");
    if (browserViewButton) {
      setBrowserView(browserViewButton.dataset.browserView, browserViewButton.dataset.viewId);
      return;
    }

    const browserSymbolButton = event.target.closest("[data-browser-symbol]");
    if (browserSymbolButton) {
      setBrowserSymbol(browserSymbolButton.dataset.browserSymbol, browserSymbolButton.dataset.symbolId);
      return;
    }

    const clearButton = event.target.closest("[data-browser-clear]");
    if (clearButton) {
      clearBrowserSearch(clearButton.dataset.browserClear);
      return;
    }

    const filterButton = event.target.closest("[data-filter]");
    if (filterButton) {
      state.activeFilter = filterButton.dataset.filter;
      renderWindowSurfaces();
      return;
    }

    const themeButton = event.target.closest("[data-theme-target]");
    if (themeButton) {
      updatePreference("theme", themeButton.dataset.themeTarget);
      return;
    }

    if (event.target.id === "settings-modal") {
      closeSettings();
      return;
    }

    if (!event.target.closest("[data-menu-group]")) {
      state.menuOpen = null;
      renderMenuState();
    }
  });

  document.addEventListener("input", (event) => {
    const browserSearch = event.target.closest("[data-browser-search]");
    if (!browserSearch) {
      return;
    }
    syncBrowserSearch(
      browserSearch.dataset.browserSearch,
      browserSearch.value,
      browserSearch.selectionStart ?? browserSearch.value.length,
    );
  });

  document.addEventListener("change", (event) => {
    const settingField = event.target.dataset.settingField;
    if (!settingField) {
      return;
    }

    const value = event.target.type === "checkbox"
      ? event.target.checked
      : event.target.value;
    updatePreference(settingField, value);
  });

  document.addEventListener("dragstart", (event) => {
    const dockWindow = event.target.closest("[data-dock-window-id]");
    if (!dockWindow) {
      return;
    }

    state.dragWindowId = dockWindow.dataset.dockWindowId;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", state.dragWindowId);
  });

  document.addEventListener("dragover", (event) => {
    if (!state.dragWindowId) {
      return;
    }

    const dropWindow = event.target.closest("[data-dock-window-id]");
    const canvas = event.target.closest("#workspace-canvas");
    if (!dropWindow && !canvas) {
      return;
    }

    event.preventDefault();
    clearDropTargets();
    if (dropWindow && dropWindow.dataset.dockWindowId !== state.dragWindowId) {
      dropWindow.classList.add("is-drop-target");
    }
  });

  document.addEventListener("drop", (event) => {
    if (!state.dragWindowId) {
      return;
    }

    const workspace = getActiveWorkspace();
    if (!workspace) {
      return;
    }

    const dropWindow = event.target.closest("[data-dock-window-id]");
    const canvas = event.target.closest("#workspace-canvas");
    if (!dropWindow && !canvas) {
      return;
    }

    event.preventDefault();
    const targetId = dropWindow ? dropWindow.dataset.dockWindowId : null;
    if (targetId !== state.dragWindowId) {
      reorderDockedWindows(workspace, state.dragWindowId, targetId);
      renderAll();
    }

    state.dragWindowId = null;
    clearDropTargets();
  });

  document.addEventListener("dragend", () => {
    state.dragWindowId = null;
    clearDropTargets();
  });

  window.addEventListener("beforeunload", () => {
    Object.keys(state.popupRefs).forEach((windowId) => {
      closePopupWindow(windowId);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.settingsOpen) {
      closeSettings();
    }
  });

  bindBrowserPaneInteractions(document);
}

function init() {
  if (!state.dashboard) {
    return;
  }

  initializeState(state.dashboard);
  bindEvents();
  renderAll();
}

init();
