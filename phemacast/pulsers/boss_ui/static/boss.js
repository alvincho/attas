(function () {
  const initial = window.__BOSS_PULSER_INITIAL__ || {};
  const exampleJobCapabilities = Array.isArray(initial?.examples?.team_job_capabilities)
    ? initial.examples.team_job_capabilities
    : [];
  const exampleJobPayload = initial?.examples?.job_payload && typeof initial.examples.job_payload === "object"
    ? initial.examples.job_payload
    : {};
  const exampleTeamManifest = initial?.examples?.team_manifest && typeof initial.examples.team_manifest === "object"
    ? initial.examples.team_manifest
    : {};
  const templateTeamManifest = initial?.defaults?.team_manifest && typeof initial.defaults.team_manifest === "object"
    ? initial.defaults.team_manifest
    : exampleTeamManifest;

  const state = {
    party: String(initial.party || "Phemacast").trim() || "Phemacast",
    teams: [],
    selectedManagerAddress: String(initial?.defaults?.manager_address || "").trim(),
    selectedTeam: null,
    selectedTeamMode: null,
    teamDraft: null,
    teamFeedback: null,
    capabilities: [],
    provisionCatalog: {
      jobCapabilities: [],
      managersForHire: [],
      workersForHire: []
    },
    status: null,
    history: null,
    provisioningTab: String(initial?.ui?.default_provisioning_tab || "team").trim() || "team",
    workspaceTab: "teams",
    heroCollapsed: true,
    selectedJobCapabilities: []
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function readStoredFlag(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw == null) return fallback;
      return raw === "true";
    } catch (_error) {
      return fallback;
    }
  }

  function writeStoredFlag(key, value) {
    try {
      window.localStorage.setItem(key, value ? "true" : "false");
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function readStoredValue(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw == null ? fallback : raw;
    } catch (_error) {
      return fallback;
    }
  }

  function writeStoredValue(key, value) {
    try {
      window.localStorage.setItem(key, String(value));
    } catch (_error) {
      // Ignore storage failures.
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
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

  function parseCsvList(rawValue) {
    return String(rawValue || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function parseInteger(value, fallback) {
    const parsed = Number.parseInt(String(value ?? ""), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function slugifyText(value, fallback) {
    const normalized = String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    return normalized || fallback;
  }

  function normalizeJobCapabilityEntry(entry) {
    if (!entry || typeof entry !== "object") return null;
    const name = String(entry.name || "").trim();
    if (!name) return null;
    const normalized = {
      name,
      description: String(entry.description || "").trim(),
      type: String(entry.type || entry.callable || "").trim(),
      callable: String(entry.callable || entry.type || "").trim()
    };
    const defaultPriority = Number.parseInt(String(entry.default_priority ?? entry.defaultPriority ?? ""), 10);
    if (Number.isFinite(defaultPriority)) normalized.default_priority = defaultPriority;
    return normalized;
  }

  function normalizeJobCapabilityList(entries) {
    const items = Array.isArray(entries) ? entries : [entries];
    const normalized = [];
    const seen = new Set();
    items.forEach((entry) => {
      const item = normalizeJobCapabilityEntry(entry);
      if (!item) return;
      const key = item.name.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      normalized.push(item);
    });
    return normalized;
  }

  function currentTeamName() {
    return String(byId("shared-team-name")?.value || templateTeamManifest.team_name || "Map Runner").trim() || "Map Runner";
  }

  function currentPlazaUrl() {
    return String(byId("shared-plaza-url")?.value || initial.plaza_url || templateTeamManifest.plaza_url || "").trim();
  }

  function currentManagerAddress() {
    return String(
      byId("shared-manager-address")?.value
      || state.selectedManagerAddress
      || initial?.defaults?.manager_address
      || ""
    ).trim();
  }

  function selectedJobCapabilities() {
    return normalizeJobCapabilityList(state.selectedJobCapabilities);
  }

  function draftTeamDescriptor() {
    if (!state.teamDraft || typeof state.teamDraft !== "object") return null;
    const manifest = state.teamDraft?.team_manifest && typeof state.teamDraft.team_manifest === "object"
      ? state.teamDraft.team_manifest
      : {};
    return {
      _draft: true,
      team_name: String(state.teamDraft.team_name || manifest.team_name || currentTeamName()).trim() || "Draft Team",
      manager_name: String(manifest?.manager_defaults?.name || state.teamDraft.manager_name || "Draft Manager").trim() || "Draft Manager",
      manager_address: String(state.teamDraft.manager_address || "").trim(),
      party: String(state.teamDraft.party || manifest.party || state.party).trim() || state.party,
      description: "Draft team ready for staffing.",
      worker_count: Number(state.teamDraft?.worker_configs?.length || manifest?.worker_defaults?.count || 0),
      job_capabilities: normalizeJobCapabilityList(manifest.job_capabilities || state.teamDraft.job_capabilities || []),
    };
  }

  function allTeams() {
    const liveTeams = Array.isArray(state.teams) ? state.teams.slice() : [];
    const draft = draftTeamDescriptor();
    if (!draft) return liveTeams;
    const duplicate = liveTeams.some((team) => {
      const liveAddress = String(team?.manager_address || "").trim();
      const draftAddress = String(draft.manager_address || "").trim();
      if (draftAddress && liveAddress === draftAddress) return true;
      return String(team?.manager_name || "").trim() === draft.manager_name
        && String(team?.party || "").trim() === draft.party;
    });
    return duplicate ? liveTeams : [draft, ...liveTeams];
  }

  function selectedCapabilityNames() {
    return selectedJobCapabilities().map((entry) => entry.name);
  }

  function managerAddressToPort(address, fallback) {
    const text = String(address || "").trim();
    const tail = text.includes(":") ? text.split(":").pop() : "";
    const parsed = Number.parseInt(String(tail || ""), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function currentTeamContext() {
    if ((state.selectedTeamMode === "draft" || (!state.selectedManagerAddress && state.teamDraft)) && state.teamDraft && typeof state.teamDraft === "object") {
      const manifest = state.teamDraft?.team_manifest && typeof state.teamDraft.team_manifest === "object"
        ? state.teamDraft.team_manifest
        : {};
      const jobCapabilities = normalizeJobCapabilityList(
        manifest.job_capabilities || state.teamDraft.job_capabilities || []
      );
      const capabilities = Array.isArray(manifest.capabilities) && manifest.capabilities.length
        ? manifest.capabilities.map((entry) => String(entry || "").trim().toLowerCase()).filter(Boolean)
        : jobCapabilities.map((entry) => String(entry.name || "").trim().toLowerCase()).filter(Boolean);
      return {
        mode: "draft",
        title: String(state.teamDraft.team_name || manifest.team_name || currentTeamName()).trim() || "Phemacast Team",
        description: "Draft team ready for manager and worker actions.",
        managerAddress: String(state.teamDraft.manager_address || "").trim(),
        managerName: String(manifest?.manager_defaults?.name || "").trim(),
        workerCount: Number(state.teamDraft?.worker_configs?.length || manifest?.worker_defaults?.count || 0),
        trackedJobs: 0,
        workerRecords: 0,
        jobCapabilities,
        capabilities,
        teamManifest: manifest,
        managerPulserAddress: String(state.teamDraft?.manager_hires?.[0]?.pulser_address || "").trim(),
      };
    }
    if (state.selectedTeam) {
      const jobCapabilities = normalizeJobCapabilityList(state.selectedTeam.job_capabilities || state.capabilities || []);
      const capabilities = jobCapabilities.map((entry) => String(entry.name || "").trim().toLowerCase()).filter(Boolean);
      return {
        mode: "live",
        title: currentTeamName(),
        description: String(state.selectedTeam.description || "Independent Phemacast teamwork manager.").trim(),
        managerAddress: String(state.selectedTeam.manager_address || "").trim(),
        managerName: String(state.selectedTeam.manager_name || "Manager").trim(),
        workerCount: Number(state.status?.workers?.total || state.selectedTeam.worker_count || 0),
        trackedJobs: Number(state.status?.jobs?.total || 0),
        workerRecords: Number(state.status?.workers?.total || 0),
        jobCapabilities,
        capabilities,
        teamManifest: buildSharedTeamManifest({
          team_name: currentTeamName(),
          manager_name: state.selectedTeam.manager_name,
          manager_port: managerAddressToPort(state.selectedTeam.manager_address, 8170),
          worker_count: Number(state.status?.workers?.total || state.selectedTeam.worker_count || 0),
          job_capabilities: jobCapabilities,
          capabilities,
        }),
        managerPulserAddress: "",
      };
    }
    return null;
  }

  function selectDraftTeam() {
    if (!state.teamDraft || typeof state.teamDraft !== "object") return;
    state.selectedTeamMode = "draft";
    state.selectedManagerAddress = "";
    state.selectedTeam = null;
    setSelectedManagerInputs("");
    switchWorkspaceTab("teams");
    renderHeroMetrics();
    renderTeams();
    renderCapabilityMap();
    renderSnapshot();
  }

  function buildSharedTeamManifest(overrides) {
    const options = overrides && typeof overrides === "object" ? overrides : {};
    const bossDefaults = templateTeamManifest?.boss_defaults && typeof templateTeamManifest.boss_defaults === "object"
      ? templateTeamManifest.boss_defaults
      : {};
    const managerDefaults = templateTeamManifest?.manager_defaults && typeof templateTeamManifest.manager_defaults === "object"
      ? templateTeamManifest.manager_defaults
      : {};
    const workerDefaults = templateTeamManifest?.worker_defaults && typeof templateTeamManifest.worker_defaults === "object"
      ? templateTeamManifest.worker_defaults
      : {};
    const teamName = String(options.team_name || currentTeamName()).trim() || "Phemacast Team";
    const teamSlug = slugifyText(options.team_slug || templateTeamManifest.team_slug || teamName, "phemacast-team");
    const jobCapabilities = normalizeJobCapabilityList(
      options.job_capabilities && Array.isArray(options.job_capabilities)
        ? options.job_capabilities
        : selectedJobCapabilities()
    );
    const capabilities = Array.isArray(options.capabilities) && options.capabilities.length
      ? options.capabilities.map((entry) => String(entry || "").trim().toLowerCase()).filter(Boolean)
      : jobCapabilities.map((entry) => entry.name);
    const managerName = String(options.manager_name || managerDefaults.name || `${teamName.replace(/\s+/g, "")}Manager`).trim();
    const managerPort = parseInteger(options.manager_port, parseInteger(managerDefaults.port, 8170));
    const workerCount = Math.max(parseInteger(options.worker_count, parseInteger(workerDefaults.count, 0)), 0);
    const workerNamePrefix = String(options.worker_name_prefix || workerDefaults.name_prefix || `${teamName.replace(/\s+/g, "")}Worker`).trim();
    const workerBasePort = parseInteger(options.worker_base_port, parseInteger(workerDefaults.base_port, managerPort + 1));
    return {
      api_version: String(templateTeamManifest.api_version || "phemacast.team_manifest.v1").trim() || "phemacast.team_manifest.v1",
      team_name: teamName,
      team_slug: teamSlug,
      party: state.party,
      plaza_url: currentPlazaUrl(),
      job_capabilities: jobCapabilities,
      capabilities,
      boss_defaults: {
        name: String(bossDefaults.name || `${teamName.replace(/\s+/g, "")}Boss`).trim(),
        host: String(bossDefaults.host || "127.0.0.1").trim(),
        port: parseInteger(bossDefaults.port, 8175),
        type: String(bossDefaults.type || "prompits.teamwork.boss.TeamBossAgent").trim(),
        monitor_refresh_sec: parseInteger(bossDefaults.monitor_refresh_sec, 10),
        auto_register: bossDefaults.auto_register !== false
      },
      manager_defaults: {
        name: managerName,
        host: String(options.manager_host || managerDefaults.host || "127.0.0.1").trim(),
        port: managerPort,
        type: String(options.manager_class || managerDefaults.type || "prompits.teamwork.agents.DispatcherManagerAgent").trim(),
        auto_register: managerDefaults.auto_register !== false
      },
      worker_defaults: {
        name_prefix: workerNamePrefix,
        host: String(options.worker_host || workerDefaults.host || "127.0.0.1").trim(),
        base_port: workerBasePort,
        count: workerCount,
        capabilities,
        job_capabilities: jobCapabilities,
        poll_interval_sec: parseInteger(options.poll_interval_sec, parseInteger(workerDefaults.poll_interval_sec, 10)),
        auto_register: workerDefaults.auto_register !== false
      }
    };
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
    state.selectedJobCapabilities = normalizeJobCapabilityList(
      Array.isArray(templateTeamManifest?.job_capabilities) && templateTeamManifest.job_capabilities.length
        ? templateTeamManifest.job_capabilities
        : exampleJobCapabilities
    );
    const teamNameField = byId("shared-team-name");
    if (teamNameField && !String(teamNameField.value || "").trim() && templateTeamManifest?.team_name) {
      teamNameField.value = String(templateTeamManifest.team_name);
    }
    const plazaField = byId("shared-plaza-url");
    if (plazaField && !String(plazaField.value || "").trim() && templateTeamManifest?.plaza_url) {
      plazaField.value = String(templateTeamManifest.plaza_url);
    }
    const managerField = byId("shared-manager-address");
    if (managerField && !String(managerField.value || "").trim() && initial?.defaults?.manager_address) {
      managerField.value = String(initial.defaults.manager_address);
    }
    const phemaField = byId("job-phema-path-input");
    if (phemaField && !String(phemaField.value || "").trim() && exampleJobPayload?.phema_path) {
      phemaField.value = String(exampleJobPayload.phema_path);
    }
    const targetsField = byId("job-targets-input");
    if (targetsField && !String(targetsField.value || "").trim() && Array.isArray(exampleJobPayload?.targets)) {
      targetsField.value = exampleJobPayload.targets.join(", ");
    }
  }

  function filteredTeams() {
    const searchValue = String(byId("team-search-input")?.value || "").trim().toLowerCase();
    const teams = allTeams();
    if (!searchValue) return teams;
    return teams.filter((team) => {
      const haystack = [
        team.team_name,
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
    const teams = allTeams();
    const workerCount = teams.reduce((total, team) => total + Number(team.worker_count || 0), 0);
    setMetric("teams", String(teams.length));
    setMetric("workers", String(workerCount));
    setMetric("jobcaps", String(state.capabilities.length));
    setMetric("manager", state.selectedManagerAddress ? state.selectedManagerAddress : "None");
  }

  function renderSharedContext() {
    const partyNode = byId("shared-party-display");
    if (partyNode) partyNode.textContent = state.party;
    const managerAddress = currentManagerAddress();
    const managerMessage = managerAddress
      ? `Using ${managerAddress}.`
      : "Pick a team or enter one address.";
    ["mission-manager-note", "worker-manager-note"].forEach((id) => {
      const node = byId(id);
      if (node) node.textContent = managerMessage;
    });
  }

  function renderSelectedJobcapSummary() {
    const container = byId("selected-jobcap-summary");
    if (!container) return;
    const entries = selectedJobCapabilities();
    if (!entries.length) {
      container.innerHTML = '<div class="empty-state">No caps selected.</div>';
      return;
    }
    container.innerHTML = entries
      .map((entry) => `<span class="badge selection-chip">${escapeHtml(entry.name)}</span>`)
      .join("");
  }

  function renderTeams() {
    const container = byId("teams-list");
    if (!container) return;
    const teams = filteredTeams();
    if (!teams.length) {
      container.innerHTML = `<div class="empty-state">${allTeams().length ? "No match." : "No teams yet."}</div>`;
      return;
    }
    container.innerHTML = teams
      .map((team, index) => {
        const isDraft = Boolean(team._draft);
        const isSelected = isDraft
          ? state.selectedTeamMode === "draft" || (!state.selectedManagerAddress && Boolean(state.teamDraft))
          : state.selectedTeamMode !== "draft" && team.manager_address === state.selectedManagerAddress;
        const capabilityNames = Array.isArray(team.job_capabilities)
          ? team.job_capabilities.map((entry) => entry?.name).filter(Boolean).slice(0, 4)
          : [];
        return `
          <button
            type="button"
            class="team-card fade-in${isSelected ? " is-selected" : ""}"
            ${isDraft ? 'data-team-draft="true"' : `data-manager-address="${escapeHtml(team.manager_address || "")}"`}
            style="animation-delay:${index * 40}ms"
          >
            <div class="team-card-header">
              <strong>${escapeHtml(isDraft ? (team.team_name || "Draft Team") : (team.manager_name || "Manager"))}</strong>
              <span class="badge">${escapeHtml(isDraft ? "Draft" : `${team.worker_count || 0} workers`)}</span>
            </div>
            <div class="mono">${escapeHtml(team.manager_address || (isDraft ? "Manager pending" : "No manager address"))}</div>
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
    Array.from(container.querySelectorAll("[data-team-draft]")).forEach((node) => {
      node.addEventListener("click", () => selectDraftTeam());
    });
  }

  function renderCapabilityMap() {
    const container = byId("capability-map");
    if (!container) return;
    const currentTeam = currentTeamContext();
    const currentCapabilities = currentTeam?.jobCapabilities?.length
      ? currentTeam.jobCapabilities
      : state.capabilities;
    if (!currentTeam && !state.selectedManagerAddress) {
      container.innerHTML = '<div class="empty-state">Pick a team.</div>';
      return;
    }
    if (!currentCapabilities.length) {
      container.innerHTML = '<div class="empty-state">No cap data.</div>';
      return;
    }
    container.innerHTML = currentCapabilities
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
    const team = currentTeamContext();
    if (!team) {
      container.innerHTML = '<div class="empty-state">Pick or create a team.</div>';
      return;
    }
    container.innerHTML = `
      <div class="fade-in">
        <div class="mono-label">${escapeHtml(team.mode === "draft" ? "Draft Team" : "Selected Team")}</div>
        <h3 class="summary-title">${escapeHtml(team.title || "Team")}</h3>
        <p class="summary-lead">${escapeHtml(team.description || "Teamwork team.")}</p>
        <div class="mono">${escapeHtml(team.managerAddress || "Manager address pending")}</div>
        <div class="badge-row">
          <span class="badge">${escapeHtml(state.party)}</span>
          <span class="badge">${escapeHtml(`${team.managerName || "Manager"} manager`)}</span>
          <span class="badge">${escapeHtml(`${team.workerCount || 0} workers`)}</span>
          <span class="badge">${escapeHtml(`${team.trackedJobs || 0} tracked jobs`)}</span>
          <span class="badge">${escapeHtml(`${team.jobCapabilities.length || 0} job caps`)}</span>
        </div>
      </div>
    `;
  }

  function renderTeamsFeedback() {
    const container = byId("teams-feedback");
    if (!container) return;
    if (!state.teamFeedback || typeof state.teamFeedback !== "object") {
      container.innerHTML = '<div class="empty-state">Create or select a team.</div>';
      return;
    }
    container.innerHTML = `
      <article class="result-card fade-in">
        <div class="result-meta">
          <strong>${escapeHtml(state.teamFeedback.title || "Team Action")}</strong>
          <span class="badge">${escapeHtml(state.teamFeedback.mode || "ready")}</span>
        </div>
        <div class="pill-row">
          ${(Array.isArray(state.teamFeedback.items) ? state.teamFeedback.items : [])
            .map((item) => `<span class="badge">${escapeHtml(item)}</span>`)
            .join("")}
        </div>
      </article>
    `;
  }

  function filteredHireableWorkers() {
    const workers = Array.isArray(state.provisionCatalog.workersForHire) ? state.provisionCatalog.workersForHire : [];
    const currentTeam = currentTeamContext();
    if (!currentTeam || !Array.isArray(currentTeam.capabilities) || !currentTeam.capabilities.length) {
      return workers;
    }
    const requested = new Set(currentTeam.capabilities.map((entry) => String(entry || "").trim().toLowerCase()).filter(Boolean));
    return workers.filter((worker) => {
      const capabilities = Array.isArray(worker.capabilities) ? worker.capabilities : [];
      const capabilityNames = capabilities.map((entry) => String(entry || "").trim().toLowerCase()).filter(Boolean);
      const jobCaps = Array.isArray(worker.job_capabilities) ? worker.job_capabilities : [];
      const jobCapNames = jobCaps.map((entry) => String(entry?.name || "").trim().toLowerCase()).filter(Boolean);
      return capabilityNames.some((capability) => requested.has(capability))
        || jobCapNames.some((capability) => requested.has(capability));
    });
  }

  function renderTeamManagerActions() {
    const note = byId("team-manager-note");
    const container = byId("team-manager-catalog");
    if (!note || !container) return;
    const currentTeam = currentTeamContext();
    if (!currentTeam) {
      note.textContent = "Pick one team to add a manager.";
      container.innerHTML = '<div class="empty-state">No managers ready.</div>';
      return;
    }
    const managers = Array.isArray(state.provisionCatalog.managersForHire) ? state.provisionCatalog.managersForHire : [];
    note.textContent = `Add one manager to ${currentTeam.title}.`;
    if (!managers.length) {
      container.innerHTML = '<div class="empty-state">No managers ready.</div>';
      return;
    }
    const preferredAddress = String(currentTeam.managerPulserAddress || "").trim();
    container.innerHTML = managers
      .map((manager, index) => {
        const address = String(manager.pulser_address || "").trim();
        const isChecked = preferredAddress ? preferredAddress === address : index === 0;
        return `
          <label class="catalog-card manager-card is-selectable fade-in${isChecked ? " is-selected" : ""}">
            <input
              type="radio"
              name="team-manager-radio"
              data-team-manager-radio
              value="${escapeHtml(address)}"
              data-pulser-address="${escapeHtml(address)}"
              data-pulser-name="${escapeHtml(manager.name || "ManagerPulser")}"
              ${isChecked ? "checked" : ""}
            >
            <div class="catalog-card-head">
              <div class="catalog-card-title">
                <strong>${escapeHtml(manager.name || "ManagerPulser")}</strong>
                <div class="mono">${escapeHtml(address)}</div>
              </div>
              <span class="badge">${escapeHtml(manager.hire_ready ? "Ready" : "Hold")}</span>
            </div>
          </label>
        `;
      })
      .join("");
    Array.from(container.querySelectorAll("[data-team-manager-radio]")).forEach((radio) => {
      radio.addEventListener("change", () => {
        Array.from(container.querySelectorAll(".catalog-card")).forEach((card) => card.classList.remove("is-selected"));
        radio.closest(".catalog-card")?.classList.add("is-selected");
      });
    });
  }

  function renderTeamWorkerActions() {
    const note = byId("team-worker-note");
    const container = byId("team-worker-catalog");
    if (!note || !container) return;
    const currentTeam = currentTeamContext();
    if (!currentTeam) {
      note.textContent = "Pick one team to hire or create a worker.";
      container.innerHTML = '<div class="empty-state">No workers ready.</div>';
      return;
    }
    note.textContent = currentTeam.managerAddress
      ? `Workers matching ${currentTeam.title}.`
      : `Create or attach workers for ${currentTeam.title}.`;
    const workers = filteredHireableWorkers();
    if (!workers.length) {
      container.innerHTML = '<div class="empty-state">No matching workers ready.</div>';
      return;
    }
    container.innerHTML = workers
      .map((worker, index) => {
        const address = String(worker.worker_address || "").trim();
        return `
          <label class="catalog-card manager-card is-selectable fade-in${index === 0 ? " is-selected" : ""}">
            <input
              type="radio"
              name="team-worker-radio"
              data-team-worker-radio
              value="${escapeHtml(address)}"
              data-worker-address="${escapeHtml(address)}"
              data-worker-name="${escapeHtml(worker.name || "Worker")}"
              ${index === 0 ? "checked" : ""}
            >
            <div class="catalog-card-head">
              <div class="catalog-card-title">
                <strong>${escapeHtml(worker.name || "Worker")}</strong>
                <div class="mono">${escapeHtml(address)}</div>
              </div>
              <span class="badge">${escapeHtml(worker.hire_ready ? "Ready" : "Busy")}</span>
            </div>
            <div class="badge-row manager-card-meta">
              ${(Array.isArray(worker.job_capabilities) ? worker.job_capabilities : [])
                .slice(0, 3)
                .map((entry) => `<span class="badge">${escapeHtml(entry?.name || "")}</span>`)
                .join("")}
            </div>
          </label>
        `;
      })
      .join("");
    Array.from(container.querySelectorAll("[data-team-worker-radio]")).forEach((radio) => {
      radio.addEventListener("change", () => {
        Array.from(container.querySelectorAll(".catalog-card")).forEach((card) => card.classList.remove("is-selected"));
        radio.closest(".catalog-card")?.classList.add("is-selected");
      });
    });
  }

  function renderWorkerHealth() {
    const container = byId("worker-health");
    if (!container) return;
    const roster = Array.isArray(state.status?.workers?.roster) ? state.status.workers.roster : [];
    if (!roster.length) {
      container.innerHTML = '<div class="empty-state">No worker data.</div>';
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
      container.innerHTML = '<div class="empty-state">No recent jobs.</div>';
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
      container.innerHTML = '<div class="empty-state">No history yet.</div>';
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
    renderTeamsFeedback();
    renderTeamManagerActions();
    renderTeamWorkerActions();
    renderWorkerHealth();
    renderQueueStatus();
    renderRecentJobs();
    renderWorkerHistory();
    const currentTeam = currentTeamContext();
    const workerNameField = byId("team-local-worker-name");
    const workerPortField = byId("team-local-worker-port");
    if (currentTeam && workerNameField && !String(workerNameField.value || "").trim()) {
      workerNameField.value = `${slugifyText(currentTeam.title, "team")}-worker-1`;
    }
    if (currentTeam && workerPortField && !String(workerPortField.value || "").trim()) {
      workerPortField.value = String(managerAddressToPort(currentTeam.managerAddress, 8271) + 1);
    }
  }

  function renderJobSubmitResult(payload, requestPayload) {
    const container = byId("job-submit-result");
    if (!container) return;
    const submitted = payload?.submitted || {};
    const job = submitted?.job && typeof submitted.job === "object" ? submitted.job : submitted;
    const meta = [
      payload?.required_capability ? ["Capability", payload.required_capability] : null,
      payload?.manager?.manager_address ? ["Manager", payload.manager.manager_address] : null,
      job?.id ? ["Job ID", job.id] : null,
      job?.status ? ["Status", job.status] : null,
      requestPayload?.payload?.phema_path ? ["Phema", requestPayload.payload.phema_path] : null,
      Array.isArray(requestPayload?.targets) && requestPayload.targets.length ? ["Targets", requestPayload.targets.join(", ")] : null
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
    `;
  }

  function setSelectedManagerInputs(address) {
    const normalized = String(address || "").trim();
    const sharedField = byId("shared-manager-address");
    if (sharedField) sharedField.value = normalized;
    renderSharedContext();
  }

  function syncCapabilityDatalist() {
    const datalist = byId("capability-datalist");
    if (!datalist) return;
    const entries = normalizeJobCapabilityList([...(state.capabilities || []), ...selectedJobCapabilities()]);
    datalist.innerHTML = entries
      .map((entry) => `<option value="${escapeHtml(entry.name || "")}"></option>`)
      .join("");
    const capabilityField = byId("required-capability-input");
    if (capabilityField && !String(capabilityField.value || "").trim() && entries[0]?.name) {
      capabilityField.value = entries[0].name;
    }
  }

  function updateHireSelectionSummary() {
    const node = byId("team-hire-selection-summary");
    if (!node) return;
    const selected = Array.from(document.querySelectorAll("[data-hire-manager-checkbox]:checked"));
    if (!selected.length) {
      const total = document.querySelectorAll("[data-hire-manager-checkbox]").length;
      node.textContent = total ? "Pick at least one manager." : "No managers available.";
      return;
    }
    const names = selected
      .map((entry) => String(entry.dataset.pulserName || entry.value || "").trim())
      .filter(Boolean);
    node.textContent = `${selected.length} manager${selected.length === 1 ? "" : "s"} selected: ${names.join(", ")}`;
  }

  function syncHireManagerSelectionClasses() {
    Array.from(document.querySelectorAll("[data-hire-manager-checkbox]")).forEach((checkbox) => {
      checkbox.closest(".catalog-card")?.classList.toggle("is-selected", checkbox.checked);
    });
  }

  function ensureHireManagerSelection() {
    const checkboxes = Array.from(document.querySelectorAll("[data-hire-manager-checkbox]"));
    if (!checkboxes.length) return;
    if (checkboxes.some((checkbox) => checkbox.checked)) {
      syncHireManagerSelectionClasses();
      updateHireSelectionSummary();
      return;
    }
    const preferred = checkboxes.find((checkbox) => String(checkbox.dataset.hireReady || "").toLowerCase() === "true");
    if (preferred) preferred.checked = true;
    syncHireManagerSelectionClasses();
    updateHireSelectionSummary();
  }

  function toggleJobCapabilitySelection(entryName) {
    const normalizedName = String(entryName || "").trim().toLowerCase();
    if (!normalizedName) return;
    const availableEntries = normalizeJobCapabilityList([
      ...state.provisionCatalog.jobCapabilities,
      ...selectedJobCapabilities(),
      ...exampleJobCapabilities
    ]);
    const existing = selectedJobCapabilities();
    const isSelected = existing.some((entry) => String(entry.name || "").trim().toLowerCase() === normalizedName);
    if (isSelected) {
      state.selectedJobCapabilities = existing.filter((entry) => String(entry.name || "").trim().toLowerCase() !== normalizedName);
    } else {
      const match = availableEntries.find((entry) => String(entry.name || "").trim().toLowerCase() === normalizedName);
      if (!match) return;
      state.selectedJobCapabilities = normalizeJobCapabilityList([...existing, match]);
    }
    renderSelectedJobcapSummary();
    renderTeamJobcapCatalog();
    syncCapabilityDatalist();
  }

  function renderTeamJobcapCatalog() {
    const container = byId("team-jobcap-catalog");
    if (!container) return;
    const entries = normalizeJobCapabilityList([
      ...(Array.isArray(state.provisionCatalog.jobCapabilities) ? state.provisionCatalog.jobCapabilities : []),
      ...selectedJobCapabilities()
    ]);
    if (!entries.length) {
      container.innerHTML = '<div class="empty-state">No caps yet.</div>';
      return;
    }
    const selectedNames = new Set(selectedJobCapabilities().map((entry) => String(entry.name || "").trim().toLowerCase()));
    container.innerHTML = entries
      .map((entry) => {
        const providers = Array.isArray(entry.providers) ? entry.providers : [];
        const isSelected = selectedNames.has(String(entry.name || "").trim().toLowerCase());
        return `
          <article class="catalog-card fade-in${isSelected ? " is-selected" : ""}">
            <div class="catalog-card-head">
              <div class="catalog-card-title">
                <strong>${escapeHtml(entry.name || "capability")}</strong>
                <div class="mono">${escapeHtml(entry.type || entry.callable || "No callable advertised")}</div>
              </div>
              <button type="button" class="ghost-btn catalog-action-btn${isSelected ? " is-selected" : ""}" data-toggle-jobcap="${escapeHtml(entry.name || "")}">
                ${isSelected ? "Selected" : "Select"}
              </button>
            </div>
            <p>${escapeHtml(entry.description || "No description configured.")}</p>
            <div class="badge-row">
              ${providers.map((provider) => `<span class="badge">${escapeHtml(`${provider.type}:${provider.name}`)}</span>`).join("")}
            </div>
          </article>
        `;
      })
      .join("");
    Array.from(container.querySelectorAll("[data-toggle-jobcap]")).forEach((button) => {
      button.addEventListener("click", () => {
        toggleJobCapabilitySelection(button.getAttribute("data-toggle-jobcap") || "");
      });
    });
  }

  function renderHireableManagers() {
    const container = byId("hireable-managers-list");
    if (!container) return;
    const managers = Array.isArray(state.provisionCatalog.managersForHire) ? state.provisionCatalog.managersForHire : [];
    if (!managers.length) {
      container.innerHTML = '<div class="empty-state">No managers yet.</div>';
      updateHireSelectionSummary();
      return;
    }
    container.innerHTML = managers
      .map((manager, index) => `
        <label class="catalog-card manager-card is-selectable fade-in" style="animation-delay:${index * 35}ms">
          <input
            type="checkbox"
            data-hire-manager-checkbox
            value="${escapeHtml(manager.pulser_address || "")}"
            data-pulser-address="${escapeHtml(manager.pulser_address || "")}"
            data-pulser-name="${escapeHtml(manager.name || "ManagerPulser")}"
            data-hire-ready="${manager.hire_ready ? "true" : "false"}"
          >
          <div class="catalog-card-head">
            <div class="catalog-card-title">
              <strong>${escapeHtml(manager.name || "ManagerPulser")}</strong>
              <div class="mono">${escapeHtml(manager.pulser_address || "")}</div>
            </div>
            <span class="badge">${escapeHtml(manager.hire_ready ? "Hire Ready" : "Unavailable")}</span>
          </div>
        </label>
      `)
      .join("");
    Array.from(container.querySelectorAll("[data-hire-manager-checkbox]")).forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        syncHireManagerSelectionClasses();
        updateHireSelectionSummary();
      });
    });
    ensureHireManagerSelection();
  }

  function setProvisionFeedback(message) {
    const node = byId("provision-feedback");
    if (node) node.textContent = String(message || "").trim() || "Create a team here, then manage managers and workers in Teams.";
  }

  function setTeamFeedback(title, items, mode) {
    state.teamFeedback = {
      title: String(title || "Team Action").trim(),
      items: Array.isArray(items) ? items.filter(Boolean) : [],
      mode: String(mode || "ready").trim() || "ready",
    };
    renderTeamsFeedback();
  }

  async function refreshProvisionCatalog() {
    try {
      const params = new URLSearchParams({ party: state.party });
      const payload = await fetchJson(`/api/provision/catalog?${params.toString()}`);
      state.provisionCatalog = {
        jobCapabilities: Array.isArray(payload?.job_capabilities) ? payload.job_capabilities : [],
        managersForHire: Array.isArray(payload?.managers_for_hire) ? payload.managers_for_hire : [],
        workersForHire: Array.isArray(payload?.workers_for_hire) ? payload.workers_for_hire : []
      };
    } catch (_error) {
      state.provisionCatalog = { jobCapabilities: [], managersForHire: [], workersForHire: [] };
    }
    renderSelectedJobcapSummary();
    renderTeamJobcapCatalog();
    renderHireableManagers();
    renderTeamManagerActions();
    renderTeamWorkerActions();
    syncCapabilityDatalist();
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
    state.selectedTeamMode = "live";
    state.selectedManagerAddress = String(address || "").trim();
    state.selectedTeam = findSelectedTeam();
    setSelectedManagerInputs(state.selectedManagerAddress);
    switchWorkspaceTab("teams");
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
      if (!state.teamDraft && !state.selectedTeam && state.teams[0]?.manager_address) {
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
    const sharedTeamName = currentTeamName();
    const sharedPlazaUrl = currentPlazaUrl();
    const sharedManagerAddress = currentManagerAddress();
    const sharedJobCapabilities = selectedJobCapabilities();
    const base = {
      team_name: sharedTeamName,
      party: state.party,
      plaza_url: sharedPlazaUrl
    };
    if (kind === "team") {
      const selectedManagers = Array.from(document.querySelectorAll("[data-hire-manager-checkbox]:checked"))
        .map((entry) => ({
          pulser_address: String(entry.dataset.pulserAddress || entry.value || "").trim(),
          pulser_name: String(entry.dataset.pulserName || "").trim(),
          worker_count: parseInteger(raw.hire_worker_count, 1),
          worker_name_prefix: String(raw.hire_worker_name_prefix || "").trim(),
          worker_base_port: parseInteger(raw.hire_worker_base_port, 8271)
        }))
        .filter((entry) => entry.pulser_address);
      return compactObject({
        ...base,
        worker_count: raw.worker_count ? Number.parseInt(String(raw.worker_count), 10) : undefined,
        job_capabilities: sharedJobCapabilities,
        start_hiring_managers: true,
        require_manager_hire: true,
        manager_hires: selectedManagers
      });
    }
    if (kind === "manager") {
      const teamManifest = buildSharedTeamManifest({
        manager_name: raw.manager_name,
        manager_port: raw.manager_port,
        worker_count: raw.worker_count,
        worker_name_prefix: raw.worker_name_prefix,
        worker_base_port: raw.worker_base_port
      });
      return compactObject({
        ...base,
        manager_name: raw.manager_name,
        manager_port: raw.manager_port ? Number.parseInt(String(raw.manager_port), 10) : undefined,
        worker_count: raw.worker_count ? Number.parseInt(String(raw.worker_count), 10) : undefined,
        worker_name_prefix: raw.worker_name_prefix,
        worker_base_port: raw.worker_base_port ? Number.parseInt(String(raw.worker_base_port), 10) : undefined,
        team_manifest: teamManifest,
        job_capabilities: sharedJobCapabilities
      });
    }
    return compactObject({
      ...base,
      worker_name: raw.worker_name,
      manager_address: sharedManagerAddress,
      worker_port: raw.worker_port ? Number.parseInt(String(raw.worker_port), 10) : undefined,
      capabilities: selectedCapabilityNames(),
      job_capabilities: sharedJobCapabilities
    });
  }

  async function submitProvision(endpoint, form, kind) {
    setChip("provision-status", "Working", "loading");
    setProvisionFeedback("Working...");
    try {
      let payload = collectProvisionPayload(form, kind);
      if (kind === "team" && (!Array.isArray(payload.manager_hires) || !payload.manager_hires.length)) {
        ensureHireManagerSelection();
        payload = collectProvisionPayload(form, kind);
      }
      if (kind === "team" && (!Array.isArray(payload.manager_hires) || !payload.manager_hires.length)) {
        throw new Error("No hire-ready manager.");
      }
      const response = await fetchJson(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (kind === "team") {
        state.teamDraft = response;
        state.selectedTeamMode = "draft";
        state.selectedManagerAddress = "";
        state.selectedTeam = null;
        setSelectedManagerInputs("");
        setTeamFeedback(
          `Team Ready: ${response.team_name || payload.team_name || "Phemacast Team"}`,
          [
            `${(response.manager_hires || []).length || 0} manager plans`,
            `${(response.worker_configs || []).length || 0} worker plans`,
            "Open Teams to add managers or workers.",
          ],
          "ready"
        );
        setProvisionFeedback("Team blueprint ready. Open Teams for manager and worker actions.");
        switchWorkspaceTab("teams");
        renderTeams();
        renderHeroMetrics();
        renderCapabilityMap();
        renderSnapshot();
      } else if (kind === "manager") {
        setTeamFeedback(
          `Manager Joined: ${response.team_membership?.manager_name || response.manager_address || "Manager"}`,
          [
            response.team_membership?.manager_address || response.manager_address || "",
            `${(response.worker_configs || []).length || 0} local worker plans`,
          ],
          "ready"
        );
        setProvisionFeedback("Manager join plan ready. Open Teams to continue.");
        switchWorkspaceTab("teams");
      } else {
        setTeamFeedback(
          `Worker Ready: ${response.worker_config?.name || response.worker?.worker_name || payload.worker_name || "Worker"}`,
          [response.worker_config?.config_path || response.worker?.config_path || ""],
          "ready"
        );
        setProvisionFeedback("Worker blueprint ready. Open Teams to continue.");
        switchWorkspaceTab("teams");
      }
      setChip("provision-status", "Blueprint Ready", "success");
    } catch (error) {
      setProvisionFeedback(error.message || "Provisioning failed.");
      setChip("provision-status", error.message || "Error", "error");
    }
  }

  function switchProvisionTab(tabId) {
    const buttons = Array.from(document.querySelectorAll("[data-provision-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-provision-panel]"));
    if (!buttons.length && !panels.length) return;
    state.provisioningTab = tabId;
    writeStoredValue("boss-ui-provision-tab", tabId);
    buttons.forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-provision-tab") === tabId);
    });
    let activePanel = null;
    panels.forEach((panel) => {
      const isActive = panel.getAttribute("data-provision-panel") === tabId;
      panel.hidden = !isActive;
      if (isActive) activePanel = panel;
    });
    const focusTarget = activePanel?.querySelector("input, textarea, button");
    if (focusTarget instanceof HTMLElement) {
      window.requestAnimationFrame(() => focusTarget.focus({ preventScroll: true }));
    }
  }

  function applyHeroCollapsed() {
    const hero = document.querySelector(".hero");
    const toggle = byId("hero-toggle-btn");
    if (!hero || !toggle) return;
    hero.classList.toggle("is-collapsed", state.heroCollapsed);
    toggle.textContent = state.heroCollapsed ? "Expand Overview" : "Collapse Overview";
    toggle.setAttribute("aria-expanded", String(!state.heroCollapsed));
  }

  function toggleHeroCollapsed(forceValue) {
    state.heroCollapsed = typeof forceValue === "boolean" ? forceValue : !state.heroCollapsed;
    writeStoredFlag("boss-ui-hero-collapsed", state.heroCollapsed);
    applyHeroCollapsed();
  }

  function switchWorkspaceTab(tabId) {
    state.workspaceTab = tabId;
    writeStoredValue("boss-ui-workspace-tab", tabId);
    Array.from(document.querySelectorAll("[data-workspace-tab]")).forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-workspace-tab") === tabId);
    });
    Array.from(document.querySelectorAll("[data-workspace-panel]")).forEach((panel) => {
      panel.hidden = panel.getAttribute("data-workspace-panel") !== tabId;
    });
  }

  function selectedManagerCandidateForTeam() {
    const selected = document.querySelector("[data-team-manager-radio]:checked");
    if (!(selected instanceof HTMLInputElement)) return null;
    return {
      pulser_address: String(selected.dataset.pulserAddress || selected.value || "").trim(),
      pulser_name: String(selected.dataset.pulserName || "").trim(),
    };
  }

  function selectedWorkerCandidateForTeam() {
    const selected = document.querySelector("[data-team-worker-radio]:checked");
    if (!(selected instanceof HTMLInputElement)) return null;
    return {
      worker_address: String(selected.dataset.workerAddress || selected.value || "").trim(),
      worker_name: String(selected.dataset.workerName || "").trim(),
    };
  }

  function currentTeamManagerPulserAddress() {
    const currentTeam = currentTeamContext();
    if (currentTeam?.managerPulserAddress) return currentTeam.managerPulserAddress;
    if (currentTeam?.managerAddress) {
      const match = (Array.isArray(state.provisionCatalog.managersForHire) ? state.provisionCatalog.managersForHire : [])
        .find((entry) => String(entry.manager_address || "").trim() === currentTeam.managerAddress);
      if (match?.pulser_address) return String(match.pulser_address).trim();
    }
    return selectedManagerCandidateForTeam()?.pulser_address || "";
  }

  async function addManagerToCurrentTeam() {
    const currentTeam = currentTeamContext();
    if (!currentTeam?.teamManifest) throw new Error("Select or create a team first.");
    const managerCandidate = selectedManagerCandidateForTeam();
    if (!managerCandidate?.pulser_address) throw new Error("Select a manager pulser.");
    const provisionForm = byId("provision-team-form");
    const formData = provisionForm ? new FormData(provisionForm) : new FormData();
    const raw = Object.fromEntries(formData.entries());
    const payload = {
      party: state.party,
      team_name: currentTeam.title,
      team_manifest: currentTeam.teamManifest,
      manager_hires: [
        {
          pulser_address: managerCandidate.pulser_address,
          pulser_name: managerCandidate.pulser_name,
          manager_name: managerCandidate.pulser_name,
          worker_count: parseInteger(raw.hire_worker_count, 1),
          worker_name_prefix: String(raw.hire_worker_name_prefix || "").trim(),
          worker_base_port: parseInteger(raw.hire_worker_base_port, 8271),
        }
      ],
    };
    const response = await fetchJson("/api/team-actions/add-manager", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (state.teamDraft && typeof state.teamDraft === "object") {
      state.teamDraft.manager_hires = Array.isArray(state.teamDraft.manager_hires)
        ? [...state.teamDraft.manager_hires, ...(response.manager_hires || [])]
        : [...(response.manager_hires || [])];
      if (response.primary_manager_address) state.teamDraft.manager_address = response.primary_manager_address;
    }
    setTeamFeedback(
      `Manager Added: ${managerCandidate.pulser_name || "ManagerPulser"}`,
      [
        response.primary_manager_address || "",
        `${response.added || 0} manager joined`,
      ],
      "ready"
    );
    renderSnapshot();
    renderTeams();
    await refreshProvisionCatalog();
  }

  async function hireWorkerForCurrentTeam() {
    const currentTeam = currentTeamContext();
    if (!currentTeam?.managerAddress) throw new Error("Select a live or planned manager first.");
    const workerCandidate = selectedWorkerCandidateForTeam();
    if (!workerCandidate?.worker_address) throw new Error("Select a worker pulser.");
    const payload = {
      party: state.party,
      manager_address: currentTeam.managerAddress,
      manager_name: currentTeam.managerName || "Manager",
      worker_address: workerCandidate.worker_address,
      worker_name: workerCandidate.worker_name,
      capability: currentTeam.capabilities?.[0] || "",
    };
    const response = await fetchJson("/api/team-actions/hire-worker", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setTeamFeedback(
      `Worker Hired: ${workerCandidate.worker_name || "Worker"}`,
      [
        response.assignment?.worker_address || workerCandidate.worker_address,
        response.assignment?.manager_address || currentTeam.managerAddress,
      ],
      "ready"
    );
    await refreshProvisionCatalog();
    if (state.selectedTeam) await refreshSelectedTeamData();
  }

  async function createLocalWorkerForCurrentTeam() {
    const currentTeam = currentTeamContext();
    if (!currentTeam) throw new Error("Select or create a team first.");
    const managerPulserAddress = currentTeamManagerPulserAddress();
    if (!managerPulserAddress) throw new Error("No manager pulser is selected for local worker creation.");
    const workerName = String(byId("team-local-worker-name")?.value || "").trim();
    const workerPort = parseInteger(byId("team-local-worker-port")?.value, 0);
    const payload = compactObject({
      party: state.party,
      manager_pulser_address: managerPulserAddress,
      team_name: currentTeam.title,
      manager_address: currentTeam.managerAddress,
      worker_name: workerName,
      worker_port: workerPort || undefined,
      capabilities: currentTeam.capabilities,
      job_capabilities: currentTeam.jobCapabilities,
    });
    const response = await fetchJson("/api/team-actions/create-local-worker", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setTeamFeedback(
      `Local Worker Ready: ${workerName || "Worker"}`,
      [
        response.worker?.worker_config?.config_path || response.worker?.config_path || managerPulserAddress,
      ],
      "ready"
    );
    renderSnapshot();
  }

  function applyPanelCollapsed(button, collapsed) {
    const bodyId = button.getAttribute("aria-controls") || "";
    const body = byId(bodyId);
    if (!body) return;
    body.hidden = collapsed;
    button.textContent = collapsed ? "Expand" : "Collapse";
    button.setAttribute("aria-expanded", String(!collapsed));
  }

  function bindPanelToggles() {
    Array.from(document.querySelectorAll("[data-panel-toggle]")).forEach((button) => {
      const bodyId = button.getAttribute("aria-controls") || "";
      const storageKey = `boss-ui-panel-${bodyId}`;
      applyPanelCollapsed(button, readStoredFlag(storageKey, false));
      button.addEventListener("click", () => {
        const collapsed = button.getAttribute("aria-expanded") === "true";
        writeStoredFlag(storageKey, collapsed);
        applyPanelCollapsed(button, collapsed);
      });
    });
  }

  function bindEvents() {
    byId("refresh-teams-btn")?.addEventListener("click", () => {
      state.party = String(byId("party-input")?.value || state.party).trim() || "Phemacast";
      renderSharedContext();
      refreshTeams();
      refreshProvisionCatalog();
    });

    byId("party-input")?.addEventListener("change", () => {
      state.party = String(byId("party-input")?.value || state.party).trim() || "Phemacast";
      renderSharedContext();
      refreshProvisionCatalog();
    });

    byId("shared-manager-address")?.addEventListener("input", () => {
      renderSharedContext();
      renderSnapshot();
    });

    byId("team-search-input")?.addEventListener("input", renderTeams);
    byId("clear-team-search-btn")?.addEventListener("click", () => {
      const field = byId("team-search-input");
      if (field) field.value = "";
      renderTeams();
    });

    Array.from(document.querySelectorAll("[data-workspace-tab]")).forEach((button) => {
      button.addEventListener("click", () => switchWorkspaceTab(button.getAttribute("data-workspace-tab") || "teams"));
    });

    byId("hero-toggle-btn")?.addEventListener("click", () => toggleHeroCollapsed());

    byId("job-submit-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      setChip("job-submit-status", "Sending", "loading");
      try {
        const managerAddress = currentManagerAddress();
        const requiredCapability = String(byId("required-capability-input")?.value || "").trim();
        if (!managerAddress) throw new Error("Manager address is required.");
        if (!requiredCapability) throw new Error("Required capability is required.");
        const targets = parseCsvList(byId("job-targets-input")?.value);
        const payload = {
          manager_address: managerAddress,
          required_capability: requiredCapability,
          priority: Number.parseInt(String(byId("job-priority-input")?.value || "100"), 10),
          targets,
          payload: compactObject({
            phema_path: String(byId("job-phema-path-input")?.value || "").trim(),
            targets,
            note: String(byId("job-note-input")?.value || "").trim()
          })
        };
        const response = await fetchJson("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        renderJobSubmitResult(response, payload);
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

    byId("team-add-manager-btn")?.addEventListener("click", async () => {
      setChip("snapshot-status", "Working", "loading");
      try {
        await addManagerToCurrentTeam();
        setChip("snapshot-status", "Manager Added", "success");
      } catch (error) {
        setTeamFeedback("Manager Add Failed", [error.message || "Unable to add manager."], "error");
        setChip("snapshot-status", error.message || "Error", "error");
      }
    });

    byId("team-hire-worker-btn")?.addEventListener("click", async () => {
      setChip("snapshot-status", "Working", "loading");
      try {
        await hireWorkerForCurrentTeam();
        setChip("snapshot-status", "Worker Hired", "success");
      } catch (error) {
        setTeamFeedback("Worker Hire Failed", [error.message || "Unable to hire worker."], "error");
        setChip("snapshot-status", error.message || "Error", "error");
      }
    });

    byId("team-create-local-worker-btn")?.addEventListener("click", async () => {
      setChip("snapshot-status", "Working", "loading");
      try {
        await createLocalWorkerForCurrentTeam();
        setChip("snapshot-status", "Worker Ready", "success");
      } catch (error) {
        setTeamFeedback("Local Worker Failed", [error.message || "Unable to create local worker."], "error");
        setChip("snapshot-status", error.message || "Error", "error");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    state.heroCollapsed = readStoredFlag("boss-ui-hero-collapsed", true);
    state.workspaceTab = readStoredValue("boss-ui-workspace-tab", "teams");
    state.provisioningTab = "team";
    seedExamples();
    bindEvents();
    bindPanelToggles();
    applyHeroCollapsed();
    switchWorkspaceTab(state.workspaceTab);
    setSelectedManagerInputs(state.selectedManagerAddress);
    renderSharedContext();
    renderSelectedJobcapSummary();
    renderHeroMetrics();
    renderTeams();
    renderCapabilityMap();
    renderSnapshot();
    refreshProvisionCatalog();
    refreshTeams();
  });
})();
