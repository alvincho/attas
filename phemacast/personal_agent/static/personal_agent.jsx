/* global React, ReactDOM */

const { useDeferredValue, useEffect, useRef, useState } = React;
const MAP_PHEMAR_SHARED = window.__PHEMACAST_MAP_PHEMAR_SHARED__ || {};
const MAP_PHEMAR_PRESET_OVERRIDES = typeof MAP_PHEMAR_SHARED.getShapePresetOverrides === "function"
  ? (MAP_PHEMAR_SHARED.getShapePresetOverrides() || {})
  : {};

const STORAGE_KEYS = {
  preferences: "phemacast.personal_agent.preferences.v1",
  workspaces: "phemacast.personal_agent.workspace_state.v1",
  snapshots: "phemacast.personal_agent.browser_layouts.v1",
  mindMapLayouts: "phemacast.personal_agent.mindmap_layouts.v1",
  workspaceLayouts: "phemacast.personal_agent.workspace_layouts.v1",
  plazaAuthSession: "phemacast.personal_agent.plaza_auth_session.v1",
};
const MAP_PHEMAR_PREFERENCE_STORAGE_KEY = "phemacast.map_phemar.preferences.v1";

const THEME_OPTIONS = [
  { id: "mercury", label: "Mercury Ledger" },
  { id: "paper", label: "Signal Paper" },
  { id: "after-hours", label: "After Hours" },
];

const SETTINGS_TABS = [
  { id: "profile", label: "Profile" },
  { id: "llm", label: "LLM Config" },
  { id: "api_keys", label: "API Keys" },
  { id: "plaza_access", label: "Plaza Access" },
  { id: "connection", label: "Connection" },
  { id: "storage", label: "Storage" },
];
const OPERATOR_TABS = [
  { id: "works", label: "Works" },
  { id: "assignments", label: "Assignments" },
  { id: "results", label: "Results" },
  { id: "destinations", label: "Destinations" },
];
const DEFAULT_OPERATOR_CHANNELS = [
  { kind: "slack", label: "Slack", status: "available", detail: "Desk channel delivery lane." },
  { kind: "teams", label: "Teams", status: "available", detail: "Microsoft Teams delivery lane." },
  { kind: "email", label: "Email", status: "available", detail: "Direct email delivery lane." },
];

const LLM_CONFIG_TYPES = [
  { id: "api", label: "API" },
  { id: "llm_pulse", label: "LLM Pulse" },
];

const LLM_API_PROVIDERS = ["openai", "anthropic", "google", "openrouter", "ollama", "custom"];
const FILE_SAVE_BACKENDS = [
  { id: "filesystem", label: "Local Filesystem" },
  { id: "system_pulser", label: "SystemPulser" },
];
const LEGACY_SYSTEM_PULSER_BACKEND = ["file", "storage", "pulser"].join("_");
const BROWSER_PANE_TYPES = [
  { id: "plain_text", label: "Plain" },
  { id: "mind_map", label: "Diagram" },
  { id: "managed_work", label: "Managed Work" },
];
const BROWSER_PANE_FORMATS = ["plain_text", "json", "list", "chart"];
const BROWSER_CHART_TYPES = ["bar", "line", "candle"];
const MINDMAP_PULSER_MODES = ["specific", "dynamic"];
const MINDMAP_PREFERRED_PULSES = [
  "price_change_summary",
  "last_price",
  "intraday_ohlcv_bar",
  "daily_ohlcv_bar",
  "ohlc_bar_series",
  "fifty_two_week_range",
  "company_profile",
];
const BRANCH_CONNECTOR_SIDES = ["top", "right", "bottom", "left"];
const BRANCH_CONNECTOR_PROCESS_MODES = ["any", "all"];
const MINDMAP_BASE_SHAPE_PRESETS = [
  { id: "rounded", label: "Rounded", description: "Rounded box", w: 22, h: 14 },
  { id: "rectangle", label: "Rectangle", description: "Straight edge box", w: 22, h: 14 },
  { id: "pill", label: "Pill", description: "Capsule label", w: 20, h: 12 },
  { id: "note", label: "Note", description: "Sticky note", w: 18, h: 16 },
  { id: "diamond", label: "Diamond", description: "Decision shape", w: 18, h: 18, ...(MAP_PHEMAR_PRESET_OVERRIDES.diamond || {}) },
  { id: "branch", label: "Branch", description: "Conditional decision", w: 18, h: 18, ...(MAP_PHEMAR_PRESET_OVERRIDES.branch || {}) },
];
const MINDMAP_SHAPE_PRESETS = typeof MAP_PHEMAR_SHARED.filterShapePresets === "function"
  ? MAP_PHEMAR_SHARED.filterShapePresets(MINDMAP_BASE_SHAPE_PRESETS)
  : MINDMAP_BASE_SHAPE_PRESETS;
const MINDMAP_BOUNDARY_ROLES = ["input", "output"];
const BOOTSTRAP = window.__PHEMACAST_PERSONAL_AGENT_BOOTSTRAP__ || {};
const APP_MODE = String(BOOTSTRAP?.meta?.app_mode || "").trim().toLowerCase();
const IS_MAP_PHEMAR_MODE = APP_MODE === "map_phemar";
const MAP_PHEMAR_SETTINGS_SCOPE = String(BOOTSTRAP?.meta?.map_phemar_settings_scope || "").trim().toLowerCase() || "personal_agent";
const MAP_PHEMAR_STORAGE_SETTINGS_MODE = String(BOOTSTRAP?.meta?.map_phemar_storage_settings_mode || "").trim().toLowerCase() || "local";
const APP_DISPLAY_NAME = String(BOOTSTRAP?.meta?.agent_name || "").trim()
  || (IS_MAP_PHEMAR_MODE ? "MapPhemar" : "Personal Agent");
const PHEMA_API_PREFIX = String(BOOTSTRAP?.meta?.phema_api_prefix || "").trim()
  || "/api/map-phemar/phemas";
const MAP_PHEMAR_EDITOR_PREFIX = "/map-phemar/phemas/editor";
const MAP_PHEMAR_RETURN_MESSAGE_TYPE = "phemacast:map-phemar:return";
const MAP_PHEMAR_STORAGE_DIRECTORY_QUERY_PARAM = "map_phemar_storage_directory";
const MAP_PHEMAR_SETTINGS_SCOPE_QUERY_PARAM = "map_phemar_settings_scope";
const MAP_PHEMAR_STORAGE_SETTINGS_MODE_QUERY_PARAM = "map_phemar_storage_settings_mode";
const MAP_PHEMAR_PREFERENCE_STORAGE_KEY_QUERY_PARAM = "map_phemar_preference_storage_key";
const MAP_PHEMAR_PLAZA_URL_QUERY_PARAM = "map_phemar_plaza_url";
const MAP_PHEMAR_LAUNCH_DRAFT_QUERY_PARAM = "map_phemar_launch_draft";
const MAP_PHEMAR_LAUNCH_DRAFT_STORAGE_PREFIX = "phemacast.map_phemar.launch_draft";
const MAP_PHEMAR_PREFERENCE_STORAGE_KEY_OVERRIDE = String(BOOTSTRAP?.meta?.map_phemar_preference_storage_key || "").trim();
const PERSONAL_AGENT_USER_GUIDE_PATH = "/docs/personal-agent/user-guide";
const KNOWN_PLAZA_PATH_SUFFIXES = [
  "/api/plazas_status",
  "/api/pulsers/test",
  "/.well-known/agent-card",
  "/health",
  "/search",
];
const KNOWN_BOSS_PATH_SUFFIXES = [
  "/api/managed-work/monitor",
  "/api/managed-work/tickets",
  "/api/managed-work/schedules",
  "/api/jobs",
  "/api/status",
  "/api/teams",
  "/health",
];
const KNOWN_BOSS_PATH_PREFIXES = [
  "/api/managed-work/tickets/",
  "/api/managed-work/schedules/",
  "/api/jobs/",
];
const WORKSPACE_LEFT_INSET = 12;
const WORKSPACE_TOP_INSET = 32;
const BROWSER_LAYOUT_STORAGE_FILE_NAME = "browser-layouts.json";
const BROWSER_LAYOUT_STORAGE_TITLE = "browser-layouts";
const WORKSPACE_LAYOUT_STORAGE_FILE_NAME = "workspace-layouts.json";
const WORKSPACE_LAYOUT_STORAGE_TITLE = "workspace-layouts";
const DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY = "phemacast/personal_agent/storage/saved_files";
const MAP_PHEMAR_STORAGE_DIRECTORY_NAME = "map_phemar";
const MAP_PHEMA_LIBRARY_STORAGE_FILE_NAME = "map-phemas.json";
const MAP_PHEMA_LIBRARY_STORAGE_TITLE = "map-phemas";

function currentPreferenceStorageKey() {
  if (MAP_PHEMAR_PREFERENCE_STORAGE_KEY_OVERRIDE) {
    return MAP_PHEMAR_PREFERENCE_STORAGE_KEY_OVERRIDE;
  }
  if (IS_MAP_PHEMAR_MODE && MAP_PHEMAR_SETTINGS_SCOPE === "map_phemar") {
    return MAP_PHEMAR_PREFERENCE_STORAGE_KEY;
  }
  return STORAGE_KEYS.preferences;
}

function defaultMapPhemarStorageDirectory() {
  return String(BOOTSTRAP?.settings?.default_file_save_local_directory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY).trim();
}

function effectiveMapPhemarStorageDirectory() {
  const preferenceKey = currentPreferenceStorageKey();
  const storedPreferences = loadStorage(preferenceKey, null) || {};
  return String(storedPreferences?.fileSaveLocalDirectory || defaultMapPhemarStorageDirectory()).trim();
}

function mapPhemarLaunchDraftStorageKey(draftId) {
  return `${MAP_PHEMAR_LAUNCH_DRAFT_STORAGE_PREFIX}.${String(draftId || "").trim()}`;
}

function createMapPhemarLaunchDraft(phema) {
  if (!(phema && typeof phema === "object")) {
    return "";
  }
  const draftId = createId("map-phemar-draft");
  const storageKey = mapPhemarLaunchDraftStorageKey(draftId);
  try {
    window.localStorage.setItem(storageKey, JSON.stringify({
      createdAt: new Date().toISOString(),
      phema: cloneValue(phema),
    }));
    return draftId;
  } catch (error) {
    throw new Error("Unable to prepare the diagram draft for MapPhemar.");
  }
}

function consumeMapPhemarLaunchDraftFromLocation() {
  if (typeof window === "undefined") {
    return null;
  }
  const params = new URLSearchParams(window.location.search || "");
  const draftId = String(params.get(MAP_PHEMAR_LAUNCH_DRAFT_QUERY_PARAM) || "").trim();
  if (!draftId) {
    return null;
  }
  const storageKey = mapPhemarLaunchDraftStorageKey(draftId);
  try {
    const raw = window.localStorage.getItem(storageKey);
    window.localStorage.removeItem(storageKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return parsed?.phema && typeof parsed.phema === "object" ? parsed.phema : null;
  } catch (error) {
    try {
      window.localStorage.removeItem(storageKey);
    } catch (cleanupError) {
      // Ignore cleanup errors for transient launch drafts.
    }
    return null;
  }
}

function buildMapPhemarRequestUrl(path, extraParams = null, storageDirectory = "") {
  const url = new URL(path, window.location.origin);
  const effectiveDirectory = String(storageDirectory || effectiveMapPhemarStorageDirectory() || "").trim();
  if (effectiveDirectory) {
    url.searchParams.set(MAP_PHEMAR_STORAGE_DIRECTORY_QUERY_PARAM, effectiveDirectory);
  }
  if (extraParams && typeof extraParams === "object") {
    Object.entries(extraParams).forEach(([key, value]) => {
      const normalizedValue = String(value ?? "").trim();
      if (normalizedValue) {
        url.searchParams.set(key, normalizedValue);
      }
    });
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

function browserLayoutStorageTarget(preferences, appState) {
  if (normalizeFileSaveBackend(preferences?.fileSaveBackend) === "system_pulser") {
    const pulser = configuredSystemPulser(preferences, appState);
    const pulserLabel = formatConfiguredSystemPulserLabel(preferences, pulser);
    const bucketName = String(preferences?.fileSaveBucketName || "unset bucket").trim();
    const objectKey = joinStorageObjectKey(preferences?.fileSaveObjectPrefix, BROWSER_LAYOUT_STORAGE_FILE_NAME);
    return {
      backend: "system_pulser",
      label: `SystemPulser · ${pulserLabel}`,
      detail: `${bucketName}/${objectKey}`,
      objectKey,
      bucketName,
      pulser,
    };
  }
  const directory = String(preferences?.fileSaveLocalDirectory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY).trim();
  return {
    backend: "filesystem",
    label: "Local Filesystem",
    detail: `${directory.replace(/[\\/]+$/, "")}/${BROWSER_LAYOUT_STORAGE_FILE_NAME}`,
    directory,
  };
}

function snapshotStorageTarget(kind, preferences, appState, windowId = "") {
  if (kind === "browser") {
    return browserLayoutStorageTarget(preferences, appState);
  }
  if (kind === "mind_map") {
    return {
      label: "Browser Local Cache",
      detail: `localStorage/${STORAGE_KEYS.mindMapLayouts}`,
    };
  }
  return {
    label: "Browser Local Cache",
    detail: `localStorage/${STORAGE_KEYS.snapshots}/${windowId || "window"}`,
  };
}

function defaultSaveStorageTarget(preferences, appState) {
  if (normalizeFileSaveBackend(preferences?.fileSaveBackend) === "system_pulser") {
    const pulser = configuredSystemPulser(preferences, appState);
    const pulserLabel = formatConfiguredSystemPulserLabel(preferences, pulser);
    const bucketName = String(preferences?.fileSaveBucketName || "unset bucket").trim();
    const objectPrefix = String(preferences?.fileSaveObjectPrefix || "").trim().replace(/^\/+|\/+$/g, "");
    return {
      backend: "system_pulser",
      label: `SystemPulser · ${pulserLabel}`,
      detail: objectPrefix ? `${bucketName}/${objectPrefix}` : bucketName,
    };
  }
  const directory = String(preferences?.fileSaveLocalDirectory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY).trim();
  return {
    backend: "filesystem",
    label: "Local Filesystem",
    detail: directory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY,
  };
}

function formatStorageTargetSummary(target) {
  const label = String(target?.label || "").trim();
  const detail = String(target?.detail || "").trim();
  if (!label) {
    return detail;
  }
  return detail ? `${label} · ${detail}` : label;
}

function isDataPaneType(type) {
  return type === "plain_text" || type === "mind_map";
}

function isOperatorPaneType(type) {
  return type === "managed_work";
}

function cloneValue(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function isObjectRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function mergeObjectRecords(base, override) {
  const merged = isObjectRecord(base) ? cloneValue(base) : {};
  if (!isObjectRecord(override)) {
    return merged;
  }
  Object.entries(override).forEach(([key, value]) => {
    if (isObjectRecord(value) && isObjectRecord(merged[key])) {
      merged[key] = mergeObjectRecords(merged[key], value);
      return;
    }
    merged[key] = cloneValue(value);
  });
  return merged;
}

function createId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeFileSaveBackend(value) {
  const normalized = String(value || "").trim();
  if (normalized === LEGACY_SYSTEM_PULSER_BACKEND) {
    return "system_pulser";
  }
  return FILE_SAVE_BACKENDS.some((entry) => entry.id === normalized) ? normalized : "filesystem";
}

function openPersonalAgentUserGuide() {
  window.open(PERSONAL_AGENT_USER_GUIDE_PATH, "_blank", "noopener,noreferrer");
}

function normalizeMapPhemarReturnContext(context) {
  if (!context || typeof context !== "object") {
    return {
      workspaceId: "",
      windowId: "",
      browserWindowId: "",
      paneId: "",
    };
  }
  return {
    workspaceId: String(context.workspaceId || "").trim(),
    windowId: String(context.windowId || "").trim(),
    browserWindowId: String(context.browserWindowId || "").trim(),
    paneId: String(context.paneId || "").trim(),
  };
}

function mapPhemarReturnContextFromLocation() {
  if (typeof window === "undefined") {
    return normalizeMapPhemarReturnContext(null);
  }
  const params = new URLSearchParams(window.location.search || "");
  return normalizeMapPhemarReturnContext({
    workspaceId: params.get("return_workspace_id") || "",
    windowId: params.get("return_window_id") || "",
    browserWindowId: params.get("return_browser_window_id") || "",
    paneId: params.get("return_pane_id") || "",
  });
}

function mapPhemarEditorHref(phemaId = "", sourceContext = null, storageOptions = null) {
  const normalizedId = String(phemaId || "").trim();
  const href = normalizedId
    ? `${MAP_PHEMAR_EDITOR_PREFIX}/${encodeURIComponent(normalizedId)}`
    : MAP_PHEMAR_EDITOR_PREFIX;
  const normalizedContext = normalizeMapPhemarReturnContext(sourceContext);
  const extraParams = {};
  if (normalizedContext.workspaceId) {
    extraParams.return_workspace_id = normalizedContext.workspaceId;
  }
  if (normalizedContext.windowId) {
    extraParams.return_window_id = normalizedContext.windowId;
  }
  if (normalizedContext.browserWindowId) {
    extraParams.return_browser_window_id = normalizedContext.browserWindowId;
  }
  if (normalizedContext.paneId) {
    extraParams.return_pane_id = normalizedContext.paneId;
  }
  if (storageOptions && typeof storageOptions === "object") {
    const storageDirectory = String(storageOptions.storageDirectory || "").trim();
    if (storageDirectory) {
      extraParams[MAP_PHEMAR_STORAGE_DIRECTORY_QUERY_PARAM] = storageDirectory;
    }
    const launchDraftKey = String(storageOptions.launchDraftKey || "").trim();
    if (launchDraftKey) {
      extraParams[MAP_PHEMAR_LAUNCH_DRAFT_QUERY_PARAM] = launchDraftKey;
    }
    const settingsScope = String(storageOptions.settingsScope || "").trim();
    if (settingsScope) {
      extraParams[MAP_PHEMAR_SETTINGS_SCOPE_QUERY_PARAM] = settingsScope;
    }
    const settingsMode = String(storageOptions.storageSettingsMode || "").trim();
    if (settingsMode) {
      extraParams[MAP_PHEMAR_STORAGE_SETTINGS_MODE_QUERY_PARAM] = settingsMode;
    }
    const preferenceStorageKey = String(storageOptions.preferenceStorageKey || "").trim();
    if (preferenceStorageKey) {
      extraParams[MAP_PHEMAR_PREFERENCE_STORAGE_KEY_QUERY_PARAM] = preferenceStorageKey;
    }
    const plazaUrl = String(storageOptions.plazaUrl || "").trim();
    if (plazaUrl) {
      extraParams[MAP_PHEMAR_PLAZA_URL_QUERY_PARAM] = plazaUrl;
    }
  }
  return buildMapPhemarRequestUrl(href, extraParams, extraParams[MAP_PHEMAR_STORAGE_DIRECTORY_QUERY_PARAM] || "");
}

function openPendingMapPhemarWindow(label = "MapPhemar") {
  const popup = window.open(
    "about:blank",
    "_blank",
    [
      "popup=yes",
      "width=1440",
      "height=920",
      "left=140",
      "top=140",
    ].join(","),
  );
  if (!popup) {
    return null;
  }
  try {
    popup.document.title = label;
    popup.document.body.className = "personal-agent-popup-body";
    popup.document.body.innerHTML = `
      <div class="map-phemar-launch-shell">
        <strong>Opening ${label}...</strong>
        <span>Preparing the shared diagram owner.</span>
      </div>
    `;
  } catch (error) {
    console.error("Unable to prime the MapPhemar popup window.", error);
  }
  return popup;
}

function navigatePendingMapPhemarWindow(popup, href) {
  if (popup && !popup.closed) {
    popup.location.href = href;
    return;
  }
  window.open(href, "_blank", "popup=yes,width=1440,height=920,left=140,top=140");
}

function normalizeMindMapShapeId(shapeId) {
  if (typeof MAP_PHEMAR_SHARED.normalizeShapeId === "function") {
    return MAP_PHEMAR_SHARED.normalizeShapeId(shapeId);
  }
  return String(shapeId || "").trim().toLowerCase();
}

function normalizeBranchMindMapRoute(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "yes" || normalized === "branch-yes") {
    return "yes";
  }
  if (normalized === "no" || normalized === "branch-no") {
    return "no";
  }
  return "";
}

function branchMindMapRouteLabel(route) {
  return normalizeBranchMindMapRoute(route) === "no" ? "No" : "Yes";
}

function branchMindMapRouteAnchor(route) {
  return normalizeBranchMindMapRoute(route) === "no" ? "branch-no" : "branch-yes";
}

function branchMindMapRouteFromAnchor(anchor) {
  return normalizeBranchMindMapRoute(anchor);
}

function isBranchMindMapInputAnchor(anchor) {
  return String(anchor || "").trim().toLowerCase() === "branch-in";
}

function normalizeBranchConnectorSide(value, fallback = "right") {
  const normalized = String(value || "").trim().toLowerCase();
  return BRANCH_CONNECTOR_SIDES.includes(normalized) ? normalized : fallback;
}

function defaultBranchConnectorSide(kind) {
  return kind === "input" ? "left" : "right";
}

function branchConnectorSide(node, kind) {
  if (kind === "input") {
    return normalizeBranchConnectorSide(node?.branchInputSide, defaultBranchConnectorSide("input"));
  }
  if (kind === "yes") {
    return normalizeBranchConnectorSide(node?.branchYesSide, defaultBranchConnectorSide("yes"));
  }
  return normalizeBranchConnectorSide(node?.branchNoSide, defaultBranchConnectorSide("no"));
}

function branchConnectorField(kind) {
  if (kind === "input") {
    return "branchInputSide";
  }
  if (kind === "yes") {
    return "branchYesSide";
  }
  return "branchNoSide";
}

function normalizeBranchConnectorMode(value, fallback = "all") {
  const normalized = String(value || "").trim().toLowerCase();
  return BRANCH_CONNECTOR_PROCESS_MODES.includes(normalized) ? normalized : fallback;
}

function defaultBranchConnectorMode(kind) {
  return kind === "input" ? "any" : "all";
}

function branchConnectorMode(node, kind) {
  if (kind === "input") {
    return normalizeBranchConnectorMode(node?.branchInputMode, defaultBranchConnectorMode("input"));
  }
  if (kind === "yes") {
    return normalizeBranchConnectorMode(node?.branchYesMode, defaultBranchConnectorMode("yes"));
  }
  return normalizeBranchConnectorMode(node?.branchNoMode, defaultBranchConnectorMode("no"));
}

function branchConnectorModeField(kind) {
  if (kind === "input") {
    return "branchInputMode";
  }
  if (kind === "yes") {
    return "branchYesMode";
  }
  return "branchNoMode";
}

function mindMapShapePreset(shapeId) {
  const normalizedShapeId = normalizeMindMapShapeId(shapeId);
  return MINDMAP_SHAPE_PRESETS.find((entry) => entry.id === normalizedShapeId)
    || MINDMAP_SHAPE_PRESETS.find((entry) => entry.id === "rounded")
    || MINDMAP_BASE_SHAPE_PRESETS[0];
}

function usesDiamondMindMapFootprint(shapeId) {
  if (typeof MAP_PHEMAR_SHARED.usesSquareFootprint === "function") {
    return Boolean(MAP_PHEMAR_SHARED.usesSquareFootprint(shapeId));
  }
  const normalized = normalizeMindMapShapeId(shapeId);
  return normalized === "diamond" || normalized === "branch";
}

function constrainMindMapShapeResize(shapeId, width, height) {
  if (typeof MAP_PHEMAR_SHARED.constrainResize === "function") {
    const constrained = MAP_PHEMAR_SHARED.constrainResize(shapeId, width, height);
    if (constrained && Number.isFinite(Number(constrained.w)) && Number.isFinite(Number(constrained.h))) {
      return {
        w: Number(constrained.w),
        h: Number(constrained.h),
      };
    }
  }
  if (usesDiamondMindMapFootprint(shapeId)) {
    const size = Math.max(Number(width) || 0, Number(height) || 0, 10);
    return { w: size, h: size };
  }
  return { w: Number(width) || 0, h: Number(height) || 0 };
}

function mindMapNodeFootprintStyle(node) {
  if (typeof MAP_PHEMAR_SHARED.getNodeFootprintStyle === "function") {
    const sharedStyle = MAP_PHEMAR_SHARED.getNodeFootprintStyle(node);
    if (sharedStyle && Number.isFinite(Number(sharedStyle.w)) && Number.isFinite(Number(sharedStyle.h))) {
      return {
        width: `${Number(sharedStyle.w)}%`,
        height: `${Number(sharedStyle.h)}%`,
      };
    }
  }
  if (usesDiamondMindMapFootprint(node?.type)) {
    const size = Math.max(Number(node?.w || 0), Number(node?.h || 0), 10);
    return {
      width: `${size}%`,
      height: `${size}%`,
    };
  }
  return {
    width: `${node?.w || 0}%`,
    height: `${node?.h || 0}%`,
  };
}

function normalizeBoundaryMindMapRole(role) {
  const normalized = String(role || "").toLowerCase();
  if (normalized === "start" || normalized === "input") {
    return "input";
  }
  if (normalized === "end" || normalized === "output") {
    return "output";
  }
  return "";
}

function isBoundaryMindMapRole(role) {
  return Boolean(normalizeBoundaryMindMapRole(role));
}

function isBoundaryMindMapNode(node) {
  return isBoundaryMindMapRole(node?.role);
}

function isBranchMindMapNode(node) {
  return !isBoundaryMindMapNode(node) && String(node?.type || "") === "branch";
}

function branchConditionConfigured(node) {
  return Boolean(String(node?.conditionExpression || "").trim());
}

function boundaryMindMapTitle(role) {
  return normalizeBoundaryMindMapRole(role) === "output" ? "Output" : "Input";
}

function boundarySchemaConfig(role) {
  const normalized = normalizeBoundaryMindMapRole(role);
  if (normalized === "output") {
    return {
      schemaKey: "inputSchema",
      textKey: "inputSchemaText",
      errorKey: "inputSchemaError",
      label: "Output Schema",
      helper: "Receives the final payload from upstream shapes.",
    };
  }
  return {
    schemaKey: "outputSchema",
    textKey: "outputSchemaText",
    errorKey: "outputSchemaError",
    label: "Input Schema",
    helper: "Provides the initial payload to downstream shapes.",
  };
}

function boundarySchemaConfigured(node) {
  const config = boundarySchemaConfig(node?.role);
  return Object.keys(schemaProperties(node?.[config.schemaKey] || {})).length > 0;
}

function schemaHasFields(schema) {
  return Object.keys(schemaProperties(schema || {})).length > 0;
}

function schemaTextValue(schema) {
  return JSON.stringify(schema && typeof schema === "object" ? schema : {}, null, 2) || "{}";
}

function createBoundaryMindMapNode(role) {
  const normalizedRole = normalizeBoundaryMindMapRole(role) || "input";
  const title = boundaryMindMapTitle(normalizedRole);
  const preset = mindMapShapePreset("pill");
  return {
    id: `mind-boundary-${normalizedRole}`,
    role: normalizedRole,
    type: preset.id,
    title,
    subtitle: "",
    body: "",
    x: normalizedRole === "input" ? 12 : 62,
    y: 42,
    w: 16,
    h: 10,
    pulserMode: "specific",
    pulserId: "",
    pulserName: "",
    pulserAddress: "",
    practiceId: "get_pulse_data",
    pulseName: "",
    pulseAddress: "",
    inputSchema: {},
    outputSchema: {},
    inputSchemaText: "{}",
    outputSchemaText: "{}",
    inputSchemaError: "",
    outputSchemaError: "",
    paramsText: "{}",
    conditionExpression: "",
    branchInputSide: defaultBranchConnectorSide("input"),
    branchYesSide: defaultBranchConnectorSide("yes"),
    branchNoSide: defaultBranchConnectorSide("no"),
    branchInputMode: defaultBranchConnectorMode("input"),
    branchYesMode: defaultBranchConnectorMode("yes"),
    branchNoMode: defaultBranchConnectorMode("no"),
  };
}

function setMindMapNodeSchemas(node, inputSchema, outputSchema) {
  node.inputSchema = inputSchema && typeof inputSchema === "object" ? inputSchema : {};
  node.outputSchema = outputSchema && typeof outputSchema === "object" ? outputSchema : {};
  node.inputSchemaText = schemaTextValue(node.inputSchema);
  node.outputSchemaText = schemaTextValue(node.outputSchema);
  node.inputSchemaError = "";
  node.outputSchemaError = "";
}

function inferBranchMindMapSchema(map, node) {
  if (!map || !node) {
    return {};
  }
  const incomingEdges = mindMapIncomingEdges(map, node.id);
  for (const edge of incomingEdges) {
    const sourceNode = map.nodes.find((entry) => entry.id === edge.from) || null;
    if (sourceNode && schemaHasFields(sourceNode.outputSchema || {})) {
      return cloneValue(sourceNode.outputSchema || {});
    }
  }
  const outgoingEdges = mindMapOutgoingEdges(map, node.id);
  for (const edge of outgoingEdges) {
    const targetNode = map.nodes.find((entry) => entry.id === edge.to) || null;
    if (targetNode && schemaHasFields(targetNode.inputSchema || {})) {
      return cloneValue(targetNode.inputSchema || {});
    }
  }
  return {};
}

function syncBranchMindMapSchemas(map) {
  if (!map || !Array.isArray(map.nodes)) {
    return;
  }
  const branchNodes = map.nodes.filter((entry) => isBranchMindMapNode(entry));
  const maxPasses = Math.max(branchNodes.length, 1);
  for (let pass = 0; pass < maxPasses; pass += 1) {
    let changed = false;
    branchNodes.forEach((node) => {
      const nextSchema = inferBranchMindMapSchema(map, node);
      const nextSignature = schemaTextValue(nextSchema);
      const currentInputSignature = schemaTextValue(node.inputSchema || {});
      const currentOutputSignature = schemaTextValue(node.outputSchema || {});
      if (currentInputSignature !== nextSignature || currentOutputSignature !== nextSignature) {
        node.inputSchema = cloneValue(nextSchema);
        node.outputSchema = cloneValue(nextSchema);
        changed = true;
      }
    });
    if (!changed) {
      break;
    }
  }
}

function branchSchemaConfigured(node) {
  return schemaHasFields(node?.inputSchema || {}) || schemaHasFields(node?.outputSchema || {});
}

function boundaryMindMapLinkedNode(map, node) {
  const role = normalizeBoundaryMindMapRole(node?.role);
  if (!role || !map || !Array.isArray(map.nodes) || !Array.isArray(map.edges)) {
    return null;
  }
  const linkedEdge = role === "input"
    ? map.edges.find((entry) => entry.from === node.id)
    : map.edges.find((entry) => entry.to === node.id);
  if (!linkedEdge) {
    return null;
  }
  const linkedNodeId = role === "input" ? linkedEdge.to : linkedEdge.from;
  return map.nodes.find((entry) => entry.id === linkedNodeId) || null;
}

function syncBoundaryMindMapSchemas(map) {
  if (!map || !Array.isArray(map.nodes)) {
    return;
  }
  map.nodes.forEach((node) => {
    const role = normalizeBoundaryMindMapRole(node?.role);
    if (!role) {
      return;
    }
    const linkedNode = boundaryMindMapLinkedNode(map, node);
    if (!linkedNode) {
      return;
    }
    if (role === "input") {
      const nextSchema = cloneValue(linkedNode.inputSchema && typeof linkedNode.inputSchema === "object" ? linkedNode.inputSchema : {});
      node.outputSchema = nextSchema;
      node.outputSchemaText = schemaTextValue(nextSchema);
      node.outputSchemaError = "";
      return;
    }
    const nextSchema = cloneValue(linkedNode.outputSchema && typeof linkedNode.outputSchema === "object" ? linkedNode.outputSchema : {});
    node.inputSchema = nextSchema;
    node.inputSchemaText = schemaTextValue(nextSchema);
    node.inputSchemaError = "";
  });
}

function createPhemaDialogState() {
  return {
    open: false,
    windowId: "",
    mode: "save",
    name: "",
    query: "",
    selectedPhemaId: "",
    phemas: [],
    error: "",
    loading: false,
    saving: false,
  };
}

function mindMapHandleDescriptors(node) {
  const role = normalizeBoundaryMindMapRole(node?.role);
  if (role === "input") {
    return [{ anchor: "right", interactive: true, label: "", title: `Create connection from ${node?.title || "Input"}` }];
  }
  if (role === "output") {
    return [];
  }
  if (isBranchMindMapNode(node)) {
    const handles = [
      {
        key: "input",
        anchor: "branch-in",
        interactive: false,
        label: "In",
        title: `${node?.title || "Branch"} accepts inbound connections.`,
        side: branchConnectorSide(node, "input"),
      },
      {
        key: "yes",
        anchor: "branch-yes",
        interactive: true,
        label: "Yes",
        title: `Create the Yes connection from ${node?.title || "Branch"}`,
        side: branchConnectorSide(node, "yes"),
      },
      {
        key: "no",
        anchor: "branch-no",
        interactive: true,
        label: "No",
        title: `Create the No connection from ${node?.title || "Branch"}`,
        side: branchConnectorSide(node, "no"),
      },
    ];
    const grouped = new Map();
    handles.forEach((handle) => {
      const list = grouped.get(handle.side) || [];
      list.push(handle);
      grouped.set(handle.side, list);
    });
    const offsetsForCount = (count) => {
      if (count <= 1) {
        return [50];
      }
      if (count === 2) {
        return [34, 66];
      }
      return [22, 50, 78];
    };
    grouped.forEach((entries, side) => {
      const offsets = offsetsForCount(entries.length);
      entries.forEach((entry, index) => {
        const offset = offsets[index] ?? 50;
        let xPercent = 50;
        let yPercent = 50;
        let transform = "translate(-50%, -50%)";
        if (side === "left") {
          xPercent = 0;
          yPercent = offset;
          transform = "translate(-50%, -50%)";
        } else if (side === "right") {
          xPercent = 100;
          yPercent = offset;
          transform = "translate(50%, -50%)";
        } else if (side === "top") {
          xPercent = offset;
          yPercent = 0;
          transform = "translate(-50%, -50%)";
        } else if (side === "bottom") {
          xPercent = offset;
          yPercent = 100;
          transform = "translate(-50%, 50%)";
        }
        entry.xPercent = xPercent;
        entry.yPercent = yPercent;
        entry.transform = transform;
        entry.style = {
          left: `${xPercent}%`,
          top: `${yPercent}%`,
          transform,
        };
      });
    });
    return handles;
  }
  return ["top", "right", "bottom", "left"].map((anchor) => ({
    anchor,
    interactive: true,
    label: "",
    title: `Create connection from ${node?.title || "Shape"}`,
  }));
}

function ensureBoundaryMindMapNodes(nodes) {
  const nextNodes = Array.isArray(nodes) ? [...nodes] : [];
  MINDMAP_BOUNDARY_ROLES.forEach((role) => {
    const existingIndex = nextNodes.findIndex((entry) => normalizeBoundaryMindMapRole(entry?.role) === role);
    if (existingIndex >= 0) {
      const existing = nextNodes[existingIndex];
      const boundary = createBoundaryMindMapNode(role);
      nextNodes[existingIndex] = {
        ...existing,
        role,
        type: "pill",
        title: boundary.title,
        subtitle: "",
        pulseName: "",
        pulseAddress: "",
        pulserId: "",
        pulserName: "",
        pulserAddress: "",
      };
      return;
    }
    nextNodes.push(createBoundaryMindMapNode(role));
  });
  const inputNode = nextNodes.find((entry) => normalizeBoundaryMindMapRole(entry?.role) === "input");
  const outputNode = nextNodes.find((entry) => normalizeBoundaryMindMapRole(entry?.role) === "output");
  if (
    inputNode
    && outputNode
    && inputNode.id === "mind-boundary-input"
    && outputNode.id === "mind-boundary-output"
    && Number(inputNode.x) === 74
    && Number(outputNode.x) === 74
    && Number(inputNode.y) === 42
    && Number(outputNode.y) === 42
  ) {
    const inputDefaults = createBoundaryMindMapNode("input");
    const outputDefaults = createBoundaryMindMapNode("output");
    inputNode.x = inputDefaults.x;
    inputNode.y = inputDefaults.y;
    outputNode.x = outputDefaults.x;
    outputNode.y = outputDefaults.y;
  }
  return nextNodes;
}

function normalizeMindMapNode(entry, index = 0) {
  const role = normalizeBoundaryMindMapRole(entry?.role);
  const preset = mindMapShapePreset(isBoundaryMindMapRole(role) ? "pill" : entry?.type === "pulse" ? "rounded" : entry?.type);
  const isBranch = !isBoundaryMindMapRole(role) && preset.id === "branch";
  const title = isBoundaryMindMapRole(role)
    ? boundaryMindMapTitle(role)
    : String(entry?.title || `${preset.label} ${String(index + 1).padStart(2, "0")}`);
  const legacySubtitle = String(entry?.pulseName || "").trim();
  const inputSchema = entry?.inputSchema && typeof entry.inputSchema === "object" ? entry.inputSchema : {};
  const outputSchema = entry?.outputSchema && typeof entry.outputSchema === "object" ? entry.outputSchema : {};
  return {
    id: entry?.id || (isBoundaryMindMapRole(role) ? `mind-boundary-${role}` : createId("mind-node")),
    role: isBoundaryMindMapRole(role) ? role : "",
    type: preset.id,
    title,
    subtitle: isBoundaryMindMapRole(role) || isBranch ? "" : String(entry?.subtitle || (legacySubtitle && legacySubtitle !== title ? legacySubtitle : "")),
    body: isBranch ? "" : String(entry?.body || ""),
    x: Number.isFinite(entry?.x) ? entry.x : clamp(12 + (index % 4) * 18, 0, 78),
    y: Number.isFinite(entry?.y) ? entry.y : clamp(12 + Math.floor(index / 4) * 18, 0, 80),
    w: Number.isFinite(entry?.w) ? entry.w : preset.w,
    h: Number.isFinite(entry?.h) ? entry.h : preset.h,
    pulserMode: String(entry?.pulserMode || "specific"),
    pulserId: isBranch ? "" : String(entry?.pulserId || ""),
    pulserName: isBranch ? "" : String(entry?.pulserName || ""),
    pulserAddress: isBranch ? "" : String(entry?.pulserAddress || ""),
    practiceId: String(entry?.practiceId || "get_pulse_data"),
    pulseName: isBoundaryMindMapRole(role) || isBranch ? "" : String(entry?.pulseName || ""),
    pulseAddress: isBoundaryMindMapRole(role) || isBranch ? "" : String(entry?.pulseAddress || ""),
    inputSchema,
    outputSchema,
    inputSchemaText: typeof entry?.inputSchemaText === "string" ? entry.inputSchemaText : schemaTextValue(inputSchema),
    outputSchemaText: typeof entry?.outputSchemaText === "string" ? entry.outputSchemaText : schemaTextValue(outputSchema),
    inputSchemaError: typeof entry?.inputSchemaError === "string" ? entry.inputSchemaError : "",
    outputSchemaError: typeof entry?.outputSchemaError === "string" ? entry.outputSchemaError : "",
    paramsText: typeof entry?.paramsText === "string" ? entry.paramsText : "{}",
    conditionExpression: isBranch ? String(entry?.conditionExpression || entry?.expression || "") : "",
    branchInputSide: normalizeBranchConnectorSide(entry?.branchInputSide, defaultBranchConnectorSide("input")),
    branchYesSide: normalizeBranchConnectorSide(entry?.branchYesSide, defaultBranchConnectorSide("yes")),
    branchNoSide: normalizeBranchConnectorSide(entry?.branchNoSide, defaultBranchConnectorSide("no")),
    branchInputMode: normalizeBranchConnectorMode(entry?.branchInputMode, defaultBranchConnectorMode("input")),
    branchYesMode: normalizeBranchConnectorMode(entry?.branchYesMode, defaultBranchConnectorMode("yes")),
    branchNoMode: normalizeBranchConnectorMode(entry?.branchNoMode, defaultBranchConnectorMode("no")),
  };
}

function normalizeMindMapEdge(entry) {
  return {
    id: entry?.id || createId("mind-edge"),
    from: String(entry?.from || ""),
    to: String(entry?.to || ""),
    label: String(entry?.label || ""),
    fromAnchor: String(entry?.fromAnchor || ""),
    toAnchor: String(entry?.toAnchor || ""),
    mappingText: typeof entry?.mappingText === "string" ? entry.mappingText : "{}",
    route: normalizeBranchMindMapRoute(entry?.route || entry?.branchRoute || entry?.decision || entry?.fromAnchor),
  };
}

function syncBranchMindMapEdges(map) {
  if (!map || !Array.isArray(map.nodes) || !Array.isArray(map.edges)) {
    return;
  }
  const nodesById = new Map(map.nodes.map((node) => [node.id, node]));
  const branchRoutes = new Map();
  const nextEdges = [];

  map.edges.forEach((edge) => {
    const nextEdge = { ...edge };
    const fromNode = nodesById.get(nextEdge.from) || null;
    const toNode = nodesById.get(nextEdge.to) || null;

    if (fromNode && isBranchMindMapNode(fromNode)) {
      const usedRoutes = branchRoutes.get(fromNode.id) || { yes: 0, no: 0 };
      let route = normalizeBranchMindMapRoute(nextEdge.route || nextEdge.fromAnchor);
      if (!route) {
        route = usedRoutes.yes <= usedRoutes.no ? "yes" : "no";
      }
      usedRoutes[route] = Number(usedRoutes[route] || 0) + 1;
      branchRoutes.set(fromNode.id, usedRoutes);
      nextEdge.route = route;
      nextEdge.fromAnchor = branchMindMapRouteAnchor(route);
      if (!String(nextEdge.label || "").trim()) {
        nextEdge.label = branchMindMapRouteLabel(route);
      }
    } else {
      nextEdge.route = "";
      if (normalizeBranchMindMapRoute(nextEdge.fromAnchor)) {
        nextEdge.fromAnchor = "";
      }
    }

    if (toNode && isBranchMindMapNode(toNode)) {
      nextEdge.toAnchor = "branch-in";
    } else if (isBranchMindMapInputAnchor(nextEdge.toAnchor)) {
      nextEdge.toAnchor = "";
    }

    nextEdges.push(nextEdge);
  });

  map.edges = nextEdges;
}

function currency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 100 ? 2 : 4,
  }).format(Number(value || 0));
}

function safeJsonParse(value, fallback) {
  try {
    return JSON.parse(value);
  } catch (error) {
    return fallback;
  }
}

function normalizeServiceUrl(value, knownSuffixes, knownPrefixes = []) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  const withProtocol = raw.startsWith("http://") || raw.startsWith("https://") ? raw : `http://${raw}`;
  try {
    const url = new URL(withProtocol);
    let pathname = url.pathname.replace(/\/+$/, "");
    knownSuffixes.forEach((suffix) => {
      if (pathname.endsWith(suffix)) {
        pathname = pathname.slice(0, -suffix.length);
      }
    });
    knownPrefixes.forEach((prefix) => {
      if (pathname.startsWith(prefix)) {
        pathname = "";
      }
    });
    url.pathname = pathname.replace(/\/+$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch (error) {
    return withProtocol.replace(/\/$/, "");
  }
}

function normalizePlazaUrl(value) {
  return normalizeServiceUrl(value, KNOWN_PLAZA_PATH_SUFFIXES);
}

function normalizeBossUrl(value) {
  return normalizeServiceUrl(value, KNOWN_BOSS_PATH_SUFFIXES, KNOWN_BOSS_PATH_PREFIXES);
}

async function loadJsonResponse(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

async function chooseLocalDirectory(initialDirectory = "") {
  const params = new URLSearchParams();
  const normalizedInitialDirectory = String(initialDirectory || "").trim();
  if (normalizedInitialDirectory) {
    params.set("initial_directory", normalizedInitialDirectory);
  }
  const response = await fetch(`/api/system/select-directory${params.toString() ? `?${params.toString()}` : ""}`);
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Folder picker route is not available on the running Personal Agent backend yet. Restart the app, then try Choose Folder again.");
    }
    throw new Error(payload.detail || payload.message || "Unable to open the local folder picker.");
  }
  if (String(payload?.status || "").trim().toLowerCase() === "cancelled") {
    return "";
  }
  return String(payload?.directory || "").trim();
}

function compareScoreTuple(left, right) {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const leftValue = Number(left[index] || 0);
    const rightValue = Number(right[index] || 0);
    if (leftValue !== rightValue) {
      return leftValue - rightValue;
    }
  }
  return 0;
}

function normalizePracticeEntry(entry) {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const id = String(entry.id || "").trim();
  if (!id) {
    return null;
  }
  return {
    id,
    name: String(entry.name || id),
    path: String(entry.path || ""),
    tags: Array.isArray(entry.tags) ? entry.tags : [],
  };
}

function normalizeCatalogPulseEntry(entry) {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const pulseName = String(entry.pulse_name || entry.name || "").trim();
  const pulseAddress = String(entry.pulse_address || entry.pit_address || entry.address || "").trim();
  const pulseId = String(entry.pulse_id || entry.pit_id || "").trim();
  if (!pulseName && !pulseAddress && !pulseId) {
    return null;
  }
  const pulseDefinition = entry.pulse_definition && typeof entry.pulse_definition === "object" ? entry.pulse_definition : {};
  return {
    pulse_id: pulseId,
    pulse_name: pulseName,
    pulse_address: pulseAddress,
    description: String(entry.description || pulseDefinition.description || "").trim(),
    input_schema: entry.input_schema && typeof entry.input_schema === "object" ? entry.input_schema : {},
    output_schema: entry.output_schema && typeof entry.output_schema === "object" ? entry.output_schema : {},
    pulse_definition: pulseDefinition,
    test_data: entry.test_data && typeof entry.test_data === "object" ? entry.test_data : {},
    tags: Array.isArray(entry.tags) ? entry.tags : [],
  };
}

function normalizeSupportedPulseEntry(entry) {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const pulseName = String(entry.pulse_name || entry.name || "").trim();
  const pulseAddress = String(entry.pulse_address || entry.address || "").trim();
  if (!pulseName && !pulseAddress) {
    return null;
  }
  const pulseDefinition = entry.pulse_definition && typeof entry.pulse_definition === "object" ? entry.pulse_definition : {};
  let testData = entry.test_data && typeof entry.test_data === "object" ? entry.test_data : {};
  if ((!testData || !Object.keys(testData).length) && pulseDefinition.test_data && typeof pulseDefinition.test_data === "object") {
    testData = cloneValue(pulseDefinition.test_data);
  }
  return {
    pulse_id: String(entry.pulse_id || "").trim(),
    pulse_name: pulseName,
    pulse_address: pulseAddress,
    description: String(entry.description || ""),
    input_schema: entry.input_schema && typeof entry.input_schema === "object" ? entry.input_schema : {},
    output_schema: entry.output_schema && typeof entry.output_schema === "object" ? entry.output_schema : {},
    pulse_definition: pulseDefinition,
    test_data: testData,
    test_data_path: String(entry.test_data_path || pulseDefinition.test_data_path || "").trim(),
  };
}

function defaultPracticeId(practices) {
  const preferred = practices.find((entry) => entry.id === "get_pulse_data");
  return preferred?.id || practices[0]?.id || "get_pulse_data";
}

function supportedPulseDedupeKey(entry) {
  return String(entry?.pulse_id || entry?.pulse_address || entry?.pulse_name || "").trim().toLowerCase();
}

function catalogPulseDedupeKey(entry) {
  return String(entry?.pulse_name || entry?.pulse_id || entry?.pulse_address || "").trim().toLowerCase();
}

function supportedPulsePreferenceKey(entry) {
  return [
    entry?.pulse_definition ? 1 : 0,
    Object.keys(entry?.output_schema || {}).length,
    Object.keys(entry?.input_schema || {}).length,
    Object.keys(entry?.test_data || {}).length,
    String(entry?.description || "").length,
  ];
}

function dedupeSupportedPulses(pulses) {
  const deduped = new Map();
  (pulses || []).forEach((pulse) => {
    const key = supportedPulseDedupeKey(pulse);
    if (!key) {
      return;
    }
    const existing = deduped.get(key);
    if (!existing || compareScoreTuple(supportedPulsePreferenceKey(pulse), supportedPulsePreferenceKey(existing)) > 0) {
      deduped.set(key, pulse);
    }
  });
  return Array.from(deduped.values());
}

function dedupeCatalogPulses(pulses) {
  const deduped = new Map();
  (pulses || []).forEach((pulse) => {
    const key = catalogPulseDedupeKey(pulse);
    if (!key) {
      return;
    }
    const existing = deduped.get(key);
    if (!existing || compareScoreTuple(supportedPulsePreferenceKey(pulse), supportedPulsePreferenceKey(existing)) > 0) {
      deduped.set(key, pulse);
    }
  });
  return Array.from(deduped.values());
}

function isLoopbackUrl(value) {
  try {
    const host = new URL(String(value || "")).hostname || "";
    return host === "127.0.0.1" || host === "localhost";
  } catch (error) {
    return false;
  }
}

function pulserPreferenceKey(pulser) {
  return [
    isLoopbackUrl(String(pulser?.address || "")) ? 1 : 0,
    Number(pulser?.last_active || 0),
    dedupeSupportedPulses(pulser?.supported_pulses || []).length,
    Number(pulser?.pulse_count || 0),
    String(pulser?.description || "").length,
  ];
}

function dedupePulsers(pulsers) {
  const deduped = new Map();
  (pulsers || []).forEach((pulser) => {
    const key = String(pulser?.name || pulser?.address || pulser?.agent_id || "").trim().toLowerCase();
    if (!key) {
      return;
    }
    const existing = deduped.get(key);
    if (!existing || compareScoreTuple(pulserPreferenceKey(pulser), pulserPreferenceKey(existing)) > 0) {
      deduped.set(key, pulser);
    }
  });
  return Array.from(deduped.values());
}

function fileStoragePulserSavePulse(pulser) {
  return (pulser?.supported_pulses || []).find((pulse) => (
    String(pulse?.pulse_name || pulse?.name || "").trim().toLowerCase() === "object_save"
  )) || null;
}

function fileStoragePulserLoadPulse(pulser) {
  return (pulser?.supported_pulses || []).find((pulse) => (
    String(pulse?.pulse_name || pulse?.name || "").trim().toLowerCase() === "object_load"
  )) || null;
}

function fileStoragePulserCreateBucketPulse(pulser) {
  return (pulser?.supported_pulses || []).find((pulse) => {
    const normalized = String(pulse?.pulse_name || pulse?.name || "").trim().toLowerCase();
    return normalized === "bucket_create" || normalized === "create_bucket";
  }) || null;
}

function fileStoragePulserListBucketPulse(pulser) {
  return (pulser?.supported_pulses || []).find((pulse) => {
    const normalized = String(pulse?.pulse_name || pulse?.name || "").trim().toLowerCase();
    return normalized === "list_bucket" || normalized === "bucket_list" || normalized === "list_buckets";
  }) || null;
}

function isFileStorageCatalogPulser(pulser) {
  return Boolean(fileStoragePulserSavePulse(pulser) && fileStoragePulserLoadPulse(pulser));
}

function pulserPartyValue(pulser) {
  return String(pulser?.party || pulser?.meta?.party || pulser?.card?.party || pulser?.card?.meta?.party || "").trim();
}

function isSystemPartyPulser(pulser) {
  return pulserPartyValue(pulser).toLowerCase() === "system";
}

function availableSystemPulsers(appState) {
  const knownPulsers = [
    ...(appState?.globalPlazaStatus?.pulsers || []),
    ...((appState?.workspaces || []).flatMap((workspace) => (
      (workspace?.windows || []).flatMap((windowItem) => windowItem?.browserCatalog?.pulsers || [])
    ))),
  ];
  const storagePulsers = dedupePulsers(knownPulsers.filter((pulser) => isFileStorageCatalogPulser(pulser))).sort((left, right) => (
    String(left?.name || "").localeCompare(String(right?.name || ""))
    || String(left?.address || "").localeCompare(String(right?.address || ""))
  ));
  const preferred = storagePulsers.filter((pulser) => isSystemPartyPulser(pulser));
  return preferred.length ? preferred : storagePulsers;
}

function selectedSystemPulser(preferences, pulsers) {
  const exact = (pulsers || []).find((pulser) => (
    (preferences?.fileSavePulserId && pulser.agent_id === preferences.fileSavePulserId)
    || (preferences?.fileSavePulserName && pulser.name === preferences.fileSavePulserName)
    || (preferences?.fileSavePulserAddress && pulser.address === preferences.fileSavePulserAddress)
  ));
  return exact || ((pulsers || []).length === 1 ? pulsers[0] : null);
}

function configuredSystemPulser(preferences, appState) {
  const exact = selectedSystemPulser(preferences, availableSystemPulsers(appState));
  if (exact) {
    return exact;
  }
  const agentId = String(preferences?.fileSavePulserId || "").trim();
  const name = String(preferences?.fileSavePulserName || "").trim();
  const address = String(preferences?.fileSavePulserAddress || "").trim();
  if (!agentId && !name && !address) {
    return null;
  }
  return {
    agent_id: agentId,
    name,
    address,
    practice_id: "get_pulse_data",
    supported_pulses: [
      { pulse_name: "object_save", pulse_address: "plaza://pulse/object_save", output_schema: {} },
      { pulse_name: "object_load", pulse_address: "plaza://pulse/object_load", output_schema: {} },
    ],
  };
}

function slugifyFileSaveName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 72) || "saved-result";
}

function defaultSavedFileName(title) {
  const now = new Date();
  const timestamp = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("")
    + "-"
    + [
      String(now.getHours()).padStart(2, "0"),
      String(now.getMinutes()).padStart(2, "0"),
      String(now.getSeconds()).padStart(2, "0"),
    ].join("");
  return `${slugifyFileSaveName(title)}-${timestamp}.json`;
}

function joinStorageObjectKey(prefix, fileName) {
  const cleanedPrefix = String(prefix || "").trim().replace(/^\/+|\/+$/g, "");
  const cleanedFileName = String(fileName || "").trim().replace(/^\/+/, "");
  return cleanedPrefix ? `${cleanedPrefix}/${cleanedFileName}` : cleanedFileName;
}

function mapPhemaLibraryObjectKey(prefix) {
  return joinStorageObjectKey(prefix, `${MAP_PHEMAR_STORAGE_DIRECTORY_NAME}/${MAP_PHEMA_LIBRARY_STORAGE_FILE_NAME}`);
}

function legacyMapPhemaLibraryObjectKey(prefix) {
  return joinStorageObjectKey(prefix, MAP_PHEMA_LIBRARY_STORAGE_FILE_NAME);
}

function joinLocalFilesystemPath(directory, child) {
  const cleanedDirectory = String(directory || "").trim().replace(/[\\/]+$/g, "");
  const cleanedChild = String(child || "").trim().replace(/^[\\/]+/g, "");
  if (!cleanedDirectory) {
    return cleanedChild;
  }
  return cleanedChild ? `${cleanedDirectory}/${cleanedChild}` : cleanedDirectory;
}

function pulserDisplayNameValue(pulser, fallbackName = "Pulser") {
  return String(
    pulser?.pulser_name
      || pulser?.name
      || pulser?.pulser_id
      || pulser?.agent_id
      || fallbackName,
  ).trim() || fallbackName;
}

function pulserDisplayAddressValue(pulser) {
  return String(pulser?.pulser_address || pulser?.address || "").trim();
}

function isPulserMarkedActive(pulser) {
  return Number(pulser?.last_active ?? pulser?.lastActive ?? 0) > 0;
}

function pulserActivityLabel(pulser) {
  return isPulserMarkedActive(pulser) ? "Active" : "Inactive";
}

function formatPulserDisplayName(pulser, { includeAddress = false, fallbackName = "Pulser" } = {}) {
  const name = pulserDisplayNameValue(pulser, fallbackName);
  const address = pulserDisplayAddressValue(pulser);
  const parts = [name, pulserActivityLabel(pulser)];
  if (includeAddress && address) {
    parts.push(address);
  }
  return parts.join(" · ");
}

function formatCompatiblePulserOptionLabel(pulser, options = {}) {
  return formatPulserDisplayName({
    pulser_name: pulser?.pulser_name,
    pulser_id: pulser?.pulser_id,
    pulser_address: pulser?.pulser_address,
    last_active: pulser?.last_active,
  }, options);
}

function formatConfiguredSystemPulserLabel(preferences, pulser, options = {}) {
  if (pulser) {
    return formatPulserDisplayName(pulser, options);
  }
  const fallbackName = String(preferences?.fileSavePulserName || preferences?.fileSavePulserId || "").trim();
  if (!fallbackName) {
    return "Unset SystemPulser";
  }
  return formatPulserDisplayName({
    name: fallbackName,
    address: String(preferences?.fileSavePulserAddress || "").trim(),
    last_active: 0,
  }, { ...options, fallbackName });
}

function formatPulseExecutionLabel(pulseName, pulserName, pulserActive = null) {
  const parts = [];
  if (pulseName) {
    parts.push(pulseName);
  }
  if (pulserName) {
    parts.push(pulserActive === null ? pulserName : `${pulserName} · ${pulserActive ? "Active" : "Inactive"}`);
  }
  return parts.join(" · ") || "Pulse node";
}

function normalizePulserAgent(agent, plazaName) {
  if (!agent || typeof agent !== "object") {
    return null;
  }
  const card = agent.card && typeof agent.card === "object" ? agent.card : {};
  const meta = agent.meta && typeof agent.meta === "object" ? agent.meta : {};
  const cardMeta = card.meta && typeof card.meta === "object" ? card.meta : {};
  const pitType = String(agent.pit_type || card.pit_type || agent.type || card.type || "").trim();
  const rawPractices = Array.isArray(agent.practices)
    ? agent.practices
    : (Array.isArray(card.practices) ? card.practices : []);
  const rawSupportedPulses = Array.isArray(agent.supported_pulses)
    ? agent.supported_pulses
    : (Array.isArray(meta.supported_pulses)
      ? meta.supported_pulses
      : (Array.isArray(cardMeta.supported_pulses) ? cardMeta.supported_pulses : []));
  const hasPulserIdentity = Boolean(
    String(agent.agent_id || card.agent_id || "").trim()
    || String(agent.name || card.name || "").trim()
    || String(agent.address || card.address || "").trim()
    || String(agent.practice_id || agent.practiceId || "").trim()
    || rawSupportedPulses.length,
  );
  if (pitType && pitType !== "Pulser") {
    return null;
  }
  if (!pitType && !hasPulserIdentity) {
    return null;
  }
  const practices = rawPractices
    .map((entry) => normalizePracticeEntry(entry))
    .filter(Boolean);
  const supportedPulses = dedupeSupportedPulses(
    rawSupportedPulses
      .map((entry) => normalizeSupportedPulseEntry(entry))
      .filter(Boolean),
  );
  return {
    agent_id: String(agent.agent_id || card.agent_id || "").trim(),
    name: String(agent.name || card.name || "Unnamed Pulser"),
    address: String(card.address || agent.address || "").trim(),
    description: String(agent.description || card.description || ""),
    owner: String(agent.owner || card.owner || ""),
    party: String(agent.party || card.party || meta.party || cardMeta.party || "").trim(),
    practice_id: String(agent.practice_id || agent.practiceId || defaultPracticeId(practices)).trim() || defaultPracticeId(practices),
    practices,
    supported_pulses: supportedPulses,
    last_active: Number(agent.last_active ?? agent.lastActive ?? 0),
    plaza_name: String(agent.plaza_name || agent.plazaName || plazaName || ""),
    pulse_count: Number((agent.pulse_count ?? agent.pulseCount ?? supportedPulses.length) || supportedPulses.length),
  };
}

function standardizeCatalogPayload(payload, plazaUrl) {
  const normalizedUrl = normalizePlazaUrl(plazaUrl || payload?.plaza_url || payload?.plazaUrl || "");
  const plazaSummaries = Array.isArray(payload?.plazas) ? payload.plazas : [];
  const rawPulsers = Array.isArray(payload?.pulsers) ? payload.pulsers : [];
  const plazaDerivedPulsers = plazaSummaries.flatMap((plaza) => {
    if (!plaza || typeof plaza !== "object") {
      return [];
    }
    const card = plaza.card && typeof plaza.card === "object" ? plaza.card : {};
    const plazaName = String(card.name || plaza.name || plaza.url || "Plaza");
    return (Array.isArray(plaza.agents) ? plaza.agents : [])
      .map((agent) => normalizePulserAgent(agent, plazaName))
      .filter(Boolean);
  });
  const pulsers = dedupePulsers(
    [...rawPulsers, ...plazaDerivedPulsers]
      .map((entry) => normalizePulserAgent(entry, entry?.plaza_name || entry?.plazaName || ""))
      .filter(Boolean),
  ).sort((left, right) => (
    String(left?.name || "").localeCompare(String(right?.name || ""))
    || String(left?.address || "").localeCompare(String(right?.address || ""))
  ));
  const rawPulses = Array.isArray(payload?.pulses) ? payload.pulses : [];
  const pulses = dedupeCatalogPulses(
    (rawPulses.length ? rawPulses : pulsers.flatMap((pulser) => pulser.supported_pulses || []))
      .map((entry) => normalizeCatalogPulseEntry(entry))
      .filter(Boolean),
  ).sort((left, right) => (
    String(left?.pulse_name || "").localeCompare(String(right?.pulse_name || ""))
    || String(left?.pulse_address || "").localeCompare(String(right?.pulse_address || ""))
  ));
  const uniquePulseKeys = new Set(
    pulses
      .map((pulse) => String(pulse?.pulse_address || pulse?.pulse_name || pulse?.pulse_id || "").trim())
      .filter(Boolean),
  );
  return {
    ...payload,
    status: String(payload?.status || "success"),
    connected: Boolean(payload?.connected ?? true),
    error: String(payload?.error || ""),
    plazaUrl: normalizedUrl,
    plaza_url: normalizedUrl,
    pulsers,
    pulses,
    plazas: plazaSummaries,
    pulserCount: Number((payload?.pulserCount ?? payload?.pulser_count ?? pulsers.length) || 0),
    pulseCount: Number((payload?.pulseCount ?? payload?.pulse_count ?? uniquePulseKeys.size) || 0),
    pulser_count: Number((payload?.pulser_count ?? payload?.pulserCount ?? pulsers.length) || 0),
    pulse_count: Number((payload?.pulse_count ?? payload?.pulseCount ?? uniquePulseKeys.size) || 0),
  };
}

function normalizeDirectPlazaCatalog(payload, plazaUrl, pulsesPayload = null) {
  const normalizedUrl = normalizePlazaUrl(plazaUrl);
  const plazas = Array.isArray(payload?.plazas) ? payload.plazas : [];
  const pulserRows = [];
  const plazaSummaries = [];

  plazas.forEach((plaza) => {
    if (!plaza || typeof plaza !== "object") {
      return;
    }
    const card = plaza.card && typeof plaza.card === "object" ? plaza.card : {};
    const plazaName = String(card.name || plaza.url || "Plaza");
    plazaSummaries.push({
      name: plazaName,
      url: String(plaza.url || normalizedUrl),
      online: Boolean(plaza.online ?? true),
    });
    (Array.isArray(plaza.agents) ? plaza.agents : []).forEach((agent) => {
      const pulser = normalizePulserAgent(agent, plazaName);
      if (pulser) {
        pulserRows.push(pulser);
      }
    });
  });

  const pulsers = dedupePulsers(pulserRows).sort((left, right) => (
    String(left.name || "").localeCompare(String(right.name || ""))
    || String(left.address || "").localeCompare(String(right.address || ""))
  ));

  const catalogPulseEntries = Array.isArray(pulsesPayload?.pulses)
    ? pulsesPayload.pulses.map((entry) => normalizeCatalogPulseEntry(entry)).filter(Boolean)
    : [];
  const pulses = dedupeCatalogPulses(
    catalogPulseEntries.length
      ? catalogPulseEntries
      : pulsers.flatMap((pulser) => pulser.supported_pulses || []),
  ).sort((left, right) => (
    String(left.pulse_name || "").localeCompare(String(right.pulse_name || ""))
    || String(left.pulse_address || "").localeCompare(String(right.pulse_address || ""))
  ));

  return standardizeCatalogPayload({
    status: "success",
    connected: true,
    plaza_url: normalizedUrl,
    plazas: plazaSummaries,
    pulsers,
    pulses,
  }, normalizedUrl);
}

function buildCatalogErrorMessage(plazaUrl, message, isStarting = false) {
  const normalizedUrl = normalizePlazaUrl(plazaUrl);
  if (isStarting) {
    return `Plaza at ${normalizedUrl} is online but still starting. Wait a few seconds and refresh.`;
  }
  return message || `Unable to load Plaza catalog from ${normalizedUrl}.`;
}

async function requestCatalogDirect(plazaUrl) {
  const normalizedUrl = normalizePlazaUrl(plazaUrl);
  if (!normalizedUrl) {
    throw new Error("Plaza URL is required.");
  }

  const catalogResponse = await fetch(`${normalizedUrl}/api/plazas_status?pit_type=Pulser`);
  const catalogPayload = await loadJsonResponse(catalogResponse);
  if (!catalogResponse.ok) {
    const detail = String(catalogPayload?.detail || catalogPayload?.message || "");
    let healthOkay = false;
    try {
      const healthResponse = await fetch(`${normalizedUrl}/health`);
      healthOkay = healthResponse.ok;
    } catch (error) {
      healthOkay = false;
    }
    throw new Error(buildCatalogErrorMessage(
      normalizedUrl,
      detail || `Catalog request failed with ${catalogResponse.status}.`,
      healthOkay && catalogResponse.status === 503 && detail.toLowerCase() === "starting",
    ));
  }

  let pulsesPayload = null;
  try {
    const pulsesResponse = await fetch(`${normalizedUrl}/api/plaza/pulses`);
    if (pulsesResponse.ok) {
      pulsesPayload = await loadJsonResponse(pulsesResponse);
    }
  } catch (error) {
    pulsesPayload = null;
  }

  return normalizeDirectPlazaCatalog(catalogPayload, normalizedUrl, pulsesPayload);
}

async function runBrowserPaneDirect(payload) {
  const normalizedUrl = normalizePlazaUrl(payload?.plaza_url || payload?.plazaUrl || "");
  const requestPayload = {
    pulser_id: payload?.pulser_id || "",
    pulser_name: payload?.pulser_name || "",
    pulser_address: payload?.pulser_address || "",
    practice_id: payload?.practice_id || "",
    pulse_name: payload?.pulse_name || "",
    pulse_address: payload?.pulse_address || "",
    output_schema: payload?.output_schema || {},
    input: payload?.input ?? {},
  };
  const response = await fetch(`${normalizedUrl}/api/pulsers/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  const responsePayload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(responsePayload?.detail || responsePayload?.message || "Pulser execution failed.");
  }
  return responsePayload;
}

function nestedPulserResponseErrorMessage(payload, depth = 0) {
  if (depth > 5 || !(payload && typeof payload === "object")) {
    return "";
  }
  const explicitError = String(payload.error || "").trim();
  if (explicitError) {
    return explicitError;
  }
  const status = String(payload.status || "").trim().toLowerCase();
  if (status === "error") {
    const statusMessage = String(payload.detail || payload.message || "").trim();
    if (statusMessage) {
      return statusMessage;
    }
  }
  if (payload.result && typeof payload.result === "object") {
    return nestedPulserResponseErrorMessage(payload.result, depth + 1);
  }
  return "";
}

function createPulserResponseError(message, fallbackMessage = "Pulser request failed.") {
  const normalizedMessage = String(message || fallbackMessage).trim() || fallbackMessage;
  const error = new Error(normalizedMessage);
  const loweredMessage = normalizedMessage.toLowerCase();
  if (
    loweredMessage.includes("not found")
    || loweredMessage.includes("does not exist")
    || loweredMessage.includes("was not found")
  ) {
    error.code = "not_found";
  }
  return error;
}

function unwrapStoragePulserPayload(payload, fallbackMessage = "Storage request failed.") {
  const nestedError = nestedPulserResponseErrorMessage(payload);
  if (nestedError) {
    throw createPulserResponseError(nestedError, fallbackMessage);
  }
  if (payload && typeof payload === "object" && payload.result !== undefined) {
    return payload.result;
  }
  return payload;
}

async function runPulserRequest(requestPayload) {
  let payload;
  try {
    const response = await fetch("/api/plaza/panes/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
    });
    payload = await loadJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || "Pulser execution failed.");
    }
  } catch (proxyError) {
    payload = await runBrowserPaneDirect(requestPayload);
  }
  return payload;
}

async function evaluateMindMapBranchCondition(expression, inputPayload) {
  const response = await fetch("/api/plaza/branch/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      expression: String(expression || ""),
      input: inputPayload ?? {},
    }),
  });
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || "Branch condition evaluation failed.");
  }
  return Boolean(payload?.result);
}

function resolveMapPhemaAppState(appState = null) {
  if (appState && typeof appState === "object") {
    return appState;
  }
  const preferences = normalizePreferences(loadStorage(currentPreferenceStorageKey(), {}), BOOTSTRAP);
  return {
    preferences,
    plazaAccess: createDefaultPlazaAccessState(preferences.connectionPlazaUrl),
    globalPlazaStatus: emptyCatalog(preferences.connectionPlazaUrl),
    workspaces: [],
  };
}

function emptyMapPhemaLibrary() {
  return { phemas: [] };
}

function normalizeMapPhemaLibrary(candidate) {
  const parsed = parseWorkspaceLayoutContentCandidate(candidate);
  if (Array.isArray(parsed)) {
    return { phemas: parsed };
  }
  if (!(parsed && typeof parsed === "object")) {
    return null;
  }
  if (Array.isArray(parsed.phemas)) {
    return {
      ...parsed,
      phemas: parsed.phemas,
    };
  }
  for (const key of ["items", "rows", "documents", "saved_phemas", "supported_phemas"]) {
    if (Array.isArray(parsed[key])) {
      return { phemas: parsed[key] };
    }
  }
  if (parsed.phema && typeof parsed.phema === "object" && !Array.isArray(parsed.phema)) {
    return { phemas: [parsed.phema] };
  }
  if ((parsed.phema_id || parsed.id) && (parsed.name || Array.isArray(parsed.sections) || parsed.meta)) {
    return { phemas: [parsed] };
  }
  return null;
}

function isMapPhemaLibrary(candidate) {
  return Boolean(normalizeMapPhemaLibrary(candidate));
}

function extractMapPhemaLibrary(payload) {
  const seen = new Set();

  function visit(candidate, depth = 0) {
    if (depth > 6 || candidate === null || candidate === undefined) {
      return null;
    }
    const normalized = normalizeMapPhemaLibrary(candidate);
    if (normalized) {
      return normalized;
    }
    const parsed = parseWorkspaceLayoutContentCandidate(candidate);
    if (!(parsed && typeof parsed === "object")) {
      return null;
    }
    if (Array.isArray(parsed)) {
      for (const entry of parsed) {
        const nested = visit(entry, depth + 1);
        if (nested) {
          return nested;
        }
      }
      return null;
    }
    if (seen.has(parsed)) {
      return null;
    }
    seen.add(parsed);
    const preferredKeys = ["data", "content", "result", "payload", "file", "body", "document", "value", "text"];
    for (const key of preferredKeys) {
      if (!Object.prototype.hasOwnProperty.call(parsed, key)) {
        continue;
      }
      const nested = visit(parsed[key], depth + 1);
      if (nested) {
        return nested;
      }
    }
    for (const value of Object.values(parsed)) {
      const nested = visit(value, depth + 1);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  return visit(payload);
}

function filterMapPhemaRows(rows, query = "") {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  const orderedRows = [...(Array.isArray(rows) ? rows : [])].sort((left, right) => (
    String(right?.updated_at || right?.created_at || "").localeCompare(String(left?.updated_at || left?.created_at || ""))
  ));
  if (!normalizedQuery) {
    return orderedRows;
  }
  return orderedRows.filter((entry) => {
    const tags = Array.isArray(entry?.tags) ? entry.tags.join(" ") : "";
    const haystack = [
      entry?.name,
      entry?.phema_id,
      entry?.id,
      entry?._storage?.relative_path,
      entry?._storage?.file_name,
      entry?.description,
      tags,
    ].join(" ").toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

function phemaDialogRowLabel(phema) {
  return String(
    phema?._storage?.relative_path
      || phema?._storage?.file_name
      || phema?.name
      || phema?.phema_id
      || phema?.id
      || "Untitled Phema",
  ).trim() || "Untitled Phema";
}

function phemaDialogRowTimestamp(phema) {
  return new Date(phema?.updated_at || phema?.created_at || Date.now()).toLocaleString();
}

function phemaDialogRowTitle(phema) {
  const label = phemaDialogRowLabel(phema);
  const name = String(phema?.name || "").trim();
  const timestamp = phemaDialogRowTimestamp(phema);
  return [label, name && name !== label ? `Phema: ${name}` : "", timestamp].filter(Boolean).join("\n");
}

function normalizeMapPhemaRecord(phema, existing = null) {
  const source = phema && typeof phema === "object" ? cloneValue(phema) : {};
  const now = new Date().toISOString();
  const phemaId = String(
    source.phema_id
      || source.id
      || existing?.phema_id
      || existing?.id
      || createId("phema"),
  ).trim();
  return {
    ...(existing && typeof existing === "object" ? cloneValue(existing) : {}),
    ...source,
    phema_id: phemaId,
    id: phemaId,
    created_at: String(existing?.created_at || source.created_at || now),
    updated_at: now,
  };
}

async function loadMapPhemaLibraryFromConfiguredStorage(appState) {
  const target = mapPhemaStorageTarget(appState.preferences, appState);
  if (target.backend !== "system_pulser") {
    throw new Error("MapPhemar configured storage is not using a SystemPulser.");
  }
  if (!target.pulser) {
    throw new Error("Choose a SystemPulser in Settings before loading saved Phemas.");
  }
  if (!target.bucketName || target.bucketName === "unset bucket") {
    throw new Error("Set a default SystemPulser bucket name in Settings before loading saved Phemas.");
  }
  const loadPulse = fileStoragePulserLoadPulse(target.pulser);
  async function loadObjectKey(objectKey) {
    const payload = await runPulserRequest({
      plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
      pulser_id: target.pulser.agent_id || "",
      pulser_name: target.pulser.name || "",
      pulser_address: target.pulser.address || "",
      practice_id: target.pulser.practice_id || "get_pulse_data",
      pulse_name: loadPulse?.pulse_name || "object_load",
      pulse_address: loadPulse?.pulse_address || "",
      output_schema: loadPulse?.output_schema || {},
      input: {
        bucket_name: target.bucketName,
        object_key: objectKey,
        response_format: "json",
      },
    });
    const content = extractMapPhemaLibrary(payload);
    if (!(content && typeof content === "object")) {
      throw new Error("The saved Phema library at this location is not a MapPhemar JSON document yet.");
    }
    return content;
  }

  const candidateKeys = [target.objectKey, target.legacyObjectKey].filter(Boolean);
  const triedKeys = new Set();
  let lastRecoverableError = null;
  for (const objectKey of candidateKeys) {
    if (triedKeys.has(objectKey)) {
      continue;
    }
    triedKeys.add(objectKey);
    try {
      return await loadObjectKey(objectKey);
    } catch (error) {
      if (!isMissingStorageDocumentError(error) && !isInvalidMapPhemaLibraryError(error)) {
        throw error;
      }
      lastRecoverableError = error;
    }
  }
  throw lastRecoverableError || new Error("Unable to load saved Phemas.");
}

async function saveMapPhemaLibraryToConfiguredStorage(library, appState) {
  const target = mapPhemaStorageTarget(appState.preferences, appState);
  if (target.backend !== "system_pulser") {
    throw new Error("MapPhemar configured storage is not using a SystemPulser.");
  }
  if (!target.pulser) {
    throw new Error("Choose a SystemPulser in Settings before saving Phemas.");
  }
  if (!target.bucketName || target.bucketName === "unset bucket") {
    throw new Error("Set a default SystemPulser bucket name in Settings before saving Phemas.");
  }
  const savePulse = fileStoragePulserSavePulse(target.pulser);
  await runPulserRequest({
    plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
    pulser_id: target.pulser.agent_id || "",
    pulser_name: target.pulser.name || "",
    pulser_address: target.pulser.address || "",
    practice_id: target.pulser.practice_id || "get_pulse_data",
    pulse_name: savePulse?.pulse_name || "object_save",
    pulse_address: savePulse?.pulse_address || "",
    output_schema: savePulse?.output_schema || {},
    input: {
      bucket_name: target.bucketName,
      object_key: target.objectKey,
      data: cloneValue(library),
      metadata: {
        document_type: "map_phemas",
        saved_at: new Date().toISOString(),
      },
    },
  });
  return target;
}

async function fetchMapPhemaLibrary(query = "", appState = null) {
  const storageState = resolveMapPhemaAppState(appState);
  const target = mapPhemaStorageTarget(storageState.preferences, storageState);
  if (target.backend === "system_pulser") {
    try {
      const library = await loadMapPhemaLibraryFromConfiguredStorage(storageState);
      return filterMapPhemaRows(library?.phemas || [], query);
    } catch (error) {
      if (isMissingStorageDocumentError(error) || isInvalidMapPhemaLibraryError(error)) {
        return [];
      }
      throw error;
    }
  }

  const response = await fetch(buildMapPhemarRequestUrl(PHEMA_API_PREFIX, {
    q: String(query || "").trim(),
  }, target.directory));
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || "Unable to load saved Phemas.");
  }
  return Array.isArray(payload?.phemas) ? payload.phemas : [];
}

async function fetchMapPhema(phemaId, appState = null) {
  const storageState = resolveMapPhemaAppState(appState);
  const target = mapPhemaStorageTarget(storageState.preferences, storageState);
  if (target.backend === "system_pulser") {
    const library = await loadMapPhemaLibraryFromConfiguredStorage(storageState);
    const phema = (library?.phemas || []).find((entry) => String(entry?.phema_id || entry?.id || "") === String(phemaId || "").trim()) || null;
    if (!(phema && typeof phema === "object")) {
      throw new Error(`Phema '${String(phemaId || "").trim()}' was not found.`);
    }
    return phema;
  }

  const response = await fetch(buildMapPhemarRequestUrl(
    `${PHEMA_API_PREFIX}/${encodeURIComponent(String(phemaId || ""))}`,
    null,
    target.directory,
  ));
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || "Unable to load the selected Phema.");
  }
  if (!(payload?.phema && typeof payload.phema === "object")) {
    throw new Error("The selected Phema payload is invalid.");
  }
  return payload.phema;
}

async function saveMapPhemaPayload(phema, appState = null) {
  const storageState = resolveMapPhemaAppState(appState);
  const target = mapPhemaStorageTarget(storageState.preferences, storageState);
  if (target.backend === "system_pulser") {
    if (!(phema && typeof phema === "object")) {
      throw new Error("Phema payload must be a JSON object.");
    }
    if (!String(phema.name || "").trim()) {
      throw new Error("Phema name is required.");
    }
    let library = emptyMapPhemaLibrary();
    try {
      library = await loadMapPhemaLibraryFromConfiguredStorage(storageState);
    } catch (error) {
      if (!isMissingStorageDocumentError(error) && !isInvalidMapPhemaLibraryError(error)) {
        throw error;
      }
    }
    const rows = Array.isArray(library?.phemas) ? [...library.phemas] : [];
    const existingIndex = rows.findIndex((entry) => (
      String(entry?.phema_id || entry?.id || "") === String(phema?.phema_id || phema?.id || "").trim()
    ));
    const existing = existingIndex >= 0 ? rows[existingIndex] : null;
    const saved = normalizeMapPhemaRecord(phema, existing);
    if (existingIndex >= 0) {
      rows.splice(existingIndex, 1);
    }
    rows.unshift(saved);
    await saveMapPhemaLibraryToConfiguredStorage({ phemas: rows }, storageState);
    return saved;
  }

  const response = await fetch(buildMapPhemarRequestUrl(PHEMA_API_PREFIX, null, target.directory), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phema }),
  });
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || "Unable to save the diagram as a Phema.");
  }
  if (!(payload?.phema && typeof payload.phema === "object")) {
    throw new Error("The saved Phema response is invalid.");
  }
  return payload.phema;
}

async function saveLocalJsonFilePayload(filePayload) {
  const response = await fetch("/api/files/save/local", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filePayload || {}),
  });
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || "Unable to save the file locally.");
  }
  if (!(payload?.file && typeof payload.file === "object")) {
    throw new Error("The local file save response is invalid.");
  }
  return payload.file;
}

async function loadLocalJsonFilePayload(filePayload) {
  const response = await fetch("/api/files/load/local", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(filePayload || {}),
  });
  const payload = await loadJsonResponse(response);
  if (!response.ok) {
    const error = new Error(payload?.detail || payload?.message || "Unable to load the file locally.");
    if (response.status === 404) {
      error.code = "not_found";
    }
    throw error;
  }
  if (!(payload?.file && typeof payload.file === "object")) {
    throw new Error("The local file load response is invalid.");
  }
  return payload.file;
}

function workspaceLayoutStorageTarget(preferences, appState) {
  if (normalizeFileSaveBackend(preferences?.fileSaveBackend) === "system_pulser") {
    const pulser = configuredSystemPulser(preferences, appState);
    const pulserLabel = formatConfiguredSystemPulserLabel(preferences, pulser);
    const bucketName = String(preferences?.fileSaveBucketName || "unset bucket").trim();
    const objectKey = joinStorageObjectKey(preferences?.fileSaveObjectPrefix, WORKSPACE_LAYOUT_STORAGE_FILE_NAME);
    return {
      backend: "system_pulser",
      label: `SystemPulser · ${pulserLabel}`,
      detail: `${bucketName}/${objectKey}`,
      objectKey,
      bucketName,
      pulser,
    };
  }
  const directory = String(preferences?.fileSaveLocalDirectory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY).trim();
  return {
    backend: "filesystem",
    label: "Local Filesystem",
    detail: `${directory.replace(/[\\/]+$/, "")}/${WORKSPACE_LAYOUT_STORAGE_FILE_NAME}`,
    directory,
  };
}

function mapPhemaStorageTarget(preferences, appState = null) {
  const inheritedSettings = (
    !IS_MAP_PHEMAR_MODE
    || MAP_PHEMAR_SETTINGS_SCOPE !== "map_phemar"
    || MAP_PHEMAR_STORAGE_SETTINGS_MODE === "inherited"
  );
  const scopeLabel = inheritedSettings
    ? (MAP_PHEMAR_SETTINGS_SCOPE === "personal_agent" ? "Personal Agent" : "Inherited")
    : "MapPhemar";
  if (normalizeFileSaveBackend(preferences?.fileSaveBackend) === "system_pulser") {
    const pulser = configuredSystemPulser(preferences, appState);
    const pulserLabel = formatConfiguredSystemPulserLabel(preferences, pulser);
    const bucketName = String(preferences?.fileSaveBucketName || "unset bucket").trim();
    const objectKey = mapPhemaLibraryObjectKey(preferences?.fileSaveObjectPrefix);
    const legacyObjectKey = legacyMapPhemaLibraryObjectKey(preferences?.fileSaveObjectPrefix);
    return {
      backend: "system_pulser",
      label: `${scopeLabel} · ${pulserLabel}`,
      detail: `${bucketName}/${objectKey}`,
      objectKey,
      legacyObjectKey,
      bucketName,
      pulser,
    };
  }
  const directory = String(
    preferences?.fileSaveLocalDirectory
      || defaultMapPhemarStorageDirectory()
      || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY,
  ).trim();
  const storageRoot = joinLocalFilesystemPath(directory, MAP_PHEMAR_STORAGE_DIRECTORY_NAME);
  return {
    backend: "filesystem",
    label: `${scopeLabel} · Local Filesystem`,
    detail: storageRoot,
    directory,
    storageRoot,
  };
}

function isMissingStorageDocumentError(error) {
  const message = String(error?.message || "").toLowerCase();
  return error?.code === "not_found"
    || message.includes("not found")
    || message.includes("does not exist")
    || message.includes("was not found");
}

function isInvalidMapPhemaLibraryError(error) {
  return String(error?.message || "").toLowerCase().includes("not a mapphemar json document");
}

function parseWorkspaceLayoutContentCandidate(candidate) {
  if (candidate && typeof candidate === "object") {
    return candidate;
  }
  if (typeof candidate !== "string" || !candidate.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(candidate);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (error) {
    return null;
  }
}

function normalizeWorkspaceLayoutLibrary(candidate) {
  const parsed = parseWorkspaceLayoutContentCandidate(candidate);
  if (Array.isArray(parsed)) {
    return { snapshots: parsed };
  }
  if (!(parsed && typeof parsed === "object")) {
    return null;
  }
  if (Array.isArray(parsed.snapshots)) {
    return {
      ...parsed,
      snapshots: parsed.snapshots,
    };
  }
  for (const key of ["layouts", "workspaceLayouts"]) {
    if (Array.isArray(parsed[key])) {
      return { snapshots: parsed[key] };
    }
  }
  return null;
}

function extractWorkspaceLayoutLibrary(payload) {
  const seen = new WeakSet();

  function visit(candidate, depth = 0) {
    if (depth > 6 || candidate === null || candidate === undefined) {
      return null;
    }
    const normalized = normalizeWorkspaceLayoutLibrary(candidate);
    if (normalized) {
      return normalized;
    }
    const parsed = parseWorkspaceLayoutContentCandidate(candidate);
    if (!(parsed && typeof parsed === "object")) {
      return null;
    }
    if (seen.has(parsed)) {
      return null;
    }
    seen.add(parsed);
    if (Array.isArray(parsed)) {
      for (const entry of parsed) {
        const nested = visit(entry, depth + 1);
        if (nested) {
          return nested;
        }
      }
      return null;
    }
    const preferredKeys = ["data", "content", "result", "payload", "file", "body", "document", "value", "text"];
    for (const key of preferredKeys) {
      if (!Object.prototype.hasOwnProperty.call(parsed, key)) {
        continue;
      }
      const nested = visit(parsed[key], depth + 1);
      if (nested) {
        return nested;
      }
    }
    for (const value of Object.values(parsed)) {
      const nested = visit(value, depth + 1);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  return visit(payload);
}

function isBrowserSnapshotLibrary(candidate) {
  if (!(candidate && typeof candidate === "object") || Array.isArray(candidate)) {
    return false;
  }
  const values = Object.values(candidate);
  if (!values.length) {
    return true;
  }
  return values.some((entry) => entry && typeof entry === "object" && Array.isArray(entry.snapshots));
}

function extractBrowserSnapshotLibrary(payload) {
  const seen = new WeakSet();

  function visit(candidate, depth = 0) {
    if (depth > 6 || candidate === null || candidate === undefined) {
      return null;
    }
    const parsed = parseWorkspaceLayoutContentCandidate(candidate);
    if (!(parsed && typeof parsed === "object")) {
      return null;
    }
    if (Array.isArray(parsed)) {
      for (const entry of parsed) {
        const nested = visit(entry, depth + 1);
        if (nested) {
          return nested;
        }
      }
      return null;
    }
    if (seen.has(parsed)) {
      return null;
    }
    seen.add(parsed);
    const preferredKeys = ["data", "content", "result", "payload", "file", "body", "document", "value", "text"];
    for (const key of preferredKeys) {
      if (!Object.prototype.hasOwnProperty.call(parsed, key)) {
        continue;
      }
      const nested = visit(parsed[key], depth + 1);
      if (nested) {
        return nested;
      }
    }
    if (isBrowserSnapshotLibrary(parsed)) {
      return parsed;
    }
    for (const value of Object.values(parsed)) {
      const nested = visit(value, depth + 1);
      if (nested) {
        return nested;
      }
    }
    return null;
  }

  return visit(payload);
}

async function saveWorkspaceLayoutLibraryToConfiguredStorage(library, appState) {
  const target = workspaceLayoutStorageTarget(appState.preferences, appState);
  if (target.backend === "system_pulser") {
    if (!target.pulser) {
      throw new Error("Choose a SystemPulser in Settings before saving a workspace.");
    }
    if (!target.bucketName || target.bucketName === "unset bucket") {
      throw new Error("Set a default SystemPulser bucket name in Settings before saving a workspace.");
    }
    const savePulse = fileStoragePulserSavePulse(target.pulser);
    await runPulserRequest({
      plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
      pulser_id: target.pulser.agent_id || "",
      pulser_name: target.pulser.name || "",
      pulser_address: target.pulser.address || "",
      practice_id: target.pulser.practice_id || "get_pulse_data",
      pulse_name: savePulse?.pulse_name || "object_save",
      pulse_address: savePulse?.pulse_address || "",
      output_schema: savePulse?.output_schema || {},
      input: {
        bucket_name: target.bucketName,
        object_key: target.objectKey,
        data: cloneValue(library),
        metadata: {
          document_type: "workspace_layouts",
          saved_at: new Date().toISOString(),
        },
      },
    });
    return target;
  }

  await saveLocalJsonFilePayload({
    directory: target.directory,
    file_name: WORKSPACE_LAYOUT_STORAGE_FILE_NAME,
    title: WORKSPACE_LAYOUT_STORAGE_TITLE,
    content: cloneValue(library),
  });
  return target;
}

async function loadWorkspaceLayoutLibraryFromConfiguredStorage(appState) {
  const target = workspaceLayoutStorageTarget(appState.preferences, appState);
  if (target.backend === "system_pulser") {
    if (!target.pulser) {
      throw new Error("Choose a SystemPulser in Settings before loading a workspace.");
    }
    if (!target.bucketName || target.bucketName === "unset bucket") {
      throw new Error("Set a default SystemPulser bucket name in Settings before loading a workspace.");
    }
    const loadPulse = fileStoragePulserLoadPulse(target.pulser);
    const payload = await runPulserRequest({
      plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
      pulser_id: target.pulser.agent_id || "",
      pulser_name: target.pulser.name || "",
      pulser_address: target.pulser.address || "",
      practice_id: target.pulser.practice_id || "get_pulse_data",
      pulse_name: loadPulse?.pulse_name || "object_load",
      pulse_address: loadPulse?.pulse_address || "",
      output_schema: loadPulse?.output_schema || {},
      input: {
        bucket_name: target.bucketName,
        object_key: target.objectKey,
        response_format: "json",
      },
    });
    const content = extractWorkspaceLayoutLibrary(payload);
    if (!(content && typeof content === "object")) {
      throw new Error("The saved workspace file at this location is not a workspace-layout JSON document yet.");
    }
    return content;
  }

  const loaded = await loadLocalJsonFilePayload({
    directory: target.directory,
    file_name: WORKSPACE_LAYOUT_STORAGE_FILE_NAME,
    title: WORKSPACE_LAYOUT_STORAGE_TITLE,
  });
  const content = extractWorkspaceLayoutLibrary(loaded?.content);
  if (!(content && typeof content === "object")) {
    throw new Error("The saved workspace layout document is invalid.");
  }
  return content;
}

async function refreshWorkspaceLayoutsFromConfiguredStorage(appState) {
  try {
    const library = await loadWorkspaceLayoutLibraryFromConfiguredStorage(appState);
    saveStorage(STORAGE_KEYS.workspaceLayouts, library);
    return Array.isArray(library?.snapshots) ? library.snapshots : [];
  } catch (error) {
    if (isMissingStorageDocumentError(error)) {
      const emptyLibrary = { snapshots: [] };
      saveStorage(STORAGE_KEYS.workspaceLayouts, emptyLibrary);
      return [];
    }
    throw error;
  }
}

async function saveBrowserSnapshotLibraryToConfiguredStorage(library, appState) {
  const target = browserLayoutStorageTarget(appState.preferences, appState);
  if (target.backend === "system_pulser") {
    if (!target.pulser) {
      throw new Error("Choose a SystemPulser in Settings before saving layouts.");
    }
    if (!target.bucketName || target.bucketName === "unset bucket") {
      throw new Error("Set a default SystemPulser bucket name in Settings before saving layouts.");
    }
    const savePulse = fileStoragePulserSavePulse(target.pulser);
    await runPulserRequest({
      plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
      pulser_id: target.pulser.agent_id || "",
      pulser_name: target.pulser.name || "",
      pulser_address: target.pulser.address || "",
      practice_id: target.pulser.practice_id || "get_pulse_data",
      pulse_name: savePulse?.pulse_name || "object_save",
      pulse_address: savePulse?.pulse_address || "",
      output_schema: savePulse?.output_schema || {},
      input: {
        bucket_name: target.bucketName,
        object_key: target.objectKey,
        data: cloneValue(library),
        metadata: {
          document_type: "browser_layouts",
          saved_at: new Date().toISOString(),
        },
      },
    });
    return target;
  }

  await saveLocalJsonFilePayload({
    directory: target.directory,
    file_name: BROWSER_LAYOUT_STORAGE_FILE_NAME,
    title: BROWSER_LAYOUT_STORAGE_TITLE,
    content: cloneValue(library),
  });
  return target;
}

async function loadBrowserSnapshotLibraryFromConfiguredStorage(appState) {
  const target = browserLayoutStorageTarget(appState.preferences, appState);
  if (target.backend === "system_pulser") {
    if (!target.pulser) {
      throw new Error("Choose a SystemPulser in Settings before loading layouts.");
    }
    if (!target.bucketName || target.bucketName === "unset bucket") {
      throw new Error("Set a default SystemPulser bucket name in Settings before loading layouts.");
    }
    const loadPulse = fileStoragePulserLoadPulse(target.pulser);
    const payload = await runPulserRequest({
      plaza_url: appState.globalPlazaStatus.plazaUrl || appState.preferences.connectionPlazaUrl,
      pulser_id: target.pulser.agent_id || "",
      pulser_name: target.pulser.name || "",
      pulser_address: target.pulser.address || "",
      practice_id: target.pulser.practice_id || "get_pulse_data",
      pulse_name: loadPulse?.pulse_name || "object_load",
      pulse_address: loadPulse?.pulse_address || "",
      output_schema: loadPulse?.output_schema || {},
      input: {
        bucket_name: target.bucketName,
        object_key: target.objectKey,
        response_format: "json",
      },
    });
    const content = extractBrowserSnapshotLibrary(payload);
    if (!(content && typeof content === "object" && !Array.isArray(content))) {
      throw new Error("The saved pane layout file at this location is not a pane-layout JSON document yet.");
    }
    return content;
  }

  const loaded = await loadLocalJsonFilePayload({
    directory: target.directory,
    file_name: BROWSER_LAYOUT_STORAGE_FILE_NAME,
    title: BROWSER_LAYOUT_STORAGE_TITLE,
  });
  const content = extractBrowserSnapshotLibrary(loaded?.content);
  if (!(content && typeof content === "object" && !Array.isArray(content))) {
    throw new Error("The saved pane layout document is invalid.");
  }
  return content;
}

async function refreshBrowserSnapshotLibraryFromConfiguredStorage(appState) {
  try {
    const library = await loadBrowserSnapshotLibraryFromConfiguredStorage(appState);
    saveStorage(STORAGE_KEYS.snapshots, library);
    return library;
  } catch (error) {
    if (isMissingStorageDocumentError(error)) {
      const emptyLibrary = {};
      saveStorage(STORAGE_KEYS.snapshots, emptyLibrary);
      return emptyLibrary;
    }
    throw error;
  }
}

function loadStorage(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function saveStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    // Local-first persistence is best-effort only.
  }
}

function loadStoredPlazaAuthSession(plazaUrl) {
  const record = loadStorage(STORAGE_KEYS.plazaAuthSession, null);
  const normalizedPlazaUrl = normalizePlazaUrl(plazaUrl);
  if (!(record && typeof record === "object")) {
    return null;
  }
  const recordPlazaUrl = normalizePlazaUrl(record.plazaUrl || "");
  const session = record.session && typeof record.session === "object" ? record.session : null;
  if (!normalizedPlazaUrl || !recordPlazaUrl || recordPlazaUrl !== normalizedPlazaUrl || !session) {
    return null;
  }
  return cloneValue(session);
}

function saveStoredPlazaAuthSession(plazaUrl, session) {
  const normalizedPlazaUrl = normalizePlazaUrl(plazaUrl);
  if (!normalizedPlazaUrl || !(session && typeof session === "object")) {
    try {
      window.localStorage.removeItem(STORAGE_KEYS.plazaAuthSession);
    } catch (error) {
      // Ignore storage cleanup failures.
    }
    return;
  }
  saveStorage(STORAGE_KEYS.plazaAuthSession, {
    plazaUrl: normalizedPlazaUrl,
    session: cloneValue(session),
  });
}

function createDefaultPlazaAccessState(plazaUrl = "") {
  const normalizedPlazaUrl = normalizePlazaUrl(plazaUrl);
  const storedSession = normalizedPlazaUrl ? loadStoredPlazaAuthSession(normalizedPlazaUrl) : null;
  return {
    session: storedSession,
    sessionPlazaUrl: storedSession ? normalizedPlazaUrl : "",
    user: null,
    authMode: "signin",
    authBusy: false,
    authMessage: "",
    identifier: "",
    password: "",
    displayName: "",
    config: null,
    configStatus: normalizedPlazaUrl ? "idle" : "error",
    configError: normalizedPlazaUrl ? "" : "Plaza URL is required.",
    keys: [],
    keysStatus: "idle",
    keysError: "",
    keyDraftName: "",
    keyBusy: false,
    keyMessage: "",
    keyReveal: null,
    pendingKeyId: "",
    pendingKeyAction: "",
  };
}

function currentPlazaAccessSession(appState) {
  const normalizedPlazaUrl = normalizePlazaUrl(appState?.preferences?.connectionPlazaUrl || "");
  const sessionPlazaUrl = normalizePlazaUrl(appState?.plazaAccess?.sessionPlazaUrl || "");
  if (!normalizedPlazaUrl || !sessionPlazaUrl || normalizedPlazaUrl !== sessionPlazaUrl) {
    return null;
  }
  return appState?.plazaAccess?.session && typeof appState.plazaAccess.session === "object"
    ? appState.plazaAccess.session
    : null;
}

function buildPlazaOwnerKeySnippet(plazaUrl, keyId, secret = "") {
  const normalizedPlazaUrl = normalizePlazaUrl(plazaUrl);
  return JSON.stringify({
    agent_card: {
      meta: {
        trusted_plaza_urls: normalizedPlazaUrl ? [normalizedPlazaUrl] : [],
        plaza_owner_key_id: String(keyId || "saved-key-id"),
        ...(secret ? { plaza_owner_key: String(secret) } : {}),
      },
    },
  }, null, 2);
}

function resetPersonalAgentStorage({ preservePreferences = false } = {}) {
  try {
    const preferenceSnapshot = preservePreferences ? loadStorage(currentPreferenceStorageKey(), null) : null;
    Object.values(STORAGE_KEYS).forEach((key) => {
      window.localStorage.removeItem(key);
    });
    if (currentPreferenceStorageKey() !== STORAGE_KEYS.preferences) {
      window.localStorage.removeItem(currentPreferenceStorageKey());
    }
    if (preservePreferences && preferenceSnapshot) {
      saveStorage(currentPreferenceStorageKey(), preferenceSnapshot);
    }
  } catch (error) {
    // Ignore storage reset failures and fall back to a plain reload.
  }
}

function createDefaultPreferences(dashboard) {
  return {
    theme: "mercury",
    sidebarCollapsed: false,
    workspaceSidebarCollapsed: false,
    defaultWorkspaceId: dashboard.workspaces?.[0]?.id || null,
    profileDisplayName: dashboard.settings?.profile_name || "Phemacast User",
    profileEmail: "user@local.phemacast",
    profileDesk: dashboard.meta?.profile || "Personal research desk",
    profileTimezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
    paymentPlan: dashboard.settings?.billing_plan || "Phemacast Personal Pro Annual",
    paymentEmail: "billing@local.phemacast",
    paymentBudget: "500",
    paymentAutopay: true,
    apiKeyOpenAI: "",
    apiKeyFinnhub: "",
    apiKeyAlphaVantage: "",
    apiKeyBroker: "",
    connectionMode: dashboard.meta?.mode || "Prototype Web Terminal",
    connectionHost: window.location.origin,
    connectionPlazaUrl: dashboard.meta?.plaza_url || "http://127.0.0.1:8011",
    operatorBossUrl: dashboard.meta?.boss_url || window.location.origin,
    operatorManagerAddress: dashboard.meta?.manager_address || "",
    operatorManagerParty: dashboard.meta?.party || "Phemacast",
    connectionDefaultParamsText: "{}",
    connectionStorage: dashboard.settings?.active_storage || "Filesystem + SQLite edge cache",
    fileSaveBackend: normalizeFileSaveBackend(dashboard.settings?.default_file_save_backend || "filesystem"),
    fileSaveLocalDirectory: String(dashboard.settings?.default_file_save_local_directory || DEFAULT_PERSONAL_AGENT_STORAGE_DIRECTORY),
    fileSavePulserId: String(dashboard.settings?.default_file_save_pulser_id || ""),
    fileSavePulserName: String(dashboard.settings?.default_file_save_pulser_name || ""),
    fileSavePulserAddress: String(dashboard.settings?.default_file_save_pulser_address || ""),
    fileSaveBucketName: String(dashboard.settings?.default_file_save_bucket_name || ""),
    fileSaveObjectPrefix: String(dashboard.settings?.default_file_save_object_prefix || ""),
    llmConfigs: [],
    llmDefaultConfigId: "",
  };
}

function normalizeModels(value) {
  const list = Array.isArray(value) ? value : String(value || "").split(/[\n,]/);
  const seen = new Set();
  return list
    .map((entry) => String(entry || "").trim())
    .filter((entry) => entry && !seen.has(entry) && seen.add(entry));
}

function createDefaultLlmConfig(index, plazaUrl) {
  return {
    id: createId("llm-config"),
    type: "api",
    name: `API Route ${index + 1}`,
    description: "",
    enabled: true,
    provider: "openai",
    model: "",
    models: [],
    baseUrl: "",
    apiKey: "",
    temperature: "0.2",
    plazaUrl,
    pulserId: "",
    pulserName: "",
    pulserAddress: "",
    practiceId: "get_pulse_data",
    pulseName: "llm_chat",
  };
}

function normalizePreferences(candidate, dashboard) {
  const defaults = createDefaultPreferences(dashboard);
  const merged = { ...defaults, ...(candidate || {}) };
  merged.connectionDefaultParamsText = typeof merged.connectionDefaultParamsText === "string"
    ? merged.connectionDefaultParamsText
    : defaults.connectionDefaultParamsText;
  merged.operatorBossUrl = typeof merged.operatorBossUrl === "string"
    ? merged.operatorBossUrl
    : defaults.operatorBossUrl;
  merged.operatorManagerAddress = typeof merged.operatorManagerAddress === "string"
    ? merged.operatorManagerAddress
    : defaults.operatorManagerAddress;
  merged.operatorManagerParty = typeof merged.operatorManagerParty === "string"
    ? merged.operatorManagerParty
    : defaults.operatorManagerParty;
  merged.fileSaveBackend = normalizeFileSaveBackend(merged.fileSaveBackend);
  merged.fileSaveLocalDirectory = typeof merged.fileSaveLocalDirectory === "string"
    ? merged.fileSaveLocalDirectory
    : defaults.fileSaveLocalDirectory;
  merged.fileSavePulserId = typeof merged.fileSavePulserId === "string" ? merged.fileSavePulserId : defaults.fileSavePulserId;
  merged.fileSavePulserName = typeof merged.fileSavePulserName === "string" ? merged.fileSavePulserName : defaults.fileSavePulserName;
  merged.fileSavePulserAddress = typeof merged.fileSavePulserAddress === "string" ? merged.fileSavePulserAddress : defaults.fileSavePulserAddress;
  merged.fileSaveBucketName = typeof merged.fileSaveBucketName === "string" ? merged.fileSaveBucketName : defaults.fileSaveBucketName;
  merged.fileSaveObjectPrefix = typeof merged.fileSaveObjectPrefix === "string" ? merged.fileSaveObjectPrefix : defaults.fileSaveObjectPrefix;
  merged.llmConfigs = Array.isArray(merged.llmConfigs)
    ? merged.llmConfigs.map((config, index) => {
        const base = createDefaultLlmConfig(index, merged.connectionPlazaUrl);
        const models = normalizeModels(config.models || config.model || "");
        return {
          ...base,
          ...config,
          type: LLM_CONFIG_TYPES.some((entry) => entry.id === config.type) ? config.type : "api",
          provider: LLM_API_PROVIDERS.includes(config.provider) ? config.provider : "custom",
          models,
          model: models[0] || "",
        };
      })
    : [];
  if (!merged.llmDefaultConfigId || !merged.llmConfigs.some((entry) => entry.id === merged.llmDefaultConfigId)) {
    merged.llmDefaultConfigId = merged.llmConfigs[0]?.id || "";
  }
  if (!THEME_OPTIONS.some((option) => option.id === merged.theme)) {
    merged.theme = defaults.theme;
  }
  return merged;
}

function emptyCatalog(plazaUrl) {
  const normalizedUrl = normalizePlazaUrl(plazaUrl);
  return {
    status: normalizedUrl ? "idle" : "error",
    connected: false,
    error: normalizedUrl ? "" : "Plaza URL is required.",
    plazaUrl: normalizedUrl,
    plaza_url: normalizedUrl,
    pulserCount: 0,
    pulseCount: 0,
    pulser_count: 0,
    pulse_count: 0,
    pulsers: [],
    pulses: [],
    plazas: [],
  };
}

function createDefaultBrowserDefaults(preferences, dashboard) {
  return {
    plazaUrl: preferences.connectionPlazaUrl || dashboard.meta?.plaza_url || "",
    symbol: "",
    symbolDraft: "",
    interval: "1d",
    startDate: "",
    endDate: "",
    limit: "64",
    extraParamsText: "{}",
  };
}

function createDefaultMindMapState(preferences, dashboard) {
  return {
    plazaUrl: preferences.connectionPlazaUrl || dashboard.meta?.plaza_url || "",
    nodes: ensureBoundaryMindMapNodes([]),
    edges: [],
    showGrid: true,
    inspectorWidth: 320,
    expandedSourcePaths: [],
    selectedNodeId: "",
    selectedEdgeId: "",
    nextNodeIndex: 0,
    nextEdgeIndex: 0,
    linkDraftFrom: "",
    linkDraftAnchor: "",
    linkDraftX: null,
    linkDraftY: null,
    linkedPhemaId: "",
    linkedPhemaName: "",
    importNotice: "",
  };
}

function createDiagramRunDialogState() {
  return {
    open: false,
    windowId: "",
    inputText: "{}",
    inputError: "",
    status: "idle",
    steps: [],
    error: "",
    startedAt: "",
    finishedAt: "",
  };
}

function createOperatorConsoleState(preferences, candidate = null) {
  const hasCandidate = Boolean(candidate && typeof candidate === "object");
  return {
    view: OPERATOR_TABS.some((entry) => entry.id === candidate?.view) ? candidate.view : "works",
    status: typeof candidate?.status === "string" ? candidate.status : "idle",
    error: typeof candidate?.error === "string" ? candidate.error : "",
    manager: candidate?.manager && typeof candidate.manager === "object" ? candidate.manager : {},
    summary: candidate?.summary && typeof candidate.summary === "object" ? candidate.summary : {},
    workers: Array.isArray(candidate?.workers) ? candidate.workers : [],
    tickets: Array.isArray(candidate?.tickets) ? candidate.tickets : [],
    schedules: Array.isArray(candidate?.schedules) ? candidate.schedules : [],
    channelCatalog: Array.isArray(candidate?.channelCatalog) && candidate.channelCatalog.length
      ? candidate.channelCatalog
      : cloneValue(DEFAULT_OPERATOR_CHANNELS),
    selectedTicketId: typeof candidate?.selectedTicketId === "string" ? candidate.selectedTicketId : "",
    selectedScheduleId: typeof candidate?.selectedScheduleId === "string" ? candidate.selectedScheduleId : "",
    selectedTicketStatus: typeof candidate?.selectedTicketStatus === "string" ? candidate.selectedTicketStatus : "idle",
    selectedTicketError: typeof candidate?.selectedTicketError === "string" ? candidate.selectedTicketError : "",
    selectedTicket: candidate?.selectedTicket || null,
    selectedJobStatus: typeof candidate?.selectedJobStatus === "string" ? candidate.selectedJobStatus : "idle",
    selectedJobError: typeof candidate?.selectedJobError === "string" ? candidate.selectedJobError : "",
    selectedJob: candidate?.selectedJob || null,
    controlStatus: typeof candidate?.controlStatus === "string" ? candidate.controlStatus : "idle",
    controlError: typeof candidate?.controlError === "string" ? candidate.controlError : "",
    lastRefreshedAt: typeof candidate?.lastRefreshedAt === "string" ? candidate.lastRefreshedAt : "",
    bossUrl: hasCandidate && typeof candidate?.bossUrl === "string"
      ? candidate.bossUrl
      : String(preferences?.operatorBossUrl || "").trim(),
    managerAddress: hasCandidate && typeof candidate?.managerAddress === "string"
      ? candidate.managerAddress
      : String(preferences?.operatorManagerAddress || "").trim(),
    managerParty: hasCandidate && typeof candidate?.managerParty === "string"
      ? candidate.managerParty
      : String(preferences?.operatorManagerParty || "").trim(),
  };
}

function createBrowserPane(type, index, preferences, dashboard) {
  const paneType = BROWSER_PANE_TYPES.some((entry) => entry.id === type) ? type : "plain_text";
  const defaultWidth = paneType === "mind_map" ? 360 : paneType === "managed_work" ? 520 : 420;
  const defaultHeight = paneType === "managed_work" ? 420 : 240;
  const column = index % 2;
  const row = Math.floor(index / 2);
  return {
    id: createId("pane"),
    type: paneType,
    title: paneType === "mind_map"
      ? `Diagram ${index + 1}`
      : paneType === "managed_work"
        ? `Managed Work ${index + 1}`
        : `Pulse Pane ${index + 1}`,
    x: 16 + column * 28 + column * defaultWidth,
    y: 16 + row * 28 + row * defaultHeight,
    width: defaultWidth,
    height: defaultHeight,
    z: index + 1,
    pulserQuery: "",
    pulseFilterText: "",
    pulserId: "",
    pulserName: "",
    pulserAddress: "",
    practiceId: "get_pulse_data",
    pulseName: "",
    pulseAddress: "",
    outputSchema: {},
    displayFormat: "json",
    chartType: "bar",
    fieldPaths: [],
    diagramDisplayMode: paneType === "mind_map" ? "diagram" : "info",
    paramsText: "{}",
    paramsExpanded: false,
    status: "idle",
    error: "",
    result: null,
    lastRunAt: "",
    saveStatus: "idle",
    saveError: "",
    lastSavedAt: "",
    lastSavedLocation: "",
    mindMapState: paneType === "mind_map" ? createDefaultMindMapState(preferences, dashboard) : null,
    operatorState: paneType === "managed_work" ? createOperatorConsoleState(preferences) : null,
  };
}

function createBrowserWindow(index, preferences, dashboard, overrides) {
  return {
    id: createId("window"),
    type: "browser",
    title: overrides?.title || "Research Browser",
    subtitle: overrides?.subtitle || "React-driven live market workspace",
    order: index,
    mode: overrides?.mode || "docked",
    x: overrides?.x || WORKSPACE_LEFT_INSET + index * 24,
    y: overrides?.y || WORKSPACE_TOP_INSET + index * 24,
    z: overrides?.z || 100 + index,
    width: overrides?.width || 980,
    height: overrides?.height || 660,
    lastDockedBounds: overrides?.lastDockedBounds || null,
    lastExternalBounds: overrides?.lastExternalBounds || null,
    browserPageMode: overrides?.browserPageMode || "view",
    browserDefaults: overrides?.browserDefaults || createDefaultBrowserDefaults(preferences, dashboard),
    browserCatalog: overrides?.browserCatalog || emptyCatalog(overrides?.browserDefaults?.plazaUrl || preferences.connectionPlazaUrl),
    panes: overrides?.panes || [],
    selectedBookmarkId: overrides?.selectedBookmarkId || "",
  };
}

function createMindMapWindow(index, preferences, dashboard, overrides) {
  return {
    id: createId("window"),
    type: "mind_map",
    title: overrides?.title || "Diagram",
    subtitle: overrides?.subtitle || "Whiteboard canvas",
    order: index,
    mode: overrides?.mode || "external",
    x: overrides?.x || WORKSPACE_LEFT_INSET + 36 + index * 24,
    y: overrides?.y || WORKSPACE_TOP_INSET + index * 24,
    z: overrides?.z || 200 + index,
    width: overrides?.width || 1080,
    height: overrides?.height || 760,
    lastDockedBounds: overrides?.lastDockedBounds || null,
    lastExternalBounds: overrides?.lastExternalBounds || null,
    zoom: overrides?.zoom || 1,
    mindMapState: overrides?.mindMapState || createDefaultMindMapState(preferences, dashboard),
    mindMapCatalog: overrides?.mindMapCatalog || emptyCatalog(overrides?.mindMapState?.plazaUrl || preferences.connectionPlazaUrl),
    mindMapError: typeof overrides?.mindMapError === "string" ? overrides.mindMapError : "",
    linkedPaneContext: overrides?.linkedPaneContext || null,
  };
}

function createWorkspaceRuntime(workspace, index, preferences, dashboard) {
  return {
    ...workspace,
    windows: [createBrowserWindow(0, preferences, dashboard, { mode: "docked" })],
  };
}

function createMapPhemarWorkspaceSummary(dashboard) {
  return {
    id: "map-phemar-workspace",
    name: dashboard.meta?.agent_name || "MapPhemar",
    focus: "Diagram editor",
    description: "Build, save, and run diagram-backed Phemas.",
  };
}

function createMapPhemarWindow(preferences, dashboard, overrides) {
  return createMindMapWindow(0, preferences, dashboard, {
    mode: "docked",
    x: WORKSPACE_LEFT_INSET,
    y: WORKSPACE_TOP_INSET,
    width: 1440,
    height: 880,
    title: dashboard.meta?.initial_phema_name || "Untitled Phema",
    subtitle: "Diagram-backed Phema",
    ...(overrides || {}),
  });
}

function normalizeBrowserDefaults(candidate, preferences, dashboard) {
  return {
    ...createDefaultBrowserDefaults(preferences, dashboard),
    ...(candidate || {}),
  };
}

function normalizeMindMapState(candidate, preferences, dashboard) {
  const normalizedNodes = ensureBoundaryMindMapNodes(Array.isArray(candidate?.nodes)
    ? candidate.nodes.map((entry, index) => normalizeMindMapNode(entry, index))
    : []);
  const normalizedMap = {
    nodes: normalizedNodes,
    edges: Array.isArray(candidate?.edges)
      ? candidate.edges.map((entry) => normalizeMindMapEdge(entry))
      : [],
  };
  syncBranchMindMapEdges(normalizedMap);
  syncBranchMindMapSchemas(normalizedMap);
  syncBoundaryMindMapSchemas(normalizedMap);
  const regularNodeCount = normalizedNodes.filter((entry) => !isBoundaryMindMapNode(entry)).length;
  return {
    ...createDefaultMindMapState(preferences, dashboard),
    ...(candidate || {}),
    nodes: normalizedMap.nodes,
    edges: normalizedMap.edges,
    showGrid: typeof candidate?.showGrid === "boolean" ? candidate.showGrid : true,
    inspectorWidth: Number.isFinite(candidate?.inspectorWidth) ? clamp(candidate.inspectorWidth, 280, 560) : 320,
    expandedSourcePaths: Array.isArray(candidate?.expandedSourcePaths)
      ? candidate.expandedSourcePaths.map((entry) => String(entry || "")).filter(Boolean)
      : [],
    nextNodeIndex: Math.max(Number(candidate?.nextNodeIndex || 0), regularNodeCount),
    nextEdgeIndex: Math.max(Number(candidate?.nextEdgeIndex || 0), normalizedMap.edges.length),
    linkedPhemaId: typeof candidate?.linkedPhemaId === "string" ? candidate.linkedPhemaId : "",
    linkedPhemaName: typeof candidate?.linkedPhemaName === "string" ? candidate.linkedPhemaName : "",
    importNotice: typeof candidate?.importNotice === "string" ? candidate.importNotice : "",
  };
}

function normalizePaneState(candidate, index, preferences, dashboard) {
  const base = createBrowserPane(candidate?.type, index, preferences, dashboard);
  const normalizedType = BROWSER_PANE_TYPES.some((entry) => entry.id === candidate?.type) ? candidate.type : base.type;
  return {
    ...base,
    ...(candidate || {}),
    type: normalizedType,
    title: typeof candidate?.title === "string" && normalizedType === candidate?.type ? candidate.title : base.title,
    pulseFilterText: typeof candidate?.pulseFilterText === "string" ? candidate.pulseFilterText : base.pulseFilterText,
    diagramDisplayMode: normalizedType === "mind_map" && candidate?.diagramDisplayMode === "info" ? "info" : base.diagramDisplayMode,
    paramsExpanded: typeof candidate?.paramsExpanded === "boolean" ? candidate.paramsExpanded : base.paramsExpanded,
    x: Number.isFinite(candidate?.x) ? candidate.x : base.x,
    y: Number.isFinite(candidate?.y) ? candidate.y : base.y,
    width: Number.isFinite(candidate?.width) ? candidate.width : base.width,
    height: Number.isFinite(candidate?.height) ? candidate.height : base.height,
    z: Number.isFinite(candidate?.z) ? candidate.z : base.z,
    mindMapState: normalizedType === "mind_map"
      ? normalizeMindMapState(candidate?.mindMapState, preferences, dashboard)
      : null,
    operatorState: normalizedType === "managed_work"
      ? createOperatorConsoleState(preferences, candidate?.operatorState)
      : null,
  };
}

function clampDockedWindowOrigin(windowItem) {
  if (!windowItem || windowItem.mode !== "docked") {
    return windowItem;
  }
  windowItem.x = Math.max(Number(windowItem.x || 0), WORKSPACE_LEFT_INSET);
  windowItem.y = Math.max(Number(windowItem.y || 0), WORKSPACE_TOP_INSET);
  if (windowItem.lastDockedBounds && typeof windowItem.lastDockedBounds === "object") {
    windowItem.lastDockedBounds.x = Math.max(Number(windowItem.lastDockedBounds.x || 0), WORKSPACE_LEFT_INSET);
    windowItem.lastDockedBounds.y = Math.max(Number(windowItem.lastDockedBounds.y || 0), WORKSPACE_TOP_INSET);
  }
  return windowItem;
}

function normalizeWorkspaceDockedOrigin(workspace) {
  if (!workspace || !Array.isArray(workspace.windows)) {
    return workspace;
  }
  const dockedWindows = workspace.windows.filter((entry) => entry.mode === "docked");
  if (!dockedWindows.length) {
    return workspace;
  }
  let minX = Infinity;
  let minY = Infinity;
  dockedWindows.forEach((windowItem) => {
    minX = Math.min(minX, Number(windowItem.x || 0));
    minY = Math.min(minY, Number(windowItem.y || 0));
  });
  const deltaX = Number.isFinite(minX) ? WORKSPACE_LEFT_INSET - minX : 0;
  const deltaY = Number.isFinite(minY) ? WORKSPACE_TOP_INSET - minY : 0;
  dockedWindows.forEach((windowItem) => {
    windowItem.x = Math.max(Math.round(Number(windowItem.x || 0) + deltaX), WORKSPACE_LEFT_INSET);
    windowItem.y = Math.max(Math.round(Number(windowItem.y || 0) + deltaY), WORKSPACE_TOP_INSET);
    if (windowItem.lastDockedBounds && typeof windowItem.lastDockedBounds === "object") {
      windowItem.lastDockedBounds.x = Math.max(Math.round(Number(windowItem.lastDockedBounds.x || 0) + deltaX), WORKSPACE_LEFT_INSET);
      windowItem.lastDockedBounds.y = Math.max(Math.round(Number(windowItem.lastDockedBounds.y || 0) + deltaY), WORKSPACE_TOP_INSET);
    }
  });
  return workspace;
}

function normalizeWindowState(candidate, index, preferences, dashboard) {
  if (candidate?.type === "mind_map") {
    const base = createMindMapWindow(index, preferences, dashboard, candidate);
    const mindMapState = normalizeMindMapState(candidate?.mindMapState, preferences, dashboard);
    return clampDockedWindowOrigin({
      ...base,
      ...(candidate || {}),
      mindMapState,
      mindMapCatalog: emptyCatalog(mindMapState.plazaUrl || preferences.connectionPlazaUrl),
    });
  }
  const base = createBrowserWindow(index, preferences, dashboard, candidate);
  const browserDefaults = normalizeBrowserDefaults(candidate?.browserDefaults, preferences, dashboard);
  return clampDockedWindowOrigin({
    ...base,
    ...(candidate || {}),
    browserDefaults,
    browserCatalog: emptyCatalog(browserDefaults.plazaUrl || preferences.connectionPlazaUrl),
    panes: Array.isArray(candidate?.panes)
      ? candidate.panes
        .filter((pane) => BROWSER_PANE_TYPES.some((entry) => entry.id === pane?.type))
        .map((pane, paneIndex) => normalizePaneState(pane, paneIndex, preferences, dashboard))
      : [],
  });
}

function normalizeWorkspaceState(workspaces, preferences, dashboard) {
  return workspaces.map((workspace, workspaceIndex) => normalizeWorkspaceDockedOrigin({
    ...workspace,
    windows: Array.isArray(workspace?.windows) && workspace.windows.length
      ? workspace.windows.map((windowItem, windowIndex) => normalizeWindowState(windowItem, windowIndex, preferences, dashboard))
      : createWorkspaceRuntime(workspace, workspaceIndex, preferences, dashboard).windows,
  }));
}

function loadSnapshots() {
  return loadStorage(STORAGE_KEYS.snapshots, {});
}

function loadWorkspaceLayouts() {
  return loadStorage(STORAGE_KEYS.workspaceLayouts, {});
}

function loadMindMapLayouts() {
  return loadStorage(STORAGE_KEYS.mindMapLayouts, {});
}

function getBrowserSnapshots(windowId) {
  const library = loadSnapshots();
  return Array.isArray(library[windowId]?.snapshots) ? library[windowId].snapshots : [];
}

function getMindMapSnapshots() {
  const library = loadMindMapLayouts();
  return Array.isArray(library?.snapshots) ? library.snapshots : [];
}

function getWorkspaceLayouts() {
  const library = loadWorkspaceLayouts();
  return Array.isArray(library?.snapshots) ? library.snapshots : [];
}

async function saveBrowserSnapshot(windowId, snapshot, appState, existingLibrary = null) {
  const library = existingLibrary && typeof existingLibrary === "object"
    ? cloneValue(existingLibrary)
    : loadSnapshots();
  const current = Array.isArray(library[windowId]?.snapshots)
    ? library[windowId].snapshots.filter((entry) => entry.name.toLowerCase() !== snapshot.name.toLowerCase())
    : [];
  library[windowId] = {
    snapshots: [snapshot, ...current].slice(0, 24),
  };
  saveStorage(STORAGE_KEYS.snapshots, library);
  if (appState) {
    await saveBrowserSnapshotLibraryToConfiguredStorage(library, appState);
  }
  return library;
}

function saveMindMapSnapshot(snapshot) {
  const current = getMindMapSnapshots().filter((entry) => entry.name.toLowerCase() !== snapshot.name.toLowerCase());
  saveStorage(STORAGE_KEYS.mindMapLayouts, {
    snapshots: [snapshot, ...current].slice(0, 24),
  });
}

async function saveWorkspaceLayout(snapshot, appState, existingLayouts = null) {
  const baseLayouts = Array.isArray(existingLayouts) ? existingLayouts : getWorkspaceLayouts();
  const current = baseLayouts.filter((entry) => entry.name.toLowerCase() !== snapshot.name.toLowerCase());
  const library = {
    snapshots: [snapshot, ...current].slice(0, 24),
  };
  saveStorage(STORAGE_KEYS.workspaceLayouts, library);
  await saveWorkspaceLayoutLibraryToConfiguredStorage(library, appState);
  return library.snapshots;
}

function rebuildWorkspaceLayout(savedWorkspace, targetWorkspaceId, preferences, dashboard) {
  const source = cloneValue(savedWorkspace || {});
  const rawWindows = Array.isArray(source.windows) ? source.windows : [];
  const windowIdMap = new Map();
  const windows = rawWindows.map((windowItem, index) => {
    const cloned = cloneValue(windowItem || {});
    const previousId = String(cloned.id || "");
    const nextId = createId("window");
    if (previousId) {
      windowIdMap.set(previousId, nextId);
    }
    cloned.id = nextId;
    return normalizeWindowState(cloned, index, preferences, dashboard);
  });

  windows.forEach((windowItem) => {
    if (windowItem.type === "mind_map" && windowItem.linkedPaneContext?.browserWindowId) {
      const remappedWindowId = windowIdMap.get(windowItem.linkedPaneContext.browserWindowId);
      if (remappedWindowId) {
        windowItem.linkedPaneContext.browserWindowId = remappedWindowId;
      }
    }
  });

  return normalizeWorkspaceDockedOrigin({
    ...source,
    id: targetWorkspaceId,
    name: String(source.name || "Workspace").trim() || "Workspace",
    windows: windows.length ? windows : createWorkspaceRuntime(source, 0, preferences, dashboard).windows,
  });
}

function serializeWindowStateForStorage(windowItem) {
  const cloned = cloneValue(windowItem || {});
  if (cloned.type === "browser") {
    delete cloned.browserCatalog;
  }
  if (cloned.type === "mind_map") {
    delete cloned.mindMapCatalog;
  }
  return cloned;
}

function serializeWorkspacesForStorage(workspaces) {
  return (Array.isArray(workspaces) ? workspaces : []).map((workspace) => ({
    ...cloneValue(workspace || {}),
    windows: Array.isArray(workspace?.windows)
      ? workspace.windows.map((windowItem) => serializeWindowStateForStorage(windowItem))
      : [],
  }));
}

function createClosedPaneConfigState() {
  return { open: false, windowId: "", paneId: "", reason: "" };
}

function createPrintDialogState() {
  return { open: false, workspaceId: "", printing: false };
}

function workspaceShortLabel(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return "WS";
  }
  return parts.slice(0, 2).map((entry) => entry[0]?.toUpperCase() || "").join("") || "WS";
}

function createMapPhemarInitialState(dashboard) {
  const preferences = normalizePreferences(loadStorage(currentPreferenceStorageKey(), {}), dashboard);
  const storedWorkspaceState = loadStorage(STORAGE_KEYS.workspaces, null);
  const storedWorkspaces = Array.isArray(storedWorkspaceState?.workspaces) ? storedWorkspaceState.workspaces : [];
  const storedMindMapWindow = storedWorkspaces
    .flatMap((workspace) => Array.isArray(workspace?.windows) ? workspace.windows : [])
    .find((windowItem) => windowItem?.type === "mind_map");
  const summary = createMapPhemarWorkspaceSummary(dashboard);
  const windowItem = storedMindMapWindow
    ? normalizeWindowState({
      ...storedMindMapWindow,
      type: "mind_map",
      mode: "docked",
      x: WORKSPACE_LEFT_INSET,
      y: WORKSPACE_TOP_INSET,
      width: Math.max(Number(storedMindMapWindow.width || 0), 1080),
      height: Math.max(Number(storedMindMapWindow.height || 0), 760),
      title: storedMindMapWindow.title || dashboard.meta?.initial_phema_name || "Untitled Phema",
      subtitle: storedMindMapWindow.subtitle || "Diagram-backed Phema",
    }, 0, preferences, dashboard)
    : createMapPhemarWindow(preferences, dashboard);
  const workspace = normalizeWorkspaceDockedOrigin({
    ...summary,
    windows: [windowItem],
  });

  return {
    dashboard,
    preferences,
    workspaces: [workspace],
    activeWorkspaceId: workspace.id,
    plazaAccess: createDefaultPlazaAccessState(preferences.connectionPlazaUrl),
    settingsOpen: false,
    settingsTab: "storage",
    settingsLlmSelectedId: preferences.llmDefaultConfigId || preferences.llmConfigs[0]?.id || "",
    paneConfig: createClosedPaneConfigState(),
    paneConfigSnapshot: null,
    snapshotDialog: { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" },
    workspaceDialog: { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" },
    printDialog: createPrintDialogState(),
    diagramRunDialog: createDiagramRunDialogState(),
    operator: createOperatorConsoleState(preferences),
    globalPlazaStatus: emptyCatalog(preferences.connectionPlazaUrl),
    nextWorkspaceIndex: 2,
    paneMenuWindowId: "",
    menuBarMenuId: "",
  };
}

function createInitialState() {
  const dashboard = BOOTSTRAP;
  try {
    if (IS_MAP_PHEMAR_MODE) {
      return createMapPhemarInitialState(dashboard);
    }
    const preferences = normalizePreferences(loadStorage(currentPreferenceStorageKey(), {}), dashboard);
    const storedWorkspaceState = loadStorage(STORAGE_KEYS.workspaces, null);
    const workspaces = Array.isArray(storedWorkspaceState?.workspaces) && storedWorkspaceState.workspaces.length
      ? storedWorkspaceState.workspaces
      : (dashboard.workspaces || []).map((workspace, index) => createWorkspaceRuntime(workspace, index, preferences, dashboard));
    const normalizedWorkspaces = normalizeWorkspaceState(workspaces, preferences, dashboard);
    const activeWorkspaceId = storedWorkspaceState?.activeWorkspaceId
      && normalizedWorkspaces.some((entry) => entry.id === storedWorkspaceState.activeWorkspaceId)
        ? storedWorkspaceState.activeWorkspaceId
        : preferences.defaultWorkspaceId && normalizedWorkspaces.some((entry) => entry.id === preferences.defaultWorkspaceId)
          ? preferences.defaultWorkspaceId
          : normalizedWorkspaces[0]?.id || "";

    return {
      dashboard,
      preferences,
      workspaces: normalizedWorkspaces,
      activeWorkspaceId,
      plazaAccess: createDefaultPlazaAccessState(preferences.connectionPlazaUrl),
      settingsOpen: false,
      settingsTab: "profile",
      settingsLlmSelectedId: preferences.llmDefaultConfigId || preferences.llmConfigs[0]?.id || "",
      paneConfig: createClosedPaneConfigState(),
      paneConfigSnapshot: null,
      snapshotDialog: { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" },
      workspaceDialog: { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" },
      printDialog: createPrintDialogState(),
      diagramRunDialog: createDiagramRunDialogState(),
      operator: createOperatorConsoleState(preferences),
      globalPlazaStatus: emptyCatalog(preferences.connectionPlazaUrl),
      nextWorkspaceIndex: normalizedWorkspaces.length + 1,
      paneMenuWindowId: "",
      menuBarMenuId: "",
    };
  } catch (error) {
    console.error("Failed to restore personal agent state from local storage.", error);
    resetPersonalAgentStorage({ preservePreferences: true });
    if (IS_MAP_PHEMAR_MODE) {
      return createMapPhemarInitialState(dashboard);
    }
    const preferences = normalizePreferences(loadStorage(currentPreferenceStorageKey(), {}), dashboard);
    const normalizedWorkspaces = normalizeWorkspaceState(
      (dashboard.workspaces || []).map((workspace, index) => createWorkspaceRuntime(workspace, index, preferences, dashboard)),
      preferences,
      dashboard,
    );
    return {
      dashboard,
      preferences,
      workspaces: normalizedWorkspaces,
      activeWorkspaceId: preferences.defaultWorkspaceId && normalizedWorkspaces.some((entry) => entry.id === preferences.defaultWorkspaceId)
        ? preferences.defaultWorkspaceId
        : normalizedWorkspaces[0]?.id || "",
      plazaAccess: createDefaultPlazaAccessState(preferences.connectionPlazaUrl),
      settingsOpen: false,
      settingsTab: "profile",
      settingsLlmSelectedId: preferences.llmDefaultConfigId || preferences.llmConfigs[0]?.id || "",
      paneConfig: createClosedPaneConfigState(),
      paneConfigSnapshot: null,
      snapshotDialog: { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" },
      workspaceDialog: { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" },
      printDialog: createPrintDialogState(),
      diagramRunDialog: createDiagramRunDialogState(),
      operator: createOperatorConsoleState(preferences),
      globalPlazaStatus: emptyCatalog(preferences.connectionPlazaUrl),
      nextWorkspaceIndex: normalizedWorkspaces.length + 1,
      paneMenuWindowId: "",
      menuBarMenuId: "",
    };
  }
}

function findWorkspace(state, workspaceId) {
  return state.workspaces.find((workspace) => workspace.id === workspaceId) || null;
}

function findWindowLocation(state, windowId) {
  for (let workspaceIndex = 0; workspaceIndex < state.workspaces.length; workspaceIndex += 1) {
    const windowIndex = state.workspaces[workspaceIndex].windows.findIndex((entry) => entry.id === windowId);
    if (windowIndex >= 0) {
      return {
        workspace: state.workspaces[workspaceIndex],
        workspaceIndex,
        windowIndex,
        windowItem: state.workspaces[workspaceIndex].windows[windowIndex],
      };
    }
  }
  return null;
}

function findPaneLocation(state, windowId, paneId) {
  const located = findWindowLocation(state, windowId);
  if (!located || located.windowItem.type !== "browser") {
    return null;
  }
  const paneIndex = located.windowItem.panes.findIndex((entry) => entry.id === paneId);
  if (paneIndex < 0) {
    return null;
  }
  return {
    ...located,
    paneIndex,
    pane: located.windowItem.panes[paneIndex],
  };
}

function resolveMindMapSource(state, windowId) {
  const located = findWindowLocation(state, windowId);
  if (!located || located.windowItem.type !== "mind_map") {
    return null;
  }
  const linked = located.windowItem.linkedPaneContext;
  if (!linked) {
    return {
      windowLocation: located,
      mapState: located.windowItem.mindMapState,
      catalog: located.windowItem.mindMapCatalog,
      linkedPaneLocation: null,
    };
  }
  const paneLocation = findPaneLocation(state, linked.browserWindowId, linked.paneId);
  if (!paneLocation || paneLocation.pane.type !== "mind_map") {
    return {
      windowLocation: located,
      mapState: located.windowItem.mindMapState,
      catalog: located.windowItem.mindMapCatalog,
      linkedPaneLocation: null,
    };
  }
  return {
    windowLocation: located,
    mapState: paneLocation.pane.mindMapState,
    catalog: located.windowItem.mindMapCatalog,
    linkedPaneLocation: paneLocation,
  };
}

function collectLinkedMindMapPhemaIds(appState) {
  const ids = new Set();
  (appState?.workspaces || []).forEach((workspace) => {
    (workspace?.windows || []).forEach((windowItem) => {
      if (windowItem?.type === "browser") {
        (windowItem.panes || []).forEach((pane) => {
          if (pane?.type !== "mind_map") {
            return;
          }
          const linkedId = String(pane?.mindMapState?.linkedPhemaId || "").trim();
          if (linkedId) {
            ids.add(linkedId);
          }
        });
        return;
      }
      if (windowItem?.type !== "mind_map") {
        return;
      }
      const linkedId = String(windowItem?.mindMapState?.linkedPhemaId || "").trim();
      if (linkedId) {
        ids.add(linkedId);
      }
    });
  });
  return Array.from(ids);
}

function applyLinkedMindMapPhemas(appState, phemasById) {
  const lookup = phemasById instanceof Map ? phemasById : new Map();
  if (!lookup.size) {
    return;
  }
  (appState?.workspaces || []).forEach((workspace) => {
    (workspace?.windows || []).forEach((windowItem) => {
      if (windowItem?.type === "browser") {
        (windowItem.panes || []).forEach((pane) => {
          if (pane?.type !== "mind_map") {
            return;
          }
          const linkedId = String(pane?.mindMapState?.linkedPhemaId || "").trim();
          const phema = linkedId ? lookup.get(linkedId) : null;
          if (!phema) {
            return;
          }
          applyMindMapPhemaToPaneState(
            pane,
            phema,
            appState.preferences,
            appState.dashboard,
            `Unable to apply linked MapPhemar state for pane ${pane.id}.`,
          );
        });
        return;
      }
      if (windowItem?.type !== "mind_map" || windowItem.linkedPaneContext) {
        return;
      }
      const linkedId = String(windowItem?.mindMapState?.linkedPhemaId || "").trim();
      const phema = linkedId ? lookup.get(linkedId) : null;
      if (!phema) {
        return;
      }
      applyMindMapPhemaToWindowState(
        windowItem,
        phema,
        appState.preferences,
        appState.dashboard,
        `Unable to apply linked MapPhemar state for window ${windowItem.id}.`,
      );
    });
  });
}

function applyReturnedMapPhemaToContext(appState, context, phema) {
  if (!(phema && typeof phema === "object")) {
    return false;
  }
  if (context?.browserWindowId && context?.paneId) {
    const paneLocation = findPaneLocation(appState, context.browserWindowId, context.paneId);
    if (paneLocation?.pane?.type === "mind_map") {
      return applyMindMapPhemaToPaneState(
        paneLocation.pane,
        phema,
        appState.preferences,
        appState.dashboard,
        "Unable to apply the returned MapPhemar diagram.",
      );
    }
  }
  const targetWindowId = String(context?.windowId || "").trim();
  if (!targetWindowId) {
    return false;
  }
  const windowLocation = findWindowLocation(appState, targetWindowId);
  if (windowLocation?.windowItem?.type !== "mind_map") {
    return false;
  }
  return applyMindMapPhemaToWindowState(
    windowLocation.windowItem,
    phema,
    appState.preferences,
    appState.dashboard,
    "Unable to apply the returned MapPhemar diagram.",
  );
}

function setMindMapImportNotice(mapState, message) {
  if (!mapState || typeof mapState !== "object") {
    return;
  }
  mapState.importNotice = String(message || "").trim();
}

function clearMindMapImportNotice(mapState) {
  setMindMapImportNotice(mapState, "");
}

function buildMindMapApplyErrorMessage(error, phema) {
  const title = String(phema?.name || phema?.phema_id || phema?.id || "This diagram").trim() || "This diagram";
  const detail = String(
    error?.message || error || "MapPhemar returned a diagram payload that Personal Agent could not apply.",
  ).trim();
  return `${title} could not be applied in Personal Agent. ${detail}`;
}

function applyMindMapPhemaToPaneState(pane, phema, preferences, dashboard, logPrefix = "Unable to apply the returned MapPhemar diagram.") {
  if (!pane || pane.type !== "mind_map") {
    return false;
  }
  try {
    const restored = deserializeMindMapFromPhema(phema, preferences, dashboard);
    clearMindMapImportNotice(restored);
    pane.mindMapState = restored;
    pane.title = String(phema?.name || pane.title || "Diagram");
    pane.error = "";
    if (pane.status === "error") {
      pane.status = "idle";
    }
    return true;
  } catch (error) {
    const message = buildMindMapApplyErrorMessage(error, phema);
    console.error(logPrefix, error);
    setMindMapImportNotice(pane.mindMapState, message);
    pane.status = "error";
    pane.error = message;
    return false;
  }
}

function applyMindMapPhemaToWindowState(windowItem, phema, preferences, dashboard, logPrefix = "Unable to apply the returned MapPhemar diagram.") {
  if (!windowItem || windowItem.type !== "mind_map") {
    return false;
  }
  try {
    const restored = deserializeMindMapFromPhema(phema, preferences, dashboard);
    clearMindMapImportNotice(restored);
    windowItem.mindMapState = restored;
    windowItem.title = String(phema?.name || windowItem.title || "Diagram");
    windowItem.subtitle = "Diagram-backed Phema";
    windowItem.mindMapError = "";
    return true;
  } catch (error) {
    const message = buildMindMapApplyErrorMessage(error, phema);
    console.error(logPrefix, error);
    setMindMapImportNotice(windowItem.mindMapState, message);
    windowItem.mindMapError = message;
    return false;
  }
}

async function fetchLinkedMindMapPhemas(appState) {
  const linkedIds = collectLinkedMindMapPhemaIds(appState);
  if (!linkedIds.length) {
    return new Map();
  }
  const loaded = await Promise.all(linkedIds.map(async (linkedId) => {
    try {
      return [linkedId, await fetchMapPhema(linkedId, appState)];
    } catch (error) {
      console.error(`Unable to refresh linked MapPhemar document ${linkedId}.`, error);
      return null;
    }
  }));
  return new Map(loaded.filter(Boolean));
}

function focusWindowInState(appState, windowId) {
  const normalizedWindowId = String(windowId || "").trim();
  if (!normalizedWindowId) {
    return null;
  }
  const located = findWindowLocation(appState, normalizedWindowId);
  if (!located) {
    return null;
  }
  const maximum = Math.max(0, ...located.workspace.windows.map((entry) => Number(entry.z || 0))) + 1;
  located.windowItem.z = maximum;
  return located;
}

function focusPaneInState(appState, windowId, paneId) {
  const normalizedPaneId = String(paneId || "").trim();
  if (!normalizedPaneId) {
    return null;
  }
  const located = findPaneLocation(appState, windowId, normalizedPaneId);
  if (!located) {
    return null;
  }
  const maximum = Math.max(0, ...located.windowItem.panes.map((entry) => Number(entry.z || 0))) + 1;
  located.pane.z = maximum;
  return located;
}

function getSampleParameters(pulse) {
  if (!pulse) {
    return {};
  }
  if (pulse.test_data && typeof pulse.test_data === "object") {
    return cloneValue(pulse.test_data);
  }
  if (pulse.pulse_definition?.test_data && typeof pulse.pulse_definition.test_data === "object") {
    return cloneValue(pulse.pulse_definition.test_data);
  }
  return {};
}

function schemaExplicitRequired(schema) {
  return Array.isArray(schema?.required) ? schema.required : [];
}

function sampleValueFromSchema(definition) {
  const types = schemaTypes(definition);
  if (types.includes("number") || types.includes("integer")) {
    return 0;
  }
  if (types.includes("boolean")) {
    return false;
  }
  if (types.includes("array")) {
    return [];
  }
  if (types.includes("object")) {
    return {};
  }
  return "";
}

function paneParameterTemplate(pulse) {
  const sample = getSampleParameters(pulse);
  const template = sample && typeof sample === "object" ? cloneValue(sample) : {};
  const properties = schemaProperties(pulse?.input_schema || {});
  schemaExplicitRequired(pulse?.input_schema || {}).forEach((field) => {
    if (!(field in template)) {
      template[field] = sampleValueFromSchema(properties[field]);
    }
  });
  return template;
}

function mindMapNodeParameterTemplate(node, baseTemplate = null) {
  const parsed = safeJsonParse(node?.paramsText || "{}", {});
  const template = mergeObjectRecords(
    isObjectRecord(baseTemplate) ? baseTemplate : {},
    isObjectRecord(parsed) ? parsed : {},
  );
  const properties = schemaProperties(node?.inputSchema || {});
  schemaExplicitRequired(node?.inputSchema || {}).forEach((field) => {
    if (!(field in template)) {
      template[field] = sampleValueFromSchema(properties[field]);
    }
  });
  return template;
}

function paneExtraParameterKeys(pulse) {
  const sampleKeys = Object.keys(paneParameterTemplate(pulse) || {});
  const requiredKeys = schemaExplicitRequired(pulse?.input_schema || {});
  return Array.from(new Set([...requiredKeys, ...sampleKeys]))
    .map((entry) => String(entry || "").trim())
    .filter((entry) => entry && entry.toLowerCase() !== "symbol");
}

function paneNeedsExpandedParams(pulse) {
  return paneExtraParameterKeys(pulse).length > 0;
}

function pulseDescription(pulse) {
  return String(pulse?.description || pulse?.pulse_definition?.description || "").trim();
}

function catalogPulseKey(pulse) {
  return String(pulse?.pulse_name || pulse?.pulse_id || pulse?.pulse_address || "").trim().toLowerCase();
}

function pulseMatches(pulse, pulseAddress, pulseName) {
  const address = String(pulse?.pulse_address || "").trim();
  const name = String(pulse?.pulse_name || pulse?.name || "").trim();
  if (pulseName) {
    return name === pulseName || catalogPulseKey(pulse) === String(pulseName || "").trim().toLowerCase();
  }
  if (pulseAddress) {
    return address === pulseAddress;
  }
  return false;
}

function findSelectedCatalogPulse(pulseCatalog, pane) {
  return pulseCatalog.find((entry) => pulseMatches(entry, pane?.pulseAddress, pane?.pulseName)) || null;
}

function findSelectedCompatiblePulser(selectedPulse, pane) {
  return (selectedPulse?.compatible_pulsers || []).find((entry) => (
    (pane?.pulserId && (
      entry.pulser_id === pane.pulserId
      || entry.pulser_name === pane.pulserId
      || entry.key === String(pane.pulserId || "").trim().toLowerCase()
    ))
    || (pane?.pulserName && entry.pulser_name === pane.pulserName)
    || (pane?.pulserAddress && entry.pulser_address === pane.pulserAddress)
  )) || null;
}

function preferredCompatiblePulser(pulseOption) {
  const compatiblePulsers = Array.isArray(pulseOption?.compatible_pulsers) ? pulseOption.compatible_pulsers : [];
  return compatiblePulsers.find((entry) => Number(entry?.last_active || 0) > 0) || compatiblePulsers[0] || null;
}

function catalogHasEntries(catalog) {
  return Boolean(
    (Array.isArray(catalog?.pulses) && catalog.pulses.length)
    || (Array.isArray(catalog?.pulsers) && catalog.pulsers.length),
  );
}

function resolveBrowserCatalog(windowItem, preferences, globalCatalog = null) {
  const plazaUrl = windowItem?.browserDefaults?.plazaUrl || preferences?.connectionPlazaUrl || globalCatalog?.plazaUrl || globalCatalog?.plaza_url || "";
  const browserCatalog = standardizeCatalogPayload(windowItem?.browserCatalog || emptyCatalog(plazaUrl), plazaUrl);
  if (
    catalogHasEntries(browserCatalog)
    || String(browserCatalog?.status || "").trim().toLowerCase() === "loading"
    || String(browserCatalog?.error || "").trim()
  ) {
    return browserCatalog;
  }
  const resolvedGlobalCatalog = standardizeCatalogPayload(globalCatalog || emptyCatalog(plazaUrl), plazaUrl);
  if (
    catalogHasEntries(resolvedGlobalCatalog)
    && normalizePlazaUrl(resolvedGlobalCatalog.plazaUrl || resolvedGlobalCatalog.plaza_url || "") === normalizePlazaUrl(plazaUrl)
  ) {
    return resolvedGlobalCatalog;
  }
  return browserCatalog;
}

function resolvePaneSourcePulse(windowItem, pane, preferences, globalCatalog = null) {
  const pulseOptions = collectCatalogPulses(resolveBrowserCatalog(windowItem, preferences, globalCatalog));
  const selectedPulse = findSelectedCatalogPulse(pulseOptions, pane);
  const selectedCompatiblePulser = findSelectedCompatiblePulser(selectedPulse, pane);
  return selectedCompatiblePulser?.pulse || selectedPulse || null;
}

function primePaneParameterState(windowItem, pane, preferences, globalCatalog = null, { force = false } = {}) {
  const sourcePulse = resolvePaneSourcePulse(windowItem, pane, preferences, globalCatalog);
  if (!sourcePulse) {
    if (force) {
      pane.paramsExpanded = false;
      pane.paramsText = "{}";
    }
    return;
  }
  const nextTemplate = paneParameterTemplate(sourcePulse);
  const nextText = JSON.stringify(nextTemplate, null, 2) || "{}";
  if (paneNeedsExpandedParams(sourcePulse)) {
    pane.paramsExpanded = true;
    if (force || !String(pane.paramsText || "").trim() || String(pane.paramsText || "").trim() === "{}") {
      pane.paramsText = nextText;
    }
    return;
  }
  if (force) {
    pane.paramsExpanded = false;
    pane.paramsText = "{}";
  }
}

function collectCatalogPulses(catalog) {
  const plazaPulses = Array.isArray(catalog?.pulses) ? catalog.pulses : [];
  const merged = new Map();
  plazaPulses.forEach((pulse) => {
    const key = catalogPulseKey(pulse);
    if (!key) {
      return;
    }
    merged.set(key, {
      key,
      pulse_name: pulse?.pulse_name || pulse?.name || pulse?.pulse_address || "",
      pulse_id: pulse?.pulse_id || "",
      pulse_address: pulse?.pulse_address || "",
      description: pulseDescription(pulse),
      plazaDescription: pulseDescription(pulse),
      input_schema: pulse?.input_schema || {},
      output_schema: pulse?.output_schema || {},
      compatible_pulsers: [],
    });
  });
  const pulsers = Array.isArray(catalog?.pulsers) ? catalog.pulsers : [];
  pulsers.forEach((pulser) => {
    (pulser.supported_pulses || []).forEach((pulse) => {
      const key = catalogPulseKey(pulse);
      if (!key) {
        return;
      }
      if (!merged.has(key)) {
        merged.set(key, {
          key,
          pulse_name: pulse?.pulse_name || pulse?.name || pulse?.pulse_address || "",
          pulse_id: pulse?.pulse_id || "",
          pulse_address: pulse?.pulse_address || "",
          description: pulseDescription(pulse),
          plazaDescription: "",
          input_schema: pulse?.input_schema || {},
          output_schema: pulse?.output_schema || {},
          compatible_pulsers: [],
        });
      }
      const entry = merged.get(key);
      if (!entry.description && pulseDescription(pulse)) {
        entry.description = pulseDescription(pulse);
      }
      if (!entry.pulse_id && pulse?.pulse_id) {
        entry.pulse_id = pulse.pulse_id;
      }
      if (!entry.pulse_address && pulse?.pulse_address) {
        entry.pulse_address = pulse.pulse_address;
      }
      const compatibleKey = String(pulser.agent_id || pulser.address || pulser.name || "").trim().toLowerCase();
      if (!entry.compatible_pulsers.some((candidate) => candidate.key === compatibleKey)) {
        entry.compatible_pulsers.push({
          key: compatibleKey,
          pulser_id: pulser.agent_id || "",
          pulser_name: pulser.name || pulser.agent_id || "Pulser",
          pulser_address: pulser.address || "",
          practice_id: pulser.practice_id || "get_pulse_data",
          last_active: Number(pulser.last_active || 0),
          pulse,
        });
      }
    });
  });
  return Array.from(merged.values())
    .map((entry) => ({
      ...entry,
      compatible_pulsers: [...entry.compatible_pulsers].sort((left, right) => (
        Number(right.last_active || 0) - Number(left.last_active || 0)
        || String(left.pulser_name || "").localeCompare(String(right.pulser_name || ""))
      )),
    }))
    .sort((left, right) => String(left.pulse_name || left.pulse_address || "").localeCompare(String(right.pulse_name || right.pulse_address || "")));
}

function getFieldOptions(value, prefix = "", depth = 0, output = []) {
  if (depth > 4) {
    return output;
  }
  if (Array.isArray(value)) {
    output.push({
      path: prefix,
      label: prefix || "root",
      detail: `Array(${value.length})`,
      depth,
    });
    if (value.length && depth < 4) {
      getFieldOptions(value[0], prefix ? `${prefix}[0]` : "[0]", depth + 1, output);
    }
    return output;
  }
  if (value && typeof value === "object") {
    if (prefix) {
      output.push({
        path: prefix,
        label: prefix,
        detail: "Object",
        depth,
      });
    }
    Object.entries(value).forEach(([key, entry]) => {
      const nextPath = prefix ? `${prefix}.${key}` : key;
      if (entry && typeof entry === "object") {
        getFieldOptions(entry, nextPath, depth + 1, output);
      } else {
        output.push({
          path: nextPath,
          label: nextPath,
          detail: typeof entry,
          depth: depth + 1,
        });
      }
    });
    return output;
  }
  output.push({
    path: prefix,
    label: prefix || "root",
    detail: typeof value,
    depth,
  });
  return output;
}

function readPath(value, path) {
  if (!path) {
    return value;
  }
  const normalized = path.replace(/\[(\d+)\]/g, ".$1");
  return normalized.split(".").filter(Boolean).reduce((acc, key) => {
    if (acc === null || acc === undefined) {
      return undefined;
    }
    return acc[key];
  }, value);
}

function writePathValue(target, path, value) {
  if (!path) {
    return cloneValue(value);
  }
  const tokens = String(path || "").replace(/\[(\d+)\]/g, ".$1").split(".").filter(Boolean);
  if (!tokens.length) {
    return cloneValue(value);
  }
  let current = target;
  tokens.forEach((token, index) => {
    const key = /^\d+$/.test(token) ? Number(token) : token;
    const isLast = index === tokens.length - 1;
    const nextToken = tokens[index + 1];
    const nextContainerIsArray = /^\d+$/.test(nextToken || "");
    if (isLast) {
      current[key] = cloneValue(value);
      return;
    }
    const nextValue = current[key];
    if (!nextValue || typeof nextValue !== "object") {
      current[key] = nextContainerIsArray ? [] : {};
    }
    current = current[key];
  });
  return target;
}

function mergeStructuredData(target, source) {
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return cloneValue(source);
  }
  const base = target && typeof target === "object" && !Array.isArray(target) ? target : {};
  Object.entries(source).forEach(([key, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      base[key] = mergeStructuredData(base[key], value);
      return;
    }
    base[key] = cloneValue(value);
  });
  return base;
}

function getDisplayValue(pane) {
  if (!pane.fieldPaths.length) {
    return pane.result;
  }
  if (pane.fieldPaths.length === 1) {
    return readPath(pane.result, pane.fieldPaths[0]);
  }
  const payload = {};
  pane.fieldPaths.forEach((fieldPath) => {
    payload[fieldPath] = readPath(pane.result, fieldPath);
  });
  return payload;
}

function sparkPath(points, width, height) {
  const values = points.map((point) => Number(point)).filter((point) => Number.isFinite(point));
  if (!values.length) {
    return "";
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 1);
  return values.map((point, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * width;
    const y = height - ((point - min) / spread) * (height - 12) - 6;
    return `${x},${y}`;
  }).join(" ");
}

function numericValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function ohlcValue(entry, keys) {
  for (const key of keys) {
    if (!(key in entry)) {
      continue;
    }
    const number = numericValue(entry[key]);
    if (number !== null) {
      return number;
    }
  }
  return null;
}

function ohlcPoint(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return null;
  }
  const open = ohlcValue(entry, ["open", "o", "Open", "O"]);
  const high = ohlcValue(entry, ["high", "h", "High", "H"]);
  const low = ohlcValue(entry, ["low", "l", "Low", "L"]);
  const close = ohlcValue(entry, ["close", "c", "Close", "C"]);
  if ([open, high, low, close].some((value) => value === null)) {
    return null;
  }
  return { open, high, low, close };
}

function getCandleSeries(value, depth = 0) {
  if (depth > 4 || value === null || value === undefined) {
    return [];
  }
  if (Array.isArray(value)) {
    const candles = value.map((entry) => ohlcPoint(entry)).filter(Boolean);
    if (candles.length >= 2) {
      return candles;
    }
    for (const entry of value) {
      const nested = getCandleSeries(entry, depth + 1);
      if (nested.length) {
        return nested;
      }
    }
    return [];
  }
  if (value && typeof value === "object") {
    for (const entry of Object.values(value)) {
      const nested = getCandleSeries(entry, depth + 1);
      if (nested.length) {
        return nested;
      }
    }
  }
  return [];
}

function getChartSeries(value) {
  if (Array.isArray(value)) {
    if (value.every((entry) => typeof entry === "number")) {
      return value;
    }
    const firstNumericKey = value.find((entry) => entry && typeof entry === "object")
      ? Object.keys(value.find((entry) => entry && typeof entry === "object")).find((key) => typeof value.find((entry) => entry && typeof entry === "object")[key] === "number")
      : "";
    if (firstNumericKey) {
      return value.map((entry) => Number(entry?.[firstNumericKey] || 0));
    }
  }
  if (value && typeof value === "object") {
    return Object.values(value).filter((entry) => typeof entry === "number");
  }
  return [];
}

function summarizeSchema(schema) {
  if (!schema || typeof schema !== "object") {
    return "No schema";
  }
  const properties = schema.properties && typeof schema.properties === "object" ? Object.keys(schema.properties) : Object.keys(schema);
  const required = Array.isArray(schema.required) ? schema.required : [];
  return `${properties.length} fields${required.length ? ` · ${required.length} required` : ""}`;
}

function schemaFieldEntries(schema) {
  const properties = schemaProperties(schema);
  const requiredSet = new Set(schemaRequired(schema));
  return Object.entries(properties).map(([name, definition]) => ({
    name,
    definition,
    required: requiredSet.has(name),
    types: schemaTypes(definition),
  }));
}

function buildSchemaTreeNode(name, definition, path, depth, required = false) {
  const normalizedPath = String(path || name || "");
  const children = [];
  if (definition && typeof definition === "object" && definition.items) {
    children.push(buildSchemaTreeNode("[]", definition.items, `${normalizedPath}[]`, depth + 1, false));
  }
  schemaFieldEntries(definition).forEach((entry) => {
    children.push(buildSchemaTreeNode(entry.name, entry.definition, `${normalizedPath}.${entry.name}`, depth + 1, entry.required));
  });
  return {
    name,
    label: name,
    path: normalizedPath,
    definition,
    required,
    depth,
    types: schemaTypes(definition),
    expandable: children.length > 0,
    children,
  };
}

function schemaTreeEntries(schema) {
  return schemaFieldEntries(schema).map((entry) => buildSchemaTreeNode(entry.name, entry.definition, entry.name, 0, entry.required));
}

function flattenSchemaTree(nodes, expandedSet, rows = []) {
  nodes.forEach((node) => {
    rows.push(node);
    if (node.expandable && expandedSet.has(node.path)) {
      flattenSchemaTree(node.children, expandedSet, rows);
    }
  });
  return rows;
}

function flattenSchemaTreeAll(nodes, rows = []) {
  nodes.forEach((node) => {
    rows.push(node);
    if (node.children.length) {
      flattenSchemaTreeAll(node.children, rows);
    }
  });
  return rows;
}

function schemaTypeLabel(definition) {
  const types = schemaTypes(definition);
  return types.length ? types.join(" | ") : "any";
}

function schemaProperties(schema) {
  if (schema?.properties && typeof schema.properties === "object") {
    return schema.properties;
  }
  return schema && typeof schema === "object" ? schema : {};
}

function schemaRequired(schema) {
  if (Array.isArray(schema?.required) && schema.required.length) {
    return schema.required;
  }
  return Object.keys(schemaProperties(schema));
}

function schemaTypes(definition) {
  if (typeof definition === "string") {
    return [definition.toLowerCase()];
  }
  if (!definition || typeof definition !== "object") {
    return [];
  }
  if (Array.isArray(definition.type)) {
    return definition.type.map((entry) => String(entry).toLowerCase());
  }
  if (definition.type) {
    return [String(definition.type).toLowerCase()];
  }
  if (definition.properties) {
    return ["object"];
  }
  if (definition.items) {
    return ["array"];
  }
  return [];
}

function compatibleTypes(outputDefinition, inputDefinition) {
  const output = schemaTypes(outputDefinition);
  const input = schemaTypes(inputDefinition);
  if (!output.length || !input.length) {
    return true;
  }
  return input.every((inputType) => (
    output.includes(inputType)
    || (inputType === "number" && output.includes("integer"))
    || (inputType === "integer" && output.includes("number"))
    || inputType === "null"
  ));
}

function schemaPathTokens(path) {
  return String(path || "").match(/([^[.\]]+)|\[\]/g) || [];
}

function schemaDefinitionAtPath(schema, path) {
  if (!path) {
    return null;
  }
  let current = schema;
  for (const token of schemaPathTokens(path)) {
    if (token === "[]") {
      if (!current || typeof current !== "object" || !current.items) {
        return null;
      }
      current = current.items;
      continue;
    }
    const properties = schemaProperties(current);
    if (!properties[token]) {
      return null;
    }
    current = properties[token];
  }
  return current;
}

function parseEdgeMapping(edge) {
  const parsed = safeJsonParse(edge?.mappingText || "{}", null);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { mapping: {}, error: "Mapping config must be a JSON object." };
  }
  return { mapping: parsed, error: "" };
}

function stringifyEdgeMapping(mapping) {
  return JSON.stringify(mapping, null, 2) || "{}";
}

function mappedSourceField(mappingValue, fallbackField) {
  if (typeof mappingValue === "string") {
    return mappingValue.trim();
  }
  if (mappingValue && typeof mappingValue === "object" && typeof mappingValue.from === "string") {
    return mappingValue.from.trim();
  }
  return fallbackField;
}

function mappedConstantValue(mappingValue) {
  if (mappingValue && typeof mappingValue === "object" && Object.prototype.hasOwnProperty.call(mappingValue, "const")) {
    if (typeof mappingValue.const === "string") {
      return mappingValue.const;
    }
    return mappingValue.const === undefined ? "" : JSON.stringify(mappingValue.const);
  }
  return "";
}

function hasMappedConstant(mappingValue) {
  if (!(mappingValue && typeof mappingValue === "object" && Object.prototype.hasOwnProperty.call(mappingValue, "const"))) {
    return false;
  }
  if (typeof mappingValue.const === "string") {
    return mappingValue.const.trim().length > 0;
  }
  return mappingValue.const !== undefined;
}

function schemaDefinitionFromValue(value) {
  if (value === null) {
    return { type: "null" };
  }
  if (Array.isArray(value)) {
    return { type: "array" };
  }
  if (typeof value === "number") {
    return { type: Number.isInteger(value) ? "integer" : "number" };
  }
  if (typeof value === "boolean") {
    return { type: "boolean" };
  }
  if (value && typeof value === "object") {
    return { type: "object" };
  }
  return { type: "string" };
}

function schemaDefinitionForConstant(mappingValue) {
  const raw = mappedConstantValue(mappingValue);
  if (!raw.trim()) {
    return null;
  }
  const invalid = {};
  const parsed = safeJsonParse(raw, invalid);
  return parsed === invalid ? { type: "string" } : schemaDefinitionFromValue(parsed);
}

function hasConfiguredPulse(node) {
  if (isBoundaryMindMapNode(node)) {
    return boundarySchemaConfigured(node);
  }
  if (isBranchMindMapNode(node)) {
    return branchSchemaConfigured(node);
  }
  return Boolean(String(node?.pulseName || node?.pulseAddress || "").trim());
}

function edgeCompatibility(map, edge) {
  const fromNode = map.nodes.find((entry) => entry.id === edge.from);
  const toNode = map.nodes.find((entry) => entry.id === edge.to);
  if (!fromNode || !toNode) {
    return { status: "warning", label: "Broken", reason: "One side of this connection is missing." };
  }
  if (!hasConfiguredPulse(fromNode) || !hasConfiguredPulse(toNode)) {
    return {
      status: "pending",
      label: "Unconfigured",
      reason: "Configure pulses on both shapes to validate this connection.",
    };
  }
  const { mapping, error } = parseEdgeMapping(edge);
  if (error) {
    return {
      status: "warning",
      label: "Invalid Mapping",
      reason: error,
    };
  }
  const requiredFields = schemaRequired(toNode.inputSchema || {});
  if (!requiredFields.length) {
    return {
      status: "compatible",
      label: "Compatible",
      reason: "The destination pulse accepts the source output without additional mapping.",
    };
  }
  const missingFields = [];
  const mismatchedFields = [];
  requiredFields.forEach((field) => {
    const mappingValue = mapping[field];
    const inputDefinition = schemaDefinitionAtPath(toNode.inputSchema || {}, field);
    if (hasMappedConstant(mappingValue)) {
      const constantDefinition = schemaDefinitionForConstant(mappingValue);
      if (inputDefinition && constantDefinition && !compatibleTypes(constantDefinition, inputDefinition)) {
        mismatchedFields.push(field);
      }
      return;
    }
    const sourceField = mappedSourceField(mappingValue, field);
    const outputDefinition = schemaDefinitionAtPath(fromNode.outputSchema || {}, sourceField);
    if (!outputDefinition) {
      missingFields.push(sourceField === field ? field : `${field} <= ${sourceField}`);
      return;
    }
    if (inputDefinition && !compatibleTypes(outputDefinition, inputDefinition)) {
      mismatchedFields.push(field);
    }
  });
  if (missingFields.length) {
    return {
      status: "warning",
      label: "Mismatch",
      reason: `Missing mapped source field${missingFields.length === 1 ? "" : "s"}: ${missingFields.slice(0, 4).join(", ")}.`,
    };
  }
  if (mismatchedFields.length) {
    return {
      status: "warning",
      label: "Mismatch",
      reason: `Type mismatch for destination field${mismatchedFields.length === 1 ? "" : "s"}: ${mismatchedFields.slice(0, 4).join(", ")}.`,
    };
  }
  return {
    status: "compatible",
    label: "Compatible",
    reason: "The source output schema matches the destination input schema.",
  };
}

function mindMapOutgoingEdges(map, nodeId) {
  return Array.isArray(map?.edges) ? map.edges.filter((entry) => entry.from === nodeId) : [];
}

function mindMapIncomingEdges(map, nodeId) {
  return Array.isArray(map?.edges) ? map.edges.filter((entry) => entry.to === nodeId) : [];
}

function branchMindMapConnectionCounts(map, node, relevantIds = null) {
  if (!isBranchMindMapNode(node)) {
    return { input: 0, yes: 0, no: 0 };
  }
  const includes = (nodeId) => !relevantIds || relevantIds.has(nodeId);
  const incomingEdges = mindMapIncomingEdges(map, node.id).filter((edge) => includes(edge.from));
  const outgoingEdges = mindMapOutgoingEdges(map, node.id).filter((edge) => includes(edge.to));
  return {
    input: incomingEdges.length,
    yes: outgoingEdges.filter((edge) => normalizeBranchMindMapRoute(edge.route || edge.fromAnchor) === "yes").length,
    no: outgoingEdges.filter((edge) => normalizeBranchMindMapRoute(edge.route || edge.fromAnchor) === "no").length,
  };
}

function branchMindMapInputSatisfied(node, activeIncomingEdges, connectedIncomingEdges) {
  if (!isBranchMindMapNode(node)) {
    return activeIncomingEdges.length > 0;
  }
  if (!connectedIncomingEdges.length) {
    return false;
  }
  return branchConnectorMode(node, "input") === "all"
    ? activeIncomingEdges.length === connectedIncomingEdges.length
    : activeIncomingEdges.length > 0;
}

function branchMindMapActiveRouteEdges(node, outgoingEdges, route) {
  const matchingEdges = outgoingEdges.filter((edge) => normalizeBranchMindMapRoute(edge.route || edge.fromAnchor) === route);
  if (branchConnectorMode(node, route) === "any") {
    return matchingEdges.slice(0, 1);
  }
  return matchingEdges;
}

function branchMindMapConnectionsComplete(map, node) {
  if (!isBranchMindMapNode(node)) {
    return true;
  }
  const counts = branchMindMapConnectionCounts(map, node);
  return counts.input > 0 && counts.yes > 0 && counts.no > 0;
}

function mindMapEdgeHasActivePayload(edge, map, stepOutputs, activeBranchEdgeIds) {
  if (!edge || !stepOutputs.has(edge.from)) {
    return false;
  }
  const sourceNode = Array.isArray(map?.nodes)
    ? map.nodes.find((entry) => entry.id === edge.from) || null
    : null;
  if (sourceNode && isBranchMindMapNode(sourceNode)) {
    return activeBranchEdgeIds.has(edge.id);
  }
  return true;
}

function collectReachableMindMapNodes(map, startId, direction = "out") {
  const visited = new Set();
  const queue = [startId];
  while (queue.length) {
    const currentId = queue.shift();
    if (!currentId || visited.has(currentId)) {
      continue;
    }
    visited.add(currentId);
    const nextEdges = direction === "in"
      ? mindMapIncomingEdges(map, currentId)
      : mindMapOutgoingEdges(map, currentId);
    nextEdges.forEach((edge) => {
      queue.push(direction === "in" ? edge.from : edge.to);
    });
  }
  return visited;
}

function mappedConstantRuntimeValue(mappingValue) {
  if (!hasMappedConstant(mappingValue)) {
    return undefined;
  }
  const raw = mappedConstantValue(mappingValue);
  const invalid = {};
  const parsed = safeJsonParse(raw, invalid);
  return parsed === invalid ? raw : parsed;
}

function buildMappedEdgePayload(sourceOutput, targetNode, edge) {
  const payload = {};
  const { mapping } = parseEdgeMapping(edge);
  const schemaFieldNames = schemaFieldEntries(targetNode?.inputSchema || {}).map((entry) => entry.name);
  const targetPaths = Array.from(new Set([...schemaFieldNames, ...Object.keys(mapping)]));
  targetPaths.forEach((targetPath) => {
    const mappingValue = mapping[targetPath];
    if (hasMappedConstant(mappingValue)) {
      writePathValue(payload, targetPath, mappedConstantRuntimeValue(mappingValue));
      return;
    }
    const fallbackField = schemaFieldNames.includes(targetPath) ? targetPath : "";
    const sourceField = mappedSourceField(mappingValue, fallbackField);
    if (!sourceField) {
      return;
    }
    const nextValue = readPath(sourceOutput, sourceField);
    if (nextValue === undefined) {
      return;
    }
    writePathValue(payload, targetPath, nextValue);
  });
  return payload;
}

function diagramBoundaryNode(map, role) {
  return Array.isArray(map?.nodes)
    ? map.nodes.find((entry) => normalizeBoundaryMindMapRole(entry?.role) === role) || null
    : null;
}

function diagramBoundarySchema(map, role) {
  const node = diagramBoundaryNode(map, role);
  if (!node) {
    return {};
  }
  if (role === "output") {
    if (schemaHasFields(node.inputSchema || {})) {
      return cloneValue(node.inputSchema || {});
    }
    if (schemaHasFields(node.outputSchema || {})) {
      return cloneValue(node.outputSchema || {});
    }
    return {};
  }
  if (schemaHasFields(node.outputSchema || {})) {
    return cloneValue(node.outputSchema || {});
  }
  if (schemaHasFields(node.inputSchema || {})) {
    return cloneValue(node.inputSchema || {});
  }
  return {};
}

function summarizeMindMapNodeForPhema(node, map) {
  if (!node) {
    return "";
  }
  if (isBranchMindMapNode(node)) {
    const outboundCount = mindMapOutgoingEdges(map, node.id).length;
    const condition = String(node.conditionExpression || "").trim();
    return `Branch node evaluates ${condition || "a Python boolean expression"} and routes the payload to ${outboundCount || 0} downstream shape${outboundCount === 1 ? "" : "s"}.`;
  }
  const executionLabel = node.pulseName
    ? `Runs pulse ${node.pulseName}${node.pulserName ? ` via ${node.pulserName}` : ""}.`
    : `Uses a ${mindMapShapePreset(node.type).label.toLowerCase()} shape configuration.`;
  const inboundCount = mindMapIncomingEdges(map, node.id).length;
  const outboundCount = mindMapOutgoingEdges(map, node.id).length;
  return `${executionLabel} ${inboundCount} inbound and ${outboundCount} outbound connection${outboundCount === 1 ? "" : "s"}.`;
}

function buildMindMapPhemaSections(map) {
  const nodes = Array.isArray(map?.nodes)
    ? map.nodes.filter((entry) => !isBoundaryMindMapNode(entry))
    : [];
  if (!nodes.length) {
    return [
      {
        name: "Diagram Flow",
        description: "Auto-generated from MapPhemar.",
        modifier: "",
        content: [
          {
            type: "text",
            text: "This Phema is diagram-backed. Load it in the diagram editor to inspect or modify the workflow.",
          },
        ],
      },
    ];
  }
  return nodes.map((node) => ({
    name: node.title || mindMapShapePreset(node.type).label,
    description: summarizeMindMapNodeForPhema(node, map),
    modifier: "",
    content: [
      {
        type: "text",
        text: isBranchMindMapNode(node)
          ? `Branch condition: ${String(node.conditionExpression || "").trim() || "(unset)"}`
          : node.pulseName
            ? `Pulse: ${node.pulseName}`
            : `Shape: ${mindMapShapePreset(node.type).label}`,
      },
    ],
  }));
}

function serializeMindMapToPhema(map, title, existingPhemaId = "") {
  const normalizedTitle = String(title || "").trim() || "Diagram Phema";
  const inputSchema = diagramBoundarySchema(map, "input");
  const outputSchema = diagramBoundarySchema(map, "output");
  const serializedMap = {
    plazaUrl: String(map?.plazaUrl || ""),
    showGrid: map?.showGrid !== false,
    inspectorWidth: Number.isFinite(map?.inspectorWidth) ? map.inspectorWidth : 320,
    expandedSourcePaths: Array.isArray(map?.expandedSourcePaths) ? [...map.expandedSourcePaths] : [],
    nextNodeIndex: Number(map?.nextNodeIndex || 0),
    nextEdgeIndex: Number(map?.nextEdgeIndex || 0),
    nodes: cloneValue(Array.isArray(map?.nodes) ? map.nodes : []),
    edges: cloneValue(Array.isArray(map?.edges) ? map.edges : []),
  };
  return {
    ...(existingPhemaId ? { phema_id: existingPhemaId, id: existingPhemaId } : {}),
    name: normalizedTitle,
    description: "Diagram-backed Phema managed by MapPhemar.",
    tags: ["diagram", "map-phemar"],
    input_schema: inputSchema,
    output_schema: outputSchema,
    sections: buildMindMapPhemaSections(map),
    resolution_mode: "dynamic",
    meta: {
      builder: "MapPhemar",
      kind: "diagram",
      resolution_mode: "dynamic",
      map_phemar: {
        version: 1,
        diagram: serializedMap,
      },
    },
  };
}

function deserializeMindMapFromPhema(phema, preferences, dashboard) {
  const meta = phema?.meta && typeof phema.meta === "object" ? phema.meta : {};
  const mapMeta = meta.map_phemar && typeof meta.map_phemar === "object" ? meta.map_phemar : {};
  const diagram = mapMeta.diagram && typeof mapMeta.diagram === "object" ? mapMeta.diagram : null;
  if (!diagram) {
    throw new Error("This Phema does not include a MapPhemar diagram.");
  }
  const restored = normalizeMindMapState(
    {
      ...diagram,
      linkedPhemaId: String(phema?.phema_id || phema?.id || ""),
      linkedPhemaName: String(phema?.name || ""),
    },
    preferences,
    dashboard,
  );
  const inputNode = diagramBoundaryNode(restored, "input");
  if (inputNode && !schemaHasFields(inputNode.outputSchema || {}) && phema?.input_schema && typeof phema.input_schema === "object") {
    inputNode.outputSchema = cloneValue(phema.input_schema);
    inputNode.outputSchemaText = schemaTextValue(phema.input_schema);
  }
  const outputNode = diagramBoundaryNode(restored, "output");
  if (outputNode && !schemaHasFields(outputNode.inputSchema || {}) && phema?.output_schema && typeof phema.output_schema === "object") {
    outputNode.inputSchema = cloneValue(phema.output_schema);
    outputNode.inputSchemaText = schemaTextValue(phema.output_schema);
  }
  syncBranchMindMapSchemas(restored);
  syncBoundaryMindMapSchemas(restored);
  return restored;
}

function resolveMindMapNodeExecution(node, catalog, fallbackPlazaUrl = "") {
  if (!node || isBoundaryMindMapNode(node)) {
    return {
      ready: true,
      selectedPulse: null,
      compatiblePulser: null,
      sourcePulse: null,
      pulseName: "",
      pulseAddress: "",
      pulserId: "",
      pulserName: "",
      pulserAddress: "",
      practiceId: "get_pulse_data",
      inputSchema: node?.inputSchema || {},
      outputSchema: node?.outputSchema || {},
    };
  }
  if (isBranchMindMapNode(node)) {
    return {
      ready: true,
      selectedPulse: null,
      compatiblePulser: null,
      sourcePulse: null,
      pulseName: "",
      pulseAddress: "",
      pulserId: "",
      pulserName: "",
      pulserAddress: "",
      practiceId: "get_pulse_data",
      inputSchema: node?.inputSchema || {},
      outputSchema: node?.outputSchema || {},
    };
  }
  const pulseOptions = collectCatalogPulses(catalog || emptyCatalog(fallbackPlazaUrl));
  const selectedPulse = pulseOptions.find((entry) => pulseMatches(entry, node.pulseAddress, node.pulseName)) || null;
  const compatiblePulser = findSelectedCompatiblePulser(selectedPulse, node) || preferredCompatiblePulser(selectedPulse);
  const sourcePulse = compatiblePulser?.pulse || selectedPulse || null;
  const pulseName = sourcePulse?.pulse_name || selectedPulse?.pulse_name || node.pulseName || "";
  const pulseAddress = sourcePulse?.pulse_address || selectedPulse?.pulse_address || node.pulseAddress || "";
  const pulserId = compatiblePulser?.pulser_id || node.pulserId || "";
  const pulserName = compatiblePulser?.pulser_name || node.pulserName || "";
  const pulserAddress = compatiblePulser?.pulser_address || node.pulserAddress || "";
  return {
    ready: Boolean(String(pulseName || pulseAddress).trim() && String(pulserId || pulserName || pulserAddress).trim()),
    selectedPulse,
    compatiblePulser,
    sourcePulse,
    pulseName,
    pulseAddress,
    pulserId,
    pulserName,
    pulserAddress,
    practiceId: compatiblePulser?.practice_id || node.practiceId || "get_pulse_data",
    inputSchema: sourcePulse?.input_schema || selectedPulse?.input_schema || node.inputSchema || {},
    outputSchema: sourcePulse?.output_schema || selectedPulse?.output_schema || node.outputSchema || {},
  };
}

function mindMapRunInputTemplate(node, catalog, fallbackPlazaUrl = "") {
  if (!node) {
    return {};
  }
  const execution = resolveMindMapNodeExecution(node, catalog, fallbackPlazaUrl);
  const sourcePulse = execution.sourcePulse || execution.selectedPulse || null;
  const schemaNode = execution.inputSchema && typeof execution.inputSchema === "object"
    ? { ...node, inputSchema: execution.inputSchema }
    : node;
  const baseTemplate = sourcePulse ? paneParameterTemplate(sourcePulse) : {};
  return mindMapNodeParameterTemplate(schemaNode, baseTemplate);
}

function mindMapRunReadiness(map, fallbackPlazaUrl = "", catalog = null) {
  const inputNode = Array.isArray(map?.nodes)
    ? map.nodes.find((entry) => normalizeBoundaryMindMapRole(entry?.role) === "input") || null
    : null;
  const outputNode = Array.isArray(map?.nodes)
    ? map.nodes.find((entry) => normalizeBoundaryMindMapRole(entry?.role) === "output") || null
    : null;
  if (!inputNode || !outputNode) {
    return { canRun: false, reason: "Input and Output nodes are required." };
  }
  if (!normalizePlazaUrl(map?.plazaUrl || fallbackPlazaUrl || "")) {
    return { canRun: false, reason: "Set a Plaza URL before running the diagram." };
  }
  const invalidEdge = (map.edges || []).find((edge) => edgeCompatibility(map, edge).status !== "compatible") || null;
  if (invalidEdge) {
    const fromNode = map.nodes.find((entry) => entry.id === invalidEdge.from) || null;
    const toNode = map.nodes.find((entry) => entry.id === invalidEdge.to) || null;
    return {
      canRun: false,
      reason: `${fromNode?.title || "Source"} -> ${toNode?.title || "Target"} is not valid yet.`,
      invalidEdge,
    };
  }
  const inputEdges = mindMapOutgoingEdges(map, inputNode.id);
  const outputEdges = mindMapIncomingEdges(map, outputNode.id);
  if (inputEdges.length !== 1) {
    return {
      canRun: false,
      reason: inputEdges.length ? "Input can only connect to one downstream shape for test runs." : "Connect Input to a shape before running.",
    };
  }
  if (!outputEdges.length) {
    return {
      canRun: false,
      reason: "Connect a shape into Output before running.",
    };
  }
  const forward = collectReachableMindMapNodes(map, inputNode.id, "out");
  if (!forward.has(outputNode.id)) {
    return { canRun: false, reason: "Create a connected path from Input to Output before running." };
  }
  const backward = collectReachableMindMapNodes(map, outputNode.id, "in");
  const relevantIds = new Set(Array.from(forward).filter((nodeId) => backward.has(nodeId)));
  const runnableNodes = (map.nodes || []).filter((node) => relevantIds.has(node.id) && !isBoundaryMindMapNode(node));
  const incompleteBranch = runnableNodes.find((node) => {
    if (!isBranchMindMapNode(node)) {
      return false;
    }
    if (!branchConditionConfigured(node)) {
      return true;
    }
    const counts = branchMindMapConnectionCounts(map, node, relevantIds);
    return counts.input < 1 || counts.yes < 1 || counts.no < 1;
  }) || null;
  if (incompleteBranch) {
    if (!branchConditionConfigured(incompleteBranch)) {
      return { canRun: false, reason: `${incompleteBranch.title} needs a Python boolean expression before it can route Yes and No.` };
    }
    return { canRun: false, reason: `${incompleteBranch.title} needs at least one inbound, one Yes, and one No connection.` };
  }
  const executionWarnings = runnableNodes.flatMap((node) => {
    if (isBranchMindMapNode(node)) {
      return [];
    }
    if (!resolveMindMapNodeExecution(node, catalog, map?.plazaUrl || fallbackPlazaUrl).ready) {
      return [`${node.title} needs both a pulse and an active pulser to execute.`];
    }
    return [];
  });
  const runnableIds = new Set(runnableNodes.map((node) => node.id));
  const relevantEdges = (map.edges || []).filter((edge) => relevantIds.has(edge.from) && relevantIds.has(edge.to));
  const indegree = new Map(runnableNodes.map((node) => [node.id, 0]));
  relevantEdges.forEach((edge) => {
    if (runnableIds.has(edge.from) && runnableIds.has(edge.to)) {
      indegree.set(edge.to, (indegree.get(edge.to) || 0) + 1);
    }
  });
  const queue = runnableNodes
    .filter((node) => (indegree.get(node.id) || 0) === 0)
    .sort((left, right) => map.nodes.findIndex((entry) => entry.id === left.id) - map.nodes.findIndex((entry) => entry.id === right.id));
  const executionOrder = [];
  while (queue.length) {
    const node = queue.shift();
    executionOrder.push(node);
    relevantEdges.forEach((edge) => {
      if (edge.from !== node.id || !runnableIds.has(edge.to)) {
        return;
      }
      indegree.set(edge.to, (indegree.get(edge.to) || 0) - 1);
      if ((indegree.get(edge.to) || 0) === 0) {
        const nextNode = runnableNodes.find((entry) => entry.id === edge.to);
        if (nextNode && !executionOrder.some((entry) => entry.id === nextNode.id) && !queue.some((entry) => entry.id === nextNode.id)) {
          queue.push(nextNode);
        }
      }
    });
  }
  if (executionOrder.length !== runnableNodes.length) {
    return { canRun: false, reason: "Diagram test runs require a directed acyclic flow." };
  }
  return {
    canRun: true,
    reason: "",
    inputNode,
    outputNode,
    startNode: map.nodes.find((entry) => entry.id === inputEdges[0].to) || null,
    endNode: map.nodes.find((entry) => entry.id === outputEdges[0].from) || null,
    relevantIds,
    relevantEdges,
    executionWarnings,
    executionOrder,
  };
}

async function executeMindMap(source, fallbackPlazaUrl, initialInput, onProgress = null) {
  const readiness = mindMapRunReadiness(source?.mapState, fallbackPlazaUrl, source?.catalog);
  if (!readiness.canRun) {
    const error = new Error(readiness.reason || "Diagram execution failed.");
    error.diagramSteps = [];
    throw error;
  }
  const normalizedInput = cloneValue(initialInput && typeof initialInput === "object" && !Array.isArray(initialInput) ? initialInput : {});
  const stepOutputs = new Map();
  const activeBranchEdgeIds = new Set();
  const initialStep = {
    kind: "input",
    nodeId: readiness.inputNode.id,
    title: readiness.inputNode.title,
    status: "ready",
    input: normalizedInput,
    output: normalizedInput,
    pulseName: "",
    pulserName: "",
    pulserActive: null,
    error: "",
  };
  const steps = [initialStep];
  const emitProgress = () => {
    if (typeof onProgress === "function") {
      onProgress(cloneValue(steps));
    }
  };
  stepOutputs.set(readiness.inputNode.id, normalizedInput);
  emitProgress();
  try {
    for (const node of readiness.executionOrder) {
      const connectedIncomingEdges = mindMapIncomingEdges(source.mapState, node.id).filter((edge) => readiness.relevantIds.has(edge.from));
      const incomingEdges = connectedIncomingEdges.filter((edge) => (
        mindMapEdgeHasActivePayload(edge, source.mapState, stepOutputs, activeBranchEdgeIds)
      ));
      let nodeInput = {};
      incomingEdges.forEach((edge) => {
        const patch = buildMappedEdgePayload(stepOutputs.get(edge.from), node, edge);
        nodeInput = mergeStructuredData(nodeInput, patch);
      });
      const branchInputReady = !isBranchMindMapNode(node) || branchMindMapInputSatisfied(node, incomingEdges, connectedIncomingEdges);
      const execution = isBranchMindMapNode(node)
        ? null
        : resolveMindMapNodeExecution(
          node,
          source.catalog,
          source.mapState.plazaUrl || fallbackPlazaUrl,
        );
      const stepPulserName = execution?.pulserName || node.pulserName || "";
      const stepPulserActive = execution?.compatiblePulser
        ? isPulserMarkedActive(execution.compatiblePulser)
        : (stepPulserName ? false : null);
      if (!incomingEdges.length || !branchInputReady) {
        const skipReason = isBranchMindMapNode(node) && connectedIncomingEdges.length && branchConnectorMode(node, "input") === "all"
          ? "Waiting for all inbound branch connections before evaluating this branch."
          : "";
        steps.push({
          kind: isBranchMindMapNode(node) ? "branch" : "node",
          nodeId: node.id,
          title: node.title,
          status: "skipped",
          input: nodeInput,
          output: null,
          pulseName: execution?.pulseName || node.pulseName || "",
          pulserName: stepPulserName,
          pulserActive: stepPulserActive,
          error: skipReason,
        });
        emitProgress();
        continue;
      }
      if (isBranchMindMapNode(node)) {
        let branchDecision;
        try {
          branchDecision = await evaluateMindMapBranchCondition(node.conditionExpression, nodeInput);
        } catch (error) {
          steps.push({
            kind: "branch",
            nodeId: node.id,
            title: node.title,
            status: "error",
            input: nodeInput,
            output: null,
            pulseName: "",
            pulserName: "",
            pulserActive: null,
            error: error.message || "Branch condition evaluation failed.",
          });
          emitProgress();
          throw error;
        }
        const selectedRoute = branchDecision ? "yes" : "no";
        const branchOutput = cloneValue(nodeInput);
        stepOutputs.set(node.id, branchOutput);
        const routeEdges = branchMindMapActiveRouteEdges(
          node,
          mindMapOutgoingEdges(source.mapState, node.id).filter((edge) => readiness.relevantIds.has(edge.to)),
          selectedRoute,
        );
        const activeRouteEdgeIds = new Set(routeEdges.map((edge) => edge.id));
        mindMapOutgoingEdges(source.mapState, node.id)
          .filter((edge) => readiness.relevantIds.has(edge.to))
          .forEach((edge) => {
            if (activeRouteEdgeIds.has(edge.id)) {
              activeBranchEdgeIds.add(edge.id);
            } else {
              activeBranchEdgeIds.delete(edge.id);
            }
          });
        steps.push({
          kind: "branch",
          nodeId: node.id,
          title: node.title,
          status: "ready",
          input: nodeInput,
          output: branchOutput,
          conditionExpression: node.conditionExpression || "",
          selectedRoute,
          pulseName: "",
          pulserName: "",
          pulserActive: null,
          error: "",
        });
        emitProgress();
        continue;
      }
      if (!execution.ready) {
        const errorMessage = `${node.title} needs both a pulse and an active pulser to run.`;
        steps.push({
          kind: "node",
          nodeId: node.id,
          title: node.title,
          status: "error",
          input: nodeInput,
          output: null,
          pulseName: execution.pulseName || node.pulseName || "",
          pulserName: stepPulserName,
          pulserActive: stepPulserActive,
          error: errorMessage,
        });
        emitProgress();
        throw new Error(errorMessage);
      }
      const requestPayload = {
        plaza_url: source.windowLocation.windowItem.mindMapCatalog?.plazaUrl || source.mapState.plazaUrl || fallbackPlazaUrl,
        pulser_id: execution.pulserId || "",
        pulser_name: execution.pulserName || "",
        pulser_address: execution.pulserAddress || "",
        practice_id: execution.practiceId || "get_pulse_data",
        pulse_name: execution.pulseName || "",
        pulse_address: execution.pulseAddress || "",
        output_schema: execution.outputSchema || {},
        input: nodeInput,
      };
      let payload;
      try {
        payload = await runPulserRequest(requestPayload);
      } catch (error) {
        steps.push({
          kind: "node",
          nodeId: node.id,
          title: node.title,
          status: "error",
          input: nodeInput,
          output: null,
          pulseName: execution.pulseName || node.pulseName || "",
          pulserName: stepPulserName,
          pulserActive: stepPulserActive,
          error: error.message || "Node execution failed.",
        });
        emitProgress();
        throw error;
      }
      const nodeOutput = payload.result ?? payload;
      stepOutputs.set(node.id, nodeOutput);
      steps.push({
        kind: "node",
        nodeId: node.id,
        title: node.title,
        status: "ready",
        input: nodeInput,
        output: nodeOutput,
        pulseName: execution.pulseName || node.pulseName || "",
        pulserName: stepPulserName,
        pulserActive: stepPulserActive,
        error: "",
      });
      emitProgress();
    }
    let outputPayload = {};
    const outputIncomingEdges = mindMapIncomingEdges(source.mapState, readiness.outputNode.id).filter((edge) => (
      readiness.relevantIds.has(edge.from)
      && mindMapEdgeHasActivePayload(edge, source.mapState, stepOutputs, activeBranchEdgeIds)
    ));
    if (!outputIncomingEdges.length) {
      throw new Error("The active diagram path did not reach Output.");
    }
    outputIncomingEdges.forEach((edge) => {
      const patch = buildMappedEdgePayload(stepOutputs.get(edge.from), readiness.outputNode, edge);
      outputPayload = mergeStructuredData(outputPayload, patch);
    });
    stepOutputs.set(readiness.outputNode.id, outputPayload);
    steps.push({
      kind: "output",
      nodeId: readiness.outputNode.id,
      title: readiness.outputNode.title,
      status: "ready",
      input: outputPayload,
      output: outputPayload,
      pulseName: "",
      pulserName: "",
      pulserActive: null,
      error: "",
    });
    emitProgress();
    return {
      readiness,
      steps: cloneValue(steps),
      output: cloneValue(outputPayload),
    };
  } catch (error) {
    const failure = error instanceof Error ? error : new Error("Diagram execution failed.");
    failure.diagramSteps = cloneValue(steps);
    throw failure;
  }
}

function nodeCenter(node) {
  return { x: node.x + node.w / 2, y: node.y + node.h / 2 };
}

function automaticAnchor(sourceNode, targetNode) {
  if (isBranchMindMapNode(targetNode)) {
    return "branch-in";
  }
  if (isBranchMindMapNode(sourceNode)) {
    return nodeCenter(targetNode).y <= nodeCenter(sourceNode).y ? "branch-yes" : "branch-no";
  }
  const source = nodeCenter(sourceNode);
  const target = nodeCenter(targetNode);
  const deltaX = target.x - source.x;
  const deltaY = target.y - source.y;
  if (Math.abs(deltaX) >= Math.abs(deltaY)) {
    return deltaX >= 0 ? "right" : "left";
  }
  return deltaY >= 0 ? "bottom" : "top";
}

function branchHandleDescriptor(node, anchor) {
  if (!isBranchMindMapNode(node)) {
    return null;
  }
  return mindMapHandleDescriptors(node).find((handle) => handle.anchor === anchor) || null;
}

function anchorPoint(node, anchor) {
  const branchHandle = branchHandleDescriptor(node, anchor);
  if (branchHandle) {
    return {
      x: node.x + node.w * ((Number(branchHandle.xPercent) || 0) / 100),
      y: node.y + node.h * ((Number(branchHandle.yPercent) || 0) / 100),
    };
  }
  switch (anchor) {
    case "top":
      return { x: node.x + node.w / 2, y: node.y };
    case "right":
      return { x: node.x + node.w, y: node.y + node.h / 2 };
    case "bottom":
      return { x: node.x + node.w / 2, y: node.y + node.h };
    case "left":
      return { x: node.x, y: node.y + node.h / 2 };
    default:
      return nodeCenter(node);
  }
}

function anchorVectorForNode(node, anchor) {
  const branchHandle = branchHandleDescriptor(node, anchor);
  const side = branchHandle?.side || String(anchor || "").trim().toLowerCase();
  if (side === "top") {
    return { x: 0, y: -1 };
  }
  if (side === "right") {
    return { x: 1, y: 0 };
  }
  if (side === "bottom") {
    return { x: 0, y: 1 };
  }
  if (side === "left") {
    return { x: -1, y: 0 };
  }
  return { x: 1, y: 0 };
}

function connectionPath(fromNode, toNode, edge) {
  const fromAnchor = edge.fromAnchor || automaticAnchor(fromNode, toNode);
  const toAnchor = edge.toAnchor || automaticAnchor(toNode, fromNode);
  const start = anchorPoint(fromNode, fromAnchor);
  const end = anchorPoint(toNode, toAnchor);
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const controlDistance = Math.max(distance * 0.35, 8);
  const startVector = anchorVectorForNode(fromNode, fromAnchor);
  const endVector = anchorVectorForNode(toNode, toAnchor);
  const controlA = { x: start.x + startVector.x * controlDistance, y: start.y + startVector.y * controlDistance };
  const controlB = { x: end.x + endVector.x * controlDistance, y: end.y + endVector.y * controlDistance };
  return `M ${start.x} ${start.y} C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`;
}

function pointConnectionVector(fromPoint, toPoint) {
  const deltaX = toPoint.x - fromPoint.x;
  const deltaY = toPoint.y - fromPoint.y;
  if (Math.abs(deltaX) >= Math.abs(deltaY)) {
    return deltaX >= 0 ? { x: 1, y: 0 } : { x: -1, y: 0 };
  }
  return deltaY >= 0 ? { x: 0, y: 1 } : { x: 0, y: -1 };
}

function connectionPathToPoint(fromNode, fromAnchor, point) {
  const start = anchorPoint(fromNode, fromAnchor);
  const end = {
    x: Number(point?.x) || 0,
    y: Number(point?.y) || 0,
  };
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const controlDistance = Math.max(distance * 0.35, 8);
  const startVector = anchorVectorForNode(fromNode, fromAnchor);
  const endVector = pointConnectionVector(start, end);
  const controlA = { x: start.x + startVector.x * controlDistance, y: start.y + startVector.y * controlDistance };
  const controlB = { x: end.x - endVector.x * controlDistance, y: end.y - endVector.y * controlDistance };
  return `M ${start.x} ${start.y} C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`;
}

function PopupWindowPortal({ windowItem, theme, title, onClosed, children }) {
  const [container, setContainer] = useState(null);
  const popupRef = useRef(null);

  useEffect(() => {
    const popup = window.open("", `phemacast_personal_agent_${windowItem.id}`, [
      "popup=yes",
      `width=${Math.round(windowItem.width || 1420)}`,
      `height=${Math.round(windowItem.height || 920)}`,
      `left=${windowItem.x || 140}`,
      `top=${windowItem.y || 140}`,
    ].join(","));

    if (!popup) {
      onClosed(windowItem.id, "blocked");
      return undefined;
    }

    popupRef.current = popup;
    popup.document.title = title;
    popup.document.body.className = "personal-agent-popup-body";
    popup.document.body.dataset.theme = theme;
    popup.document.body.innerHTML = "";

    document.querySelectorAll('link[rel="stylesheet"], style').forEach((node) => {
      popup.document.head.appendChild(node.cloneNode(true));
    });

    const portalRoot = popup.document.createElement("div");
    portalRoot.className = "popup-root";
    popup.document.body.appendChild(portalRoot);
    setContainer(portalRoot);

    const handleUnload = () => {
      const nextX = typeof popup.screenX === "number" ? popup.screenX : windowItem.x;
      const nextY = typeof popup.screenY === "number" ? popup.screenY : windowItem.y;
      const nextWidth = typeof popup.outerWidth === "number" ? popup.outerWidth : windowItem.width;
      const nextHeight = typeof popup.outerHeight === "number" ? popup.outerHeight : windowItem.height;
      onClosed(windowItem.id, "closed", { x: nextX, y: nextY, width: nextWidth, height: nextHeight });
    };

    popup.addEventListener("beforeunload", handleUnload);
    return () => {
      popup.removeEventListener("beforeunload", handleUnload);
      if (!popup.closed) {
        popup.close();
      }
    };
  }, [windowItem.id]);

  useEffect(() => {
    if (popupRef.current && !popupRef.current.closed) {
      popupRef.current.document.title = title;
      popupRef.current.document.body.dataset.theme = theme;
    }
  }, [title, theme]);

  if (!container) {
    return null;
  }

  return ReactDOM.createPortal(children, container);
}

function ChartPreview({ value, chartType }) {
  const width = 300;
  const height = 120;
  if (chartType === "candle") {
    const candles = getCandleSeries(value);
    if (!candles.length) {
      return <div className="pane-empty small">No OHLC series available for candle preview.</div>;
    }
    const highs = candles.map((entry) => entry.high);
    const lows = candles.map((entry) => entry.low);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const spread = Math.max(max - min, 1);
    const candleSlot = width / Math.max(candles.length, 1);
    const candleWidth = Math.max(Math.min(candleSlot * 0.58, 16), 4);
    const scaleY = (point) => height - ((point - min) / spread) * (height - 12) - 6;
    return (
      <svg className="mini-chart mini-chart--candle" viewBox={`0 0 ${width} ${height}`}>
        {candles.map((entry, index) => {
          const x = index * candleSlot + candleSlot / 2;
          const openY = scaleY(entry.open);
          const highY = scaleY(entry.high);
          const lowY = scaleY(entry.low);
          const closeY = scaleY(entry.close);
          const bodyTop = Math.min(openY, closeY);
          const bodyHeight = Math.max(Math.abs(closeY - openY), 2);
          const rising = entry.close >= entry.open;
          return (
            <g key={index} className={rising ? "mini-candle mini-candle--up" : "mini-candle mini-candle--down"}>
              <line x1={x} y1={highY} x2={x} y2={lowY} />
              <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} rx="2" />
            </g>
          );
        })}
      </svg>
    );
  }
  const series = getChartSeries(value);
  if (!series.length) {
    return <div className="pane-empty small">No numeric series available for chart preview.</div>;
  }
  const max = Math.max(...series, 1);
  const polyline = sparkPath(series, width, height);
  return (
    <svg className={`mini-chart mini-chart--${chartType}`} viewBox={`0 0 ${width} ${height}`}>
      {chartType === "line" ? (
        <polyline fill="none" stroke="currentColor" strokeWidth="3" points={polyline} />
      ) : (
        series.map((point, index) => {
          const barWidth = width / series.length - 4;
          const barHeight = (point / max) * (height - 12);
          return (
            <rect
              key={index}
              x={index * (width / series.length) + 2}
              y={height - barHeight - 6}
              width={Math.max(barWidth, 4)}
              height={barHeight}
              rx="4"
            />
          );
        })
      )}
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M13.6 4.9V1.8l-1.3 1.3A5.9 5.9 0 0 0 8 1.3a6 6 0 1 0 5.5 8.3h-1.7A4.6 4.6 0 1 1 8 2.7c1.2 0 2.4.5 3.2 1.3L9.8 5.4h3.8Z"
        fill="currentColor"
      />
    </svg>
  );
}

function ConfigIcon() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M9.67 1.84c-.23-.78-1.34-.78-1.57 0l-.18.62a1.7 1.7 0 0 1-2.45 1.02l-.56-.31c-.71-.39-1.56.46-1.17 1.17l.31.56a1.7 1.7 0 0 1-1.02 2.45l-.62.18c-.78.23-.78 1.34 0 1.57l.62.18a1.7 1.7 0 0 1 1.02 2.45l-.31.56c-.39.71.46 1.56 1.17 1.17l.56-.31a1.7 1.7 0 0 1 2.45 1.02l.18.62c.23.78 1.34.78 1.57 0l.18-.62a1.7 1.7 0 0 1 2.45-1.02l.56.31c.71.39 1.56-.46 1.17-1.17l-.31-.56a1.7 1.7 0 0 1 1.02-2.45l.62-.18c.78-.23.78-1.34 0-1.57l-.62-.18a1.7 1.7 0 0 1-1.02-2.45l.31-.56c.39-.71-.46-1.56-1.17-1.17l-.56.31a1.7 1.7 0 0 1-2.45-1.02l-.18-.62ZM8.89 10.7a2.7 2.7 0 1 1 0-5.4 2.7 2.7 0 0 1 0 5.4Z"
        fill="currentColor"
      />
    </svg>
  );
}

function toValueText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((entry) => toValueText(entry)).filter(Boolean).join(", ");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch (error) {
      return String(value);
    }
  }
  return String(value);
}

function getValueEntryLabel(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return "";
  }
  return String(entry.headline || entry.title || entry.name || entry.symbol || "").trim();
}

function getValueEntryCopyField(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return "";
  }
  return [
    "summary",
    "description",
    "detail",
    "snippet",
    "body",
    "content",
  ].find((key) => typeof entry[key] === "string" && entry[key].trim()) || "";
}

function getValueEntryUrl(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return "";
  }
  const raw = String(entry.url || entry.link || entry.href || "").trim();
  if (!raw) {
    return "";
  }
  const candidate = /^https?:\/\//i.test(raw)
    ? raw
    : /^www\./i.test(raw)
      ? `https://${raw}`
      : "";
  if (!candidate) {
    return "";
  }
  try {
    const parsed = new URL(candidate);
    if (!/^https?:$/i.test(parsed.protocol)) {
      return "";
    }
    return parsed.toString();
  } catch (error) {
    return "";
  }
}

function getValueEntryCopy(entry, label) {
  if (entry === null || entry === undefined) {
    return "";
  }
  if (typeof entry === "string" || typeof entry === "number" || typeof entry === "boolean") {
    return String(entry);
  }
  if (Array.isArray(entry)) {
    return toValueText(entry);
  }
  if (typeof entry !== "object") {
    return String(entry);
  }
  const copyField = getValueEntryCopyField(entry);
  const preferredCopy = copyField ? entry[copyField] : "";
  if (preferredCopy) {
    return preferredCopy;
  }
  const compactPairs = Object.entries(entry)
    .filter(([key, value]) => !["headline", "title", "name", "symbol"].includes(key))
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .filter(([, value]) => typeof value !== "object")
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${value}`);
  if (compactPairs.length > 0) {
    return compactPairs.join(" • ");
  }
  if (label) {
    return "";
  }
  const fallbackKeys = Object.keys(entry).slice(0, 4);
  return fallbackKeys.length ? fallbackKeys.join(" • ") : "Structured item";
}

function getValueEntryMeta(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    return [];
  }
  const copyField = getValueEntryCopyField(entry);
  return Object.entries(entry)
    .filter(([key, value]) => !["headline", "title", "name", "symbol", "url", "link", "href", copyField].includes(key))
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .filter(([, value]) => typeof value !== "object")
    .slice(0, 8);
}

function StructuredListValue({ value, depth = 0 }) {
  if (value === null || value === undefined || value === "") {
    return <div className="pane-empty small">No list items.</div>;
  }

  if (Array.isArray(value)) {
    if (!value.length) {
      return <div className="pane-empty small">No list items.</div>;
    }
    const primitivesOnly = value.every((entry) => (
      entry === null
      || entry === undefined
      || ["string", "number", "boolean"].includes(typeof entry)
    ));
    if (primitivesOnly) {
      return (
        <div className="value-token-list">
          {value.slice(0, 24).map((entry, index) => (
            <span className="value-token" key={`${toValueText(entry)}-${index}`}>{toValueText(entry)}</span>
          ))}
        </div>
      );
    }
    return (
      <div className="value-card-list">
        {value.slice(0, 24).map((entry, index) => {
          if (entry && typeof entry === "object" && !Array.isArray(entry)) {
            const label = getValueEntryLabel(entry);
            const linkUrl = getValueEntryUrl(entry);
            const copy = getValueEntryCopy(entry, label);
            const metaEntries = getValueEntryMeta(entry);
            const showCopy = Boolean(copy) && (label || metaEntries.length === 0);
            return (
              <article className={label ? "value-card" : "value-card value-card--compact"} key={`${label || "entry"}-${index}`}>
                {label ? (
                  <strong>
                    {linkUrl ? (
                      <a className="value-link" href={linkUrl} target="_blank" rel="noopener noreferrer">{label}</a>
                    ) : label}
                  </strong>
                ) : null}
                {showCopy ? <p>{copy}</p> : null}
                {metaEntries.length ? (
                  <div className="value-card-meta">
                    {metaEntries.map(([key, metaValue]) => (
                      <span key={key}>
                        <small>{key}</small>
                        <strong>{toValueText(metaValue)}</strong>
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          }
          return (
            <article className="value-card value-card--compact" key={`primitive-${index}`}>
              <p>{toValueText(entry)}</p>
            </article>
          );
        })}
      </div>
    );
  }

  if (value && typeof value === "object") {
    const simpleEntries = [];
    const complexEntries = [];
    Object.entries(value).forEach(([key, entry]) => {
      if (entry === null || entry === undefined || entry === "") {
        return;
      }
      if (Array.isArray(entry) || (entry && typeof entry === "object")) {
        complexEntries.push([key, entry]);
        return;
      }
      simpleEntries.push([key, entry]);
    });
    if (!simpleEntries.length && complexEntries.length === 1) {
      return <StructuredListValue value={complexEntries[0][1]} depth={depth + 1} />;
    }
    return (
      <div className="value-structured">
        {simpleEntries.length ? (
          <dl className="value-kv">
            {simpleEntries.map(([key, entry]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{toValueText(entry)}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {complexEntries.map(([key, entry]) => (
          <section className="value-group" key={key}>
            <div className="value-group-head">
              <strong>{key}</strong>
            </div>
            {depth >= 2 ? <div className="value-inline">{toValueText(entry)}</div> : <StructuredListValue value={entry} depth={depth + 1} />}
          </section>
        ))}
      </div>
    );
  }

  return <div className="value-inline">{toValueText(value)}</div>;
}

function ValueRenderer({ value, format, chartType }) {
  if (format === "chart") {
    return <ChartPreview value={value} chartType={chartType} />;
  }
  if (format === "list") {
    return <StructuredListValue value={value} />;
  }
  if (format === "plain_text") {
    return <pre className="value-pre">{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>;
  }
  return <pre className="value-pre">{JSON.stringify(value, null, 2)}</pre>;
}

function operatorTicketId(ticket) {
  return String(ticket?.ticket?.id || ticket?.ticket_id || "").trim();
}

function operatorScheduleId(schedule) {
  return String(schedule?.schedule?.id || schedule?.schedule_id || "").trim();
}

function defaultOperatorDestinationStatus() {
  return {
    notion: { label: "Notion", status: "not_configured", title: "", detail: "", url: "", available: false, actions: [] },
    notebooklm: { label: "NotebookLM", status: "not_configured", detail: "", directory: "", source_url_bundle: "", mode: "", available: false, actions: [] },
    channels: cloneValue(DEFAULT_OPERATOR_CHANNELS),
    publication_preview: "",
  };
}

function operatorDestinationStatus(ticket) {
  const destinationStatus = ticket?.destination_status;
  if (!destinationStatus || typeof destinationStatus !== "object") {
    return defaultOperatorDestinationStatus();
  }
  return {
    ...defaultOperatorDestinationStatus(),
    ...destinationStatus,
    channels: Array.isArray(destinationStatus.channels) && destinationStatus.channels.length
      ? destinationStatus.channels
      : cloneValue(DEFAULT_OPERATOR_CHANNELS),
  };
}

function formatTimestamp(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "Not recorded";
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  return parsed.toLocaleString();
}

function compactText(value, maxLength = 160) {
  const normalized = String(value || "").trim();
  if (!normalized || normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function labelizeStatus(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "Unknown";
  }
  return normalized
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function statusPillClass(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["ready", "delivered", "published", "completed", "exported", "online"].includes(normalized)) {
    return "status-pill ready";
  }
  if (["loading", "queued", "running", "claimed"].includes(normalized)) {
    return "status-pill loading";
  }
  if (["failed", "attention", "stopped", "cancelled", "deleted"].includes(normalized)) {
    return "status-pill offline";
  }
  return "status-pill";
}

function operatorSummaryCounts(operator) {
  const tickets = Array.isArray(operator?.tickets) ? operator.tickets : [];
  const destinationReadyCount = tickets.filter((ticket) => {
    const destination = operatorDestinationStatus(ticket);
    const notionReady = ["ready", "published"].includes(String(destination?.notion?.status || ""));
    const notebookReady = ["ready", "exported"].includes(String(destination?.notebooklm?.status || ""));
    const channelReady = (destination.channels || []).some((lane) => ["ready", "delivered"].includes(String(lane?.status || "")));
    return notionReady || notebookReady || channelReady;
  }).length;
  return {
    total: tickets.length,
    attention: tickets.filter((ticket) => Boolean(ticket?.execution_state?.attention_required)).length,
    assigned: tickets.filter((ticket) => String(ticket?.worker_assignment?.status || "").trim().toLowerCase() !== "unassigned").length,
    destinations: destinationReadyCount,
  };
}

function App() {
  const [state, setState] = useState(createInitialState);
  const [phemaDialog, setPhemaDialog] = useState(createPhemaDialogState);
  const [paneFilterText, setPaneFilterText] = useState("");
  const deferredPaneFilterText = useDeferredValue(paneFilterText);
  const [mindMapPulseFilterText, setMindMapPulseFilterText] = useState("");
  const deferredMindMapPulseFilterText = useDeferredValue(mindMapPulseFilterText);
  const [mindMapMappingTab, setMindMapMappingTab] = useState("visual");
  const [storageBuckets, setStorageBuckets] = useState([]);
  const [storageBucketStatus, setStorageBucketStatus] = useState("idle");
  const [storageBucketError, setStorageBucketError] = useState("");
  const [storageBucketAddMode, setStorageBucketAddMode] = useState(false);
  const [storageBucketDraft, setStorageBucketDraft] = useState("");
  const [storageBucketCreateStatus, setStorageBucketCreateStatus] = useState("idle");
  const mindMapDragRef = useRef(null);
  const mindMapResizeRef = useRef(null);
  const mindMapLinkRef = useRef(null);
  const mindMapInspectorResizeRef = useRef(null);
  const windowInteractionRef = useRef(null);
  const workspaceCanvasRef = useRef(null);
  const workspaceWorldRef = useRef({ workspaceId: "", offsetX: 0, offsetY: 0 });
  const paneInteractionRef = useRef(null);
  const browserPaneCanvasRefs = useRef({});
  const menuBarButtonRefs = useRef({});
  const initialPhemaLoadRef = useRef(false);
  const storagePlazaRefreshRef = useRef("");
  const storageBucketRefreshRef = useRef("");
  const plazaAccessRefreshRef = useRef("");
  const previousPlazaAccessUrlRef = useRef(normalizePlazaUrl(state.preferences.connectionPlazaUrl || ""));
  const latestStateRef = useRef(state);

  useEffect(() => {
    latestStateRef.current = state;
  }, [state]);

  function updateState(mutator) {
    setState((current) => {
      const next = cloneValue(current);
      mutator(next);
      latestStateRef.current = next;
      return next;
    });
  }

  async function chooseSettingsLocalDirectory() {
    try {
      const selectedDirectory = await chooseLocalDirectory(state.preferences.fileSaveLocalDirectory);
      if (!selectedDirectory) {
        return;
      }
      updateState((next) => {
        next.preferences.fileSaveLocalDirectory = selectedDirectory;
      });
    } catch (error) {
      window.alert(String(error?.message || "Unable to choose a local folder."));
    }
  }

  function clearPlazaAccessSession(next, message = "") {
    next.plazaAccess.session = null;
    next.plazaAccess.sessionPlazaUrl = "";
    next.plazaAccess.user = null;
    next.plazaAccess.keys = [];
    next.plazaAccess.keysStatus = "idle";
    next.plazaAccess.keysError = "";
    next.plazaAccess.keyReveal = null;
    next.plazaAccess.pendingKeyId = "";
    next.plazaAccess.pendingKeyAction = "";
    next.plazaAccess.authMessage = message;
    next.plazaAccess.keyMessage = "";
  }

  function plazaProxyPath(path, plazaUrlOverride = "") {
    const normalizedPlazaUrl = normalizePlazaUrl(plazaUrlOverride || latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    const url = new URL(path, window.location.origin);
    if (normalizedPlazaUrl) {
      url.searchParams.set("plaza_url", normalizedPlazaUrl);
    }
    return `${url.pathname}${url.search}`;
  }

  async function refreshPlazaAccessSession() {
    const currentState = latestStateRef.current;
    const plazaUrl = normalizePlazaUrl(currentState?.preferences?.connectionPlazaUrl || "");
    const session = currentPlazaAccessSession(currentState);
    const refreshToken = String(session?.refresh_token || "").trim();
    if (!plazaUrl || !refreshToken) {
      return null;
    }
    try {
      const response = await fetch(plazaProxyPath("/api/plaza/auth/refresh", plazaUrl), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        updateState((next) => {
          if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
            return;
          }
          clearPlazaAccessSession(next, payload.detail || payload.message || "Plaza session expired.");
        });
        return null;
      }
      const refreshedSession = payload.session && typeof payload.session === "object" ? payload.session : null;
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.session = refreshedSession;
        next.plazaAccess.sessionPlazaUrl = refreshedSession ? plazaUrl : "";
        next.plazaAccess.user = payload.user || next.plazaAccess.user;
        next.plazaAccess.authMessage = "";
      });
      return refreshedSession;
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        clearPlazaAccessSession(next, String(error?.message || "Unable to refresh the Plaza session."));
      });
      return null;
    }
  }

  async function plazaAccessFetch(path, options = {}) {
    const {
      auth = true,
      plazaUrlOverride = "",
      _retryAfterRefresh = false,
      ...requestOptions
    } = options;
    const currentState = latestStateRef.current;
    const plazaUrl = normalizePlazaUrl(plazaUrlOverride || currentState?.preferences?.connectionPlazaUrl || "");
    if (!plazaUrl) {
      throw new Error("Plaza URL is required.");
    }
    const headers = new Headers(requestOptions.headers || {});
    const session = auth ? currentPlazaAccessSession(currentState) : null;
    if (auth && session?.access_token) {
      headers.set("Authorization", `Bearer ${session.access_token}`);
    }
    const response = await fetch(plazaProxyPath(path, plazaUrl), { ...requestOptions, headers });
    if (auth && response.status === 401 && !_retryAfterRefresh && String(session?.refresh_token || "").trim()) {
      const refreshedSession = await refreshPlazaAccessSession();
      if (refreshedSession?.access_token) {
        const retryHeaders = new Headers(requestOptions.headers || {});
        retryHeaders.set("Authorization", `Bearer ${refreshedSession.access_token}`);
        return fetch(plazaProxyPath(path, plazaUrl), { ...requestOptions, headers: retryHeaders });
      }
    }
    return response;
  }

  async function refreshPlazaAccessConfig({ quiet = false } = {}) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    if (!plazaUrl) {
      updateState((next) => {
        next.plazaAccess.config = null;
        next.plazaAccess.configStatus = "error";
        next.plazaAccess.configError = "Plaza URL is required.";
      });
      return null;
    }
    updateState((next) => {
      next.plazaAccess.configStatus = "loading";
      if (!quiet) {
        next.plazaAccess.configError = "";
      }
    });
    try {
      const response = await plazaAccessFetch("/api/plaza/auth/config", { auth: false, plazaUrlOverride: plazaUrl });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load Plaza access settings.");
      }
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.config = payload;
        next.plazaAccess.configStatus = "ready";
        next.plazaAccess.configError = "";
        if (
          payload?.auth_enabled
          && /supabase auth is unavailable for this plaza/i.test(String(next.plazaAccess.authMessage || ""))
        ) {
          next.plazaAccess.authMessage = "";
        }
      });
      return payload;
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.config = null;
        next.plazaAccess.configStatus = "error";
        next.plazaAccess.configError = String(error?.message || "Unable to load Plaza access settings.");
      });
      return null;
    }
  }

  async function refreshPlazaAccessUser({ quiet = false } = {}) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    if (!plazaUrl || !currentPlazaAccessSession(latestStateRef.current)) {
      updateState((next) => {
        next.plazaAccess.user = null;
        if (!quiet) {
          next.plazaAccess.authMessage = "";
        }
      });
      return null;
    }
    try {
      const response = await plazaAccessFetch("/api/plaza/auth/me", { plazaUrlOverride: plazaUrl });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load the Plaza user profile.");
      }
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.user = payload.user || null;
        if (!quiet) {
          next.plazaAccess.authMessage = "";
        }
      });
      return payload.user || null;
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.user = null;
        if (!quiet) {
          next.plazaAccess.authMessage = String(error?.message || "Unable to load the Plaza user profile.");
        }
      });
      return null;
    }
  }

  async function refreshPlazaAccessKeys({ quiet = false } = {}) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    if (!plazaUrl || !currentPlazaAccessSession(latestStateRef.current)) {
      updateState((next) => {
        next.plazaAccess.keys = [];
        next.plazaAccess.keysStatus = "idle";
        next.plazaAccess.keysError = "";
        if (!quiet) {
          next.plazaAccess.keyMessage = "";
        }
      });
      return [];
    }
    updateState((next) => {
      next.plazaAccess.keysStatus = "loading";
      if (!quiet) {
        next.plazaAccess.keysError = "";
      }
    });
    try {
      const response = await plazaAccessFetch("/api/plaza/agent-keys", { plazaUrlOverride: plazaUrl });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load Plaza owner keys.");
      }
      const keys = Array.isArray(payload.agent_keys) ? payload.agent_keys : [];
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keys = keys;
        next.plazaAccess.keysStatus = "ready";
        next.plazaAccess.keysError = "";
        next.plazaAccess.user = payload.viewer || next.plazaAccess.user;
        if (!quiet) {
          next.plazaAccess.keyMessage = "";
        }
      });
      return keys;
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keys = [];
        next.plazaAccess.keysStatus = "error";
        next.plazaAccess.keysError = String(error?.message || "Unable to load Plaza owner keys.");
        if (!quiet) {
          next.plazaAccess.keyMessage = next.plazaAccess.keysError;
        }
      });
      return [];
    }
  }

  async function runPlazaAccessSignIn(identifier, password, successMessage = "Signed in to Plaza.") {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    const response = await plazaAccessFetch("/api/plaza/auth/signin", {
      auth: false,
      plazaUrlOverride: plazaUrl,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, password }),
    });
    const payload = await loadJsonResponse(response);
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || "Unable to sign in to Plaza.");
    }
    updateState((next) => {
      if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
        return;
      }
      next.plazaAccess.session = payload.session || null;
      next.plazaAccess.sessionPlazaUrl = payload.session ? plazaUrl : "";
      next.plazaAccess.user = payload.user || null;
      next.plazaAccess.authMessage = successMessage;
      next.plazaAccess.password = "";
    });
    await refreshPlazaAccessKeys({ quiet: true });
    return payload;
  }

  async function submitPlazaAccessAuth() {
    const currentState = latestStateRef.current;
    const plazaUrl = normalizePlazaUrl(currentState?.preferences?.connectionPlazaUrl || "");
    const identifier = String(currentState?.plazaAccess?.identifier || "").trim();
    const password = String(currentState?.plazaAccess?.password || "");
    const displayName = String(currentState?.plazaAccess?.displayName || "").trim();
    const authMode = currentState?.plazaAccess?.authMode === "signup" ? "signup" : "signin";
    if (!plazaUrl) {
      updateState((next) => {
        next.plazaAccess.authMessage = "Set the Plaza URL in Settings before signing in.";
      });
      return;
    }
    if (!identifier || !password) {
      updateState((next) => {
        next.plazaAccess.authMessage = authMode === "signup"
          ? "Enter a username or email and a password to create the Plaza account."
          : "Enter your Plaza username or email and password.";
      });
      return;
    }
    updateState((next) => {
      next.plazaAccess.authBusy = true;
      next.plazaAccess.authMessage = authMode === "signup" ? "Creating Plaza account..." : "Signing in to Plaza...";
    });
    try {
      if (authMode === "signup") {
        const signupPayload = identifier.includes("@")
          ? { email: identifier, password, display_name: displayName || undefined }
          : { username: identifier, password, display_name: displayName || undefined };
        const signupResponse = await plazaAccessFetch("/api/plaza/auth/signup", {
          auth: false,
          plazaUrlOverride: plazaUrl,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(signupPayload),
        });
        const signupData = await loadJsonResponse(signupResponse);
        if (!signupResponse.ok) {
          throw new Error(signupData.detail || signupData.message || "Unable to create the Plaza account.");
        }
        try {
          await runPlazaAccessSignIn(identifier, password, signupData.message || "Plaza account created and signed in.");
        } catch (signInError) {
          updateState((next) => {
            if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
              return;
            }
            next.plazaAccess.authMode = "signin";
            next.plazaAccess.authMessage = signupData.message || String(signInError?.message || "Plaza account created. Sign in to continue.");
          });
        }
      } else {
        await runPlazaAccessSignIn(identifier, password);
      }
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.authMessage = String(error?.message || "Unable to reach Plaza.");
      });
    } finally {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.authBusy = false;
      });
    }
  }

  async function signOutPlazaAccess() {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    try {
      if (plazaUrl && currentPlazaAccessSession(latestStateRef.current)) {
        await plazaAccessFetch("/api/plaza/auth/signout", {
          plazaUrlOverride: plazaUrl,
          method: "POST",
        });
      }
    } catch (error) {
      // Local sign-out still clears Personal Agent state.
    }
    updateState((next) => {
      clearPlazaAccessSession(next, "Signed out from Plaza.");
    });
  }

  async function createPlazaOwnerKey() {
    const currentState = latestStateRef.current;
    const plazaUrl = normalizePlazaUrl(currentState?.preferences?.connectionPlazaUrl || "");
    const keyName = String(currentState?.plazaAccess?.keyDraftName || "").trim();
    if (!currentPlazaAccessSession(currentState)) {
      updateState((next) => {
        next.plazaAccess.keyMessage = "Sign in to Plaza before creating an owner key.";
      });
      return;
    }
    if (!keyName) {
      updateState((next) => {
        next.plazaAccess.keyMessage = "Enter a name for the Plaza owner key.";
      });
      return;
    }
    updateState((next) => {
      next.plazaAccess.keyBusy = true;
      next.plazaAccess.keyMessage = "Creating Plaza owner key...";
    });
    try {
      const response = await plazaAccessFetch("/api/plaza/agent-keys", {
        plazaUrlOverride: plazaUrl,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: keyName }),
      });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to create the Plaza owner key.");
      }
      const createdKey = payload.agent_key || {};
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyDraftName = "";
        next.plazaAccess.keyReveal = createdKey.secret
          ? { id: createdKey.id || "", name: createdKey.name || keyName, secret: createdKey.secret }
          : null;
        next.plazaAccess.keyMessage = `Created Plaza owner key "${createdKey.name || keyName}".`;
      });
      await refreshPlazaAccessKeys({ quiet: true });
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyMessage = String(error?.message || "Unable to create the Plaza owner key.");
      });
    } finally {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyBusy = false;
      });
    }
  }

  async function setPlazaOwnerKeyStatus(keyId, nextStatus) {
    const currentState = latestStateRef.current;
    const plazaUrl = normalizePlazaUrl(currentState?.preferences?.connectionPlazaUrl || "");
    const normalizedStatus = String(nextStatus || "").trim().toLowerCase();
    const action = normalizedStatus === "active" ? "enable" : "disable";
    updateState((next) => {
      next.plazaAccess.pendingKeyId = keyId;
      next.plazaAccess.pendingKeyAction = action;
      next.plazaAccess.keyMessage = normalizedStatus === "active" ? "Enabling Plaza owner key..." : "Disabling Plaza owner key...";
    });
    try {
      const response = await plazaAccessFetch(`/api/plaza/agent-keys/${encodeURIComponent(keyId)}`, {
        plazaUrlOverride: plazaUrl,
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: normalizedStatus }),
      });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to update the Plaza owner key.");
      }
      await refreshPlazaAccessKeys({ quiet: true });
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyMessage = normalizedStatus === "active" ? "Plaza owner key enabled." : "Plaza owner key disabled.";
      });
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyMessage = String(error?.message || "Unable to update the Plaza owner key.");
      });
    } finally {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.pendingKeyId = "";
        next.plazaAccess.pendingKeyAction = "";
      });
    }
  }

  async function regeneratePlazaOwnerKey(keyId) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    updateState((next) => {
      next.plazaAccess.pendingKeyId = keyId;
      next.plazaAccess.pendingKeyAction = "regenerate";
      next.plazaAccess.keyMessage = "Regenerating Plaza owner key...";
    });
    try {
      const response = await plazaAccessFetch(`/api/plaza/agent-keys/${encodeURIComponent(keyId)}`, {
        plazaUrlOverride: plazaUrl,
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ regenerate: true }),
      });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to regenerate the Plaza owner key.");
      }
      const updatedKey = payload.agent_key || {};
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyReveal = updatedKey.secret
          ? { id: updatedKey.id || keyId, name: updatedKey.name || "Plaza owner key", secret: updatedKey.secret }
          : null;
        next.plazaAccess.keyMessage = `Regenerated Plaza owner key "${updatedKey.name || keyId}".`;
      });
      await refreshPlazaAccessKeys({ quiet: true });
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyMessage = String(error?.message || "Unable to regenerate the Plaza owner key.");
      });
    } finally {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.pendingKeyId = "";
        next.plazaAccess.pendingKeyAction = "";
      });
    }
  }

  async function deletePlazaOwnerKey(keyId) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    updateState((next) => {
      next.plazaAccess.pendingKeyId = keyId;
      next.plazaAccess.pendingKeyAction = "delete";
      next.plazaAccess.keyMessage = "Deleting Plaza owner key...";
    });
    try {
      const response = await plazaAccessFetch(`/api/plaza/agent-keys/${encodeURIComponent(keyId)}`, {
        plazaUrlOverride: plazaUrl,
        method: "DELETE",
      });
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to delete the Plaza owner key.");
      }
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        if (next.plazaAccess.keyReveal?.id === keyId) {
          next.plazaAccess.keyReveal = null;
        }
        next.plazaAccess.keyMessage = "Plaza owner key deleted.";
      });
      await refreshPlazaAccessKeys({ quiet: true });
    } catch (error) {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.keyMessage = String(error?.message || "Unable to delete the Plaza owner key.");
      });
    } finally {
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.pendingKeyId = "";
        next.plazaAccess.pendingKeyAction = "";
      });
    }
  }

  async function copyPlazaOwnerKeySecret(secret) {
    const normalized = String(secret || "").trim();
    if (!normalized) {
      return;
    }
    await copyOperatorText(normalized, "Plaza owner key");
    updateState((next) => {
      next.plazaAccess.keyMessage = "Plaza owner key copied to the clipboard prompt.";
    });
  }

  async function copyPlazaOwnerKeySnippet(keyId, secret = "", includeRuntime = Boolean(secret)) {
    const plazaUrl = normalizePlazaUrl(latestStateRef.current?.preferences?.connectionPlazaUrl || "");
    await copyOperatorText(
      buildPlazaOwnerKeySnippet(plazaUrl, keyId, secret),
      includeRuntime ? "Plaza runtime JSON" : "Plaza config JSON",
    );
    updateState((next) => {
      next.plazaAccess.keyMessage = includeRuntime
        ? (secret ? "Plaza runtime JSON copied with the current secret." : "Plaza runtime JSON copied with a secret placeholder.")
        : "Plaza config JSON copied with the trusted Plaza URL and key id.";
    });
  }

  function activeWorkspace() {
    return findWorkspace(state, state.activeWorkspaceId);
  }

  function activeWindowList() {
    return state.workspaces.flatMap((workspace) => workspace.windows);
  }

  function operatorPaneLocation(appState, windowId, paneId) {
    const located = findPaneLocation(appState, windowId, paneId);
    if (!located || !isOperatorPaneType(located.pane.type)) {
      return null;
    }
    return located;
  }

  function selectedOperatorTicket(windowId, paneId) {
    const operator = operatorPaneLocation(state, windowId, paneId)?.pane?.operatorState;
    if (!operator) {
      return null;
    }
    if (operator.selectedTicket && operatorTicketId(operator.selectedTicket) === operator.selectedTicketId) {
      return operator.selectedTicket;
    }
    return operator.tickets.find((entry) => operatorTicketId(entry) === operator.selectedTicketId) || null;
  }

  function selectedOperatorSchedule(windowId, paneId) {
    const operator = operatorPaneLocation(state, windowId, paneId)?.pane?.operatorState;
    if (!operator) {
      return null;
    }
    return operator.schedules.find((entry) => operatorScheduleId(entry) === operator.selectedScheduleId) || null;
  }

  function operatorPaneConnection(appState, windowId, paneId) {
    const operator = operatorPaneLocation(appState, windowId, paneId)?.pane?.operatorState;
    if (!operator) {
      return null;
    }
    return {
      operator,
      bossUrl: normalizeBossUrl(operator.bossUrl || ""),
      managerAddress: String(operator.managerAddress || "").trim(),
      managerParty: String(operator.managerParty || "").trim(),
    };
  }

  async function copyOperatorText(value, label = "text") {
    const normalized = String(value || "").trim();
    if (!normalized) {
      return;
    }
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(normalized);
        return;
      }
    } catch (error) {
      console.warn(`Unable to copy ${label}.`, error);
    }
    window.prompt(`Copy ${label}`, normalized);
  }

  function openOperatorUrl(url) {
    const normalized = String(url || "").trim();
    if (!normalized) {
      return;
    }
    window.open(normalized, "_blank", "noopener,noreferrer");
  }

  async function refreshOperatorTicketDetail(windowId, paneId, ticketId) {
    const normalizedTicketId = String(ticketId || "").trim();
    const currentState = latestStateRef.current;
    const connection = operatorPaneConnection(currentState, windowId, paneId);
    if (!normalizedTicketId || !connection?.bossUrl) {
      return;
    }
    updateState((next) => {
      const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
      if (!target) {
        return;
      }
      target.selectedTicketStatus = "loading";
      target.selectedTicketError = "";
    });
    const params = new URLSearchParams({ boss_url: connection.bossUrl });
    if (connection.managerAddress) {
      params.set("manager_address", connection.managerAddress);
    }
    if (connection.managerParty) {
      params.set("party", connection.managerParty);
    }
    try {
      const response = await fetch(`/api/managed-work/tickets/${encodeURIComponent(normalizedTicketId)}?${params.toString()}`);
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load managed work detail.");
      }
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target || target.selectedTicketId !== normalizedTicketId) {
          return;
        }
        target.selectedTicketStatus = "ready";
        target.selectedTicketError = "";
        target.selectedTicket = payload.ticket || null;
        target.channelCatalog = Array.isArray(payload.channel_catalog) && payload.channel_catalog.length
          ? payload.channel_catalog
          : target.channelCatalog;
      });
    } catch (error) {
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target || target.selectedTicketId !== normalizedTicketId) {
          return;
        }
        target.selectedTicketStatus = "error";
        target.selectedTicketError = error.message || "Unable to load managed work detail.";
      });
    }
  }

  async function refreshOperatorJobDetail(windowId, paneId, jobId) {
    const normalizedJobId = String(jobId || "").trim();
    const currentState = latestStateRef.current;
    const connection = operatorPaneConnection(currentState, windowId, paneId);
    if (!normalizedJobId || !connection?.bossUrl) {
      return;
    }
    updateState((next) => {
      const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
      if (!target) {
        return;
      }
      target.selectedJobStatus = "loading";
      target.selectedJobError = "";
    });
    const params = new URLSearchParams({ boss_url: connection.bossUrl });
    if (connection.managerAddress) {
      params.set("manager_address", connection.managerAddress);
      params.set("dispatcher_address", connection.managerAddress);
    }
    if (connection.managerParty) {
      params.set("party", connection.managerParty);
    }
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(normalizedJobId)}?${params.toString()}`);
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load job detail.");
      }
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target || target.selectedTicketId !== normalizedJobId) {
          return;
        }
        target.selectedJobStatus = "ready";
        target.selectedJobError = "";
        target.selectedJob = payload;
        target.channelCatalog = Array.isArray(payload.channel_catalog) && payload.channel_catalog.length
          ? payload.channel_catalog
          : target.channelCatalog;
      });
    } catch (error) {
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target || target.selectedTicketId !== normalizedJobId) {
          return;
        }
        target.selectedJobStatus = "error";
        target.selectedJobError = error.message || "Unable to load job detail.";
      });
    }
  }

  async function refreshOperatorMonitor(windowId, paneId, options = {}) {
    const preserveSelection = options.preserveSelection !== false;
    const currentState = latestStateRef.current;
    const connection = operatorPaneConnection(currentState, windowId, paneId);
    if (!connection) {
      return;
    }
    if (!connection.bossUrl) {
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target) {
          return;
        }
        target.status = "idle";
        target.error = "Set a Boss URL in Pane Config to load managed work.";
        target.manager = {};
        target.summary = {};
        target.workers = [];
        target.tickets = [];
        target.schedules = [];
        target.channelCatalog = cloneValue(DEFAULT_OPERATOR_CHANNELS);
        target.selectedTicketId = "";
        target.selectedScheduleId = "";
        target.selectedTicketStatus = "idle";
        target.selectedTicket = null;
        target.selectedJobStatus = "idle";
        target.selectedJob = null;
      });
      return;
    }
    updateState((next) => {
      const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
      if (!target) {
        return;
      }
      target.status = "loading";
      target.error = "";
    });
    const params = new URLSearchParams({
      boss_url: connection.bossUrl,
      ticket_limit: "24",
      schedule_limit: "12",
      preview_limit: "500",
    });
    if (connection.managerAddress) {
      params.set("manager_address", connection.managerAddress);
    }
    if (connection.managerParty) {
      params.set("party", connection.managerParty);
    }
    try {
      const response = await fetch(`/api/managed-work/monitor?${params.toString()}`);
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load managed work monitor.");
      }
      const tickets = Array.isArray(payload.tickets) ? payload.tickets : [];
      const schedules = Array.isArray(payload.schedules) ? payload.schedules : [];
      const currentOperator = connection.operator;
      const currentTicketId = preserveSelection ? String(currentOperator?.selectedTicketId || "").trim() : "";
      const currentScheduleId = preserveSelection ? String(currentOperator?.selectedScheduleId || "").trim() : "";
      const nextTicketId = tickets.some((entry) => operatorTicketId(entry) === currentTicketId)
        ? currentTicketId
        : operatorTicketId(tickets[0]);
      const nextScheduleId = schedules.some((entry) => operatorScheduleId(entry) === currentScheduleId)
        ? currentScheduleId
        : operatorScheduleId(schedules[0]);
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target) {
          return;
        }
        target.status = "ready";
        target.error = "";
        target.manager = payload.manager_assignment || payload.manager || {};
        target.summary = payload.summary || {};
        target.workers = Array.isArray(payload.workers) ? payload.workers : [];
        target.tickets = tickets;
        target.schedules = schedules;
        target.channelCatalog = Array.isArray(payload.channel_catalog) && payload.channel_catalog.length
          ? payload.channel_catalog
          : cloneValue(DEFAULT_OPERATOR_CHANNELS);
        target.selectedTicketId = nextTicketId;
        target.selectedScheduleId = nextScheduleId;
        target.lastRefreshedAt = new Date().toISOString();
        if (!nextTicketId) {
          target.selectedTicketStatus = "idle";
          target.selectedTicket = null;
          target.selectedJobStatus = "idle";
          target.selectedJob = null;
        }
      });
      if (nextTicketId) {
        void refreshOperatorTicketDetail(windowId, paneId, nextTicketId);
        void refreshOperatorJobDetail(windowId, paneId, nextTicketId);
      }
    } catch (error) {
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target) {
          return;
        }
        target.status = "error";
        target.error = error.message || "Unable to load managed work monitor.";
        target.channelCatalog = target.channelCatalog.length
          ? target.channelCatalog
          : cloneValue(DEFAULT_OPERATOR_CHANNELS);
      });
    }
  }

  function selectOperatorTicket(windowId, paneId, ticketId) {
    const normalizedTicketId = String(ticketId || "").trim();
    updateState((next) => {
      const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
      if (!target) {
        return;
      }
      target.selectedTicketId = normalizedTicketId;
      target.selectedTicket = null;
      target.selectedJob = null;
      target.selectedTicketStatus = normalizedTicketId ? "loading" : "idle";
      target.selectedJobStatus = normalizedTicketId ? "loading" : "idle";
      target.selectedTicketError = "";
      target.selectedJobError = "";
      target.view = target.view === "works" ? "assignments" : target.view;
    });
    if (normalizedTicketId) {
      void refreshOperatorTicketDetail(windowId, paneId, normalizedTicketId);
      void refreshOperatorJobDetail(windowId, paneId, normalizedTicketId);
    }
  }

  async function issueOperatorSchedule(windowId, paneId, scheduleId) {
    const normalizedScheduleId = String(scheduleId || "").trim();
    const currentState = latestStateRef.current;
    const connection = operatorPaneConnection(currentState, windowId, paneId);
    if (!normalizedScheduleId || !connection?.bossUrl) {
      return;
    }
    updateState((next) => {
      const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
      if (!target) {
        return;
      }
      target.controlStatus = "loading";
      target.controlError = "";
      target.selectedScheduleId = normalizedScheduleId;
    });
    try {
      const response = await fetch(
        `/api/managed-work/schedules/${encodeURIComponent(normalizedScheduleId)}/control?${new URLSearchParams({ boss_url: connection.bossUrl }).toString()}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "issue" }),
        },
      );
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to issue the schedule.");
      }
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target) {
          return;
        }
        target.controlStatus = "ready";
        target.controlError = "";
      });
      void refreshOperatorMonitor(windowId, paneId, { preserveSelection: true });
    } catch (error) {
      updateState((next) => {
        const target = operatorPaneLocation(next, windowId, paneId)?.pane?.operatorState;
        if (!target) {
          return;
        }
        target.controlStatus = "error";
        target.controlError = error.message || "Unable to issue the schedule.";
      });
    }
  }

function windowMinimums(windowItem) {
  if (windowItem.type === "mind_map") {
    return { width: 760, height: 520 };
  }
  return { width: 620, height: 380 };
}

function windowBoundsSnapshot(windowItem) {
  return {
    x: Number(windowItem?.x || 0),
    y: Number(windowItem?.y || 0),
    width: Number(windowItem?.width || 0),
    height: Number(windowItem?.height || 0),
  };
}

function workspaceCanvasMetrics() {
  const canvas = workspaceCanvasRef.current;
  if (!canvas) {
    return null;
  }
  return {
    width: Math.max(Number(canvas.clientWidth || 0), 0),
    height: Math.max(Number(canvas.clientHeight || 0), 0),
  };
}

function workspaceWorldMetrics(workspace) {
  const dockedWindows = Array.isArray(workspace?.windows)
    ? workspace.windows.filter((entry) => entry.mode === "docked")
    : [];
  const padding = 180;
  const minimumWidth = 2200;
  const minimumHeight = 1600;
  if (!dockedWindows.length) {
    return {
      offsetX: 0,
      offsetY: 0,
      width: minimumWidth,
      height: minimumHeight,
    };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = 0;
  let maxY = 0;
  dockedWindows.forEach((windowItem) => {
    const minimums = windowMinimums(windowItem);
    const width = Math.max(Number(windowItem?.width || 0), minimums.width);
    const height = Math.max(Number(windowItem?.height || 0), minimums.height);
    const x = Math.max(Number(windowItem?.x || 0), WORKSPACE_LEFT_INSET);
    const y = Math.max(Number(windowItem?.y || 0), WORKSPACE_TOP_INSET);
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + width);
    maxY = Math.max(maxY, y + height);
  });
  const offsetX = 0;
  const offsetY = 0;
  return {
    offsetX,
    offsetY,
    width: Math.max(minimumWidth, maxX + padding),
    height: Math.max(minimumHeight, maxY + padding),
  };
}

function normalizeDockedWindowBounds(windowItem, metrics, preferredBounds = null) {
  const minimums = windowMinimums(windowItem);
  const fallbackWidth = windowItem.type === "mind_map" ? 1080 : 980;
  const fallbackHeight = windowItem.type === "mind_map" ? 760 : 660;
  const storedDocked = windowItem?.lastDockedBounds && typeof windowItem.lastDockedBounds === "object"
    ? windowItem.lastDockedBounds
    : null;
  const source = storedDocked || preferredBounds || windowBoundsSnapshot(windowItem);
  const hasStoredDocked = Boolean(storedDocked);
  const width = Math.max(Number(source?.width || windowItem?.width || fallbackWidth), minimums.width);
  const height = Math.max(Number(source?.height || windowItem?.height || fallbackHeight), minimums.height);
  const centeredX = metrics ? Math.round(Math.max((metrics.width - width) / 2, WORKSPACE_LEFT_INSET)) : WORKSPACE_LEFT_INSET;
  const centeredY = metrics ? Math.round(Math.max((metrics.height - height) / 2, WORKSPACE_TOP_INSET)) : WORKSPACE_TOP_INSET;
  const x = Math.max(hasStoredDocked ? Number(source?.x || 0) : centeredX, WORKSPACE_LEFT_INSET);
  const y = Math.max(hasStoredDocked ? Number(source?.y || 0) : centeredY, WORKSPACE_TOP_INSET);

  return { x, y, width, height };
}

  function paneMinimums(pane) {
    if (pane.type === "mind_map") {
      return { width: 280, height: 190 };
    }
    if (pane.type === "managed_work") {
      return { width: 360, height: 260 };
    }
    return { width: 240, height: 170 };
  }

  function focusWindow(windowId) {
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located) {
        return;
      }
      const currentMax = Math.max(0, ...located.workspace.windows.map((entry) => Number(entry.z || 0)));
      if (Number(located.windowItem.z || 0) >= currentMax) {
        return;
      }
      const nextZ = currentMax + 1;
      located.windowItem.z = nextZ;
    });
  }

  function handleWindowMouseDown(windowId, event) {
    if (event.target.closest("button, input, textarea, select, label")) {
      return;
    }
    focusWindow(windowId);
  }

  function setBrowserPaneCanvasRef(windowId, node) {
    if (node) {
      browserPaneCanvasRefs.current[windowId] = node;
      return;
    }
    delete browserPaneCanvasRefs.current[windowId];
  }

  function focusPane(windowId, paneId) {
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located || located.windowItem.type !== "browser") {
        return;
      }
      const target = located.windowItem.panes.find((entry) => entry.id === paneId);
      if (!target) {
        return;
      }
      const currentMax = Math.max(0, ...located.windowItem.panes.map((entry) => Number(entry.z || 0)));
      if (Number(target.z || 0) >= currentMax) {
        return;
      }
      target.z = currentMax + 1;
    });
  }

  function handlePaneMouseDown(windowId, paneId, event) {
    if (event.target.closest("button, input, textarea, select, label")) {
      return;
    }
    event.stopPropagation();
    focusPane(windowId, paneId);
  }

  function beginPaneDrag(windowId, paneId, event) {
    const located = findPaneLocation(state, windowId, paneId);
    const canvas = browserPaneCanvasRefs.current[windowId];
    if (!located || !canvas || located.windowItem.browserPageMode !== "edit") {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    paneInteractionRef.current = {
      kind: "drag",
      windowId,
      paneId,
      rect,
      startX: event.clientX,
      startY: event.clientY,
      originX: Number(located.pane.x || 0),
      originY: Number(located.pane.y || 0),
    };
    focusPane(windowId, paneId);
    event.preventDefault();
    event.stopPropagation();
  }

  function handlePaneHeaderMouseDown(windowId, paneId, event) {
    if (event.target.closest("button, input, textarea, select, label")) {
      return;
    }
    beginPaneDrag(windowId, paneId, event);
  }

  function beginPaneResize(windowId, paneId, event) {
    const located = findPaneLocation(state, windowId, paneId);
    const canvas = browserPaneCanvasRefs.current[windowId];
    if (!located || !canvas || located.windowItem.browserPageMode !== "edit") {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const minimums = paneMinimums(located.pane);
    paneInteractionRef.current = {
      kind: "resize",
      windowId,
      paneId,
      rect,
      startX: event.clientX,
      startY: event.clientY,
      originWidth: Number(located.pane.width || minimums.width),
      originHeight: Number(located.pane.height || minimums.height),
      originPaneX: Number(located.pane.x || 0),
      originPaneY: Number(located.pane.y || 0),
      minimums,
    };
    focusPane(windowId, paneId);
    event.preventDefault();
    event.stopPropagation();
  }

  function beginWindowDrag(windowId, event) {
    const located = findWindowLocation(state, windowId);
    const canvas = workspaceCanvasRef.current;
    if (!located || located.windowItem.mode !== "docked" || !canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    windowInteractionRef.current = {
      kind: "drag",
      windowId,
      rect,
      startX: event.clientX,
      startY: event.clientY,
      originX: Number(located.windowItem.x || 0),
      originY: Number(located.windowItem.y || 0),
    };
    focusWindow(windowId);
    event.preventDefault();
  }

  function beginWindowResize(windowId, event) {
    const located = findWindowLocation(state, windowId);
    const canvas = workspaceCanvasRef.current;
    if (!located || located.windowItem.mode !== "docked" || !canvas) {
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const minimums = windowMinimums(located.windowItem);
    windowInteractionRef.current = {
      kind: "resize",
      windowId,
      rect,
      startX: event.clientX,
      startY: event.clientY,
      originWidth: Number(located.windowItem.width || minimums.width),
      originHeight: Number(located.windowItem.height || minimums.height),
      originWindowX: Number(located.windowItem.x || 0),
      originWindowY: Number(located.windowItem.y || 0),
      minimums,
    };
    focusWindow(windowId);
    event.preventDefault();
  }

  useEffect(() => {
    document.body.dataset.theme = state.preferences.theme;
    document.body.dataset.appMode = APP_MODE || "personal_agent";
  }, [state.preferences.theme]);

  useEffect(() => {
    document.body.classList.toggle("print-preview-open", Boolean(state.printDialog.open));
    return () => {
      document.body.classList.remove("print-preview-open");
    };
  }, [state.printDialog.open]);

  useEffect(() => {
    if (!state.printDialog.open || !state.printDialog.printing) {
      return undefined;
    }
    let active = true;
    const frameId = window.requestAnimationFrame(() => {
      if (!active) {
        return;
      }
      try {
        window.print();
      } catch (error) {
        console.error("Unable to open the browser print dialog.", error);
        updateState((next) => {
          next.printDialog = createPrintDialogState();
        });
      }
    });
    function handleAfterPrint() {
      if (!active) {
        return;
      }
      active = false;
      window.cancelAnimationFrame(frameId);
      updateState((next) => {
        next.printDialog = createPrintDialogState();
      });
    }
    window.addEventListener("afterprint", handleAfterPrint);
    return () => {
      active = false;
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("afterprint", handleAfterPrint);
    };
  }, [state.printDialog.open, state.printDialog.printing]);

  useEffect(() => {
    saveStoredPlazaAuthSession(
      state.preferences.connectionPlazaUrl,
      currentPlazaAccessSession(state),
    );
  }, [
    state.preferences.connectionPlazaUrl,
    state.plazaAccess.session,
    state.plazaAccess.sessionPlazaUrl,
  ]);

  useEffect(() => {
    const normalizedPlazaUrl = normalizePlazaUrl(state.preferences.connectionPlazaUrl || "");
    const previousPlazaUrl = previousPlazaAccessUrlRef.current;
    if (previousPlazaUrl === normalizedPlazaUrl) {
      return;
    }
    previousPlazaAccessUrlRef.current = normalizedPlazaUrl;
    updateState((next) => {
      const nextNormalizedPlazaUrl = normalizePlazaUrl(next.preferences.connectionPlazaUrl || "");
      next.plazaAccess.config = null;
      next.plazaAccess.configStatus = nextNormalizedPlazaUrl ? "idle" : "error";
      next.plazaAccess.configError = nextNormalizedPlazaUrl ? "" : "Plaza URL is required.";
      next.plazaAccess.authMessage = "";
      next.plazaAccess.keys = [];
      next.plazaAccess.keysStatus = "idle";
      next.plazaAccess.keysError = "";
      next.plazaAccess.keyMessage = "";
      next.plazaAccess.keyReveal = null;
      next.plazaAccess.pendingKeyId = "";
      next.plazaAccess.pendingKeyAction = "";
      if (normalizePlazaUrl(next.plazaAccess.sessionPlazaUrl || "") !== nextNormalizedPlazaUrl) {
        clearPlazaAccessSession(next, "");
        next.plazaAccess.configStatus = nextNormalizedPlazaUrl ? "idle" : "error";
        next.plazaAccess.configError = nextNormalizedPlazaUrl ? "" : "Plaza URL is required.";
      }
    });
  }, [state.preferences.connectionPlazaUrl]);

  useEffect(() => {
    const normalizedPlazaUrl = normalizePlazaUrl(state.preferences.connectionPlazaUrl || "");
    const sessionPlazaUrl = normalizePlazaUrl(state.plazaAccess.sessionPlazaUrl || "");
    if (!state.plazaAccess.session || !sessionPlazaUrl || sessionPlazaUrl === normalizedPlazaUrl) {
      return;
    }
    updateState((next) => {
      if (
        !next.plazaAccess.session
        || normalizePlazaUrl(next.plazaAccess.sessionPlazaUrl || "") === normalizePlazaUrl(next.preferences.connectionPlazaUrl || "")
      ) {
        return;
      }
      clearPlazaAccessSession(next, "Plaza URL changed. Sign in again for this Plaza.");
      next.plazaAccess.config = null;
      next.plazaAccess.configStatus = normalizedPlazaUrl ? "idle" : "error";
      next.plazaAccess.configError = normalizedPlazaUrl ? "" : "Plaza URL is required.";
    });
  }, [
    state.preferences.connectionPlazaUrl,
    state.plazaAccess.session,
    state.plazaAccess.sessionPlazaUrl,
  ]);

  useEffect(() => {
    const viewingPlazaAccess = state.settingsOpen && state.settingsTab === "plaza_access";
    if (!viewingPlazaAccess) {
      plazaAccessRefreshRef.current = "";
      return;
    }
    const plazaUrl = normalizePlazaUrl(state.preferences.connectionPlazaUrl || "");
    const session = currentPlazaAccessSession(state);
    const refreshKey = [plazaUrl, session?.access_token || "", session?.refresh_token || ""].join("|");
    if (plazaAccessRefreshRef.current === refreshKey) {
      return;
    }
    plazaAccessRefreshRef.current = refreshKey;
    let cancelled = false;
    (async () => {
      await refreshPlazaAccessConfig({ quiet: true });
      if (cancelled) {
        return;
      }
      if (session) {
        await refreshPlazaAccessUser({ quiet: true });
        if (cancelled) {
          return;
        }
        await refreshPlazaAccessKeys({ quiet: true });
        return;
      }
      updateState((next) => {
        if (normalizePlazaUrl(next.preferences.connectionPlazaUrl || "") !== plazaUrl) {
          return;
        }
        next.plazaAccess.user = null;
        next.plazaAccess.keys = [];
        next.plazaAccess.keysStatus = "idle";
        next.plazaAccess.keysError = "";
        next.plazaAccess.keyReveal = null;
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [
    state.settingsOpen,
    state.settingsTab,
    state.preferences.connectionPlazaUrl,
    state.plazaAccess.session,
    state.plazaAccess.sessionPlazaUrl,
  ]);

  useEffect(() => {
    const currentWorkspace = findWorkspace(state, state.activeWorkspaceId);
    const world = workspaceWorldMetrics(currentWorkspace);
    const canvas = workspaceCanvasRef.current;
    if (!canvas) {
      workspaceWorldRef.current = {
        workspaceId: state.activeWorkspaceId,
        offsetX: world.offsetX,
        offsetY: world.offsetY,
      };
      return;
    }
    const previous = workspaceWorldRef.current;
    if (previous.workspaceId === state.activeWorkspaceId) {
      const deltaX = world.offsetX - previous.offsetX;
      const deltaY = world.offsetY - previous.offsetY;
      if (deltaX) {
        canvas.scrollLeft += deltaX;
      }
      if (deltaY) {
        canvas.scrollTop += deltaY;
      }
    }
    workspaceWorldRef.current = {
      workspaceId: state.activeWorkspaceId,
      offsetX: world.offsetX,
      offsetY: world.offsetY,
    };
  }, [state.activeWorkspaceId, state.workspaces]);

  useEffect(() => {
    saveStorage(currentPreferenceStorageKey(), state.preferences);
  }, [state.preferences]);

  useEffect(() => {
    saveStorage(STORAGE_KEYS.workspaces, {
      activeWorkspaceId: state.activeWorkspaceId,
      workspaces: serializeWorkspacesForStorage(state.workspaces),
    });
  }, [state.workspaces, state.activeWorkspaceId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cachedLayouts = getWorkspaceLayouts();
      let preparedState = state;
      try {
        const prepared = await ensureStoragePulserReady(state);
        preparedState = prepared.appState;
      } catch (error) {
        if (cancelled) {
          return;
        }
        updateState((next) => {
          if (next.workspaceDialog.open && next.workspaceDialog.mode === "load") {
            next.workspaceDialog.selectedLayoutId = next.workspaceDialog.selectedLayoutId || cachedLayouts[0]?.id || "";
            next.workspaceDialog.error = cachedLayouts.length
              ? ""
              : (error.message || "Unable to load saved workspaces from the configured storage location.");
          }
        });
        return;
      }
      try {
        const layouts = await refreshWorkspaceLayoutsFromConfiguredStorage(preparedState);
        if (cancelled) {
          return;
        }
        updateState((next) => {
          if (next.workspaceDialog.open && next.workspaceDialog.mode === "load") {
            next.workspaceDialog.selectedLayoutId = layouts[0]?.id || "";
            next.workspaceDialog.error = layouts.length ? "" : "No saved workspaces yet.";
          }
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        updateState((next) => {
          if (next.workspaceDialog.open && next.workspaceDialog.mode === "load") {
            next.workspaceDialog.selectedLayoutId = next.workspaceDialog.selectedLayoutId || cachedLayouts[0]?.id || "";
            next.workspaceDialog.error = cachedLayouts.length
              ? ""
              : (error.message || "Unable to load saved workspaces from the configured storage location.");
          }
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    state.preferences.fileSaveBackend,
    state.preferences.fileSaveLocalDirectory,
    state.preferences.fileSavePulserId,
    state.preferences.fileSavePulserName,
    state.preferences.fileSavePulserAddress,
    state.preferences.fileSaveBucketName,
    state.preferences.fileSaveObjectPrefix,
    state.preferences.connectionPlazaUrl,
    state.globalPlazaStatus.plazaUrl,
  ]);

  useEffect(() => {
    if (normalizeFileSaveBackend(state.preferences.fileSaveBackend) !== "system_pulser") {
      storagePlazaRefreshRef.current = "";
      return;
    }
    const plazaUrl = String(state.preferences.connectionPlazaUrl || "").trim();
    const refreshKey = `${plazaUrl}|${state.preferences.fileSavePulserId || state.preferences.fileSavePulserAddress || state.preferences.fileSavePulserName || ""}`;
    if (!plazaUrl || state.globalPlazaStatus.status === "loading" || selectedSystemPulser(state.preferences, availableSystemPulsers(state))) {
      storagePlazaRefreshRef.current = refreshKey;
      return;
    }
    if (storagePlazaRefreshRef.current === refreshKey) {
      return;
    }
    storagePlazaRefreshRef.current = refreshKey;
    void refreshGlobalPlaza();
  }, [
    state.preferences.fileSaveBackend,
    state.preferences.connectionPlazaUrl,
    state.preferences.fileSavePulserId,
    state.preferences.fileSavePulserName,
    state.preferences.fileSavePulserAddress,
    state.globalPlazaStatus.status,
    state.globalPlazaStatus.pulserCount,
  ]);

  useEffect(() => {
    const usingSystemPulser = normalizeFileSaveBackend(state.preferences.fileSaveBackend) === "system_pulser";
    const viewingStorageSettings = state.settingsOpen && state.settingsTab === "storage";
    if (!usingSystemPulser || !viewingStorageSettings) {
      storageBucketRefreshRef.current = "";
      setStorageBuckets([]);
      setStorageBucketStatus("idle");
      setStorageBucketError("");
      setStorageBucketAddMode(false);
      setStorageBucketDraft("");
      setStorageBucketCreateStatus("idle");
      return;
    }
    const refreshKey = [
      state.preferences.connectionPlazaUrl,
      state.preferences.fileSavePulserId,
      state.preferences.fileSavePulserName,
      state.preferences.fileSavePulserAddress,
      state.globalPlazaStatus.status,
      state.globalPlazaStatus.pulserCount,
      state.globalPlazaStatus.plazaUrl,
    ].join("|");
    if (storageBucketRefreshRef.current === refreshKey) {
      return;
    }
    storageBucketRefreshRef.current = refreshKey;
    setStorageBucketStatus("loading");
    setStorageBucketError("");
    let cancelled = false;
    (async () => {
      try {
        const buckets = await fetchStorageBucketCatalog();
        if (cancelled) {
          return;
        }
        setStorageBuckets(buckets);
        setStorageBucketStatus("ready");
        setStorageBucketError("");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setStorageBuckets([]);
        setStorageBucketStatus("error");
        setStorageBucketError(error.message || "Unable to load storage buckets.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    state.settingsOpen,
    state.settingsTab,
    state.preferences.fileSaveBackend,
    state.preferences.connectionPlazaUrl,
    state.preferences.fileSavePulserId,
    state.preferences.fileSavePulserName,
    state.preferences.fileSavePulserAddress,
    state.globalPlazaStatus.status,
    state.globalPlazaStatus.pulserCount,
    state.globalPlazaStatus.plazaUrl,
  ]);

  useEffect(() => {
    if (!state.preferences.connectionPlazaUrl) {
      return;
    }
    state.workspaces.forEach((workspaceEntry) => {
      workspaceEntry.windows.forEach((windowItem) => {
        if (windowItem.type === "browser" && windowItem.browserCatalog?.status === "idle") {
          refreshBrowserCatalog(windowItem.id);
        }
        if (windowItem.type === "mind_map" && windowItem.mindMapCatalog?.status === "idle") {
          refreshMindMapCatalog(windowItem.id);
        }
      });
    });
  }, [state.workspaces, state.preferences.connectionPlazaUrl]);

  useEffect(() => {
    if (!state.paneMenuWindowId) {
      return undefined;
    }
    function handlePointerDown(event) {
      if (event.target.closest(".pane-dropdown")) {
        return;
      }
      updateState((next) => {
        next.paneMenuWindowId = "";
      });
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [state.paneMenuWindowId]);

  useEffect(() => {
    if (!state.menuBarMenuId) {
      return undefined;
    }
    function handlePointerDown(event) {
      if (event.target.closest(".app-menu, .app-menu-dropdown")) {
        return;
      }
      updateState((next) => {
        next.menuBarMenuId = "";
      });
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [state.menuBarMenuId]);

  useEffect(() => {
    if (!state.menuBarMenuId) {
      return undefined;
    }
    function handleViewportChange() {
      updateState((next) => {
        next.menuBarMenuId = "";
      });
    }
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [state.menuBarMenuId]);

  useEffect(() => {
    if (!IS_MAP_PHEMAR_MODE || initialPhemaLoadRef.current) {
      return undefined;
    }
    const initialDraftPhema = consumeMapPhemarLaunchDraftFromLocation();
    const initialPhemaId = initialDraftPhema ? "" : String(BOOTSTRAP?.meta?.initial_phema_id || "").trim();
    initialPhemaLoadRef.current = true;
    if (!(initialDraftPhema || initialPhemaId)) {
      return undefined;
    }
    const primaryWindow = activeWindowList().find((entry) => entry.type === "mind_map");
    if (!primaryWindow) {
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const phema = initialDraftPhema || await fetchMapPhema(initialPhemaId, state);
        if (!(phema && typeof phema === "object")) {
          return;
        }
        if (cancelled) {
          return;
        }
        updateState((next) => {
          const source = resolveMindMapSource(next, primaryWindow.id);
          if (!source) {
            return;
          }
          const restored = deserializeMindMapFromPhema(phema, next.preferences, next.dashboard);
          source.windowLocation.windowItem.mindMapState = restored;
          source.windowLocation.windowItem.title = String(phema.name || source.windowLocation.windowItem.title || "Untitled Phema");
          source.windowLocation.windowItem.subtitle = "Diagram-backed Phema";
        });
      } catch (error) {
        console.error("Failed to load initial MapPhemar document.", error);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.workspaces, state.activeWorkspaceId]);

  useEffect(() => {
    if (IS_MAP_PHEMAR_MODE) {
      return undefined;
    }
    let cancelled = false;

    async function syncLinkedMindMapsFromOwner() {
      const phemasById = await fetchLinkedMindMapPhemas(state);
      if (cancelled || !phemasById.size) {
        return;
      }
      updateState((next) => {
        applyLinkedMindMapPhemas(next, phemasById);
      });
    }

    function handleFocus() {
      void syncLinkedMindMapsFromOwner();
    }

    window.addEventListener("focus", handleFocus);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", handleFocus);
    };
  }, [state.workspaces, state.preferences, state.dashboard]);

  useEffect(() => {
    if (IS_MAP_PHEMAR_MODE) {
      return undefined;
    }

    function handleMapPhemarReturn(event) {
      if (event.origin !== window.location.origin) {
        return;
      }
      const payload = event.data;
      if (!payload || payload.type !== MAP_PHEMAR_RETURN_MESSAGE_TYPE) {
        return;
      }
      const context = normalizeMapPhemarReturnContext(payload.context);
      const returnedPhema = payload.phema && typeof payload.phema === "object" ? payload.phema : null;
      try {
        updateState((next) => {
          if (context.workspaceId && findWorkspace(next, context.workspaceId)) {
            next.activeWorkspaceId = context.workspaceId;
            next.preferences.defaultWorkspaceId = context.workspaceId;
          }
          const targetWindowId = context.browserWindowId || context.windowId;
          if (targetWindowId) {
            const focusedWindow = focusWindowInState(next, targetWindowId);
            if (focusedWindow?.workspace?.id) {
              next.activeWorkspaceId = focusedWindow.workspace.id;
              next.preferences.defaultWorkspaceId = focusedWindow.workspace.id;
            }
          }
          if (context.browserWindowId && context.paneId) {
            const focusedPane = focusPaneInState(next, context.browserWindowId, context.paneId);
            if (focusedPane?.workspace?.id) {
              next.activeWorkspaceId = focusedPane.workspace.id;
              next.preferences.defaultWorkspaceId = focusedPane.workspace.id;
            }
          }
          next.paneMenuWindowId = "";
          next.menuBarMenuId = "";
          if (returnedPhema) {
            const returnedPhemaId = String(returnedPhema?.phema_id || returnedPhema?.id || "").trim();
            applyReturnedMapPhemaToContext(next, context, returnedPhema);
            if (returnedPhemaId) {
              applyLinkedMindMapPhemas(next, new Map([[returnedPhemaId, returnedPhema]]));
            }
          }
        });
      } catch (error) {
        console.error("Unable to process the MapPhemar return payload in Personal Agent.", error);
      }
      window.focus();
      if (!returnedPhema) {
        void fetchLinkedMindMapPhemas(latestStateRef.current)
          .then((phemasById) => {
            if (!phemasById.size) {
              return;
            }
            updateState((next) => {
              applyLinkedMindMapPhemas(next, phemasById);
            });
          })
          .catch((error) => {
            console.error("Unable to refresh linked MapPhemar diagrams after returning to the agent.", error);
          });
      }
    }

    window.addEventListener("message", handleMapPhemarReturn);
    return () => {
      window.removeEventListener("message", handleMapPhemarReturn);
    };
  }, []);

  useEffect(() => {
    function handlePointerMove(event) {
      const interaction = windowInteractionRef.current;
      if (interaction) {
        updateState((next) => {
          const located = findWindowLocation(next, interaction.windowId);
          if (!located) {
            return;
          }
          const target = located.windowItem;
          if (interaction.kind === "drag") {
            const nextX = interaction.originX + (event.clientX - interaction.startX);
            const nextY = interaction.originY + (event.clientY - interaction.startY);
            target.x = Math.max(Math.round(nextX), WORKSPACE_LEFT_INSET);
            target.y = Math.max(Math.round(nextY), WORKSPACE_TOP_INSET);
            return;
          }
          const minimums = interaction.minimums || windowMinimums(target);
          const nextWidth = interaction.originWidth + (event.clientX - interaction.startX);
          const nextHeight = interaction.originHeight + (event.clientY - interaction.startY);
          target.width = Math.max(Math.round(nextWidth), minimums.width);
          target.height = Math.max(Math.round(nextHeight), minimums.height);
        });
        return;
      }
      const paneInteraction = paneInteractionRef.current;
      if (!paneInteraction) {
        return;
      }
      updateState((next) => {
        const located = findPaneLocation(next, paneInteraction.windowId, paneInteraction.paneId);
        if (!located) {
          return;
        }
        const target = located.pane;
        if (paneInteraction.kind === "drag") {
          const nextX = paneInteraction.originX + (event.clientX - paneInteraction.startX);
          const nextY = paneInteraction.originY + (event.clientY - paneInteraction.startY);
          const maxX = Math.max(paneInteraction.rect.width - Number(target.width || 0), 0);
          const maxY = Math.max(paneInteraction.rect.height - Number(target.height || 0), 0);
          target.x = clamp(nextX, 0, maxX);
          target.y = clamp(nextY, 0, maxY);
          return;
        }
        const minimums = paneInteraction.minimums || paneMinimums(target);
        const nextWidth = paneInteraction.originWidth + (event.clientX - paneInteraction.startX);
        const nextHeight = paneInteraction.originHeight + (event.clientY - paneInteraction.startY);
        const maxWidth = Math.max(paneInteraction.rect.width - Number(target.x || paneInteraction.originPaneX || 0), minimums.width);
        const maxHeight = Math.max(paneInteraction.rect.height - Number(target.y || paneInteraction.originPaneY || 0), minimums.height);
        target.width = clamp(nextWidth, minimums.width, maxWidth);
        target.height = clamp(nextHeight, minimums.height, maxHeight);
      });
    }

    function finishPointerInteraction() {
      windowInteractionRef.current = null;
      paneInteractionRef.current = null;
    }

    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", finishPointerInteraction);
    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", finishPointerInteraction);
    };
  }, []);

  async function requestCatalog(plazaUrl) {
    const normalizedUrl = normalizePlazaUrl(plazaUrl);
    const params = new URLSearchParams({ plaza_url: normalizedUrl });

    try {
      const response = await fetch(`/api/plaza/catalog?${params.toString()}`);
      const payload = await loadJsonResponse(response);
      if (!response.ok) {
        throw new Error(payload.detail || payload.message || "Unable to load Plaza catalog.");
      }
      return standardizeCatalogPayload(payload, normalizedUrl);
    } catch (proxyError) {
      try {
        return await requestCatalogDirect(normalizedUrl);
      } catch (directError) {
        throw new Error(directError.message || proxyError.message || "Unable to load Plaza catalog.");
      }
    }
  }

  async function ensureStoragePulserReady(appState = state) {
    if (normalizeFileSaveBackend(appState.preferences.fileSaveBackend) !== "system_pulser") {
      return { appState, pulser: null };
    }
    const plazaUrl = String(appState.preferences.connectionPlazaUrl || "").trim();
    const exactPulser = selectedSystemPulser(appState.preferences, availableSystemPulsers(appState));
    if (exactPulser || !plazaUrl) {
      return {
        appState,
        pulser: configuredSystemPulser(appState.preferences, appState),
      };
    }

    try {
      updateState((next) => {
        next.globalPlazaStatus = {
          ...emptyCatalog(plazaUrl),
          status: "loading",
          error: "",
        };
      });
      const payload = await requestCatalog(plazaUrl);
      const refreshedStatus = {
        ...payload,
        status: "ready",
        error: "",
      };
      updateState((next) => {
        next.globalPlazaStatus = refreshedStatus;
      });
      const refreshedAppState = {
        ...appState,
        globalPlazaStatus: refreshedStatus,
      };
      return {
        appState: refreshedAppState,
        pulser: configuredSystemPulser(refreshedAppState.preferences, refreshedAppState),
      };
    } catch (error) {
      updateState((next) => {
        next.globalPlazaStatus = {
          ...emptyCatalog(plazaUrl),
          status: "error",
          error: error.message || "Unable to load Plaza catalog.",
        };
      });
      const fallbackPulser = configuredSystemPulser(appState.preferences, appState);
      if (fallbackPulser) {
        return { appState, pulser: fallbackPulser };
      }
      throw error;
    }
  }

  function storagePulserRequestBase(appState, preferences, pulser) {
    return {
      plaza_url: appState.globalPlazaStatus.plazaUrl || preferences.connectionPlazaUrl,
      pulser_id: pulser.agent_id || "",
      pulser_name: pulser.name || "",
      pulser_address: pulser.address || "",
      practice_id: pulser.practice_id || "get_pulse_data",
    };
  }

  function sortStorageBucketRows(rows) {
    return [...(Array.isArray(rows) ? rows : [])].sort((left, right) => (
      String(left?.bucket_name || left?.name || "").localeCompare(String(right?.bucket_name || right?.name || ""))
      || String(left?.visibility || "").localeCompare(String(right?.visibility || ""))
    ));
  }

  async function fetchStorageBucketCatalog(preferencesOverride = null) {
    const normalizedPreferences = normalizePreferences(preferencesOverride || state.preferences, state.dashboard);
    if (normalizeFileSaveBackend(normalizedPreferences.fileSaveBackend) !== "system_pulser") {
      return [];
    }
    const prepared = await ensureStoragePulserReady({
      ...state,
      preferences: normalizedPreferences,
    });
    const pulser = prepared.pulser || configuredSystemPulser(normalizedPreferences, prepared.appState);
    if (!pulser) {
      return [];
    }
    const listBucketPulse = fileStoragePulserListBucketPulse(pulser);
    if (!listBucketPulse) {
      throw new Error("Selected SystemPulser does not expose list_bucket.");
    }
    const payload = unwrapStoragePulserPayload(await runPulserRequest({
      ...storagePulserRequestBase(prepared.appState, normalizedPreferences, pulser),
      pulse_name: listBucketPulse.pulse_name || listBucketPulse.name || "list_bucket",
      pulse_address: listBucketPulse.pulse_address || "",
      output_schema: listBucketPulse.output_schema || {},
      input: {
        visibility: "all",
        limit: 500,
      },
    }), "Unable to load storage buckets.");
    return sortStorageBucketRows(Array.isArray(payload?.buckets) ? payload.buckets : []);
  }

  async function refreshStorageBucketCatalog(preferencesOverride = null) {
    setStorageBucketStatus("loading");
    setStorageBucketError("");
    try {
      const buckets = await fetchStorageBucketCatalog(preferencesOverride);
      setStorageBuckets(buckets);
      setStorageBucketStatus("ready");
      return buckets;
    } catch (error) {
      setStorageBuckets([]);
      setStorageBucketStatus("error");
      setStorageBucketError(error.message || "Unable to load storage buckets.");
      throw error;
    }
  }

  async function createStorageBucket() {
    const bucketName = String(storageBucketDraft || "").trim();
    if (!bucketName) {
      setStorageBucketError("Enter a bucket name before creating a bucket.");
      return;
    }
    setStorageBucketCreateStatus("loading");
    setStorageBucketError("");
    try {
      const normalizedPreferences = normalizePreferences(state.preferences, state.dashboard);
      const prepared = await ensureStoragePulserReady({
        ...state,
        preferences: normalizedPreferences,
      });
      const pulser = prepared.pulser || configuredSystemPulser(normalizedPreferences, prepared.appState);
      if (!pulser) {
        throw new Error("Choose a SystemPulser in Settings before creating a bucket.");
      }
      const createBucketPulse = fileStoragePulserCreateBucketPulse(pulser);
      if (!createBucketPulse) {
        throw new Error("Selected SystemPulser does not expose bucket_create.");
      }
      const createdBucket = unwrapStoragePulserPayload(await runPulserRequest({
        ...storagePulserRequestBase(prepared.appState, normalizedPreferences, pulser),
        pulse_name: createBucketPulse.pulse_name || createBucketPulse.name || "bucket_create",
        pulse_address: createBucketPulse.pulse_address || "",
        output_schema: createBucketPulse.output_schema || {},
        input: {
          bucket_name: bucketName,
          visibility: "private",
        },
      }), "Unable to create the storage bucket.");
      const createdBucketName = String(createdBucket?.bucket_name || bucketName).trim() || bucketName;
      updateState((next) => {
        next.preferences.fileSaveBucketName = createdBucketName;
      });
      setStorageBucketAddMode(false);
      setStorageBucketDraft("");
      setStorageBucketCreateStatus("idle");
      try {
        await refreshStorageBucketCatalog({
          ...state.preferences,
          fileSaveBucketName: createdBucketName,
        });
      } catch (refreshError) {
        setStorageBuckets((current) => sortStorageBucketRows([
          ...current,
          {
            bucket_name: createdBucketName,
            visibility: createdBucket?.visibility || "private",
          },
        ]));
        setStorageBucketStatus("ready");
        setStorageBucketError("");
      }
    } catch (error) {
      setStorageBucketCreateStatus("error");
      setStorageBucketError(error.message || "Unable to create the storage bucket.");
    }
  }

  function syncPaneWithCatalog(windowItem, pane, preferences, globalCatalog = null) {
    if (!isDataPaneType(pane?.type)) {
      return;
    }
    const catalog = resolveBrowserCatalog(windowItem, preferences, globalCatalog);
    const pulseCatalog = collectCatalogPulses(catalog);
    const selectedPulse = findSelectedCatalogPulse(pulseCatalog, pane);
    if (!selectedPulse) {
      pane.pulserId = "";
      pane.pulserName = "";
      pane.pulserAddress = "";
      pane.practiceId = "get_pulse_data";
      pane.pulseName = "";
      pane.pulseAddress = "";
      pane.outputSchema = {};
      return;
    }
    const compatiblePulser = findSelectedCompatiblePulser(selectedPulse, pane) || selectedPulse.compatible_pulsers?.[0] || null;
    const pulse = compatiblePulser?.pulse || selectedPulse;
    pane.pulserId = compatiblePulser?.pulser_id || "";
    pane.pulserName = compatiblePulser?.pulser_name || "";
    pane.pulserAddress = compatiblePulser?.pulser_address || "";
    pane.practiceId = compatiblePulser?.practice_id || "get_pulse_data";
    pane.pulseName = pulse?.pulse_name || selectedPulse.pulse_name || "";
    pane.pulseAddress = pulse?.pulse_address || selectedPulse.pulse_address || "";
    pane.outputSchema = pulse?.output_schema || selectedPulse.output_schema || {};
  }

  function syncMindMapNodeWithCatalog(source, node, { resetPulse = false } = {}) {
    if (isBoundaryMindMapNode(node) || isBranchMindMapNode(node)) {
      return;
    }
    const catalog = source.catalog || emptyCatalog(source.mapState.plazaUrl);
    const pulsers = Array.isArray(catalog.pulsers) ? catalog.pulsers : [];
    const dynamicPulses = () => {
      const merged = new Map();
      pulsers.forEach((pulser) => {
        (pulser.supported_pulses || []).forEach((pulse) => {
          const key = String(pulse.pulse_address || pulse.pulse_name || createId("pulse")).toLowerCase();
          if (!merged.has(key)) {
            merged.set(key, {
              ...pulse,
              preferred_pulser_id: pulser.agent_id || "",
              preferred_pulser_name: pulser.name || "",
              preferred_pulser_address: pulser.address || "",
              preferred_practice_id: pulser.practice_id || "get_pulse_data",
            });
          }
        });
      });
      return Array.from(merged.values());
    };

    let pulseList = [];
    if (node.pulserMode === "dynamic") {
      pulseList = dynamicPulses();
      const pulse = resetPulse
        ? pulseList[0]
        : pulseList.find((entry) => entry.pulse_address === node.pulseAddress || entry.pulse_name === node.pulseName) || pulseList[0];
      node.pulserId = pulse?.preferred_pulser_id || "";
      node.pulserName = pulse?.preferred_pulser_name || "";
      node.pulserAddress = pulse?.preferred_pulser_address || "";
      node.practiceId = pulse?.preferred_practice_id || "get_pulse_data";
      if (pulse) {
        node.pulseName = pulse.pulse_name || "";
        node.pulseAddress = pulse.pulse_address || "";
        node.body = pulse.description || pulse.pulse_definition?.description || "";
        node.inputSchema = pulse.input_schema || {};
        node.outputSchema = pulse.output_schema || {};
        node.paramsText = JSON.stringify(getSampleParameters(pulse), null, 2) || "{}";
        if (!node.title || node.title.startsWith("Pulse ")) {
          node.title = pulse.pulse_name || node.title;
        }
      }
      return;
    }

    const pulser = pulsers.find((entry) => entry.agent_id === node.pulserId)
      || pulsers.find((entry) => entry.name === node.pulserName)
      || pulsers[0]
      || null;
    node.pulserId = pulser?.agent_id || "";
    node.pulserName = pulser?.name || "";
    node.pulserAddress = pulser?.address || "";
    node.practiceId = pulser?.practice_id || "get_pulse_data";
    pulseList = pulser?.supported_pulses || [];
    const preferred = pulseList.find((entry) => MINDMAP_PREFERRED_PULSES.includes(String(entry.pulse_name || "")));
    const pulse = resetPulse
      ? preferred || pulseList[0]
      : pulseList.find((entry) => entry.pulse_address === node.pulseAddress || entry.pulse_name === node.pulseName) || preferred || pulseList[0];
    if (pulse) {
      node.pulseName = pulse.pulse_name || "";
      node.pulseAddress = pulse.pulse_address || "";
      node.body = pulse.description || pulse.pulse_definition?.description || "";
      node.inputSchema = pulse.input_schema || {};
      node.outputSchema = pulse.output_schema || {};
      node.paramsText = JSON.stringify(getSampleParameters(pulse), null, 2) || "{}";
      if (!node.title || node.title.startsWith("Pulse ")) {
        node.title = pulse.pulse_name || node.title;
      }
    }
  }

  async function refreshGlobalPlaza() {
    const plazaUrl = String(state.preferences.connectionPlazaUrl || "").trim();
    updateState((next) => {
      next.globalPlazaStatus = {
        ...emptyCatalog(plazaUrl),
        status: "loading",
        error: "",
      };
    });
    try {
      const payload = await requestCatalog(plazaUrl);
      updateState((next) => {
        next.globalPlazaStatus = {
          ...payload,
          status: "ready",
          error: "",
        };
      });
    } catch (error) {
      updateState((next) => {
        next.globalPlazaStatus = {
          ...emptyCatalog(plazaUrl),
          status: "error",
          error: error.message,
        };
      });
    }
  }

  async function refreshBrowserCatalog(windowId) {
    const located = findWindowLocation(state, windowId);
    if (!located || located.windowItem.type !== "browser") {
      return;
    }
    const plazaUrl = String(located.windowItem.browserDefaults?.plazaUrl || state.preferences.connectionPlazaUrl || "").trim();
    updateState((next) => {
      const target = findWindowLocation(next, windowId).windowItem;
      target.browserCatalog = {
        ...emptyCatalog(plazaUrl),
        status: "loading",
      };
    });
    try {
      const payload = await requestCatalog(plazaUrl);
      updateState((next) => {
        const target = findWindowLocation(next, windowId).windowItem;
        target.browserCatalog = {
          ...payload,
          status: "ready",
          error: "",
        };
        target.panes.forEach((pane) => syncPaneWithCatalog(target, pane, next.preferences, payload));
        next.globalPlazaStatus = {
          ...payload,
          status: "ready",
          error: "",
        };
      });
    } catch (error) {
      updateState((next) => {
        const target = findWindowLocation(next, windowId).windowItem;
        target.browserCatalog = {
          ...emptyCatalog(plazaUrl),
          status: "error",
          error: error.message,
        };
      });
    }
  }

  async function refreshMindMapCatalog(windowId) {
    const source = resolveMindMapSource(state, windowId);
    if (!source) {
      return;
    }
    const plazaUrl = String(state.preferences.connectionPlazaUrl || "").trim();
    updateState((next) => {
      const targetWindow = findWindowLocation(next, windowId).windowItem;
      targetWindow.mindMapCatalog = {
        ...emptyCatalog(plazaUrl),
        status: "loading",
      };
    });
    try {
      const payload = await requestCatalog(plazaUrl);
      updateState((next) => {
        const refreshed = resolveMindMapSource(next, windowId);
        if (!refreshed) {
          return;
        }
        refreshed.windowLocation.windowItem.mindMapCatalog = {
          ...payload,
          status: "ready",
          error: "",
        };
        refreshed.mapState.nodes.forEach((node) => syncMindMapNodeWithCatalog(refreshed, node));
        next.globalPlazaStatus = {
          ...payload,
          status: "ready",
          error: "",
        };
      });
    } catch (error) {
      updateState((next) => {
        const refreshed = resolveMindMapSource(next, windowId);
        if (!refreshed) {
          return;
        }
        refreshed.windowLocation.windowItem.mindMapCatalog = {
          ...emptyCatalog(plazaUrl),
          status: "error",
          error: error.message,
        };
      });
    }
  }

  function openDiagramRunDialog(windowId) {
    const source = resolveMindMapSource(state, windowId);
    if (!source) {
      return;
    }
    const readiness = mindMapRunReadiness(source.mapState, state.preferences.connectionPlazaUrl, source.catalog);
    if (!readiness.canRun) {
      return;
    }
    const template = readiness.startNode
      ? mindMapRunInputTemplate(readiness.startNode, source.catalog, source.mapState?.plazaUrl || state.preferences.connectionPlazaUrl)
      : {};
    updateState((next) => {
      const refreshed = resolveMindMapSource(next, windowId);
      if (!refreshed) {
        return;
      }
      next.diagramRunDialog = {
        ...createDiagramRunDialogState(),
        open: true,
        windowId,
        inputText: schemaTextValue(template),
      };
    });
  }

  function closeDiagramRunDialog() {
    updateState((next) => {
      next.diagramRunDialog = createDiagramRunDialogState();
    });
  }

  function updateDiagramRunInput(text) {
    updateState((next) => {
      if (!next.diagramRunDialog.open) {
        return;
      }
      next.diagramRunDialog.inputText = text;
      next.diagramRunDialog.inputError = "";
      next.diagramRunDialog.error = "";
    });
  }

  async function runMindMapDiagram(windowId) {
    const source = resolveMindMapSource(state, windowId);
    if (!source) {
      return;
    }
    const readiness = mindMapRunReadiness(source.mapState, state.preferences.connectionPlazaUrl, source.catalog);
    if (!readiness.canRun) {
      updateState((next) => {
        if (next.diagramRunDialog.windowId !== windowId) {
          return;
        }
        next.diagramRunDialog.error = readiness.reason;
        next.diagramRunDialog.status = "error";
      });
      return;
    }
    const dialogInputText = state.diagramRunDialog.windowId === windowId
      ? state.diagramRunDialog.inputText
      : schemaTextValue(
        readiness.startNode
          ? mindMapRunInputTemplate(readiness.startNode, source.catalog, source.mapState?.plazaUrl || state.preferences.connectionPlazaUrl)
          : {},
      );
    const invalid = {};
    const parsedInput = safeJsonParse(dialogInputText, invalid);
    if (!parsedInput || typeof parsedInput !== "object" || Array.isArray(parsedInput) || parsedInput === invalid) {
      updateState((next) => {
        if (next.diagramRunDialog.windowId !== windowId) {
          return;
        }
        next.diagramRunDialog.inputError = "Initial input must be a JSON object.";
        next.diagramRunDialog.status = "idle";
      });
      return;
    }
    const normalizedInput = cloneValue(parsedInput);
    const startedAt = new Date().toLocaleTimeString("en-US", { hour12: false });
    updateState((next) => {
      next.diagramRunDialog = {
        ...next.diagramRunDialog,
        open: true,
        windowId,
        inputText: schemaTextValue(normalizedInput),
        inputError: "",
        status: "loading",
        steps: [],
        error: "",
        startedAt,
        finishedAt: "",
      };
    });
    try {
      const execution = await executeMindMap(
        source,
        state.preferences.connectionPlazaUrl,
        normalizedInput,
        (steps) => {
          updateState((next) => {
            if (next.diagramRunDialog.windowId !== windowId) {
              return;
            }
            next.diagramRunDialog.steps = cloneValue(steps);
          });
        },
      );
      updateState((next) => {
        if (next.diagramRunDialog.windowId !== windowId) {
          return;
        }
        next.diagramRunDialog.steps = cloneValue(execution.steps);
        next.diagramRunDialog.status = "success";
        next.diagramRunDialog.error = "";
        next.diagramRunDialog.finishedAt = new Date().toLocaleTimeString("en-US", { hour12: false });
      });
    } catch (error) {
      const steps = Array.isArray(error?.diagramSteps) ? error.diagramSteps : [];
      updateState((next) => {
        if (next.diagramRunDialog.windowId !== windowId) {
          return;
        }
        next.diagramRunDialog.steps = cloneValue(steps);
        next.diagramRunDialog.status = "error";
        next.diagramRunDialog.error = error.message || "Diagram execution failed.";
        next.diagramRunDialog.finishedAt = new Date().toLocaleTimeString("en-US", { hour12: false });
      });
    }
  }

  async function runBrowserPane(windowId, paneId) {
    const located = findPaneLocation(state, windowId, paneId);
    if (!located) {
      return;
    }
    if (isOperatorPaneType(located.pane.type)) {
      await refreshOperatorMonitor(windowId, paneId, { preserveSelection: true });
      return;
    }
    if (!isDataPaneType(located.pane.type)) {
      return;
    }
    const windowItem = located.windowItem;
    const pane = cloneValue(located.pane);
    if (pane.type === "mind_map") {
      const invalid = {};
      const paneParams = safeJsonParse(pane.paramsText || "{}", invalid);
      if (!paneParams || typeof paneParams !== "object" || Array.isArray(paneParams) || paneParams === invalid) {
        updateState((next) => {
          const target = findPaneLocation(next, windowId, paneId)?.pane;
          if (!target) {
            return;
          }
          target.status = "error";
          target.error = "Diagram input must be a JSON object.";
        });
        return;
      }
      const input = cloneValue(paneParams);
      if (windowItem.browserDefaults.symbol) {
        input.symbol = windowItem.browserDefaults.symbol;
      }
      if (windowItem.browserDefaults.interval) {
        input.interval = windowItem.browserDefaults.interval;
      }
      if (windowItem.browserDefaults.limit) {
        input.limit = Number(windowItem.browserDefaults.limit) || windowItem.browserDefaults.limit;
      }
      if (windowItem.browserDefaults.startDate) {
        input.start_date = windowItem.browserDefaults.startDate;
      }
      if (windowItem.browserDefaults.endDate) {
        input.end_date = windowItem.browserDefaults.endDate;
      }
      const source = {
        windowLocation: located,
        mapState: pane.mindMapState || createDefaultMindMapState(state.preferences, state.dashboard),
        catalog: resolveBrowserCatalog(windowItem, state.preferences, state.globalPlazaStatus),
        linkedPaneLocation: located,
      };
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId)?.pane;
        if (!target) {
          return;
        }
        target.status = "loading";
        target.error = "";
      });
      try {
        const execution = await executeMindMap(source, state.preferences.connectionPlazaUrl, input);
        updateState((next) => {
          const target = findPaneLocation(next, windowId, paneId)?.pane;
          if (!target) {
            return;
          }
          target.status = "ready";
          target.error = "";
          target.result = execution.output;
          target.lastRunAt = new Date().toLocaleTimeString("en-US", { hour12: false });
          if (!target.fieldPaths.length) {
            const options = getFieldOptions(target.result);
            target.fieldPaths = options[0]?.path ? [options[0].path] : [];
          }
        });
      } catch (error) {
        updateState((next) => {
          const target = findPaneLocation(next, windowId, paneId)?.pane;
          if (!target) {
            return;
          }
          target.status = "error";
          target.error = error.message || "Diagram execution failed.";
        });
      }
      return;
    }
    syncPaneWithCatalog(windowItem, pane, state.preferences, state.globalPlazaStatus);
    const browserCatalog = resolveBrowserCatalog(windowItem, state.preferences, state.globalPlazaStatus);
    if (!pane.pulserId || !pane.pulseName) {
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId).pane;
        target.status = "error";
        target.error = "Choose a pulser and pulse before running.";
      });
      return;
    }
    updateState((next) => {
      const target = findPaneLocation(next, windowId, paneId).pane;
      target.status = "loading";
      target.error = "";
    });
    const pulser = (browserCatalog?.pulsers || []).find((entry) => entry.agent_id === pane.pulserId) || null;
    const pulse = (pulser?.supported_pulses || []).find((entry) => entry.pulse_name === pane.pulseName || entry.pulse_address === pane.pulseAddress) || null;
    const defaultParams = safeJsonParse(state.preferences.connectionDefaultParamsText || "{}", {});
    const paneParams = safeJsonParse(pane.paramsText || "{}", {});
    const input = {
      ...getSampleParameters(pulse),
      ...defaultParams,
      ...paneParams,
    };
    if (windowItem.browserDefaults.symbol) {
      input.symbol = windowItem.browserDefaults.symbol;
    }
    if (windowItem.browserDefaults.interval) {
      input.interval = windowItem.browserDefaults.interval;
    }
    if (windowItem.browserDefaults.limit) {
      input.limit = Number(windowItem.browserDefaults.limit) || windowItem.browserDefaults.limit;
    }
    if (windowItem.browserDefaults.startDate) {
      input.start_date = windowItem.browserDefaults.startDate;
    }
    if (windowItem.browserDefaults.endDate) {
      input.end_date = windowItem.browserDefaults.endDate;
    }
    try {
      const requestPayload = {
        plaza_url: state.preferences.connectionPlazaUrl,
        pulser_id: pulser?.agent_id || pane.pulserId,
        pulser_name: pulser?.name || pane.pulserName,
        pulser_address: pulser?.address || pane.pulserAddress,
        practice_id: pane.practiceId || pulser?.practice_id || "get_pulse_data",
        pulse_name: pulse?.pulse_name || pane.pulseName,
        pulse_address: pulse?.pulse_address || pane.pulseAddress,
        output_schema: pulse?.output_schema || pane.outputSchema || {},
        input,
      };
      const payload = await runPulserRequest(requestPayload);
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId).pane;
        target.status = "ready";
        target.error = "";
        target.result = payload.result ?? payload;
        target.lastRunAt = new Date().toLocaleTimeString("en-US", { hour12: false });
        if (!target.fieldPaths.length) {
          const options = getFieldOptions(target.result);
          target.fieldPaths = options[0]?.path ? [options[0].path] : [];
        }
      });
    } catch (error) {
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId).pane;
        target.status = "error";
        target.error = error.message || "Pulser execution failed.";
      });
    }
  }

  async function savePaneResultToDefaultLocation(windowId, paneId) {
    const located = findPaneLocation(state, windowId, paneId);
    if (!located || located.pane.result === null || located.pane.result === undefined) {
      return;
    }
    const fileName = defaultSavedFileName(located.pane.title || "saved-result");
    updateState((next) => {
      const target = findPaneLocation(next, windowId, paneId)?.pane;
      if (!target) {
        return;
      }
      target.saveStatus = "saving";
      target.saveError = "";
    });
    try {
      let savedLocation = "";
      if (normalizeFileSaveBackend(state.preferences.fileSaveBackend) === "system_pulser") {
        const prepared = await ensureStoragePulserReady(state);
        const pulser = configuredSystemPulser(prepared.appState.preferences, prepared.appState);
        const savePulse = fileStoragePulserSavePulse(pulser);
        if (!pulser || !savePulse) {
          throw new Error("Choose a SystemPulser in Settings before saving.");
        }
        const bucketName = String(prepared.appState.preferences.fileSaveBucketName || "").trim();
        if (!bucketName) {
          throw new Error("Set a default SystemPulser bucket name in Settings before saving.");
        }
        const objectKey = joinStorageObjectKey(prepared.appState.preferences.fileSaveObjectPrefix, fileName);
        await runPulserRequest({
          plaza_url: prepared.appState.globalPlazaStatus.plazaUrl || prepared.appState.preferences.connectionPlazaUrl,
          pulser_id: pulser.agent_id || "",
          pulser_name: pulser.name || "",
          pulser_address: pulser.address || "",
          practice_id: pulser.practice_id || "get_pulse_data",
          pulse_name: savePulse.pulse_name || "object_save",
          pulse_address: savePulse.pulse_address || "",
          output_schema: savePulse.output_schema || {},
          input: {
            bucket_name: bucketName,
            object_key: objectKey,
            data: cloneValue(located.pane.result),
            metadata: {
              pane_title: located.pane.title || "",
              saved_at: new Date().toISOString(),
            },
          },
        });
        savedLocation = `${bucketName}/${objectKey}`;
      } else {
        const saved = await saveLocalJsonFilePayload({
          directory: state.preferences.fileSaveLocalDirectory,
          file_name: fileName,
          title: located.pane.title || "saved-result",
          content: cloneValue(located.pane.result),
        });
        savedLocation = String(saved.path || saved.file_name || fileName);
      }
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId)?.pane;
        if (!target) {
          return;
        }
        target.saveStatus = "ready";
        target.saveError = "";
        target.lastSavedAt = new Date().toLocaleTimeString("en-US", { hour12: false });
        target.lastSavedLocation = savedLocation;
      });
    } catch (error) {
      updateState((next) => {
        const target = findPaneLocation(next, windowId, paneId)?.pane;
        if (!target) {
          return;
        }
        target.saveStatus = "error";
        target.saveError = error.message || "Unable to save the pane result.";
      });
    }
  }

  async function refreshWorkspace(workspaceId) {
    const targetWorkspace = findWorkspace(state, workspaceId);
    if (!targetWorkspace) {
      return;
    }
    const jobs = [];
    targetWorkspace.windows.forEach((windowItem) => {
      if (windowItem.type !== "browser") {
        return;
      }
      windowItem.panes
        .filter((pane) => (
          (isDataPaneType(pane.type) && (pane.pulserId || pane.pulseName))
          || isOperatorPaneType(pane.type)
        ))
        .forEach((pane) => {
          jobs.push(runBrowserPane(windowItem.id, pane.id));
        });
    });
    if (!jobs.length) {
      return;
    }
    await Promise.allSettled(jobs);
  }

  function createWorkspace() {
    updateState((next) => {
      const workspaceIndex = next.nextWorkspaceIndex;
      const summary = {
        id: `workspace-${workspaceIndex}`,
        name: `New Workspace ${String(workspaceIndex).padStart(2, "0")}`,
        kind: "Scratch Workspace",
        focus: "Cross-asset sandbox",
        status: "Draft",
        owner: "phemacast-user",
        description: "A fresh workspace for arranging browser and mind-map windows.",
        panes: ["Browser", "Pulse tape", "Ledger", "Notes"],
        highlights: ["Workspace created from the File menu.", "Use React popouts to spread work across screens."],
      };
      next.workspaces.unshift(createWorkspaceRuntime(summary, 0, next.preferences, next.dashboard));
      next.activeWorkspaceId = summary.id;
      next.nextWorkspaceIndex += 1;
      next.menuBarMenuId = "";
    });
  }

  function deleteWorkspace(workspaceId) {
    updateState((next) => {
      const workspaceIndex = next.workspaces.findIndex((entry) => entry.id === workspaceId);
      if (workspaceIndex < 0) {
        return;
      }
      const workspaceToDelete = next.workspaces[workspaceIndex];
      const workspaceWindowIds = new Set((workspaceToDelete.windows || []).map((entry) => entry.id));

      if (next.workspaces.length === 1) {
        const replacementIndex = next.nextWorkspaceIndex;
        const summary = {
          id: `workspace-${replacementIndex}`,
          name: `New Workspace ${String(replacementIndex).padStart(2, "0")}`,
          kind: "Scratch Workspace",
          focus: "Cross-asset sandbox",
          status: "Draft",
          owner: "phemacast-user",
          description: "A fresh workspace for arranging browser and mind-map windows.",
          panes: ["Browser", "Pulse tape", "Ledger", "Notes"],
          highlights: ["Workspace recreated after delete.", "Use React popouts to spread work across screens."],
        };
        next.workspaces = [createWorkspaceRuntime(summary, 0, next.preferences, next.dashboard)];
        next.activeWorkspaceId = summary.id;
        next.preferences.defaultWorkspaceId = summary.id;
        next.nextWorkspaceIndex += 1;
      } else {
        const remainingWorkspaces = next.workspaces.filter((entry) => entry.id !== workspaceId);
        const fallbackWorkspace = remainingWorkspaces[Math.min(workspaceIndex, remainingWorkspaces.length - 1)] || remainingWorkspaces[0] || null;
        next.workspaces = remainingWorkspaces;
        if (next.activeWorkspaceId === workspaceId) {
          next.activeWorkspaceId = fallbackWorkspace?.id || "";
        }
        if (next.preferences.defaultWorkspaceId === workspaceId) {
          next.preferences.defaultWorkspaceId = fallbackWorkspace?.id || next.activeWorkspaceId || null;
        }
      }

      if (workspaceWindowIds.has(next.paneConfig.windowId)) {
        clearPaneConfig(next);
      }
      if (workspaceWindowIds.has(next.snapshotDialog.windowId)) {
        next.snapshotDialog = { open: false, windowId: "", mode: "save", name: "", selectedSnapshotId: "", error: "" };
      }
      if (workspaceWindowIds.has(next.diagramRunDialog.windowId)) {
        next.diagramRunDialog = createDiagramRunDialogState();
      }
      if (next.printDialog.workspaceId === workspaceId) {
        next.printDialog = createPrintDialogState();
      }
      if (next.activeWorkspaceId === workspaceId) {
        next.workspaceDialog = { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" };
      }
      if (workspaceWindowIds.has(next.paneMenuWindowId)) {
        next.paneMenuWindowId = "";
      }
    });
  }

  function createBrowser(mode) {
    updateState((next) => {
      const workspace = findWorkspace(next, next.activeWorkspaceId);
      if (!workspace) {
        return;
      }
      const browserCount = workspace.windows.filter((entry) => entry.type === "browser").length;
      workspace.windows.push(createBrowserWindow(browserCount, next.preferences, next.dashboard, {
        mode,
        title: browserCount === 0 ? "Research Browser" : `Research Browser ${browserCount + 1}`,
      }));
      next.paneMenuWindowId = "";
      next.menuBarMenuId = "";
    });
  }

  function openStandaloneMapPhemarEditor() {
    const popup = openPendingMapPhemarWindow("MapPhemar");
    navigatePendingMapPhemarWindow(popup, mapPhemarEditorHref("", {
      workspaceId: state.activeWorkspaceId,
    }, {
      storageDirectory: state.preferences.fileSaveLocalDirectory,
      settingsScope: "personal_agent",
      storageSettingsMode: "inherited",
      preferenceStorageKey: currentPreferenceStorageKey(),
      plazaUrl: state.preferences.connectionPlazaUrl,
    }));
  }

  async function openMindMapWindowInMapPhemar(windowId) {
    const popup = openPendingMapPhemarWindow("MapPhemar");
    if (!popup) {
      window.alert("Allow popups to open this diagram in MapPhemar.");
      return;
    }
    const located = findWindowLocation(state, windowId);
    if (!located || located.windowItem.type !== "mind_map") {
      if (popup && !popup.closed) {
        popup.close();
      }
      return;
    }
    const source = resolveMindMapSource(state, windowId);
    const title = String(located.windowItem.title || "Diagram Phema").trim() || "Diagram Phema";
    const existingPhemaId = String(source?.mapState?.linkedPhemaId || "").trim();
    const returnContext = normalizeMapPhemarReturnContext({
      workspaceId: located.workspace?.id || state.activeWorkspaceId,
      windowId,
      browserWindowId: located.windowItem.linkedPaneContext?.browserWindowId || "",
      paneId: located.windowItem.linkedPaneContext?.paneId || "",
    });
    const storageOptions = {
      storageDirectory: state.preferences.fileSaveLocalDirectory,
      settingsScope: "personal_agent",
      storageSettingsMode: "inherited",
      preferenceStorageKey: currentPreferenceStorageKey(),
      plazaUrl: state.preferences.connectionPlazaUrl,
    };

    try {
      if (!source?.mapState) {
        navigatePendingMapPhemarWindow(popup, mapPhemarEditorHref(existingPhemaId, returnContext, storageOptions));
        return;
      }
      const payload = serializeMindMapToPhema(source.mapState, title, existingPhemaId);
      const launchDraftKey = createMapPhemarLaunchDraft(payload);
      navigatePendingMapPhemarWindow(popup, mapPhemarEditorHref("", returnContext, {
        ...storageOptions,
        launchDraftKey,
      }));
    } catch (error) {
      console.error("Unable to open the diagram in MapPhemar.", error);
      if (popup && !popup.closed) {
        popup.document.body.innerHTML = `
          <div class="map-phemar-launch-shell map-phemar-launch-shell--error">
            <strong>Unable to open MapPhemar.</strong>
            <span>${String(error?.message || "The diagram could not be saved to the owner route.")}</span>
          </div>
        `;
      }
    }
  }

  function createMindMap(mode, linkedPaneContext) {
    if (!IS_MAP_PHEMAR_MODE && !linkedPaneContext) {
      openStandaloneMapPhemarEditor();
      updateState((next) => {
        next.paneMenuWindowId = "";
        next.menuBarMenuId = "";
      });
      return;
    }
    updateState((next) => {
      const workspace = findWorkspace(next, next.activeWorkspaceId);
      if (!workspace) {
        return;
      }
      const count = workspace.windows.filter((entry) => entry.type === "mind_map").length;
      workspace.windows.push(createMindMapWindow(count, next.preferences, next.dashboard, {
        mode,
        title: linkedPaneContext ? "Linked Diagram" : count === 0 ? "Diagram" : `Diagram ${count + 1}`,
        subtitle: linkedPaneContext ? "Linked whiteboard editor" : "Whiteboard canvas",
        linkedPaneContext: linkedPaneContext || null,
      }));
      next.paneMenuWindowId = "";
      next.menuBarMenuId = "";
    });
  }

  function deleteWindow(windowId) {
    updateState((next) => {
      next.workspaces.forEach((workspace) => {
        workspace.windows = workspace.windows.filter((entry) => entry.id !== windowId);
      });
      if (next.paneConfig.windowId === windowId) {
        clearPaneConfig(next);
      }
      if (next.snapshotDialog.windowId === windowId) {
        next.snapshotDialog = { open: false, windowId: "", mode: "save", name: "", selectedSnapshotId: "", error: "" };
      }
      if (next.diagramRunDialog.windowId === windowId) {
        next.diagramRunDialog = createDiagramRunDialogState();
      }
      if (next.paneMenuWindowId === windowId) {
        next.paneMenuWindowId = "";
      }
    });
  }

  function toggleWindowMode(windowId, mode) {
    const canvasMetrics = workspaceCanvasMetrics();
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located) {
        return;
      }
      if (mode === "external" && located.windowItem.mode === "docked") {
        located.windowItem.lastDockedBounds = windowBoundsSnapshot(located.windowItem);
        if (located.windowItem.lastExternalBounds) {
          located.windowItem.x = Number(located.windowItem.lastExternalBounds.x || located.windowItem.x);
          located.windowItem.y = Number(located.windowItem.lastExternalBounds.y || located.windowItem.y);
          located.windowItem.width = Number(located.windowItem.lastExternalBounds.width || located.windowItem.width);
          located.windowItem.height = Number(located.windowItem.lastExternalBounds.height || located.windowItem.height);
        }
      }
      located.windowItem.mode = mode;
      if (mode === "docked") {
        const maximum = Math.max(0, ...located.workspace.windows.map((entry) => Number(entry.z || 0))) + 1;
        located.windowItem.z = maximum;
        const dockedBounds = normalizeDockedWindowBounds(located.windowItem, canvasMetrics);
        located.windowItem.x = dockedBounds.x;
        located.windowItem.y = dockedBounds.y;
        located.windowItem.width = dockedBounds.width;
        located.windowItem.height = dockedBounds.height;
        located.windowItem.lastDockedBounds = dockedBounds;
      }
      if (next.paneMenuWindowId === windowId) {
        next.paneMenuWindowId = "";
      }
    });
  }

  function addPane(windowId, type) {
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located || located.windowItem.type !== "browser") {
        return;
      }
      located.windowItem.panes.push(createBrowserPane(type, located.windowItem.panes.length, next.preferences, next.dashboard));
      located.windowItem.browserPageMode = "edit";
      next.paneMenuWindowId = "";
    });
  }

  async function openLinkedMindMapPaneEditor(browserWindowId, paneId) {
    return openLinkedMindMapPaneInMapPhemar(browserWindowId, paneId);
  }

  async function openLinkedMindMapPaneInMapPhemar(browserWindowId, paneId) {
    const popup = openPendingMapPhemarWindow("MapPhemar");
    if (!popup) {
      window.alert("Allow popups to open this diagram in MapPhemar.");
      return;
    }
    const paneLocation = findPaneLocation(state, browserWindowId, paneId);
    if (!paneLocation || paneLocation.pane.type !== "mind_map") {
      if (popup && !popup.closed) {
        popup.close();
      }
      return;
    }
    const title = String(paneLocation.pane.title || "Diagram Phema").trim() || "Diagram Phema";
    const mapState = paneLocation.pane.mindMapState || createDefaultMindMapState(state.preferences, state.dashboard);
    const existingPhemaId = String(mapState.linkedPhemaId || "").trim();
    const returnContext = normalizeMapPhemarReturnContext({
      workspaceId: paneLocation.workspace?.id || state.activeWorkspaceId,
      browserWindowId,
      paneId,
    });
    const storageOptions = {
      storageDirectory: state.preferences.fileSaveLocalDirectory,
      settingsScope: "personal_agent",
      storageSettingsMode: "inherited",
      preferenceStorageKey: currentPreferenceStorageKey(),
      plazaUrl: state.preferences.connectionPlazaUrl,
    };

    try {
      const payload = serializeMindMapToPhema(mapState, title, existingPhemaId);
      const launchDraftKey = createMapPhemarLaunchDraft(payload);
      navigatePendingMapPhemarWindow(popup, mapPhemarEditorHref("", returnContext, {
        ...storageOptions,
        launchDraftKey,
      }));
    } catch (error) {
      console.error("Unable to open the linked diagram in MapPhemar.", error);
      if (popup && !popup.closed) {
        popup.document.body.innerHTML = `
          <div class="map-phemar-launch-shell map-phemar-launch-shell--error">
            <strong>Unable to open MapPhemar.</strong>
            <span>${String(error?.message || "The linked diagram could not be saved to the owner route.")}</span>
          </div>
        `;
      }
    }
  }

  function deletePane(windowId, paneId) {
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located || located.windowItem.type !== "browser") {
        return;
      }
      located.windowItem.panes = located.windowItem.panes.filter((entry) => entry.id !== paneId);
      if (next.paneConfig.windowId === windowId && next.paneConfig.paneId === paneId) {
        clearPaneConfig(next);
      }
    });
  }

  function togglePaneMenu(windowId) {
    updateState((next) => {
      next.paneMenuWindowId = next.paneMenuWindowId === windowId ? "" : windowId;
    });
  }

  function toggleMenuBarMenu(menuId) {
    updateState((next) => {
      next.menuBarMenuId = next.menuBarMenuId === menuId ? "" : menuId;
    });
  }

  function setMenuBarButtonRef(menuId, node) {
    if (node) {
      menuBarButtonRefs.current[menuId] = node;
      return;
    }
    delete menuBarButtonRefs.current[menuId];
  }

  function menuBarDropdownStyle(menuId) {
    const button = menuBarButtonRefs.current[menuId];
    if (!button || typeof window === "undefined") {
      return undefined;
    }
    const rect = button.getBoundingClientRect();
    const minWidth = Math.max(Math.round(rect.width), 240);
    const viewportWidth = Math.max(window.innerWidth || 0, minWidth + 24);
    const left = Math.max(12, Math.min(rect.left, viewportWidth - minWidth - 12));
    return {
      top: `${rect.bottom + 8}px`,
      left: `${left}px`,
      minWidth: `${minWidth}px`,
    };
  }

  function renderMenuBarDropdown(menuId, ariaLabel, children) {
    if (state.menuBarMenuId !== menuId || typeof document === "undefined") {
      return null;
    }
    return ReactDOM.createPortal(
      (
        <div className="app-menu-dropdown" role="menu" aria-label={ariaLabel} style={menuBarDropdownStyle(menuId)}>
          {children}
        </div>
      ),
      document.body,
    );
  }

  function clearPaneConfig(next) {
    next.paneConfig = createClosedPaneConfigState();
    next.paneConfigSnapshot = null;
  }

  function closeMenuBarMenu() {
    updateState((next) => {
      next.menuBarMenuId = "";
    });
  }

  function openSettingsFromMenu(tab = "profile") {
    updateState((next) => {
      next.settingsOpen = true;
      next.settingsTab = tab;
      next.menuBarMenuId = "";
    });
  }

  function openWorkspaceDialogFromMenu(mode) {
    closeMenuBarMenu();
    void openWorkspaceDialog(mode);
  }

  function printWorkspaceFromMenu() {
    updateState((next) => {
      next.menuBarMenuId = "";
      next.printDialog = {
        open: true,
        workspaceId: next.activeWorkspaceId,
        printing: false,
      };
    });
  }

  function closePrintDialog() {
    updateState((next) => {
      next.printDialog = createPrintDialogState();
    });
  }

  function submitPrintDialog() {
    updateState((next) => {
      if (!next.printDialog.open) {
        return;
      }
      next.printDialog.printing = true;
    });
  }

  function openUserGuideFromMenu() {
    openPersonalAgentUserGuide();
    closeMenuBarMenu();
  }

  function toggleSidebarFromMenu() {
    updateState((next) => {
      next.preferences.sidebarCollapsed = !next.preferences.sidebarCollapsed;
      next.menuBarMenuId = "";
    });
  }

  function openPaneConfig(windowId, paneId, reason = "") {
    const target = findPaneLocation(state, windowId, paneId);
    const paneSnapshot = target ? cloneValue(target.pane) : null;
    const paneSnapshotFilterText = String(target?.pane?.pulseFilterText || "");
    setPaneFilterText(paneSnapshotFilterText);
    updateState((next) => {
      const targetPane = findPaneLocation(next, windowId, paneId);
      if (targetPane && isDataPaneType(targetPane.pane.type)) {
        primePaneParameterState(targetPane.windowItem, targetPane.pane, next.preferences, next.globalPlazaStatus);
      }
      if (next.paneConfig.open) {
        const current = findPaneLocation(next, next.paneConfig.windowId, next.paneConfig.paneId);
        if (current) {
          current.pane.pulseFilterText = paneFilterText;
        }
      }
      next.paneConfig = { open: true, windowId, paneId, reason };
      next.paneConfigSnapshot = paneSnapshot ? {
        windowId,
        paneId,
        pane: paneSnapshot,
        pulseFilterText: paneSnapshotFilterText,
      } : null;
    });
  }

  function savePaneConfig() {
    updateState((next) => {
      if (next.paneConfig.open) {
        const current = findPaneLocation(next, next.paneConfig.windowId, next.paneConfig.paneId);
        if (current) {
          current.pane.pulseFilterText = paneFilterText;
        }
      }
      clearPaneConfig(next);
    });
  }

  function cancelPaneConfig() {
    const snapshot = state.paneConfigSnapshot;
    setPaneFilterText(String(snapshot?.pulseFilterText || ""));
    updateState((next) => {
      const currentSnapshot = next.paneConfigSnapshot;
      if (currentSnapshot) {
        const located = findPaneLocation(next, currentSnapshot.windowId, currentSnapshot.paneId);
        if (located) {
          located.windowItem.panes[located.paneIndex] = cloneValue(currentSnapshot.pane);
        }
      }
      clearPaneConfig(next);
    });
  }

  async function openSnapshotDialog(windowId, mode, kind = "browser") {
    const snapshotKind = kind === "mind_map" ? "mind_map" : "browser";
    const snapshots = snapshotKind === "mind_map" ? getMindMapSnapshots() : getBrowserSnapshots(windowId);
    updateState((next) => {
      next.snapshotDialog = {
        open: true,
        windowId,
        kind: snapshotKind,
        mode,
        name: "",
        selectedSnapshotId: snapshots[0]?.id || "",
        error: mode === "load"
          ? snapshots.length
            ? ""
            : snapshotKind === "mind_map"
              ? "No saved diagrams yet."
              : "No saved layouts yet."
          : "",
      };
    });
    if (snapshotKind !== "browser") {
      return;
    }
    let preparedState = state;
    try {
      const prepared = await ensureStoragePulserReady(state);
      preparedState = prepared.appState;
    } catch (error) {
      if (mode === "load" && !snapshots.length) {
        updateState((next) => {
          if (!next.snapshotDialog.open || next.snapshotDialog.windowId !== windowId || next.snapshotDialog.kind !== snapshotKind || next.snapshotDialog.mode !== mode) {
            return;
          }
          next.snapshotDialog.error = error.message || "Unable to load saved layouts from the configured storage location.";
        });
      }
      return;
    }
    if (mode !== "load") {
      void refreshBrowserSnapshotLibraryFromConfiguredStorage(preparedState).catch(() => {});
      return;
    }
    try {
      const library = await refreshBrowserSnapshotLibraryFromConfiguredStorage(preparedState);
      const nextSnapshots = Array.isArray(library?.[windowId]?.snapshots) ? library[windowId].snapshots : [];
      updateState((next) => {
        if (!next.snapshotDialog.open || next.snapshotDialog.windowId !== windowId || next.snapshotDialog.kind !== snapshotKind || next.snapshotDialog.mode !== mode) {
          return;
        }
        next.snapshotDialog.selectedSnapshotId = nextSnapshots[0]?.id || "";
        next.snapshotDialog.error = nextSnapshots.length ? "" : "No saved layouts yet.";
      });
    } catch (error) {
      if (!snapshots.length) {
        updateState((next) => {
          if (!next.snapshotDialog.open || next.snapshotDialog.windowId !== windowId || next.snapshotDialog.kind !== snapshotKind || next.snapshotDialog.mode !== mode) {
            return;
          }
          next.snapshotDialog.error = error.message || "Unable to load saved layouts from the configured storage location.";
        });
      }
    }
  }

  async function submitSnapshotDialog() {
    const dialog = state.snapshotDialog;
    if (!dialog.open || !dialog.windowId) {
      return;
    }
    const snapshotKind = dialog.kind === "mind_map" ? "mind_map" : "browser";
    if (dialog.mode === "save") {
      if (snapshotKind === "mind_map") {
        const resolved = resolveMindMapSource(state, dialog.windowId);
        if (!resolved) {
          return;
        }
        const snapshot = {
          id: createId("snapshot"),
          name: dialog.name.trim() || `Diagram layout ${new Date().toLocaleString()}`,
          savedAt: new Date().toISOString(),
          zoom: resolved.windowLocation.windowItem.zoom || 1,
          mindMapState: cloneValue(resolved.mapState),
        };
        saveMindMapSnapshot(snapshot);
        closeSnapshotDialog();
        return;
      }
      const located = findWindowLocation(state, dialog.windowId);
      if (!located || located.windowItem.type !== "browser") {
        return;
      }
      const snapshot = {
        id: createId("snapshot"),
        name: dialog.name.trim() || `Browser layout ${new Date().toLocaleString()}`,
        savedAt: new Date().toISOString(),
        browserPageMode: located.windowItem.browserPageMode,
        browserDefaults: located.windowItem.browserDefaults,
        panes: located.windowItem.panes,
      };
      let preparedState = state;
      try {
        const prepared = await ensureStoragePulserReady(state);
        preparedState = prepared.appState;
      } catch (error) {
        updateState((next) => {
          next.snapshotDialog.error = error.message || "Unable to prepare the storage backend for layout save.";
        });
        return;
      }
      let existingLibrary = loadSnapshots();
      try {
        existingLibrary = await refreshBrowserSnapshotLibraryFromConfiguredStorage(preparedState);
      } catch (error) {
        existingLibrary = loadSnapshots();
      }
      try {
        await saveBrowserSnapshot(dialog.windowId, snapshot, preparedState, existingLibrary);
        closeSnapshotDialog();
      } catch (error) {
        updateState((next) => {
          next.snapshotDialog.error = error.message || "Unable to save the layout to the configured storage location.";
        });
      }
      return;
    }
    let browserSnapshots = getBrowserSnapshots(dialog.windowId);
    if (snapshotKind === "browser") {
      let preparedState = state;
      try {
        const prepared = await ensureStoragePulserReady(state);
        preparedState = prepared.appState;
      } catch (error) {
        if (!browserSnapshots.length) {
          updateState((next) => {
            next.snapshotDialog.error = error.message || "Unable to prepare the storage backend for layout load.";
          });
          return;
        }
      }
      try {
        const library = await refreshBrowserSnapshotLibraryFromConfiguredStorage(preparedState);
        browserSnapshots = Array.isArray(library?.[dialog.windowId]?.snapshots) ? library[dialog.windowId].snapshots : [];
      } catch (error) {
        if (!browserSnapshots.length) {
          updateState((next) => {
            next.snapshotDialog.error = error.message || "Unable to load saved layouts from the configured storage location.";
          });
          return;
        }
      }
    }
    const snapshot = (snapshotKind === "mind_map" ? getMindMapSnapshots() : browserSnapshots)
      .find((entry) => entry.id === dialog.selectedSnapshotId);
    if (!snapshot) {
      updateState((next) => {
        next.snapshotDialog.error = snapshotKind === "mind_map" ? "Choose a saved diagram to load." : "Choose a saved layout to load.";
      });
      return;
    }
    updateState((next) => {
      if (snapshotKind === "mind_map") {
        const resolved = resolveMindMapSource(next, dialog.windowId);
        if (!resolved) {
          return;
        }
        const restored = normalizeMindMapState(snapshot.mindMapState, next.preferences, next.dashboard);
        if (resolved.linkedPaneLocation) {
          resolved.linkedPaneLocation.pane.mindMapState = restored;
        } else {
          resolved.windowLocation.windowItem.mindMapState = restored;
        }
        resolved.windowLocation.windowItem.zoom = Number.isFinite(snapshot.zoom)
          ? snapshot.zoom
          : resolved.windowLocation.windowItem.zoom;
        next.snapshotDialog = { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" };
        return;
      }
      const located = findWindowLocation(next, dialog.windowId);
      if (!located || located.windowItem.type !== "browser") {
        return;
      }
      located.windowItem.browserPageMode = snapshot.browserPageMode || "view";
      located.windowItem.browserDefaults = snapshot.browserDefaults || located.windowItem.browserDefaults;
      located.windowItem.panes = Array.isArray(snapshot.panes)
        ? snapshot.panes.map((pane, index) => normalizePaneState(pane, index, next.preferences, next.dashboard))
        : [];
      next.snapshotDialog = { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" };
    });
  }

  function closeSnapshotDialog() {
    updateState((next) => {
      next.snapshotDialog = { open: false, windowId: "", kind: "browser", mode: "save", name: "", selectedSnapshotId: "", error: "" };
    });
  }

  async function openPhemaDialog(windowId, mode) {
    const resolved = resolveMindMapSource(state, windowId);
    const defaultName = String(resolved?.windowLocation?.windowItem?.title || "Diagram Phema").trim() || "Diagram Phema";
    setPhemaDialog({
      ...createPhemaDialogState(),
      open: true,
      windowId,
      mode,
      name: defaultName,
      loading: mode === "load",
    });
    if (mode !== "load") {
      return;
    }
    try {
      const prepared = await ensureStoragePulserReady(state);
      const phemas = await fetchMapPhemaLibrary("", prepared.appState);
      setPhemaDialog((current) => ({
        ...current,
        open: true,
        windowId,
        mode,
        name: current.name || defaultName,
        phemas,
        selectedPhemaId: phemas[0]?.phema_id || phemas[0]?.id || "",
        loading: false,
        error: mode === "load" && !phemas.length ? "No saved Phemas yet." : "",
      }));
    } catch (error) {
      setPhemaDialog((current) => ({
        ...current,
        open: true,
        windowId,
        mode,
        name: current.name || defaultName,
        loading: false,
        error: error.message || "Unable to load saved Phemas.",
      }));
    }
  }

  function closePhemaDialog() {
    setPhemaDialog(createPhemaDialogState());
  }

  async function refreshPhemaDialog(query = "") {
    setPhemaDialog((current) => ({ ...current, query, loading: true, error: "" }));
    try {
      const prepared = await ensureStoragePulserReady(state);
      const phemas = await fetchMapPhemaLibrary(query, prepared.appState);
      setPhemaDialog((current) => ({
        ...current,
        query,
        phemas,
        selectedPhemaId: phemas.some((entry) => String(entry.phema_id || entry.id || "") === current.selectedPhemaId)
          ? current.selectedPhemaId
          : phemas[0]?.phema_id || phemas[0]?.id || "",
        loading: false,
        error: current.mode === "load" && !phemas.length ? "No saved Phemas yet." : "",
      }));
    } catch (error) {
      setPhemaDialog((current) => ({
        ...current,
        query,
        loading: false,
        error: error.message || "Unable to load saved Phemas.",
      }));
    }
  }

  async function loadPhemaDialogSelection(windowId, phemaId) {
    const normalizedWindowId = String(windowId || "").trim();
    const normalizedPhemaId = String(phemaId || "").trim();
    if (!normalizedWindowId) {
      return;
    }
    if (!normalizedPhemaId) {
      setPhemaDialog((current) => ({ ...current, error: "Choose a saved Phema to load." }));
      return;
    }
    setPhemaDialog((current) => ({
      ...current,
      open: true,
      windowId: normalizedWindowId,
      selectedPhemaId: normalizedPhemaId,
      loading: true,
      error: "",
    }));
    try {
      const prepared = await ensureStoragePulserReady(state);
      const phema = await fetchMapPhema(normalizedPhemaId, prepared.appState);
      updateState((next) => {
        const source = resolveMindMapSource(next, normalizedWindowId);
        if (!source) {
          return;
        }
        const restored = deserializeMindMapFromPhema(phema, next.preferences, next.dashboard);
        if (source.linkedPaneLocation) {
          source.linkedPaneLocation.pane.mindMapState = restored;
          source.linkedPaneLocation.pane.title = String(phema.name || source.linkedPaneLocation.pane.title || "Diagram");
        } else {
          source.windowLocation.windowItem.mindMapState = restored;
        }
        source.windowLocation.windowItem.title = String(phema.name || source.windowLocation.windowItem.title || "Diagram");
        source.windowLocation.windowItem.subtitle = "Diagram-backed Phema";
      });
      closePhemaDialog();
    } catch (error) {
      setPhemaDialog((current) => ({
        ...current,
        open: true,
        windowId: normalizedWindowId,
        selectedPhemaId: normalizedPhemaId,
        loading: false,
        error: error.message || "Unable to load the selected Phema.",
      }));
    }
  }

  async function submitPhemaDialog() {
    const dialog = phemaDialog;
    if (!dialog.open || !dialog.windowId) {
      return;
    }
    if (dialog.mode === "save") {
      const resolved = resolveMindMapSource(state, dialog.windowId);
      if (!resolved) {
        setPhemaDialog((current) => ({ ...current, error: "Diagram source was not found." }));
        return;
      }
      setPhemaDialog((current) => ({ ...current, saving: true, error: "" }));
      try {
        const existingPhemaId = String(resolved.mapState?.linkedPhemaId || "");
        const payload = serializeMindMapToPhema(
          resolved.mapState,
          dialog.name.trim() || resolved.windowLocation.windowItem.title || "Diagram Phema",
          existingPhemaId,
        );
        const prepared = await ensureStoragePulserReady(state);
        const saved = await saveMapPhemaPayload(payload, prepared.appState);
        updateState((next) => {
          const source = resolveMindMapSource(next, dialog.windowId);
          if (!source) {
            return;
          }
          source.mapState.linkedPhemaId = String(saved.phema_id || saved.id || "");
          source.mapState.linkedPhemaName = String(saved.name || "");
          source.windowLocation.windowItem.title = String(saved.name || source.windowLocation.windowItem.title || "Diagram");
          source.windowLocation.windowItem.subtitle = "Diagram-backed Phema";
          if (source.linkedPaneLocation) {
            source.linkedPaneLocation.pane.title = String(saved.name || source.linkedPaneLocation.pane.title || "Diagram");
          }
        });
        closePhemaDialog();
      } catch (error) {
        setPhemaDialog((current) => ({
          ...current,
          saving: false,
          error: error.message || "Unable to save the diagram as a Phema.",
        }));
      }
      return;
    }
    if (!dialog.selectedPhemaId) {
      setPhemaDialog((current) => ({ ...current, error: "Choose a saved Phema to load." }));
      return;
    }
    await loadPhemaDialogSelection(dialog.windowId, dialog.selectedPhemaId);
  }

  async function openWorkspaceDialog(mode) {
    const layouts = getWorkspaceLayouts();
    updateState((next) => {
      const active = findWorkspace(next, next.activeWorkspaceId);
      next.workspaceDialog = {
        open: true,
        mode,
        name: active?.name || "",
        selectedLayoutId: layouts[0]?.id || "",
        error: mode === "load" && !layouts.length ? "No saved workspaces yet." : "",
      };
    });
    let preparedState = state;
    try {
      const prepared = await ensureStoragePulserReady(state);
      preparedState = prepared.appState;
    } catch (error) {
      if (mode === "load" && !layouts.length) {
        updateState((next) => {
          if (!next.workspaceDialog.open || next.workspaceDialog.mode !== mode) {
            return;
          }
          next.workspaceDialog.error = error.message || "Unable to load saved workspaces from the configured storage location.";
        });
      }
      return;
    }
    if (mode !== "load") {
      void refreshWorkspaceLayoutsFromConfiguredStorage(preparedState).catch(() => {});
      return;
    }
    try {
      const nextLayouts = await refreshWorkspaceLayoutsFromConfiguredStorage(preparedState);
      updateState((next) => {
        if (!next.workspaceDialog.open || next.workspaceDialog.mode !== mode) {
          return;
        }
        next.workspaceDialog.selectedLayoutId = nextLayouts[0]?.id || "";
        next.workspaceDialog.error = mode === "load" && !nextLayouts.length ? "No saved workspaces yet." : "";
      });
    } catch (error) {
      if (!layouts.length) {
        updateState((next) => {
          if (!next.workspaceDialog.open || next.workspaceDialog.mode !== mode) {
            return;
          }
          next.workspaceDialog.error = error.message || "Unable to load saved workspaces from the configured storage location.";
        });
      }
    }
  }

  function closeWorkspaceDialog() {
    updateState((next) => {
      next.workspaceDialog = { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" };
    });
  }

  async function submitWorkspaceDialog() {
    const dialog = state.workspaceDialog;
    if (!dialog.open) {
      return;
    }
    if (dialog.mode === "save") {
      const active = activeWorkspace();
      if (!active) {
        return;
      }
      let preparedState = state;
      try {
        const prepared = await ensureStoragePulserReady(state);
        preparedState = prepared.appState;
      } catch (error) {
        updateState((next) => {
          next.workspaceDialog.error = error.message || "Unable to prepare the storage backend for workspace save.";
        });
        return;
      }
      let existingLayouts = getWorkspaceLayouts();
      try {
        existingLayouts = await refreshWorkspaceLayoutsFromConfiguredStorage(preparedState);
      } catch (error) {
        existingLayouts = getWorkspaceLayouts();
      }
      const snapshot = {
        id: createId("workspace-layout"),
        name: dialog.name.trim() || active.name || `Workspace ${new Date().toLocaleString()}`,
        savedAt: new Date().toISOString(),
        workspace: cloneValue(active),
      };
      try {
        await saveWorkspaceLayout(snapshot, preparedState, existingLayouts);
        closeWorkspaceDialog();
      } catch (error) {
        updateState((next) => {
          next.workspaceDialog.error = error.message || "Unable to save the workspace to the configured storage location.";
        });
      }
      return;
    }
    let preparedState = state;
    let layouts = getWorkspaceLayouts();
    try {
      const prepared = await ensureStoragePulserReady(state);
      preparedState = prepared.appState;
    } catch (error) {
      if (!layouts.length) {
        updateState((next) => {
          next.workspaceDialog.error = error.message || "Unable to prepare the storage backend for workspace load.";
        });
        return;
      }
    }
    try {
      layouts = await refreshWorkspaceLayoutsFromConfiguredStorage(preparedState);
    } catch (error) {
      if (!layouts.length) {
        updateState((next) => {
          next.workspaceDialog.error = error.message || "Unable to load saved workspaces from the configured storage location.";
        });
        return;
      }
    }
    const snapshot = layouts.find((entry) => entry.id === dialog.selectedLayoutId);
    if (!snapshot) {
      updateState((next) => {
        next.workspaceDialog.error = "Choose a saved workspace to load.";
      });
      return;
    }
    updateState((next) => {
      const workspaceIndex = next.workspaces.findIndex((entry) => entry.id === next.activeWorkspaceId);
      if (workspaceIndex < 0) {
        return;
      }
      const currentWorkspaceId = next.workspaces[workspaceIndex].id;
      next.workspaces[workspaceIndex] = rebuildWorkspaceLayout(snapshot.workspace, currentWorkspaceId, next.preferences, next.dashboard);
      next.preferences.defaultWorkspaceId = currentWorkspaceId;
      clearPaneConfig(next);
      next.snapshotDialog = { open: false, windowId: "", mode: "save", name: "", selectedSnapshotId: "", error: "" };
      next.workspaceDialog = { open: false, mode: "save", name: "", selectedLayoutId: "", error: "" };
      next.paneMenuWindowId = "";
    });
  }

  function updatePaneField(windowId, paneId, field, value) {
    updateState((next) => {
      const located = findPaneLocation(next, windowId, paneId);
      if (!located) {
        return;
      }
      located.pane[field] = value;
      if (field === "pulseAddress" || field === "pulseName") {
        if (!value) {
          located.pane.pulseName = "";
          located.pane.pulseAddress = "";
        } else if (field === "pulseAddress") {
          located.pane.pulseName = "";
        } else if (field === "pulseName") {
          located.pane.pulseAddress = "";
        }
        syncPaneWithCatalog(located.windowItem, located.pane, next.preferences, next.globalPlazaStatus);
      }
    });
  }

  function updateOperatorPaneField(windowId, paneId, field, value) {
    updateState((next) => {
      const located = operatorPaneLocation(next, windowId, paneId);
      if (!located) {
        return;
      }
      located.pane.operatorState[field] = value;
    });
  }

  function updatePaneMindMapState(windowId, paneId, mutator) {
    updateState((next) => {
      const located = findPaneLocation(next, windowId, paneId);
      if (!located || located.pane.type !== "mind_map") {
        return;
      }
      if (!located.pane.mindMapState) {
        located.pane.mindMapState = createDefaultMindMapState(next.preferences, next.dashboard);
      }
      mutator(located.pane.mindMapState);
    });
  }

  function selectPanePulse(windowId, paneId, pulseKey) {
    updateState((next) => {
      const located = findPaneLocation(next, windowId, paneId);
      if (!located) {
        return;
      }
      const pulseOptions = collectCatalogPulses(resolveBrowserCatalog(located.windowItem, next.preferences, next.globalPlazaStatus));
      const selectedPulse = pulseOptions.find((entry) => entry.key === pulseKey) || null;
      located.pane.pulseName = selectedPulse?.pulse_name || "";
      located.pane.pulseAddress = "";
      syncPaneWithCatalog(located.windowItem, located.pane, next.preferences, next.globalPlazaStatus);
      primePaneParameterState(located.windowItem, located.pane, next.preferences, next.globalPlazaStatus, { force: true });
    });
  }

  function selectPanePulser(windowId, paneId, pulserKey) {
    updateState((next) => {
      const located = findPaneLocation(next, windowId, paneId);
      if (!located) {
        return;
      }
      const pulseOptions = collectCatalogPulses(resolveBrowserCatalog(located.windowItem, next.preferences, next.globalPlazaStatus));
      const selectedPulse = findSelectedCatalogPulse(pulseOptions, located.pane);
      if (!selectedPulse) {
        located.pane.pulserId = "";
        located.pane.pulserName = "";
        located.pane.pulserAddress = "";
        located.pane.practiceId = "get_pulse_data";
        return;
      }
      const selectedPulser = (selectedPulse.compatible_pulsers || []).find((entry) => entry.key === pulserKey)
        || (selectedPulse.compatible_pulsers || []).find((entry) => entry.pulser_id === pulserKey)
        || (selectedPulse.compatible_pulsers || []).find((entry) => entry.pulser_name === pulserKey)
        || null;
      if (!selectedPulser) {
        located.pane.pulserId = "";
        located.pane.pulserName = "";
        located.pane.pulserAddress = "";
        located.pane.practiceId = "get_pulse_data";
        return;
      }
      const pulse = selectedPulser.pulse || selectedPulse;
      located.pane.pulserId = selectedPulser.pulser_id || "";
      located.pane.pulserName = selectedPulser.pulser_name || "";
      located.pane.pulserAddress = selectedPulser.pulser_address || "";
      located.pane.practiceId = selectedPulser.practice_id || "get_pulse_data";
      located.pane.pulseName = pulse?.pulse_name || selectedPulse.pulse_name || "";
      located.pane.pulseAddress = pulse?.pulse_address || selectedPulse.pulse_address || "";
      located.pane.outputSchema = pulse?.output_schema || selectedPulse.output_schema || {};
      primePaneParameterState(located.windowItem, located.pane, next.preferences, next.globalPlazaStatus, { force: true });
    });
  }

  function togglePaneFieldPath(windowId, paneId, fieldPath) {
    updateState((next) => {
      const located = findPaneLocation(next, windowId, paneId);
      if (!located) {
        return;
      }
      const exists = located.pane.fieldPaths.includes(fieldPath);
      located.pane.fieldPaths = exists
        ? located.pane.fieldPaths.filter((entry) => entry !== fieldPath)
        : [...located.pane.fieldPaths, fieldPath];
    });
  }

  function updateMindMap(windowId, mutator) {
    updateState((next) => {
      const source = resolveMindMapSource(next, windowId);
      if (!source) {
        return;
      }
      mutator(source.mapState, source);
      syncBranchMindMapEdges(source.mapState);
      syncBranchMindMapSchemas(source.mapState);
      syncBoundaryMindMapSchemas(source.mapState);
      if (source.mapState.selectedEdgeId && !source.mapState.edges.some((edge) => edge.id === source.mapState.selectedEdgeId)) {
        source.mapState.selectedEdgeId = "";
      }
    });
  }

  function setMindMapZoom(windowId, nextZoom) {
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located) {
        return;
      }
      located.windowItem.zoom = clamp(nextZoom, 0.5, 2.2);
    });
  }

  function clearMindMapSelection(windowId) {
    updateMindMap(windowId, (map) => {
      map.selectedNodeId = "";
      map.selectedEdgeId = "";
      map.linkDraftFrom = "";
      map.linkDraftAnchor = "";
      map.linkDraftX = null;
      map.linkDraftY = null;
    });
    if (mindMapLinkRef.current?.windowId === windowId) {
      mindMapLinkRef.current = null;
    }
  }

  function createMindMapNodeDraft(map, x, y, shapeId = "rounded") {
    const preset = mindMapShapePreset(shapeId);
    map.nextNodeIndex += 1;
    return {
      id: createId("mind-node"),
      type: preset.id,
      title: `${preset.label} ${String(map.nextNodeIndex).padStart(2, "0")}`,
      subtitle: "",
      body: "",
      x: clamp(x ?? 12 + (map.nodes.length % 4) * 18, 0, 78),
      y: clamp(y ?? 12 + Math.floor(map.nodes.length / 4) * 18, 0, 80),
      w: preset.w,
      h: preset.h,
      pulserMode: "specific",
      pulserId: "",
      pulserName: "",
      pulserAddress: "",
      practiceId: "get_pulse_data",
      pulseName: "",
      pulseAddress: "",
      inputSchema: {},
      outputSchema: {},
      paramsText: "{}",
      conditionExpression: "",
      branchInputSide: defaultBranchConnectorSide("input"),
      branchYesSide: defaultBranchConnectorSide("yes"),
      branchNoSide: defaultBranchConnectorSide("no"),
      branchInputMode: defaultBranchConnectorMode("input"),
      branchYesMode: defaultBranchConnectorMode("yes"),
      branchNoMode: defaultBranchConnectorMode("no"),
    };
  }

  function applyCatalogPulseToMindMapNodeData(node, pulseOption) {
    if (isBoundaryMindMapNode(node) || isBranchMindMapNode(node)) {
      return;
    }
    if (!pulseOption) {
      return;
    }
    const compatiblePulser = preferredCompatiblePulser(pulseOption);
    const sourcePulse = compatiblePulser?.pulse || pulseOption;
    node.pulserMode = compatiblePulser ? "specific" : "dynamic";
    node.pulserId = compatiblePulser?.pulser_id || "";
    node.pulserName = compatiblePulser?.pulser_name || "";
    node.pulserAddress = compatiblePulser?.pulser_address || "";
    node.practiceId = compatiblePulser?.practice_id || "get_pulse_data";
    node.pulseName = sourcePulse?.pulse_name || pulseOption.pulse_name || "";
    node.pulseAddress = sourcePulse?.pulse_address || pulseOption.pulse_address || "";
    node.subtitle = node.pulseName && node.pulseName !== node.title ? node.pulseName : "";
    node.body = pulseDescription(sourcePulse) || pulseOption.description || "";
    node.inputSchema = sourcePulse?.input_schema || pulseOption.input_schema || {};
    node.outputSchema = sourcePulse?.output_schema || pulseOption.output_schema || {};
    node.paramsText = JSON.stringify(getSampleParameters(sourcePulse), null, 2) || "{}";
    if (!node.title || node.title.startsWith("Pulse ")) {
      node.title = node.pulseName || node.title;
    }
  }

  function selectMindMapNodePulser(windowId, nodeId, pulserKey) {
    updateMindMap(windowId, (map, source) => {
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node || isBoundaryMindMapNode(node) || isBranchMindMapNode(node)) {
        return;
      }
      const pulseOptions = collectCatalogPulses(source.catalog || emptyCatalog(source.mapState.plazaUrl));
      const selectedPulse = pulseOptions.find((entry) => pulseMatches(entry, node.pulseAddress, node.pulseName)) || null;
      const compatiblePulser = (selectedPulse?.compatible_pulsers || []).find((entry) => (
        entry.pulser_id === pulserKey
        || entry.pulser_name === pulserKey
        || entry.pulser_address === pulserKey
      )) || null;
      if (!compatiblePulser) {
        return;
      }
      const sourcePulse = compatiblePulser.pulse || selectedPulse;
      node.pulserMode = "specific";
      node.pulserId = compatiblePulser.pulser_id || "";
      node.pulserName = compatiblePulser.pulser_name || "";
      node.pulserAddress = compatiblePulser.pulser_address || "";
      node.practiceId = compatiblePulser.practice_id || "get_pulse_data";
      node.pulseName = sourcePulse?.pulse_name || selectedPulse?.pulse_name || node.pulseName;
      node.pulseAddress = sourcePulse?.pulse_address || selectedPulse?.pulse_address || node.pulseAddress;
      node.body = pulseDescription(sourcePulse) || selectedPulse?.description || node.body;
      node.inputSchema = sourcePulse?.input_schema || selectedPulse?.input_schema || {};
      node.outputSchema = sourcePulse?.output_schema || selectedPulse?.output_schema || {};
      node.paramsText = JSON.stringify(getSampleParameters(sourcePulse), null, 2) || "{}";
    });
  }

  function addMindMapNode(windowId, x, y, shapeId = "rounded") {
    updateMindMap(windowId, (map) => {
      const node = createMindMapNodeDraft(map, x, y, shapeId);
      map.nodes.push(node);
      map.selectedNodeId = node.id;
      map.selectedEdgeId = "";
      map.linkDraftFrom = "";
      map.linkDraftAnchor = "";
      map.linkDraftX = null;
      map.linkDraftY = null;
    });
  }

  function addMindMapCatalogNode(windowId, pulseKey, x, y) {
    updateMindMap(windowId, (map, source) => {
      const node = createMindMapNodeDraft(map, x, y);
      const pulseOption = collectCatalogPulses(source.catalog || emptyCatalog(source.mapState.plazaUrl))
        .find((entry) => entry.key === pulseKey);
      if (pulseOption) {
        applyCatalogPulseToMindMapNodeData(node, pulseOption);
      } else {
        syncMindMapNodeWithCatalog(source, node, { resetPulse: true });
      }
      map.nodes.push(node);
      map.selectedNodeId = node.id;
      map.selectedEdgeId = "";
      map.linkDraftFrom = "";
      map.linkDraftAnchor = "";
      map.linkDraftX = null;
      map.linkDraftY = null;
    });
  }

  function assignCatalogPulseToMindMapNode(windowId, nodeId, pulseKey) {
    updateMindMap(windowId, (map, source) => {
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node || isBoundaryMindMapNode(node) || isBranchMindMapNode(node)) {
        return;
      }
      const pulseOption = collectCatalogPulses(source.catalog || emptyCatalog(source.mapState.plazaUrl))
        .find((entry) => entry.key === pulseKey);
      applyCatalogPulseToMindMapNodeData(node, pulseOption);
    });
  }

  function updateMindMapBoundarySchema(windowId, nodeId, text) {
    updateMindMap(windowId, (map) => {
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node || !isBoundaryMindMapNode(node)) {
        return;
      }
      const config = boundarySchemaConfig(node.role);
      node[config.textKey] = text;
      const parsed = safeJsonParse(text, null);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        node[config.errorKey] = "Schema must be a JSON object.";
        return;
      }
      node[config.schemaKey] = parsed;
      node[config.errorKey] = "";
    });
  }

  function selectMindMapNode(windowId, nodeId) {
    updateMindMap(windowId, (map) => {
      map.selectedNodeId = nodeId;
      map.selectedEdgeId = "";
    });
  }

  function startMindMapLink(windowId, nodeId, anchor = "right", rect = null) {
    const resolved = resolveMindMapSource(state, windowId);
    const sourceNode = resolved?.mapState?.nodes.find((entry) => entry.id === nodeId) || null;
    if (normalizeBoundaryMindMapRole(sourceNode?.role) === "output") {
      return;
    }
    const draftPoint = sourceNode ? anchorPoint(sourceNode, anchor) : { x: 0, y: 0 };
    mindMapLinkRef.current = {
      windowId,
      nodeId,
      anchor,
      rect,
    };
    updateMindMap(windowId, (map) => {
      map.linkDraftFrom = nodeId;
      map.linkDraftAnchor = anchor;
      map.linkDraftX = draftPoint.x;
      map.linkDraftY = draftPoint.y;
      map.selectedNodeId = nodeId;
      map.selectedEdgeId = "";
    });
  }

  function cancelMindMapLink(windowId) {
    mindMapLinkRef.current = null;
    updateMindMap(windowId, (map) => {
      map.linkDraftFrom = "";
      map.linkDraftAnchor = "";
      map.linkDraftX = null;
      map.linkDraftY = null;
    });
  }

  function completeMindMapLink(windowId, targetNodeId) {
    const draft = mindMapLinkRef.current;
    if (!draft || draft.windowId !== windowId) {
      selectMindMapNode(windowId, targetNodeId);
      return;
    }
    updateMindMap(windowId, (map) => {
      const fromNode = map.nodes.find((entry) => entry.id === draft.nodeId);
      const toNode = map.nodes.find((entry) => entry.id === targetNodeId);
      const branchRoute = fromNode && isBranchMindMapNode(fromNode)
        ? normalizeBranchMindMapRoute(draft.anchor)
        : "";
      map.linkDraftFrom = "";
      map.linkDraftAnchor = "";
      map.linkDraftX = null;
      map.linkDraftY = null;
      if (!fromNode || !toNode || fromNode.id === toNode.id) {
        map.selectedNodeId = targetNodeId;
        map.selectedEdgeId = "";
        return;
      }
      if (normalizeBoundaryMindMapRole(fromNode.role) === "output" || normalizeBoundaryMindMapRole(toNode.role) === "input") {
        map.selectedNodeId = targetNodeId;
        map.selectedEdgeId = "";
        return;
      }
      if (isBranchMindMapNode(fromNode) && !branchRoute) {
        map.selectedNodeId = targetNodeId;
        map.selectedEdgeId = "";
        return;
      }
      const existing = map.edges.find((edge) => (
        edge.from === draft.nodeId
        && edge.to === targetNodeId
        && (!branchRoute || normalizeBranchMindMapRoute(edge.route || edge.fromAnchor) === branchRoute)
      ));
      if (existing) {
        map.selectedNodeId = "";
        map.selectedEdgeId = existing.id;
        return;
      }
      map.nextEdgeIndex += 1;
      const edge = {
        id: createId("mind-edge"),
        from: draft.nodeId,
        to: targetNodeId,
        label: branchRoute ? branchMindMapRouteLabel(branchRoute) : "",
        fromAnchor: branchRoute ? branchMindMapRouteAnchor(branchRoute) : (draft.anchor || automaticAnchor(fromNode, toNode)),
        toAnchor: isBranchMindMapNode(toNode) ? "branch-in" : automaticAnchor(toNode, fromNode),
        mappingText: "{}",
        route: branchRoute,
      };
      map.edges.push(edge);
      map.selectedNodeId = "";
      map.selectedEdgeId = edge.id;
    });
    mindMapLinkRef.current = null;
  }

  function deleteMindMapNode(windowId, nodeId) {
    updateMindMap(windowId, (map) => {
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node || isBoundaryMindMapNode(node)) {
        return;
      }
      map.nodes = map.nodes.filter((entry) => entry.id !== nodeId);
      map.edges = map.edges.filter((entry) => entry.from !== nodeId && entry.to !== nodeId);
      if (map.selectedNodeId === nodeId) {
        map.selectedNodeId = "";
      }
      if (map.linkDraftFrom === nodeId) {
        map.linkDraftFrom = "";
        map.linkDraftAnchor = "";
        map.linkDraftX = null;
        map.linkDraftY = null;
      }
    });
    if (mindMapLinkRef.current?.nodeId === nodeId) {
      mindMapLinkRef.current = null;
    }
  }

  function deleteMindMapEdge(windowId, edgeId) {
    updateMindMap(windowId, (map) => {
      map.edges = map.edges.filter((entry) => entry.id !== edgeId);
      if (map.selectedEdgeId === edgeId) {
        map.selectedEdgeId = "";
      }
    });
  }

  function updateMindMapEdge(windowId, edgeId, field, value) {
    updateMindMap(windowId, (map) => {
      const edge = map.edges.find((entry) => entry.id === edgeId);
      if (!edge) {
        return;
      }
      edge[field] = value;
    });
  }

  function updateMindMapEdgeMapping(windowId, edgeId, transform) {
    updateMindMap(windowId, (map) => {
      const edge = map.edges.find((entry) => entry.id === edgeId);
      if (!edge) {
        return;
      }
      const { mapping } = parseEdgeMapping(edge);
      const nextMapping = transform({ ...mapping });
      edge.mappingText = stringifyEdgeMapping(nextMapping && typeof nextMapping === "object" ? nextMapping : {});
    });
  }

  function setMindMapEdgeMappingField(windowId, edgeId, targetField, sourceField) {
    if (!targetField) {
      return;
    }
    updateMindMapEdgeMapping(windowId, edgeId, (mapping) => {
      if (!sourceField) {
        const current = mapping[targetField];
        if (current && typeof current === "object" && !Array.isArray(current)) {
          const nextEntry = { ...current };
          delete nextEntry.from;
          if (Object.keys(nextEntry).length) {
            mapping[targetField] = nextEntry;
          } else {
            delete mapping[targetField];
          }
        } else {
          delete mapping[targetField];
        }
        return mapping;
      }
      const current = mapping[targetField];
      if (current && typeof current === "object" && !Array.isArray(current)) {
        mapping[targetField] = { ...current, from: sourceField };
      } else {
        mapping[targetField] = sourceField;
      }
      return mapping;
    });
  }

  function setMindMapEdgeMappingConstant(windowId, edgeId, targetField, constantValue) {
    if (!targetField) {
      return;
    }
    updateMindMapEdgeMapping(windowId, edgeId, (mapping) => {
      const current = mapping[targetField];
      const nextConstant = String(constantValue ?? "");
      if (!nextConstant.trim()) {
        if (current && typeof current === "object" && !Array.isArray(current)) {
          const nextEntry = { ...current };
          delete nextEntry.const;
          if (Object.keys(nextEntry).length) {
            mapping[targetField] = nextEntry;
          } else {
            delete mapping[targetField];
          }
        }
        return mapping;
      }
      if (current && typeof current === "object" && !Array.isArray(current)) {
        mapping[targetField] = { ...current, const: nextConstant };
      } else if (typeof current === "string" && current.trim()) {
        mapping[targetField] = { from: current, const: nextConstant };
      } else {
        mapping[targetField] = { const: nextConstant };
      }
      return mapping;
    });
  }

  function clearMindMapEdgeMappingField(windowId, edgeId, targetField) {
    if (!targetField) {
      return;
    }
    updateMindMapEdgeMapping(windowId, edgeId, (mapping) => {
      delete mapping[targetField];
      return mapping;
    });
  }

  function toggleMindMapSourcePath(windowId, sourcePath) {
    if (!sourcePath) {
      return;
    }
    updateMindMap(windowId, (map) => {
      const current = new Set(Array.isArray(map.expandedSourcePaths) ? map.expandedSourcePaths : []);
      if (current.has(sourcePath)) {
        current.delete(sourcePath);
      } else {
        current.add(sourcePath);
      }
      map.expandedSourcePaths = Array.from(current);
    });
  }

  function setMindMapInspectorWidth(windowId, width) {
    updateMindMap(windowId, (map) => {
      map.inspectorWidth = clamp(Number(width || 320), 280, 560);
    });
  }

  function toggleMindMapGrid(windowId) {
    updateMindMap(windowId, (map) => {
      map.showGrid = map.showGrid === false;
    });
  }

  function updateMindMapNode(windowId, nodeId, field, value) {
    updateMindMap(windowId, (map, source) => {
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node) {
        return;
      }
      const wasBranch = isBranchMindMapNode(node);
      if (isBoundaryMindMapNode(node)) {
        if (field === "title" || field === "type" || field === "pulserMode" || field === "pulserId" || field === "pulserName" || field === "pulseName" || field === "pulseAddress") {
          return;
        }
      }
      if (isBranchMindMapNode(node) && (field === "pulserMode" || field === "pulserId" || field === "pulserName" || field === "pulseName" || field === "pulseAddress")) {
        return;
      }
      node[field] = value;
      if (field === "type") {
        const preset = mindMapShapePreset(value);
        node.type = preset.id;
        node.w = preset.w;
        node.h = preset.h;
        if (!node.title || MINDMAP_SHAPE_PRESETS.some((entry) => node.title.startsWith(entry.label))) {
          node.title = preset.label;
        }
        if (preset.id === "branch") {
          node.subtitle = "";
          node.body = "";
          node.pulserMode = "specific";
          node.pulserId = "";
          node.pulserName = "";
          node.pulserAddress = "";
          node.practiceId = "get_pulse_data";
          node.pulseName = "";
          node.pulseAddress = "";
          node.paramsText = "{}";
          node.inputSchema = {};
          node.outputSchema = {};
          node.conditionExpression = String(node.conditionExpression || "").trim();
          node.branchInputSide = normalizeBranchConnectorSide(node.branchInputSide, defaultBranchConnectorSide("input"));
          node.branchYesSide = normalizeBranchConnectorSide(node.branchYesSide, defaultBranchConnectorSide("yes"));
          node.branchNoSide = normalizeBranchConnectorSide(node.branchNoSide, defaultBranchConnectorSide("no"));
          node.branchInputMode = normalizeBranchConnectorMode(node.branchInputMode, defaultBranchConnectorMode("input"));
          node.branchYesMode = normalizeBranchConnectorMode(node.branchYesMode, defaultBranchConnectorMode("yes"));
          node.branchNoMode = normalizeBranchConnectorMode(node.branchNoMode, defaultBranchConnectorMode("no"));
        } else if (wasBranch) {
          node.conditionExpression = "";
        }
      }
      if (field === "pulserMode") {
        syncMindMapNodeWithCatalog(source, node, { resetPulse: true });
      }
      if (field === "pulserId" || field === "pulserName") {
        node.pulseName = "";
        node.pulseAddress = "";
        syncMindMapNodeWithCatalog(source, node, { resetPulse: true });
      }
      if (field === "pulseName" || field === "pulseAddress") {
        syncMindMapNodeWithCatalog(source, node, { resetPulse: false });
      }
    });
  }

  function handlePopupClosed(windowId, reason, bounds) {
    const canvasMetrics = workspaceCanvasMetrics();
    updateState((next) => {
      const located = findWindowLocation(next, windowId);
      if (!located) {
        return;
      }
      if (bounds) {
        located.windowItem.lastExternalBounds = {
          x: Number(bounds.x || located.windowItem.x),
          y: Number(bounds.y || located.windowItem.y),
          width: Number(bounds.width || located.windowItem.width),
          height: Number(bounds.height || located.windowItem.height),
        };
      }
      if (reason === "closed" && located.windowItem.type === "mind_map") {
        located.workspace.windows = located.workspace.windows.filter((entry) => entry.id !== windowId);
        if (next.paneConfig.windowId === windowId) {
          clearPaneConfig(next);
        }
        if (next.snapshotDialog.windowId === windowId) {
          next.snapshotDialog = { open: false, windowId: "", mode: "save", name: "", selectedSnapshotId: "", error: "" };
        }
        if (next.diagramRunDialog.windowId === windowId) {
          next.diagramRunDialog = createDiagramRunDialogState();
        }
        if (next.paneMenuWindowId === windowId) {
          next.paneMenuWindowId = "";
        }
        return;
      }
      if (reason === "blocked" || reason === "closed") {
        located.windowItem.mode = "docked";
        const maximum = Math.max(0, ...located.workspace.windows.map((entry) => Number(entry.z || 0))) + 1;
        located.windowItem.z = maximum;
        const dockedBounds = normalizeDockedWindowBounds(
          located.windowItem,
          canvasMetrics,
          located.windowItem.lastDockedBounds || bounds || null,
        );
        located.windowItem.x = dockedBounds.x;
        located.windowItem.y = dockedBounds.y;
        located.windowItem.width = dockedBounds.width;
        located.windowItem.height = dockedBounds.height;
        located.windowItem.lastDockedBounds = dockedBounds;
      }
    });
  }

  function addLlmConfig(type) {
    updateState((next) => {
      const config = {
        ...createDefaultLlmConfig(next.preferences.llmConfigs.length, next.preferences.connectionPlazaUrl),
        type,
        name: type === "llm_pulse" ? `LLM Pulse ${next.preferences.llmConfigs.length + 1}` : `API Route ${next.preferences.llmConfigs.length + 1}`,
      };
      next.preferences.llmConfigs.push(config);
      if (!next.preferences.llmDefaultConfigId) {
        next.preferences.llmDefaultConfigId = config.id;
      }
      next.settingsLlmSelectedId = config.id;
    });
  }

  const workspace = activeWorkspace();
  const workspaceLayouts = getWorkspaceLayouts();
  const workspaceDockedWindows = (workspace?.windows || [])
    .filter((entry) => entry.mode === "docked")
    .sort((left, right) => (left.z || 0) - (right.z || 0));
  const workspaceWorld = workspaceWorldMetrics(workspace);
  const workspaceIsRefreshing = Boolean(
    (workspace?.windows || []).some((windowItem) => windowItem.type === "browser" && windowItem.panes.some((pane) => (
      pane.status === "loading" || String(pane?.operatorState?.status || "") === "loading"
    ))),
  );
  const workspacePlazaStatusClass = state.globalPlazaStatus.connected
    ? "status-pill ready"
    : state.globalPlazaStatus.status === "loading"
      ? "status-pill loading"
      : "status-pill offline";
  const workspacePlazaStatusLabel = state.globalPlazaStatus.status === "loading"
    ? "Plaza Refreshing"
    : state.globalPlazaStatus.connected
      ? "Plaza Ready"
      : "Plaza Offline";
  const workspacePlazaStatusDetail = state.globalPlazaStatus.error
    || `${state.globalPlazaStatus.pulserCount || 0} pulsers · ${state.globalPlazaStatus.pulseCount || 0} pulses`;
  const menuBarPlazaStatusLabel = state.globalPlazaStatus.status === "loading"
    ? "Checking"
    : state.globalPlazaStatus.connected
      ? "Online"
      : "Mock Mode";
  const printWorkspace = state.printDialog.open
    ? findWorkspace(state, state.printDialog.workspaceId) || workspace
    : workspace;

  function printableWindowList(targetWorkspace) {
    return (targetWorkspace?.windows || []).slice().sort((left, right) => (
      (left.y || 0) - (right.y || 0)
      || (left.x || 0) - (right.x || 0)
      || (left.z || 0) - (right.z || 0)
    ));
  }

  function printablePaneList(windowItem) {
    return (windowItem?.panes || [])
      .filter((pane) => BROWSER_PANE_TYPES.some((entry) => entry.id === pane.type))
      .slice()
      .sort((left, right) => (
        (left.y || 0) - (right.y || 0)
        || (left.x || 0) - (right.x || 0)
        || (left.z || 0) - (right.z || 0)
      ));
  }

  function renderPrintMindMapCanvas(map, variant = "pane") {
    const previewClassName = variant === "window"
      ? "pane-diagram-preview print-diagram-preview print-diagram-preview--window"
      : "pane-diagram-preview print-diagram-preview";
    const canvasClassName = map?.showGrid === false
      ? "pane-diagram-canvas pane-diagram-canvas--grid-hidden"
      : "pane-diagram-canvas";
    return (
      <div className={previewClassName}>
        <div className={canvasClassName}>
          {map?.edges?.length ? (
            <svg className="pane-diagram-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {map.edges.map((edge) => {
                const fromNode = map.nodes.find((entry) => entry.id === edge.from);
                const toNode = map.nodes.find((entry) => entry.id === edge.to);
                if (!fromNode || !toNode) {
                  return null;
                }
                return <path key={edge.id} className="pane-diagram-link" d={connectionPath(fromNode, toNode, edge)} />;
              })}
            </svg>
          ) : null}
          {map?.nodes?.length ? map.nodes.slice(0, 20).map((node) => (
            <div
              key={node.id}
              className={`pane-diagram-node pane-diagram-node--${node.type}`}
              style={{
                left: `${clamp(Number(node.x || 0), 0, 84)}%`,
                top: `${clamp(Number(node.y || 0), 0, 86)}%`,
                width: `${clamp(Number(node.w || 18), 12, 32)}%`,
                height: `${clamp(Number(node.h || 12), 8, 24)}%`,
              }}
            >
              <span>{node.title || "Shape"}</span>
            </div>
          )) : (
            <div className="pane-diagram-empty">
              <strong>Diagram pane</strong>
              <span>Open the editor to start mapping ideas.</span>
            </div>
          )}
        </div>
        <div className="pane-diagram-meta">
          <span>{map?.nodes?.length || 0} shapes</span>
          <span>{map?.edges?.length || 0} links</span>
        </div>
      </div>
    );
  }

  function renderPrintOperatorPane(windowItem, pane) {
    const operator = pane.operatorState || createOperatorConsoleState(state.preferences);
    const counts = operatorSummaryCounts(operator);
    const tickets = operator.tickets.slice(0, 6);
    return (
      <div className="print-operator-panel">
        <div className="print-operator-summary">
          <span className="print-operator-chip"><strong>{counts.total}</strong><small>Works</small></span>
          <span className="print-operator-chip"><strong>{counts.assigned}</strong><small>Assigned</small></span>
          <span className="print-operator-chip"><strong>{counts.attention}</strong><small>Attention</small></span>
          <span className="print-operator-chip"><strong>{counts.destinations}</strong><small>Ready</small></span>
        </div>
        {operator.error ? <div className="form-error">{operator.error}</div> : null}
        {tickets.length ? (
          <div className="print-operator-list">
            {tickets.map((ticket) => {
              const ticketId = operatorTicketId(ticket);
              const executionStatus = String(ticket?.execution_state?.status || ticket?.result_summary?.status || "queued").trim().toLowerCase();
              const title = String(ticket?.ticket?.title || ticket?.work_item?.title || ticket?.work_item?.required_capability || ticketId || "Managed work").trim();
              const workerName = String(ticket?.worker_assignment?.worker_name || ticket?.worker_assignment?.worker_id || "Unassigned").trim();
              return (
                <article key={ticketId || title} className="print-operator-item">
                  <div className="print-pane-head">
                    <strong>{title}</strong>
                    <span className={statusPillClass(executionStatus)}>{labelizeStatus(executionStatus)}</span>
                  </div>
                  <div className="print-pane-meta">
                    <span>{compactText(ticket?.work_item?.required_capability || "Capability not recorded", 88)}</span>
                    <span>{`Worker: ${workerName}`}</span>
                    <span>{`Updated: ${formatTimestamp(ticket?.ticket?.updated_at || ticket?.execution_state?.updated_at || ticket?.execution_state?.completed_at)}`}</span>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="pane-empty small">
            {operator.bossUrl ? "No managed work yet." : "Boss URL not configured."}
          </div>
        )}
      </div>
    );
  }

  function renderPrintBrowserPane(windowItem, pane) {
    const browserCatalog = resolveBrowserCatalog(windowItem, state.preferences, state.globalPlazaStatus);
    const pulser = (browserCatalog?.pulsers || []).find((entry) => (
      (pane.pulserId && entry.agent_id === pane.pulserId)
      || (pane.pulserAddress && entry.agent_address === pane.pulserAddress)
      || (pane.pulserName && (entry.pulser_name === pane.pulserName || entry.name === pane.pulserName || entry.agent_name === pane.pulserName))
    )) || null;
    const pulserLabel = String(
      pulser?.pulser_name
      || pulser?.name
      || pulser?.agent_name
      || pane.pulserName
      || pane.pulserId
      || pane.pulserAddress
      || "",
    ).trim();
    const isMindMapPane = pane.type === "mind_map";
    const isOperatorPane = isOperatorPaneType(pane.type);
    const value = !isOperatorPane && pane.result !== null ? getDisplayValue(pane) : null;
    const paneMap = isMindMapPane ? normalizeMindMapState(pane.mindMapState, state.preferences, state.dashboard) : null;
    const effectivePaneStatus = isOperatorPane ? String(pane.operatorState?.status || "idle") : pane.status;
    const paneMeta = [
      pane.pulseName || pane.pulseAddress ? `Pulse: ${pane.pulseName || pane.pulseAddress}` : "",
      pulserLabel ? `Pulser: ${pulserLabel}` : "",
      pane.displayFormat ? `Format: ${pane.displayFormat === "chart" ? `${pane.displayFormat} · ${pane.chartType}` : pane.displayFormat}` : "",
    ].filter(Boolean);

    let bodyContent = null;
    if (pane.error) {
      bodyContent = <div className="pane-empty error">{pane.error}</div>;
    } else if (isOperatorPane) {
      bodyContent = renderPrintOperatorPane(windowItem, pane);
    } else if (isMindMapPane) {
      bodyContent = renderPrintMindMapCanvas(paneMap);
    } else if (value === null) {
      bodyContent = (
        <div className="pane-empty small">
          {pane.pulseName || pane.pulseAddress ? "Ready to print after running this pane." : "Select a pulse to populate this pane."}
        </div>
      );
    } else {
      bodyContent = <ValueRenderer key={`print:${pane.id}:${pane.displayFormat}:${pane.chartType}`} value={value} format={pane.displayFormat} chartType={pane.chartType} />;
    }

    return (
      <article key={pane.id} className={`print-pane-card print-pane-card--${effectivePaneStatus}${isOperatorPane ? " print-pane-card--managed-work" : ""}`}>
        <div className="print-pane-head">
          <strong>{pane.title}</strong>
          <span className={statusPillClass(effectivePaneStatus)}>{labelizeStatus(effectivePaneStatus)}</span>
        </div>
        {paneMeta.length ? (
          <div className="print-pane-meta">
            {paneMeta.map((entry) => <span key={entry}>{entry}</span>)}
          </div>
        ) : null}
        {pane.plazaDescription || pane.description ? (
          <p className="print-pane-copy">{compactText(pane.plazaDescription || pane.description, 220)}</p>
        ) : null}
        <div className="print-pane-body">
          {bodyContent}
        </div>
      </article>
    );
  }

  function renderPrintBrowserWindow(windowItem) {
    const visiblePanes = printablePaneList(windowItem);
    const symbol = String(windowItem.browserDefaults?.symbol || "").trim();
    return (
      <section className="print-window" key={windowItem.id}>
        <div className="print-window-head">
          <div>
            <p className="eyebrow">Workspace Browser</p>
            <h4>{windowItem.title || "Research Browser"}</h4>
          </div>
          <div className="print-window-meta">
            {symbol ? <span>{`Symbol: ${symbol}`}</span> : null}
            <span>{`${visiblePanes.length} pane${visiblePanes.length === 1 ? "" : "s"}`}</span>
          </div>
        </div>
        {visiblePanes.length ? (
          <div className="print-pane-grid">
            {visiblePanes.map((pane) => renderPrintBrowserPane(windowItem, pane))}
          </div>
        ) : (
          <div className="pane-empty wide workspace-empty">No panes in this browser window.</div>
        )}
      </section>
    );
  }

  function renderPrintMindMapWindow(windowItem) {
    const resolved = resolveMindMapSource(state, windowItem.id);
    const map = resolved?.mapState;
    return (
      <section className="print-window" key={windowItem.id}>
        <div className="print-window-head">
          <div>
            <p className="eyebrow">Workspace Diagram</p>
            <h4>{windowItem.title || "Diagram"}</h4>
          </div>
          <div className="print-window-meta">
            <span>{`${map?.nodes?.length || 0} shapes`}</span>
            <span>{`${map?.edges?.length || 0} links`}</span>
          </div>
        </div>
        {map ? renderPrintMindMapCanvas(map, "window") : <div className="pane-empty small">Diagram source unavailable.</div>}
      </section>
    );
  }

  function renderPrintableWorkspace(targetWorkspace) {
    const workspaceWindows = printableWindowList(targetWorkspace);
    const totalPaneCount = workspaceWindows.reduce((count, windowItem) => (
      count + (windowItem.type === "browser" ? printablePaneList(windowItem).length : 1)
    ), 0);
    return (
      <div className="print-preview-sheet">
        <header className="print-preview-head">
          <div>
            <p className="eyebrow">Workspace Print Preview</p>
            <h3>{targetWorkspace?.name || "Workspace"}</h3>
            <p className="print-preview-copy">
              Clean preview of the current workspace content with the floating shell, resize grips, and action buttons removed for paper output.
            </p>
          </div>
          <div className="print-preview-meta">
            <span>{`${workspaceWindows.length} window${workspaceWindows.length === 1 ? "" : "s"}`}</span>
            <span>{`${totalPaneCount} pane${totalPaneCount === 1 ? "" : "s"}`}</span>
            <span>{state.preferences.profileDisplayName || "Personal Agent"}</span>
            <span>{new Date().toLocaleString()}</span>
          </div>
        </header>
        <div className="print-preview-stack">
          {workspaceWindows.length ? workspaceWindows.map((windowItem) => (
            windowItem.type === "browser"
              ? renderPrintBrowserWindow(windowItem)
              : renderPrintMindMapWindow(windowItem)
          )) : (
            <div className="pane-empty wide workspace-empty">No windows in this workspace yet.</div>
          )}
        </div>
      </div>
    );
  }

  function renderBrowserPane(windowItem, pane) {
    const editing = windowItem.browserPageMode === "edit";
    const paneStyle = {
      left: `${pane.x || 0}px`,
      top: `${pane.y || 0}px`,
      width: `${pane.width || 320}px`,
      height: `${pane.height || 220}px`,
      zIndex: pane.z || 1,
    };
    const value = pane.result !== null ? getDisplayValue(pane) : null;
    const isMindMapPane = pane.type === "mind_map";
    const isOperatorPane = isOperatorPaneType(pane.type);
    const effectivePaneStatus = isOperatorPane ? String(pane.operatorState?.status || "idle") : pane.status;
    const paneMap = isMindMapPane ? normalizeMindMapState(pane.mindMapState, state.preferences, state.dashboard) : null;
    const diagramDisplayMode = pane.diagramDisplayMode === "info" ? "info" : "diagram";
    const showDiagramPreview = isMindMapPane && diagramDisplayMode !== "info";
    const paneEditorLabel = IS_MAP_PHEMAR_MODE ? "MapPhemar" : "Editor";
    const paneEditorTitle = IS_MAP_PHEMAR_MODE ? "Open diagram in MapPhemar" : "Open linked diagram in the MapPhemar editor";
    const canSaveResult = !isOperatorPane && pane.result !== null && pane.result !== undefined && !pane.error;
    const paneValueContent = pane.error ? (
      <div className="pane-empty error">{pane.error}</div>
    ) : isOperatorPane ? (
      renderManagedWorkPane(windowItem, pane)
    ) : value === null ? (
      <div className="pane-empty">
        {pane.pulseName || pane.pulseAddress ? "Ready." : "Select a pulse."}
      </div>
    ) : (
      <ValueRenderer key={`${pane.id}:${pane.displayFormat}:${pane.chartType}`} value={value} format={pane.displayFormat} chartType={pane.chartType} />
    );
    return (
      <article
        key={pane.id}
        className={`pane-card pane-card--${effectivePaneStatus} pane-card--floating${isMindMapPane ? " pane-card--mind-map" : ""}${isOperatorPane ? " pane-card--managed-work" : ""}`}
        style={paneStyle}
        onMouseDown={(event) => handlePaneMouseDown(windowItem.id, pane.id, event)}
      >
        <header className={editing ? "pane-card-head pane-card-head--draggable" : "pane-card-head"} onMouseDown={editing ? (event) => handlePaneHeaderMouseDown(windowItem.id, pane.id, event) : undefined}>
          <strong>{pane.title}</strong>
          <div className="pane-card-actions">
            {isMindMapPane ? (
              <>
                <div className="segmented pane-card-view-toggle">
                  {["diagram", "info"].map((mode) => (
                    <button
                      key={mode}
                      className={diagramDisplayMode === mode ? "segment active" : "segment"}
                      onClick={() => updatePaneField(windowItem.id, pane.id, "diagramDisplayMode", mode)}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
                <button
                  className="icon-button"
                  onClick={() => runBrowserPane(windowItem.id, pane.id)}
                  disabled={pane.status === "loading"}
                  aria-label="Refresh pane data"
                  title={pane.status === "loading" ? "Getting data..." : "Refresh pane data"}
                >
                  <RefreshIcon />
                </button>
                <button
                  className="ghost-button pane-open-editor-button"
                  onClick={() => openLinkedMindMapPaneEditor(windowItem.id, pane.id)}
                  aria-label={paneEditorTitle}
                  title={paneEditorTitle}
                >
                  {paneEditorLabel}
                </button>
              </>
            ) : (
                <button
                  className="icon-button"
                  onClick={() => runBrowserPane(windowItem.id, pane.id)}
                  disabled={effectivePaneStatus === "loading"}
                  aria-label="Refresh pane"
                  title={effectivePaneStatus === "loading" ? "Refreshing..." : "Refresh pane"}
                >
                  <RefreshIcon />
                </button>
            )}
            {isMindMapPane || isOperatorPane ? null : (
              <button
                className="ghost-button"
                onClick={() => savePaneResultToDefaultLocation(windowItem.id, pane.id)}
                disabled={!canSaveResult || pane.saveStatus === "saving"}
                title={!canSaveResult ? "Run the pane first to save a result." : pane.saveStatus === "saving" ? "Saving result..." : "Save result to the default storage destination"}
              >
                {pane.saveStatus === "saving" ? "Saving..." : "Save"}
              </button>
            )}
            {editing ? (
              <>
                <button className="icon-button" onClick={() => openPaneConfig(windowItem.id, pane.id)} aria-label="Configure pane" title="Configure pane">
                  <ConfigIcon />
                </button>
                <button className="icon-button icon-button--danger" onClick={() => deletePane(windowItem.id, pane.id)} aria-label="Delete pane" title="Delete pane">
                  ×
                </button>
              </>
            ) : null}
          </div>
        </header>
        {showDiagramPreview ? (
          <div className="pane-card-body pane-card-body--diagram">
            <div className="pane-diagram-preview" onDoubleClick={() => openLinkedMindMapPaneEditor(windowItem.id, pane.id)}>
              <div className={paneMap?.showGrid === false ? "pane-diagram-canvas pane-diagram-canvas--grid-hidden" : "pane-diagram-canvas"}>
                {paneMap?.edges?.length ? (
                  <svg className="pane-diagram-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                    {paneMap.edges.map((edge) => {
                      const fromNode = paneMap.nodes.find((entry) => entry.id === edge.from);
                      const toNode = paneMap.nodes.find((entry) => entry.id === edge.to);
                      if (!fromNode || !toNode) {
                        return null;
                      }
                      return <path key={edge.id} className="pane-diagram-link" d={connectionPath(fromNode, toNode, edge)} />;
                    })}
                  </svg>
                ) : null}
                {paneMap?.nodes?.length ? paneMap.nodes.slice(0, 16).map((node) => (
                  <div
                    key={node.id}
                    className={`pane-diagram-node pane-diagram-node--${node.type}`}
                    style={{
                      left: `${clamp(Number(node.x || 0), 0, 84)}%`,
                      top: `${clamp(Number(node.y || 0), 0, 86)}%`,
                      width: `${clamp(Number(node.w || 18), 12, 32)}%`,
                      height: `${clamp(Number(node.h || 12), 8, 24)}%`,
                    }}
                  >
                    <span>{node.title || "Shape"}</span>
                  </div>
                )) : (
                  <div className="pane-diagram-empty">
                    <strong>Diagram pane</strong>
                    <span>Open the editor to start mapping ideas.</span>
                  </div>
                )}
              </div>
              <div className="pane-diagram-meta">
                <span>{paneMap?.nodes?.length || 0} shapes</span>
                <span>{paneMap?.edges?.length || 0} links</span>
              </div>
            </div>
          </div>
        ) : (
          <div className={isOperatorPane ? "pane-card-body pane-card-body--operator" : "pane-card-body"}>
            {paneValueContent}
          </div>
        )}
        {!isOperatorPane && pane.saveError ? (
          <div className="pane-save-status pane-save-status--error">{pane.saveError}</div>
        ) : !isOperatorPane && pane.lastSavedLocation ? (
          <div className="pane-save-status">
            Saved to <code>{pane.lastSavedLocation}</code>{pane.lastSavedAt ? ` at ${pane.lastSavedAt}` : ""}
          </div>
        ) : null}
        {editing ? <button className="pane-resize-handle" onMouseDown={(event) => beginPaneResize(windowItem.id, pane.id, event)} aria-label="Resize pane" /> : null}
      </article>
    );
  }

  function renderBrowserWindow(windowItem) {
    const snapshots = getBrowserSnapshots(windowItem.id);
    const visiblePanes = windowItem.panes.filter((pane) => BROWSER_PANE_TYPES.some((entry) => entry.id === pane.type));

    return (
      <section className="window-surface browser-surface">
        <div className="window-toolbar window-toolbar--browser">
          <div className="browser-toolbar-actions">
            <div className="browser-toolbar-symbol">
              <input
                className="toolbar-symbol-input"
                value={windowItem.browserDefaults.symbolDraft}
                onChange={(event) => updateState((next) => {
                  const target = findWindowLocation(next, windowItem.id).windowItem;
                  target.browserDefaults.symbolDraft = event.target.value;
                })}
                onBlur={() => updateState((next) => {
                  const target = findWindowLocation(next, windowItem.id).windowItem;
                  target.browserDefaults.symbol = target.browserDefaults.symbolDraft.trim().toUpperCase();
                })}
                placeholder="Symbol"
              />
            </div>
            <div className="browser-toolbar-buttons">
              <button className="ghost-button" onClick={() => refreshBrowserCatalog(windowItem.id)}>{windowItem.browserCatalog.status === "loading" ? "Refreshing..." : "Refresh"}</button>
              <button className="ghost-button" onClick={() => addPane(windowItem.id, "managed_work")}>Managed Work</button>
              <button
                className={state.snapshotDialog.open && state.snapshotDialog.windowId === windowItem.id && state.snapshotDialog.mode === "save" ? "ghost-button active" : "ghost-button"}
                onClick={() => openSnapshotDialog(windowItem.id, "save")}
              >
                Save
              </button>
              <button
                className={state.snapshotDialog.open && state.snapshotDialog.windowId === windowItem.id && state.snapshotDialog.mode === "load" ? "ghost-button active" : "ghost-button"}
                onClick={() => openSnapshotDialog(windowItem.id, "load")}
              >
                Load
              </button>
              <button className="ghost-button" onClick={() => toggleWindowMode(windowItem.id, windowItem.mode === "docked" ? "external" : "docked")}>{windowItem.mode === "docked" ? "Pop" : "Dock"}</button>
              <div className="segmented segmented--mode">
                {["view", "edit"].map((mode) => (
                  <button
                    key={mode}
                    className={windowItem.browserPageMode === mode ? "segment active" : "segment"}
                    onClick={() => updateState((next) => {
                      const target = findWindowLocation(next, windowItem.id).windowItem;
                      target.browserPageMode = mode;
                      if (mode !== "edit" && next.paneMenuWindowId === windowItem.id) {
                        next.paneMenuWindowId = "";
                      }
                    })}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              {windowItem.browserPageMode === "edit" && (
                <>
                  <div className="pane-dropdown">
                    <button className="accent-button" onClick={() => togglePaneMenu(windowItem.id)}>
                      Add Pane
                    </button>
                    {state.paneMenuWindowId === windowItem.id ? (
                      <div className="pane-dropdown-menu">
                        {BROWSER_PANE_TYPES.map((paneType) => (
                          <button key={paneType.id} className="ghost-button pane-dropdown-item" onClick={() => addPane(windowItem.id, paneType.id)}>
                            {paneType.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <button className="icon-button icon-button--danger" onClick={() => deleteWindow(windowItem.id)} aria-label="Delete window">
                    ×
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="browser-pane-canvas" ref={(node) => setBrowserPaneCanvasRef(windowItem.id, node)}>
          {visiblePanes.length ? visiblePanes.map((pane) => renderBrowserPane(windowItem, pane)) : (
            <div className="pane-empty wide browser-pane-empty">
              {windowItem.browserDefaults.symbol ? "Add a pane." : "Enter a symbol."}
            </div>
          )}
        </div>
      </section>
    );
  }

  function renderMindMapWindow(windowItem) {
    const resolved = resolveMindMapSource(state, windowItem.id);
    const map = resolved?.mapState;
    const mindMapCatalog = windowItem.mindMapCatalog || emptyCatalog(state.preferences.connectionPlazaUrl);
    const mindMapSnapshots = getMindMapSnapshots();

    if (!map) {
      return <div className="pane-empty">Mind map source unavailable.</div>;
    }

    if (!IS_MAP_PHEMAR_MODE) {
      const linkedPhemaId = String(map.linkedPhemaId || "").trim();
      const ownerLabel = linkedPhemaId ? (map.linkedPhemaName || windowItem.title || "Diagram-backed Phema") : (windowItem.title || "Diagram");
      const sourceSummary = windowItem.linkedPaneContext
        ? "Use the pane Editor button to open this linked diagram directly in MapPhemar."
        : "MapPhemar now owns diagram editing for personal-agent flows.";
      return (
        <section className="window-surface window-surface--mindmap-owner">
          <div className="mindmap-owner-bridge">
            <div className="mindmap-owner-copy">
              <strong>{ownerLabel}</strong>
              <span>{sourceSummary}</span>
            </div>
            <div className="mindmap-owner-meta">
              <span>{map.nodes.length} shapes</span>
              <span>{map.edges.length} links</span>
              <span>{linkedPhemaId ? `Owner Phema: ${linkedPhemaId}` : "Owner Phema will be created on open"}</span>
            </div>
            <div className="mindmap-owner-actions">
              <button className="accent-button" onClick={() => openMindMapWindowInMapPhemar(windowItem.id)}>
                Open In MapPhemar
              </button>
              {linkedPhemaId ? (
                <button className="ghost-button" onClick={() => openMindMapWindowInMapPhemar(windowItem.id)}>
                  Update Owner
                </button>
              ) : null}
            </div>
          </div>
        </section>
      );
    }

    function beginDrag(nodeId, event) {
      if (mindMapLinkRef.current || mindMapResizeRef.current) {
        return;
      }
      const canvas = event.currentTarget.closest(".mindmap-canvas");
      if (!canvas) {
        return;
      }
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node) {
        return;
      }
      const rect = canvas.getBoundingClientRect();
      mindMapDragRef.current = {
        windowId: windowItem.id,
        nodeId,
        startX: event.clientX,
        startY: event.clientY,
        rect,
        node,
        dragging: false,
      };
    }

    function beginResize(nodeId, event) {
      event.preventDefault();
      event.stopPropagation();
      const canvas = event.currentTarget.closest(".mindmap-canvas");
      if (!canvas) {
        return;
      }
      const node = map.nodes.find((entry) => entry.id === nodeId);
      if (!node) {
        return;
      }
      const rect = canvas.getBoundingClientRect();
      mindMapResizeRef.current = {
        windowId: windowItem.id,
        nodeId,
        startX: event.clientX,
        startY: event.clientY,
        rect,
        node,
      };
      selectMindMapNode(windowItem.id, nodeId);
    }

    function beginInspectorResize(event) {
      event.preventDefault();
      event.stopPropagation();
      mindMapInspectorResizeRef.current = {
        windowId: windowItem.id,
        startX: event.clientX,
        startWidth: clamp(Number(map.inspectorWidth || 320), 280, 560),
      };
    }

  function handleCanvasMove(event) {
      if (mindMapLinkRef.current && mindMapLinkRef.current.windowId === windowItem.id) {
        const draft = mindMapLinkRef.current;
        if (!draft.rect) {
          const canvas = event.target instanceof Element ? event.target.closest(".mindmap-canvas") : null;
          if (canvas) {
            draft.rect = canvas.getBoundingClientRect();
          }
        }
        if (draft.rect?.width && draft.rect?.height) {
          const x = clamp(((event.clientX - draft.rect.left) / draft.rect.width) * 100, 0, 100);
          const y = clamp(((event.clientY - draft.rect.top) / draft.rect.height) * 100, 0, 100);
          updateState((next) => {
            const target = resolveMindMapSource(next, windowItem.id);
            if (!target) {
              return;
            }
            target.mapState.linkDraftX = x;
            target.mapState.linkDraftY = y;
          });
        }
      }
      if (mindMapInspectorResizeRef.current && mindMapInspectorResizeRef.current.windowId === windowItem.id) {
        const resize = mindMapInspectorResizeRef.current;
        const delta = resize.startX - event.clientX;
        setMindMapInspectorWidth(windowItem.id, resize.startWidth + delta);
        return;
      }
      if (mindMapResizeRef.current && mindMapResizeRef.current.windowId === windowItem.id) {
        const resize = mindMapResizeRef.current;
        const deltaX = ((event.clientX - resize.startX) / resize.rect.width) * 100;
        const deltaY = ((event.clientY - resize.startY) / resize.rect.height) * 100;
        updateMindMap(windowItem.id, (nextMap) => {
          const node = nextMap.nodes.find((entry) => entry.id === resize.nodeId);
          if (!node) {
            return;
          }
          if (usesDiamondMindMapFootprint(node.type)) {
            const constrained = constrainMindMapShapeResize(node.type, resize.node.w + deltaX, resize.node.h + deltaY);
            node.w = clamp(constrained.w, 10, 36);
            node.h = clamp(constrained.h, 10, 36);
            return;
          }
          node.w = clamp(resize.node.w + deltaX, 10, 44);
          node.h = clamp(resize.node.h + deltaY, 8, 36);
        });
        return;
      }
      if (!mindMapDragRef.current || mindMapDragRef.current.windowId !== windowItem.id) {
        return;
      }
      const drag = mindMapDragRef.current;
      const moveX = event.clientX - drag.startX;
      const moveY = event.clientY - drag.startY;
      if (!drag.dragging) {
        if (Math.hypot(moveX, moveY) < 4) {
          return;
        }
        drag.dragging = true;
      }
      const deltaX = (moveX / drag.rect.width) * 100;
      const deltaY = (moveY / drag.rect.height) * 100;
      updateMindMap(windowItem.id, (nextMap) => {
        const node = nextMap.nodes.find((entry) => entry.id === drag.nodeId);
        if (!node) {
          return;
        }
        node.x = clamp(drag.node.x + deltaX, 0, 78);
        node.y = clamp(drag.node.y + deltaY, 0, 82);
      });
    }

    function handleCanvasUp() {
      mindMapDragRef.current = null;
      mindMapResizeRef.current = null;
      mindMapInspectorResizeRef.current = null;
      if (mindMapLinkRef.current?.windowId === windowItem.id) {
        cancelMindMapLink(windowItem.id);
      }
    }

    const selectedNode = map.nodes.find((entry) => entry.id === map.selectedNodeId) || null;
    const selectedEdge = map.edges.find((entry) => entry.id === map.selectedEdgeId) || null;
    const selectedEdgeMeta = selectedEdge ? edgeCompatibility(map, selectedEdge) : null;
    const selectedEdgeMapping = selectedEdge ? parseEdgeMapping(selectedEdge) : { mapping: {}, error: "" };
    const selectedEdgeSourceNode = selectedEdge ? map.nodes.find((entry) => entry.id === selectedEdge.from) || null : null;
    const selectedEdgeTargetNode = selectedEdge ? map.nodes.find((entry) => entry.id === selectedEdge.to) || null : null;
    const selectedEdgeSourceTree = selectedEdgeSourceNode ? schemaTreeEntries(selectedEdgeSourceNode.outputSchema || {}) : [];
    const selectedEdgeSourceLookup = flattenSchemaTreeAll(selectedEdgeSourceTree).reduce((lookup, entry) => {
      lookup.set(entry.path, entry);
      return lookup;
    }, new Map());
    const expandedSourcePathSet = new Set(Array.isArray(map.expandedSourcePaths) ? map.expandedSourcePaths : []);
    const selectedEdgeVisibleSourceNodes = flattenSchemaTree(selectedEdgeSourceTree, expandedSourcePathSet);
    const selectedEdgeSourceOptions = Array.from(selectedEdgeSourceLookup.values());
    const selectedEdgeTargetFields = selectedEdgeTargetNode ? schemaFieldEntries(selectedEdgeTargetNode.inputSchema || {}) : [];
    const inspectorWidth = clamp(Number(map.inspectorWidth || 320), 280, 560);
    const shapePresets = MINDMAP_SHAPE_PRESETS;
    const pulseOptions = collectCatalogPulses(mindMapCatalog);
    const selectedNodeBoundary = selectedNode ? normalizeBoundaryMindMapRole(selectedNode.role) : "";
    const selectedNodeBranch = selectedNode ? isBranchMindMapNode(selectedNode) : false;
    const selectedBranchConnectionCounts = selectedNodeBranch && selectedNode
      ? branchMindMapConnectionCounts(map, selectedNode)
      : { input: 0, yes: 0, no: 0 };
    const selectedBoundaryConfig = selectedNodeBoundary ? boundarySchemaConfig(selectedNodeBoundary) : null;
    const selectedBoundaryLinkedNode = selectedNodeBoundary && selectedNode
      ? boundaryMindMapLinkedNode(map, selectedNode)
      : null;
    const pulseFilterText = String(deferredMindMapPulseFilterText || "").trim().toLowerCase();
    const filteredPulseOptions = pulseFilterText
      ? pulseOptions.filter((pulse) => `${pulse.pulse_name || ""}\n${pulse.plazaDescription || pulse.description || ""}`.toLowerCase().includes(pulseFilterText))
      : pulseOptions;
    const selectedPulse = selectedNode && !selectedNodeBoundary && !selectedNodeBranch
      ? pulseOptions.find((entry) => pulseMatches(entry, selectedNode.pulseAddress, selectedNode.pulseName)) || null
      : null;
    const activePulserOptions = (selectedPulse?.compatible_pulsers || []).filter((entry) => Number(entry.last_active || 0) > 0);
    const selectedCompatiblePulser = activePulserOptions.find((entry) => (
      (selectedNode?.pulserId && entry.pulser_id === selectedNode.pulserId)
      || (selectedNode?.pulserName && entry.pulser_name === selectedNode.pulserName)
      || (selectedNode?.pulserAddress && entry.pulser_address === selectedNode.pulserAddress)
    )) || null;
    const mindMapImportNotice = String(
      resolved?.linkedPaneLocation?.pane?.error
      || windowItem.mindMapError
      || map.importNotice
      || "",
    ).trim();
    const diagramRunReady = mindMapRunReadiness(map, state.preferences.connectionPlazaUrl, mindMapCatalog);
    const diagramRunOpen = state.diagramRunDialog.open && state.diagramRunDialog.windowId === windowItem.id;
    const diagramRunBusy = diagramRunOpen && state.diagramRunDialog.status === "loading";
    const linkSourceNode = map.nodes.find((entry) => entry.id === map.linkDraftFrom) || null;
    const linkDraftPoint = linkSourceNode && Number.isFinite(Number(map.linkDraftX)) && Number.isFinite(Number(map.linkDraftY))
      ? { x: Number(map.linkDraftX), y: Number(map.linkDraftY) }
      : null;
    const linkDraftPath = linkSourceNode && linkDraftPoint
      ? connectionPathToPoint(linkSourceNode, map.linkDraftAnchor || "right", linkDraftPoint)
      : "";
    const showLayoutSnapshotButtons = !IS_MAP_PHEMAR_MODE;
    const canvasSummary = linkSourceNode
      ? `Linking from ${linkSourceNode.title}. Select another node to create a connection.`
      : selectedNode
        ? `${selectedNode.title} is selected. Tune the shape settings in the inspector or connect it to another shape.`
        : selectedEdgeMeta
          ? selectedEdgeMeta.reason
          : "Arrange shapes on the canvas and connect them like a lightweight diagram board.";
    const windowTitle = IS_MAP_PHEMAR_MODE
      ? APP_DISPLAY_NAME
      : windowItem.linkedPaneContext
        ? "Linked Diagram"
        : "Diagram Builder";
    const contextTitle = selectedNode
      ? selectedNode.title
      : selectedEdge
        ? selectedEdge.label || "Connection"
        : linkSourceNode
          ? `Link from ${linkSourceNode.title}`
          : IS_MAP_PHEMAR_MODE
            ? (map.linkedPhemaName || windowItem.title || "Untitled Phema")
            : "Canvas";
    const contextMeta = selectedNode
      ? selectedNodeBoundary
        ? `${boundaryMindMapTitle(selectedNodeBoundary)} schema boundary`
        : selectedNodeBranch
          ? "Branch node"
        : `${mindMapShapePreset(selectedNode.type).label} shape`
      : selectedEdgeMeta
        ? selectedEdgeMeta.label
        : `${map.nodes.length} nodes and ${map.edges.length} links`;
    function renderShapeToolButton(shape, mode, active = false) {
      const isAddMode = mode === "add";
      const label = isAddMode ? `Add ${shape.label}` : `Set shape to ${shape.label}`;
      return (
        <button
          key={`${mode}-${shape.id}`}
          type="button"
          className={active ? "mindmap-shape-button active" : "mindmap-shape-button"}
          title={label}
          aria-label={label}
          aria-pressed={active}
          draggable={isAddMode}
          onClick={() => {
            if (isAddMode) {
              addMindMapNode(windowItem.id, undefined, undefined, shape.id);
              return;
            }
            if (selectedNode) {
              updateMindMapNode(windowItem.id, selectedNode.id, "type", shape.id);
            }
          }}
          onDragStart={isAddMode ? (event) => {
            event.dataTransfer.setData("text/plain", shape.id);
          } : undefined}
        >
          <span className={`mindmap-shape-preview mindmap-shape-preview--${shape.id}`} aria-hidden="true" />
        </button>
      );
    }
    function renderConnectionHandle(node, handle) {
      const isActive = handle.interactive && map.linkDraftFrom === node.id && map.linkDraftAnchor === handle.anchor;
      const className = [
        "mindmap-node-handle",
        `mindmap-node-handle--${handle.anchor}`,
        handle.side ? `mindmap-node-handle--side-${handle.side}` : "",
        isBranchMindMapNode(node) ? "mindmap-node-handle--branch" : "",
        handle.interactive ? "" : "mindmap-node-handle--passive",
        isActive ? "active" : "",
      ].filter(Boolean).join(" ");
      if (!handle.interactive) {
        return (
          <span
            key={`${node.id}-${handle.anchor}`}
            className={className}
            style={handle.style}
            title={handle.title}
            aria-hidden="true"
          >
            {handle.label ? <span className="mindmap-node-handle-label">{handle.label}</span> : null}
          </span>
        );
      }
      return (
        <button
          key={`${node.id}-${handle.anchor}`}
          type="button"
          className={className}
          style={handle.style}
          aria-label={handle.title || `Create connection from ${node.title}`}
          title={handle.title}
          onMouseDown={(event) => {
            event.preventDefault();
            event.stopPropagation();
            const canvas = event.currentTarget.closest(".mindmap-canvas");
            startMindMapLink(windowItem.id, node.id, handle.anchor, canvas ? canvas.getBoundingClientRect() : null);
          }}
        >
          {handle.label ? <span className="mindmap-node-handle-label">{handle.label}</span> : null}
        </button>
      );
    }

    return (
      <section className="window-surface window-surface--mindmap">
        <div className="mindmap-app-shell">
          <div className="mindmap-layout" onMouseMove={handleCanvasMove} onMouseUp={handleCanvasUp}>
            <div className="mindmap-top-zone">
              <div className="mindmap-top-group mindmap-top-group--brand">
                <button className="mindmap-ui-button mindmap-ui-button--icon" onClick={() => clearMindMapSelection(windowItem.id)}>
                  DG
                </button>
                <div className="mindmap-top-copy">
                  <strong>{windowTitle}</strong>
                  <span>{canvasSummary}</span>
                </div>
              </div>
              <div className="mindmap-top-group mindmap-top-group--context">
                <div className="mindmap-context-copy">
                  <strong>{contextTitle}</strong>
                  <span>{contextMeta}</span>
                </div>
              </div>
              <div className="mindmap-top-group mindmap-top-group--actions">
                {showLayoutSnapshotButtons ? (
                  <button
                    className={state.snapshotDialog.open && state.snapshotDialog.windowId === windowItem.id && state.snapshotDialog.kind === "mind_map" && state.snapshotDialog.mode === "load" ? "mindmap-ui-button active" : "mindmap-ui-button"}
                    onClick={() => openSnapshotDialog(windowItem.id, "load", "mind_map")}
                    disabled={!mindMapSnapshots.length}
                  >
                    Load
                  </button>
                ) : (
                  <>
                    <button
                      className={phemaDialog.open && phemaDialog.windowId === windowItem.id && phemaDialog.mode === "save" ? "mindmap-ui-button active" : "mindmap-ui-button"}
                      onClick={() => openPhemaDialog(windowItem.id, "save")}
                    >
                      Save
                    </button>
                    <button
                      className={phemaDialog.open && phemaDialog.windowId === windowItem.id && phemaDialog.mode === "load" ? "mindmap-ui-button active" : "mindmap-ui-button"}
                      onClick={() => openPhemaDialog(windowItem.id, "load")}
                    >
                      Load
                    </button>
                  </>
                )}
                {!IS_MAP_PHEMAR_MODE ? (
                  <>
                    <button
                      className={phemaDialog.open && phemaDialog.windowId === windowItem.id && phemaDialog.mode === "save" ? "mindmap-ui-button active" : "mindmap-ui-button"}
                      onClick={() => openPhemaDialog(windowItem.id, "save")}
                    >
                      Save Phema
                    </button>
                    <button
                      className={phemaDialog.open && phemaDialog.windowId === windowItem.id && phemaDialog.mode === "load" ? "mindmap-ui-button active" : "mindmap-ui-button"}
                      onClick={() => openPhemaDialog(windowItem.id, "load")}
                    >
                      Load Phema
                    </button>
                  </>
                ) : null}
                <button
                  className={diagramRunOpen ? "mindmap-ui-button active" : "mindmap-ui-button"}
                  onClick={() => openDiagramRunDialog(windowItem.id)}
                  disabled={!diagramRunReady.canRun || diagramRunBusy}
                  title={diagramRunReady.canRun ? "Test the connected diagram flow." : diagramRunReady.reason}
                >
                  {diagramRunBusy ? "Running..." : "Test Run"}
                </button>
                {!IS_MAP_PHEMAR_MODE && windowItem.mode === "docked" ? (
                  <>
                    <button className="mindmap-ui-button" onClick={() => toggleWindowMode(windowItem.id, "external")}>
                      Pop Out
                    </button>
                    <button className="mindmap-ui-button mindmap-ui-button--danger" onClick={() => deleteWindow(windowItem.id)}>
                      Delete
                    </button>
                  </>
                ) : !IS_MAP_PHEMAR_MODE ? (
                  <button className="mindmap-ui-button mindmap-ui-button--danger" onClick={() => deleteWindow(windowItem.id)}>
                    Close Window
                  </button>
                ) : null}
              </div>
            </div>

            <aside className="mindmap-library-panel">
              <div className="mindmap-panel-header">
                <div>
                  <strong>Shapes</strong>
                </div>
              </div>
              <div className="mindmap-shape-grid" role="toolbar" aria-label="Add shapes">
                {shapePresets.map((shape) => renderShapeToolButton(shape, "add", selectedNode?.type === shape.id))}
              </div>
            </aside>

            <aside className="mindmap-right-panel" style={{ width: `${inspectorWidth}px` }}>
              <button
                type="button"
                className="mindmap-right-panel-resize"
                aria-label="Resize inspector"
                onMouseDown={beginInspectorResize}
              />
              <div className="mindmap-panel-header">
                <div>
                  <strong>Inspector</strong>
                  <span>{selectedNode ? "Shape config" : selectedEdge ? "Connection config" : "Canvas summary"}</span>
                </div>
              </div>
              {mindMapImportNotice ? <div className="form-error">{mindMapImportNotice}</div> : null}
              {!selectedNode && !selectedEdge ? (
                <div className="inspector-empty">
                  <strong>Select a node or edge.</strong>
                  <span>{linkSourceNode ? `Linking from ${linkSourceNode.title}.` : "The right panel stays contextual, just like a whiteboard editor."}</span>
                </div>
              ) : null}
              {selectedNode ? (
                <div className="inspector-stack">
                  <div className="subhead">
                    <strong>{selectedNodeBoundary ? boundaryMindMapTitle(selectedNodeBoundary) : "Shape"}</strong>
                    <span>{selectedNodeBoundary ? "Schema boundary" : mindMapShapePreset(selectedNode.type).label}</span>
                  </div>
                  {selectedNodeBoundary ? (
                    <div className="inspector-stack">
                      <p className="compatibility-copy">
                        {selectedBoundaryLinkedNode
                          ? `${selectedBoundaryConfig?.helper} Inherited from ${selectedBoundaryLinkedNode.title} while connected.`
                          : selectedBoundaryConfig?.helper}
                      </p>
                      <label className="field">
                        <span>{selectedBoundaryConfig?.label}</span>
                        <textarea
                          value={selectedNode[selectedBoundaryConfig.textKey] || "{}"}
                          readOnly={Boolean(selectedBoundaryLinkedNode)}
                          onChange={(event) => updateMindMapBoundarySchema(windowItem.id, selectedNode.id, event.target.value)}
                          placeholder={'{\n  "field_name": { "type": "string" }\n}'}
                        />
                      </label>
                      {selectedBoundaryConfig && selectedNode[selectedBoundaryConfig.errorKey] ? (
                        <p className="form-error">{selectedNode[selectedBoundaryConfig.errorKey]}</p>
                      ) : null}
                    </div>
                  ) : selectedNodeBranch ? (
                    <>
                      <div className="mindmap-inspector-actions">
                        <button className="mindmap-ui-button mindmap-ui-button--danger" onClick={() => deleteMindMapNode(windowItem.id, selectedNode.id)}>
                          Delete Node
                        </button>
                      </div>
                      <div className="field">
                        <span>Shape</span>
                        <div className="mindmap-shape-picker" role="toolbar" aria-label="Select shape">
                          {shapePresets.map((shape) => renderShapeToolButton(shape, "select", selectedNode.type === shape.id))}
                        </div>
                      </div>
                      <label className="field">
                        <span>Title</span>
                        <input value={selectedNode.title} onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, "title", event.target.value)} />
                      </label>
                      <label className="field">
                        <span>Python Condition</span>
                        <textarea
                          value={selectedNode.conditionExpression || ""}
                          onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, "conditionExpression", event.target.value)}
                          placeholder={'input_data.get("passed", False)'}
                        />
                      </label>
                      <label className="field">
                        <span>Input Dot Side</span>
                        <select
                          value={branchConnectorSide(selectedNode, "input")}
                          onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorField("input"), event.target.value)}
                        >
                          {BRANCH_CONNECTOR_SIDES.map((side) => (
                            <option key={side} value={side}>{side}</option>
                          ))}
                        </select>
                      </label>
                      {selectedBranchConnectionCounts.input > 1 ? (
                        <label className="field">
                          <span>Input Multi-Link Mode</span>
                          <select
                            value={branchConnectorMode(selectedNode, "input")}
                            onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorModeField("input"), event.target.value)}
                          >
                            {BRANCH_CONNECTOR_PROCESS_MODES.map((mode) => (
                              <option key={mode} value={mode}>{mode === "any" ? "Any" : "All"}</option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      <label className="field">
                        <span>Yes Dot Side</span>
                        <select
                          value={branchConnectorSide(selectedNode, "yes")}
                          onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorField("yes"), event.target.value)}
                        >
                          {BRANCH_CONNECTOR_SIDES.map((side) => (
                            <option key={side} value={side}>{side}</option>
                          ))}
                        </select>
                      </label>
                      {selectedBranchConnectionCounts.yes > 1 ? (
                        <label className="field">
                          <span>Yes Multi-Link Mode</span>
                          <select
                            value={branchConnectorMode(selectedNode, "yes")}
                            onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorModeField("yes"), event.target.value)}
                          >
                            {BRANCH_CONNECTOR_PROCESS_MODES.map((mode) => (
                              <option key={mode} value={mode}>{mode === "any" ? "Any" : "All"}</option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      <label className="field">
                        <span>No Dot Side</span>
                        <select
                          value={branchConnectorSide(selectedNode, "no")}
                          onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorField("no"), event.target.value)}
                        >
                          {BRANCH_CONNECTOR_SIDES.map((side) => (
                            <option key={side} value={side}>{side}</option>
                          ))}
                        </select>
                      </label>
                      {selectedBranchConnectionCounts.no > 1 ? (
                        <label className="field">
                          <span>No Multi-Link Mode</span>
                          <select
                            value={branchConnectorMode(selectedNode, "no")}
                            onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, branchConnectorModeField("no"), event.target.value)}
                          >
                            {BRANCH_CONNECTOR_PROCESS_MODES.map((mode) => (
                              <option key={mode} value={mode}>{mode === "any" ? "Any" : "All"}</option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      <p className="compatibility-copy">
                        Branch nodes evaluate the Python expression against the inbound payload as <code>input_data</code> or <code>payload</code>. Input <code>Any</code> runs when at least one inbound link is active, Input <code>All</code> waits for every inbound link, and Yes or No <code>Any</code> uses the first matching route while <code>All</code> fans out to every matching route.
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="mindmap-inspector-actions">
                        <button className="mindmap-ui-button" onClick={() => refreshMindMapCatalog(windowItem.id)}>
                          {mindMapCatalog.status === "loading" ? "Loading..." : "Refresh Pulses"}
                        </button>
                        <button className="mindmap-ui-button mindmap-ui-button--danger" onClick={() => deleteMindMapNode(windowItem.id, selectedNode.id)}>
                          Delete Node
                        </button>
                      </div>
                      <div className="field">
                        <span>Shape</span>
                        <div className="mindmap-shape-picker" role="toolbar" aria-label="Select shape">
                          {shapePresets.map((shape) => renderShapeToolButton(shape, "select", selectedNode.type === shape.id))}
                        </div>
                      </div>
                      <label className="field">
                        <span>Title</span>
                        <input value={selectedNode.title} onChange={(event) => updateMindMapNode(windowItem.id, selectedNode.id, "title", event.target.value)} />
                      </label>
                      <label className="field">
                        <span>Search Pulse</span>
                        <input value={mindMapPulseFilterText} placeholder="Find a pulse" onChange={(event) => setMindMapPulseFilterText(event.target.value)} />
                      </label>
                      <label className="field">
                        <span>Pulse</span>
                        <select value={selectedPulse?.key || ""} onChange={(event) => assignCatalogPulseToMindMapNode(windowItem.id, selectedNode.id, event.target.value)}>
                          <option value="">{mindMapCatalog.status === "loading" ? "Loading pulses" : "Choose pulse"}</option>
                          {filteredPulseOptions.map((pulse) => (
                            <option key={pulse.key} value={pulse.key}>
                              {pulse.pulse_name || pulse.pulse_address}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Active Pulser</span>
                        <select
                          value={selectedCompatiblePulser?.pulser_id || selectedCompatiblePulser?.pulser_name || ""}
                          onChange={(event) => selectMindMapNodePulser(windowItem.id, selectedNode.id, event.target.value)}
                          disabled={!selectedPulse || !activePulserOptions.length}
                        >
                          <option value="">
                            {!selectedPulse ? "Choose pulse first" : activePulserOptions.length ? "Choose pulser" : "No active pulser"}
                          </option>
                          {activePulserOptions.map((pulser) => (
                            <option key={pulser.pulser_id || pulser.pulser_name} value={pulser.pulser_id || pulser.pulser_name}>
                              {formatCompatiblePulserOptionLabel(pulser)}
                            </option>
                          ))}
                        </select>
                      </label>
                      {mindMapCatalog.status === "error" ? <p className="form-error">{mindMapCatalog.error || "Unable to load pulses."}</p> : null}
                    </>
                  )}
                </div>
              ) : null}
              {selectedEdge ? (
                <div className="inspector-stack">
                  <div className="subhead">
                    <strong>Connection</strong>
                    <span>{selectedEdge.label || "Connection"}</span>
                  </div>
                  <label className="field">
                    <span>Label</span>
                    <input value={selectedEdge.label || ""} onChange={(event) => updateMindMapEdge(windowItem.id, selectedEdge.id, "label", event.target.value)} />
                  </label>
                  <div className="field">
                    <span>Mapping Config</span>
                    <div className="segmented mindmap-mapping-tabs" role="tablist" aria-label="Mapping config mode">
                      <button
                        type="button"
                        className={mindMapMappingTab === "visual" ? "segment active" : "segment"}
                        role="tab"
                        aria-selected={mindMapMappingTab === "visual"}
                        onClick={() => setMindMapMappingTab("visual")}
                      >
                        Visual
                      </button>
                      <button
                        type="button"
                        className={mindMapMappingTab === "raw" ? "segment active" : "segment"}
                        role="tab"
                        aria-selected={mindMapMappingTab === "raw"}
                        onClick={() => setMindMapMappingTab("raw")}
                      >
                        Raw
                      </button>
                    </div>
                  </div>
                  {mindMapMappingTab === "visual" ? (
                    <div className="mindmap-mapper">
                      <div className="mindmap-mapper-source-browser">
                        <div className="mindmap-mapper-subhead">
                          <strong>Source Schema</strong>
                          <span>{selectedEdgeSourceNode ? summarizeSchema(selectedEdgeSourceNode.outputSchema || {}) : "Unavailable"}</span>
                        </div>
                        {selectedEdgeVisibleSourceNodes.length ? (
                          <div className="mindmap-source-tree" role="tree" aria-label="Source fields">
                            {selectedEdgeVisibleSourceNodes.map((field) => (
                              <div
                                key={field.path}
                                className="mindmap-source-row"
                                role="treeitem"
                                aria-expanded={field.expandable ? expandedSourcePathSet.has(field.path) : undefined}
                                style={{ "--mindmap-source-depth": field.depth }}
                              >
                                <div className="mindmap-source-row-main">
                                  {field.expandable ? (
                                    <button
                                      type="button"
                                      className="mindmap-source-toggle"
                                      onClick={() => toggleMindMapSourcePath(windowItem.id, field.path)}
                                      aria-label={expandedSourcePathSet.has(field.path) ? `Collapse ${field.path}` : `Expand ${field.path}`}
                                    >
                                      {expandedSourcePathSet.has(field.path) ? "−" : "+"}
                                    </button>
                                  ) : (
                                    <span className="mindmap-source-toggle-spacer" aria-hidden="true" />
                                  )}
                                  <button
                                    type="button"
                                    className="mindmap-source-chip"
                                    draggable
                                    onDragStart={(event) => {
                                      event.dataTransfer.effectAllowed = "copy";
                                      event.dataTransfer.setData("text/plain", field.path);
                                    }}
                                    title={field.path}
                                  >
                                    <strong>{field.label === "[]" ? "item" : field.label}</strong>
                                    <span>{schemaTypeLabel(field.definition)}</span>
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="mindmap-mapper-empty">No output schema fields available.</p>
                        )}
                      </div>
                      <div className="mindmap-mapper-table-shell">
                        <div className="mindmap-mapper-table-head">
                          <span>Input</span>
                          <span>Source</span>
                          <span>Constant</span>
                        </div>
                        {selectedEdgeTargetFields.length ? selectedEdgeTargetFields.map((field) => {
                          const explicitValue = selectedEdgeMapping.mapping[field.name];
                          const explicitSourceField = mappedSourceField(explicitValue, "");
                          const explicitConstantValue = mappedConstantValue(explicitValue);
                          const hasExplicitMapping = Boolean(explicitSourceField);
                          const hasConstant = hasMappedConstant(explicitValue);
                          const explicitSourceEntry = hasExplicitMapping
                            ? selectedEdgeSourceLookup.get(explicitSourceField) || null
                            : null;
                          const autoSourceEntry = !hasExplicitMapping && !hasConstant
                            ? selectedEdgeSourceLookup.get(field.name) || null
                            : null;
                          const missingExplicitSource = hasExplicitMapping && !explicitSourceEntry;
                          const selectValue = missingExplicitSource ? "__missing__" : hasExplicitMapping ? explicitSourceField : "";
                          const sourceStatus = hasConstant ? "Constant" : hasExplicitMapping ? "Mapped" : autoSourceEntry ? "Auto" : "Unset";
                          return (
                            <div className="mindmap-mapper-table-row" key={field.name}>
                              <div className="mindmap-mapper-table-cell mindmap-mapper-table-cell--field">
                                <strong>{field.name}</strong>
                                <span>{schemaTypeLabel(field.definition)}</span>
                                {field.required ? <em className="mindmap-mapper-required">Required</em> : null}
                              </div>
                              <div
                                className={missingExplicitSource ? "mindmap-mapper-table-cell mindmap-mapper-table-cell--source warning" : "mindmap-mapper-table-cell mindmap-mapper-table-cell--source"}
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={(event) => {
                                  event.preventDefault();
                                  const sourceField = event.dataTransfer.getData("text/plain").trim();
                                  setMindMapEdgeMappingField(windowItem.id, selectedEdge.id, field.name, sourceField);
                                }}
                              >
                                <select
                                  value={selectValue}
                                  onChange={(event) => setMindMapEdgeMappingField(windowItem.id, selectedEdge.id, field.name, event.target.value === "__missing__" ? "" : event.target.value)}
                                >
                                  {missingExplicitSource ? <option value="__missing__">Missing: {explicitSourceField}</option> : null}
                                  <option value="">{autoSourceEntry ? `Auto match: ${autoSourceEntry.path}` : "Choose source field"}</option>
                                  {selectedEdgeSourceOptions.map((option) => (
                                    <option key={option.path} value={option.path}>
                                      {`${"  ".repeat(option.depth)}${option.path} (${schemaTypeLabel(option.definition)})`}
                                    </option>
                                  ))}
                                </select>
                                <span className={hasExplicitMapping || missingExplicitSource ? "mindmap-mapper-mode" : "mindmap-mapper-mode mindmap-mapper-mode--auto"}>
                                  {sourceStatus}
                                </span>
                              </div>
                              <div className="mindmap-mapper-table-cell mindmap-mapper-table-cell--constant">
                                <input
                                  value={explicitConstantValue}
                                  placeholder="optional constant"
                                  onChange={(event) => setMindMapEdgeMappingConstant(windowItem.id, selectedEdge.id, field.name, event.target.value)}
                                />
                                <button
                                  type="button"
                                  className="mindmap-mapper-clear"
                                  onClick={() => clearMindMapEdgeMappingField(windowItem.id, selectedEdge.id, field.name)}
                                >
                                  Clear
                                </button>
                              </div>
                            </div>
                          );
                        }) : (
                          <p className="mindmap-mapper-empty">No destination input schema fields available.</p>
                        )}
                      </div>
                    </div>
                  ) : (
                    <label className="field">
                      <span>Raw JSON</span>
                      <textarea
                        value={selectedEdge.mappingText || "{}"}
                        onChange={(event) => updateMindMapEdge(windowItem.id, selectedEdge.id, "mappingText", event.target.value)}
                        placeholder={'{\n  "dest_field": "source_field"\n}'}
                      />
                    </label>
                  )}
                  <div className={`compatibility-pill ${selectedEdgeMeta?.status || "warning"}`}>
                    {selectedEdgeMeta?.label || "Connection"}
                  </div>
                  <p className="compatibility-copy">{selectedEdgeMeta?.reason || "Review the selected connection."}</p>
                  {selectedEdgeMapping.error ? <p className="form-error">{selectedEdgeMapping.error}</p> : null}
                  <button className="mindmap-ui-button mindmap-ui-button--danger" onClick={() => deleteMindMapEdge(windowItem.id, selectedEdge.id)}>
                    Delete Edge
                  </button>
                </div>
              ) : null}
            </aside>

            <div
              className="mindmap-surface"
            >
              <div
                className={map.showGrid === false ? "mindmap-canvas mindmap-canvas--grid-hidden" : "mindmap-canvas"}
                style={{ width: `${1280 * (windowItem.zoom || 1)}px`, height: `${720 * (windowItem.zoom || 1)}px` }}
                onClick={(event) => {
                  const clickedCanvasBackdrop = event.target === event.currentTarget
                    || (event.target instanceof Element && event.target.classList.contains("mindmap-links"));
                  if (clickedCanvasBackdrop) {
                    clearMindMapSelection(windowItem.id);
                  }
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const rect = event.currentTarget.getBoundingClientRect();
                  const x = ((event.clientX - rect.left) / rect.width) * 100;
                  const y = ((event.clientY - rect.top) / rect.height) * 100;
                  const droppedShape = normalizeMindMapShapeId(event.dataTransfer.getData("text/plain"));
                  const shapeId = MINDMAP_SHAPE_PRESETS.some((entry) => entry.id === droppedShape) ? droppedShape : "rounded";
                  addMindMapNode(windowItem.id, x, y, shapeId);
                }}
              >
                <svg className="mindmap-links" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <defs>
                    <marker id={`mindmap-arrow-${windowItem.id}-compatible`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
                      <path d="M 0 0 L 8 4 L 0 8 z" fill="#2563eb" />
                    </marker>
                    <marker id={`mindmap-arrow-${windowItem.id}-warning`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
                      <path d="M 0 0 L 8 4 L 0 8 z" fill="#dc2626" />
                    </marker>
                    <marker id={`mindmap-arrow-${windowItem.id}-pending`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
                      <path d="M 0 0 L 8 4 L 0 8 z" fill="#94a3b8" />
                    </marker>
                  </defs>
                  {map.edges.map((edge) => {
                    const fromNode = map.nodes.find((entry) => entry.id === edge.from);
                    const toNode = map.nodes.find((entry) => entry.id === edge.to);
                    if (!fromNode || !toNode) {
                      return null;
                    }
                    const meta = edgeCompatibility(map, edge);
                    return (
                      <g key={edge.id} className={`mindmap-link-group ${map.selectedEdgeId === edge.id ? "selected" : ""}`}>
                        <path
                          className={`mindmap-link ${meta.status}`}
                          d={connectionPath(fromNode, toNode, edge)}
                          markerEnd={`url(#mindmap-arrow-${windowItem.id}-${meta.status === "compatible" ? "compatible" : meta.status === "pending" ? "pending" : "warning"})`}
                          onClick={() => {
                            mindMapLinkRef.current = null;
                            updateMindMap(windowItem.id, (nextMap) => {
                            nextMap.selectedEdgeId = edge.id;
                            nextMap.selectedNodeId = "";
                            nextMap.linkDraftFrom = "";
                            nextMap.linkDraftAnchor = "";
                            nextMap.linkDraftX = null;
                            nextMap.linkDraftY = null;
                            });
                          }}
                        />
                      </g>
                    );
                  })}
                  {linkDraftPath ? (
                    <path
                      className="mindmap-link mindmap-link--draft pending"
                      d={linkDraftPath}
                      markerEnd={`url(#mindmap-arrow-${windowItem.id}-pending)`}
                    />
                  ) : null}
                </svg>
                {map.nodes.length === 0 ? (
                  <div className="mindmap-empty">
                    <strong>Drop a shape on the canvas.</strong>
                    <span>Use the left toolbar or the bottom controls to start building the diagram.</span>
                  </div>
                ) : map.nodes.map((node) => (
                  (() => {
                    const nodeClassName = [
                      "mindmap-node",
                      `mindmap-node--${node.type}`,
                      map.selectedNodeId === node.id ? "selected" : "",
                      isBranchMindMapNode(node) && !branchMindMapConnectionsComplete(map, node) ? "branch-incomplete" : "",
                    ].filter(Boolean).join(" ");
                    return (
                      <article
                        key={node.id}
                        className={nodeClassName}
                        style={{ left: `${node.x}%`, top: `${node.y}%`, ...mindMapNodeFootprintStyle(node) }}
                        onMouseDown={(event) => {
                          if (map.selectedNodeId === node.id) {
                            beginDrag(node.id, event);
                          }
                        }}
                        onMouseUp={(event) => {
                          const drag = mindMapDragRef.current?.windowId === windowItem.id ? mindMapDragRef.current : null;
                          const resize = mindMapResizeRef.current?.windowId === windowItem.id ? mindMapResizeRef.current : null;
                          mindMapDragRef.current = null;
                          mindMapResizeRef.current = null;
                          event.stopPropagation();
                          if (mindMapLinkRef.current?.windowId === windowItem.id) {
                            completeMindMapLink(windowItem.id, node.id);
                            return;
                          }
                          if (!drag?.dragging && !resize) {
                            selectMindMapNode(windowItem.id, node.id);
                          }
                        }}
                      >
                    {mindMapHandleDescriptors(node).map((handle) => renderConnectionHandle(node, handle))}
                    {map.selectedNodeId === node.id ? (
                      <button
                        type="button"
                        className="mindmap-node-resize"
                        aria-label={`Resize ${node.title}`}
                        onMouseDown={(event) => beginResize(node.id, event)}
                      />
                    ) : null}
                    <div className="mindmap-node-surface">
                      {isBranchMindMapNode(node) ? (
                        <svg className="mindmap-node-frame mindmap-node-frame--branch" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                          <polygon points="50,2 98,50 50,98 2,50" />
                        </svg>
                      ) : null}
                      <strong className="mindmap-node-title">{node.title}</strong>
                    </div>
                      </article>
                    );
                  })()
                ))}
              </div>
            </div>

            <div className="mindmap-bottom-left">
              <button className="mindmap-ui-button mindmap-ui-button--icon" onClick={() => setMindMapZoom(windowItem.id, (windowItem.zoom || 1) - 0.1)}>−</button>
              <button className="mindmap-ui-button mindmap-ui-button--compact" onClick={() => setMindMapZoom(windowItem.id, 1)}>
                {Math.round((windowItem.zoom || 1) * 100)}%
              </button>
              <button className="mindmap-ui-button mindmap-ui-button--icon" onClick={() => setMindMapZoom(windowItem.id, (windowItem.zoom || 1) + 0.1)}>+</button>
            </div>

            <div className="mindmap-bottom-center">
              <button className={`mindmap-tool-chip ${!selectedNode && !selectedEdge && !linkSourceNode ? "active" : ""}`} onClick={() => clearMindMapSelection(windowItem.id)}>
                <span>V</span>
                <strong>Select</strong>
              </button>
              <button className="mindmap-tool-chip" onClick={() => addMindMapNode(windowItem.id)}>
                <span>+</span>
                <strong>Shape</strong>
              </button>
              <button className={map.showGrid === false ? "mindmap-tool-chip" : "mindmap-tool-chip active"} onClick={() => toggleMindMapGrid(windowItem.id)}>
                <span>#</span>
                <strong>Grid</strong>
              </button>
              <button className="mindmap-tool-chip" onClick={() => setMindMapZoom(windowItem.id, 1)}>
                <span>100</span>
                <strong>Reset</strong>
              </button>
            </div>

            <div className="mindmap-bottom-right">
              <span className="mindmap-stat-chip">{map.nodes.length} shapes</span>
              <span className="mindmap-stat-chip">{map.edges.length} links</span>
              {selectedNode ? <span className="mindmap-stat-chip">{mindMapShapePreset(selectedNode.type).label}</span> : null}
              {selectedEdge ? <span className="mindmap-stat-chip">Connection</span> : null}
            </div>
          </div>
        </div>
      </section>
    );
  }

  function renderPaneConfigModal() {
    if (!state.paneConfig.open) {
      return null;
    }
    const located = findPaneLocation(state, state.paneConfig.windowId, state.paneConfig.paneId);
    if (!located) {
      return null;
    }
    const { windowItem, pane } = located;
    const browserCatalog = resolveBrowserCatalog(windowItem, state.preferences, state.globalPlazaStatus);
    const pulseOptions = collectCatalogPulses(browserCatalog);
    const filterText = String(deferredPaneFilterText || "").trim().toLowerCase();
    const filteredPulseOptions = filterText
      ? pulseOptions.filter((pulse) => `${pulse.pulse_name || ""}\n${pulse.plazaDescription || pulse.description || ""}`.toLowerCase().includes(filterText))
      : pulseOptions;
    const selectedPulse = findSelectedCatalogPulse(pulseOptions, pane);
    const compatiblePulserOptions = selectedPulse?.compatible_pulsers || [];
    const selectedPulser = findSelectedCompatiblePulser(selectedPulse, pane);
    const selectedPulseDescription = selectedPulse?.plazaDescription || selectedPulse?.description || "";
    const fieldOptions = pane.result !== null ? getFieldOptions(pane.result) : [];
    const previewValue = pane.result !== null ? getDisplayValue(pane) : null;
    const isDiagramPane = pane.type === "mind_map";
    const isDataPane = isDataPaneType(pane.type);
    const isOperatorPane = isOperatorPaneType(pane.type);
    const operatorState = isOperatorPane ? (pane.operatorState || createOperatorConsoleState(state.preferences)) : null;
    const currentSymbol = String(windowItem.browserDefaults?.symbol || "").trim().toUpperCase();
    const diagramReadiness = isDiagramPane
      ? mindMapRunReadiness(
          normalizeMindMapState(pane.mindMapState, state.preferences, state.dashboard),
          state.preferences.connectionPlazaUrl,
          browserCatalog,
        )
      : null;
    const paneStatusLabel = isOperatorPane
      ? (
        operatorState?.status === "loading"
          ? "Refreshing managed work..."
          : operatorState?.status === "error"
            ? (operatorState?.error || "Unable to load managed work.")
            : operatorState?.status === "ready"
              ? `${operatorState?.tickets?.length || 0} tickets · ${operatorState?.schedules?.length || 0} schedules`
              : "Configure a Boss URL to load managed work."
      )
      : pane.status === "loading"
        ? "Getting data..."
        : pane.status === "error"
          ? (pane.error || "Request failed.")
          : pane.status === "ready"
            ? (pane.lastRunAt ? `Updated ${pane.lastRunAt}` : "Data loaded.")
            : isDiagramPane
              ? (
                diagramReadiness?.canRun
                  ? (
                    diagramReadiness.executionWarnings?.length
                      ? `${diagramReadiness.executionWarnings.length} diagram node${diagramReadiness.executionWarnings.length === 1 ? "" : "s"} still need pulse or pulser setup.`
                      : (currentSymbol ? `Ready to run with symbol ${currentSymbol}.` : "Ready to run diagram input.")
                  )
                  : (diagramReadiness?.reason || "Connect a diagram path from Input to Output before running.")
              )
              : selectedPulse
                ? "Ready to fetch."
                : "Choose a pulse and pulser.";
    const paneStatusClass = isOperatorPane
      ? operatorState?.status === "error"
        ? "pane-config-status error"
        : operatorState?.status === "loading"
          ? "pane-config-status loading"
          : "pane-config-status"
      : pane.status === "error"
        ? "pane-config-status error"
        : pane.status === "loading"
          ? "pane-config-status loading"
          : "pane-config-status";
    const paneConfigPlazaUrl = normalizePlazaUrl(
      browserCatalog?.plazaUrl || browserCatalog?.plaza_url || windowItem.browserDefaults?.plazaUrl || state.preferences.connectionPlazaUrl || "",
    );
    const paneConfigPlazaStatusClass = browserCatalog?.connected
      ? "status-pill ready"
      : browserCatalog?.status === "loading"
        ? "status-pill loading"
        : "status-pill offline";
    const paneConfigPlazaStatusLabel = browserCatalog?.status === "loading"
      ? "Checking"
      : browserCatalog?.connected
        ? "Online"
        : "Offline";
    const paneConfigPlazaStatusDetail = browserCatalog?.error
      || `${browserCatalog?.pulserCount || 0} pulsers · ${browserCatalog?.pulseCount || 0} pulses`;
    const paneConfigPlazaBusy = browserCatalog?.status === "loading";

    return (
      <div className="modal-backdrop" onClick={cancelPaneConfig}>
        <div className="modal-shell pane-config-shell" onClick={(event) => event.stopPropagation()}>
          <div className="modal-grid pane-config-grid">
            <div className="pane-config-header wide">
              <input
                className="pane-config-title-input"
                value={pane.title}
                onChange={(event) => updatePaneField(windowItem.id, pane.id, "title", event.target.value)}
                placeholder="Pane Title"
              />
              <div className="pane-config-header-actions">
                <span className="pane-config-plaza-url" title={paneConfigPlazaUrl || "Plaza URL not set"}>
                  {paneConfigPlazaUrl || "No Plaza URL"}
                </span>
                <span className={paneConfigPlazaStatusClass} title={paneConfigPlazaStatusDetail}>
                  {paneConfigPlazaStatusLabel}
                </span>
                <button
                  className={paneConfigPlazaBusy ? "ghost-button pane-config-refresh-button active" : "ghost-button pane-config-refresh-button"}
                  onClick={() => refreshBrowserCatalog(windowItem.id)}
                  disabled={!paneConfigPlazaUrl || paneConfigPlazaBusy}
                >
                  {paneConfigPlazaBusy ? "Refreshing Plaza..." : "Refresh Plaza"}
                </button>
                <button className="ghost-button pane-config-cancel-button" onClick={cancelPaneConfig}>Cancel</button>
                <button className="accent-button pane-config-save-button" onClick={savePaneConfig}>Save</button>
              </div>
            </div>
            {isOperatorPane ? (
              <>
                <label className="field wide">
                  <span>Boss URL</span>
                  <input
                    value={operatorState?.bossUrl || ""}
                    onChange={(event) => updateOperatorPaneField(windowItem.id, pane.id, "bossUrl", event.target.value)}
                    placeholder="http://127.0.0.1:8170"
                  />
                </label>
                <label className="field">
                  <span>Manager Address</span>
                  <input
                    value={operatorState?.managerAddress || ""}
                    onChange={(event) => updateOperatorPaneField(windowItem.id, pane.id, "managerAddress", event.target.value)}
                    placeholder="Optional"
                  />
                </label>
                <label className="field">
                  <span>Manager Party</span>
                  <input
                    value={operatorState?.managerParty || ""}
                    onChange={(event) => updateOperatorPaneField(windowItem.id, pane.id, "managerParty", event.target.value)}
                    placeholder="Optional"
                  />
                </label>
                <div className="field wide field--pulse-description">
                  <span>Managed Work Scope</span>
                  <div className="pulse-description-card">
                    This pane monitors one BossPulser or teamwork boss endpoint. Assignments, results, and delivery lanes stay attached to the pane layout.
                  </div>
                </div>
                <div className="field field--get-data">
                  <span>&nbsp;</span>
                  <button
                    className="ghost-button pane-config-run-button"
                    onClick={() => refreshOperatorMonitor(windowItem.id, pane.id, { preserveSelection: true })}
                    disabled={operatorState?.status === "loading"}
                  >
                    {operatorState?.status === "loading" ? "Refreshing..." : "Refresh Managed Work"}
                  </button>
                </div>
                <div className="pane-config-status-row wide">
                  <div className={paneStatusClass}>{paneStatusLabel}</div>
                </div>
                <div className="connection-card wide">
                  <strong>Resolved Boss Endpoint</strong>
                  <span>{normalizeBossUrl(operatorState?.bossUrl || "") || "Boss URL not set"}</span>
                  <span>{operatorState?.managerAddress || operatorState?.managerParty ? `${operatorState?.managerParty || "Party"} · ${operatorState?.managerAddress || "Manager auto-select"}` : "Manager address not pinned"}</span>
                </div>
              </>
            ) : isDataPane ? (
              <>
                {isDiagramPane ? (
                  <div className="field wide field--pulse-description">
                    <span>Diagram Input</span>
                    <div className="pulse-description-card">
                      {currentSymbol
                        ? `Runs the diagram with symbol "${currentSymbol}" plus the JSON below as input.`
                        : "Runs the diagram with the JSON below as input. Set a browser symbol to include it automatically."}
                    </div>
                  </div>
                ) : (
                  <>
                    <label className="field field--find-pulse">
                      <span>Find Pulse</span>
                      <input
                        value={paneFilterText}
                        onChange={(event) => setPaneFilterText(event.target.value)}
                        placeholder="Filter name or description"
                      />
                    </label>
                    <label className="field field--pulse">
                      <span>Pulse</span>
                      <select value={selectedPulse?.key || ""} onChange={(event) => selectPanePulse(windowItem.id, pane.id, event.target.value)}>
                        <option value="">Choose pulse</option>
                        {filteredPulseOptions.map((pulse) => (
                          <option key={pulse.key} value={pulse.key}>
                            {(pulse.plazaDescription || pulse.description)
                              ? `${pulse.pulse_name || pulse.pulse_address} - ${(pulse.plazaDescription || pulse.description).slice(0, 96)}`
                              : pulse.pulse_name || pulse.pulse_address}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field field--pulser">
                      <span>Pulser</span>
                      <select
                        value={selectedPulser?.key || ""}
                        onChange={(event) => selectPanePulser(windowItem.id, pane.id, event.target.value)}
                        disabled={!selectedPulse}
                      >
                        <option value="">{selectedPulse ? "Auto" : "Choose pulse first"}</option>
                        {compatiblePulserOptions.map((pulser) => (
                          <option key={pulser.key || pulser.pulser_id || pulser.pulser_name} value={pulser.key || pulser.pulser_id || pulser.pulser_name}>
                            {formatCompatiblePulserOptionLabel(pulser)}
                          </option>
                        ))}
                      </select>
                    </label>
                    {selectedPulse ? (
                      <div className="field wide field--pulse-description">
                        <span>Pulse Description</span>
                        <div className="pulse-description-card">
                          {selectedPulseDescription || "No pulse description available."}
                        </div>
                      </div>
                    ) : null}
                  </>
                )}
                <label className="field field--format">
                  <span>Format</span>
                  <select value={pane.displayFormat} onChange={(event) => updatePaneField(windowItem.id, pane.id, "displayFormat", event.target.value)}>
                    {BROWSER_PANE_FORMATS.map((format) => <option key={format} value={format}>{format}</option>)}
                  </select>
                </label>
                {isDiagramPane ? (
                  <div className="field field--diagram-grid">
                    <span>Grid Lines</span>
                    <button
                      className={pane.mindMapState?.showGrid === false ? "ghost-button" : "ghost-button active"}
                      onClick={() => updatePaneMindMapState(windowItem.id, pane.id, (map) => {
                        map.showGrid = map.showGrid === false;
                      })}
                    >
                      {pane.mindMapState?.showGrid === false ? "Hidden" : "Shown"}
                    </button>
                  </div>
                ) : null}
                {pane.displayFormat === "chart" ? (
                  <label className="field field--chart-style">
                    <span>Chart Style</span>
                    <select value={pane.chartType} onChange={(event) => updatePaneField(windowItem.id, pane.id, "chartType", event.target.value)}>
                      {BROWSER_CHART_TYPES.map((chartType) => <option key={chartType} value={chartType}>{chartType}</option>)}
                    </select>
                  </label>
                ) : null}
                <div className="field field--get-data">
                  <span>&nbsp;</span>
                  <button
                    className="ghost-button pane-config-run-button"
                    onClick={() => runBrowserPane(windowItem.id, pane.id)}
                    disabled={pane.status === "loading"}
                  >
                    {pane.status === "loading" ? "Getting data..." : "Get Data"}
                  </button>
                </div>
                <div className="pane-config-status-row wide">
                  <div className={paneStatusClass}>{paneStatusLabel}</div>
                </div>
                <details
                  className="params-disclosure wide"
                  open={Boolean(pane.paramsExpanded)}
                  onToggle={(event) => updatePaneField(windowItem.id, pane.id, "paramsExpanded", event.currentTarget.open)}
                >
                  <summary>{isDiagramPane ? "Diagram Input JSON" : "Pane Params JSON"}</summary>
                  <textarea value={pane.paramsText} onChange={(event) => updatePaneField(windowItem.id, pane.id, "paramsText", event.target.value)} />
                </details>
                <div className="field field--display-fields">
                  <span>Display Fields</span>
                  <div className="field-chip-list">
                    {fieldOptions.length ? fieldOptions.map((option) => (
                      <button
                        key={option.path}
                        className={pane.fieldPaths.includes(option.path) ? "field-chip active" : "field-chip"}
                        onClick={() => togglePaneFieldPath(windowItem.id, pane.id, option.path)}
                      >
                        {option.label}
                      </button>
                    )) : <div className="pane-empty small">Run the pane once to choose fields from the live response.</div>}
                  </div>
                </div>
                <div className="preview-card field--preview">
                  <div className="subhead">
                    <strong>Preview</strong>
                  </div>
                  {previewValue !== null ? <ValueRenderer key={`${pane.displayFormat}:${pane.chartType}`} value={previewValue} format={pane.displayFormat} chartType={pane.chartType} /> : <div className="pane-empty small">No preview yet.</div>}
                </div>
              </>
            ) : (
              <div className="pane-empty wide">Mind map panes are configured through the linked full editor.</div>
            )}
          </div>
        </div>
      </div>
    );
  }

  function renderSnapshotModal() {
    if (!state.snapshotDialog.open) {
      return null;
    }
    const snapshotKind = state.snapshotDialog.kind === "mind_map" ? "mind_map" : "browser";
    const snapshots = snapshotKind === "mind_map"
      ? getMindMapSnapshots()
      : getBrowserSnapshots(state.snapshotDialog.windowId);
    const snapshotLabel = snapshotKind === "mind_map" ? "Diagram Layout" : "Pane Layout";
    const snapshotActionLabel = snapshotKind === "mind_map" ? "Diagram" : "Layout";
    const storageTarget = snapshotStorageTarget(snapshotKind, state.preferences, state, state.snapshotDialog.windowId);
    return (
      <div className="modal-backdrop" onClick={closeSnapshotDialog}>
        <div className="modal-shell narrow" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <p className="eyebrow">{snapshotLabel}</p>
              <h3>{state.snapshotDialog.mode === "save" ? `Save ${snapshotLabel}` : `Load ${snapshotLabel}`}</h3>
            </div>
            <button className="ghost-button" onClick={closeSnapshotDialog}>Close</button>
          </div>
          <div className="connection-card workspace-dialog-storage-card">
            <strong>Current Save Location</strong>
            <span>{storageTarget.label}</span>
            <span className="workspace-dialog-storage-path">{storageTarget.detail}</span>
          </div>
          {state.snapshotDialog.mode === "save" ? (
            <label className="field">
              <span>{snapshotActionLabel} Name</span>
              <input value={state.snapshotDialog.name} onChange={(event) => updateState((next) => {
                next.snapshotDialog.name = event.target.value;
                next.snapshotDialog.error = "";
              })} />
            </label>
          ) : (
            <div className="snapshot-list">
              {snapshots.length ? snapshots.map((snapshot) => (
                <button
                  key={snapshot.id}
                  className={state.snapshotDialog.selectedSnapshotId === snapshot.id ? "snapshot-row active" : "snapshot-row"}
                  onClick={() => updateState((next) => {
                    next.snapshotDialog.selectedSnapshotId = snapshot.id;
                    next.snapshotDialog.error = "";
                  })}
                >
                  <strong>{snapshot.name}</strong>
                  <span>{new Date(snapshot.savedAt).toLocaleString()}</span>
                </button>
              )) : <div className="pane-empty small">{snapshotKind === "mind_map" ? "No saved diagrams yet." : "No saved layouts yet."}</div>}
            </div>
          )}
          {state.snapshotDialog.error ? <div className="form-error">{state.snapshotDialog.error}</div> : null}
          <div className="modal-actions">
            <button className="ghost-button" onClick={closeSnapshotDialog}>Cancel</button>
            <button className="accent-button" onClick={submitSnapshotDialog}>
              {state.snapshotDialog.mode === "save" ? `Save ${snapshotActionLabel}` : `Load ${snapshotActionLabel}`}
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderPhemaDialog() {
    if (!phemaDialog.open) {
      return null;
    }
    const busy = phemaDialog.loading || phemaDialog.saving;
    const storageTarget = mapPhemaStorageTarget(state.preferences, state);
    return (
      <div className="modal-backdrop" onClick={busy ? undefined : closePhemaDialog}>
        <div className="modal-shell narrow" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <p className="eyebrow">MapPhemar</p>
              <h3>{phemaDialog.mode === "save" ? "Save Diagram as Phema" : "Load Diagram Phema"}</h3>
            </div>
            <button className="ghost-button" onClick={closePhemaDialog} disabled={busy}>Close</button>
          </div>
          <div className="connection-card workspace-dialog-storage-card">
            <strong>{phemaDialog.mode === "save" ? "Current Save Location" : "Current Library Location"}</strong>
            <span>{storageTarget.label}</span>
            <span className="workspace-dialog-storage-path">{storageTarget.detail}</span>
          </div>
          {phemaDialog.mode === "save" ? (
            <label className="field">
              <span>Phema Name</span>
              <input
                value={phemaDialog.name}
                onChange={(event) => setPhemaDialog((current) => ({ ...current, name: event.target.value, error: "" }))}
                disabled={busy}
              />
            </label>
          ) : (
            <>
              <label className="field">
                <span>Search Phemas</span>
                <input
                  value={phemaDialog.query}
                  placeholder="Find a saved diagram phema"
                  onChange={(event) => refreshPhemaDialog(event.target.value)}
                  disabled={busy}
                />
              </label>
              <div className="snapshot-list snapshot-list--file-box">
                {phemaDialog.phemas.length ? phemaDialog.phemas.map((phema) => {
                  const phemaId = String(phema.phema_id || phema.id || "");
                  return (
                    <button
                      key={phemaId}
                      className={phemaDialog.selectedPhemaId === phemaId ? "snapshot-row snapshot-row--file-line active" : "snapshot-row snapshot-row--file-line"}
                      onClick={() => setPhemaDialog((current) => ({ ...current, selectedPhemaId: phemaId, error: "" }))}
                      onDoubleClick={() => { void loadPhemaDialogSelection(phemaDialog.windowId, phemaId); }}
                      disabled={busy}
                      title={phemaDialogRowTitle(phema)}
                    >
                      <strong>{phemaDialogRowLabel(phema)}</strong>
                      <span>{phemaDialogRowTimestamp(phema)}</span>
                    </button>
                  );
                }) : <div className="pane-empty small">{phemaDialog.loading ? "Loading saved Phemas..." : "No saved Phemas yet."}</div>}
              </div>
            </>
          )}
          {phemaDialog.error ? <div className="form-error">{phemaDialog.error}</div> : null}
          <div className="modal-actions">
            <button className="ghost-button" onClick={closePhemaDialog} disabled={busy}>Cancel</button>
            <button className="accent-button" onClick={submitPhemaDialog} disabled={busy}>
              {phemaDialog.saving ? "Saving Phema..." : phemaDialog.loading && phemaDialog.mode === "load" ? "Loading..." : phemaDialog.mode === "save" ? "Save Phema" : "Load Phema"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderWorkspaceDialog() {
    if (!state.workspaceDialog.open) {
      return null;
    }
    const layouts = getWorkspaceLayouts();
    const storageTarget = workspaceLayoutStorageTarget(state.preferences, state);
    return (
      <div className="modal-backdrop" onClick={closeWorkspaceDialog}>
        <div className="modal-shell narrow" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <h3>{state.workspaceDialog.mode === "save" ? "Save Workspace" : "Load Workspace"}</h3>
            </div>
            <button className="ghost-button" onClick={closeWorkspaceDialog}>Close</button>
          </div>
          <div className="connection-card workspace-dialog-storage-card">
            <strong>Current Save Location</strong>
            <span>{storageTarget.label}</span>
            <span className="workspace-dialog-storage-path">{storageTarget.detail}</span>
          </div>
          {state.workspaceDialog.mode === "save" ? (
            <label className="field">
              <span>Workspace Name</span>
              <input value={state.workspaceDialog.name} onChange={(event) => updateState((next) => {
                next.workspaceDialog.name = event.target.value;
                next.workspaceDialog.error = "";
              })} />
            </label>
          ) : (
            <div className="snapshot-list">
              {layouts.length ? layouts.map((snapshot) => (
                <button
                  key={snapshot.id}
                  className={state.workspaceDialog.selectedLayoutId === snapshot.id ? "snapshot-row active" : "snapshot-row"}
                  onClick={() => updateState((next) => {
                    next.workspaceDialog.selectedLayoutId = snapshot.id;
                    next.workspaceDialog.error = "";
                  })}
                >
                  <strong>{snapshot.name}</strong>
                  <span>{new Date(snapshot.savedAt).toLocaleString()}</span>
                </button>
              )) : <div className="pane-empty small">No saved workspaces yet.</div>}
            </div>
          )}
          {state.workspaceDialog.error ? <div className="form-error">{state.workspaceDialog.error}</div> : null}
          <div className="modal-actions">
            <button className="ghost-button" onClick={closeWorkspaceDialog}>Cancel</button>
            <button className="accent-button" onClick={submitWorkspaceDialog}>
              {state.workspaceDialog.mode === "save" ? "Save Workspace" : "Load Workspace"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderPrintDialog() {
    if (!state.printDialog.open) {
      return null;
    }
    const targetWorkspace = printWorkspace;
    const workspaceWindows = printableWindowList(targetWorkspace);
    const totalPaneCount = workspaceWindows.reduce((count, windowItem) => (
      count + (windowItem.type === "browser" ? printablePaneList(windowItem).length : 1)
    ), 0);
    return (
      <div className="modal-backdrop print-dialog-backdrop" onClick={state.printDialog.printing ? undefined : closePrintDialog}>
        <div className="modal-shell print-dialog-shell" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <p className="eyebrow">Workspace File</p>
              <h3>Print Workspace</h3>
            </div>
            <button className="ghost-button" onClick={closePrintDialog} disabled={state.printDialog.printing}>Close</button>
          </div>
          <div className="print-dialog-layout">
            <aside className="print-dialog-sidebar">
              <div className="connection-card wide">
                <strong>{targetWorkspace?.name || "Workspace"}</strong>
                <span>{`${workspaceWindows.length} window${workspaceWindows.length === 1 ? "" : "s"}`}</span>
                <span>{`${totalPaneCount} pane${totalPaneCount === 1 ? "" : "s"} ready for preview and print`}</span>
              </div>
              <div className="connection-card wide">
                <strong>Output</strong>
                <span>Workspace content only</span>
                <span>Frames, resize handles, toolbar controls, and action buttons stay out of the preview and the printed page.</span>
              </div>
              <div className="connection-card wide print-preview-note">
                <strong>Preview</strong>
                <span>Use the browser print dialog after pressing Print to choose your paper size and destination.</span>
              </div>
            </aside>
            <div className="print-preview-frame">
              {renderPrintableWorkspace(targetWorkspace)}
            </div>
          </div>
          <div className="modal-actions">
            <button className="ghost-button" onClick={closePrintDialog} disabled={state.printDialog.printing}>Cancel</button>
            <button className="accent-button" onClick={submitPrintDialog} disabled={!targetWorkspace || state.printDialog.printing}>
              {state.printDialog.printing ? "Opening Print..." : "Print"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderDiagramRunDialog() {
    if (!state.diagramRunDialog.open || !state.diagramRunDialog.windowId) {
      return null;
    }
    const source = resolveMindMapSource(state, state.diagramRunDialog.windowId);
    if (!source) {
      return null;
    }
    const readiness = mindMapRunReadiness(source.mapState, state.preferences.connectionPlazaUrl, source.catalog);
    const stepCount = state.diagramRunDialog.steps.length;
    const diagramRunBusy = state.diagramRunDialog.status === "loading";
    return (
      <div className="modal-backdrop" onClick={diagramRunBusy ? undefined : closeDiagramRunDialog}>
        <div className="modal-shell diagram-run-shell" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <p className="eyebrow">Diagram Test Run</p>
              <h3>{source.windowLocation.windowItem.title || "Diagram"}</h3>
            </div>
            <button className="ghost-button" onClick={closeDiagramRunDialog} disabled={diagramRunBusy}>Close</button>
          </div>
          <div className="diagram-run-grid">
            <div className="diagram-run-panel">
              <div className="subhead">
                <strong>Initial Input</strong>
                <span>{readiness.startNode ? `Seeded from ${readiness.startNode.title}` : "Connect Input to a shape."}</span>
              </div>
              <p className="compatibility-copy">
                {readiness.startNode
                  ? `This payload enters through Input and feeds ${readiness.startNode.title} first.`
                  : "This payload is unavailable until Input is connected."}
              </p>
              {readiness.executionWarnings?.length ? (
                <p className="compatibility-copy">
                  {`${readiness.executionWarnings.length} node${readiness.executionWarnings.length === 1 ? "" : "s"} still need pulse or pulser setup. The run will stop on the first incomplete node.`}
                </p>
              ) : null}
              <label className="field">
                <span>Payload JSON</span>
                <textarea
                  className="diagram-run-input"
                  value={state.diagramRunDialog.inputText}
                  onChange={(event) => updateDiagramRunInput(event.target.value)}
                  placeholder={'{\n  "field_name": "value"\n}'}
                  disabled={state.diagramRunDialog.status === "loading"}
                />
              </label>
              {state.diagramRunDialog.inputError ? <div className="form-error">{state.diagramRunDialog.inputError}</div> : null}
              {!readiness.canRun ? <div className="form-error">{readiness.reason}</div> : null}
            </div>
            <div className="diagram-run-panel">
              <div className="subhead">
                <strong>Run Trace</strong>
                <span>{stepCount ? `${stepCount} step${stepCount === 1 ? "" : "s"} captured` : "No steps yet"}</span>
              </div>
              <div className="diagram-run-meta">
                <span>Status: {state.diagramRunDialog.status}</span>
                {state.diagramRunDialog.startedAt ? <span>Started: {state.diagramRunDialog.startedAt}</span> : null}
                {state.diagramRunDialog.finishedAt ? <span>Finished: {state.diagramRunDialog.finishedAt}</span> : null}
              </div>
              {state.diagramRunDialog.steps.length ? (
                <div className="diagram-run-step-list">
                  {state.diagramRunDialog.steps.map((step, index) => (
                    <article key={`${step.nodeId}-${index}`} className={step.status === "error" ? "diagram-run-step diagram-run-step--error" : "diagram-run-step"}>
                      <div className="diagram-run-step-head">
                        <div>
                          <strong>{step.title}</strong>
                          <span>
                            {step.kind === "node"
                              ? formatPulseExecutionLabel(step.pulseName, step.pulserName, step.pulserActive ?? null)
                              : step.kind === "branch"
                                ? step.selectedRoute
                                  ? `Branch · ${branchMindMapRouteLabel(step.selectedRoute)}`
                                  : "Branch"
                                : step.kind}
                          </span>
                        </div>
                        <span className="diagram-run-step-status">{step.status}</span>
                      </div>
                      <div className="diagram-run-step-body">
                        <div className="diagram-run-step-column">
                          <strong>Input</strong>
                          <pre className="value-pre">{JSON.stringify(step.input ?? {}, null, 2)}</pre>
                        </div>
                        <div className="diagram-run-step-column">
                          <strong>{step.kind === "output" ? "Received" : "Output"}</strong>
                          <pre className="value-pre">{JSON.stringify(step.output ?? null, null, 2)}</pre>
                        </div>
                      </div>
                      {step.kind === "branch" && step.conditionExpression ? (
                        <p className="compatibility-copy">{`Condition: ${step.conditionExpression}`}</p>
                      ) : null}
                      {step.error ? <div className="form-error">{step.error}</div> : null}
                    </article>
                  ))}
                </div>
              ) : (
                <div className="pane-empty small">Run the diagram once to inspect each node result through Output.</div>
              )}
            </div>
          </div>
          {state.diagramRunDialog.error ? <div className="form-error">{state.diagramRunDialog.error}</div> : null}
          <div className="modal-actions">
            <button className="ghost-button" onClick={closeDiagramRunDialog} disabled={diagramRunBusy}>Cancel</button>
            <button
              className="accent-button"
              onClick={() => runMindMapDiagram(state.diagramRunDialog.windowId)}
              disabled={!readiness.canRun || diagramRunBusy}
            >
              {diagramRunBusy ? "Running Diagram..." : "Run Diagram"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  function renderSettingsModal() {
    if (!state.settingsOpen) {
      return null;
    }
    const visibleSettingsTabs = IS_MAP_PHEMAR_MODE
      ? SETTINGS_TABS.filter((tab) => tab.id === "storage")
      : SETTINGS_TABS;
    const selectedSettingsTab = visibleSettingsTabs.find((entry) => entry.id === state.settingsTab)?.id || visibleSettingsTabs[0]?.id || "storage";
    const selectedLlm = state.preferences.llmConfigs.find((entry) => entry.id === state.settingsLlmSelectedId)
      || state.preferences.llmConfigs[0]
      || null;
    const storagePulsers = availableSystemPulsers(state);
    const selectedStoragePulser = selectedSystemPulser(state.preferences, storagePulsers);
    const mapPhemaStorageInfo = mapPhemaStorageTarget(state.preferences, state);
    const configuredStorageSummary = formatStorageTargetSummary(defaultSaveStorageTarget(state.preferences, state));
    const usingSystemPulser = normalizeFileSaveBackend(state.preferences.fileSaveBackend) === "system_pulser";
    const currentBucketName = String(state.preferences.fileSaveBucketName || "").trim();
    const plazaAccess = state.plazaAccess || createDefaultPlazaAccessState(state.preferences.connectionPlazaUrl);
    const plazaAccessSession = currentPlazaAccessSession(state);
    const plazaAccessUser = plazaAccess.user;
    const plazaAccessKeys = Array.isArray(plazaAccess.keys) ? plazaAccess.keys : [];
    const storageBucketOptions = sortStorageBucketRows([
      ...(currentBucketName && !storageBuckets.some((entry) => String(entry?.bucket_name || "").trim() === currentBucketName)
        ? [{ bucket_name: currentBucketName, visibility: "current" }]
        : []),
      ...storageBuckets,
    ]);
    const listedStorageBucketCount = storageBuckets.length;
    const canCreateStorageBucket = Boolean(selectedStoragePulser && fileStoragePulserCreateBucketPulse(selectedStoragePulser));
    return (
      <div className="modal-backdrop" onClick={() => updateState((next) => { next.settingsOpen = false; })}>
        <div className="settings-shell" onClick={(event) => event.stopPropagation()}>
          <div className="settings-sidebar">
            <div className="identity-card">
              <strong>{state.preferences.profileDisplayName}</strong>
              <span>{state.preferences.profileEmail}</span>
              <p>{state.preferences.profileDesk}</p>
            </div>
            <div className="settings-tabs">
              {visibleSettingsTabs.map((tab) => (
                <button key={tab.id} className={selectedSettingsTab === tab.id ? "settings-tab active" : "settings-tab"} onClick={() => updateState((next) => { next.settingsTab = tab.id; })}>
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <div className="settings-content">
            <div className="modal-head">
              <div>
                <p className="eyebrow">Preferences</p>
                <h3>{visibleSettingsTabs.find((entry) => entry.id === selectedSettingsTab)?.label}</h3>
              </div>
              <button className="ghost-button" onClick={() => updateState((next) => { next.settingsOpen = false; })}>Close</button>
            </div>
            {selectedSettingsTab === "profile" ? (
              <div className="settings-grid">
                <label className="field"><span>Display Name</span><input value={state.preferences.profileDisplayName} onChange={(event) => updateState((next) => { next.preferences.profileDisplayName = event.target.value; })} /></label>
                <label className="field"><span>Email</span><input value={state.preferences.profileEmail} onChange={(event) => updateState((next) => { next.preferences.profileEmail = event.target.value; })} /></label>
                <label className="field"><span>Desk</span><input value={state.preferences.profileDesk} onChange={(event) => updateState((next) => { next.preferences.profileDesk = event.target.value; })} /></label>
                <label className="field"><span>Timezone</span><input value={state.preferences.profileTimezone} onChange={(event) => updateState((next) => { next.preferences.profileTimezone = event.target.value; })} /></label>
                <div className="field wide">
                  <span>Theme</span>
                  <div className="theme-row">
                    {THEME_OPTIONS.map((theme) => (
                      <button key={theme.id} className={state.preferences.theme === theme.id ? "theme-chip active" : "theme-chip"} onClick={() => updateState((next) => { next.preferences.theme = theme.id; })}>{theme.label}</button>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
            {selectedSettingsTab === "api_keys" ? (
              <div className="settings-grid">
                {["apiKeyOpenAI", "apiKeyFinnhub", "apiKeyAlphaVantage", "apiKeyBroker"].map((field) => (
                  <label key={field} className="field">
                    <span>{field.replace("apiKey", "").replace("AlphaVantage", "Alpha Vantage")}</span>
                    <input type="password" value={state.preferences[field]} onChange={(event) => updateState((next) => { next.preferences[field] = event.target.value; })} />
                  </label>
                ))}
              </div>
            ) : null}
            {selectedSettingsTab === "plaza_access" ? (
              <div className="settings-grid">
                <div className="connection-card wide">
                  <strong>
                    {plazaAccessSession
                      ? "Plaza Session Active"
                      : plazaAccess.configStatus === "loading"
                        ? "Checking Plaza Access..."
                        : plazaAccess.config?.auth_enabled
                          ? "Plaza Ready"
                          : "Plaza Access Unavailable"}
                  </strong>
                  <span>{normalizePlazaUrl(state.preferences.connectionPlazaUrl) || "Set the Plaza URL in Connection settings first."}</span>
                  <span>
                    {plazaAccessSession
                      ? `${plazaAccessUser?.display_name || plazaAccessUser?.username || plazaAccessUser?.email || "Signed in"} · ${plazaAccessUser?.role || "user"}`
                      : plazaAccess.configError
                        || (plazaAccess.config?.auth_enabled
                          ? "Create a Plaza account or sign in to register owner keys for this Personal Agent."
                          : "This Plaza has not enabled UI authentication yet.")}
                  </span>
                  <div className="theme-row">
                    <button className="ghost-button" onClick={() => void refreshPlazaAccessConfig()}>
                      {plazaAccess.configStatus === "loading" ? "Refreshing Access..." : "Refresh Access"}
                    </button>
                    {plazaAccessSession ? (
                      <button className="ghost-button" onClick={() => void refreshPlazaAccessKeys()}>
                        {plazaAccess.keysStatus === "loading" ? "Refreshing Keys..." : "Refresh Keys"}
                      </button>
                    ) : null}
                    {plazaAccessSession ? (
                      <button className="ghost-button" onClick={() => void signOutPlazaAccess()}>
                        Sign Out
                      </button>
                    ) : null}
                  </div>
                </div>

                {!plazaAccessSession ? (
                  <>
                    <div className="field wide">
                      <span>Access Mode</span>
                      <div className="theme-row">
                        <button
                          className={plazaAccess.authMode === "signin" ? "theme-chip active" : "theme-chip"}
                          onClick={() => updateState((next) => {
                            next.plazaAccess.authMode = "signin";
                            next.plazaAccess.authMessage = "";
                          })}
                        >
                          Sign In
                        </button>
                        <button
                          className={plazaAccess.authMode === "signup" ? "theme-chip active" : "theme-chip"}
                          onClick={() => updateState((next) => {
                            next.plazaAccess.authMode = "signup";
                            next.plazaAccess.authMessage = "";
                          })}
                        >
                          Create Account
                        </button>
                      </div>
                    </div>
                    <label className="field">
                      <span>Username or Email</span>
                      <input
                        value={plazaAccess.identifier}
                        onChange={(event) => updateState((next) => { next.plazaAccess.identifier = event.target.value; })}
                      />
                    </label>
                    <label className="field">
                      <span>Password</span>
                      <input
                        type="password"
                        value={plazaAccess.password}
                        onChange={(event) => updateState((next) => { next.plazaAccess.password = event.target.value; })}
                      />
                    </label>
                    {plazaAccess.authMode === "signup" ? (
                      <label className="field wide">
                        <span>Display Name</span>
                        <input
                          value={plazaAccess.displayName}
                          onChange={(event) => updateState((next) => { next.plazaAccess.displayName = event.target.value; })}
                        />
                      </label>
                    ) : null}
                    <div className="field wide">
                      <span>Connect</span>
                      <button
                        className="accent-button"
                        onClick={() => void submitPlazaAccessAuth()}
                        disabled={plazaAccess.authBusy || !normalizePlazaUrl(state.preferences.connectionPlazaUrl)}
                      >
                        {plazaAccess.authBusy
                          ? (plazaAccess.authMode === "signup" ? "Creating Account..." : "Signing In...")
                          : (plazaAccess.authMode === "signup" ? "Create Plaza Account" : "Sign In to Plaza")}
                      </button>
                    </div>
                    {plazaAccess.authMessage ? (
                      <div className="connection-card wide">
                        <strong>Access Status</strong>
                        <span>{plazaAccess.authMessage}</span>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <>
                    <div className="connection-card">
                      <strong>{plazaAccessUser?.display_name || plazaAccessUser?.username || plazaAccessUser?.email || "Plaza User"}</strong>
                      <span>{plazaAccessUser?.email || "No email available"}</span>
                      <span>{`${plazaAccessUser?.role || "user"} · ${plazaAccessUser?.auth_provider || "password"}`}</span>
                    </div>
                    <div className="connection-card">
                      <strong>Owner Key Library</strong>
                      <span>{plazaAccess.keysStatus === "loading" ? "Refreshing Plaza owner keys..." : `${plazaAccessKeys.length} key${plazaAccessKeys.length === 1 ? "" : "s"} available on this Plaza.`}</span>
                      <span>Use these keys to register Personal Agent-launched runtimes under your Plaza account.</span>
                    </div>
                    <label className="field wide">
                      <span>Create Owner Key</span>
                      <input
                        value={plazaAccess.keyDraftName}
                        placeholder="Personal agent launcher"
                        onChange={(event) => updateState((next) => { next.plazaAccess.keyDraftName = event.target.value; })}
                      />
                    </label>
                    <div className="field">
                      <span>Create</span>
                      <button
                        className="accent-button"
                        onClick={() => void createPlazaOwnerKey()}
                        disabled={plazaAccess.keyBusy}
                      >
                        {plazaAccess.keyBusy ? "Creating Key..." : "Create Owner Key"}
                      </button>
                    </div>
                    {plazaAccess.keyMessage ? (
                      <div className="connection-card wide">
                        <strong>Key Status</strong>
                        <span>{plazaAccess.keyMessage}</span>
                      </div>
                    ) : null}
                    {plazaAccess.keyReveal?.secret ? (
                      <div className="connection-card wide">
                        <strong>{plazaAccess.keyReveal.name || "Plaza owner key ready"}</strong>
                        <span>Plaza only shows the full secret when you create or regenerate a key.</span>
                        <pre className="value-pre">{buildPlazaOwnerKeySnippet(state.preferences.connectionPlazaUrl, plazaAccess.keyReveal.id, plazaAccess.keyReveal.secret)}</pre>
                        <div className="theme-row">
                          <button className="ghost-button" onClick={() => void copyPlazaOwnerKeySecret(plazaAccess.keyReveal.secret)}>
                            Copy Secret
                          </button>
                          <button className="ghost-button" onClick={() => void copyPlazaOwnerKeySnippet(plazaAccess.keyReveal.id, "", false)}>
                            Copy Config JSON
                          </button>
                          <button className="ghost-button" onClick={() => void copyPlazaOwnerKeySnippet(plazaAccess.keyReveal.id, plazaAccess.keyReveal.secret, true)}>
                            Copy Runtime JSON
                          </button>
                          <button className="ghost-button" onClick={() => updateState((next) => { next.plazaAccess.keyReveal = null; })}>
                            Dismiss
                          </button>
                        </div>
                      </div>
                    ) : null}
                    <div className="connection-card wide">
                      <strong>Trusted Plaza Template</strong>
                      <span>Personal Agent uses the same trusted-Plaza metadata as the Plaza UI for launched runtimes.</span>
                      <pre className="value-pre">{buildPlazaOwnerKeySnippet(state.preferences.connectionPlazaUrl, plazaAccessKeys[0]?.id || "saved-key-id")}</pre>
                    </div>
                    <div className="connection-card wide">
                      <strong>Saved Keys</strong>
                      {plazaAccessKeys.length ? (
                        <div className="diagram-run-step-list">
                          {plazaAccessKeys.map((key) => {
                            const pending = plazaAccess.pendingKeyId === key.id;
                            const isDisabled = String(key.status || "").trim().toLowerCase() === "disabled";
                            const revealSecret = plazaAccess.keyReveal?.id === key.id ? plazaAccess.keyReveal.secret : "";
                            return (
                              <article key={key.id || key.name} className="diagram-run-step">
                                <div className="diagram-run-step-head">
                                  <div>
                                    <strong>{key.name || "Unnamed owner key"}</strong>
                                    <span>{key.id || "Key id unavailable"}</span>
                                  </div>
                                  <span className={statusPillClass(key.status || "active")}>{labelizeStatus(key.status || "active")}</span>
                                </div>
                                <div className="diagram-run-meta">
                                  <span>{`Preview: ${key.secret_preview || "hidden"}`}</span>
                                  <span>{`Last used: ${formatTimestamp(key.last_used_at || "never")}`}</span>
                                  <span>{`Updated: ${formatTimestamp(key.updated_at || key.created_at)}`}</span>
                                </div>
                                <pre className="value-pre">{buildPlazaOwnerKeySnippet(state.preferences.connectionPlazaUrl, key.id, revealSecret)}</pre>
                                <div className="theme-row">
                                  <button className="ghost-button" onClick={() => void copyPlazaOwnerKeySnippet(key.id, "", false)}>
                                    Copy Config
                                  </button>
                                  <button className="ghost-button" onClick={() => void copyPlazaOwnerKeySnippet(key.id, revealSecret, true)}>
                                    Copy Runtime JSON
                                  </button>
                                  {!isDisabled ? (
                                    <button
                                      className="ghost-button"
                                      onClick={() => {
                                        if (window.confirm(`Regenerate Plaza owner key "${key.name || key.id}"? Existing runtimes using the old secret will stop claiming your account until updated.`)) {
                                          void regeneratePlazaOwnerKey(key.id);
                                        }
                                      }}
                                      disabled={pending}
                                    >
                                      {pending && plazaAccess.pendingKeyAction === "regenerate" ? "Regenerating..." : "Regenerate"}
                                    </button>
                                  ) : null}
                                  <button
                                    className="ghost-button"
                                    onClick={() => {
                                      if (!isDisabled && !window.confirm(`Disable Plaza owner key "${key.name || key.id}"? You can re-enable it later.`)) {
                                        return;
                                      }
                                      void setPlazaOwnerKeyStatus(key.id, isDisabled ? "active" : "disabled");
                                    }}
                                    disabled={pending}
                                  >
                                    {pending && (plazaAccess.pendingKeyAction === "disable" || plazaAccess.pendingKeyAction === "enable")
                                      ? (isDisabled ? "Enabling..." : "Disabling...")
                                      : (isDisabled ? "Enable" : "Disable")}
                                  </button>
                                  <button
                                    className="ghost-button"
                                    onClick={() => {
                                      if (window.confirm(`Delete Plaza owner key "${key.name || key.id}"? It will no longer claim ownership for saved launches.`)) {
                                        void deletePlazaOwnerKey(key.id);
                                      }
                                    }}
                                    disabled={pending}
                                  >
                                    {pending && plazaAccess.pendingKeyAction === "delete" ? "Deleting..." : "Delete"}
                                  </button>
                                </div>
                              </article>
                            );
                          })}
                        </div>
                      ) : (
                        <span>{plazaAccess.keysError || "No Plaza owner keys yet. Create one above to register trusted Personal Agent launches."}</span>
                      )}
                    </div>
                  </>
                )}
              </div>
            ) : null}
            {selectedSettingsTab === "connection" ? (
              <div className="settings-grid">
                <label className="field"><span>Connection Mode</span><input value={state.preferences.connectionMode} onChange={(event) => updateState((next) => { next.preferences.connectionMode = event.target.value; })} /></label>
                <label className="field"><span>Host</span><input value={state.preferences.connectionHost} onChange={(event) => updateState((next) => { next.preferences.connectionHost = event.target.value; })} /></label>
                <label className="field wide"><span>Plaza URL</span><input value={state.preferences.connectionPlazaUrl} onChange={(event) => updateState((next) => { next.preferences.connectionPlazaUrl = event.target.value; })} /></label>
                <label className="field wide"><span>Default Boss URL</span><input value={state.preferences.operatorBossUrl} onChange={(event) => updateState((next) => { next.preferences.operatorBossUrl = event.target.value; })} /></label>
                <label className="field"><span>Default Manager Address</span><input value={state.preferences.operatorManagerAddress} onChange={(event) => updateState((next) => { next.preferences.operatorManagerAddress = event.target.value; })} /></label>
                <label className="field"><span>Default Manager Party</span><input value={state.preferences.operatorManagerParty} onChange={(event) => updateState((next) => { next.preferences.operatorManagerParty = event.target.value; })} /></label>
                <label className="field wide"><span>Default Params JSON</span><textarea value={state.preferences.connectionDefaultParamsText} onChange={(event) => updateState((next) => { next.preferences.connectionDefaultParamsText = event.target.value; })} /></label>
                <div className="connection-card">
                  <strong>Configured Storage</strong>
                  <span>{configuredStorageSummary}</span>
                </div>
                <div className="connection-card">
                  <strong>Managed Work Pane Defaults</strong>
                  <span>{normalizeBossUrl(state.preferences.operatorBossUrl) || "Boss URL not set"}</span>
                  <span>New managed-work panes inherit these values until you override them in Pane Config.</span>
                </div>
                <div className="connection-card wide">
                  <strong>{state.globalPlazaStatus.connected ? "Plaza Connected" : state.globalPlazaStatus.status === "loading" ? "Checking Plaza..." : "Plaza Offline"}</strong>
                  <span>{state.globalPlazaStatus.error || `${state.globalPlazaStatus.pulserCount || 0} pulsers · ${state.globalPlazaStatus.pulseCount || 0} pulses`}</span>
                  <button className="accent-button" onClick={refreshGlobalPlaza}>{state.globalPlazaStatus.status === "loading" ? "Refreshing..." : "Refresh Plaza Catalog"}</button>
                </div>
              </div>
            ) : null}
            {selectedSettingsTab === "storage" ? (
              <div className="settings-grid">
                {IS_MAP_PHEMAR_MODE && !mapPhemarHasOwnSettings ? (
                  <div className="connection-card wide">
                    <strong>Inherited Location</strong>
                    <span>{mapPhemaStorageInfo.label}</span>
                    <span className="workspace-dialog-storage-path">{mapPhemaStorageInfo.detail}</span>
                  </div>
                ) : (
                  <>
                    <div className="settings-storage-header">
                      <label className="field settings-storage-header-field">
                        <span>Default Save Backend</span>
                        <select
                          value={normalizeFileSaveBackend(state.preferences.fileSaveBackend)}
                          onChange={(event) => updateState((next) => { next.preferences.fileSaveBackend = normalizeFileSaveBackend(event.target.value); })}
                        >
                          {FILE_SAVE_BACKENDS.map((backend) => (
                            <option key={backend.id} value={backend.id}>{backend.label}</option>
                          ))}
                        </select>
                      </label>
                      {usingSystemPulser ? (
                        <button className={state.globalPlazaStatus.status === "loading" ? "ghost-button settings-storage-refresh active" : "ghost-button settings-storage-refresh"} onClick={refreshGlobalPlaza}>
                          {state.globalPlazaStatus.status === "loading" ? "Refreshing..." : "Refresh Plaza Catalog"}
                        </button>
                      ) : null}
                    </div>
                    {usingSystemPulser === false ? (
                      <>
                        <div className="settings-storage-directory-row">
                          <label className="field settings-storage-directory-field">
                            <span>{IS_MAP_PHEMAR_MODE ? "MapPhemar Directory" : "Local Directory"}</span>
                            <input
                              value={state.preferences.fileSaveLocalDirectory}
                              placeholder={IS_MAP_PHEMAR_MODE ? "phemacast/map_phemar/storage" : "phemacast/personal_agent/storage/saved_files"}
                              onChange={(event) => updateState((next) => { next.preferences.fileSaveLocalDirectory = event.target.value; })}
                            />
                          </label>
                          <div className="settings-storage-directory-actions">
                            <button className="ghost-button" onClick={chooseSettingsLocalDirectory}>
                              Choose Folder
                            </button>
                          </div>
                        </div>
                        <div className="connection-card wide">
                          <strong>{IS_MAP_PHEMAR_MODE ? "Filesystem Root" : "Default Local Save Path"}</strong>
                          <span>{state.preferences.fileSaveLocalDirectory || (IS_MAP_PHEMAR_MODE ? "phemacast/map_phemar/storage" : "phemacast/personal_agent/storage/saved_files")}</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <label className="field wide">
                          <span>SystemPulser</span>
                          <select
                            value={selectedStoragePulser?.agent_id || state.preferences.fileSavePulserId || ""}
                            onChange={(event) => updateState((next) => {
                              const pulser = storagePulsers.find((entry) => entry.agent_id === event.target.value) || null;
                              next.preferences.fileSavePulserId = pulser?.agent_id || "";
                              next.preferences.fileSavePulserName = pulser?.name || "";
                              next.preferences.fileSavePulserAddress = pulser?.address || "";
                            })}
                          >
                            <option value="">{storagePulsers.length ? "Choose SystemPulser" : "Refresh Plaza catalog first"}</option>
                            {storagePulsers.map((pulser) => (
                              <option key={pulser.agent_id || pulser.name} value={pulser.agent_id || ""}>
                                {formatPulserDisplayName(pulser, { includeAddress: true, fallbackName: "SystemPulser" })}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field field--storage-bucket">
                          <span>Bucket Name</span>
                          <select
                            value={state.preferences.fileSaveBucketName}
                            onChange={(event) => {
                              const nextValue = event.target.value;
                              updateState((next) => { next.preferences.fileSaveBucketName = nextValue; });
                              setStorageBucketError("");
                              setStorageBucketAddMode(false);
                              setStorageBucketDraft("");
                              setStorageBucketCreateStatus("idle");
                            }}
                            disabled={!selectedStoragePulser && storageBucketStatus === "idle"}
                          >
                            <option value="">
                              {storageBucketStatus === "loading"
                                ? "Loading current buckets..."
                                : selectedStoragePulser
                                  ? (storageBucketOptions.length ? "Choose bucket" : "No buckets yet")
                                  : "Choose SystemPulser first"}
                            </option>
                            {storageBucketOptions.map((bucket) => {
                              const bucketName = String(bucket?.bucket_name || bucket?.name || "").trim();
                              if (!bucketName) {
                                return null;
                              }
                              const visibility = String(bucket?.visibility || "").trim().toLowerCase();
                              const suffix = visibility && visibility !== "current" ? ` · ${visibility}` : visibility === "current" ? " · current" : "";
                              return (
                                <option key={`${bucketName}:${visibility || "default"}`} value={bucketName}>
                                  {`${bucketName}${suffix}`}
                                </option>
                              );
                            })}
                          </select>
                        </label>
                        <div className="field field--storage-bucket-action">
                          <span>Bucket Actions</span>
                          <button
                            className={storageBucketAddMode ? "ghost-button active" : "ghost-button"}
                            onClick={() => {
                              setStorageBucketAddMode((current) => !current);
                              setStorageBucketDraft(currentBucketName);
                              setStorageBucketError("");
                              setStorageBucketCreateStatus("idle");
                            }}
                            disabled={!canCreateStorageBucket || storageBucketCreateStatus === "loading"}
                            title={!canCreateStorageBucket ? "Selected SystemPulser does not expose bucket_create." : "Create a new private bucket on the selected SystemPulser"}
                          >
                            {storageBucketAddMode ? "Cancel New" : "Add New"}
                          </button>
                        </div>
                        {storageBucketAddMode ? (
                          <div className="storage-bucket-create-row">
                            <label className="field storage-bucket-create-field">
                              <span>New Bucket Name</span>
                              <input
                                value={storageBucketDraft}
                                placeholder="demo-assets"
                                onChange={(event) => setStorageBucketDraft(event.target.value)}
                              />
                            </label>
                            <button
                              className="ghost-button storage-bucket-create-cancel"
                              onClick={() => {
                                setStorageBucketAddMode(false);
                                setStorageBucketDraft("");
                                setStorageBucketError("");
                                setStorageBucketCreateStatus("idle");
                              }}
                              disabled={storageBucketCreateStatus === "loading"}
                            >
                              Cancel
                            </button>
                            <button
                              className="accent-button storage-bucket-create-submit"
                              onClick={createStorageBucket}
                              disabled={storageBucketCreateStatus === "loading" || !storageBucketDraft.trim()}
                            >
                              {storageBucketCreateStatus === "loading" ? "Creating..." : "Create Bucket"}
                            </button>
                          </div>
                        ) : null}
                        <div className={storageBucketError ? "settings-inline-note settings-inline-note--error" : "settings-inline-note"}>
                          {storageBucketError
                            || (selectedStoragePulser
                              ? storageBucketStatus === "loading"
                                ? "Loading current buckets from the selected SystemPulser..."
                                : listedStorageBucketCount
                                  ? `${listedStorageBucketCount} bucket${listedStorageBucketCount === 1 ? "" : "s"} available on the selected SystemPulser.`
                                  : "No buckets found yet. Create one to start saving through SystemPulser."
                              : "Choose a SystemPulser to load current buckets.")}
                        </div>
                        <label className="field">
                          <span>Object Prefix</span>
                          <input
                            value={state.preferences.fileSaveObjectPrefix}
                            placeholder={IS_MAP_PHEMAR_MODE ? "map-phemar/library" : "personal-agent/results"}
                            onChange={(event) => updateState((next) => { next.preferences.fileSaveObjectPrefix = event.target.value; })}
                          />
                        </label>
                        <div className="connection-card wide">
                          <strong>{formatConfiguredSystemPulserLabel(state.preferences, selectedStoragePulser, { fallbackName: "SystemPulser" })}</strong>
                          <span>
                            {selectedStoragePulser
                              ? `${state.preferences.fileSaveBucketName || "unset bucket"} / ${state.preferences.fileSaveObjectPrefix || "(root prefix)"}`
                              : "Refresh the Plaza catalog, then choose a SystemPulser that supports object_save."}
                          </span>
                        </div>
                      </>
                    )}
                    <div className="connection-card wide">
                      {IS_MAP_PHEMAR_MODE ? (
                        <>
                          <strong>Phema Library Location</strong>
                          <span>{mapPhemaStorageInfo.label}</span>
                          <span className="workspace-dialog-storage-path">{mapPhemaStorageInfo.detail}</span>
                        </>
                      ) : (
                        <>
                          <strong>Save Result Behavior</strong>
                          <span>
                            {normalizeFileSaveBackend(state.preferences.fileSaveBackend) === "filesystem"
                              ? "Pane Save Result writes JSON into the configured local directory."
                              : "Pane Save Result sends JSON through object_save on the configured SystemPulser."}
                          </span>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            ) : null}
            {selectedSettingsTab === "llm" ? (
              <div className="llm-manager">
                <div className="llm-toolbar">
                  <div className="subhead">
                    <strong>Routes</strong>
                    <span>{state.preferences.llmConfigs.length} saved</span>
                  </div>
                  <div className="llm-toolbar-actions">
                    <button className="ghost-button" onClick={() => addLlmConfig("api")}>Add API Config</button>
                    <button className="accent-button" onClick={() => addLlmConfig("llm_pulse")}>Add LLM Pulse</button>
                  </div>
                </div>
                <div className="llm-layout">
                  <div className="llm-list">
                    {state.preferences.llmConfigs.length ? state.preferences.llmConfigs.map((config) => (
                      <button key={config.id} className={state.settingsLlmSelectedId === config.id ? "llm-row active" : "llm-row"} onClick={() => updateState((next) => { next.settingsLlmSelectedId = config.id; })}>
                        <strong>{config.name}</strong>
                        <span>{config.type === "llm_pulse" ? "Plaza llm_chat route" : `${config.provider} API route`}</span>
                      </button>
                    )) : <div className="pane-empty small">No LLM routes saved yet.</div>}
                  </div>
                  <div className="llm-editor">
                    {selectedLlm ? (
                      <div className="settings-grid">
                        <label className="field"><span>Name</span><input value={selectedLlm.name} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) target.name = event.target.value;
                        })} /></label>
                        <label className="field"><span>Type</span><select value={selectedLlm.type} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) target.type = event.target.value;
                        })}>{LLM_CONFIG_TYPES.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
                        <label className="field"><span>Provider</span><select value={selectedLlm.provider} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) target.provider = event.target.value;
                        })}>{LLM_API_PROVIDERS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
                        <label className="field"><span>Models</span><input value={normalizeModels(selectedLlm.models || selectedLlm.model).join(", ")} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) {
                            target.models = normalizeModels(event.target.value);
                            target.model = target.models[0] || "";
                          }
                        })} /></label>
                        <label className="field wide"><span>Base URL / Plaza URL</span><input value={selectedLlm.type === "llm_pulse" ? selectedLlm.plazaUrl : selectedLlm.baseUrl} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) {
                            if (target.type === "llm_pulse") target.plazaUrl = event.target.value;
                            else target.baseUrl = event.target.value;
                          }
                        })} /></label>
                        <label className="field"><span>API Key / Pulser ID</span><input value={selectedLlm.type === "llm_pulse" ? selectedLlm.pulserId : selectedLlm.apiKey} onChange={(event) => updateState((next) => {
                          const target = next.preferences.llmConfigs.find((entry) => entry.id === selectedLlm.id);
                          if (target) {
                            if (target.type === "llm_pulse") target.pulserId = event.target.value;
                            else target.apiKey = event.target.value;
                          }
                        })} /></label>
                        <label className="field"><span>Default Route</span><button className={state.preferences.llmDefaultConfigId === selectedLlm.id ? "ghost-button active" : "ghost-button"} onClick={() => updateState((next) => { next.preferences.llmDefaultConfigId = selectedLlm.id; })}>{state.preferences.llmDefaultConfigId === selectedLlm.id ? "Default" : "Make Default"}</button></label>
                        <div className="field">
                          <span>Remove Route</span>
                          <button className="danger-button" onClick={() => updateState((next) => {
                            next.preferences.llmConfigs = next.preferences.llmConfigs.filter((entry) => entry.id !== selectedLlm.id);
                            next.settingsLlmSelectedId = next.preferences.llmConfigs[0]?.id || "";
                            if (next.preferences.llmDefaultConfigId === selectedLlm.id) {
                              next.preferences.llmDefaultConfigId = next.preferences.llmConfigs[0]?.id || "";
                            }
                          })}>Remove</button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  const primaryMapWindow = (workspace?.windows || []).find((entry) => entry.type === "mind_map")
    || activeWindowList().find((entry) => entry.type === "mind_map")
    || null;
  const mapPhemarBackHref = String(state.dashboard.meta?.back_href || "").trim();
  const mapPhemarBackLabel = String(state.dashboard.meta?.back_label || "").trim();
  const mapPhemarHasOwnSettings = IS_MAP_PHEMAR_MODE && MAP_PHEMAR_SETTINGS_SCOPE === "map_phemar" && MAP_PHEMAR_STORAGE_SETTINGS_MODE !== "inherited";
  const mapPhemarUsesInheritedSettings = IS_MAP_PHEMAR_MODE && !mapPhemarHasOwnSettings;
  const mapPhemaStorage = mapPhemaStorageTarget(state.preferences, state);
  const defaultSaveStorageSummary = formatStorageTargetSummary(defaultSaveStorageTarget(state.preferences, state));
  const mapPhemarReturnContext = mapPhemarReturnContextFromLocation();

  async function returnFromMapPhemar() {
    let returnedToOpener = false;
    let returnedPhema = null;
    try {
      if (primaryMapWindow) {
        const source = resolveMindMapSource(state, primaryMapWindow.id);
        const title = String(source?.windowLocation?.windowItem?.title || primaryMapWindow.title || "Diagram Phema").trim() || "Diagram Phema";
        if (source?.mapState) {
          const existingPhemaId = String(source.mapState.linkedPhemaId || "").trim();
          const payload = serializeMindMapToPhema(source.mapState, title, existingPhemaId);
          const prepared = await ensureStoragePulserReady(state);
          returnedPhema = await saveMapPhemaPayload(payload, prepared.appState);
          const savedId = String(returnedPhema?.phema_id || returnedPhema?.id || "").trim();
          updateState((next) => {
            const refreshed = resolveMindMapSource(next, primaryMapWindow.id);
            if (!refreshed?.mapState) {
              return;
            }
            refreshed.mapState.linkedPhemaId = savedId;
            refreshed.mapState.linkedPhemaName = String(returnedPhema?.name || "");
            refreshed.windowLocation.windowItem.title = String(returnedPhema?.name || refreshed.windowLocation.windowItem.title || "Diagram");
            refreshed.windowLocation.windowItem.subtitle = "Diagram-backed Phema";
            if (refreshed.linkedPaneLocation) {
              refreshed.linkedPaneLocation.pane.title = String(returnedPhema?.name || refreshed.linkedPaneLocation.pane.title || "Diagram");
            }
          });
        }
      }
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage(
          {
            type: MAP_PHEMAR_RETURN_MESSAGE_TYPE,
            context: mapPhemarReturnContext,
            phema: returnedPhema,
          },
          window.location.origin,
        );
        window.opener.focus();
        returnedToOpener = true;
      }
    } catch (error) {
      console.error("Unable to return focus to the personal agent opener.", error);
      window.alert(String(error?.message || "Unable to save the diagram before returning to the agent."));
      return;
    }
    if (returnedToOpener) {
      window.close();
      return;
    }
  if (mapPhemarBackHref) {
      window.location.href = mapPhemarBackHref;
    }
  }

  function renderManagedWorkPane(windowItem, pane) {
    const operator = pane.operatorState || createOperatorConsoleState(state.preferences);
    const counts = operatorSummaryCounts(operator);
    const selectedTicket = selectedOperatorTicket(windowItem.id, pane.id);
    const selectedSchedule = selectedOperatorSchedule(windowItem.id, pane.id);
    const selectedJob = operator.selectedJob;
    const destination = operatorDestinationStatus(selectedTicket);
    const selectedResultSummary = selectedTicket?.result_summary?.summary && typeof selectedTicket.result_summary.summary === "object"
      ? selectedTicket.result_summary.summary
      : selectedTicket?.result_summary || {};
    const operatorStatusLabel = operator.status === "loading"
      ? "Refreshing"
      : operator.status === "ready"
        ? "Synced"
        : operator.status === "error"
          ? "Attention"
          : "Idle";
    const operatorNote = operator.error
      ? operator.error
      : operator.lastRefreshedAt
        ? `Last refresh ${formatTimestamp(operator.lastRefreshedAt)}`
        : operator.bossUrl
          ? "Ready to monitor managed work."
          : "Set the Boss URL in Pane Config to start monitoring.";

    function renderEmptyState(title, detail) {
      return (
        <div className="pane-empty wide operator-empty">
          <strong>{title}</strong>
          <span>{detail}</span>
        </div>
      );
    }

    function renderWorkRows() {
      if (!operator.tickets.length) {
        return renderEmptyState(
          operator.bossUrl ? "No managed work yet." : "Boss URL not configured.",
          operator.bossUrl
            ? "Refresh again after BossPulser or the teamwork boss has issued work."
            : "Open Pane Config, add the Boss URL, and refresh this managed-work pane.",
        );
      }
      return (
        <div className="operator-ticket-list">
          {operator.tickets.map((ticket) => {
            const ticketId = operatorTicketId(ticket);
            const workerName = String(ticket?.worker_assignment?.worker_name || ticket?.worker_assignment?.worker_id || "Unassigned").trim();
            const executionStatus = String(ticket?.execution_state?.status || ticket?.result_summary?.status || "queued").trim().toLowerCase();
            const title = String(ticket?.ticket?.title || ticket?.work_item?.title || ticket?.work_item?.required_capability || ticketId || "Managed work").trim();
            return (
              <button
                key={ticketId || title}
                className={operator.selectedTicketId === ticketId ? "snapshot-row operator-ticket-row active" : "snapshot-row operator-ticket-row"}
                onClick={() => selectOperatorTicket(windowItem.id, pane.id, ticketId)}
              >
                <div className="operator-ticket-row-top">
                  <strong>{title}</strong>
                  <span className={statusPillClass(executionStatus)}>{labelizeStatus(executionStatus)}</span>
                </div>
                <span>{compactText(ticket?.work_item?.required_capability || "Capability not set", 72)}</span>
                <span>{`Worker: ${workerName}`}</span>
                <span>{`Updated: ${formatTimestamp(ticket?.ticket?.updated_at || ticket?.execution_state?.updated_at || ticket?.execution_state?.completed_at)}`}</span>
              </button>
            );
          })}
        </div>
      );
    }

    function renderScheduleRows() {
      if (!operator.schedules.length) {
        return <div className="pane-empty small">No saved schedules published by the boss yet.</div>;
      }
      return (
        <div className="operator-schedule-list">
          {operator.schedules.slice(0, 4).map((schedule) => {
            const scheduleId = operatorScheduleId(schedule);
            const scheduleStatus = String(schedule?.schedule?.status || "scheduled").trim().toLowerCase();
            return (
              <article key={scheduleId || schedule?.schedule?.name} className={selectedSchedule && operatorScheduleId(selectedSchedule) === scheduleId ? "connection-card operator-schedule-card active" : "connection-card operator-schedule-card"}>
                <div className="operator-ticket-row-top">
                  <strong>{schedule?.schedule?.name || schedule?.work_item?.title || scheduleId || "Managed schedule"}</strong>
                  <span className={statusPillClass(scheduleStatus)}>{labelizeStatus(scheduleStatus)}</span>
                </div>
                <span>{compactText(schedule?.work_item?.required_capability || "Capability not set", 72)}</span>
                <span>{`Next run: ${formatTimestamp(schedule?.schedule?.scheduled_for || schedule?.schedule?.schedule_time)}`}</span>
                <div className="operator-action-row">
                  <button className="ghost-button" onClick={() => issueOperatorSchedule(windowItem.id, pane.id, scheduleId)} disabled={operator.controlStatus === "loading"}>
                    {operator.controlStatus === "loading" && operator.selectedScheduleId === scheduleId ? "Issuing..." : "Issue Now"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      );
    }

    function renderAssignmentCards() {
      if (!selectedTicket) {
        return renderEmptyState("Pick a work item.", "Select a managed ticket to inspect manager assignment and worker execution.");
      }
      return (
        <div className="operator-detail-grid">
          <article className="connection-card">
            <strong>Boss Issuance</strong>
            <span>{selectedTicket?.ticket?.source || "manual"}</span>
            <span>{selectedTicket?.ticket?.workflow_id || selectedTicket?.ticket?.schedule_id || "Direct ticket"}</span>
          </article>
          <article className="connection-card">
            <strong>Manager Assignment</strong>
            <span>{selectedTicket?.manager_assignment?.manager_name || selectedTicket?.manager_assignment?.manager_address || "Manager not recorded"}</span>
            <span>{selectedTicket?.manager_assignment?.manager_party || "Party not recorded"}</span>
            <span>{formatTimestamp(selectedTicket?.manager_assignment?.assigned_at)}</span>
          </article>
          <article className="connection-card">
            <strong>Worker Assignment</strong>
            <span>{selectedTicket?.worker_assignment?.worker_name || selectedTicket?.worker_assignment?.worker_id || "Unassigned"}</span>
            <span>{selectedTicket?.worker_assignment?.worker_address || selectedTicket?.worker_assignment?.status || "No worker address yet"}</span>
            <span>{`Claimed: ${formatTimestamp(selectedTicket?.worker_assignment?.claimed_at)}`}</span>
          </article>
          <article className="connection-card wide">
            <strong>Execution Timeline</strong>
            <span>{`Status: ${labelizeStatus(selectedTicket?.execution_state?.status || selectedTicket?.result_summary?.status)}`}</span>
            <span>{`Queued: ${formatTimestamp(selectedTicket?.execution_state?.created_at)}`}</span>
            <span>{`Completed: ${formatTimestamp(selectedTicket?.execution_state?.completed_at)}`}</span>
            {selectedJob?.latest_heartbeat ? (
              <span>{`Latest heartbeat: ${formatTimestamp(selectedJob.latest_heartbeat?.updated_at || selectedJob.latest_heartbeat?.created_at)}`}</span>
            ) : null}
            {selectedTicket?.execution_state?.error ? <span>{compactText(selectedTicket.execution_state.error, 220)}</span> : null}
          </article>
        </div>
      );
    }

    function renderResultCards() {
      if (!selectedTicket) {
        return renderEmptyState("No result selected.", "Choose a ticket to inspect the structured result summary and raw job detail.");
      }
      return (
        <div className="operator-detail-grid">
          <article className="connection-card">
            <strong>Result Status</strong>
            <span>{labelizeStatus(selectedTicket?.result_summary?.status || selectedTicket?.execution_state?.status)}</span>
            <span>{`Stored rows: ${selectedTicket?.result_summary?.stored_rows || 0}`}</span>
            <span>{selectedTicket?.result_summary?.target_table || "No target table recorded"}</span>
          </article>
          <article className="connection-card">
            <strong>Job Detail</strong>
            <span>{selectedJob?.detail_source || (selectedJob?.job ? "job_detail" : "managed_ticket_detail")}</span>
            <span>{selectedJob?.job?.id || selectedTicket?.ticket?.id || "No job id"}</span>
            <span>{selectedJob?.job?.required_capability || selectedTicket?.work_item?.required_capability || "Capability not recorded"}</span>
          </article>
          <article className="preview-card wide">
            <div className="subhead">
              <strong>Result Summary</strong>
              <span>{formatTimestamp(selectedTicket?.execution_state?.updated_at || selectedTicket?.ticket?.updated_at)}</span>
            </div>
            {Object.keys(selectedResultSummary || {}).length
              ? <ValueRenderer value={selectedResultSummary} format="json" chartType="bar" />
              : <div className="pane-empty small">No structured result summary recorded yet.</div>}
          </article>
          <article className="preview-card wide">
            <div className="subhead">
              <strong>Raw Records</strong>
              <span>{Array.isArray(selectedJob?.raw_records) ? `${selectedJob.raw_records.length} rows` : "No rows"}</span>
            </div>
            {Array.isArray(selectedJob?.raw_records) && selectedJob.raw_records.length
              ? <ValueRenderer value={selectedJob.raw_records} format="json" chartType="bar" />
              : <div className="pane-empty small">The boss detail route has not recorded raw records for this run.</div>}
          </article>
        </div>
      );
    }

    function renderDestinationCards() {
      if (!selectedTicket) {
        return renderEmptyState("No destination view yet.", "Choose a ticket to inspect Notion publishing, NotebookLM export, and B2B delivery lanes.");
      }
      const notionMarkdown = selectedTicket?.work_item?.metadata?.publication?.notion_markdown
        || destination?.notion?.metadata?.publication?.notion_markdown
        || "";
      const notebookBundle = destination?.notebooklm?.source_url_bundle || "";
      return (
        <div className="operator-detail-grid">
          <article className="connection-card">
            <div className="operator-ticket-row-top">
              <strong>{destination?.notion?.label || "Notion"}</strong>
              <span className={statusPillClass(destination?.notion?.status)}>{labelizeStatus(destination?.notion?.status)}</span>
            </div>
            <span>{destination?.notion?.title || destination?.notion?.detail || "No Notion publication payload recorded."}</span>
            <span>{destination?.notion?.url || "Page URL not recorded"}</span>
            <div className="operator-action-row">
              {destination?.notion?.url ? <button className="ghost-button" onClick={() => openOperatorUrl(destination.notion.url)}>Open Page</button> : null}
              {notionMarkdown ? <button className="ghost-button" onClick={() => copyOperatorText(notionMarkdown, "Notion markdown")}>Copy Markdown</button> : null}
            </div>
          </article>
          <article className="connection-card">
            <div className="operator-ticket-row-top">
              <strong>{destination?.notebooklm?.label || "NotebookLM"}</strong>
              <span className={statusPillClass(destination?.notebooklm?.status)}>{labelizeStatus(destination?.notebooklm?.status)}</span>
            </div>
            <span>{destination?.notebooklm?.detail || destination?.notebooklm?.mode || "No NotebookLM export payload recorded."}</span>
            <span>{destination?.notebooklm?.directory || "Export directory not recorded"}</span>
            <div className="operator-action-row">
              {destination?.notebooklm?.directory ? <button className="ghost-button" onClick={() => copyOperatorText(destination.notebooklm.directory, "NotebookLM directory")}>Copy Directory</button> : null}
              {notebookBundle ? <button className="ghost-button" onClick={() => copyOperatorText(notebookBundle, "NotebookLM source URLs")}>Copy URLs</button> : null}
            </div>
          </article>
          {destination.channels.map((lane) => (
            <article key={lane.kind || lane.label} className="connection-card">
              <div className="operator-ticket-row-top">
                <strong>{lane.label || lane.kind || "Channel"}</strong>
                <span className={statusPillClass(lane.status)}>{labelizeStatus(lane.status)}</span>
              </div>
              <span>{lane.recipient || lane.destination || "Recipient not configured"}</span>
              <span>{lane.detail || "Lane is available for routed delivery."}</span>
              <div className="operator-action-row">
                {destination.publication_preview ? <button className="ghost-button" onClick={() => copyOperatorText(destination.publication_preview, `${lane.label || lane.kind} payload`)}>Copy Payload</button> : null}
                {lane.url ? <button className="ghost-button" onClick={() => openOperatorUrl(lane.url)}>Open</button> : null}
              </div>
            </article>
          ))}
          <article className="preview-card wide">
            <div className="subhead">
              <strong>Channel Payload Preview</strong>
              <span>{destination.publication_preview ? "Ready" : "Not recorded"}</span>
            </div>
            {destination.publication_preview
              ? <ValueRenderer value={destination.publication_preview} format="plain_text" chartType="bar" />
              : <div className="pane-empty small">The selected run has not recorded a channel-ready payload yet.</div>}
          </article>
        </div>
      );
    }

    let tabContent = null;
    if (operator.view === "assignments") {
      tabContent = renderAssignmentCards();
    } else if (operator.view === "results") {
      tabContent = renderResultCards();
    } else if (operator.view === "destinations") {
      tabContent = renderDestinationCards();
    } else {
      tabContent = (
        <>
          {renderWorkRows()}
          <section className="operator-schedule-section">
            <div className="subhead">
              <strong>Managed Schedules</strong>
              <span>{operator.schedules.length} tracked</span>
            </div>
            {renderScheduleRows()}
            {operator.controlError ? <div className="form-error">{operator.controlError}</div> : null}
          </section>
        </>
      );
    }

    return (
      <div className="operator-console operator-pane">
        <div className="operator-console-head">
          <div className="segmented operator-tabs">
            {OPERATOR_TABS.map((tab) => (
              <button key={tab.id} className={operator.view === tab.id ? "segment active" : "segment"} onClick={() => updateOperatorPaneField(windowItem.id, pane.id, "view", tab.id)}>
                {tab.label}
              </button>
            ))}
          </div>
          <div className="operator-console-actions">
            <span className={statusPillClass(operator.status)}>{operatorStatusLabel}</span>
            <button className={operator.status === "loading" ? "ghost-button active" : "ghost-button"} onClick={() => refreshOperatorMonitor(windowItem.id, pane.id, { preserveSelection: true })}>
              {operator.status === "loading" ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        <div className="operator-summary-strip" aria-label="Managed work summary">
          <span className="operator-metric-chip"><strong>{counts.total}</strong><small>Works</small></span>
          <span className="operator-metric-chip"><strong>{counts.assigned}</strong><small>Assigned</small></span>
          <span className="operator-metric-chip"><strong>{counts.attention}</strong><small>Attention</small></span>
          <span className="operator-metric-chip"><strong>{counts.destinations}</strong><small>Ready</small></span>
        </div>

        <div className={operator.error ? "operator-console-note operator-console-note--error" : "operator-console-note"}>
          {operatorNote}
        </div>

        <div className="operator-console-body">
          {tabContent}
        </div>
      </div>
    );
  }

  if (IS_MAP_PHEMAR_MODE) {
    return (
      <>
        <div className="map-phemar-shell">
          <header className="map-phemar-header">
            <div className="map-phemar-copy">
              <strong>{APP_DISPLAY_NAME}</strong>
              <span>Phemar agent with a diagram editor</span>
            </div>
            <div className="map-phemar-actions">
              <span className={workspacePlazaStatusClass} title={workspacePlazaStatusDetail}>
                {workspacePlazaStatusLabel}
              </span>
              <button className="ghost-button" onClick={openPersonalAgentUserGuide}>
                User Guide
              </button>
              {mapPhemarHasOwnSettings ? (
                <button className="ghost-button" onClick={() => updateState((next) => { next.settingsOpen = true; next.settingsTab = "storage"; })}>
                  Settings
                </button>
              ) : mapPhemarUsesInheritedSettings ? (
                <span className="status-pill ready" title={mapPhemaStorage.detail}>
                  Storage: Inherited
                </span>
              ) : null}
              {mapPhemarBackHref && mapPhemarBackLabel ? (
                <button className="ghost-button" onClick={returnFromMapPhemar}>
                  {mapPhemarBackLabel}
                </button>
              ) : null}
            </div>
          </header>
          <main className="map-phemar-stage">
            {primaryMapWindow ? (
              <section className="map-phemar-frame">
                {renderMindMapWindow(primaryMapWindow)}
              </section>
            ) : (
              <div className="pane-empty wide">Diagram editor unavailable.</div>
            )}
          </main>
        </div>

        {renderSettingsModal()}
        {renderSnapshotModal()}
        {renderPhemaDialog()}
        {renderDiagramRunDialog()}
      </>
    );
  }

  return (
    <>
      <div className={state.preferences.sidebarCollapsed ? "app-shell app-shell--sidebar-collapsed" : "app-shell"}>
        <aside className={state.preferences.sidebarCollapsed ? "rail shell-panel collapsed" : "rail shell-panel"}>
          <div className="brand-block">
            <div className="brand-mark">phemacast</div>
            <div className="brand-copy">
              <strong>Personal Agent</strong>
            </div>
          </div>
          <button className="sidebar-toggle" onClick={() => updateState((next) => { next.preferences.sidebarCollapsed = !next.preferences.sidebarCollapsed; })}>
            {state.preferences.sidebarCollapsed ? ">" : "<"}
          </button>
          {!state.preferences.sidebarCollapsed ? (
            <>
              <div className="rail-section">
                <div className="meta-stack">
                  <div><strong>Mode</strong><span>{state.dashboard.meta?.mode}</span></div>
                  <div><strong>Plaza</strong><span>{state.preferences.connectionPlazaUrl}</span></div>
                  <div><strong>Default Boss</strong><span>{state.preferences.operatorBossUrl || "Not set"}</span></div>
                  <div><strong>Storage</strong><span>{defaultSaveStorageSummary}</span></div>
                </div>
              </div>
              <div className="rail-section">
                <div className="theme-column">
                  {THEME_OPTIONS.map((theme) => (
                    <button key={theme.id} className={state.preferences.theme === theme.id ? "theme-chip active" : "theme-chip"} onClick={() => updateState((next) => { next.preferences.theme = theme.id; })}>
                      {theme.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </aside>

        <main className="stage">
          <header className="menu-bar shell-panel">
            <div className="menu-group">
              <div className="app-menu">
                <button
                  type="button"
                  ref={(node) => setMenuBarButtonRef("file", node)}
                  className={state.menuBarMenuId === "file" ? "ghost-button app-menu-trigger active" : "ghost-button app-menu-trigger"}
                  onClick={() => toggleMenuBarMenu("file")}
                  aria-haspopup="menu"
                  aria-expanded={state.menuBarMenuId === "file"}
                >
                  <span>File</span>
                  <span className="app-menu-caret" aria-hidden="true">{state.menuBarMenuId === "file" ? "^" : "v"}</span>
                </button>
                {renderMenuBarDropdown("file", "File menu", (
                  <>
                    <button type="button" className="ghost-button app-menu-item" onClick={createWorkspace} role="menuitem">New</button>
                    <button type="button" className="ghost-button app-menu-item" onClick={() => openWorkspaceDialogFromMenu("load")} role="menuitem">Open</button>
                    <button type="button" className="ghost-button app-menu-item" onClick={() => openWorkspaceDialogFromMenu("save")} role="menuitem">Save</button>
                    <button type="button" className="ghost-button app-menu-item" onClick={printWorkspaceFromMenu} role="menuitem">Print</button>
                    <button type="button" className="ghost-button app-menu-item" onClick={() => openSettingsFromMenu()} role="menuitem">Settings</button>
                  </>
                ))}
              </div>
              <div className="app-menu">
                <button
                  type="button"
                  ref={(node) => setMenuBarButtonRef("help", node)}
                  className={state.menuBarMenuId === "help" ? "ghost-button app-menu-trigger active" : "ghost-button app-menu-trigger"}
                  onClick={() => toggleMenuBarMenu("help")}
                  aria-haspopup="menu"
                  aria-expanded={state.menuBarMenuId === "help"}
                >
                  <span>Help</span>
                  <span className="app-menu-caret" aria-hidden="true">{state.menuBarMenuId === "help" ? "^" : "v"}</span>
                </button>
                {renderMenuBarDropdown("help", "Help menu", (
                  <button type="button" className="ghost-button app-menu-item" onClick={openUserGuideFromMenu} role="menuitem">Document</button>
                ))}
              </div>
            </div>
            <div className="menu-bar-actions">
              <span className={workspacePlazaStatusClass} title={workspacePlazaStatusDetail}>
                {menuBarPlazaStatusLabel}
              </span>
              <button type="button" className={state.globalPlazaStatus.status === "loading" ? "ghost-button menu-refresh-button active" : "ghost-button menu-refresh-button"} onClick={refreshGlobalPlaza}>
                {state.globalPlazaStatus.status === "loading" ? "Refreshing Plaza..." : "Refresh Plaza"}
              </button>
            </div>
          </header>

          <section className={state.preferences.workspaceSidebarCollapsed ? "workspace-shell workspace-shell--sidebar-collapsed" : "workspace-shell"}>
            <div className="workspace-plane">
              <section className="workspace-dock">
                <div className="workspace-dock-head">
                  <div className="workspace-toolbar">
                    <input
                      className="workspace-title-input"
                      value={workspace?.name || ""}
                      onChange={(event) => updateState((next) => {
                        const targetWorkspace = findWorkspace(next, next.activeWorkspaceId);
                        if (!targetWorkspace) {
                          return;
                        }
                        targetWorkspace.name = event.target.value;
                      })}
                      placeholder="Workspace title"
                    />
                  </div>
                  <div className="workspace-toolbar-actions">
                    <button className="ghost-button" onClick={() => createBrowser("docked")}>Add Browser</button>
                    <button className={workspaceIsRefreshing ? "ghost-button active" : "ghost-button"} onClick={() => refreshWorkspace(state.activeWorkspaceId)} disabled={workspaceIsRefreshing}>
                      {workspaceIsRefreshing ? "Refreshing..." : "Refresh"}
                    </button>
                    <button className={state.workspaceDialog.open && state.workspaceDialog.mode === "save" ? "ghost-button active" : "ghost-button"} onClick={() => openWorkspaceDialog("save")}>Save</button>
                    <button className={state.workspaceDialog.open && state.workspaceDialog.mode === "load" ? "ghost-button active" : "ghost-button"} onClick={() => openWorkspaceDialog("load")}>Load</button>
                  </div>
                </div>
                <div className="workspace-canvas" ref={workspaceCanvasRef}>
                  <div
                    className="workspace-world"
                    style={{
                      width: `${workspaceWorld.width}px`,
                      height: `${workspaceWorld.height}px`,
                    }}
                  >
                    {workspaceDockedWindows.map((windowItem) => (
                      <section
                        key={windowItem.id}
                        className="window-frame window-frame--floating"
                        style={{
                          left: `${Math.max(Number(windowItem.x || 0), WORKSPACE_LEFT_INSET) + workspaceWorld.offsetX}px`,
                          top: `${Math.max(Number(windowItem.y || 0), WORKSPACE_TOP_INSET) + workspaceWorld.offsetY}px`,
                          width: `${windowItem.width || 960}px`,
                          height: `${windowItem.height || 640}px`,
                          zIndex: windowItem.z || 1,
                        }}
                        onMouseDown={(event) => handleWindowMouseDown(windowItem.id, event)}
                      >
                        <header className={windowItem.type === "browser" ? "window-frame-head window-frame-head--draggable window-frame-head--bare" : "window-frame-head window-frame-head--draggable"} onMouseDown={(event) => beginWindowDrag(windowItem.id, event)}>
                          {windowItem.type === "browser" ? <span className="window-grip" /> : <strong>{windowItem.title}</strong>}
                        </header>
                        {windowItem.type === "browser" ? renderBrowserWindow(windowItem) : renderMindMapWindow(windowItem)}
                        <button className="window-resize-handle" onMouseDown={(event) => beginWindowResize(windowItem.id, event)} aria-label="Resize window" />
                      </section>
                    ))}
                    {!workspaceDockedWindows.length ? (
                      <div className="pane-empty wide workspace-empty">No windows.</div>
                    ) : null}
                  </div>
                </div>
              </section>
            </div>

            <aside className={state.preferences.workspaceSidebarCollapsed ? "workspace-sidebar workspace-sidebar--collapsed" : "workspace-sidebar"}>
              <section className="shell-panel sidebar-card workspace-sidebar-panel">
                <div className="workspace-sidebar-head">
                  {!state.preferences.workspaceSidebarCollapsed ? (
                    <div className="workspace-sidebar-copy">
                      <strong>Workspaces</strong>
                      <span>{state.workspaces.length} saved</span>
                    </div>
                  ) : null}
                  <button
                    className="icon-button workspace-sidebar-toggle"
                    onClick={() => updateState((next) => { next.preferences.workspaceSidebarCollapsed = !next.preferences.workspaceSidebarCollapsed; })}
                    aria-label={state.preferences.workspaceSidebarCollapsed ? "Expand workspace selector" : "Collapse workspace selector"}
                    title={state.preferences.workspaceSidebarCollapsed ? "Expand workspace selector" : "Collapse workspace selector"}
                  >
                    {state.preferences.workspaceSidebarCollapsed ? ">" : "<"}
                  </button>
                </div>
                {state.preferences.workspaceSidebarCollapsed ? (
                  <div className="workspace-mini-list">
                    {state.workspaces.map((entry) => (
                      <button
                        key={entry.id}
                        className={state.activeWorkspaceId === entry.id ? "workspace-mini-button active" : "workspace-mini-button"}
                        onClick={() => updateState((next) => { next.activeWorkspaceId = entry.id; next.preferences.defaultWorkspaceId = entry.id; })}
                        title={entry.name}
                      >
                        {workspaceShortLabel(entry.name)}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="workspace-list">
                    {state.workspaces.map((entry) => (
                      <div key={entry.id} className="workspace-card-row">
                        <button className={state.activeWorkspaceId === entry.id ? "workspace-card active" : "workspace-card"} onClick={() => updateState((next) => { next.activeWorkspaceId = entry.id; next.preferences.defaultWorkspaceId = entry.id; })}>
                          <strong>{entry.name}</strong>
                          <span>{entry.focus}</span>
                        </button>
                        <button
                          className="icon-button workspace-card-delete"
                          onClick={() => deleteWorkspace(entry.id)}
                          aria-label={`Delete ${entry.name}`}
                          title={`Delete ${entry.name}`}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </aside>
          </section>
        </main>
      </div>

      {renderSettingsModal()}
      {renderPaneConfigModal()}
      {renderSnapshotModal()}
      {renderPhemaDialog()}
      {renderWorkspaceDialog()}
      {renderPrintDialog()}
      {renderDiagramRunDialog()}

      {activeWindowList().filter((entry) => entry.mode === "external").map((windowItem) => (
        <PopupWindowPortal
          key={windowItem.id}
          windowItem={windowItem}
          theme={state.preferences.theme}
          title={`${windowItem.title} · ${APP_DISPLAY_NAME}`}
          onClosed={handlePopupClosed}
        >
          <div className="popup-window-shell">
            <section className="window-frame window-frame--popup">
              {windowItem.type === "browser" ? null : (
                <header className="window-frame-head">
                  <strong>{windowItem.title}</strong>
                </header>
              )}
              {windowItem.type === "browser" ? renderBrowserWindow(windowItem) : renderMindMapWindow(windowItem)}
            </section>
          </div>
        </PopupWindowPortal>
      ))}
    </>
  );
}

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.handleReset = this.handleReset.bind(this);
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error(`${APP_DISPLAY_NAME} render failed.`, error, info);
  }

  handleReset() {
    resetPersonalAgentStorage({ preservePreferences: true });
    window.location.reload();
  }

  handleReload() {
    window.location.reload();
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-crash-shell">
          <div className="app-crash-card">
            <strong>{APP_DISPLAY_NAME} hit a saved-state error.</strong>
            <p>
              The app recovered the base bundle, but one of the stored windows or panes is breaking render.
            </p>
            <pre className="app-crash-error">{String(this.state.error?.message || this.state.error || "Unknown error")}</pre>
            <div className="app-crash-actions">
              <button className="accent-button" onClick={this.handleReset}>Reset Workspaces</button>
              <button className="ghost-button" onClick={this.handleReload}>Reload App</button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <RootErrorBoundary>
    <App />
  </RootErrorBoundary>,
);
