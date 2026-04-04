(function () {
  const initial = window.__BOSS_PULSER_INITIAL__ || {};
  const exampleJobCapabilities = Array.isArray(initial?.examples?.team_job_capabilities)
    ? initial.examples.team_job_capabilities
    : [];
  const exampleJobPayload = initial?.examples?.job_payload && typeof initial.examples.job_payload === "object"
    ? initial.examples.job_payload
    : {};

  const state = {
    party: String(initial.party || "Phemacast").trim() || "Phemacast",
    teams: [],
    selectedManagerAddress: "",
    selectedTeam: null,
    capabilities: [],
    status: null,
    history: null,
    provisioningTab: "team"
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatJson(value) {
    return JSON.stringify(value ?? {}, null, 2);
  }

  function formatTimestamp(value) {
    if (!value) return "Unset";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  }

  function formatRelativeTime(value) {
    if (!value) return "No recent activity";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const diffMs = Date.now() - date.getTime();
    const diffSec = Math.round(diffMs / 1000);
    if (diffSec < 10) return "Just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.round(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.round(diffHour / 24);
    return `${diffDay}d ago`;
  }

  function compactObject(value) {
    return Object.fromEntries(
      Object.entries(value || {}).filter(([, entry]) => {
        if (entry === null || entry === undefined) return false;
        if (typeof entry === "string") return entry.trim() !== "";
        if (Array.isArray(entry)) return entry.length > 0;
        return true;
      })
    );
  }

  function parseJsonField(rawValue, label) {
    const trimmed = String(rawValue || "").trim();
    if (!trimmed) return undefined;
    try {
      return JSON.parse(trimmed);
    } catch (_error) {
      throw new Error(`${label} must be valid JSON.`);
    }
  }

  function parseCsvList(rawValue) {
    return String(rawValue || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.detail || payload?.error || `Request failed: ${response.status}`);
    }
    return payload;
  }

  function setChip(id, label, mode) {
    const chip = byId(id);
    if (!chip) return;
    chip.textContent = label;
    chip.className = `status-chip${mode ? ` is-${mode}` : ""}`;
  }

  function setMetric(metricId, value) {
    const node = document.querySelector(`[data-metric="${metricId}"]`);
    if (!node) return;
    node.textContent = value;
  }

  function seedExamples() {
    const jobcapText = formatJson(exampleJobCapabilities);
    const payloadText = formatJson(exampleJobPayload);
    ["team-jobcaps-input", "manager-jobcaps-input", "worker-jobcaps-input"].forEach((id) => {
      const field = byId(id);
      if (field && !String(field.value || "").trim()) field.value = jobcapText;
    });
    const payloadField = byId("job-payload-input");
    if (payloadField && !String(payloadField.value || "").trim()) payloadField.value = payloadText;
  }

  function filteredTeams() {
    const searchValue = String(byId("team-search-input")?.value || "").trim().toLowerCase();
    if (!searchValue) return state.teams;
    return state.teams.filter((team) => {
      const haystack = [
        team.manager_name,
        team.manager_address,
        team.party,
        team.description,
        ...(Array.isArray(team.workers) ? team.workers.map((worker) => worker.name || "") : [])
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(searchValue);
    });
  }

  function findSelectedTeam() {
    return state.teams.find((team) => team.manager_address === state.selectedManagerAddress) || null;
  }

  function renderHeroMetrics() {
    const workerCount = state.teams.reduce((total, team) => total + Number(team.worker_count || 0), 0);
    setMetric("teams", String(state.teams.length));
    setMetric("workers", String(workerCount));
    setMetric("jobcaps", String(state.capabilities.length));
    setMetric("manager", state.selectedManagerAddress ? state.selectedManagerAddress : "None");
  }

  function renderTeams() {
    const container = byId("teams-list");
    if (!container) return;
    const teams = filteredTeams();
    if (!teams.length) {
      container.innerHTML = `<div class="empty-state">${state.teams.length ? "No teams match the current search." : "No teams discovered yet for this party."}</div>`;
      return;
    }
    container.innerHTML = teams
      .map((team, index) => {
        const isSelected = team.manager_address === state.selectedManagerAddress;
        const capabilityNames = Array.isArray(team.job_capabilities)
          ? team.job_capabilities.map((entry) => entry?.name).filter(Boolean).slice(0, 4)
          : [];
        return `
          <button type="button" class="team-card fade-in${isSelected ? " is-selected" : ""}" data-manager-address="${escapeHtml(team.manager_address || "")}" style="animation-delay:${index * 40}ms">
            <div class="team-card-header">
              <strong>${escapeHtml(team.manager_name || "Manager")}</strong>
              <span class="badge">${escapeHtml(`${team.worker_count || 0} workers`)}</span>
            </div>
            <div class="mono">${escapeHtml(team.manager_address || "No manager address")}</div>
            <p>${escapeHtml(team.description || "Phemacast teamwork manager.")}</p>
            <div class="badge-row">
              <span class="badge">${escapeHtml(team.party || state.party)}</span>
              ${capabilityNames.map((name) => `<span class="badge">${escapeHtml(name)}</span>`).join("")}
            </div>
          </button>
        `;
      })
      .join("");
    Array.from(container.querySelectorAll("[data-manager-address]")).forEach((node) => {
      node.addEventListener("click", () => selectManager(node.getAttribute("data-manager-address") || ""));
    });
  }

  function renderCapabilityMap() {
    const container = byId("capability-map");
    if (!container) return;
    if (!state.selectedManagerAddress) {
      container.innerHTML = '<div class="empty-state">Select a team to inspect its capability map.</div>';
      return;
    }
    if (!state.capabilities.length) {
      container.innerHTML = '<div class="empty-state">No capability data is available for this manager yet.</div>';
      return;
    }
    container.innerHTML = state.capabilities
      .map((entry) => {
        const providers = Array.isArray(entry.providers) ? entry.providers : [];
        return `
          <article class="capability-card fade-in">
            <div class="team-card-header">
              <strong>${escapeHtml(entry.name || "capability")}</strong>
              <span class="badge">${escapeHtml(`${providers.length} provider${providers.length === 1 ? "" : "s"}`)}</span>
            </div>
            <p>${escapeHtml(entry.description || "No description configured.")}</p>
            <div class="badge-row">
              ${providers.map((provider) => `<span class="badge">${escapeHtml(`${provider.type}:${provider.name}`)}</span>`).join("")}
            </div>
          </article>
        `;
      })
      .join("");
  }

  function renderSelectedSummary() {
    const container = byId("selected-team-summary");
    if (!container) return;
    const team = state.selectedTeam;
    if (!team) {
      container.innerHTML = '<div class="empty-state">Choose a live team to load status, history, and worker health.</div>';
      return;
    }
    const jobs = state.status?.jobs || {};
    const workers = state.status?.workers || {};
    container.innerHTML = `
      <div class="fade-in">
        <div class="mono-label">Selected Manager</div>
        <h3 class="summary-title">${escapeHtml(team.manager_name || "Manager")}</h3>
        <p class="summary-lead">${escapeHtml(team.description || "Independent Phemacast teamwork manager.")}</p>
        <div class="mono">${escapeHtml(team.manager_address || "")}</div>
        <div class="badge-row">
          <span class="badge">${escapeHtml(team.party || state.party)}</span>
          <span class="badge">${escapeHtml(`${team.worker_count || 0} workers discovered`)}</span>
          <span class="badge">${escapeHtml(`${jobs.total || 0} tracked jobs`)}</span>
          <span class="badge">${escapeHtml(`${workers.total || 0} worker records`)}</span>
        </div>
      </div>
    `;
  }

  function renderWorkerHealth() {
    const container = byId("worker-health");
    if (!container) return;
    const roster = Array.isArray(state.status?.workers?.roster) ? state.status.workers.roster : [];
    if (!roster.length) {
      container.innerHTML = '<div class="empty-state">No worker health loaded yet.</div>';
      return;
    }
    container.innerHTML = roster
      .map((worker) => `
        <div class="item-row fade-in">
          <div class="item-row-copy">
            <div class="item-row-title">
              <strong>${escapeHtml(worker.name || worker.worker_id || "Worker")}</strong>
              <span class="health-pill is-${escapeHtml((worker.health_status || "offline").toLowerCase())}">${escapeHtml(worker.health_status || "offline")}</span>
            </div>
            <div class="mono">${escapeHtml(worker.worker_id || worker.id || "")}</div>
          </div>
          <div class="mono">${escapeHtml(worker.heartbeat_age_sec == null ? "Unknown" : `${Math.round(Number(worker.heartbeat_age_sec || 0))}s`)}</div>
        </div>
      `)
      .join("");
  }

  function renderQueueStatus() {
    const container = byId("queue-status");
    if (!container) return;
    const jobCounts = state.status?.jobs?.by_status || {};
    const workerCounts = state.status?.workers?.by_health || {};
    const cards = [
      ["Queued", jobCounts.queued || 0],
      ["Claimed", jobCounts.claimed || 0],
      ["Completed", jobCounts.completed || 0],
      ["Online", workerCounts.online || 0],
      ["Stale", workerCounts.stale || 0],
      ["Offline", workerCounts.offline || 0]
    ];
    container.innerHTML = `
      <div class="queue-grid fade-in">
        ${cards.map(([label, value]) => `
          <article class="mini-stat">
            <span class="mono-label">${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value))}</strong>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderRecentJobs() {
    const container = byId("recent-jobs");
    if (!container) return;
    const jobs = Array.isArray(state.history?.jobs) && state.history.jobs.length
      ? state.history.jobs
      : (Array.isArray(state.status?.jobs?.recent) ? state.status.jobs.recent : []);
    if (!jobs.length) {
      container.innerHTML = '<div class="empty-state">Recent jobs will appear here.</div>';
      return;
    }
    container.innerHTML = jobs
      .slice(0, 12)
      .map((job) => `
        <div class="item-row fade-in">
          <div class="item-row-copy">
            <div class="item-row-title">
              <strong>${escapeHtml(job.required_capability || "job")}</strong>
              <span class="badge">${escapeHtml(job.status || "unknown")}</span>
            </div>
            <div class="job-id">${escapeHtml(job.id || "No id")}</div>
          </div>
          <div class="mono">${escapeHtml(formatRelativeTime(job.updated_at || job.completed_at))}</div>
        </div>
      `)
      .join("");
  }

  function renderWorkerHistory() {
    const container = byId("worker-history");
    if (!container) return;
    const events = Array.isArray(state.history?.worker_history) ? state.history.worker_history : [];
    if (!events.length) {
      container.innerHTML = '<div class="empty-state">Worker history will appear here.</div>';
      return;
    }
    container.innerHTML = events
      .slice(0, 12)
      .map((event) => `
        <div class="history-row fade-in">
          <div class="history-row-copy">
            <div class="history-row-title">
              <strong>${escapeHtml(event.name || event.worker_id || "Worker")}</strong>
              <span class="badge">${escapeHtml(event.event_type || event.status || "event")}</span>
            </div>
            <div class="mono">${escapeHtml(event.active_job_id || event.worker_id || "")}</div>
          </div>
          <div class="mono">${escapeHtml(formatRelativeTime(event.captured_at))}</div>
        </div>
      `)
      .join("");
  }

  function renderSnapshot() {
    renderSelectedSummary();
    renderWorkerHealth();
    renderQueueStatus();
    renderRecentJobs();
    renderWorkerHistory();
  }

  function renderJsonCard(title, value, subtitle) {
    return `
      <article class="json-card fade-in">
        <div class="json-card-header">
          <strong>${escapeHtml(title)}</strong>
          ${subtitle ? `<span class="badge">${escapeHtml(subtitle)}</span>` : ""}
        </div>
        <pre>${escapeHtml(formatJson(value))}</pre>
      </article>
    `;
  }

  function renderProvisionResult(payload) {
    const container = byId("provision-result");
    if (!container) return;
    const parts = [];
    const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
    const launchPlan = Array.isArray(payload?.launch_plan) ? payload.launch_plan : [];
    const pathEntries = [];
    if (payload?.config_path) pathEntries.push(["Config Path", payload.config_path]);
    if (payload?.config_paths?.boss) pathEntries.push(["Boss Config", payload.config_paths.boss]);
    if (payload?.config_paths?.manager) pathEntries.push(["Manager Config", payload.config_paths.manager]);
    if (Array.isArray(payload?.config_paths?.workers)) {
      payload.config_paths.workers.forEach((path, index) => pathEntries.push([`Worker ${index + 1}`, path]));
    }

    parts.push(`
      <article class="result-card fade-in">
        <div class="result-meta">
          <strong>${escapeHtml(payload.team_name || payload.manager_address || "Blueprint ready")}</strong>
          <span class="badge">${escapeHtml(payload.party || state.party)}</span>
        </div>
        <div class="pill-row">
          ${pathEntries.map(([label, value]) => `<span class="badge">${escapeHtml(`${label}: ${value}`)}</span>`).join("")}
          ${warnings.map((warning) => `<span class="badge">${escapeHtml(warning)}</span>`).join("")}
        </div>
      </article>
    `);

    if (launchPlan.length) {
      parts.push(`
        <article class="result-card fade-in">
          <div class="json-card-header">
            <strong>Launch Plan</strong>
            <span class="badge">${escapeHtml(`${launchPlan.length} step${launchPlan.length === 1 ? "" : "s"}`)}</span>
          </div>
          ${launchPlan.map((step) => `
            <div class="item-row">
              <div class="item-row-copy">
                <div class="item-row-title">
                  <strong>${escapeHtml(step.role || "role")}</strong>
                  <span class="badge">${escapeHtml(step.type || "")}</span>
                </div>
                <div class="mono">${escapeHtml(step.config_path || "")}</div>
              </div>
            </div>
          `).join("")}
        </article>
      `);
    }

    if (payload?.boss_config) parts.push(renderJsonCard("Boss Config", payload.boss_config));
    if (payload?.manager_config) parts.push(renderJsonCard("Manager Config", payload.manager_config));
    if (payload?.worker_config) parts.push(renderJsonCard("Worker Config", payload.worker_config));
    if (payload?.worker_configs) parts.push(renderJsonCard("Worker Configs", payload.worker_configs, `${payload.worker_configs.length} workers`));

    container.innerHTML = parts.join("");
  }

  function renderJobSubmitResult(payload) {
    const container = byId("job-submit-result");
    if (!container) return;
    const submitted = payload?.submitted || {};
    const job = submitted?.job && typeof submitted.job === "object" ? submitted.job : submitted;
    const meta = [
      payload?.required_capability ? ["Capability", payload.required_capability] : null,
      payload?.manager?.manager_address ? ["Manager", payload.manager.manager_address] : null,
      job?.id ? ["Job ID", job.id] : null,
      job?.status ? ["Status", job.status] : null
    ].filter(Boolean);
    container.innerHTML = `
      <article class="result-card fade-in">
        <div class="result-meta">
          <strong>${escapeHtml(job?.id || "Submitted")}</strong>
          <span class="badge">${escapeHtml(job?.status || "success")}</span>
        </div>
        <div class="pill-row">
          ${meta.map(([label, value]) => `<span class="badge">${escapeHtml(`${label}: ${value}`)}</span>`).join("")}
        </div>
      </article>
      ${renderJsonCard("Submission Payload", payload)}
    `;
  }

  function setSelectedManagerInputs(address) {
    const normalized = String(address || "").trim();
    const jobField = byId("job-manager-address");
    const workerField = byId("worker-manager-address-input");
    if (jobField) jobField.value = normalized;
    if (workerField) workerField.value = normalized;
  }

  function syncCapabilityDatalist() {
    const datalist = byId("capability-datalist");
    if (!datalist) return;
    datalist.innerHTML = state.capabilities
      .map((entry) => `<option value="${escapeHtml(entry.name || "")}"></option>`)
      .join("");
    const capabilityField = byId("required-capability-input");
    if (capabilityField && !String(capabilityField.value || "").trim() && state.capabilities[0]?.name) {
      capabilityField.value = state.capabilities[0].name;
    }
  }

  async function refreshSelectedTeamData() {
    if (!state.selectedManagerAddress) {
      state.status = null;
      state.history = null;
      state.capabilities = [];
      renderHeroMetrics();
      renderCapabilityMap();
      renderSnapshot();
      return;
    }
    setChip("snapshot-status", "Loading", "loading");
    try {
      const params = new URLSearchParams({
        manager_address: state.selectedManagerAddress,
        party: state.party
      });
      const [statusPayload, historyPayload, capabilityPayload] = await Promise.all([
        fetchJson(`/api/status?${params.toString()}`),
        fetchJson(`/api/history?${params.toString()}`),
        fetchJson(`/api/jobcaps?${params.toString()}`)
      ]);
      state.status = statusPayload;
      state.history = historyPayload;
      state.capabilities = Array.isArray(capabilityPayload?.job_capabilities) ? capabilityPayload.job_capabilities : [];
      renderHeroMetrics();
      renderCapabilityMap();
      syncCapabilityDatalist();
      renderSnapshot();
      setChip("snapshot-status", "Live", "success");
    } catch (error) {
      state.status = null;
      state.history = null;
      state.capabilities = [];
      renderHeroMetrics();
      renderCapabilityMap();
      renderSnapshot();
      setChip("snapshot-status", error.message || "Error", "error");
    }
  }

  function selectManager(address) {
    state.selectedManagerAddress = String(address || "").trim();
    state.selectedTeam = findSelectedTeam();
    setSelectedManagerInputs(state.selectedManagerAddress);
    renderHeroMetrics();
    renderTeams();
    refreshSelectedTeamData();
  }

  async function refreshTeams() {
    setChip("teams-status", "Loading", "loading");
    try {
      const params = new URLSearchParams({
        party: state.party,
        include_workers: "true"
      });
      const payload = await fetchJson(`/api/teams?${params.toString()}`);
      state.teams = Array.isArray(payload?.teams) ? payload.teams : [];
      state.selectedTeam = findSelectedTeam();
      renderTeams();
      renderHeroMetrics();
      if (!state.selectedTeam && state.teams[0]?.manager_address) {
        selectManager(state.teams[0].manager_address);
      } else if (state.selectedManagerAddress) {
        await refreshSelectedTeamData();
      } else {
        renderSnapshot();
        renderCapabilityMap();
      }
      setChip("teams-status", state.teams.length ? "Synced" : "No Teams", state.teams.length ? "success" : "");
    } catch (error) {
      state.teams = [];
      renderTeams();
      renderHeroMetrics();
      setChip("teams-status", error.message || "Error", "error");
    }
  }

  function collectProvisionPayload(form, kind) {
    const formData = new FormData(form);
    const raw = Object.fromEntries(formData.entries());
    const base = {
      team_name: raw.team_name,
      party: raw.party || state.party
    };
    if (kind === "team") {
      return compactObject({
        ...base,
        plaza_url: raw.plaza_url,
        worker_count: raw.worker_count ? Number.parseInt(String(raw.worker_count), 10) : undefined,
        job_capabilities: parseJsonField(raw.job_capabilities, "Job capabilities")
      });
    }
    if (kind === "manager") {
      return compactObject({
        ...base,
        manager_name: raw.manager_name,
        plaza_url: raw.plaza_url,
        manager_port: raw.manager_port ? Number.parseInt(String(raw.manager_port), 10) : undefined,
        job_capabilities: parseJsonField(raw.job_capabilities, "Job capabilities")
      });
    }
    return compactObject({
      ...base,
      worker_name: raw.worker_name,
      manager_address: raw.manager_address || state.selectedManagerAddress,
      worker_port: raw.worker_port ? Number.parseInt(String(raw.worker_port), 10) : undefined,
      capabilities: parseCsvList(raw.capabilities),
      job_capabilities: parseJsonField(raw.job_capabilities, "Job capabilities")
    });
  }

  async function submitProvision(endpoint, form, kind) {
    setChip("provision-status", "Working", "loading");
    try {
      const payload = collectProvisionPayload(form, kind);
      const response = await fetchJson(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      renderProvisionResult(response);
      setChip("provision-status", "Blueprint Ready", "success");
    } catch (error) {
      byId("provision-result").innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Provisioning failed.")}</div>`;
      setChip("provision-status", error.message || "Error", "error");
    }
  }

  function switchProvisionTab(tabId) {
    state.provisioningTab = tabId;
    Array.from(document.querySelectorAll("[data-provision-tab]")).forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-provision-tab") === tabId);
    });
    Array.from(document.querySelectorAll("[data-provision-panel]")).forEach((panel) => {
      panel.hidden = panel.getAttribute("data-provision-panel") !== tabId;
    });
  }

  function bindEvents() {
    byId("refresh-teams-btn")?.addEventListener("click", () => {
      state.party = String(byId("party-input")?.value || state.party).trim() || "Phemacast";
      refreshTeams();
    });

    byId("party-input")?.addEventListener("change", () => {
      state.party = String(byId("party-input")?.value || state.party).trim() || "Phemacast";
    });

    byId("team-search-input")?.addEventListener("input", renderTeams);
    byId("clear-team-search-btn")?.addEventListener("click", () => {
      const field = byId("team-search-input");
      if (field) field.value = "";
      renderTeams();
    });

    byId("load-job-example-btn")?.addEventListener("click", () => {
      const payloadField = byId("job-payload-input");
      if (payloadField) payloadField.value = formatJson(exampleJobPayload);
      const capabilityField = byId("required-capability-input");
      if (capabilityField && !String(capabilityField.value || "").trim() && exampleJobCapabilities[0]?.name) {
        capabilityField.value = exampleJobCapabilities[0].name;
      }
    });

    byId("load-team-example-btn")?.addEventListener("click", () => {
      const field = byId("team-jobcaps-input");
      if (field) field.value = formatJson(exampleJobCapabilities);
    });
    byId("load-manager-example-btn")?.addEventListener("click", () => {
      const field = byId("manager-jobcaps-input");
      if (field) field.value = formatJson(exampleJobCapabilities);
    });
    byId("load-worker-example-btn")?.addEventListener("click", () => {
      const field = byId("worker-jobcaps-input");
      if (field) field.value = formatJson(exampleJobCapabilities);
      const capsField = byId("worker-capabilities-input");
      if (capsField && !String(capsField.value || "").trim()) capsField.value = exampleJobCapabilities.map((entry) => entry.name).join(", ");
    });

    Array.from(document.querySelectorAll("[data-provision-tab]")).forEach((button) => {
      button.addEventListener("click", () => switchProvisionTab(button.getAttribute("data-provision-tab") || "team"));
    });

    byId("job-submit-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      setChip("job-submit-status", "Sending", "loading");
      try {
        const managerAddress = String(byId("job-manager-address")?.value || "").trim();
        const requiredCapability = String(byId("required-capability-input")?.value || "").trim();
        if (!managerAddress) throw new Error("Manager address is required.");
        if (!requiredCapability) throw new Error("Required capability is required.");
        const payload = {
          manager_address: managerAddress,
          required_capability: requiredCapability,
          priority: Number.parseInt(String(byId("job-priority-input")?.value || "100"), 10),
          payload: parseJsonField(byId("job-payload-input")?.value, "Payload JSON") || {}
        };
        const response = await fetchJson("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        renderJobSubmitResult(response);
        setChip("job-submit-status", "Submitted", "success");
        if (managerAddress === state.selectedManagerAddress) {
          refreshSelectedTeamData();
        }
      } catch (error) {
        byId("job-submit-result").innerHTML = `<div class="empty-state">${escapeHtml(error.message || "Submission failed.")}</div>`;
        setChip("job-submit-status", error.message || "Error", "error");
      }
    });

    byId("provision-team-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitProvision("/api/provision/team", event.currentTarget, "team");
    });

    byId("provision-manager-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitProvision("/api/provision/manager", event.currentTarget, "manager");
    });

    byId("provision-worker-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitProvision("/api/provision/worker", event.currentTarget, "worker");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    seedExamples();
    bindEvents();
    renderHeroMetrics();
    renderTeams();
    renderCapabilityMap();
    renderSnapshot();
    refreshTeams();
  });
})();
