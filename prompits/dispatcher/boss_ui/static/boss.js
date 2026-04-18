(function () {
  const STORAGE_KEY = "dispatcher-boss-settings-v1";
  const SIDEBAR_STORAGE_KEY = "dispatcher-boss-sidebar-v1";
  const initial = window.__DISPATCHER_BOSS_INITIAL__ || {};
  const state = {
    current_page: initial.current_page || "issue",
    hero_metrics: initial.hero_metrics || null,
    monitor_tab: "jobs",
    db_tab: "viewer",
    monitor_panel_collapsed: true,
    monitor_summary: initial.monitor_summary || null,
    job_options: initial.job_options || [],
    monitor_workers: [],
    worker_status_filter: "online",
    worker_job_modal_open: false,
    worker_job_modal_job_id: "",
    worker_history_modal_open: false,
    worker_history_modal_worker_id: "",
    worker_history_modal_worker_name: "",
    schedule_history_modal_open: false,
    schedule_history_modal_schedule_id: "",
    schedule_history_modal_schedule_name: "",
    jobs: [],
    schedules: [],
    issue_symbols_value: "",
    selected_job_id: "",
    selected_job: null,
    selected_job_raw_records: [],
    db_tables: initial.db_tables || [],
    db_column_widths: {},
    sidebar_collapsed: false,
    issue_parameters_collapsed: true,
    plaza_status: initial.plaza_status || {},
    plaza_dispatchers: Array.isArray(initial?.plaza_status?.dispatchers) ? initial.plaza_status.dispatchers : [],
    plaza_parties: Array.isArray(initial?.plaza_status?.parties) ? initial.plaza_status.parties : [],
    settings_defaults: initial.settings_defaults || {},
    runtime_summary: initial.runtime_summary || {},
    settings: {}, // Populated on DOMContentLoaded
    dispatcher_address: initial.dispatcher_address || "",
    dispatcher_party: initial.dispatcher_party || initial?.settings_defaults?.dispatcher_party || ""
  };

  let monitorRefreshHandle = null;
  let heroMetricsInFlight = false;
  let monitorSummaryInFlight = false;
  let monitorRefreshInFlight = false;
  let jobDetailRefreshInFlight = false;
  let pendingJobRefresh = false;

  const JOB_STATUS_SORT_ORDER = [
    "claimed",
    "stopping",
    "paused",
    "queued",
    "retry",
    "stopped",
    "completed",
    "failed",
    "cancelled",
    "deleted",
  ];

  const DEFAULT_HERO_METRICS = [
    { id: "dispatcher_workers", label: "Workers", table_name: "dispatcher_worker_capabilities", count: 0, available: false },
    { id: "worker_history", label: "Worker History", table_name: "dispatcher_worker_history", count: 0, available: false },
    { id: "result_rows", label: "Result Rows", table_name: "dispatcher_job_results", count: 0, available: false },
    { id: "raw_payloads", label: "Raw Payloads", table_name: "dispatcher_raw_payloads", count: 0, available: false },
    { id: "queued_jobs", label: "Queued Jobs", count: 0, available: false },
    { id: "workers_online", label: "Workers Online", count: 0, available: false }
  ];

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function coerceMonitorRefreshSec(value) {
    const parsed = Number.parseInt(String(value || "0"), 10);
    if (!Number.isFinite(parsed) || Number.isNaN(parsed)) return 0;
    return Math.max(0, Math.min(parsed, 3600));
  }

  function readStoredSettings() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  function writeStoredSettings(settings) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (_error) {
    }
  }

  function readStoredSidebarCollapsed() {
    try {
      return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
    } catch (_error) {
      return false;
    }
  }

  function writeStoredSidebarCollapsed(collapsed) {
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
    } catch (_error) {
    }
  }

  function buildSettingsState(stored) {
    return Object.assign({}, state.settings_defaults, stored);
  }

  function formatTimestamp(value) {
    if (!value) return "Unset";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  }

  function formatRelativeTime(value) {
    if (!value) return "No activity yet";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const diffMs = Date.now() - date.getTime();
    if (diffMs < 0) return "In the future";
    const diffSec = Math.round(diffMs / 1000);
    if (diffSec < 10) return "Just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.round(diffHr / 24);
    return `${diffDay}d ago`;
  }

  function formatSeconds(value) {
    if (value === null || value === undefined || value === "") return "Unknown";
    const seconds = Number(value);
    if (!Number.isFinite(seconds) || Number.isNaN(seconds)) return "Unknown";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
    return `${Math.round(seconds / 86400)}d`;
  }

  function formatMetricCount(value) {
    const count = Number(value);
    if (!Number.isFinite(count) || Number.isNaN(count) || count < 0) return "--";
    return new Intl.NumberFormat().format(Math.trunc(count));
  }

  function shortJobId(jobId) {
    const text = String(jobId || "").trim();
    if (!text) return "No id";
    const parts = text.split(":");
    return parts.length > 1 ? parts[parts.length - 1] : text;
  }

  function heroMetricList(payload) {
    const merged = new Map(DEFAULT_HERO_METRICS.map(metric => [metric.id, Object.assign({}, metric)]));
    const orderedIds = DEFAULT_HERO_METRICS.map(metric => metric.id);
    const metricGroups = [];
    if (Array.isArray(initial?.hero_metrics?.metrics)) metricGroups.push(initial.hero_metrics.metrics);
    if (Array.isArray(payload?.metrics)) metricGroups.push(payload.metrics);
    if (Array.isArray(payload?.operational_metrics)) metricGroups.push(payload.operational_metrics);
    metricGroups.flat().forEach(metric => {
      const metricId = String(metric?.id || "").trim();
      if (!metricId) return;
      if (!orderedIds.includes(metricId)) orderedIds.push(metricId);
      merged.set(metricId, Object.assign({}, merged.get(metricId) || {}, metric));
    });
    return orderedIds.map(metricId => merged.get(metricId)).filter(Boolean);
  }

  function buildOperationalHeroMetrics(payload) {
    const dispatcher = isPlainObject(payload?.dispatcher) ? payload.dispatcher : {};
    const connectionStatus = String(dispatcher.connection_status || "unknown").trim().toLowerCase() || "unknown";
    const available = connectionStatus === "connected";
    const jobCounts = isPlainObject(dispatcher.job_counts) ? dispatcher.job_counts : {};
    const workerCounts = isPlainObject(dispatcher.worker_counts) ? dispatcher.worker_counts : {};
    return [
      {
        id: "queued_jobs",
        label: "Queued Jobs",
        count: Number(jobCounts.queued || 0),
        available,
      },
      {
        id: "workers_online",
        label: "Workers Online",
        count: Number(dispatcher.active_workers ?? workerCounts.online ?? 0),
        available,
      }
    ];
  }

  function buildHeroMetricCard(metric, summary) {
    const status = String(summary?.status || "idle").trim().toLowerCase() || "idle";
    const label = String(metric?.label || humanizeKey(metric?.id || "metric")).trim() || "Metric";
    const available = Boolean(metric?.available);
    const value = status === "loading"
      ? "..."
      : (available ? formatMetricCount(metric?.count) : "--");

    const classes = ["hero-metric-card"];
    if (!available || status === "not_configured" || status === "unreachable") classes.push("is-unavailable");
    if (status === "loading") classes.push("is-loading");

    return `
      <article class="${classes.join(" ")}" data-hero-metric-id="${escapeHtml(metric?.id || "")}">
        <div class="hero-metric-label">${escapeHtml(label)}</div>
        <div class="hero-metric-value">${escapeHtml(value)}</div>
      </article>
    `;
  }

  function renderHeroMetrics(payload) {
    const grid = byId("hero-metrics-grid");
    if (!grid) return;
    const summary = payload && typeof payload === "object" ? payload : (state.hero_metrics || initial.hero_metrics || {});
    const status = String(summary?.status || "idle").trim().toLowerCase() || "idle";
    grid.dataset.heroMetricsStatus = status;
    grid.innerHTML = heroMetricList(summary).map(metric => buildHeroMetricCard(metric, summary)).join("");
  }

  function setHeroMetricsRefreshState(isLoading) {
    const button = byId("hero-metrics-refresh");
    if (!button) return;
    button.disabled = Boolean(isLoading);
    button.textContent = isLoading ? "Refreshing..." : "Refresh Metrics";
  }

  function setStatus(id, label, mode) {
    const chip = byId(id);
    if (!chip) return;
    chip.textContent = label;
    chip.className = `status is-${mode || 'muted'}`;
  }

  function resolvePreferredPlazaUrl() {
    const candidates = [
      byId("settings-plaza-url-input")?.value,
      state.settings?.plaza_url,
      state.runtime_summary?.plaza_url,
      state.plaza_status?.plaza_url,
      "http://127.0.0.1:8011",
    ];
    return candidates.map(value => String(value || "").trim()).find(Boolean) || "";
  }

  function syncPlazaUrlState(url) {
    const normalized = String(url || "").trim();
    if (!normalized) return;
    state.settings.plaza_url = normalized;
    state.runtime_summary.plaza_url = normalized;
    const input = byId("settings-plaza-url-input");
    if (input && input.value !== normalized) {
      input.value = normalized;
    }
    writeStoredSettings(state.settings);
    renderRuntimeSummary();
  }

  function normalizeDispatcherParty(value) {
    return String(value || "").trim();
  }

  function currentDispatcherParty() {
    return normalizeDispatcherParty(byId("settings-dispatcher-party")?.value || state.dispatcher_party || state.settings?.dispatcher_party || "");
  }

  function setDispatcherParty(value) {
    const normalized = normalizeDispatcherParty(value);
    state.dispatcher_party = normalized;
    state.settings.dispatcher_party = normalized;
    if (byId("settings-dispatcher-party") && byId("settings-dispatcher-party").value !== normalized) {
      byId("settings-dispatcher-party").value = normalized;
    }
    renderRuntimeSummary();
  }

  function renderDispatcherPartyOptions() {
    const select = byId("settings-dispatcher-party");
    if (!select) return;
    const selected = currentDispatcherParty() || normalizeDispatcherParty(state.settings_defaults?.dispatcher_party || "Prompits");
    const parties = Array.from(new Set(
      [selected, ...(Array.isArray(state.plaza_parties) ? state.plaza_parties : [])]
        .map(item => normalizeDispatcherParty(item))
        .filter(Boolean)
    ));
    select.innerHTML = parties.map(party => `<option value="${escapeHtml(party)}">${escapeHtml(party)}</option>`).join("");
    if (selected) {
      select.value = selected;
    }
  }

  function renderDispatcherSelectOptions() {
    const select = byId("settings-dispatcher-select");
    if (!select) return;
    const dispatchers = Array.isArray(state.plaza_dispatchers) ? state.plaza_dispatchers : [];
    const current = String(state.dispatcher_address || "").trim();
    const options = [
      `<option value="">Auto-select discovered dispatcher</option>`,
      ...dispatchers.map(dispatcher => {
        const address = String(dispatcher?.address || "").trim();
        const name = String(dispatcher?.name || "Dispatcher").trim() || "Dispatcher";
        const label = address ? `${name} · ${address}` : name;
        return `<option value="${escapeHtml(address)}">${escapeHtml(label)}</option>`;
      }),
    ];
    select.innerHTML = options.join("");
    if (current && dispatchers.some(dispatcher => String(dispatcher?.address || "").trim() === current)) {
      select.value = current;
    }
  }

  function syncPlazaDirectory(payload) {
    if (!payload || typeof payload !== "object") return;
    state.plaza_status = payload;
    state.plaza_dispatchers = Array.isArray(payload.dispatchers) ? payload.dispatchers : [];
    state.plaza_parties = Array.isArray(payload.parties) ? payload.parties : [];
    const selectedParty = normalizeDispatcherParty(payload.dispatcher_party || currentDispatcherParty());
    if (selectedParty) {
      setDispatcherParty(selectedParty);
    }
    renderDispatcherPartyOptions();
    renderDispatcherSelectOptions();
    const selectedAddress = String(payload.selected_dispatcher_address || "").trim();
    const dispatcherAddresses = state.plaza_dispatchers.map(dispatcher => String(dispatcher?.address || "").trim()).filter(Boolean);
    if (selectedAddress && (!state.dispatcher_address || !dispatcherAddresses.includes(state.dispatcher_address))) {
      setDispatcherAddress(selectedAddress);
    }
    renderRuntimeSummary();
  }

  function updateHeroConnectButton(payload) {
    const button = byId("hero-connect-plaza");
    if (!button) return;
    const status = String(payload?.connection_status || "").trim().toLowerCase();
    const plazaUrl = String(payload?.plaza_url || state.settings?.plaza_url || "").trim();
    if (status === "connected") {
      button.textContent = "Reconnect Plaza";
      button.title = plazaUrl ? `Reconnect using ${plazaUrl}` : "Reconnect Plaza";
      return;
    }
    if (status === "disconnected") {
      button.textContent = "Retry Plaza";
      button.title = plazaUrl ? `Retry using ${plazaUrl}` : "Retry Plaza";
      return;
    }
    button.textContent = "Connect Plaza";
    button.title = plazaUrl ? `Connect using ${plazaUrl}` : "Connect Plaza";
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function cloneJsonValue(value) {
    if (Array.isArray(value)) return value.map(item => cloneJsonValue(item));
    if (isPlainObject(value)) {
      const cloned = {};
      Object.entries(value).forEach(([key, item]) => {
        cloned[key] = cloneJsonValue(item);
      });
      return cloned;
    }
    return value;
  }

  function jobOptionById(value) {
    const normalized = String(value || "").trim();
    if (!normalized) return null;
    return state.job_options.find(option => String(option?.id || "").trim() === normalized) || null;
  }

  function currentIssueJobOption() {
    return jobOptionById(byId("required-capability")?.value);
  }

  function jobOptionDefaultPriority(option) {
    const parsed = Number.parseInt(String(option?.default_priority ?? "100"), 10);
    return Number.isFinite(parsed) ? parsed : 100;
  }

  function syncIssueJobPriority(option = currentIssueJobOption()) {
    const input = byId("priority");
    if (!input) return;
    input.value = String(jobOptionDefaultPriority(option));
  }

  function jobOptionPayloadTemplate(option) {
    return isPlainObject(option?.payload_template) ? cloneJsonValue(option.payload_template) : {};
  }

  function jobOptionParameters(option) {
    return Array.isArray(option?.parameters) ? option.parameters : [];
  }

  function jobOptionRequiresSymbols(option) {
    return Boolean(option?.requires_symbols);
  }

  function jobTargets(job) {
    if (Array.isArray(job?.targets)) return job.targets.filter(Boolean);
    if (Array.isArray(job?.symbols)) return job.symbols.filter(Boolean);
    return [];
  }

  function readJsonTextareaValue(textareaId, fallback = {}) {
    const textarea = byId(textareaId);
    const raw = textarea?.value || "{}";
    try {
      return { valid: true, value: JSON.parse(raw || "{}") };
    } catch (_error) {
      return { valid: false, value: cloneJsonValue(fallback) };
    }
  }

  function writeJsonTextareaValue(textareaId, value) {
    const textarea = byId(textareaId);
    if (!textarea) return;
    textarea.value = JSON.stringify(value, null, 2);
  }

  function normalizeFeedListValue(value) {
    if (!Array.isArray(value)) return [];
    return value
      .map(item => {
        if (isPlainObject(item)) {
          return {
            source: String(item.source || item.name || "").trim(),
            url: String(item.url || item.feed_url || "").trim(),
          };
        }
        if (typeof item === "string") {
          return { source: "", url: item.trim() };
        }
        return null;
      })
      .filter(Boolean);
  }

  function seedPayloadObject(payload, template, parameters) {
    const nextPayload = isPlainObject(payload) ? cloneJsonValue(payload) : cloneJsonValue(template);
    let changed = !isPlainObject(payload);
    parameters.forEach(parameter => {
      const key = String(parameter?.key || "").trim();
      if (!key || nextPayload[key] !== undefined) return;
      if (template[key] !== undefined) {
        nextPayload[key] = cloneJsonValue(template[key]);
      } else if (String(parameter?.type || "").trim() === "feed_list") {
        nextPayload[key] = [];
      } else {
        nextPayload[key] = null;
      }
      changed = true;
    });
    return { changed, payload: nextPayload };
  }

  function buildFeedParameterRowMarkup(parameterKey, row, index) {
    return `
      <div class="parameter-feed-row" data-param-key="${escapeHtml(parameterKey)}" data-param-index="${escapeHtml(String(index))}">
        <div class="field">
          <label>Source</label>
          <input
            type="text"
            value="${escapeHtml(row?.source || "")}"
            placeholder="SEC"
            data-param-key="${escapeHtml(parameterKey)}"
            data-param-index="${escapeHtml(String(index))}"
            data-param-field="source"
          >
        </div>
        <div class="field">
          <label>Feed URL</label>
          <input
            type="url"
            value="${escapeHtml(row?.url || "")}"
            placeholder="https://example.com/feed.xml"
            data-param-key="${escapeHtml(parameterKey)}"
            data-param-index="${escapeHtml(String(index))}"
            data-param-field="url"
          >
        </div>
        <button
          type="button"
          class="danger-btn"
          data-param-action="remove-row"
          data-param-key="${escapeHtml(parameterKey)}"
          data-param-index="${escapeHtml(String(index))}"
        >Remove</button>
      </div>
    `;
  }

  function buildSymbolsParameterMarkup() {
    const currentSymbols = String(byId("symbols")?.value || state.issue_symbols_value || "").trim();
    return `
      <section class="parameter-card" data-param-type="symbols">
        <div class="parameter-card-head">
          <div class="parameter-card-title">Targets</div>
        </div>
        <div class="field">
          <label for="symbols">Targets</label>
          <input id="symbols" name="symbols" type="text" value="${escapeHtml(currentSymbols)}" placeholder="item-a, item-b">
        </div>
        <div class="muted">Enter comma-separated tickers when the job targets specific instruments. Leave blank for jobs that collect feed-wide or market-wide data.</div>
      </section>
    `;
  }

  function buildIssueParameterMarkup(parameter, payload) {
    const key = String(parameter?.key || "").trim();
    const label = String(parameter?.label || humanizeKey(key || "parameter")).trim() || "Parameter";
    const help = String(parameter?.help || "").trim();
    const type = String(parameter?.type || "").trim().toLowerCase();
    if (type !== "feed_list" || !key) return "";

    const rows = normalizeFeedListValue(payload?.[key]);
    const rowMarkup = rows.length
      ? rows.map((row, index) => buildFeedParameterRowMarkup(key, row, index)).join("")
      : '<div class="empty-state">No feeds configured yet.</div>';

    return `
      <section class="parameter-card" data-param-type="${escapeHtml(type)}" data-param-key="${escapeHtml(key)}">
        <div class="parameter-card-head">
          <div class="parameter-card-title">${escapeHtml(label)}</div>
          <button type="button" class="ghost-btn" data-param-action="add-row" data-param-key="${escapeHtml(key)}">Add Feed</button>
        </div>
        <div class="parameter-feed-list">${rowMarkup}</div>
        ${help ? `<div class="muted">${escapeHtml(help)}</div>` : ""}
      </section>
    `;
  }

  function renderIssueParameters(options = {}) {
    const field = byId("job-parameters-field");
    const shell = byId("job-parameters");
    if (!field || !shell) return;

    const option = currentIssueJobOption();
    const parameters = jobOptionParameters(option);
    const sections = jobOptionRequiresSymbols(option) ? [buildSymbolsParameterMarkup()] : [];
    if (!parameters.length) {
      field.hidden = sections.length === 0;
      shell.innerHTML = sections.join("");
      applyIssueParametersCollapsed(state.issue_parameters_collapsed);
      return;
    }

    const template = jobOptionPayloadTemplate(option);
    const payloadState = readJsonTextareaValue("payload-json", template);
    if (!payloadState.valid) {
      field.hidden = false;
      shell.innerHTML = `${sections.join("")}<div class="empty-state">Payload JSON must be valid before these parameters can be edited.</div>`;
      applyIssueParametersCollapsed(state.issue_parameters_collapsed);
      return;
    }

    const seedDefaults = options.seedDefaults !== false;
    let payload = payloadState.value;
    if (seedDefaults) {
      const seeded = seedPayloadObject(payloadState.value, template, parameters);
      payload = seeded.payload;
      if (seeded.changed) writeJsonTextareaValue("payload-json", payload);
    } else if (!isPlainObject(payloadState.value)) {
      payload = template;
      writeJsonTextareaValue("payload-json", payload);
    }

    field.hidden = false;
    shell.innerHTML = sections.concat(
      parameters
        .map(parameter => buildIssueParameterMarkup(parameter, payload))
        .filter(Boolean)
    ).join("");
    applyIssueParametersCollapsed(state.issue_parameters_collapsed);
  }

  function updateIssueParameterFieldFromInput(input) {
    const parameterKey = String(input?.getAttribute("data-param-key") || "").trim();
    const fieldName = String(input?.getAttribute("data-param-field") || "").trim();
    const index = Number.parseInt(String(input?.getAttribute("data-param-index") || "-1"), 10);
    if (!parameterKey || !fieldName || !Number.isFinite(index) || index < 0) return;

    const option = currentIssueJobOption();
    const template = jobOptionPayloadTemplate(option);
    const payloadState = readJsonTextareaValue("payload-json", template);
    if (!payloadState.valid || !isPlainObject(payloadState.value)) return;

    const rows = normalizeFeedListValue(payloadState.value[parameterKey]);
    while (rows.length <= index) {
      rows.push({ source: "", url: "" });
    }
    rows[index][fieldName] = input.value;
    payloadState.value[parameterKey] = rows;
    writeJsonTextareaValue("payload-json", payloadState.value);
  }

  function addIssueParameterRow(parameterKey) {
    const option = currentIssueJobOption();
    const template = jobOptionPayloadTemplate(option);
    const payloadState = readJsonTextareaValue("payload-json", template);
    if (!payloadState.valid || !isPlainObject(payloadState.value)) return;
    const rows = normalizeFeedListValue(payloadState.value[parameterKey]);
    rows.push({ source: "", url: "" });
    payloadState.value[parameterKey] = rows;
    writeJsonTextareaValue("payload-json", payloadState.value);
    renderIssueParameters({ seedDefaults: false });
  }

  function removeIssueParameterRow(parameterKey, index) {
    const option = currentIssueJobOption();
    const template = jobOptionPayloadTemplate(option);
    const payloadState = readJsonTextareaValue("payload-json", template);
    if (!payloadState.valid || !isPlainObject(payloadState.value)) return;
    const rows = normalizeFeedListValue(payloadState.value[parameterKey]);
    if (index < 0 || index >= rows.length) return;
    rows.splice(index, 1);
    payloadState.value[parameterKey] = rows;
    writeJsonTextareaValue("payload-json", payloadState.value);
    renderIssueParameters({ seedDefaults: false });
  }

  function humanizeKey(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, match => match.toUpperCase());
  }

  function formatInlineDetailValue(value) {
    if (value === null || value === undefined || value === "") return "Unset";
    if (Array.isArray(value)) {
      const items = value.map(item => formatInlineDetailValue(item)).filter(Boolean);
      return items.length ? items.join(", ") : "Unset";
    }
    if (isPlainObject(value)) {
      const entries = Object.entries(value);
      if (!entries.length) return "Unset";
      return entries
        .slice(0, 6)
        .map(([key, item]) => `${humanizeKey(key)}: ${formatInlineDetailValue(item)}`)
        .join(" | ");
    }
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
  }

  function statusTone(status) {
    const normalized = String(status || "").trim().toLowerCase();
    if (["completed", "issued", "connected", "online", "working"].includes(normalized)) return "success";
    if (["failed", "cancelled", "deleted", "error", "offline", "blocked", "attention", "unreachable"].includes(normalized)) return "error";
    if (["claimed", "stopping", "paused", "retry", "unfinished", "issuing", "queued", "stale", "checking"].includes(normalized)) return "loading";
    return "muted";
  }

  function statusChipMarkup(status) {
    const normalized = String(status || "unknown").trim().toLowerCase() || "unknown";
    return `<span class="status is-${statusTone(normalized)}">${escapeHtml(humanizeKey(normalized))}</span>`;
  }

  function detailItemMarkup(label, value, options = {}) {
    const classes = ["job-detail-value"];
    if (options.mono) classes.push("is-mono");
    if (options.danger) classes.push("is-danger");
    return `
      <div class="job-detail-item">
        <div class="job-detail-label">${escapeHtml(label)}</div>
        <div class="${classes.join(" ")}">${escapeHtml(formatInlineDetailValue(value))}</div>
      </div>
    `;
  }

  function pillListMarkup(values, emptyLabel = "None") {
    const items = Array.isArray(values) ? values.filter(Boolean) : [];
    if (!items.length) {
      return `<div class="job-detail-empty">${escapeHtml(emptyLabel)}</div>`;
    }
    return `<div class="job-detail-tags">${items.map(value => `<span class="job-detail-pill">${escapeHtml(formatInlineDetailValue(value))}</span>`).join("")}</div>`;
  }

  function summarizeRawRecord(record) {
    const payload = isPlainObject(record?.payload) ? record.payload : {};
    const requests = Array.isArray(payload.requests) ? payload.requests.length : 0;
    const provider = payload.provider || record?.metadata?.provider || record?.metadata?.source || "";
    const summary = [];
    if (provider) summary.push(`Provider: ${provider}`);
    if (requests) summary.push(`Requests: ${requests}`);
    if (record?.target_table) summary.push(`Target: ${record.target_table}`);
    if (record?.source_url) summary.push(`Source: ${record.source_url}`);
    return summary.length ? summary.join(" | ") : "Stored raw collection payload.";
  }

  function conciseSourceLabel(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    try {
      const parsed = new URL(text);
      return parsed.hostname || text;
    } catch (_error) {
      return text.length > 48 ? `${text.slice(0, 45)}...` : text;
    }
  }

  function buildCriticalJobCardSummary(job) {
    const payload = isPlainObject(job?.payload) ? job.payload : {};
    const parts = [];
    const identity = String(payload.wns_number || payload.item_id || payload.record_id || "").trim();
    const pageIndex = Number.parseInt(String(payload.page_index ?? payload.page ?? ""), 10);
    if (identity) parts.push(identity);
    if (Number.isFinite(pageIndex) && !Number.isNaN(pageIndex)) {
      parts.push(`Page ${pageIndex}`);
    }
    if (payload.refresh_item === true) {
      parts.push("Refresh");
    }
    return parts.join(" · ");
  }

  function buildJobImportantSummary(job, options = {}) {
    const criticalSummary = buildCriticalJobCardSummary(job);
    if (criticalSummary) return criticalSummary;

    const targets = jobTargets(job);
    const payloadData = isPlainObject(job?.payload) ? job.payload : {};
    const maxPayloadFields = Number.isFinite(options.maxPayloadFields) ? options.maxPayloadFields : 2;
    const maxParts = Number.isFinite(options.maxParts) ? options.maxParts : 4;
    const parts = [];

    if (targets.length) {
      const targetPreview = targets.slice(0, 3).join(", ");
      parts.push(targets.length > 3 ? `Targets: ${targetPreview} +${targets.length - 3}` : `Targets: ${targetPreview}`);
    }
    if (job?.target_table) {
      parts.push(`Target: ${job.target_table}`);
    }

    Object.entries(payloadData)
      .filter(([key, value]) => {
        const normalizedKey = String(key || "").trim().toLowerCase();
        return !["symbol", "symbols", "target", "targets"].includes(normalizedKey) && value !== "" && value !== null && value !== undefined;
      })
      .slice(0, maxPayloadFields)
      .forEach(([key, value]) => {
        parts.push(`${humanizeKey(key)}: ${formatInlineDetailValue(value)}`);
      });

    if (!parts.length && job?.scheduled_for) {
      parts.push(`Scheduled: ${formatTimestamp(job.scheduled_for)}`);
    }
    if (!parts.length && (job?.priority || job?.priority === 0)) {
      parts.push(`Priority: ${job.priority}`);
    }
    if (!parts.length) {
      const sourceLabel = conciseSourceLabel(job?.source_url);
      if (sourceLabel) {
        parts.push(`Source: ${sourceLabel}`);
      }
    }

    return parts.slice(0, maxParts).join(" | ");
  }

  function buildJobMetaLabel(job, options = {}) {
    const name = String(job?.required_capability || options.fallbackName || "Current Job").trim();
    const summary = buildJobImportantSummary(job, { maxPayloadFields: 1, maxParts: 2 });
    return summary ? `${name} · ${summary}` : name;
  }

  function resolveWorkerActiveJobs(worker) {
    const directJobs = Array.isArray(worker?.active_jobs) ? worker.active_jobs.filter(isPlainObject) : [];
    if (directJobs.length) return directJobs;
    const activeJobIds = Array.isArray(worker?.active_job_ids) ? worker.active_job_ids : [];
    return activeJobIds.map(jobId => {
      const normalizedJobId = String(jobId || "").trim();
      if (!normalizedJobId) return null;
      return state.jobs.find(job => job.id === normalizedJobId) || { id: normalizedJobId };
    }).filter(Boolean);
  }

  function workerActiveJobName(job, index = 0) {
    const name = String(job?.required_capability || job?.name || "").trim();
    return name || `Active Job ${index + 1}`;
  }

  function workerActiveJobButtonLabel(job, index = 0) {
    const name = workerActiveJobName(job, index);
    const summary = buildJobImportantSummary(job, { maxPayloadFields: 1, maxParts: 1 });
    return summary ? `${name} · ${summary}` : name;
  }

  function workerActiveJobsPreview(activeJobs) {
    const names = (Array.isArray(activeJobs) ? activeJobs : []).map((job, index) => workerActiveJobName(job, index)).filter(Boolean);
    if (!names.length) return "0";
    const preview = names.slice(0, 2).join(", ");
    return names.length > 2 ? `${names.length} · ${preview} +${names.length - 2}` : `${names.length} · ${preview}`;
  }

  function workerCapabilitiesMarkup(capabilities) {
    const items = Array.isArray(capabilities) ? capabilities.filter(Boolean) : [];
    return `
      <details class="worker-capabilities">
        <summary>Capabilities${items.length ? ` · ${items.length}` : ""}</summary>
        ${
          items.length
            ? `<div class="worker-capabilities-body">${items.map(capability => `<span class="monitor-chip">${escapeHtml(capability)}</span>`).join("")}</div>`
            : `<div class="worker-capabilities-empty">No capabilities registered.</div>`
        }
      </details>
    `;
  }

  function canForceTerminateJob(job) {
    const status = String(job?.status || "").trim().toLowerCase();
    return Boolean(job?.id) && ["claimed", "working"].includes(status);
  }

  function buildWorkerHistoryCard(job) {
    const summary = buildJobImportantSummary(job, { maxPayloadFields: 2, maxParts: 3 });
    const currentStatuses = new Set(["claimed", "stopping"]);
    const isCurrent = currentStatuses.has(String(job?.status || "").trim().toLowerCase());
    return `
      <section class="job-detail-card worker-history-card">
        <div class="job-detail-headline">
          <div>
            <div class="job-detail-name">${escapeHtml(job?.required_capability || "Unknown Job")}</div>
            <div class="job-detail-summary">${escapeHtml(summary || "No key request parameters attached.")}</div>
          </div>
          <div class="job-detail-head-actions">
            ${isCurrent ? '<span class="monitor-chip">Current</span>' : ""}
            ${statusChipMarkup(job?.status)}
            <button
              type="button"
              class="ghost-btn job-detail-inline-action"
              data-worker-history-job-detail="${escapeHtml(job?.id || "")}"
            >
              Open Detail
            </button>
          </div>
        </div>
        <div class="job-detail-grid" style="margin-top: 14px;">
          ${detailItemMarkup("Job Id", shortJobId(job?.id || ""))}
          ${detailItemMarkup("Claimed By", job?.claimed_by || "Unclaimed")}
          ${detailItemMarkup("Created", formatTimestamp(job?.created_at))}
          ${detailItemMarkup("Updated", formatTimestamp(job?.updated_at))}
          ${detailItemMarkup("Claimed At", formatTimestamp(job?.claimed_at))}
          ${detailItemMarkup("Completed At", formatTimestamp(job?.completed_at))}
        </div>
      </section>
    `;
  }

  function renderWorkerHistory(payload) {
    const meta = byId("worker-history-modal-meta");
    const body = byId("worker-history-modal-body");
    if (!meta || !body) return;
    const jobs = Array.isArray(payload?.jobs) ? payload.jobs : [];
    const worker = isPlainObject(payload?.worker) ? payload.worker : {};
    const workerName = String(worker?.name || state.worker_history_modal_worker_name || payload?.worker_id || "Worker").trim();
    const totalCount = Number(payload?.count || jobs.length || 0);
    meta.textContent = `${workerName} · last ${Math.min(jobs.length, Number(payload?.limit || 10) || 10)} of ${totalCount} tracked job${totalCount === 1 ? "" : "s"}`;
    if (!jobs.length) {
      body.innerHTML = `<div class="empty-state">No jobs recorded for ${escapeHtml(workerName)} yet.</div>`;
      return;
    }
    body.innerHTML = `<div class="worker-history-list">${jobs.map(buildWorkerHistoryCard).join("")}</div>`;
  }

  function buildScheduleHistoryCard(job) {
    const summary = buildJobImportantSummary(job, { maxPayloadFields: 2, maxParts: 3 });
    return `
      <section class="job-detail-card worker-history-card">
        <div class="job-detail-headline">
          <div>
            <div class="job-detail-name">${escapeHtml(job?.required_capability || "Unknown Job")}</div>
            <div class="job-detail-summary">${escapeHtml(summary || "No key request parameters attached.")}</div>
          </div>
          <div class="job-detail-head-actions">
            ${statusChipMarkup(job?.status)}
            <button
              type="button"
              class="ghost-btn job-detail-inline-action"
              data-schedule-history-job-detail="${escapeHtml(job?.id || "")}"
            >
              Open Detail
            </button>
          </div>
        </div>
        <div class="job-detail-grid" style="margin-top: 14px;">
          ${detailItemMarkup("Job Id", shortJobId(job?.id || ""))}
          ${detailItemMarkup("Claimed By", job?.claimed_by || "Unclaimed")}
          ${detailItemMarkup("Created", formatTimestamp(job?.created_at))}
          ${detailItemMarkup("Updated", formatTimestamp(job?.updated_at))}
          ${detailItemMarkup("Completed At", formatTimestamp(job?.completed_at))}
          ${detailItemMarkup("Attempts", `${job?.attempts ?? 0} / ${job?.max_attempts ?? "?"}`)}
        </div>
      </section>
    `;
  }

  function renderScheduleHistory(payload) {
    const meta = byId("schedule-history-modal-meta");
    const body = byId("schedule-history-modal-body");
    if (!meta || !body) return;
    const jobs = Array.isArray(payload?.jobs) ? payload.jobs : [];
    const schedule = isPlainObject(payload?.schedule) ? payload.schedule : {};
    const scheduleName = String(
      schedule?.name
      || state.schedule_history_modal_schedule_name
      || schedule?.required_capability
      || "Schedule"
    ).trim();
    const totalCount = Number(payload?.count || jobs.length || 0);
    meta.textContent = `${scheduleName} · last ${Math.min(jobs.length, Number(payload?.limit || 20) || 20)} of ${totalCount} related job${totalCount === 1 ? "" : "s"}`;
    if (!jobs.length) {
      body.innerHTML = `<div class="empty-state">No issued jobs recorded for ${escapeHtml(scheduleName)} yet.</div>`;
      return;
    }
    body.innerHTML = `<div class="worker-history-list">${jobs.map(buildScheduleHistoryCard).join("")}</div>`;
  }

  async function loadScheduleHistory(scheduleId, options = {}) {
    const normalizedScheduleId = String(scheduleId || "").trim();
    if (!normalizedScheduleId) return;
    const scheduleName = String(options.scheduleName || state.schedule_history_modal_schedule_name || normalizedScheduleId).trim();
    state.schedule_history_modal_schedule_id = normalizedScheduleId;
    state.schedule_history_modal_schedule_name = scheduleName;
    const meta = byId("schedule-history-modal-meta");
    if (meta) meta.textContent = `Loading related jobs for ${scheduleName}...`;
    renderJobDetailLoading("Loading related issued jobs...", "schedule-history-modal-body");
    try {
      const query = new URLSearchParams();
      query.set("limit", "20");
      const suffix = query.toString();
      const payload = await fetchJson(`/api/schedules/${encodeURIComponent(normalizedScheduleId)}/history${suffix ? `?${suffix}` : ""}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      if (state.schedule_history_modal_schedule_id !== normalizedScheduleId) return;
      renderScheduleHistory(payload);
    } catch (error) {
      if (state.schedule_history_modal_schedule_id !== normalizedScheduleId) return;
      if (meta) meta.textContent = "Unable to load schedule job history.";
      renderJobDetailError(error.message || "Unable to load schedule job history.", "schedule-history-modal-body");
    }
  }

  async function openScheduleHistoryModal(scheduleId, scheduleName = "") {
    const normalizedScheduleId = String(scheduleId || "").trim();
    if (!normalizedScheduleId) return;
    state.schedule_history_modal_schedule_id = normalizedScheduleId;
    state.schedule_history_modal_schedule_name = String(scheduleName || normalizedScheduleId).trim() || normalizedScheduleId;
    setScheduleHistoryModalOpen(true);
    await loadScheduleHistory(normalizedScheduleId, { scheduleName: state.schedule_history_modal_schedule_name });
  }

  function buildJobDetailMarkup(payload) {
    const job = isPlainObject(payload?.job) ? payload.job : {};
    const rawRecords = Array.isArray(payload?.raw_records) ? payload.raw_records : [];
    const latestHeartbeat = isPlainObject(payload?.latest_heartbeat) ? payload.latest_heartbeat : {};
    const resultSummary = isPlainObject(job.result_summary) ? job.result_summary : {};
    const errorHistory = Array.isArray(resultSummary.error_history)
      ? resultSummary.error_history.filter(isPlainObject)
      : [];
    const latestHistoricalError = errorHistory.length ? errorHistory[errorHistory.length - 1] : null;
    const visibleResultSummary = Object.fromEntries(
      Object.entries(resultSummary).filter(([key]) => key !== "error_history" && key !== "last_error")
    );
    const metadata = isPlainObject(job.metadata) ? job.metadata : {};
    const payloadData = isPlainObject(job.payload) ? job.payload : {};
    const targets = jobTargets(job);
    const tags = Array.isArray(job.capability_tags) ? job.capability_tags : [];
    const resultSummaryItems = Object.keys(visibleResultSummary).length
      ? Object.entries(visibleResultSummary).map(([key, value]) => detailItemMarkup(humanizeKey(key), value, { mono: typeof value === "string" && String(value).includes(":") }))
      : [`<div class="job-detail-empty">No result summary recorded.</div>`];
    const metadataItems = Object.keys(metadata).length
      ? Object.entries(metadata).slice(0, 8).map(([key, value]) => detailItemMarkup(humanizeKey(key), value))
      : [`<div class="job-detail-empty">No metadata recorded.</div>`];
    const displayedError = job.error || latestHistoricalError?.error || "";
    const errorLabel = job.error ? "Error" : (latestHistoricalError ? "Latest Error" : "Error");
    const errorHistoryItems = errorHistory.length
      ? errorHistory.slice(-3).reverse().map((entry) => {
          const labelParts = [humanizeKey(entry.status || "error")];
          if (entry.attempt) labelParts.push(`Attempt ${entry.attempt}`);
          return detailItemMarkup(
            labelParts.join(" · "),
            {
              error: entry.error || "",
              exception: entry.exception || "",
              retryable: entry.retryable,
              recorded_at: formatTimestamp(entry.recorded_at),
              worker_id: entry.worker_id || "",
            },
            { danger: true }
          );
        })
      : [`<div class="job-detail-empty">No prior errors recorded.</div>`];
    const requestItems = [
      detailItemMarkup("Job Type", job.job_type || "collect"),
      detailItemMarkup("Priority", job.priority),
      detailItemMarkup("Attempts", `${job.attempts ?? 0} / ${job.max_attempts ?? "?"}`),
      detailItemMarkup("Dispatcher Source", job.source_url || "Unset", { mono: Boolean(job.source_url) }),
      detailItemMarkup("Claimed By", job.claimed_by || "Unclaimed", { mono: Boolean(job.claimed_by) }),
      detailItemMarkup("Scheduled For", formatTimestamp(job.scheduled_for)),
    ];

    if (Object.keys(payloadData).length) {
      requestItems.push(...Object.entries(payloadData).slice(0, 6).map(([key, value]) => detailItemMarkup(`Payload · ${humanizeKey(key)}`, value)));
    }
    const importantSummary = buildJobImportantSummary(job, { maxPayloadFields: 3, maxParts: 5 });
    const heartbeatMessage = String(latestHeartbeat.message || "").trim();
    const heartbeatPhase = String(latestHeartbeat.phase || latestHeartbeat.status || "").trim().toLowerCase();
    const heartbeatMeta = [
      String(latestHeartbeat.worker_name || latestHeartbeat.worker_id || "").trim(),
      heartbeatPhase ? humanizeKey(heartbeatPhase) : "",
      latestHeartbeat.captured_at
        ? `${formatTimestamp(latestHeartbeat.captured_at)} (${formatRelativeTime(latestHeartbeat.captured_at)})`
        : "",
    ].filter(Boolean).join(" · ");
    const heartbeatBanner = heartbeatMessage || heartbeatMeta
      ? `
          <div class="job-detail-heartbeat-banner">
            <div class="job-detail-heartbeat-label">Latest Heartbeat</div>
            <div class="job-detail-heartbeat-message">${escapeHtml(heartbeatMessage || "Worker heartbeat recorded.")}</div>
            ${heartbeatMeta ? `<div class="job-detail-heartbeat-meta">${escapeHtml(heartbeatMeta)}</div>` : ""}
          </div>
        `
      : "";
    const forceTerminateAction = canForceTerminateJob(job)
      ? `
          <button
            type="button"
            class="danger-btn job-detail-inline-action"
            data-job-detail-action="force_terminate"
            data-job-id="${escapeHtml(job.id || "")}"
          >
            Force Terminate
          </button>
        `
      : "";

    return `
      <section class="job-detail-card">
        ${heartbeatBanner}
        <div class="job-detail-headline">
          <div>
            <div class="job-detail-name">${escapeHtml(job.required_capability || "Unknown Job")}</div>
            <div class="job-detail-summary">${escapeHtml(importantSummary || "No key request parameters attached.")}</div>
          </div>
          <div class="job-detail-head-actions">
            ${statusChipMarkup(job.status)}
            ${forceTerminateAction}
          </div>
        </div>
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Lifecycle</h3>
        </div>
        <div class="job-detail-grid">
          ${detailItemMarkup("Created", formatTimestamp(job.created_at))}
          ${detailItemMarkup("Updated", formatTimestamp(job.updated_at))}
          ${detailItemMarkup("Claimed At", formatTimestamp(job.claimed_at))}
          ${detailItemMarkup("Completed At", formatTimestamp(job.completed_at))}
        </div>
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Request</h3>
        </div>
        <div class="job-detail-grid">
          ${requestItems.join("")}
        </div>
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Targets</h3>
        </div>
        ${pillListMarkup(targets, "No targets attached to this job.")}
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Capability Tags</h3>
        </div>
        ${pillListMarkup(tags, "No capability tags.")}
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Outcome</h3>
        </div>
        <div class="job-detail-grid">
          ${displayedError ? detailItemMarkup(errorLabel, displayedError, { danger: true }) : detailItemMarkup("Error", "No error recorded.")}
          ${detailItemMarkup("Raw Records", rawRecords.length)}
        </div>
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Result Summary</h3>
        </div>
        <div class="job-detail-grid">
          ${resultSummaryItems.join("")}
        </div>
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Error History</h3>
        </div>
        <div class="job-detail-grid">
          ${errorHistoryItems.join("")}
        </div>
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Metadata</h3>
        </div>
        <div class="job-detail-grid">
          ${metadataItems.join("")}
        </div>
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Raw Activity</h3>
        </div>
        ${
          rawRecords.length
            ? `<div class="job-detail-record-list">${rawRecords.slice(0, 4).map(record => `
                <div class="job-detail-record">
                  <div class="job-detail-value">${escapeHtml(summarizeRawRecord(record))}</div>
                  <div class="job-detail-record-meta">
                    <span class="job-detail-pill">${escapeHtml(formatTimestamp(record.collected_at))}</span>
                    ${record.worker_id ? `<span class="job-detail-pill">${escapeHtml(record.worker_id)}</span>` : ""}
                    ${record.target_table ? `<span class="job-detail-pill">${escapeHtml(record.target_table)}</span>` : ""}
                  </div>
                </div>
              `).join("")}</div>`
            : `<div class="job-detail-empty">No raw collection payloads stored for this job yet.</div>`
        }
      </section>
    `;
  }

  function renderJobDetailResponse(payload) {
    const shell = byId("job-detail");
    if (!shell) return;
    shell.innerHTML = buildJobDetailMarkup(payload);
  }

  function renderJobDetailLoading(label, targetId = "job-detail") {
    const shell = byId(targetId);
    if (!shell) return;
    shell.innerHTML = `<div class="empty-state">${escapeHtml(label || "Loading job detail...")}</div>`;
  }

  function renderJobDetailEmpty(label, targetId = "job-detail") {
    const shell = byId(targetId);
    if (!shell) return;
    shell.innerHTML = `<div class="empty-state">${escapeHtml(label || "Select a job to inspect its state.")}</div>`;
  }

  function renderJobDetailError(message, targetId = "job-detail") {
    const shell = byId(targetId);
    if (!shell) return;
    shell.innerHTML = `
      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Job Detail Error</h3>
          <span class="status is-error">Error</span>
        </div>
        <div class="job-detail-value is-danger">${escapeHtml(message || "Unable to load job detail.")}</div>
      </section>
    `;
  }

  function renderBossSubmitResult(payload) {
    const shell = byId("boss-result");
    if (!shell) return;

    const submission = isPlainObject(payload?.submission) ? payload.submission : {};
    const job = isPlainObject(submission?.job) ? submission.job : (isPlainObject(payload?.job) ? payload.job : {});
    const payloadData = isPlainObject(job.payload) ? job.payload : {};
    const metadata = isPlainObject(job.metadata) ? job.metadata : {};
    const targets = jobTargets(job);
    const capabilityTags = Array.isArray(job.capability_tags) ? job.capability_tags : [];
    const payloadItems = Object.keys(payloadData).length
      ? Object.entries(payloadData).slice(0, 6).map(([key, value]) => detailItemMarkup(humanizeKey(key), value))
      : [`<div class="job-detail-empty">No payload fields were supplied.</div>`];
    const metadataItems = Object.keys(metadata).length
      ? Object.entries(metadata).slice(0, 6).map(([key, value]) => detailItemMarkup(humanizeKey(key), value))
      : [`<div class="job-detail-empty">No metadata attached.</div>`];
    const dispatchStatus = String(submission?.status || payload?.status || job?.status || "submitted").trim();

    if (!Object.keys(job).length) {
      shell.innerHTML = `
        <section class="job-detail-card">
          <div class="job-detail-card-header">
            <h3 class="job-detail-card-title">Submission</h3>
            ${statusChipMarkup(dispatchStatus)}
          </div>
          <div class="job-detail-value">Dispatcher accepted the request, but no structured job detail was returned.</div>
        </section>
      `;
      return;
    }

    shell.innerHTML = `
      <section class="job-detail-card">
        <div class="job-detail-headline">
          <div>
            <div class="job-detail-name">${escapeHtml(job.required_capability || "Submitted Job")}</div>
            <div class="job-detail-summary">${escapeHtml(buildJobImportantSummary(job, { maxPayloadFields: 3, maxParts: 5 }) || "No key request parameters attached.")}</div>
          </div>
          ${statusChipMarkup(job.status || dispatchStatus)}
        </div>
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Dispatch Summary</h3>
        </div>
        <div class="job-detail-grid">
          ${detailItemMarkup("Submission Status", dispatchStatus)}
          ${detailItemMarkup("Dispatcher", currentDispatcherAddress() || state.dispatcher_address || "Unset", { mono: true })}
          ${detailItemMarkup("Job Type", job.job_type || "collect")}
          ${detailItemMarkup("Priority", job.priority)}
          ${detailItemMarkup("Attempts", `${job.attempts ?? 0} / ${job.max_attempts ?? "?"}`)}
          ${detailItemMarkup("Scheduled For", formatTimestamp(job.scheduled_for))}
          ${detailItemMarkup("Created", formatTimestamp(job.created_at))}
          ${detailItemMarkup("Updated", formatTimestamp(job.updated_at))}
        </div>
      </section>

      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Request</h3>
        </div>
        <div class="job-detail-card-header" style="margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Targets</h3>
        </div>
        ${pillListMarkup(targets, "No targets attached.")}
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Capability Tags</h3>
        </div>
        ${pillListMarkup(capabilityTags, "No capability tags.")}
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Payload Fields</h3>
        </div>
        <div class="job-detail-grid">
          ${payloadItems.join("")}
        </div>
        <div class="job-detail-card-header" style="margin-top: 14px; margin-bottom: 8px;">
          <h3 class="job-detail-card-title">Metadata</h3>
        </div>
        <div class="job-detail-grid">
          ${metadataItems.join("")}
        </div>
      </section>
    `;
  }

  function renderBossSubmitError(message) {
    const shell = byId("boss-result");
    if (!shell) return;
    shell.innerHTML = `
      <section class="job-detail-card">
        <div class="job-detail-card-header">
          <h3 class="job-detail-card-title">Submission Error</h3>
          <span class="status is-error">Error</span>
        </div>
        <div class="job-detail-value is-danger">${escapeHtml(message || "Unable to submit job.")}</div>
      </section>
    `;
  }

  function renderDbTableOptions() {
    const select = byId("db-table-name");
    if (!select) return;
    const selected = select.value;
    const options = state.db_tables || [];
    select.innerHTML = options.map(table => `<option value="${escapeHtml(table.name)}">${escapeHtml(table.label || table.name)}</option>`).join("");
    if (options.some(table => table.name === selected)) {
      select.value = selected;
    }
  }

  function formatCellValue(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "object") return JSON.stringify(value, null, 2);
    return String(value);
  }

  function dbColumnWidthKey(columns) {
    return (Array.isArray(columns) ? columns : []).map(column => String(column || "")).join("|");
  }

  function estimateDbColumnWidth(column, rows) {
    const samples = [column, ...(Array.isArray(rows) ? rows.slice(0, 20).map(row => formatCellValue(row?.[column])) : [])]
      .map(value => String(value || "").replace(/\s+/g, " ").trim())
      .filter(Boolean);
    const longest = samples.reduce((max, sample) => Math.max(max, sample.length), 0);
    if (longest >= 120) return 460;
    if (longest >= 72) return 380;
    if (longest >= 40) return 300;
    if (longest >= 24) return 240;
    if (longest >= 12) return 180;
    return 140;
  }

  function columnWidthStyle(width) {
    const pixels = Math.max(120, Number.parseInt(String(width || "0"), 10) || 0);
    return `${pixels}px`;
  }

  function initDbTableResizers(shell, payload) {
    if (!shell || !payload || !Array.isArray(payload.columns)) return;
    const table = shell.querySelector(".table-result-grid");
    if (!table) return;

    const columns = payload.columns;
    const key = dbColumnWidthKey(columns);
    const storedWidths = state.db_column_widths[key] || {};
    const colElements = Array.from(table.querySelectorAll("col[data-column-index]"));
    const handles = Array.from(table.querySelectorAll(".table-col-resizer"));

    handles.forEach((handle, index) => {
      const columnName = columns[index];
      const col = colElements[index];
      if (!columnName || !col) return;

      handle.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const startX = event.clientX;
        const startWidth = Number.parseInt(String(storedWidths[columnName] || col.offsetWidth || 0), 10) || estimateDbColumnWidth(columnName, payload.rows);

        function onPointerMove(moveEvent) {
          const nextWidth = Math.max(120, startWidth + (moveEvent.clientX - startX));
          col.style.width = columnWidthStyle(nextWidth);
          state.db_column_widths[key] = Object.assign({}, state.db_column_widths[key], {
            [columnName]: nextWidth,
          });
        }

        function finishResize() {
          document.body.classList.remove("is-db-col-resizing");
          window.removeEventListener("pointermove", onPointerMove);
          window.removeEventListener("pointerup", finishResize);
          window.removeEventListener("pointercancel", finishResize);
        }

        document.body.classList.add("is-db-col-resizing");
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", finishResize, { once: true });
        window.addEventListener("pointercancel", finishResize, { once: true });
      });
    });
  }

  function renderDbResult(payload, metaLabel) {
    const shell = byId("db-result");
    const meta = byId("db-result-meta");
    if (!shell || !meta) return;
    if (!payload || !Array.isArray(payload.columns) || !Array.isArray(payload.rows)) {
      shell.innerHTML = '<div class="empty-state">No database result loaded yet.</div>';
      meta.textContent = metaLabel || "Load a table or run a query.";
      return;
    }

    meta.textContent = metaLabel || `${payload.count || payload.rows.length} row${(payload.count || payload.rows.length) === 1 ? "" : "s"} loaded.`;
    if (!payload.rows.length) {
      shell.innerHTML = '<div class="empty-state">Query returned no rows.</div>';
      return;
    }

    const widthKey = dbColumnWidthKey(payload.columns);
    const widthMap = state.db_column_widths[widthKey] || {};

    shell.innerHTML = `
      <table class="table-result-grid">
        <colgroup>
          ${payload.columns.map(column => `<col data-column-index="${escapeHtml(column)}" style="width: ${escapeHtml(columnWidthStyle(widthMap[column] || estimateDbColumnWidth(column, payload.rows)))};">`).join("")}
        </colgroup>
        <thead>
          <tr>${payload.columns.map((column, index) => `
            <th scope="col">
              <div class="table-result-th-inner">
                <span class="table-result-th-label">${escapeHtml(column)}</span>
                <button
                  type="button"
                  class="table-col-resizer"
                  data-column-index="${index}"
                  aria-label="Resize ${escapeHtml(column)} column"
                  tabindex="-1"
                ></button>
              </div>
            </th>
          `).join("")}</tr>
        </thead>
        <tbody>
          ${payload.rows.map(row => `
            <tr>
              ${payload.columns.map(column => `<td><div class="table-result-code">${escapeHtml(formatCellValue(row[column]))}</div></td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
    initDbTableResizers(shell, payload);
  }

  function monitorDetailItemMarkup(label, value, options = {}) {
    const valueClass = options.mono ? "monitor-detail-value is-mono" : "monitor-detail-value";
    return `
      <div class="monitor-detail-item">
        <div class="monitor-detail-label">${escapeHtml(label)}</div>
        <div class="${valueClass}">${escapeHtml(value)}</div>
      </div>
    `;
  }

  function normalizeWorkerStatusFilter(value) {
    const normalized = String(value || "online").trim().toLowerCase();
    return ["online", "stale", "offline", "all"].includes(normalized) ? normalized : "online";
  }

  function normalizeJobSort(value) {
    const normalized = String(value || "time_desc").trim().toLowerCase();
    return ["time_desc", "name_asc", "status_asc"].includes(normalized) ? normalized : "time_desc";
  }

  function jobSortLabel(value) {
    const normalized = normalizeJobSort(value);
    if (normalized === "name_asc") return "job name";
    if (normalized === "status_asc") return "status";
    return "latest time";
  }

  function jobTimeValue(job) {
    const timestamp = Date.parse(String(job?.updated_at || job?.created_at || ""));
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function compareText(left, right) {
    return String(left || "").localeCompare(String(right || ""), undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }

  function jobStatusRank(status) {
    const normalized = String(status || "").trim().toLowerCase();
    const index = JOB_STATUS_SORT_ORDER.indexOf(normalized);
    return index === -1 ? JOB_STATUS_SORT_ORDER.length : index;
  }

  function sortJobs(jobs) {
    const normalizedSort = normalizeJobSort(byId("job-filter-sort")?.value || "time_desc");
    const items = Array.isArray(jobs) ? [...jobs] : [];
    items.sort((left, right) => {
      if (normalizedSort === "name_asc") {
        return (
          compareText(left?.required_capability, right?.required_capability) ||
          (jobTimeValue(right) - jobTimeValue(left)) ||
          compareText(left?.id, right?.id)
        );
      }
      if (normalizedSort === "status_asc") {
        return (
          (jobStatusRank(left?.status) - jobStatusRank(right?.status)) ||
          compareText(left?.required_capability, right?.required_capability) ||
          (jobTimeValue(right) - jobTimeValue(left)) ||
          compareText(left?.id, right?.id)
        );
      }
      return (
        (jobTimeValue(right) - jobTimeValue(left)) ||
        compareText(left?.required_capability, right?.required_capability) ||
        compareText(left?.id, right?.id)
      );
    });
    return items;
  }

  function renderMonitorSummary(payload) {
    const overview = byId("monitor-overview");
    const dispatcherShell = byId("dispatcher-summary");
    const dispatcherMeta = byId("dispatcher-summary-meta");
    const workerMeta = byId("worker-status-meta");
    const workerList = byId("worker-status-list");
    if (!overview || !dispatcherShell || !dispatcherMeta || !workerMeta || !workerList) return;

    const dispatcher = isPlainObject(payload?.dispatcher) ? payload.dispatcher : {};
    const workers = Array.isArray(payload?.workers) ? payload.workers : [];
    const readyJobs = Number(dispatcher.ready_jobs || 0);
    const inflightJobs = Number(dispatcher.inflight_jobs || 0);
    const attentionCount = Number(dispatcher.failed_jobs || 0) + Number(dispatcher.paused_jobs || 0) + Number(dispatcher.stale_workers || 0);
    const activeWorkers = Number(dispatcher.active_workers || 0);
    const totalWorkers = Number(dispatcher.total_workers || workers.length || 0);
    const queueState = String(dispatcher.queue_state || dispatcher.connection_status || "idle").trim().toLowerCase() || "idle";
    const connectionStatus = String(dispatcher.connection_status || "connected").trim().toLowerCase() || "connected";
    const dispatcherAddress = String(dispatcher.address || payload?.dispatcher_address || "").trim();
    const capabilityCounts = Array.isArray(dispatcher.capability_counts) ? dispatcher.capability_counts : [];
    const alerts = Array.isArray(dispatcher.alerts) ? dispatcher.alerts.filter(Boolean) : [];
    const jobCounts = isPlainObject(dispatcher.job_counts) ? dispatcher.job_counts : {};
    const workerCounts = isPlainObject(dispatcher.worker_counts) ? dispatcher.worker_counts : {};
    const workerFilter = normalizeWorkerStatusFilter(byId("worker-status-filter")?.value || state.worker_status_filter);
    state.worker_status_filter = workerFilter;
    const filteredWorkers = workerFilter === "all"
      ? workers
      : workers.filter(worker => String(worker?.health_status || worker?.status || "unknown").trim().toLowerCase() === workerFilter);

    overview.innerHTML = [
      {
        label: "Dispatcher",
        value: humanizeKey(connectionStatus),
        copy: dispatcherAddress
          ? `${humanizeKey(queueState)} queue state at ${dispatcherAddress}`
          : "Set a dispatcher address to start monitoring.",
      },
      {
        label: "Workers",
        value: String(activeWorkers),
        copy: `${totalWorkers} seen · ${Number(workerCounts.stale || 0)} stale · ${Number(workerCounts.offline || 0)} offline`,
      },
      {
        label: "Ready Queue",
        value: String(readyJobs),
        copy: `${inflightJobs} in flight · ${Number(dispatcher.total_jobs || 0)} total tracked jobs`,
      },
      {
        label: "Attention",
        value: String(attentionCount),
        copy: attentionCount
          ? `${Number(dispatcher.failed_jobs || 0)} failed · ${Number(dispatcher.paused_jobs || 0)} paused · ${Number(dispatcher.stale_workers || 0)} stale workers`
          : "No failed jobs, no paused jobs, and no stale worker heartbeats.",
      },
    ].map(card => `
      <article class="monitor-metric-card">
        <div class="monitor-metric-label">${escapeHtml(card.label)}</div>
        <div class="monitor-metric-value">${escapeHtml(card.value)}</div>
        <div class="monitor-metric-copy">${escapeHtml(card.copy)}</div>
      </article>
    `).join("");

    if (!dispatcherAddress && connectionStatus === "not_configured") {
      dispatcherMeta.textContent = "Dispatcher address required.";
    } else if (dispatcher.error) {
      dispatcherMeta.textContent = dispatcher.error;
    } else {
      dispatcherMeta.textContent = `${humanizeKey(connectionStatus)} · Last worker ${formatRelativeTime(dispatcher.last_worker_seen)} · Last job ${formatRelativeTime(dispatcher.last_job_update)}`;
    }

    dispatcherShell.innerHTML = `
      <section class="monitor-detail-card">
        <div class="monitor-detail-head">
          <div>
            <h3 class="monitor-detail-title">Dispatcher</h3>
            <div class="monitor-detail-subtitle">${escapeHtml(dispatcherAddress || "Dispatcher not configured.")}</div>
          </div>
          ${statusChipMarkup(queueState)}
        </div>
        <div class="monitor-detail-grid">
          ${monitorDetailItemMarkup("Connection", humanizeKey(connectionStatus))}
          ${monitorDetailItemMarkup("Queue State", humanizeKey(queueState))}
          ${monitorDetailItemMarkup("Last Worker Heartbeat", dispatcher.last_worker_seen ? `${formatTimestamp(dispatcher.last_worker_seen)} (${formatRelativeTime(dispatcher.last_worker_seen)})` : "No worker heartbeat yet")}
          ${monitorDetailItemMarkup("Last Job Update", dispatcher.last_job_update ? `${formatTimestamp(dispatcher.last_job_update)} (${formatRelativeTime(dispatcher.last_job_update)})` : "No job activity yet")}
          ${monitorDetailItemMarkup("Ready Jobs", String(readyJobs))}
          ${monitorDetailItemMarkup("In Flight", String(inflightJobs))}
          ${monitorDetailItemMarkup("Completed", String(dispatcher.completed_jobs || 0))}
          ${monitorDetailItemMarkup("Failed", String(dispatcher.failed_jobs || 0))}
          ${monitorDetailItemMarkup("Paused", String(dispatcher.paused_jobs || 0))}
          ${monitorDetailItemMarkup("Workers Seen", `${activeWorkers} online / ${totalWorkers} total`)}
        </div>
        ${
          capabilityCounts.length
            ? `<div class="monitor-chip-row">${capabilityCounts.map(entry => `
                <span class="monitor-chip">${escapeHtml(entry.capability || "Unknown")} · ${escapeHtml(String(entry.active || 0))} active · ${escapeHtml(String(entry.queued || 0))} queued</span>
              `).join("")}</div>`
            : ""
        }
        ${
          alerts.length
            ? `<div class="monitor-alert-list">${alerts.map(alert => `<div class="monitor-alert">${escapeHtml(alert)}</div>`).join("")}</div>`
            : ""
        }
        ${
          connectionStatus === "not_configured"
            ? `<div class="monitor-alert-list"><div class="monitor-alert">Point the boss at an dispatcher to load queue and worker telemetry.</div></div>`
            : ""
        }
        ${
          dispatcher.error && connectionStatus !== "not_configured"
            ? `<div class="monitor-alert-list"><div class="monitor-alert">${escapeHtml(dispatcher.error)}</div></div>`
            : ""
        }
      </section>
    `;

    const filterLabel = workerFilter === "all" ? "showing all workers" : `showing ${workerFilter} only`;
    workerMeta.textContent = `${totalWorkers} worker${totalWorkers === 1 ? "" : "s"} seen · ${activeWorkers} online · ${Number(workerCounts.stale || 0)} stale · ${Number(workerCounts.offline || 0)} offline · ${filterLabel}`;
    if (!workers.length) {
      workerList.innerHTML = `<div class="empty-state">${escapeHtml(
        connectionStatus === "not_configured"
          ? "Set a dispatcher address to load worker heartbeat data."
          : "No worker heartbeat rows returned by the dispatcher yet."
      )}</div>`;
      return;
    }

    if (!filteredWorkers.length) {
      workerList.innerHTML = `<div class="empty-state">${escapeHtml(
        workerFilter === "all"
          ? "No workers match the current roster view."
          : `No ${workerFilter} workers match the current filter.`
      )}</div>`;
      return;
    }

    workerList.innerHTML = filteredWorkers.map(worker => {
      const workerId = worker.worker_id || worker.id || worker.name || "";
      const workerName = worker.name || workerId || "Worker";
      const capabilities = Array.isArray(worker.capabilities) ? worker.capabilities : [];
      const activeJobs = resolveWorkerActiveJobs(worker);
      const activeJobIds = activeJobs
        .map((job, index) => String(job?.id || worker?.active_job_ids?.[index] || "").trim())
        .filter(Boolean);
      const healthStatus = String(worker.health_status || worker.status || "unknown").trim().toLowerCase() || "unknown";
      return `
        <section class="pulse-card worker-card">
          <div class="worker-card-head">
            <div>
              <div class="worker-card-title">${escapeHtml(workerName)}</div>
            </div>
            <div class="worker-card-head-actions">
              ${
                workerId
                  ? `
                    <button
                      type="button"
                      class="monitor-chip monitor-chip-button"
                      data-worker-history="${escapeHtml(workerId)}"
                      data-worker-name="${escapeHtml(workerName)}"
                    >
                      Work History
                    </button>
                  `
                  : ""
              }
              ${statusChipMarkup(healthStatus)}
            </div>
          </div>
          <div class="worker-card-summary">
            <div class="worker-card-line">
              <span class="worker-card-inline-item">
                <span class="worker-card-inline-label">Address</span>
                <span class="worker-card-inline-value is-mono">${escapeHtml(worker.address || "Unset")}</span>
              </span>
            </div>
            <div class="worker-card-line worker-card-line-split">
              <span class="worker-card-inline-item">
                <span class="worker-card-inline-label">Active Jobs</span>
                <span class="worker-card-inline-value">${escapeHtml(workerActiveJobsPreview(activeJobs))}</span>
              </span>
              <span class="worker-card-inline-item">
                <span class="worker-card-inline-label">Heartbeat Age</span>
                <span class="worker-card-inline-value">${escapeHtml(formatSeconds(worker.heartbeat_age_sec))}</span>
              </span>
            </div>
          </div>
          ${
            activeJobIds.length
              ? `<div class="worker-card-pills worker-card-actions-row">${activeJobs.map((job, index) => {
                  const jobId = String(job?.id || activeJobIds[index] || "").trim();
                  if (!jobId) return "";
                  return `
                    <button
                      type="button"
                      class="monitor-chip monitor-chip-button"
                      data-worker-job-detail="${escapeHtml(jobId)}"
                    >
                      Job Detail · ${escapeHtml(workerActiveJobButtonLabel(job, index))}
                    </button>
                  `;
                }).join("")}</div>`
              : `<div class="worker-card-empty-row">No active worker jobs.</div>`
          }
          ${workerCapabilitiesMarkup(capabilities)}
        </section>
      `;
    }).join("");
  }

  async function loadMonitorSummary() {
    if (monitorSummaryInFlight) return;
    monitorSummaryInFlight = true;
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      const suffix = query.toString();
      const payload = await fetchJson(`/api/monitor/summary${suffix ? `?${suffix}` : ""}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      state.monitor_summary = payload.dispatcher || null;
      state.monitor_workers = Array.isArray(payload.workers) ? payload.workers : [];
      renderMonitorSummary(payload);
    } catch (error) {
      const dispatcherMeta = byId("dispatcher-summary-meta");
      const dispatcherShell = byId("dispatcher-summary");
      const workerMeta = byId("worker-status-meta");
      const workerList = byId("worker-status-list");
      if (dispatcherMeta) dispatcherMeta.textContent = error.message || "Unable to load dispatcher status.";
      if (dispatcherShell) dispatcherShell.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Unable to load dispatcher status.")}</div>`;
      if (workerMeta) workerMeta.textContent = "Worker telemetry unavailable.";
      if (workerList) workerList.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Unable to load worker status.")}</div>`;
    } finally {
      monitorSummaryInFlight = false;
    }
  }

  async function loadMonitorPageData() {
    await Promise.allSettled([loadMonitorSummary(), loadJobs()]);
  }

  function syncMonitorModalOpenState() {
    document.body.classList.toggle(
      "monitor-modal-open",
      Boolean(
        state.worker_job_modal_open
        || state.worker_history_modal_open
        || state.schedule_history_modal_open
      )
    );
  }

  function setWorkerJobModalOpen(isOpen) {
    state.worker_job_modal_open = Boolean(isOpen);
    const modal = byId("worker-job-modal");
    if (modal) {
      modal.hidden = !state.worker_job_modal_open;
    }
    syncMonitorModalOpenState();
  }

  function closeWorkerJobModal() {
    state.worker_job_modal_job_id = "";
    setWorkerJobModalOpen(false);
  }

  function setWorkerHistoryModalOpen(isOpen) {
    state.worker_history_modal_open = Boolean(isOpen);
    const modal = byId("worker-history-modal");
    if (modal) {
      modal.hidden = !state.worker_history_modal_open;
    }
    syncMonitorModalOpenState();
  }

  function closeWorkerHistoryModal() {
    state.worker_history_modal_worker_id = "";
    state.worker_history_modal_worker_name = "";
    setWorkerHistoryModalOpen(false);
  }

  function setScheduleHistoryModalOpen(isOpen) {
    state.schedule_history_modal_open = Boolean(isOpen);
    const modal = byId("schedule-history-modal");
    if (modal) {
      modal.hidden = !state.schedule_history_modal_open;
    }
    syncMonitorModalOpenState();
  }

  function closeScheduleHistoryModal() {
    state.schedule_history_modal_schedule_id = "";
    state.schedule_history_modal_schedule_name = "";
    setScheduleHistoryModalOpen(false);
  }

  async function openWorkerJobDetailModal(jobId) {
    const normalizedJobId = String(jobId || "").trim();
    if (!normalizedJobId) return;
    state.worker_job_modal_job_id = normalizedJobId;
    const meta = byId("worker-job-modal-meta");
    setWorkerJobModalOpen(true);
    if (meta) meta.textContent = "Loading current job detail...";
    renderJobDetailLoading("Loading current job detail...", "worker-job-modal-body");
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      const suffix = query.toString();
      const payload = await fetchJson(`/api/jobs/${encodeURIComponent(normalizedJobId)}${suffix ? `?${suffix}` : ""}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      if (state.worker_job_modal_job_id !== normalizedJobId) return;
      if (meta) {
        meta.textContent = buildJobMetaLabel(payload?.job || {}, { fallbackName: "Current Job" });
      }
      const shell = byId("worker-job-modal-body");
      if (shell) shell.innerHTML = buildJobDetailMarkup(payload);
    } catch (error) {
      if (state.worker_job_modal_job_id !== normalizedJobId) return;
      if (meta) meta.textContent = "Unable to load current job detail.";
      renderJobDetailError(error.message || "Unable to load current job detail.", "worker-job-modal-body");
    }
  }

  async function loadWorkerHistory(workerId, options = {}) {
    const normalizedWorkerId = String(workerId || "").trim();
    if (!normalizedWorkerId) return;
    const workerName = String(options.workerName || state.worker_history_modal_worker_name || normalizedWorkerId).trim();
    state.worker_history_modal_worker_id = normalizedWorkerId;
    state.worker_history_modal_worker_name = workerName;
    const meta = byId("worker-history-modal-meta");
    if (meta) meta.textContent = `Loading recent work history for ${workerName}...`;
    renderJobDetailLoading("Loading recent work history...", "worker-history-modal-body");
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      query.set("limit", "10");
      const suffix = query.toString();
      const payload = await fetchJson(`/api/workers/${encodeURIComponent(normalizedWorkerId)}/history${suffix ? `?${suffix}` : ""}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      if (state.worker_history_modal_worker_id !== normalizedWorkerId) return;
      renderWorkerHistory(payload);
    } catch (error) {
      if (state.worker_history_modal_worker_id !== normalizedWorkerId) return;
      if (meta) meta.textContent = "Unable to load work history.";
      renderJobDetailError(error.message || "Unable to load work history.", "worker-history-modal-body");
    }
  }

  async function openWorkerHistoryModal(workerId, workerName = "") {
    const normalizedWorkerId = String(workerId || "").trim();
    if (!normalizedWorkerId) return;
    state.worker_history_modal_worker_id = normalizedWorkerId;
    state.worker_history_modal_worker_name = String(workerName || normalizedWorkerId).trim() || normalizedWorkerId;
    setWorkerHistoryModalOpen(true);
    await loadWorkerHistory(normalizedWorkerId, { workerName: state.worker_history_modal_worker_name });
  }

  function currentDispatcherAddress() {
    return (byId("jobs-dispatcher-address")?.value || state.dispatcher_address || "").trim();
  }

  function canPauseJob(job) {
    const status = String(job?.status || "").trim().toLowerCase();
    return status === "queued" || status === "retry" || status === "unfinished";
  }

  function canStopJob(job) {
    const status = String(job?.status || "").trim().toLowerCase();
    return status === "claimed";
  }

  function canResumeJob(job) {
    const status = String(job?.status || "").trim().toLowerCase();
    return status === "paused" || status === "stopped";
  }

  function canCancelJob(job) {
    const status = String(job?.status || "").trim().toLowerCase();
    return Boolean(job) && !["claimed", "stopping", "completed", "cancelled", "deleted"].includes(status);
  }

  function updateJobActionButtons(job) {
    const pauseButton = byId("job-pause");
    const stopButton = byId("job-stop");
    const resumeButton = byId("job-resume");
    const cancelButton = byId("job-cancel");
    const statusChip = byId("job-action-status-chip");
    if (pauseButton) pauseButton.disabled = !canPauseJob(job);
    if (stopButton) stopButton.disabled = !canStopJob(job);
    if (resumeButton) resumeButton.disabled = !canResumeJob(job);
    if (cancelButton) cancelButton.disabled = !canCancelJob(job);
    if (!statusChip) return;
    if (!job) {
      setStatus("job-action-status-chip", "Awaiting Selection", "muted");
      return;
    }
    const status = String(job.status || "unknown").trim().toLowerCase();
    const mode = status === "completed" ? "success" : (status === "failed" || status === "cancelled" || status === "deleted" ? "error" : (status === "claimed" || status === "stopping" || status === "paused" || status === "unfinished" ? "loading" : "muted"));
    setStatus("job-action-status-chip", `Job ${status || "unknown"}`, mode);
  }

  function setDispatcherAddress(value) {
    const normalized = String(value || "").trim();
    [byId("dispatcher-address"), byId("schedule-dispatcher-address"), byId("jobs-dispatcher-address"), byId("settings-dispatcher-address"), byId("db-dispatcher-address")].forEach(el => {
      if (el && el.value !== normalized) el.value = normalized;
    });
    const dispatcherSelect = byId("settings-dispatcher-select");
    if (dispatcherSelect) {
      const hasOption = Array.from(dispatcherSelect.options || []).some(option => option.value === normalized);
      dispatcherSelect.value = hasOption ? normalized : "";
    }
    const chip = byId("dispatcher-address-chip");
    if (chip) chip.textContent = `Dispatcher: ${normalized || 'Unset'}`;
    state.dispatcher_address = normalized;
    state.settings.dispatcher_address = normalized;
    renderRuntimeSummary();
  }

  function applyIssueParametersCollapsed(collapsed) {
    state.issue_parameters_collapsed = Boolean(collapsed);
    const field = byId("job-parameters-field");
    const body = byId("job-parameters-body");
    const toggle = byId("job-parameters-toggle");
    const glyph = byId("job-parameters-toggle-glyph");
    const text = byId("job-parameters-toggle-text");
    if (field) {
      field.classList.toggle("is-collapsed", state.issue_parameters_collapsed);
    }
    if (body) {
      body.hidden = state.issue_parameters_collapsed;
    }
    if (toggle) {
      toggle.setAttribute("aria-expanded", state.issue_parameters_collapsed ? "false" : "true");
      toggle.setAttribute("aria-label", state.issue_parameters_collapsed ? "Expand parameters" : "Collapse parameters");
    }
    if (glyph) glyph.textContent = state.issue_parameters_collapsed ? "+" : "-";
    if (text) text.textContent = state.issue_parameters_collapsed ? "Expand" : "Collapse";
  }

  function toggleIssueParameters() {
    applyIssueParametersCollapsed(!state.issue_parameters_collapsed);
  }

  function applyMonitorPanelCollapsed(collapsed) {
    state.monitor_panel_collapsed = Boolean(collapsed);
    const panel = byId("monitor-control-panel");
    const toggle = byId("monitor-panel-toggle");
    const glyph = byId("monitor-panel-toggle-glyph");
    const text = byId("monitor-panel-toggle-text");
    if (panel) {
      panel.classList.toggle("is-collapsed", state.monitor_panel_collapsed);
    }
    if (toggle) {
      toggle.setAttribute("aria-expanded", state.monitor_panel_collapsed ? "false" : "true");
      toggle.setAttribute("aria-label", state.monitor_panel_collapsed ? "Expand operations monitor" : "Collapse operations monitor");
    }
    if (glyph) glyph.textContent = state.monitor_panel_collapsed ? "+" : "-";
    if (text) text.textContent = state.monitor_panel_collapsed ? "Expand" : "Collapse";
  }

  function toggleMonitorPanel() {
    applyMonitorPanelCollapsed(!state.monitor_panel_collapsed);
  }

  function switchMonitorTab(tabId) {
    const normalized = ["jobs", "dispatcher", "workers"].includes(String(tabId || "").trim().toLowerCase())
      ? String(tabId || "").trim().toLowerCase()
      : "jobs";
    state.monitor_tab = normalized;
    document.querySelectorAll("[data-monitor-tab]").forEach(button => {
      const isActive = button.getAttribute("data-monitor-tab") === normalized;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    document.querySelectorAll("[data-monitor-panel]").forEach(panel => {
      panel.classList.toggle("is-active", panel.getAttribute("data-monitor-panel") === normalized);
    });
  }

  function switchDbTab(tabId) {
    const normalized = ["viewer", "sql"].includes(String(tabId || "").trim().toLowerCase())
      ? String(tabId || "").trim().toLowerCase()
      : "viewer";
    state.db_tab = normalized;
    document.querySelectorAll("[data-db-tab]").forEach(button => {
      const isActive = button.getAttribute("data-db-tab") === normalized;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    document.querySelectorAll("[data-db-panel]").forEach(panel => {
      panel.classList.toggle("is-active", panel.getAttribute("data-db-panel") === normalized);
    });
  }

  function applySidebarState(collapsed) {
    state.sidebar_collapsed = Boolean(collapsed);
    document.body.setAttribute("data-sidebar", state.sidebar_collapsed ? "collapsed" : "expanded");
    const toggle = byId("sidebar-toggle");
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", state.sidebar_collapsed ? "false" : "true");
    toggle.setAttribute("aria-label", state.sidebar_collapsed ? "Expand sidebar" : "Collapse sidebar");
    const glyph = toggle.querySelector(".sidebar-toggle-glyph");
    const text = toggle.querySelector(".sidebar-toggle-text");
    if (glyph) glyph.textContent = state.sidebar_collapsed ? "⇥" : "⇤";
    if (text) text.textContent = state.sidebar_collapsed ? "Expand" : "Collapse";
  }

  function toggleSidebar() {
    applySidebarState(!state.sidebar_collapsed);
    writeStoredSidebarCollapsed(state.sidebar_collapsed);
  }

  function switchPage(pageId) {
    state.current_page = pageId;
    document.body.setAttribute("data-page", pageId);
    document.querySelectorAll("[data-page-link]").forEach(link => {
      link.classList.toggle("is-active", link.getAttribute("data-page-link") === pageId);
    });
    // Update URL without reloading if needed, but here we just show/hide
    syncMonitorAutoRefresh();
    if (pageId === "schedule") {
      loadSchedules();
    }
    if (pageId === "monitor") {
      loadMonitorPageData();
    }
    if (pageId === "db") {
      loadDbTables().then(() => loadSelectedTable());
    }
  }

  function renderRuntimeSummary() {
    const rs = state.runtime_summary || {};
    if (byId("settings-boss-name")) byId("settings-boss-name").textContent = rs.boss_name || "Dispatcher Boss";
    if (byId("settings-agent-id")) byId("settings-agent-id").textContent = rs.agent_id || "Not registered";
    if (byId("settings-plaza-url")) byId("settings-plaza-url").textContent = rs.plaza_url || state.settings.plaza_url || "Not configured";
    if (byId("settings-current-party")) byId("settings-current-party").textContent = state.dispatcher_party || rs.dispatcher_party || "Not configured";
    if (byId("settings-current-dispatcher")) byId("settings-current-dispatcher").textContent = state.dispatcher_address || "Not configured";
    if (byId("settings-dispatcher-count")) byId("settings-dispatcher-count").textContent = String((state.plaza_dispatchers || []).length);
    if (byId("settings-plaza-detail")) byId("settings-plaza-detail").textContent = JSON.stringify(state.plaza_status || {}, null, 2);
  }

  async function refreshPlazaStatus() {
    try {
      const query = new URLSearchParams();
      const dispatcherParty = currentDispatcherParty();
      if (dispatcherParty) query.set("dispatcher_party", dispatcherParty);
      const payload = await fetchJson(`/api/plaza/status${query.toString() ? `?${query.toString()}` : ""}`);
      syncPlazaDirectory(payload || {});
      if (payload?.plaza_url) {
        state.runtime_summary.plaza_url = payload.plaza_url;
      }
      if (payload?.agent_id) {
        state.runtime_summary.agent_id = payload.agent_id;
      }
      renderRuntimeSummary();
      updateHeroConnectButton(payload || {});
      return payload;
    } catch (error) {
      updateHeroConnectButton({
        connection_status: "disconnected",
        plaza_url: resolvePreferredPlazaUrl(),
        error: error.message,
      });
      return null;
    }
  }

  async function loadHeroMetrics() {
    if (heroMetricsInFlight) return;
    heroMetricsInFlight = true;
    setHeroMetricsRefreshState(true);

    if (!state.hero_metrics || String(state.hero_metrics.status || "").trim().toLowerCase() === "idle") {
      renderHeroMetrics(Object.assign({}, state.hero_metrics || {}, { status: "loading" }));
    }

    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      const suffix = query.toString();
      const metricsUrl = `/api/metrics/summary${suffix ? `?${suffix}` : ""}`;
      const monitorUrl = `/api/monitor/summary${suffix ? `?${suffix}` : ""}`;
      const [metricsResult, monitorResult] = await Promise.allSettled([
        fetchJson(metricsUrl),
        fetchJson(monitorUrl),
      ]);

      const metricsPayload = metricsResult.status === "fulfilled" ? metricsResult.value : null;
      const monitorPayload = monitorResult.status === "fulfilled" ? monitorResult.value : null;
      if (!metricsPayload && !monitorPayload) {
        throw new Error("Unable to load dispatcher metrics.");
      }

      if (metricsPayload?.dispatcher_address) setDispatcherAddress(metricsPayload.dispatcher_address);
      if (monitorPayload?.dispatcher_address) setDispatcherAddress(monitorPayload.dispatcher_address);

      const nextSummary = Object.assign(
        {},
        state.hero_metrics || initial.hero_metrics || {},
        metricsPayload || {},
        {
          operational_metrics: monitorPayload ? buildOperationalHeroMetrics(monitorPayload) : [],
        }
      );

      if (!metricsPayload && monitorPayload) {
        const connectionStatus = String(monitorPayload?.dispatcher?.connection_status || "unknown").trim().toLowerCase() || "unknown";
        nextSummary.status = connectionStatus === "connected" ? "success" : connectionStatus;
        nextSummary.error = String(monitorPayload?.dispatcher?.error || "").trim();
      }

      if (monitorPayload) {
        state.monitor_summary = monitorPayload.dispatcher || state.monitor_summary;
        state.monitor_workers = Array.isArray(monitorPayload.workers) ? monitorPayload.workers : state.monitor_workers;
      }

      state.hero_metrics = nextSummary;
      renderHeroMetrics(nextSummary);
    } catch (error) {
      state.hero_metrics = Object.assign(
        {},
        state.hero_metrics || initial.hero_metrics || {},
        {
          status: "unreachable",
          dispatcher_address: currentDispatcherAddress(),
          error: error.message || "Unable to load dispatcher metrics.",
        }
      );
      renderHeroMetrics(state.hero_metrics);
    } finally {
      heroMetricsInFlight = false;
      setHeroMetricsRefreshState(false);
    }
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Request failed.");
    return payload;
  }

  async function connectPlaza() {
    const url = resolvePreferredPlazaUrl();
    if (!url) return;
    syncPlazaUrlState(url);
    const dispatcherParty = currentDispatcherParty();
    const heroButton = byId("hero-connect-plaza");
    if (heroButton) {
      heroButton.disabled = true;
      heroButton.textContent = "Connecting...";
    }
    setStatus("settings-status-chip", "Connecting", "loading");
    try {
       const payload = await fetchJson("/api/plaza/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plaza_url: url,
          dispatcher_party: dispatcherParty,
          dispatcher_address: state.dispatcher_address || "",
        }),
      });
      syncPlazaDirectory(payload.plaza_status || {});
      state.runtime_summary.plaza_url = url;
      state.runtime_summary.agent_id = payload?.plaza_status?.agent_id || state.runtime_summary.agent_id;
      if (payload?.runtime_summary) {
        state.runtime_summary = Object.assign({}, state.runtime_summary, payload.runtime_summary);
      }
      if (payload?.dispatcher_address) {
        setDispatcherAddress(payload.dispatcher_address);
      }
      
      // The shared connector will pick up the change on next poll or we can trigger it
      if (window.agentConnection?.plazaRef) {
          window.agentConnection.plazaRef.refresh();
      }
      
      setStatus("settings-status-chip", "Connected", "success");
      renderRuntimeSummary();
      updateHeroConnectButton(state.plaza_status);
      await refreshPlazaStatus();
    } catch (error) {
      setStatus("settings-status-chip", "Failed", "error");
      updateHeroConnectButton({
        connection_status: "disconnected",
        plaza_url: url,
        error: error.message,
      });
    } finally {
      if (heroButton) {
        heroButton.disabled = false;
      }
    }
  }

  async function handleJobSubmit(event) {
    event.preventDefault();
    setStatus("boss-status-chip", "Submitting", "loading");
    try {
      const option = currentIssueJobOption();
      const parsedPriority = Number.parseInt(
        String(byId("priority")?.value || jobOptionDefaultPriority(option)),
        10
      );
      const targets = jobOptionRequiresSymbols(option)
        ? String(byId("symbols")?.value || state.issue_symbols_value || "").split(",").map(s => s.trim()).filter(Boolean)
        : [];
      const payload = {
        dispatcher_address: byId("dispatcher-address").value.trim(),
        required_capability: byId("required-capability").value,
        targets,
        priority: Number.isFinite(parsedPriority) ? parsedPriority : 100,
        payload: JSON.parse(byId("payload-json").value || "{}"),
      };
      setDispatcherAddress(payload.dispatcher_address);
      const res = await fetchJson("/api/jobs/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus("boss-status-chip", "Issued", "success");
      renderBossSubmitResult(res);
    } catch (error) {
      setStatus("boss-status-chip", "Error", "error");
      renderBossSubmitError(error.message);
    }
  }

  function localDateTimeValueFromNow(offsetMinutes) {
    const date = new Date(Date.now() + (offsetMinutes * 60 * 1000));
    const timezoneOffsetMs = date.getTimezoneOffset() * 60 * 1000;
    return new Date(date.getTime() - timezoneOffsetMs).toISOString().slice(0, 16);
  }

  function browserTimeZone() {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  }

  function currentScheduleRepeatFrequency() {
    return byId("schedule-repeat-frequency")?.value || "once";
  }

  function splitScheduleListValue(rawValue) {
    return Array.from(new Set(
      String(rawValue || "")
        .split(/[\n,]/)
        .map(part => part.trim())
        .filter(Boolean)
    ));
  }

  function collectScheduleTimes() {
    const values = splitScheduleListValue(byId("schedule-times")?.value || "");
    values.forEach(value => {
      if (!/^\d{1,2}:\d{2}$/.test(value)) {
        throw new Error("Run Times must use comma-separated HH:MM values.");
      }
    });
    return values;
  }

  function collectScheduleWeekdays() {
    return Array.from(document.querySelectorAll('input[name="schedule_weekday"]:checked'))
      .map(input => String(input.value || "").trim())
      .filter(Boolean);
  }

  function collectScheduleDaysOfMonth() {
    const rawValues = splitScheduleListValue(byId("schedule-days-of-month")?.value || "");
    return rawValues.map(value => {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isInteger(parsed) || parsed < 1 || parsed > 31) {
        throw new Error("Days Of Month must be comma-separated numbers between 1 and 31.");
      }
      return parsed;
    });
  }

  function scheduleTimesForRule(schedule) {
    if (Array.isArray(schedule.schedule_times) && schedule.schedule_times.length) {
      return schedule.schedule_times.map(value => String(value || "").trim()).filter(Boolean);
    }
    const fallback = String(schedule.schedule_time || "").trim();
    return fallback ? [fallback] : [];
  }

  function scheduleDaysForRule(schedule) {
    if (Array.isArray(schedule.schedule_days_of_month) && schedule.schedule_days_of_month.length) {
      return schedule.schedule_days_of_month
        .map(value => Number.parseInt(String(value), 10))
        .filter(value => Number.isInteger(value));
    }
    const fallback = Number.parseInt(String(schedule.schedule_day_of_month || ""), 10);
    return Number.isInteger(fallback) ? [fallback] : [];
  }

  function formatScheduleRule(schedule) {
    const frequency = String(schedule.repeat_frequency || "once").trim().toLowerCase();
    const scheduleTimes = scheduleTimesForRule(schedule);
    const timeLabel = scheduleTimes.length ? scheduleTimes.join(", ") : "--:--";
    const scheduleIntervalMinutes = Number.parseInt(
      String(schedule.schedule_interval_minutes || schedule.metadata?.schedule_interval_minutes || ""),
      10
    );
    if (frequency === "daily") {
      return `Daily at ${timeLabel} (${schedule.schedule_timezone || "UTC"})`;
    }
    if (frequency === "weekly") {
      const days = Array.isArray(schedule.schedule_weekdays) ? schedule.schedule_weekdays.join(", ").toUpperCase() : "";
      return `Weekly on ${days || "?"} at ${timeLabel} (${schedule.schedule_timezone || "UTC"})`;
    }
    if (frequency === "monthly") {
      const days = scheduleDaysForRule(schedule);
      return `Monthly on days ${days.length ? days.join(", ") : "?"} at ${timeLabel} (${schedule.schedule_timezone || "UTC"})`;
    }
    if (frequency === "interval") {
      const startAt = schedule.metadata?.interval_start_at || schedule.scheduled_for;
      return `Every ${Number.isInteger(scheduleIntervalMinutes) ? scheduleIntervalMinutes : "?"} minutes from ${formatTimestamp(startAt)} (${schedule.schedule_timezone || "UTC"})`;
    }
    return `Once at ${formatTimestamp(schedule.scheduled_for)}`;
  }

  function syncScheduleTimezoneNote() {
    const note = byId("schedule-timezone-note");
    if (!note) return;
    note.textContent = `Schedules use your browser time zone: ${browserTimeZone()}.`;
  }

  function setScheduleRepeatFrequency(value) {
    const normalized = String(value || "once").trim().toLowerCase();
    const form = byId("schedule-job-form");
    const select = byId("schedule-repeat-frequency");
    if (form) form.setAttribute("data-repeat-frequency", normalized);
    if (select && select.value !== normalized) select.value = normalized;
  }

  function formatScheduleSummary(schedule) {
    if (schedule.last_error) return `Last Error: ${schedule.last_error}`;
    if (schedule.dispatcher_job_id) return "Most recent issue completed through the boss agent.";
    return "Waiting for the boss scheduler to issue this job.";
  }

  async function handleScheduleSubmit(event) {
    event.preventDefault();
    setStatus("schedule-status-chip", "Saving", "loading");
    try {
      const repeatFrequency = currentScheduleRepeatFrequency();
      const scheduleTimes = (repeatFrequency === "once" || repeatFrequency === "interval") ? [] : collectScheduleTimes();
      const scheduleDaysOfMonth = repeatFrequency === "monthly" ? collectScheduleDaysOfMonth() : [];
      const rawScheduleIntervalMinutes = byId("schedule-interval-minutes")?.value || "";
      const scheduleIntervalMinutes = repeatFrequency === "interval"
        ? Number.parseInt(rawScheduleIntervalMinutes, 10)
        : null;
      const rawScheduleAt = byId("schedule-at")?.value || "";
      const scheduleAt = rawScheduleAt ? new Date(rawScheduleAt) : null;
      if ((repeatFrequency === "once" || repeatFrequency === "interval") && (!scheduleAt || Number.isNaN(scheduleAt.getTime()))) {
        throw new Error("Run At is required for one-time schedules.");
      }
      if (repeatFrequency !== "once" && !scheduleTimes.length) {
        if (repeatFrequency !== "interval") {
          throw new Error("At least one Run Time is required for repeating schedules.");
        }
      }
      if (repeatFrequency === "interval" && (!Number.isInteger(scheduleIntervalMinutes) || scheduleIntervalMinutes < 1)) {
        throw new Error("Interval Minutes must be a whole number greater than 0.");
      }
      if (repeatFrequency === "weekly" && !collectScheduleWeekdays().length) {
        throw new Error("Select at least one day of week for weekly schedules.");
      }
      if (repeatFrequency === "monthly" && !scheduleDaysOfMonth.length) {
        throw new Error("At least one Day Of Month is required for monthly schedules.");
      }

      const payload = {
        dispatcher_address: byId("schedule-dispatcher-address")?.value.trim() || "",
        name: byId("schedule-name")?.value.trim() || "",
        required_capability: byId("schedule-required-capability")?.value || "",
        repeat_frequency: repeatFrequency,
        schedule_timezone: browserTimeZone(),
        schedule_time: scheduleTimes[0] || "",
        schedule_times: scheduleTimes,
        schedule_weekdays: collectScheduleWeekdays(),
        schedule_day_of_month: scheduleDaysOfMonth[0] || null,
        schedule_days_of_month: scheduleDaysOfMonth,
        schedule_interval_minutes: scheduleIntervalMinutes,
        scheduled_for: scheduleAt && !Number.isNaN(scheduleAt.getTime()) ? scheduleAt.toISOString() : "",
        targets: (byId("schedule-symbols")?.value || "").split(",").map(s => s.trim()).filter(Boolean),
        payload: JSON.parse(byId("schedule-payload-json")?.value || "{}"),
      };
      setDispatcherAddress(payload.dispatcher_address);
      await fetchJson("/api/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus("schedule-status-chip", "Scheduled", "success");
      await loadSchedules();
    } catch (error) {
      setStatus("schedule-status-chip", "Error", "error");
      byId("schedule-list-meta").textContent = error.message || "Unable to create schedule.";
    }
  }

  function renderScheduleList(schedules) {
    const list = byId("schedule-list");
    const meta = byId("schedule-list-meta");
    if (!list || !meta) return;
    meta.textContent = `${schedules.length} schedule${schedules.length === 1 ? "" : "s"} found.`;
    if (!schedules.length) {
      list.innerHTML = '<div class="empty-state">No scheduled jobs saved yet.</div>';
      return;
    }

    list.innerHTML = schedules.map(schedule => `
      <section class="pulse-card schedule-card" data-schedule-id="${escapeHtml(schedule.id)}" data-schedule-name="${escapeHtml(schedule.name || schedule.required_capability || "Scheduled Job")}">
        <div class="pulse-card-line">
          <span class="pulse-card-title">${escapeHtml(schedule.name || schedule.required_capability || "Scheduled Job")}</span>
          ${statusChipMarkup(schedule.status || "scheduled")}
        </div>
        <div class="pulse-card-subtitle">${escapeHtml(schedule.required_capability || "")}</div>
        <div class="schedule-card-grid">
          <div class="schedule-card-column">
            <div class="schedule-card-detail"><strong>Rule:</strong> ${escapeHtml(formatScheduleRule(schedule))}</div>
            <div class="schedule-card-detail"><strong>Next:</strong> ${escapeHtml(formatTimestamp(schedule.scheduled_for))}</div>
            <div class="schedule-card-detail"><strong>Attempts:</strong> ${escapeHtml(String(schedule.issue_attempts || 0))}</div>
          </div>
          <div class="schedule-card-column">
            <div class="schedule-card-detail"><strong>Targets:</strong> ${escapeHtml(jobTargets(schedule).join(", ") || "None")}</div>
            <div class="schedule-card-detail"><strong>Issued:</strong> ${escapeHtml(formatTimestamp(schedule.issued_at))}</div>
            <div class="schedule-card-detail"><strong>Latest Job:</strong> ${escapeHtml(schedule.dispatcher_job_id ? shortJobId(schedule.dispatcher_job_id) : "Unset")}</div>
          </div>
          <div class="schedule-card-column">
            <div class="schedule-card-detail"><strong>Dispatcher:</strong> ${escapeHtml(schedule.dispatcher_address || "Unset")}</div>
            <div class="schedule-card-detail"><strong>Updated:</strong> ${escapeHtml(formatTimestamp(schedule.updated_at))}</div>
            <div class="schedule-card-detail"><strong>Note:</strong> ${escapeHtml(formatScheduleSummary(schedule))}</div>
          </div>
        </div>
        <div class="schedule-card-actions">
          <button type="button" class="ghost-btn" data-schedule-action="history">Job History</button>
          <button type="button" class="ghost-btn" data-schedule-action="issue">Issue Now</button>
          <button type="button" class="danger-btn" data-schedule-action="delete">Delete</button>
        </div>
      </section>
    `).join("");
  }

  async function loadSchedules() {
    setStatus("schedule-status-chip", "Syncing", "loading");
    try {
      const payload = await fetchJson("/api/schedules");
      state.schedules = payload.schedules || [];
      renderScheduleList(state.schedules);
      setStatus("schedule-status-chip", "Live", "success");
    } catch (error) {
      setStatus("schedule-status-chip", "Error", "error");
      const list = byId("schedule-list");
      if (list) {
        list.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Unable to load schedules.")}</div>`;
      }
    }
  }

  async function controlSchedule(scheduleId, action) {
    if (!scheduleId) return;
    if (action === "delete" && !window.confirm(`Delete scheduled job ${shortJobId(scheduleId)}?`)) {
      return;
    }
    const label = action === "issue" ? "Issuing" : "Deleting";
    setStatus("schedule-status-chip", label, "loading");
    try {
      await fetchJson(`/api/schedules/${encodeURIComponent(scheduleId)}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setStatus("schedule-status-chip", action === "issue" ? "Issued" : "Deleted", action === "issue" ? "success" : "error");
      if (action === "delete" && state.schedule_history_modal_open && state.schedule_history_modal_schedule_id === scheduleId) {
        closeScheduleHistoryModal();
      }
      await loadSchedules();
      if (action === "issue" && state.schedule_history_modal_open && state.schedule_history_modal_schedule_id === scheduleId) {
        await loadScheduleHistory(scheduleId, { scheduleName: state.schedule_history_modal_schedule_name });
      }
    } catch (error) {
      setStatus("schedule-status-chip", "Action Failed", "error");
      byId("schedule-list-meta").textContent = error.message || "Unable to update schedule.";
    }
  }

  async function loadJobs() {
    if (monitorRefreshInFlight) {
      pendingJobRefresh = true;
      return;
    }
    monitorRefreshInFlight = true;
    pendingJobRefresh = false;
    setStatus("jobs-status-chip", "Syncing", "loading");
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (!dispatcher) {
        state.jobs = [];
        state.selected_job_id = "";
        state.selected_job = null;
        state.selected_job_raw_records = [];
        updateJobActionButtons(null);
        renderJobList(state.jobs);
        setStatus("jobs-status-chip", "Needs Setup", "muted");
        const meta = byId("jobs-list-meta");
        if (meta) meta.textContent = "Set a dispatcher address to browse queue activity.";
        renderJobDetailEmpty("Select a dispatcher to inspect queue activity.");
        return;
      }
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      ["status", "capability", "search"].forEach(f => {
          const val = byId(`job-filter-${f}`)?.value.trim();
          if (val) query.set(f, val);
      });
      const payload = await fetchJson(`/api/jobs?${query.toString()}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      state.jobs = sortJobs(payload.jobs || []);
      const selectedJobSummary = state.selected_job_id
        ? state.jobs.find(job => job.id === state.selected_job_id) || null
        : null;
      if (state.selected_job_id && !selectedJobSummary) {
        state.selected_job_id = "";
        state.selected_job = null;
        state.selected_job_raw_records = [];
        updateJobActionButtons(null);
        byId("job-detail-meta").textContent = "Select a job.";
        renderJobDetailEmpty("Select a job to inspect its state.");
      } else if (selectedJobSummary) {
        const previousStatus = String(state.selected_job?.status || "").trim().toLowerCase();
        const previousUpdatedAt = String(state.selected_job?.updated_at || "").trim();
        state.selected_job = Object.assign({}, state.selected_job || {}, selectedJobSummary);
        updateJobActionButtons(state.selected_job);
        renderJobDetailResponse({
          job: state.selected_job,
          raw_records: state.selected_job_raw_records,
        });
        byId("job-detail-meta").textContent = buildJobMetaLabel(state.selected_job, { fallbackName: "Current Job" });
        const nextStatus = String(selectedJobSummary.status || "").trim().toLowerCase();
        const nextUpdatedAt = String(selectedJobSummary.updated_at || "").trim();
        if ((previousStatus !== nextStatus || previousUpdatedAt !== nextUpdatedAt) && !jobDetailRefreshInFlight) {
          void loadJobDetail(state.selected_job_id, { background: true });
        }
      }
      renderJobList(state.jobs);
      setStatus("jobs-status-chip", "Live", "success");
    } catch (error) {
      console.error("Failed to load jobs:", error);
      state.jobs = [];
      state.selected_job = null;
      state.selected_job_raw_records = [];
      updateJobActionButtons(null);
      renderJobList(state.jobs);
      const meta = byId("jobs-list-meta");
      if (meta) meta.textContent = error.message || "Unable to load jobs.";
      setStatus("jobs-status-chip", "Error", "error");
    } finally {
      monitorRefreshInFlight = false;
      if (pendingJobRefresh) {
        pendingJobRefresh = false;
        void loadJobs();
      }
    }
  }

  function renderJobList(jobs) {
    const list = byId("jobs-list");
    const meta = byId("jobs-list-meta");
    if (!list || !meta) return;
    meta.textContent = `${jobs.length} job${jobs.length === 1 ? "" : "s"} found · sorted by ${jobSortLabel(byId("job-filter-sort")?.value)}.`;
    if (!jobs.length) {
      list.innerHTML = '<div class="empty-state">No jobs found matching criteria.</div>';
      return;
    }
    list.innerHTML = jobs.map(job => `
      <div class="pulse-card${state.selected_job_id === job.id ? " is-active" : ""}" data-job-id="${escapeHtml(job.id)}">
        <div class="pulse-card-line">
          <span class="pulse-card-title">${escapeHtml(job.required_capability)}</span>
          <span class="status" style="font-size: 0.6rem;">${escapeHtml(job.status)}</span>
        </div>
        <div class="pulse-card-line pulse-card-line-secondary">
          <span class="pulse-card-subtitle">${escapeHtml(
            jobTargets(job).length
              ? jobTargets(job).join(", ")
              : (buildJobImportantSummary(job, { maxPayloadFields: 1, maxParts: 1 }) || "No targets attached.")
          )}</span>
          <span class="pulse-card-time">${escapeHtml(formatTimestamp(job.updated_at))}</span>
        </div>
      </div>
    `).join("");
  }

  async function loadJobDetail(jobId, options = {}) {
    const background = Boolean(options.background);
    if (background && jobDetailRefreshInFlight) return;
    jobDetailRefreshInFlight = true;
    state.selected_job_id = jobId;
    // Update visual selection
    document.querySelectorAll('#jobs-list .pulse-card').forEach(card => {
        card.classList.toggle('is-active', card.getAttribute('data-job-id') === jobId);
    });

    if (!background) {
      renderJobDetailLoading("Loading job detail...");
      byId("job-detail-meta").textContent = "Loading current job detail...";
    }
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      const payload = await fetchJson(`/api/jobs/${encodeURIComponent(jobId)}?${query.toString()}`);
      if (state.selected_job_id !== jobId) return;
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      state.selected_job = payload.job || null;
      state.selected_job_raw_records = Array.isArray(payload.raw_records) ? payload.raw_records : [];
      updateJobActionButtons(state.selected_job);
      renderJobDetailResponse(payload);
      byId("job-detail-meta").textContent = buildJobMetaLabel(state.selected_job, { fallbackName: "Current Job" });
    } catch (error) {
      if (state.selected_job_id !== jobId) return;
      if (!background) {
        state.selected_job = null;
        state.selected_job_raw_records = [];
        updateJobActionButtons(null);
        renderJobDetailError(error.message);
        byId("job-detail-meta").textContent = "Unable to load current job detail.";
      }
    } finally {
      jobDetailRefreshInFlight = false;
    }
  }

  async function controlJobById(jobId, action, options = {}) {
    const normalizedJobId = String(jobId || "").trim();
    if (!normalizedJobId) return null;

    const confirmMessages = {
      cancel: `Cancel job ${shortJobId(normalizedJobId)}?`,
      delete: `Delete job ${shortJobId(normalizedJobId)}?`,
      force_terminate: `Force terminate job ${shortJobId(normalizedJobId)}?`,
    };
    if (confirmMessages[action] && !window.confirm(confirmMessages[action])) {
      return null;
    }

    const actionLabelMap = {
      pause: "Pausing",
      stop: "Stopping",
      resume: "Resuming",
      cancel: "Canceling",
      delete: "Deleting",
      force_terminate: "Terminating",
    };
    if (normalizedJobId === state.selected_job_id) {
      setStatus("job-action-status-chip", actionLabelMap[action] || "Updating", "loading");
    }

    const fallbackJob = normalizedJobId === state.selected_job_id
      ? state.selected_job
      : (state.jobs.find(job => job.id === normalizedJobId) || null);

    if (action === "cancel" && fallbackJob && !canCancelJob(fallbackJob)) {
      return fallbackJob;
    }
    if (action === "force_terminate" && fallbackJob && !canForceTerminateJob(fallbackJob)) {
      return fallbackJob;
    }

    try {
      const payload = await fetchJson(`/api/jobs/${encodeURIComponent(normalizedJobId)}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dispatcher_address: currentDispatcherAddress(),
          action,
        }),
      });
      const controlledJob = payload?.control?.job || fallbackJob;

      if (normalizedJobId === state.selected_job_id) {
        if (action === "delete") {
          state.selected_job = null;
          state.selected_job_id = "";
          state.selected_job_raw_records = [];
          updateJobActionButtons(null);
          byId("job-detail-meta").textContent = "Deleted job.";
          renderJobDetailResponse({
            job: controlledJob || Object.assign({}, fallbackJob || {}, { status: "deleted" }),
            raw_records: [],
          });
        } else if (action === "cancel") {
          state.selected_job = controlledJob || Object.assign({}, fallbackJob || {}, { status: "cancelled" });
          updateJobActionButtons(state.selected_job);
          byId("job-detail-meta").textContent = buildJobMetaLabel(state.selected_job || {}, { fallbackName: "Current Job" });
          renderJobDetailResponse({
            job: state.selected_job || Object.assign({}, fallbackJob || {}, { status: "cancelled" }),
            raw_records: state.selected_job_raw_records,
          });
        } else {
          state.selected_job = controlledJob || fallbackJob;
          updateJobActionButtons(state.selected_job);
          byId("job-detail-meta").textContent = buildJobMetaLabel(state.selected_job || {}, { fallbackName: "Current Job" });
          renderJobDetailResponse({
            job: state.selected_job || fallbackJob || {},
            raw_records: state.selected_job_raw_records,
          });
        }
      }

      await loadMonitorPageData();

      if (state.worker_job_modal_job_id === normalizedJobId && state.worker_job_modal_open) {
        await openWorkerJobDetailModal(normalizedJobId);
      }
      if (state.worker_history_modal_open && state.worker_history_modal_worker_id) {
        await loadWorkerHistory(state.worker_history_modal_worker_id, {
          workerName: state.worker_history_modal_worker_name,
        });
      }
      return controlledJob;
    } catch (error) {
      if (normalizedJobId === state.selected_job_id) {
        setStatus("job-action-status-chip", "Action Failed", "error");
        renderJobDetailError(`${humanizeKey(action)} failed: ${error.message}`);
        byId("job-detail-meta").textContent = "Unable to update current job detail.";
      }
      if (state.worker_job_modal_job_id === normalizedJobId && state.worker_job_modal_open) {
        const meta = byId("worker-job-modal-meta");
        if (meta) meta.textContent = "Unable to update current job detail.";
        renderJobDetailError(`${humanizeKey(action)} failed: ${error.message}`, "worker-job-modal-body");
      }
      throw error;
    }
  }

  async function controlSelectedJob(action) {
    if (!state.selected_job || !state.selected_job_id) return;
    try {
      await controlJobById(state.selected_job_id, action);
    } catch (error) {
      console.error(`Failed to ${action} job:`, error);
    }
  }

  function syncMonitorAutoRefresh() {
    if (monitorRefreshHandle) { clearInterval(monitorRefreshHandle); monitorRefreshHandle = null; }
    const sec = coerceMonitorRefreshSec(state.settings.monitor_refresh_sec);
    if (state.current_page === "monitor" && sec > 0) {
        monitorRefreshHandle = setInterval(loadMonitorPageData, sec * 1000);
    }
  }

  function refreshMonitorView() {
    void loadMonitorPageData();
  }

  async function loadDbTables() {
    setStatus("db-status-chip", "Loading Tables", "loading");
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      const payload = await fetchJson(`/api/db/tables?${query.toString()}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      state.db_tables = payload.tables || [];
      renderDbTableOptions();
      setStatus("db-status-chip", "Tables Ready", "success");
    } catch (error) {
      setStatus("db-status-chip", "DB Error", "error");
      renderDbResult(null, error.message);
    }
  }

  async function loadSelectedTable() {
    const tableName = byId("db-table-name")?.value || "";
    if (!tableName) return;
    setStatus("db-status-chip", "Loading Table", "loading");
    try {
      const query = new URLSearchParams();
      const dispatcher = currentDispatcherAddress();
      if (dispatcher) query.set("dispatcher_address", dispatcher);
      query.set("table_name", tableName);
      query.set("limit", String(byId("db-table-limit")?.value || "100"));
      const payload = await fetchJson(`/api/db/table?${query.toString()}`);
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      renderDbResult(
        payload,
        `${payload.table_name} · ${payload.count} row${payload.count === 1 ? "" : "s"} of ${payload.total_rows}`
      );
      setStatus("db-status-chip", "Table Ready", "success");
    } catch (error) {
      setStatus("db-status-chip", "DB Error", "error");
      renderDbResult(null, error.message);
    }
  }

  async function runDbQuery() {
    setStatus("db-status-chip", "Running SQL", "loading");
    try {
      const rawParams = byId("db-params-json")?.value || "[]";
      const payload = await fetchJson("/api/db/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dispatcher_address: currentDispatcherAddress(),
          sql: byId("db-sql")?.value || "",
          params: JSON.parse(rawParams || "[]"),
          limit: Number.parseInt(String(byId("db-query-limit")?.value || "200"), 10) || 200
        }),
      });
      if (payload.dispatcher_address) setDispatcherAddress(payload.dispatcher_address);
      const truncatedLabel = payload.truncated ? " · truncated" : "";
      renderDbResult(payload, `SQL result · ${payload.count} row${payload.count === 1 ? "" : "s"}${truncatedLabel}`);
      setStatus("db-status-chip", "Query Ready", "success");
    } catch (error) {
      setStatus("db-status-chip", "DB Error", "error");
      renderDbResult(null, error.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    // 1. Setup shared components
    if (window.agentConnection) {
        window.agentConnection.mountStickyHeader({ selector: '.agent-sticky-header' });
        window.agentConnection.plazaRef = window.agentConnection.mount({
            endpoint: '/api/plaza/status',
            pollMs: 30000
        });
    }

    // 2. Initialize state
    state.settings = buildSettingsState(readStoredSettings());
    applySidebarState(readStoredSidebarCollapsed());
    applyIssueParametersCollapsed(true);
    applyMonitorPanelCollapsed(true);
    switchMonitorTab(state.monitor_tab);
    setDispatcherParty(state.settings.dispatcher_party || state.dispatcher_party || state.settings_defaults?.dispatcher_party || "");
    setDispatcherAddress(state.settings.dispatcher_address || state.dispatcher_address);
    if (byId("worker-status-filter")) byId("worker-status-filter").value = state.worker_status_filter;
    if (byId("settings-monitor-refresh-sec")) byId("settings-monitor-refresh-sec").value = state.settings.monitor_refresh_sec || 0;
    if (byId("settings-plaza-url-input")) byId("settings-plaza-url-input").value = state.settings.plaza_url || "";
    renderDispatcherPartyOptions();
    renderDispatcherSelectOptions();
    if (byId("schedule-at") && !byId("schedule-at").value) byId("schedule-at").value = localDateTimeValueFromNow(15);
    if (byId("schedule-times") && !byId("schedule-times").value) byId("schedule-times").value = "09:00";
    setScheduleRepeatFrequency(currentScheduleRepeatFrequency());
    syncScheduleTimezoneNote();
    
    renderRuntimeSummary();
    renderHeroMetrics(state.hero_metrics);
    updateHeroConnectButton(state.plaza_status);
    renderIssueParameters({ seedDefaults: true });
    syncIssueJobPriority();

    // 3. Navigation
    document.querySelectorAll("[data-page-link]").forEach(link => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        switchPage(link.getAttribute("data-page-link"));
      });
    });
    if (byId("sidebar-toggle")) byId("sidebar-toggle").addEventListener("click", toggleSidebar);
    if (byId("monitor-panel-toggle")) byId("monitor-panel-toggle").addEventListener("click", toggleMonitorPanel);
    document.querySelectorAll("[data-monitor-tab]").forEach(button => {
      button.addEventListener("click", () => switchMonitorTab(button.getAttribute("data-monitor-tab")));
    });

    // 4. Job Submission
    if (byId("boss-job-form")) byId("boss-job-form").addEventListener("submit", handleJobSubmit);
    if (byId("required-capability")) byId("required-capability").addEventListener("change", () => {
      syncIssueJobPriority();
      renderIssueParameters({ seedDefaults: true });
    });
    if (byId("job-parameters-toggle")) byId("job-parameters-toggle").addEventListener("click", toggleIssueParameters);
    if (byId("payload-json")) byId("payload-json").addEventListener("change", () => {
      renderIssueParameters({ seedDefaults: false });
    });
    if (byId("job-parameters")) byId("job-parameters").addEventListener("input", (event) => {
      const symbolsInput = event.target.closest("#symbols");
      if (symbolsInput) {
        state.issue_symbols_value = String(symbolsInput.value || "");
      }
      const input = event.target.closest("[data-param-field]");
      if (!input) return;
      updateIssueParameterFieldFromInput(input);
    });
    if (byId("job-parameters")) byId("job-parameters").addEventListener("click", (event) => {
      const button = event.target.closest("[data-param-action]");
      if (!button) return;
      const action = String(button.getAttribute("data-param-action") || "").trim();
      const parameterKey = String(button.getAttribute("data-param-key") || "").trim();
      const index = Number.parseInt(String(button.getAttribute("data-param-index") || "-1"), 10);
      if (action === "add-row") {
        addIssueParameterRow(parameterKey);
      } else if (action === "remove-row") {
        removeIssueParameterRow(parameterKey, index);
      }
    });
    if (byId("boss-fill-daily-price")) byId("boss-fill-daily-price").addEventListener("click", () => {
        byId("symbols").value = "MSFT, AAPL, GOOGL";
        byId("payload-json").value = JSON.stringify({ window: "1y" }, null, 2);
        renderIssueParameters({ seedDefaults: false });
    });

    // 4b. Scheduling
    if (byId("schedule-job-form")) byId("schedule-job-form").addEventListener("submit", handleScheduleSubmit);
    if (byId("schedule-repeat-frequency")) byId("schedule-repeat-frequency").addEventListener("change", (event) => {
      setScheduleRepeatFrequency(event.target.value);
    });
    if (byId("schedule-fill-daily-price")) byId("schedule-fill-daily-price").addEventListener("click", () => {
      if (byId("schedule-symbols")) byId("schedule-symbols").value = "MSFT, AAPL, GOOGL";
      if (byId("schedule-payload-json")) byId("schedule-payload-json").value = JSON.stringify({ window: "1y" }, null, 2);
      if (byId("schedule-at") && !byId("schedule-at").value) byId("schedule-at").value = localDateTimeValueFromNow(15);
      if (byId("schedule-repeat-frequency")) setScheduleRepeatFrequency("daily");
      if (byId("schedule-times")) byId("schedule-times").value = "09:00, 16:00";
    });
    if (byId("schedule-refresh")) byId("schedule-refresh").addEventListener("click", loadSchedules);
    if (byId("schedule-list")) byId("schedule-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-schedule-action]");
      if (!button) return;
      const card = event.target.closest("[data-schedule-id]");
      if (!card) return;
      const action = button.getAttribute("data-schedule-action");
      if (action === "history") {
        void openScheduleHistoryModal(
          card.getAttribute("data-schedule-id"),
          card.getAttribute("data-schedule-name")
        );
        return;
      }
      controlSchedule(card.getAttribute("data-schedule-id"), action);
    });

    // 5. Monitoring
    if (byId("monitor-refresh")) byId("monitor-refresh").addEventListener("click", refreshMonitorView);
    if (byId("job-filter-status")) byId("job-filter-status").addEventListener("change", () => {
      void loadJobs();
    });
    if (byId("job-filter-sort")) byId("job-filter-sort").addEventListener("change", () => {
      void loadJobs();
    });
    if (byId("job-filter-capability")) byId("job-filter-capability").addEventListener("change", () => {
      void loadJobs();
    });
    if (byId("jobs-list")) byId("jobs-list").addEventListener("click", (e) => {
      const card = e.target.closest(".pulse-card");
      if (card) loadJobDetail(card.getAttribute("data-job-id"));
    });
    if (byId("job-pause")) byId("job-pause").addEventListener("click", () => controlSelectedJob("pause"));
    if (byId("job-stop")) byId("job-stop").addEventListener("click", () => controlSelectedJob("stop"));
    if (byId("job-resume")) byId("job-resume").addEventListener("click", () => controlSelectedJob("resume"));
    if (byId("job-cancel")) byId("job-cancel").addEventListener("click", () => controlSelectedJob("cancel"));
    if (byId("job-detail")) byId("job-detail").addEventListener("click", (event) => {
      const button = event.target.closest("[data-job-detail-action]");
      if (!button) return;
      void controlJobById(button.getAttribute("data-job-id"), button.getAttribute("data-job-detail-action")).catch(() => {});
    });
    if (byId("worker-status-list")) byId("worker-status-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-worker-job-detail]");
      if (button) {
        void openWorkerJobDetailModal(button.getAttribute("data-worker-job-detail"));
        return;
      }
      const historyButton = event.target.closest("[data-worker-history]");
      if (!historyButton) return;
      void openWorkerHistoryModal(
        historyButton.getAttribute("data-worker-history"),
        historyButton.getAttribute("data-worker-name")
      );
    });
    if (byId("worker-status-filter")) byId("worker-status-filter").addEventListener("change", (event) => {
      state.worker_status_filter = normalizeWorkerStatusFilter(event.target.value);
      renderMonitorSummary({
        dispatcher: state.monitor_summary || {},
        workers: state.monitor_workers || [],
        dispatcher_address: currentDispatcherAddress(),
      });
    });
    if (byId("worker-job-modal-body")) byId("worker-job-modal-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-job-detail-action]");
      if (!button) return;
      void controlJobById(button.getAttribute("data-job-id"), button.getAttribute("data-job-detail-action")).catch(() => {});
    });
    if (byId("worker-job-modal-close")) byId("worker-job-modal-close").addEventListener("click", closeWorkerJobModal);
    if (byId("worker-job-modal")) byId("worker-job-modal").addEventListener("click", (event) => {
      if (event.target.closest("[data-close-worker-job-modal='true']")) {
        closeWorkerJobModal();
      }
    });
    if (byId("worker-history-modal-body")) byId("worker-history-modal-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-worker-history-job-detail]");
      if (!button) return;
      closeWorkerHistoryModal();
      void openWorkerJobDetailModal(button.getAttribute("data-worker-history-job-detail"));
    });
    if (byId("worker-history-modal-close")) byId("worker-history-modal-close").addEventListener("click", closeWorkerHistoryModal);
    if (byId("worker-history-modal")) byId("worker-history-modal").addEventListener("click", (event) => {
      if (event.target.closest("[data-close-worker-history-modal='true']")) {
        closeWorkerHistoryModal();
      }
    });
    if (byId("schedule-history-modal-body")) byId("schedule-history-modal-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-schedule-history-job-detail]");
      if (!button) return;
      closeScheduleHistoryModal();
      void openWorkerJobDetailModal(button.getAttribute("data-schedule-history-job-detail"));
    });
    if (byId("schedule-history-modal-close")) byId("schedule-history-modal-close").addEventListener("click", closeScheduleHistoryModal);
    if (byId("schedule-history-modal")) byId("schedule-history-modal").addEventListener("click", (event) => {
      if (event.target.closest("[data-close-schedule-history-modal='true']")) {
        closeScheduleHistoryModal();
      }
    });

    // 6. DB Viewer
    renderDbTableOptions();
    switchDbTab(state.db_tab);
    document.querySelectorAll("[data-db-tab]").forEach(button => {
      button.addEventListener("click", () => switchDbTab(button.getAttribute("data-db-tab")));
    });
    if (byId("db-refresh-tables")) byId("db-refresh-tables").addEventListener("click", loadDbTables);
    if (byId("db-load-table")) byId("db-load-table").addEventListener("click", loadSelectedTable);
    if (byId("db-run-query")) byId("db-run-query").addEventListener("click", runDbQuery);

    // 7. Settings
    if (byId("hero-metrics-refresh")) byId("hero-metrics-refresh").addEventListener("click", () => {
      void loadHeroMetrics();
    });
    if (byId("hero-connect-plaza")) byId("hero-connect-plaza").addEventListener("click", connectPlaza);
    if (byId("settings-connect-plaza")) byId("settings-connect-plaza").addEventListener("click", connectPlaza);
    if (byId("settings-dispatcher-party")) byId("settings-dispatcher-party").addEventListener("change", () => {
      setDispatcherParty(byId("settings-dispatcher-party").value);
      void refreshPlazaStatus();
    });
    if (byId("settings-dispatcher-select")) byId("settings-dispatcher-select").addEventListener("change", () => {
      setDispatcherAddress(byId("settings-dispatcher-select").value.trim());
    });
    
    if (byId("boss-settings-form")) byId("boss-settings-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      state.settings.dispatcher_address = byId("settings-dispatcher-address").value.trim();
      state.settings.dispatcher_party = currentDispatcherParty();
      state.settings.plaza_url = byId("settings-plaza-url-input").value.trim();
      state.settings.monitor_refresh_sec = coerceMonitorRefreshSec(byId("settings-monitor-refresh-sec").value);

      setDispatcherParty(state.settings.dispatcher_party);
      setDispatcherAddress(state.settings.dispatcher_address);
      writeStoredSettings(state.settings);

      try {
        const payload = await fetchJson("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.settings),
        });
        if (payload?.settings) {
          state.settings = buildSettingsState(Object.assign({}, state.settings, payload.settings));
        }
        if (payload?.runtime_summary) {
          state.runtime_summary = Object.assign({}, state.runtime_summary, payload.runtime_summary);
        }
        setDispatcherParty(state.settings.dispatcher_party);
        setDispatcherAddress(state.settings.dispatcher_address);
        setStatus("settings-status-chip", "Saved", "success");
      } catch (error) {
        setStatus("settings-status-chip", "Save Failed", "error");
        return;
      }

      syncMonitorAutoRefresh();
      renderRuntimeSummary();
      updateHeroConnectButton({
        connection_status: state.plaza_status?.connection_status || "not_configured",
        plaza_url: state.settings.plaza_url,
      });
      void loadHeroMetrics();
      if (state.current_page === "monitor") {
        void loadMonitorPageData();
      }
    });

    if (byId("settings-reset")) byId("settings-reset").addEventListener("click", () => {
        state.settings = buildSettingsState({});
        writeStoredSettings(state.settings);
        window.location.reload();
    });

    if (byId("settings-save-local")) byId("settings-save-local").addEventListener("click", () => {
        const data = JSON.stringify(state.settings, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dispatcher-boss-settings-${new Date().getTime()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    });

    if (byId("settings-load-local")) byId("settings-load-local").addEventListener("click", () => {
        byId("settings-load-local-input").click();
    });

    if (byId("settings-load-local-input")) byId("settings-load-local-input").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const parsed = JSON.parse(event.target.result);
                state.settings = buildSettingsState(parsed);
                writeStoredSettings(state.settings);
                window.location.reload();
            } catch (err) {
                alert("Failed to parse settings file.");
            }
        };
        reader.readAsText(file);
    });

    // 8. Initial Page Load
    updateJobActionButtons(null);
    refreshPlazaStatus();
    void loadHeroMetrics();
    if (state.current_page === "schedule") {
        setTimeout(loadSchedules, 100);
    }
    if (state.current_page === "monitor") {
        setTimeout(loadMonitorPageData, 100);
    }
    if (state.current_page === "db") {
        setTimeout(() => {
          loadDbTables().then(() => loadSelectedTable());
        }, 100);
    }
    syncMonitorAutoRefresh();
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (state.worker_job_modal_open) closeWorkerJobModal();
        if (state.worker_history_modal_open) closeWorkerHistoryModal();
        if (state.schedule_history_modal_open) closeScheduleHistoryModal();
      }
    });
  });
})();
