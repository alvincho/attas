document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    const initialPlazas = JSON.parse(body.dataset.plazaUrls || '[]');
    const historyStorageKey = `attas-user-history:${body.dataset.agentName || 'default'}`;
    const historyLimit = 24;
    const HEARTBEAT_ACTIVE_WINDOW_SEC = 60;

    const refs = {
        navItems: Array.from(document.querySelectorAll('.nav-item')),
        views: Array.from(document.querySelectorAll('.view')),
        catalogStatus: document.getElementById('catalog-status'),
        refreshCatalog: document.getElementById('refresh-catalog'),
        refreshSaved: document.getElementById('refresh-saved'),
        catalogQuery: document.getElementById('catalog-query'),
        partyFilter: document.getElementById('party-filter'),
        plazaFilter: document.getElementById('plaza-filter'),
        phemaSelect: document.getElementById('phema-select'),
        phemaSelectionMeta: document.getElementById('phema-selection-meta'),
        refreshSnapshots: document.getElementById('refresh-snapshots'),
        snapshotCount: document.getElementById('snapshot-count'),
        snapshotSearch: document.getElementById('snapshot-search'),
        snapshotFilter: document.getElementById('snapshot-filter'),
        snapshotGroupSelect: document.getElementById('snapshot-group-select'),
        snapshotVersionSelect: document.getElementById('snapshot-version-select'),
        snapshotSelectionMeta: document.getElementById('snapshot-selection-meta'),
        snapshotActions: document.getElementById('snapshot-actions'),
        castrSelect: document.getElementById('castr-select'),
        castrSelectionMeta: document.getElementById('castr-selection-meta'),
        selectedPhemaSummary: document.getElementById('selected-phema-summary'),
        paramForm: document.getElementById('param-form'),
        renderFormat: document.getElementById('render-format'),
        cacheTime: document.getElementById('cache-time'),
        generateResult: document.getElementById('generate-result'),
        resultView: document.getElementById('result-view'),
        resultActions: document.getElementById('result-actions'),
        applicationCount: document.getElementById('application-count'),
        castrCount: document.getElementById('castr-count'),
        historyCount: document.getElementById('history-count'),
        historyList: document.getElementById('history-list'),
        savedCount: document.getElementById('saved-count'),
        savedList: document.getElementById('saved-list'),
        savedDetail: document.getElementById('saved-detail'),
        plazaRail: document.getElementById('plaza-rail'),
        plazaCount: document.getElementById('plaza-count'),
        agentConfigCount: document.getElementById('agent-config-count'),
        agentConfigQuery: document.getElementById('agent-config-query'),
        agentConfigList: document.getElementById('agent-config-list'),
        refreshAgentConfigs: document.getElementById('refresh-agent-configs'),
        launchAgentFromUser: document.getElementById('launch-agent-from-user'),
        parameterModal: document.getElementById('parameter-modal'),
        parameterModalTitle: document.getElementById('parameter-modal-title'),
        parameterModalSummary: document.getElementById('parameter-modal-summary'),
        parameterModalCopy: document.getElementById('parameter-modal-copy'),
        parameterModalError: document.getElementById('parameter-modal-error'),
        modalParamForm: document.getElementById('modal-param-form'),
        closeParameterModal: document.getElementById('close-parameter-modal'),
        parameterModalCancel: document.getElementById('parameter-modal-cancel'),
        parameterModalSubmit: document.getElementById('parameter-modal-submit'),
        castModal: document.getElementById('cast-modal'),
        castModalTitle: document.getElementById('cast-modal-title'),
        castModalSummary: document.getElementById('cast-modal-summary'),
        castModalCopy: document.getElementById('cast-modal-copy'),
        castModalError: document.getElementById('cast-modal-error'),
        castLlmPulser: document.getElementById('cast-llm-pulser'),
        castLlmPulserMeta: document.getElementById('cast-llm-pulser-meta'),
        castTone: document.getElementById('cast-tone'),
        castStyle: document.getElementById('cast-style'),
        castAudience: document.getElementById('cast-audience'),
        castLanguage: document.getElementById('cast-language'),
        castModifier: document.getElementById('cast-modifier'),
        castInstructions: document.getElementById('cast-instructions'),
        closeCastModal: document.getElementById('close-cast-modal'),
        castModalCancel: document.getElementById('cast-modal-cancel'),
        castModalSubmit: document.getElementById('cast-modal-submit'),
    };

    const state = {
        activeView: 'home-view',
        query: '',
        party: '',
        plazaUrl: '',
        loadingCatalog: false,
        loadingSnapshots: false,
        loadingSaved: false,
        loadingAgentConfigs: false,
        generating: false,
        saving: false,
        modalOpen: false,
        castModalOpen: false,
        modalIntent: 'snapshot',
        modalSourceHistoryId: '',
        snapshotApplicationKey: '',
        snapshotSearch: '',
        snapshotFilter: 'all',
        catalogActiveCastrKeys: [],
        catalog: {
            plazas: [],
            applications: [],
            castrs: [],
            llmPulsers: [],
        },
        agentConfigQuery: '',
        agentConfigs: [],
        snapshots: [],
        historyEntries: [],
        savedResults: [],
        selectedApplicationKey: '',
        selectedCastrKey: '',
        selectedLlmPulserKey: '',
        selectedSnapshotId: '',
        selectedSnapshotGroupKey: '',
        snapshotMode: 'new',
        selectedSavedResultId: '',
        paramValuesByApplication: {},
        personalizationByApplication: {},
        lastResult: null,
    };

    let searchTimer = null;
    let agentConfigSearchTimer = null;

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function prettyJson(value) {
        try {
            return JSON.stringify(value, null, 2);
        } catch (error) {
            return String(value ?? '');
        }
    }

    function summarizeValue(value) {
        if (value === null || value === undefined || value === '') {
            return '';
        }
        if (Array.isArray(value)) {
            return value
                .map((item) => summarizeValue(item))
                .filter(Boolean)
                .join(', ');
        }
        if (typeof value === 'object') {
            return Object.entries(value)
                .map(([key, item]) => `${key}: ${summarizeValue(item)}`)
                .filter(Boolean)
                .join(', ');
        }
        return String(value);
    }

    function renderContentBlocks(value) {
        if (value === null || value === undefined || value === '') {
            return '<p class="content-paragraph muted">No content returned.</p>';
        }

        if (Array.isArray(value)) {
            const simpleItems = value.every((item) => ['string', 'number', 'boolean'].includes(typeof item));
            if (simpleItems) {
                return `
                    <ul class="content-list">
                        ${value.map((item) => `<li>${escapeHtml(String(item))}</li>`).join('')}
                    </ul>
                `;
            }
            return value.map((item) => renderContentBlocks(item)).join('');
        }

        if (typeof value === 'object') {
            return `
                <dl class="content-grid">
                    ${Object.entries(value).map(([key, item]) => `
                        <div class="content-pair">
                            <dt>${escapeHtml(key.replace(/_/g, ' '))}</dt>
                            <dd>${renderContentBlocks(item)}</dd>
                        </div>
                    `).join('')}
                </dl>
            `;
        }

        return `<p class="content-paragraph">${escapeHtml(String(value))}</p>`;
    }

    function renderSnapshotSections(snapshot) {
        const sections = Array.isArray(snapshot?.sections) ? snapshot.sections : [];
        if (!sections.length) {
            return '<div class="empty-state"><strong>No section content returned.</strong><p>The selected Phemar responded without resolved sections.</p></div>';
        }

        return sections.map((section) => `
            <article class="section-card">
                <h5>${escapeHtml(section.name || 'Untitled Section')}</h5>
                ${section.description ? `<p class="saved-desc">${escapeHtml(section.description)}</p>` : ''}
                <div class="section-content">
                    ${renderContentBlocks(section.content || [])}
                </div>
            </article>
        `).join('');
    }

    function renderTemporaryScriptCard(script, llm) {
        if (!script) return '';

        const personal = script.llm_personalization && typeof script.llm_personalization === 'object'
            ? script.llm_personalization
            : {};
        const chips = [
            personal.tone ? `<span class="meta-chip">Tone: ${escapeHtml(personal.tone)}</span>` : '',
            personal.style ? `<span class="meta-chip">Style: ${escapeHtml(personal.style)}</span>` : '',
            personal.audience ? `<span class="meta-chip">Audience: ${escapeHtml(personal.audience)}</span>` : '',
            llm?.name ? `<span class="meta-chip">LLM: ${escapeHtml(llm.name)}</span>` : '',
        ].filter(Boolean).join('');

        return `
            <section class="result-card">
                <h4>LLM Temporary Script</h4>
                <p class="saved-desc">${escapeHtml(script.llm_script_summary || 'The LLM personalized a temporary script before the Castr rendered the final result.')}</p>
                <div class="result-meta">${chips}</div>
                <div class="section-list">
                    ${renderSnapshotSections(script)}
                </div>
            </section>
        `;
    }

    function applicationKey(item) {
        return `${item.plaza_url || ''}::${item.phema_id || item.id || ''}`;
    }

    function castrKey(item) {
        return `${item.plaza_url || ''}::${item.agent_id || ''}`;
    }

    function llmPulserKey(item) {
        return `${item.plaza_url || ''}::${item.agent_id || ''}`;
    }

    function agentConfigKey(item) {
        return `${item?.plaza_url || ''}::${item?.id || ''}`;
    }

    function snapshotRowId(item) {
        return `${item?.snapshot_id || item?.id || ''}`;
    }

    function inferAgentConfigPoolDraft(config = {}) {
        const pools = Array.isArray(config?.pools) ? config.pools.filter((entry) => entry && typeof entry === 'object') : [];
        const pool = pools[0] || {};
        const locationKeys = ['root_path', 'db_path', 'path', 'file_path', 'sqlite_path', 'url', 'project_url', 'supabase_url', 'location', 'directory', 'bucket'];
        const poolLocation = locationKeys
            .map((key) => String(pool?.[key] || '').trim())
            .find(Boolean)
            || '';
        return {
            poolType: String(pool?.type || '').trim(),
            poolLocation,
        };
    }

    function snapshotGroupKey(item) {
        return `${String(item?.phema_id || '')}::${String(item?.params_hash || '')}`;
    }

    function isHeartbeatActive(lastActive) {
        const timestamp = Number(lastActive || 0);
        if (!timestamp) return false;
        const diff = Math.max(0, Date.now() / 1000 - timestamp);
        return diff <= HEARTBEAT_ACTIVE_WINDOW_SEC;
    }

    function compactId(value, prefix = 8, suffix = 6) {
        const text = String(value || '').trim();
        if (!text) return '';
        if (text.length <= prefix + suffix + 1) return text;
        return `${text.slice(0, prefix)}…${text.slice(-suffix)}`;
    }

    function formatHeartbeatAge(lastActive) {
        const timestamp = Number(lastActive || 0);
        if (!timestamp) return 'never';
        const diff = Math.max(0, Math.floor(Date.now() / 1000 - timestamp));
        if (diff < 60) return `${diff}s`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
        return `${Math.floor(diff / 86400)}d`;
    }

    function plazaConnectionState(plaza) {
        const explicit = String(plaza?.connection_status || '').trim().toLowerCase();
        if (explicit === 'connected' || explicit === 'disconnected') {
            return explicit;
        }
        if (!plaza?.authenticated) {
            return 'disconnected';
        }
        return isHeartbeatActive(plaza?.connected_last_active) ? 'connected' : 'disconnected';
    }

    function plazaConnectionLabel(plaza) {
        return plazaConnectionState(plaza) === 'connected' ? 'Connected' : 'Disconnected';
    }

    function plazaConnectionTone(plaza) {
        return plazaConnectionState(plaza) === 'connected' ? 'online' : 'offline';
    }

    function plazaConnectionAgent(plaza) {
        const name = String(plaza?.connected_agent_name || '').trim();
        const agentId = String(plaza?.connected_agent_id || '').trim();
        if (name && agentId && name !== agentId) {
            return `${name} (${compactId(agentId)})`;
        }
        return name || compactId(agentId) || String(body.dataset.agentName || 'This agent');
    }

    function plazaConnectionCopy(plaza) {
        const identity = plazaConnectionAgent(plaza);
        if (plazaConnectionState(plaza) === 'connected') {
            return `Connected as ${identity} · heartbeat ${formatHeartbeatAge(plaza?.connected_last_active)} ago.`;
        }
        if (!plaza?.authenticated) {
            return `Disconnected for ${identity} · sign-in or registration is required.`;
        }
        if (Number(plaza?.connected_last_active || 0) > 0) {
            return `Disconnected for ${identity} · heartbeat lost ${formatHeartbeatAge(plaza?.connected_last_active)} ago.`;
        }
        return `Disconnected for ${identity} · no heartbeat reported yet.`;
    }

    function visibleCastrs() {
        const pinned = new Set(state.catalogActiveCastrKeys || []);
        const activeOnly = (state.catalog.castrs || []).filter((item) => isHeartbeatActive(item.last_active) || pinned.has(castrKey(item)));
        if (!activeOnly.length) {
            return [];
        }

        const sorted = [...activeOnly].sort((left, right) => {
            const activeGap = Number(right?.last_active || 0) - Number(left?.last_active || 0);
            if (activeGap !== 0) return activeGap;
            return String(left?.name || '').localeCompare(String(right?.name || ''));
        });

        const deduped = new Map();
        sorted.forEach((item) => {
            const pieces = [
                String(item?.name || '').trim().toLowerCase(),
                String(item?.media_type || '').trim().toLowerCase(),
            ];
            const dedupeKey = pieces.some(Boolean) ? pieces.join('::') : castrKey(item);
            if (!deduped.has(dedupeKey)) {
                deduped.set(dedupeKey, item);
            }
        });
        return Array.from(deduped.values());
    }

    function visibleLlmPulsers() {
        const activeOnly = (state.catalog.llmPulsers || []).filter((item) => isHeartbeatActive(item.last_active));
        if (activeOnly.length) {
            return activeOnly.sort((left, right) => {
                const activeGap = Number(right?.last_active || 0) - Number(left?.last_active || 0);
                if (activeGap !== 0) return activeGap;
                return String(left?.name || '').localeCompare(String(right?.name || ''));
            });
        }
        return [];
    }

    function castrOptionLabel(item) {
        const title = String(item?.name || 'Unnamed Castr').trim();
        const media = String(item?.media_type || '').trim();
        return truncateLabel(media ? `${title} · ${media}` : title, 84);
    }

    function pinVisibleCastrsFromCatalog() {
        state.catalogActiveCastrKeys = (state.catalog.castrs || [])
            .filter((item) => isHeartbeatActive(item.last_active))
            .map((item) => castrKey(item));
    }

    function buildSnapshotGroups(snapshots) {
        const byKey = new Map();
        (Array.isArray(snapshots) ? snapshots : []).forEach((snapshot) => {
            const key = snapshotGroupKey(snapshot);
            if (!byKey.has(key)) {
                byKey.set(key, { key, latest: snapshot, history: [snapshot] });
                return;
            }
            const existing = byKey.get(key);
            existing.history.push(snapshot);
            if (String(snapshot?.created_at || '') > String(existing.latest?.created_at || '')) {
                existing.latest = snapshot;
            }
        });
        return Array.from(byKey.values()).map((group) => ({
            ...group,
            history: group.history.sort((left, right) => String(right?.created_at || '').localeCompare(String(left?.created_at || ''))),
        }));
    }

    function currentApplication() {
        return (state.catalog.applications || []).find((item) => applicationKey(item) === state.selectedApplicationKey) || null;
    }

    function currentCastr() {
        return visibleCastrs().find((item) => castrKey(item) === state.selectedCastrKey) || null;
    }

    function currentLlmPulser() {
        return visibleLlmPulsers().find((item) => llmPulserKey(item) === state.selectedLlmPulserKey) || null;
    }

    function currentSavedResult() {
        return (state.savedResults || []).find((item) => item.id === state.selectedSavedResultId) || null;
    }

    function selectedSnapshotRow() {
        return (state.snapshots || []).find((item) => snapshotRowId(item) === state.selectedSnapshotId) || null;
    }

    function selectedSnapshotGroup() {
        return buildSnapshotGroups(state.snapshots).find((group) => group.key === state.selectedSnapshotGroupKey) || null;
    }

    function getHistoryEntryById(historyId) {
        return (state.historyEntries || []).find((item) => item.id === historyId) || null;
    }

    function readHistoryEntries() {
        try {
            const raw = window.localStorage.getItem(historyStorageKey);
            const parsed = JSON.parse(raw || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function persistHistoryEntries() {
        try {
            window.localStorage.setItem(historyStorageKey, JSON.stringify(state.historyEntries.slice(0, historyLimit)));
        } catch (error) {
            // Ignore storage failures so the UI remains usable.
        }
    }

    function loadHistoryEntries() {
        state.historyEntries = readHistoryEntries();
    }

    function formatDateTime(value) {
        if (!value) return '';
        const parsed = new Date(value);
        return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
    }

    function summarizeParamsInline(params) {
        const entries = Object.entries(params || {}).filter(([, value]) => summarizeValue(value));
        if (!entries.length) {
            return 'Default inputs';
        }
        return entries
            .slice(0, 3)
            .map(([key, value]) => `${key}: ${summarizeValue(value)}`)
            .join(' · ');
    }

    function truncateLabel(value, limit = 72) {
        const text = String(value || '').trim();
        if (text.length <= limit) return text;
        return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
    }

    function applicationOptionLabel(item) {
        const title = String(item?.name || 'Unnamed Phema').trim();
        const host = String(item?.host_phemar_name || '').trim();
        return truncateLabel(host ? `${title} · ${host}` : title, 84);
    }

    function snapshotGroupMatchesFilter(group) {
        const latest = group?.latest || {};
        const params = latest.params && typeof latest.params === 'object' ? latest.params : {};
        const hasParams = Object.keys(params).length > 0;
        if (state.snapshotFilter === 'default') {
            return !hasParams;
        }
        if (state.snapshotFilter === 'custom') {
            return hasParams;
        }
        return true;
    }

    function snapshotGroupMatchesSearch(group) {
        const query = String(state.snapshotSearch || '').trim().toLowerCase();
        if (!query) return true;
        const latest = group?.latest || {};
        const params = latest.params && typeof latest.params === 'object' ? latest.params : {};
        const haystack = [
            summarizeParamsInline(params),
            JSON.stringify(params),
            String(group?.history?.length || ''),
            String(latest.created_at || ''),
        ].join(' ').toLowerCase();
        return haystack.includes(query);
    }

    function filteredSnapshotGroups() {
        return buildSnapshotGroups(state.snapshots).filter((group) => snapshotGroupMatchesFilter(group) && snapshotGroupMatchesSearch(group));
    }

    function filteredAgentConfigs() {
        const query = String(state.agentConfigQuery || '').trim().toLowerCase();
        return (state.agentConfigs || []).filter((item) => {
            const haystack = [
                item.name,
                item.description,
                item.owner,
                item.role,
                item.agent_type,
                item.plaza_url,
                JSON.stringify(item.tags || []),
            ].join(' ').toLowerCase();
            return !query || haystack.includes(query);
        });
    }

    function serializeForInlineScript(value) {
        return JSON.stringify(value ?? null)
            .replace(/</g, '\\u003c')
            .replace(/>/g, '\\u003e')
            .replace(/&/g, '\\u0026');
    }

    function setStatus(text, tone = 'neutral') {
        refs.catalogStatus.textContent = text;
        refs.catalogStatus.className = 'status-pill';
        if (tone === 'success') refs.catalogStatus.classList.add('online');
        if (tone === 'error') refs.catalogStatus.classList.add('offline');
    }

    function switchView(viewId) {
        state.activeView = viewId;
        refs.navItems.forEach((item) => item.classList.toggle('active', item.dataset.viewTarget === viewId));
        refs.views.forEach((view) => view.classList.toggle('active', view.id === viewId));
    }

    function fieldDefinitionEntries(application) {
        const schema = application?.input_schema && typeof application.input_schema === 'object'
            ? application.input_schema
            : {};
        const properties = schema.properties && typeof schema.properties === 'object'
            ? schema.properties
            : {};
        const required = Array.isArray(schema.required) ? schema.required : [];

        return Object.entries(properties).map(([name, definition]) => ({
            name,
            definition: definition || {},
            required: required.includes(name),
        }));
    }

    function seedParamsFromSchema(application) {
        const key = applicationKey(application);
        if (state.paramValuesByApplication[key]) {
            return;
        }

        const defaults = {};
        fieldDefinitionEntries(application).forEach(({ name, definition }) => {
            if (definition.default !== undefined) {
                defaults[name] = definition.default;
            } else if (Array.isArray(definition.enum) && definition.enum.length) {
                defaults[name] = definition.enum[0];
            } else if (definition.type === 'boolean') {
                defaults[name] = false;
            } else {
                defaults[name] = '';
            }
        });
        state.paramValuesByApplication[key] = defaults;
    }

    function mergeDraftParams(application, nextValues) {
        if (!application) return;
        const key = applicationKey(application);
        seedParamsFromSchema(application);
        state.paramValuesByApplication[key] = {
            ...(state.paramValuesByApplication[key] || {}),
            ...(nextValues || {}),
        };
    }

    function seedPersonalizationDraft(application) {
        const key = applicationKey(application);
        if (state.personalizationByApplication[key]) {
            return;
        }

        state.personalizationByApplication[key] = {
            tone: 'Balanced',
            style: 'Executive brief',
            audience: '',
            language: 'en',
            modifier: '',
            instructions: '',
        };
    }

    function mergePersonalizationDraft(application, nextValues) {
        if (!application) return;
        const key = applicationKey(application);
        seedPersonalizationDraft(application);
        state.personalizationByApplication[key] = {
            ...(state.personalizationByApplication[key] || {}),
            ...(nextValues || {}),
        };
    }

    function collectPersonalization(application = currentApplication()) {
        if (!application) return {};
        seedPersonalizationDraft(application);
        const values = state.personalizationByApplication[applicationKey(application)] || {};
        return {
            tone: String(values.tone || 'Balanced').trim() || 'Balanced',
            style: String(values.style || 'Executive brief').trim() || 'Executive brief',
            audience: String(values.audience || '').trim(),
            language: String(values.language || 'en').trim() || 'en',
            modifier: String(values.modifier || '').trim(),
            instructions: String(values.instructions || '').trim(),
        };
    }

    function anyModalOpen() {
        return Boolean(state.modalOpen || state.castModalOpen);
    }

    function updateModalBodyState() {
        body.classList.toggle('modal-open', anyModalOpen());
    }

    function selectSnapshotMode({ mode = 'new', snapshot = null, group = null } = {}) {
        const application = currentApplication();
        state.snapshotMode = mode;
        state.selectedSnapshotId = mode === 'snapshot' && snapshot ? snapshotRowId(snapshot) : '';
        state.selectedSnapshotGroupKey = group?.key || (snapshot ? snapshotGroupKey(snapshot) : '');

        if (application) {
            if (snapshot && typeof snapshot.params === 'object') {
                mergeDraftParams(application, snapshot.params);
            } else if (group?.latest?.params && typeof group.latest.params === 'object') {
                mergeDraftParams(application, group.latest.params);
            }
        }
    }

    function syncSnapshotSelection() {
        const application = currentApplication();
        if (!application) {
            state.snapshotApplicationKey = '';
            state.snapshots = [];
            state.selectedSnapshotId = '';
            state.selectedSnapshotGroupKey = '';
            state.snapshotMode = 'new';
            return;
        }

        const groups = buildSnapshotGroups(state.snapshots);
        if (!groups.length) {
            state.selectedSnapshotId = '';
            state.selectedSnapshotGroupKey = '';
            state.snapshotMode = 'new';
            return;
        }

        const selectedSnapshot = selectedSnapshotRow();
        if (state.snapshotMode === 'snapshot' && selectedSnapshot) {
            selectSnapshotMode({
                mode: 'snapshot',
                snapshot: selectedSnapshot,
                group: groups.find((group) => group.key === snapshotGroupKey(selectedSnapshot)) || null,
            });
            return;
        }

        const selectedGroup = selectedSnapshotGroup();
        if (state.snapshotMode === 'new' && selectedGroup) {
            selectSnapshotMode({ mode: 'new', group: selectedGroup });
            return;
        }

        selectSnapshotMode({ mode: 'snapshot', snapshot: groups[0].latest, group: groups[0] });
    }

    function renderPrimaryAction() {
        const application = currentApplication();
        const castr = currentCastr();
        if (state.loadingSnapshots) {
            refs.generateResult.textContent = 'Loading Snapshots...';
            refs.generateResult.disabled = true;
            return;
        }
        if (!application) {
            refs.generateResult.textContent = 'Choose A Phema';
            refs.generateResult.disabled = true;
            return;
        }
        if (state.snapshotMode === 'snapshot' && state.selectedSnapshotId) {
            refs.generateResult.textContent = castr ? 'Create My Result' : 'Choose A Castr';
            refs.generateResult.disabled = !castr;
            return;
        }
        refs.generateResult.textContent = state.selectedSnapshotGroupKey
            ? 'Create Snapshot From Saved Inputs'
            : 'Create Snapshot';
        refs.generateResult.disabled = false;
    }

    function syncSelections() {
        const applications = state.catalog.applications || [];
        const castrs = visibleCastrs();
        const llmPulsers = visibleLlmPulsers();

        if (!applications.some((item) => applicationKey(item) === state.selectedApplicationKey)) {
            state.selectedApplicationKey = applications[0] ? applicationKey(applications[0]) : '';
        }

        const selectedApplication = currentApplication();
        if (selectedApplication) {
            seedParamsFromSchema(selectedApplication);
            seedPersonalizationDraft(selectedApplication);
        }

        if (!castrs.some((item) => castrKey(item) === state.selectedCastrKey)) {
            state.selectedCastrKey = castrs[0] ? castrKey(castrs[0]) : '';
        }

        if (!llmPulsers.some((item) => llmPulserKey(item) === state.selectedLlmPulserKey)) {
            state.selectedLlmPulserKey = llmPulsers[0] ? llmPulserKey(llmPulsers[0]) : '';
        }

        const selectedCastr = currentCastr();
        if (selectedCastr && !refs.renderFormat.value.trim()) {
            refs.renderFormat.value = selectedCastr.media_type || 'PDF';
        }

        if (!state.savedResults.some((item) => item.id === state.selectedSavedResultId)) {
            state.selectedSavedResultId = state.savedResults[0] ? state.savedResults[0].id : '';
        }

        syncSnapshotSelection();
    }

    function renderPhemaSummary() {
        const application = currentApplication();
        const castr = currentCastr();
        const snapshot = selectedSnapshotRow();
        const snapshotGroup = selectedSnapshotGroup();
        if (!application) {
            refs.selectedPhemaSummary.innerHTML = `
                <div class="empty-state">
                    <strong>No Phema selected.</strong>
                    <p>Choose a Phema from the library to get started.</p>
                </div>
            `;
            return;
        }

        refs.selectedPhemaSummary.innerHTML = `
            <div>
                <p class="panel-kicker">Selected Phema</p>
                <h4 class="hero-title">${escapeHtml(application.name || 'Unnamed Phema')}</h4>
                <p class="hero-copy">${escapeHtml(application.description || 'No description provided.')}</p>
                <div class="meta-row">
                    <span class="meta-chip">Hosted by ${escapeHtml(application.host_phemar_name || 'Unknown Phemar')}</span>
                    ${application.party ? `<span class="meta-chip">${escapeHtml(application.party)}</span>` : ''}
                    ${snapshot ? `<span class="meta-chip">Snapshot ${escapeHtml(snapshotRowId(snapshot).slice(0, 8))}</span>` : ''}
                    ${!snapshot && snapshotGroup ? '<span class="meta-chip">New snapshot from saved inputs</span>' : ''}
                    ${!snapshot && !snapshotGroup ? '<span class="meta-chip">New snapshot from fresh inputs</span>' : ''}
                    ${snapshot ? '<span class="meta-chip">Ready to cast</span>' : '<span class="meta-chip">Create a snapshot first</span>'}
                    ${castr ? `<span class="meta-chip">Output: ${escapeHtml(castr.media_type || castr.name || 'Castr')}</span>` : ''}
                </div>
            </div>
        `;
    }

    function renderPhemaList() {
        const items = state.catalog.applications || [];
        refs.applicationCount.textContent = String(items.length);

        if (!items.length) {
            refs.phemaSelect.innerHTML = '<option value="">No Phemas found</option>';
            refs.phemaSelect.disabled = true;
            refs.phemaSelectionMeta.textContent = 'Try another search or adjust the plaza and party filters.';
            return;
        }
        refs.phemaSelect.disabled = false;
        refs.phemaSelect.innerHTML = items.map((item) => `
            <option value="${escapeHtml(applicationKey(item))}" ${applicationKey(item) === state.selectedApplicationKey ? 'selected' : ''}>
                ${escapeHtml(applicationOptionLabel(item))}
            </option>
        `).join('');
        const application = currentApplication();
        refs.phemaSelectionMeta.textContent = application
            ? `${application.host_phemar_name || 'Unknown Phemar'} · ${application.plaza_url || 'No plaza'}`
            : 'Choose one Phema to continue.';
    }

    function renderCastrList() {
        const items = visibleCastrs();
        refs.castrCount.textContent = String(items.length);

        if (!items.length) {
            refs.castrSelect.innerHTML = '<option value="">No active Castrs available</option>';
            refs.castrSelect.disabled = true;
            refs.castrSelectionMeta.textContent = 'Refresh the catalog to look for active renderers again.';
            return;
        }

        refs.castrSelect.disabled = false;
        refs.castrSelect.innerHTML = items.map((item) => `
            <option value="${escapeHtml(castrKey(item))}" ${castrKey(item) === state.selectedCastrKey ? 'selected' : ''}>
                ${escapeHtml(castrOptionLabel(item))}
            </option>
        `).join('');
        const castr = currentCastr();
        refs.castrSelectionMeta.textContent = castr
            ? `${castr.description || 'Ready to package your selected snapshot.'} ${castr.plaza_url ? `· ${castr.plaza_url}` : ''}`
            : 'Choose one active Castr to package the selected snapshot.';
    }

    function renderSnapshotGroupList() {
        const application = currentApplication();
        refs.snapshotSearch.value = state.snapshotSearch;
        refs.snapshotFilter.value = state.snapshotFilter;
        if (!application) {
            refs.snapshotCount.textContent = '0';
            refs.snapshotGroupSelect.innerHTML = '<option value="">Choose a Phema first</option>';
            refs.snapshotVersionSelect.innerHTML = '<option value="">No snapshots yet</option>';
            refs.snapshotGroupSelect.disabled = true;
            refs.snapshotVersionSelect.disabled = true;
            refs.snapshotSelectionMeta.textContent = 'Once a Phema is selected, its saved input sets will appear here.';
            refs.snapshotActions.innerHTML = '';
            return;
        }

        if (state.loadingSnapshots) {
            refs.snapshotCount.textContent = '...';
            refs.snapshotGroupSelect.innerHTML = '<option value="">Loading input sets…</option>';
            refs.snapshotVersionSelect.innerHTML = '<option value="">Loading snapshots…</option>';
            refs.snapshotGroupSelect.disabled = true;
            refs.snapshotVersionSelect.disabled = true;
            refs.snapshotSelectionMeta.textContent = 'Gathering previous snapshots for this Phema.';
            refs.snapshotActions.innerHTML = '';
            return;
        }

        const totalGroups = buildSnapshotGroups(state.snapshots);
        const groups = filteredSnapshotGroups();
        refs.snapshotCount.textContent = groups.length === totalGroups.length
            ? String(groups.length)
            : `${groups.length}/${totalGroups.length}`;

        if (!groups.length) {
            refs.snapshotGroupSelect.innerHTML = '<option value="">No matching input sets</option>';
            refs.snapshotVersionSelect.innerHTML = '<option value="">No snapshots to show</option>';
            refs.snapshotGroupSelect.disabled = true;
            refs.snapshotVersionSelect.disabled = true;
            refs.snapshotSelectionMeta.textContent = totalGroups.length
                ? 'No input sets match the current search or filter.'
                : 'No saved snapshots for this Phema yet. Start fresh to create the first one.';
            refs.snapshotActions.innerHTML = `
                <button class="secondary-btn small-btn" data-snapshot-action="new-empty" type="button">Create Fresh Snapshot</button>
            `;
            return;
        }

        let displayGroup = groups.find((group) => group.key === state.selectedSnapshotGroupKey) || null;
        if (!displayGroup) {
            displayGroup = groups[0];
            if (state.snapshotMode === 'new') {
                selectSnapshotMode({ mode: 'new', group: displayGroup });
            } else {
                const snapshot = displayGroup.latest || null;
                selectSnapshotMode({ mode: 'snapshot', snapshot, group: displayGroup });
            }
        }

        const displaySnapshot = displayGroup.history.find((item) => snapshotRowId(item) === state.selectedSnapshotId) || displayGroup.latest || null;
        if (state.snapshotMode === 'snapshot' && displaySnapshot && snapshotRowId(displaySnapshot) !== state.selectedSnapshotId) {
            selectSnapshotMode({ mode: 'snapshot', snapshot: displaySnapshot, group: displayGroup });
        }

        refs.snapshotGroupSelect.disabled = false;
        refs.snapshotVersionSelect.disabled = false;
        refs.snapshotGroupSelect.innerHTML = groups.map((group) => {
            const latest = group.latest || {};
            const params = latest.params && typeof latest.params === 'object' ? latest.params : {};
            const label = `${summarizeParamsInline(params)} · ${group.history.length} version${group.history.length === 1 ? '' : 's'}`;
            return `
                <option value="${escapeHtml(group.key)}" ${group.key === displayGroup.key ? 'selected' : ''}>
                    ${escapeHtml(truncateLabel(label, 96))}
                </option>
            `;
        }).join('');
        refs.snapshotVersionSelect.innerHTML = displayGroup.history.map((snapshot) => `
            <option value="${escapeHtml(snapshotRowId(snapshot))}" ${displaySnapshot && snapshotRowId(snapshot) === snapshotRowId(displaySnapshot) ? 'selected' : ''}>
                ${escapeHtml(`${snapshotRowId(snapshot).slice(0, 8)} · ${formatDateTime(snapshot.created_at) || 'Unknown time'}`)}
            </option>
        `).join('');

        const selectedParams = displayGroup.latest?.params && typeof displayGroup.latest.params === 'object' ? displayGroup.latest.params : {};
        const summary = summarizeParamsInline(selectedParams);
        const selectedNote = state.snapshotMode === 'new'
            ? 'Ready to create a new snapshot from this input set.'
            : displaySnapshot
                ? `Selected snapshot ${snapshotRowId(displaySnapshot).slice(0, 8)}.`
                : 'No snapshot selected.';
        refs.snapshotSelectionMeta.textContent = `${summary} • ${displayGroup.history.length} version${displayGroup.history.length === 1 ? '' : 's'} • latest ${formatDateTime(displayGroup.latest?.created_at) || 'Unknown time'} • ${selectedNote}`;
        refs.snapshotActions.innerHTML = `
            <button class="ghost-btn small-btn" data-snapshot-action="use-selected" data-group-key="${escapeHtml(displayGroup.key)}" type="button">Use Selected Snapshot</button>
            <button class="secondary-btn small-btn" data-snapshot-action="new-from-group" data-group-key="${escapeHtml(displayGroup.key)}" type="button">Create From Selected Inputs</button>
            <button class="ghost-btn small-btn" data-snapshot-action="new-empty" type="button">Create Fresh Snapshot</button>
        `;
    }

    function renderParameterPreview() {
        const application = currentApplication();
        const snapshot = selectedSnapshotRow();
        const group = selectedSnapshotGroup();
        if (!application) {
            refs.paramForm.innerHTML = `
                <div class="empty-state">
                    <strong>Waiting for a Phema.</strong>
                    <p>The required details will appear here after you select one.</p>
                </div>
            `;
            return;
        }

        seedParamsFromSchema(application);
        const values = state.paramValuesByApplication[applicationKey(application)] || {};
        const entries = fieldDefinitionEntries(application);

        if (!entries.length) {
            refs.paramForm.innerHTML = `
                <div class="empty-state">
                    <strong>No extra details needed.</strong>
                    <p>${snapshot ? 'This snapshot is ready. Choose a Castr and use Create My Result to personalize the final output.' : 'This Phema can create a snapshot immediately when you click the main action.'}</p>
                </div>
            `;
            return;
        }

        refs.paramForm.innerHTML = `
            <div class="preview-grid">
                <div class="preview-card">
                    <span class="preview-label">Current Mode</span>
                    <span class="preview-value">
                        ${
                            snapshot
                                ? `Ready to cast snapshot ${escapeHtml(snapshotRowId(snapshot).slice(0, 8) || 'snapshot')}`
                                : group
                                    ? 'Generating a new snapshot from saved inputs'
                                    : 'Generating a new snapshot from fresh inputs'
                        }
                    </span>
                </div>
                ${entries.map(({ name, definition, required }) => {
                    const label = definition.title || name.replace(/_/g, ' ');
                    const summary = summarizeValue(values[name]);
                    return `
                        <div class="preview-card">
                            <span class="preview-label">${escapeHtml(label)}${required ? ' *' : ''}</span>
                            <span class="preview-value ${summary ? '' : 'muted'}">
                                ${summary ? escapeHtml(summary) : 'You can fill this in from the popup form.'}
                            </span>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    function renderPlazas() {
        const plazas = state.catalog.plazas || [];
        refs.plazaCount.textContent = String(plazas.length || initialPlazas.length || 0);

        refs.plazaRail.innerHTML = plazas.length
            ? plazas.map((plaza) => `
                <button class="plaza-card ${state.plazaUrl === plaza.url ? 'active' : ''}" data-card-type="plaza" data-plaza-url="${escapeHtml(plaza.url)}" type="button">
                    <div class="plaza-top">
                        <div class="plaza-title">${escapeHtml(plaza.url)}</div>
                        <span class="mini-tag ${plazaConnectionTone(plaza)}">${escapeHtml(plazaConnectionLabel(plaza))}</span>
                    </div>
                    <p class="plaza-copy">${plaza.card?.description ? escapeHtml(plaza.card.description) : 'Connected plaza for discovery and generation.'}</p>
                    <div class="plaza-meta">
                        <span class="meta-chip">${plaza.online ? 'Plaza online' : 'Plaza offline'}</span>
                        <span class="meta-chip">${escapeHtml(plazaConnectionAgent(plaza))}</span>
                        <span class="meta-chip">${escapeHtml(String((plaza.applications || []).length))} Phemas</span>
                        <span class="meta-chip">${escapeHtml(String((plaza.castrs || []).length))} Castrs</span>
                    </div>
                    <p class="selection-desc">${escapeHtml(plazaConnectionCopy(plaza))}</p>
                    ${plaza.error ? `<p class="selection-desc">${escapeHtml(plaza.error)}</p>` : ''}
                </button>
            `).join('')
            : `
                <div class="empty-state">
                    <strong>No plazas configured.</strong>
                    <p>Add plaza URLs in the user-agent config to connect this screen to a network.</p>
                </div>
            `;
    }

    function renderAgentConfigs() {
        if (!refs.agentConfigList || !refs.agentConfigCount || !refs.agentConfigQuery) return;
        refs.agentConfigQuery.value = state.agentConfigQuery;

        if (state.loadingAgentConfigs) {
            refs.agentConfigCount.textContent = '...';
            refs.agentConfigList.innerHTML = `
                <div class="empty-state">
                    <strong>Loading AgentConfig entries.</strong>
                    <p>Checking connected plazas for saved launch templates.</p>
                </div>
            `;
            return;
        }

        const items = filteredAgentConfigs();
        refs.agentConfigCount.textContent = String(items.length);
        if (!items.length) {
            refs.agentConfigList.innerHTML = `
                <div class="empty-state">
                    <strong>No AgentConfig entries found.</strong>
                    <p>Adjust the plaza filter or search terms, then refresh to load more directory entries.</p>
                </div>
            `;
            return;
        }

        refs.agentConfigList.innerHTML = items.map((item) => {
            const tags = Array.isArray(item.tags) ? item.tags.filter(Boolean).slice(0, 4) : [];
            const poolDraft = inferAgentConfigPoolDraft(item.config || {});
            return `
                <article class="selection-card">
                    <div class="selection-top">
                        <div>
                            <div class="selection-title">${escapeHtml(item.name || 'Unnamed AgentConfig')}</div>
                            <p class="selection-desc">${escapeHtml(item.description || 'No description registered.')}</p>
                        </div>
                        <button class="ghost-btn" type="button" data-launch-agent-config="${escapeHtml(agentConfigKey(item))}">Launch</button>
                    </div>
                    <div class="meta-row">
                        ${item.owner ? `<span class="meta-chip">${escapeHtml(item.owner)}</span>` : ''}
                        ${item.role ? `<span class="meta-chip">${escapeHtml(item.role)}</span>` : ''}
                        ${item.agent_type ? `<span class="meta-chip">${escapeHtml(item.agent_type)}</span>` : ''}
                        ${item.plaza_url ? `<span class="meta-chip">${escapeHtml(item.plaza_url)}</span>` : ''}
                        ${poolDraft.poolType ? `<span class="meta-chip">${escapeHtml(poolDraft.poolType)}</span>` : ''}
                        ${poolDraft.poolLocation ? `<span class="meta-chip">${escapeHtml(truncateLabel(poolDraft.poolLocation, 48))}</span>` : ''}
                        ${tags.map((tag) => `<span class="meta-chip">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                </article>
            `;
        }).join('');
    }

    function renderResult() {
        const result = state.lastResult;
        refs.resultActions.innerHTML = '';

        if (!result) {
            refs.resultView.innerHTML = `
                <div class="empty-state">
                    <strong>No result yet.</strong>
                    <p>Select a Phema, choose or create a snapshot, then package it with a Castr to see it here.</p>
                </div>
            `;
            return;
        }

        const application = result.application || {};
        const snapshotWrapper = result.snapshot || {};
        const snapshot = snapshotWrapper.snapshot || null;
        const cast = result.cast || null;
        const temporaryScript = result.temporary_script || null;
        const displayTitle = temporaryScript?.name || snapshot?.name || application.name || 'Generated Result';
        const displayDescription = temporaryScript?.description || snapshot?.description || application.description || 'Your generated result is ready below.';

        refs.resultActions.innerHTML = `
            <button id="edit-current-result" class="secondary-btn" type="button">Modify Inputs</button>
            <button id="save-current-result" class="secondary-btn" type="button">Save Locally</button>
            ${cast?.public_url ? `<a class="text-link" href="${escapeHtml(cast.public_url)}" target="_blank" rel="noreferrer">Open Output</a>` : ''}
        `;

        refs.resultView.innerHTML = `
            <section class="result-card">
                <h4>${escapeHtml(displayTitle)}</h4>
                <p class="saved-desc">${escapeHtml(displayDescription)}</p>
                <div class="result-meta">
                    <span class="meta-chip">Snapshot ID ${escapeHtml(snapshotWrapper.snapshot_id || snapshotWrapper.history?.snapshot_id || 'n/a')}</span>
                    ${result.snapshot_source ? `<span class="meta-chip">${escapeHtml(result.snapshot_source === 'existing' ? 'Existing snapshot' : result.snapshot_source === 'cached' ? 'Cached snapshot' : 'Fresh snapshot')}</span>` : ''}
                    ${result.castr?.name ? `<span class="meta-chip">${escapeHtml(result.castr.name)}</span>` : ''}
                    ${cast?.format ? `<span class="meta-chip">${escapeHtml(cast.format)}</span>` : ''}
                </div>
            </section>
            <section class="result-card">
                <h4>Sections</h4>
                <div class="section-list">
                    ${renderSnapshotSections(snapshot)}
                </div>
            </section>
            ${renderTemporaryScriptCard(temporaryScript, result.llm)}
            ${
                cast
                    ? `
                        <section class="result-card">
                            <h4>Output Package</h4>
                            <p class="saved-desc">${escapeHtml(cast.message || 'The Castr packaged your result successfully.')}</p>
                            <pre class="code-block">${escapeHtml(prettyJson(cast))}</pre>
                        </section>
                    `
                    : ''
            }
        `;
    }

    function renderSavedList() {
        const items = state.savedResults || [];
        refs.savedCount.textContent = String(items.length);

        if (!items.length) {
            refs.savedList.innerHTML = `
                <div class="empty-state">
                    <strong>No saved results yet.</strong>
                    <p>After you generate something, use “Save Locally” to keep a copy here.</p>
                </div>
            `;
            return;
        }

        refs.savedList.innerHTML = items.map((item) => `
            <button class="saved-card ${item.id === state.selectedSavedResultId ? 'selected' : ''}" data-card-type="saved" data-saved-id="${escapeHtml(item.id)}" type="button">
                <div class="saved-top">
                    <div class="saved-title">${escapeHtml(item.title || 'Saved Result')}</div>
                    <span class="mini-tag">${escapeHtml(item.format || 'Saved')}</span>
                </div>
                <p class="saved-desc">${escapeHtml(item.application_name || item.phema_name || 'Saved attas result')}</p>
                <div class="saved-meta">
                    ${item.castr_name ? `<span class="meta-chip">${escapeHtml(item.castr_name)}</span>` : ''}
                    ${item.saved_at ? `<span class="meta-chip">${escapeHtml(formatDateTime(item.saved_at))}</span>` : ''}
                </div>
            </button>
        `).join('');
    }

    function renderSavedDetail() {
        const item = currentSavedResult();
        if (!item) {
            refs.savedDetail.innerHTML = `
                <div class="empty-state">
                    <strong>No saved result selected.</strong>
                    <p>Choose one from the list to view the details.</p>
                </div>
            `;
            return;
        }

        const payload = item.payload || {};
        const snapshotWrapper = payload.snapshot || {};
        const snapshot = snapshotWrapper.snapshot || {};
        const cast = payload.cast || {};
        const temporaryScript = payload.temporary_script || null;
        const displayTitle = item.title || temporaryScript?.name || snapshot.name || 'Saved Result';
        const displayDescription = temporaryScript?.description || snapshot.description || payload.application?.description || 'Saved locally on this user agent.';

        refs.savedDetail.innerHTML = `
            <section class="result-card">
                <h4 class="saved-detail-title">${escapeHtml(displayTitle)}</h4>
                <p class="saved-desc">${escapeHtml(displayDescription)}</p>
                <div class="result-meta">
                    ${item.application_name ? `<span class="meta-chip">${escapeHtml(item.application_name)}</span>` : ''}
                    ${item.castr_name ? `<span class="meta-chip">${escapeHtml(item.castr_name)}</span>` : ''}
                    ${item.saved_at ? `<span class="meta-chip">${escapeHtml(formatDateTime(item.saved_at))}</span>` : ''}
                </div>
                <div class="link-row">
                    ${item.local_artifact_url ? `<a class="text-link" href="${escapeHtml(item.local_artifact_url)}" target="_blank" rel="noreferrer">Open Local Copy</a>` : ''}
                    ${item.public_artifact_url ? `<a class="text-link" href="${escapeHtml(item.public_artifact_url)}" target="_blank" rel="noreferrer">Open Original Output</a>` : ''}
                </div>
            </section>
            <section class="result-card">
                <h4>Saved Content</h4>
                <div class="section-list">
                    ${renderSnapshotSections(snapshot)}
                </div>
            </section>
            ${renderTemporaryScriptCard(temporaryScript, payload.llm)}
            ${
                cast && Object.keys(cast).length
                    ? `
                        <section class="result-card">
                            <h4>Output Metadata</h4>
                            <div class="content-grid">
                                ${
                                    Object.entries(cast).map(([key, value]) => `
                                        <div class="content-pair">
                                            <dt>${escapeHtml(key.replace(/_/g, ' '))}</dt>
                                            <dd>${renderContentBlocks(summarizeValue(value))}</dd>
                                        </div>
                                    `).join('')
                                }
                            </div>
                        </section>
                    `
                    : ''
            }
            <details class="payload-details">
                <summary>Show raw saved payload</summary>
                <pre class="code-block">${escapeHtml(prettyJson(payload))}</pre>
            </details>
        `;
    }

    function renderHistoryList() {
        const items = state.historyEntries || [];
        refs.historyCount.textContent = String(items.length);

        if (!items.length) {
            refs.historyList.innerHTML = `
                <div class="empty-state">
                    <strong>No recent runs yet.</strong>
                    <p>Your recent parameter sets will appear here after you generate a result.</p>
                </div>
            `;
            return;
        }

        refs.historyList.innerHTML = items.map((item) => {
            const paramEntries = Object.entries(item.params || {}).slice(0, 4);
            return `
                <article class="history-card">
                    <div class="history-top">
                        <div>
                            <div class="history-title">${escapeHtml(item.applicationName || 'Recent run')}</div>
                            <p class="history-copy">
                                ${escapeHtml(item.castrName || 'Snapshot only')} ${item.snapshotName ? `for ${escapeHtml(item.snapshotName)}` : ''}
                            </p>
                        </div>
                        <span class="mini-tag">${escapeHtml(formatDateTime(item.createdAt) || 'Recent')}</span>
                    </div>
                    <div class="tag-row">
                        ${paramEntries.length
                            ? paramEntries.map(([key, value]) => `<span class="tag">${escapeHtml(key)}: ${escapeHtml(summarizeValue(value) || 'n/a')}</span>`).join('')
                            : '<span class="tag">No parameters</span>'
                        }
                        ${item.format ? `<span class="tag">${escapeHtml(item.format)}</span>` : ''}
                    </div>
                    <div class="history-actions">
                        <button class="ghost-btn small-btn" data-history-action="edit" data-history-id="${escapeHtml(item.id)}" type="button">Modify Inputs</button>
                        <button class="secondary-btn small-btn" data-history-action="rerun" data-history-id="${escapeHtml(item.id)}" type="button">Run Again</button>
                    </div>
                </article>
            `;
        }).join('');
    }

    function renderAll() {
        renderPhemaList();
        renderSnapshotGroupList();
        renderCastrList();
        renderPhemaSummary();
        renderParameterPreview();
        renderPrimaryAction();
        renderHistoryList();
        renderResult();
        renderSavedList();
        renderSavedDetail();
        renderPlazas();
        renderAgentConfigs();
        if (state.modalOpen) {
            renderParameterModal();
        }
        if (state.castModalOpen) {
            renderCastModal();
        }
    }

    async function loadCatalog() {
        if (state.loadingCatalog) return;
        state.loadingCatalog = true;
        setStatus('Loading catalog...');

        try {
            const params = new URLSearchParams();
            if (state.query) params.set('q', state.query);
            if (state.party) params.set('party', state.party);
            if (state.plazaUrl) params.set('plaza_url', state.plazaUrl);

            const response = await fetch(`/api/attas/catalog?${params.toString()}`);
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Failed to load Phemas');
            }

            state.catalog = {
                plazas: payload.plazas || [],
                applications: payload.applications || [],
                castrs: payload.castrs || [],
                llmPulsers: payload.llm_pulsers || [],
            };
            pinVisibleCastrsFromCatalog();

            syncSelections();
            renderAll();
            await loadSnapshotsForCurrentApplication();

            const connected = (state.catalog.plazas || []).filter((item) => plazaConnectionState(item) === 'connected').length;
            const online = (state.catalog.plazas || []).filter((item) => item.online).length;
            const total = (state.catalog.plazas || []).length;
            setStatus(
                total ? `${connected} connected · ${online} of ${total} plazas online` : 'No plazas found',
                connected ? 'success' : 'error',
            );
        } catch (error) {
            setStatus(error.message || 'Catalog unavailable', 'error');
        } finally {
            state.loadingCatalog = false;
        }
    }

    async function loadSnapshotsForCurrentApplication() {
        const application = currentApplication();
        if (!application) {
            state.snapshotApplicationKey = '';
            state.snapshots = [];
            state.loadingSnapshots = false;
            syncSnapshotSelection();
            renderSnapshotGroupList();
            renderParameterPreview();
            renderPrimaryAction();
            return;
        }

        const requestKey = applicationKey(application);
        state.snapshotApplicationKey = requestKey;
        state.loadingSnapshots = true;
        renderSnapshotGroupList();
        renderPrimaryAction();

        try {
            const params = new URLSearchParams({
                application_id: application.phema_id || application.id || '',
                application_name: application.name || '',
                phema_id: application.phema_id || application.id || '',
                plaza_url: application.plaza_url || '',
                phemar_agent_id: application.host_phemar_agent_id || '',
                phemar_name: application.host_phemar_name || '',
                phemar_plaza_url: application.host_phemar_plaza_url || application.plaza_url || '',
                phemar_address: application.host_phemar_address || '',
                limit: '100',
            });
            const response = await fetch(`/api/attas/snapshots?${params.toString()}`);
            const payload = await response.json();
            if (requestKey !== applicationKey(currentApplication() || {})) {
                return;
            }
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Failed to load snapshots');
            }
            state.snapshots = Array.isArray(payload.snapshots) ? payload.snapshots : [];
            syncSnapshotSelection();
            renderSnapshotGroupList();
            renderPhemaSummary();
            renderParameterPreview();
            renderPrimaryAction();
        } catch (error) {
            if (requestKey !== applicationKey(currentApplication() || {})) {
                return;
            }
            state.snapshots = [];
            state.selectedSnapshotId = '';
            state.selectedSnapshotGroupKey = '';
            state.snapshotMode = 'new';
            renderSnapshotGroupList();
            renderParameterPreview();
            renderPrimaryAction();
            setStatus(error.message || 'Failed to load snapshots', 'error');
        } finally {
            if (requestKey === applicationKey(currentApplication() || {})) {
                state.loadingSnapshots = false;
                renderSnapshotGroupList();
                renderPrimaryAction();
            }
        }
    }

    async function loadSavedResults() {
        if (state.loadingSaved) return;
        state.loadingSaved = true;

        try {
            const response = await fetch('/api/attas/saved_results');
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Failed to load saved results');
            }
            state.savedResults = payload.results || [];
            syncSelections();
            renderSavedList();
            renderSavedDetail();
        } catch (error) {
            refs.savedList.innerHTML = `
                <div class="empty-state">
                    <strong>Could not load saved results.</strong>
                    <p>${escapeHtml(error.message || 'Unknown error')}</p>
                </div>
            `;
        } finally {
            state.loadingSaved = false;
        }
    }

    async function loadAgentConfigs() {
        if (state.loadingAgentConfigs) return;
        state.loadingAgentConfigs = true;
        renderAgentConfigs();

        try {
            const params = new URLSearchParams({ include_config: 'true' });
            if (state.agentConfigQuery) params.set('q', state.agentConfigQuery);
            if (state.plazaUrl) params.set('plaza_url', state.plazaUrl);
            const response = await fetch(`/api/agent_configs?${params.toString()}`);
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Failed to load AgentConfig entries');
            }
            state.agentConfigs = Array.isArray(payload.agent_configs) ? payload.agent_configs : [];
            renderAgentConfigs();
        } catch (error) {
            state.agentConfigs = [];
            refs.agentConfigList.innerHTML = `
                <div class="empty-state">
                    <strong>Could not load AgentConfig entries.</strong>
                    <p>${escapeHtml(error.message || 'Unknown error')}</p>
                </div>
            `;
            refs.agentConfigCount.textContent = '0';
        } finally {
            state.loadingAgentConfigs = false;
            renderAgentConfigs();
        }
    }

    function renderAgentLaunchPopupDocument({ title = 'Launch Agent', configs = [], initialConfigKey = '' }) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${escapeHtml(title)}</title>
    <style>
        :root {
            color-scheme: light;
            --launch-bg: linear-gradient(180deg, #fbfcfe 0%, #f3f7fb 100%);
            --launch-surface: rgba(255, 255, 255, 0.94);
            --launch-border: rgba(15, 23, 42, 0.12);
            --launch-text: #0f172a;
            --launch-dim: #475569;
            --launch-accent: #0f172a;
            --launch-accent-soft: rgba(15, 23, 42, 0.08);
            --launch-success: #166534;
            --launch-warning: #c96a2b;
            --launch-danger: #b42318;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            padding: 1rem;
            font-family: "Manrope", sans-serif;
            color: var(--launch-text);
            background: var(--launch-bg);
        }
        .launch-shell {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .launch-header,
        .launch-panel {
            border: 1px solid var(--launch-border);
            border-radius: 20px;
            background: var(--launch-surface);
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
        }
        .launch-header h1,
        .launch-panel h2 {
            margin: 0;
            letter-spacing: -0.03em;
            font-family: "Fraunces", serif;
            font-weight: 600;
        }
        .launch-header h1 { font-size: 1.35rem; }
        .launch-panel h2 { font-size: 1rem; margin-bottom: 0.8rem; }
        .launch-copy,
        .launch-meta {
            color: var(--launch-dim);
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .launch-layout {
            display: grid;
            grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
            gap: 1rem;
        }
        .launch-search,
        .launch-input,
        .launch-select,
        .launch-textarea {
            width: 100%;
            border: 1px solid var(--launch-border);
            border-radius: 14px;
            padding: 0.82rem 0.92rem;
            font: inherit;
            color: var(--launch-text);
            background: rgba(255, 255, 255, 0.98);
        }
        .launch-search:focus,
        .launch-input:focus,
        .launch-select:focus,
        .launch-textarea:focus {
            outline: none;
            border-color: rgba(15, 23, 42, 0.34);
            box-shadow: 0 0 0 4px rgba(15, 23, 42, 0.08);
        }
        .launch-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-top: 0.9rem;
            max-height: 560px;
            overflow: auto;
        }
        .launch-config-btn {
            width: 100%;
            text-align: left;
            border: 1px solid var(--launch-border);
            border-radius: 16px;
            padding: 0.9rem;
            background: rgba(255, 255, 255, 0.96);
            color: inherit;
            cursor: pointer;
            transition: transform 140ms ease, background 140ms ease, border-color 140ms ease;
        }
        .launch-config-btn:hover {
            transform: translateY(-1px);
        }
        .launch-config-btn.active {
            border-color: rgba(15, 23, 42, 0.24);
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.1), rgba(255, 255, 255, 0.98));
        }
        .launch-config-name {
            font-size: 0.98rem;
            font-weight: 800;
        }
        .launch-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }
        .launch-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.34rem 0.7rem;
            border-radius: 999px;
            background: var(--launch-accent-soft);
            color: var(--launch-text);
            font-size: 0.74rem;
            font-weight: 700;
        }
        .launch-chip.subtle {
            color: var(--launch-dim);
            background: rgba(15, 23, 42, 0.04);
        }
        .launch-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
        }
        .launch-card {
            border: 1px solid var(--launch-border);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.84);
            padding: 0.9rem;
        }
        .launch-field {
            display: grid;
            gap: 0.42rem;
            margin-top: 0.82rem;
        }
        .launch-field label {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: var(--launch-dim);
            font-weight: 700;
        }
        .launch-textarea {
            min-height: 220px;
            resize: vertical;
            font: 0.82rem/1.45 "IBM Plex Mono", monospace;
            white-space: pre;
        }
        .launch-actions {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        .launch-btn {
            border: 0;
            border-radius: 999px;
            padding: 0.86rem 1.2rem;
            font: inherit;
            font-weight: 800;
            cursor: pointer;
            transition: transform 140ms ease, opacity 140ms ease;
        }
        .launch-btn:hover { transform: translateY(-1px); }
        .launch-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .launch-btn.primary {
            background: #0f172a;
            color: #fff;
        }
        .launch-btn.secondary {
            background: rgba(15, 23, 42, 0.08);
            color: var(--launch-text);
        }
        .launch-empty {
            border: 1px dashed rgba(15, 23, 42, 0.18);
            border-radius: 16px;
            padding: 1rem;
            color: var(--launch-dim);
            background: rgba(255, 255, 255, 0.7);
        }
        .launch-result {
            display: none;
            margin-top: 1rem;
            border-radius: 16px;
            padding: 0.95rem 1rem;
            border: 1px solid var(--launch-border);
            background: rgba(15, 23, 42, 0.04);
        }
        .launch-result.visible { display: block; }
        .launch-result.success {
            border-color: rgba(22, 101, 52, 0.24);
            background: rgba(22, 101, 52, 0.1);
        }
        .launch-result.warning {
            border-color: rgba(201, 106, 43, 0.22);
            background: rgba(201, 106, 43, 0.1);
        }
        .launch-result.error {
            border-color: rgba(180, 35, 24, 0.22);
            background: rgba(180, 35, 24, 0.1);
        }
        .launch-result-title {
            font-weight: 800;
            margin-bottom: 0.4rem;
        }
        @media (max-width: 900px) {
            body { padding: 0.8rem; }
            .launch-layout { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="launch-shell">
        <section class="launch-header">
            <h1>${escapeHtml(title)}</h1>
            <p class="launch-copy">Choose a saved AgentConfig from any connected plaza, review its stored template, then launch it on that plaza with runtime-only agent name, IP, port, and pool overrides.</p>
        </section>
        <section class="launch-layout">
            <section class="launch-panel">
                <h2>AgentConfig Directory</h2>
                <input id="config-search" class="launch-search" type="text" placeholder="Search by name, plaza, owner, or type">
                <div id="config-list" class="launch-list"></div>
            </section>
            <section class="launch-panel">
                <h2>Launch Detail</h2>
                <div id="config-detail"></div>
                <div id="launch-result" class="launch-result"></div>
            </section>
        </section>
    </div>
    <script>
        const CONFIGS = ${serializeForInlineScript(configs)};
        let selectedConfigKey = ${serializeForInlineScript(initialConfigKey || (configs[0] ? `${configs[0].plaza_url || ''}::${configs[0].id || ''}` : ''))};

        function popupEscapeHtml(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function popupPrettyJson(value) {
            try {
                return JSON.stringify(value || {}, null, 2);
            } catch (error) {
                return '{}';
            }
        }

        function configKey(entry) {
            return (entry?.plaza_url || '') + '::' + (entry?.id || '');
        }

        function filteredConfigs() {
            const query = String(document.getElementById('config-search')?.value || '').trim().toLowerCase();
            return CONFIGS.filter((entry) => {
                const haystack = [
                    entry.name,
                    entry.description,
                    entry.owner,
                    entry.role,
                    entry.agent_type,
                    entry.plaza_url,
                    JSON.stringify(entry.tags || []),
                ].join(' ').toLowerCase();
                return !query || haystack.includes(query);
            });
        }

        function currentConfig() {
            return CONFIGS.find((entry) => configKey(entry) === selectedConfigKey) || null;
        }

        function setLaunchResult({ tone = '', title = '', body = '', meta = [] } = {}) {
            const node = document.getElementById('launch-result');
            if (!node) return;
            if (!title && !body) {
                node.className = 'launch-result';
                node.innerHTML = '';
                return;
            }
            node.className = 'launch-result visible ' + (tone || '');
            node.innerHTML = '<div class="launch-result-title">' + popupEscapeHtml(title || 'Launch Result') + '</div>'
                + (body ? '<div class="launch-meta">' + popupEscapeHtml(body) + '</div>' : '')
                + (Array.isArray(meta) && meta.length
                    ? '<div class="launch-chip-row">' + meta.map((entry) => '<span class="launch-chip subtle">' + popupEscapeHtml(entry) + '</span>').join('') + '</div>'
                    : '');
        }

        function renderConfigList() {
            const listNode = document.getElementById('config-list');
            if (!listNode) return;
            const items = filteredConfigs();
            if (!items.length) {
                listNode.innerHTML = '<div class="launch-empty">No AgentConfig entries match this search.</div>';
                return;
            }
            if (!items.some((entry) => configKey(entry) === selectedConfigKey)) {
                selectedConfigKey = configKey(items[0]);
            }
            listNode.innerHTML = items.map((entry) => {
                const chips = [
                    entry.role,
                    entry.agent_type,
                    entry.owner,
                    entry.plaza_url,
                ].filter(Boolean).slice(0, 4);
                return '<button class="launch-config-btn ' + (configKey(entry) === selectedConfigKey ? 'active' : '') + '" type="button" data-select-config="1" data-config-key="'
                    + popupEscapeHtml(configKey(entry)) + '">'
                    + '<div class="launch-config-name">' + popupEscapeHtml(entry.name || 'Unnamed AgentConfig') + '</div>'
                    + '<div class="launch-meta">' + popupEscapeHtml(entry.description || 'No description registered.') + '</div>'
                    + (chips.length ? '<div class="launch-chip-row">' + chips.map((chip) => '<span class="launch-chip subtle">' + popupEscapeHtml(chip) + '</span>').join('') + '</div>' : '')
                    + '</button>';
            }).join('');
        }

        function renderConfigDetail() {
            const detailNode = document.getElementById('config-detail');
            if (!detailNode) return;
            const selected = currentConfig();
            if (!selected) {
                detailNode.innerHTML = '<div class="launch-empty">Choose an AgentConfig to inspect its stored template and launch it.</div>';
                return;
            }
            const storedConfig = selected.config && typeof selected.config === 'object' ? selected.config : {};
            const inferredPool = (() => {
                const pools = Array.isArray(storedConfig.pools) ? storedConfig.pools.filter((entry) => entry && typeof entry === 'object') : [];
                const pool = pools[0] || {};
                const locationKeys = ['root_path', 'db_path', 'path', 'file_path', 'sqlite_path', 'url', 'project_url', 'supabase_url', 'location', 'directory', 'bucket'];
                const poolLocation = locationKeys.map((key) => String(pool?.[key] || '').trim()).find(Boolean) || '';
                return {
                    poolType: String(pool?.type || '').trim(),
                    poolLocation,
                };
            })();
            const seedId = String(detailNode.dataset.seedConfigKey || '').trim();
            const shouldSeedDefaults = seedId !== selectedConfigKey;
            if (shouldSeedDefaults) {
                detailNode.dataset.seedConfigKey = selectedConfigKey;
            }
            detailNode.innerHTML = ''
                + '<div class="launch-card">'
                + '  <div class="launch-grid">'
                + '    <div><div class="launch-meta">Name</div><div><strong>' + popupEscapeHtml(selected.name || 'Unnamed AgentConfig') + '</strong></div></div>'
                + '    <div><div class="launch-meta">Agent Type</div><div><strong>' + popupEscapeHtml(selected.agent_type || 'Unknown') + '</strong></div></div>'
                + '    <div><div class="launch-meta">Role</div><div><strong>' + popupEscapeHtml(selected.role || 'unspecified') + '</strong></div></div>'
                + '    <div><div class="launch-meta">Plaza</div><div><strong>' + popupEscapeHtml(selected.plaza_url || 'Unavailable') + '</strong></div></div>'
                + '  </div>'
                + (selected.description ? '<p class="launch-copy" style="margin:0.9rem 0 0;">' + popupEscapeHtml(selected.description) + '</p>' : '')
                + '  <div class="launch-chip-row">'
                +        (Array.isArray(selected.tags) ? selected.tags.map((tag) => '<span class="launch-chip">' + popupEscapeHtml(tag) + '</span>').join('') : '')
                + '  </div>'
                + '</div>'
                + '<div class="launch-card">'
                + '  <div class="launch-field">'
                + '    <label for="launch-agent-name">Agent Name</label>'
                + '    <input id="launch-agent-name" class="launch-input" type="text" placeholder="runtime agent name">'
                + '  </div>'
                + '  <div class="launch-grid">'
                + '    <div class="launch-field">'
                + '      <label for="launch-host">IP Address</label>'
                + '      <input id="launch-host" class="launch-input" type="text" placeholder="127.0.0.1">'
                + '    </div>'
                + '    <div class="launch-field">'
                + '      <label for="launch-port">Port</label>'
                + '      <input id="launch-port" class="launch-input" type="number" min="1" step="1" placeholder="dynamic">'
                + '    </div>'
                + '  </div>'
                + '  <div class="launch-grid">'
                + '    <div class="launch-field">'
                + '      <label for="launch-pool-type">Pool Type</label>'
                + '      <select id="launch-pool-type" class="launch-select">'
                + '        <option value="">Use saved pool</option>'
                + '        <option value="FileSystemPool">FileSystemPool</option>'
                + '        <option value="SQLitePool">SQLitePool</option>'
                + '        <option value="SupabasePool">SupabasePool</option>'
                + '      </select>'
                + '    </div>'
                + '    <div class="launch-field">'
                + '      <label for="launch-pool-location">Pool Location</label>'
                + '      <input id="launch-pool-location" class="launch-input" type="text" placeholder="filesystem path, db path, or URL">'
                + '    </div>'
                + '  </div>'
                + '  <div class="launch-field">'
                + '    <label for="launch-config-json">Stored Config</label>'
                + '    <textarea id="launch-config-json" class="launch-textarea" readonly></textarea>'
                + '  </div>'
                + '  <div class="launch-actions">'
                + '    <button id="launch-submit" class="launch-btn primary" type="button">Launch Agent</button>'
                + '    <button id="launch-reset" class="launch-btn secondary" type="button">Reset Runtime Fields</button>'
                + '  </div>'
                + '</div>';
            const agentNameInput = document.getElementById('launch-agent-name');
            const hostInput = document.getElementById('launch-host');
            const portInput = document.getElementById('launch-port');
            const poolTypeInput = document.getElementById('launch-pool-type');
            const poolLocationInput = document.getElementById('launch-pool-location');
            const configJsonInput = document.getElementById('launch-config-json');
            if (configJsonInput) {
                configJsonInput.value = popupPrettyJson(storedConfig);
            }
            if (shouldSeedDefaults) {
                if (agentNameInput) agentNameInput.value = String(storedConfig.name || selected.name || '').trim();
                if (hostInput) hostInput.value = '';
                if (portInput) portInput.value = '';
                if (poolTypeInput) poolTypeInput.value = inferredPool.poolType || '';
                if (poolLocationInput) poolLocationInput.value = inferredPool.poolLocation || '';
            }
        }

        function renderPopup() {
            renderConfigList();
            renderConfigDetail();
        }

        async function launchSelectedConfig() {
            const selected = currentConfig();
            if (!selected) {
                setLaunchResult({
                    tone: 'error',
                    title: 'Choose An AgentConfig',
                    body: 'Select one directory entry before launching.',
                });
                return;
            }

            const submitButton = document.getElementById('launch-submit');
            const agentName = String(document.getElementById('launch-agent-name')?.value || '').trim();
            const host = String(document.getElementById('launch-host')?.value || '').trim();
            const portRaw = String(document.getElementById('launch-port')?.value || '').trim();
            const poolType = String(document.getElementById('launch-pool-type')?.value || '').trim();
            const poolLocation = String(document.getElementById('launch-pool-location')?.value || '').trim();

            if (!agentName) {
                setLaunchResult({
                    tone: 'error',
                    title: 'Agent Name Required',
                    body: 'Enter the runtime agent name before launching.',
                });
                return;
            }

            setLaunchResult({
                title: 'Launching Agent',
                body: 'Contacting the selected plaza, checking stored credentials, and waiting for runtime health.',
            });
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Launching...';
            }

            try {
                const response = await fetch('/api/agent_configs/launch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        plaza_url: selected.plaza_url || '',
                        config_id: selected.id,
                        agent_name: agentName,
                        host: host || null,
                        port: portRaw ? Number(portRaw) : null,
                        pool_type: poolType || null,
                        pool_location: poolLocation || null,
                    }),
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.detail || payload.message || 'Could not launch agent');
                }
                const launch = payload.launch && typeof payload.launch === 'object' ? payload.launch : {};
                const existing = launch.existing_agent && typeof launch.existing_agent === 'object' ? launch.existing_agent : {};
                const meta = [];
                if (launch.plaza_url || selected.plaza_url) meta.push('Plaza: ' + (launch.plaza_url || selected.plaza_url));
                if (launch.requested_agent_name) meta.push('Agent: ' + launch.requested_agent_name);
                if (launch.address) meta.push('Address: ' + launch.address);
                if (existing.address) meta.push('Address: ' + existing.address);
                if (launch.used_existing_identity) meta.push('Used saved plaza credential');
                setLaunchResult({
                    tone: launch.status === 'already_running' ? 'warning' : 'success',
                    title: launch.status === 'already_running' ? 'Agent Already Running' : 'Agent Running',
                    body: launch.status === 'already_running'
                        ? 'A matching active agent already exists on the selected plaza, so no duplicate process was started.'
                        : 'The selected plaza started the agent and reported a healthy runtime.',
                    meta,
                });
                if (window.opener && !window.opener.closed) {
                    window.opener.postMessage({
                        type: 'user-agent-config-launch',
                        launch,
                    }, window.location.origin);
                }
            } catch (error) {
                setLaunchResult({
                    tone: 'error',
                    title: 'Launch Failed',
                    body: error?.message || 'Unknown launch error.',
                });
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Launch Agent';
                }
            }
        }

        document.addEventListener('click', (event) => {
            const configButton = event.target.closest('[data-select-config]');
            if (configButton) {
                selectedConfigKey = String(configButton.dataset.configKey || '').trim();
                setLaunchResult();
                renderPopup();
                return;
            }
            const resetButton = event.target.closest('#launch-reset');
            if (resetButton) {
                const selected = currentConfig();
                const storedConfig = selected?.config && typeof selected.config === 'object' ? selected.config : {};
                const inferredPool = (() => {
                    const pools = Array.isArray(storedConfig.pools) ? storedConfig.pools.filter((entry) => entry && typeof entry === 'object') : [];
                    const pool = pools[0] || {};
                    const locationKeys = ['root_path', 'db_path', 'path', 'file_path', 'sqlite_path', 'url', 'project_url', 'supabase_url', 'location', 'directory', 'bucket'];
                    const poolLocation = locationKeys.map((key) => String(pool?.[key] || '').trim()).find(Boolean) || '';
                    return {
                        poolType: String(pool?.type || '').trim(),
                        poolLocation,
                    };
                })();
                document.getElementById('launch-agent-name').value = String(storedConfig.name || selected?.name || '').trim();
                document.getElementById('launch-host').value = '';
                document.getElementById('launch-port').value = '';
                document.getElementById('launch-pool-type').value = inferredPool.poolType || '';
                document.getElementById('launch-pool-location').value = inferredPool.poolLocation || '';
                setLaunchResult();
                return;
            }
            const submitButton = event.target.closest('#launch-submit');
            if (submitButton) {
                launchSelectedConfig();
            }
        });

        document.getElementById('config-search')?.addEventListener('input', () => {
            renderConfigList();
        });

        renderPopup();
    ${'</scr' + 'ipt>'}
</body>
</html>`;
    }

    function openAgentConfigLaunchPopup(configKey = '') {
        const configs = Array.isArray(state.agentConfigs) ? state.agentConfigs.filter((entry) => entry && entry.id && entry.plaza_url) : [];
        const initialConfig = configKey
            ? configs.find((entry) => agentConfigKey(entry) === configKey) || null
            : configs[0] || null;
        const popup = window.open('', `user-agent-launch-${Date.now()}`, 'popup=yes,width=1040,height=860,resizable=yes,scrollbars=yes');
        if (!popup) {
            setStatus('Allow popups to launch AgentConfig entries.', 'error');
            return;
        }
        popup.document.write(renderAgentLaunchPopupDocument({
            title: 'Launch Agent',
            configs,
            initialConfigKey: initialConfig ? agentConfigKey(initialConfig) : '',
        }));
        popup.document.close();
    }

    function syncModalDraftFromDom() {
        const application = currentApplication();
        if (!application) return {};

        const values = { ...(state.paramValuesByApplication[applicationKey(application)] || {}) };
        refs.modalParamForm.querySelectorAll('[data-modal-param-name]').forEach((input) => {
            const name = input.dataset.modalParamName;
            if (!name) return;
            values[name] = input.type === 'checkbox' ? input.checked : input.value;
        });
        state.paramValuesByApplication[applicationKey(application)] = values;
        return values;
    }

    function normalizeTypedValue(definition, value) {
        if (definition.type === 'boolean') {
            return Boolean(value);
        }
        if (definition.type === 'integer') {
            if (value === '' || value === null || value === undefined) return null;
            const parsed = parseInt(value, 10);
            return Number.isNaN(parsed) ? null : parsed;
        }
        if (definition.type === 'number') {
            if (value === '' || value === null || value === undefined) return null;
            const parsed = parseFloat(value);
            return Number.isNaN(parsed) ? null : parsed;
        }
        if (value === '' || value === null || value === undefined) {
            return '';
        }
        return String(value);
    }

    function collectFriendlyParams(application = currentApplication()) {
        if (!application) return {};
        const values = { ...(state.paramValuesByApplication[applicationKey(application)] || {}) };
        const result = {};

        fieldDefinitionEntries(application).forEach(({ name, definition }) => {
            const normalized = normalizeTypedValue(definition, values[name]);
            if (definition.type === 'boolean') {
                result[name] = Boolean(normalized);
                return;
            }
            if (normalized === null || normalized === '') {
                return;
            }
            result[name] = normalized;
        });

        return result;
    }

    function validateRequiredFields(application) {
        const values = state.paramValuesByApplication[applicationKey(application)] || {};
        const missing = [];

        fieldDefinitionEntries(application).forEach(({ name, definition, required }) => {
            if (!required) return;
            const normalized = normalizeTypedValue(definition, values[name]);
            if (definition.type === 'boolean') return;
            if (normalized === null || normalized === '') {
                missing.push(definition.title || name.replace(/_/g, ' '));
            }
        });

        if (!missing.length) return '';
        return `Please fill in: ${missing.join(', ')}`;
    }

    function showModalError(message) {
        refs.parameterModalError.hidden = false;
        refs.parameterModalError.textContent = message;
    }

    function clearModalError() {
        refs.parameterModalError.hidden = true;
        refs.parameterModalError.textContent = '';
    }

    function showCastModalError(message) {
        refs.castModalError.hidden = false;
        refs.castModalError.textContent = message;
    }

    function clearCastModalError() {
        refs.castModalError.hidden = true;
        refs.castModalError.textContent = '';
    }

    function renderModalField(name, definition, required, value) {
        const label = definition.title || name.replace(/_/g, ' ');
        const help = definition.description ? `<span class="muted">${escapeHtml(definition.description)}</span>` : '';

        if (Array.isArray(definition.enum) && definition.enum.length) {
            return `
                <div class="field-row">
                    <label for="modal-param-${escapeHtml(name)}">${escapeHtml(label)}${required ? ' *' : ''}</label>
                    <select id="modal-param-${escapeHtml(name)}" data-modal-param-name="${escapeHtml(name)}">
                        ${definition.enum.map((option) => `
                            <option value="${escapeHtml(option)}" ${String(option) === String(value) ? 'selected' : ''}>${escapeHtml(option)}</option>
                        `).join('')}
                    </select>
                    ${help}
                </div>
            `;
        }

        if (definition.type === 'boolean') {
            return `
                <label class="checkbox-row">
                    <input id="modal-param-${escapeHtml(name)}" data-modal-param-name="${escapeHtml(name)}" type="checkbox" ${value ? 'checked' : ''}>
                    <span>${escapeHtml(label)}${required ? ' *' : ''}</span>
                </label>
            `;
        }

        const inputType = definition.type === 'number' || definition.type === 'integer' ? 'number' : 'text';
        const step = definition.type === 'integer' ? '1' : 'any';
        return `
            <div class="field-row">
                <label for="modal-param-${escapeHtml(name)}">${escapeHtml(label)}${required ? ' *' : ''}</label>
                <input
                    id="modal-param-${escapeHtml(name)}"
                    data-modal-param-name="${escapeHtml(name)}"
                    type="${inputType}"
                    step="${step}"
                    value="${escapeHtml(value ?? '')}"
                    placeholder="${escapeHtml(definition.examples?.[0] || definition.placeholder || '')}"
                >
                ${help}
            </div>
        `;
    }

    function renderParameterModal() {
        const application = currentApplication();
        const castr = currentCastr();
        const snapshot = selectedSnapshotRow();
        const group = selectedSnapshotGroup();

        if (!application) {
            refs.parameterModalSummary.innerHTML = `
                <div class="empty-state">
                    <strong>Select a Phema first.</strong>
                    <p>The snapshot form will appear here after a Phema is selected.</p>
                </div>
            `;
            refs.modalParamForm.innerHTML = '';
            refs.parameterModalSubmit.disabled = true;
            return;
        }

        refs.parameterModalSubmit.disabled = false;
        seedParamsFromSchema(application);
        const values = state.paramValuesByApplication[applicationKey(application)] || {};
        const entries = fieldDefinitionEntries(application);
        const requiredFields = entries.filter((item) => item.required);
        const optionalFields = entries.filter((item) => !item.required);

        refs.parameterModalTitle.textContent = 'Create Snapshot';
        refs.parameterModalCopy.textContent = entries.length
            ? 'Fill in the details below to create a snapshot. After that, you can package it with a Castr.'
            : 'No extra details are required for this Phema. You can create the snapshot immediately.';

        refs.parameterModalSubmit.textContent = state.modalSourceHistoryId ? 'Create Updated Snapshot' : 'Create Snapshot';

        refs.parameterModalSummary.innerHTML = `
            <div>
                <p class="panel-kicker">Snapshot</p>
                <h4 class="hero-title">${escapeHtml(application.name || 'Unnamed Phema')}</h4>
                <p class="hero-copy">${escapeHtml(application.description || 'No description provided.')}</p>
                <div class="meta-row">
                    ${snapshot ? `<span class="meta-chip">Updating from snapshot ${escapeHtml(snapshotRowId(snapshot).slice(0, 8))}</span>` : ''}
                    ${!snapshot && group ? '<span class="meta-chip">Using saved input group</span>' : ''}
                    ${!snapshot && !group ? '<span class="meta-chip">Fresh input set</span>' : ''}
                    <span class="meta-chip">Reuse data: ${escapeHtml(refs.cacheTime.value || '300')}s</span>
                    ${castr ? `<span class="meta-chip">Next: ${escapeHtml(castr.name || castr.media_type || 'Create My Result')}</span>` : ''}
                </div>
            </div>
        `;

        if (!entries.length) {
            refs.modalParamForm.innerHTML = `
                <div class="empty-state">
                    <strong>This Phema does not ask for any extra fields.</strong>
                    <p>Click “${escapeHtml(refs.parameterModalSubmit.textContent)}” to add the snapshot to your library.</p>
                </div>
            `;
            return;
        }

        const sections = [];
        if (requiredFields.length) {
            sections.push(`
                <section class="modal-section">
                    <div class="modal-section-head">
                        <h4>Required Details</h4>
                        <p class="modal-section-copy">These are the details needed before the Phema can run.</p>
                    </div>
                    <div class="modal-section-grid">
                        ${requiredFields.map(({ name, definition, required }) => renderModalField(name, definition, required, values[name])).join('')}
                    </div>
                </section>
            `);
        }
        if (optionalFields.length) {
            sections.push(`
                <section class="modal-section">
                    <div class="modal-section-head">
                        <h4>Optional Details</h4>
                        <p class="modal-section-copy">You can leave these as they are, or adjust only the parts you want to change.</p>
                    </div>
                    <div class="modal-section-grid">
                        ${optionalFields.map(({ name, definition, required }) => renderModalField(name, definition, required, values[name])).join('')}
                    </div>
                </section>
            `);
        }

        refs.modalParamForm.innerHTML = sections.join('');
    }

    function renderCastModal() {
        const application = currentApplication();
        const castr = currentCastr();
        const llmPulser = currentLlmPulser();
        const llmPulsers = visibleLlmPulsers();
        const snapshot = selectedSnapshotRow();
        const snapshotPayload = snapshot?.snapshot && typeof snapshot.snapshot === 'object'
            ? snapshot.snapshot
            : snapshot;

        if (!application || !castr || !snapshot) {
            refs.castModalSummary.innerHTML = `
                <div class="empty-state">
                    <strong>Select a snapshot and a Castr first.</strong>
                    <p>The final-result popup appears only when a saved snapshot is ready to be packaged.</p>
                </div>
            `;
            refs.castModalSubmit.disabled = true;
            return;
        }

        seedPersonalizationDraft(application);
        const values = collectPersonalization(application);
        refs.castLlmPulser.innerHTML = llmPulsers.length
            ? llmPulsers.map((item) => `
                <option value="${escapeHtml(llmPulserKey(item))}" ${llmPulserKey(item) === state.selectedLlmPulserKey ? 'selected' : ''}>
                    ${escapeHtml(item.name || 'Unnamed llm_chat pulser')}
                </option>
            `).join('')
            : '<option value="">No active llm_chat pulsers found</option>';
        refs.castLlmPulser.disabled = !llmPulsers.length;
        refs.castLlmPulserMeta.textContent = llmPulser
            ? `${llmPulser.description || 'Ready to run llm_chat inference.'}${llmPulser.plaza_url ? ` · ${llmPulser.plaza_url}` : ''}`
            : 'Choose which active llm_chat pulser should run the temporary-script inference.';
        refs.castModalSubmit.disabled = !llmPulser;
        refs.castModalSubmit.textContent = 'Generate Final Result';
        refs.castModalTitle.textContent = 'Create My Result';
        refs.castModalCopy.textContent = 'These choices are sent to an LLM pulser first, which creates a temporary script before the Castr generates the final result.';
        refs.castTone.value = values.tone || 'Balanced';
        refs.castStyle.value = values.style || 'Executive brief';
        refs.castAudience.value = values.audience || '';
        refs.castLanguage.value = values.language || 'en';
        refs.castModifier.value = values.modifier || '';
        refs.castInstructions.value = values.instructions || '';

        refs.castModalSummary.innerHTML = `
            <div>
                <p class="panel-kicker">Ready To Cast</p>
                <h4 class="hero-title">${escapeHtml(application.name || 'Unnamed Phema')}</h4>
                <p class="hero-copy">${escapeHtml(snapshotPayload?.description || application.description || 'Your snapshot is ready for final packaging.')}</p>
                <div class="meta-row">
                    <span class="meta-chip">Snapshot ${escapeHtml(snapshotRowId(snapshot).slice(0, 8) || 'n/a')}</span>
                    <span class="meta-chip">Castr: ${escapeHtml(castr.name || 'Unnamed Castr')}</span>
                    ${llmPulser ? `<span class="meta-chip">LLM pulser: ${escapeHtml(llmPulser.name || 'llm_chat')}</span>` : ''}
                    <span class="meta-chip">Format: ${escapeHtml(refs.renderFormat.value.trim() || castr.media_type || 'PDF')}</span>
                    ${snapshotPayload?.name ? `<span class="meta-chip">Snapshot title: ${escapeHtml(snapshotPayload.name)}</span>` : ''}
                </div>
            </div>
        `;
    }

    function openParameterModal() {
        const application = currentApplication();
        if (!application) {
            setStatus('Choose a Phema first', 'error');
            return;
        }

        clearModalError();
        state.modalIntent = 'snapshot';
        state.modalOpen = true;
        refs.parameterModal.hidden = false;
        refs.parameterModal.setAttribute('aria-hidden', 'false');
        updateModalBodyState();
        renderParameterModal();
    }

    function closeParameterModal() {
        state.modalOpen = false;
        state.modalIntent = 'snapshot';
        state.modalSourceHistoryId = '';
        refs.parameterModal.hidden = true;
        refs.parameterModal.setAttribute('aria-hidden', 'true');
        updateModalBodyState();
        clearModalError();
    }

    function syncCastDraftFromDom() {
        const application = currentApplication();
        if (!application) return {};

        state.selectedLlmPulserKey = refs.castLlmPulser.value || '';
        const values = {
            tone: refs.castTone.value,
            style: refs.castStyle.value,
            audience: refs.castAudience.value,
            language: refs.castLanguage.value,
            modifier: refs.castModifier.value,
            instructions: refs.castInstructions.value,
        };
        mergePersonalizationDraft(application, values);
        return collectPersonalization(application);
    }

    function openCastModal() {
        const application = currentApplication();
        const castr = currentCastr();
        const snapshot = selectedSnapshotRow();
        if (!application) {
            setStatus('Choose a Phema first', 'error');
            return;
        }
        if (!snapshot) {
            setStatus('Choose a snapshot first', 'error');
            return;
        }
        if (!castr) {
            setStatus('Choose a Castr first', 'error');
            return;
        }

        clearCastModalError();
        state.castModalOpen = true;
        refs.castModal.hidden = false;
        refs.castModal.setAttribute('aria-hidden', 'false');
        updateModalBodyState();
        renderCastModal();
    }

    function closeCastModal() {
        state.castModalOpen = false;
        refs.castModal.hidden = true;
        refs.castModal.setAttribute('aria-hidden', 'true');
        updateModalBodyState();
        clearCastModalError();
    }

    function closeActiveModal() {
        if (state.castModalOpen) {
            closeCastModal();
            return;
        }
        if (state.modalOpen) {
            closeParameterModal();
        }
    }

    function buildHistoryEntry({ application, castr, llmPulser, params, personalization, result, format, cacheTime, sourceHistoryId, snapshotId, snapshotMode }) {
        const snapshot = result?.snapshot?.snapshot || {};
        return {
            id: `run-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
            createdAt: new Date().toISOString(),
            sourceHistoryId: sourceHistoryId || '',
            applicationId: application.phema_id || application.id || '',
            applicationName: application.name || '',
            applicationPlazaUrl: application.plaza_url || '',
            castrAgentId: castr?.agent_id || '',
            castrName: castr?.name || '',
            castrPlazaUrl: castr?.plaza_url || '',
            llmPulserAgentId: llmPulser?.agent_id || '',
            llmPulserName: llmPulser?.name || '',
            llmPulserPlazaUrl: llmPulser?.plaza_url || '',
            format: format || castr?.media_type || '',
            cacheTime,
            params,
            personalization: personalization || {},
            snapshotId: snapshotId || result?.snapshot?.snapshot_id || result?.snapshot?.history?.snapshot_id || '',
            snapshotMode: snapshotMode || 'new',
            snapshotName: snapshot.name || application.name || '',
            snapshotDescription: snapshot.description || application.description || '',
            publicUrl: result?.cast?.public_url || '',
        };
    }

    function recordHistoryEntry(payload) {
        const entry = buildHistoryEntry(payload);
        state.historyEntries = [entry, ...(state.historyEntries || [])].slice(0, historyLimit);
        persistHistoryEntries();
        renderHistoryList();
    }

    async function ensureHistorySelection(entry) {
        const matchApplication = () => (state.catalog.applications || []).find((item) => {
            const id = item.phema_id || item.id || '';
            return id === entry.applicationId && (item.plaza_url || '') === (entry.applicationPlazaUrl || '');
        }) || null;

        const matchCastr = () => (state.catalog.castrs || []).find((item) => {
            return (item.agent_id || '') === entry.castrAgentId && (item.plaza_url || '') === (entry.castrPlazaUrl || '');
        }) || null;
        const matchLlmPulser = () => (state.catalog.llmPulsers || []).find((item) => {
            return (item.agent_id || '') === entry.llmPulserAgentId && (item.plaza_url || '') === (entry.llmPulserPlazaUrl || '');
        }) || null;

        let application = matchApplication();
        let castr = matchCastr();
        let llmPulser = matchLlmPulser();

        if ((!application || (entry.castrAgentId && !castr)) && state.plazaUrl) {
            state.plazaUrl = '';
            refs.plazaFilter.value = '';
            await loadCatalog();
            application = matchApplication();
            castr = matchCastr();
            llmPulser = matchLlmPulser();
        }

        if (!application || (entry.castrAgentId && !castr)) {
            setStatus('This earlier run is not available in the current catalog.', 'error');
            return false;
        }

        state.selectedApplicationKey = applicationKey(application);
        state.selectedCastrKey = castr ? castrKey(castr) : '';
        state.selectedLlmPulserKey = llmPulser ? llmPulserKey(llmPulser) : state.selectedLlmPulserKey;
        syncSelections();
        await loadSnapshotsForCurrentApplication();
        mergeDraftParams(application, entry.params || {});
        mergePersonalizationDraft(application, entry.personalization || {});
        if (entry.format) {
            refs.renderFormat.value = entry.format;
        }
        if (entry.cacheTime !== undefined && entry.cacheTime !== null) {
            refs.cacheTime.value = String(entry.cacheTime);
        }
        const matchingSnapshot = (state.snapshots || []).find((item) => snapshotRowId(item) === String(entry.snapshotId || ''));
        if (matchingSnapshot && entry.snapshotMode === 'snapshot') {
            selectSnapshotMode({
                mode: 'snapshot',
                snapshot: matchingSnapshot,
                group: buildSnapshotGroups(state.snapshots).find((group) => group.key === snapshotGroupKey(matchingSnapshot)) || null,
            });
        } else if (matchingSnapshot) {
            selectSnapshotMode({
                mode: 'new',
                group: buildSnapshotGroups(state.snapshots).find((group) => group.key === snapshotGroupKey(matchingSnapshot)) || null,
            });
        } else {
            state.selectedSnapshotId = '';
            state.selectedSnapshotGroupKey = '';
            state.snapshotMode = 'new';
        }
        renderAll();
        return true;
    }

    async function regenerateSnapshotAndResult({ sourceHistoryId = '', paramsOverride = null, personalizationOverride = null } = {}) {
        const application = currentApplication();
        const castr = currentCastr();
        const llmPulser = currentLlmPulser();
        if (!application) {
            setStatus('Choose a Phema first', 'error');
            return;
        }
        if (!castr) {
            setStatus('Choose a Castr first', 'error');
            return;
        }
        if (!llmPulser) {
            setStatus('Choose an active llm_chat pulser first', 'error');
            return;
        }

        const params = paramsOverride && typeof paramsOverride === 'object'
            ? paramsOverride
            : collectFriendlyParams(application);
        const personalization = personalizationOverride && typeof personalizationOverride === 'object'
            ? personalizationOverride
            : collectPersonalization(application);

        state.generating = true;
        refs.generateResult.disabled = true;
        refs.generateResult.textContent = 'Creating My Result...';
        setStatus('Creating your result...');

        try {
            const response = await fetch('/api/attas/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    application_id: application.phema_id || application.id,
                    application_name: application.name,
                    phema_id: application.phema_id || application.id || '',
                    plaza_url: application.plaza_url,
                    phemar_agent_id: application.host_phemar_agent_id || '',
                    phemar_name: application.host_phemar_name || '',
                    phemar_plaza_url: application.host_phemar_plaza_url || application.plaza_url || '',
                    phemar_address: application.host_phemar_address || '',
                    castr_agent_id: castr.agent_id,
                    castr_plaza_url: castr.plaza_url,
                    llm_agent_id: llmPulser.agent_id,
                    llm_plaza_url: llmPulser.plaza_url,
                    params,
                    preferences: {
                        audience: personalization.audience,
                        language: personalization.language,
                        theme: personalization.style,
                    },
                    personalization,
                    use_llm_preprocessor: true,
                    format: refs.renderFormat.value.trim() || castr.media_type || 'PDF',
                    cache_time: Number(refs.cacheTime.value || 0),
                }),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Could not create result');
            }

            state.lastResult = payload;
            await loadSnapshotsForCurrentApplication();
            const createdSnapshotId = String(payload?.snapshot?.snapshot_id || payload?.snapshot?.history?.snapshot_id || '').trim();
            const createdSnapshot = (state.snapshots || []).find((item) => snapshotRowId(item) === createdSnapshotId) || null;
            if (createdSnapshot) {
                selectSnapshotMode({
                    mode: 'snapshot',
                    snapshot: createdSnapshot,
                    group: buildSnapshotGroups(state.snapshots).find((group) => group.key === snapshotGroupKey(createdSnapshot)) || null,
                });
            }
            recordHistoryEntry({
                application,
                castr,
                llmPulser,
                params,
                personalization,
                result: payload,
                format: refs.renderFormat.value.trim() || castr.media_type || 'PDF',
                cacheTime: Number(refs.cacheTime.value || 0),
                sourceHistoryId,
                snapshotId: createdSnapshotId,
                snapshotMode: createdSnapshotId ? 'snapshot' : 'new',
            });
            renderAll();
            setStatus('Result ready', 'success');
        } catch (error) {
            setStatus(error.message || 'Could not create result', 'error');
        } finally {
            state.generating = false;
            refs.generateResult.disabled = false;
            renderPrimaryAction();
        }
    }

    async function createSnapshotOnly({ sourceHistoryId = '' } = {}) {
        const application = currentApplication();
        if (!application) {
            setStatus('Choose a Phema first', 'error');
            return;
        }

        const requiredMessage = validateRequiredFields(application);
        if (requiredMessage) {
            showModalError(requiredMessage);
            setStatus(requiredMessage, 'error');
            return;
        }
        const params = collectFriendlyParams(application);

        state.generating = true;
        refs.generateResult.disabled = true;
        refs.parameterModalSubmit.disabled = true;
        refs.generateResult.textContent = 'Creating Snapshot...';
        refs.parameterModalSubmit.textContent = 'Creating Snapshot...';
        setStatus('Creating your snapshot...');

        try {
            const response = await fetch('/api/attas/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    application_id: application.phema_id || application.id,
                    application_name: application.name,
                    phema_id: application.phema_id || application.id || '',
                    plaza_url: application.plaza_url,
                    phemar_agent_id: application.host_phemar_agent_id || '',
                    phemar_name: application.host_phemar_name || '',
                    phemar_plaza_url: application.host_phemar_plaza_url || application.plaza_url || '',
                    phemar_address: application.host_phemar_address || '',
                    params,
                    preferences: {},
                    cache_time: Number(refs.cacheTime.value || 0),
                }),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Could not create snapshot');
            }

            state.lastResult = payload;
            await loadSnapshotsForCurrentApplication();
            const createdSnapshotId = String(payload?.snapshot?.snapshot_id || payload?.snapshot?.history?.snapshot_id || '').trim();
            const createdSnapshot = (state.snapshots || []).find((item) => snapshotRowId(item) === createdSnapshotId) || null;
            if (createdSnapshot) {
                selectSnapshotMode({
                    mode: 'snapshot',
                    snapshot: createdSnapshot,
                    group: buildSnapshotGroups(state.snapshots).find((group) => group.key === snapshotGroupKey(createdSnapshot)) || null,
                });
            }
            renderAll();
            closeParameterModal();
            setStatus(
                createdSnapshotId
                    ? `Snapshot ${createdSnapshotId.slice(0, 8)} is ready. Choose a Castr to create your result.`
                    : 'Snapshot ready. Choose a Castr to create your result.',
                'success',
            );
        } catch (error) {
            showModalError(error.message || 'Could not create snapshot');
            setStatus(error.message || 'Could not create snapshot', 'error');
        } finally {
            state.generating = false;
            refs.generateResult.disabled = false;
            refs.parameterModalSubmit.disabled = false;
            renderPrimaryAction();
            renderParameterModal();
        }
    }

    async function castSelectedSnapshot({ sourceHistoryId = '', snapshotId = '', personalizationOverride = null } = {}) {
        const application = currentApplication();
        const castr = currentCastr();
        const llmPulser = currentLlmPulser();
        const activeSnapshotId = String(snapshotId || state.selectedSnapshotId || '').trim();
        const selectedSnapshot = activeSnapshotId
            ? (state.snapshots || []).find((item) => snapshotRowId(item) === activeSnapshotId) || null
            : null;
        if (!application) {
            setStatus('Choose a Phema first', 'error');
            return;
        }
        if (!activeSnapshotId || !selectedSnapshot) {
            setStatus('Choose a snapshot first', 'error');
            return;
        }
        if (!castr) {
            setStatus('Choose a Castr first', 'error');
            return;
        }
        if (!llmPulser) {
            showCastModalError('Choose an active llm_chat pulser first.');
            setStatus('Choose an active llm_chat pulser first', 'error');
            return;
        }

        const personalization = personalizationOverride && typeof personalizationOverride === 'object'
            ? personalizationOverride
            : collectPersonalization(application);

        state.generating = true;
        refs.generateResult.disabled = true;
        refs.castModalSubmit.disabled = true;
        refs.generateResult.textContent = 'Creating My Result...';
        refs.castModalSubmit.textContent = 'Generating Final Result...';
        setStatus('Creating your result...');

        try {
            const response = await fetch('/api/attas/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    application_id: application.phema_id || application.id,
                    application_name: application.name,
                    phema_id: application.phema_id || application.id || '',
                    plaza_url: application.plaza_url,
                    phemar_agent_id: application.host_phemar_agent_id || '',
                    phemar_name: application.host_phemar_name || '',
                    phemar_plaza_url: application.host_phemar_plaza_url || application.plaza_url || '',
                    phemar_address: application.host_phemar_address || '',
                    castr_agent_id: castr.agent_id,
                    castr_plaza_url: castr.plaza_url,
                    llm_agent_id: llmPulser.agent_id,
                    llm_plaza_url: llmPulser.plaza_url,
                    snapshot_id: activeSnapshotId,
                    params: selectedSnapshot.params && typeof selectedSnapshot.params === 'object'
                        ? selectedSnapshot.params
                        : collectFriendlyParams(application),
                    preferences: {
                        audience: personalization.audience,
                        language: personalization.language,
                        theme: personalization.style,
                    },
                    personalization,
                    use_llm_preprocessor: true,
                    format: refs.renderFormat.value.trim() || castr.media_type || 'PDF',
                    cache_time: Number(refs.cacheTime.value || 0),
                }),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Could not create result');
            }

            state.lastResult = payload;
            recordHistoryEntry({
                application,
                castr,
                llmPulser,
                personalization,
                params: selectedSnapshot.params && typeof selectedSnapshot.params === 'object'
                    ? selectedSnapshot.params
                    : collectFriendlyParams(application),
                result: payload,
                format: refs.renderFormat.value.trim() || castr.media_type || 'PDF',
                cacheTime: Number(refs.cacheTime.value || 0),
                sourceHistoryId,
                snapshotId: activeSnapshotId,
                snapshotMode: 'snapshot',
            });
            renderAll();
            closeCastModal();
            setStatus('Result ready', 'success');
        } catch (error) {
            showCastModalError(error.message || 'Could not create result');
            setStatus(error.message || 'Could not create result', 'error');
        } finally {
            state.generating = false;
            refs.generateResult.disabled = false;
            refs.castModalSubmit.disabled = false;
            refs.castModalSubmit.textContent = 'Generate Final Result';
            renderPrimaryAction();
            if (state.castModalOpen) {
                renderCastModal();
            }
        }
    }

    async function saveCurrentResult() {
        if (!state.lastResult || state.saving) return;
        state.saving = true;
        setStatus('Saving locally...');

        try {
            const title = state.lastResult?.temporary_script?.name
                || state.lastResult?.snapshot?.snapshot?.name
                || state.lastResult?.application?.name
                || 'Saved attas result';
            const response = await fetch('/api/attas/saved_results', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    result: state.lastResult,
                }),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== 'success') {
                throw new Error(payload.detail || payload.message || 'Could not save result');
            }

            await loadSavedResults();
            state.selectedSavedResultId = payload.saved_result.id;
            renderSavedDetail();
            setStatus('Saved locally', 'success');
            switchView('saved-view');
        } catch (error) {
            setStatus(error.message || 'Could not save result', 'error');
        } finally {
            state.saving = false;
        }
    }

    refs.navItems.forEach((item) => {
        item.addEventListener('click', () => {
            switchView(item.dataset.viewTarget);
            if (item.dataset.viewTarget === 'saved-view') {
                loadSavedResults();
            }
            if (item.dataset.viewTarget === 'plazas-view') {
                loadAgentConfigs();
            }
        });
    });

    refs.catalogQuery.addEventListener('input', (event) => {
        state.query = event.target.value.trim();
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(loadCatalog, 220);
    });

    refs.phemaSelect.addEventListener('change', async (event) => {
        state.selectedApplicationKey = event.target.value || '';
        state.snapshots = [];
        state.selectedSnapshotId = '';
        state.selectedSnapshotGroupKey = '';
        state.snapshotMode = 'new';
        syncSelections();
        renderAll();
        await loadSnapshotsForCurrentApplication();
    });

    refs.partyFilter.addEventListener('change', (event) => {
        state.party = event.target.value.trim();
        loadCatalog();
    });

    refs.plazaFilter.addEventListener('change', (event) => {
        state.plazaUrl = event.target.value;
        loadCatalog();
        loadAgentConfigs();
    });

    refs.agentConfigQuery.addEventListener('input', (event) => {
        state.agentConfigQuery = event.target.value.trim();
        window.clearTimeout(agentConfigSearchTimer);
        agentConfigSearchTimer = window.setTimeout(loadAgentConfigs, 220);
    });

    refs.snapshotSearch.addEventListener('input', (event) => {
        state.snapshotSearch = event.target.value.trim();
        renderSnapshotGroupList();
        renderParameterPreview();
        renderPrimaryAction();
    });

    refs.snapshotFilter.addEventListener('change', (event) => {
        state.snapshotFilter = event.target.value || 'all';
        renderSnapshotGroupList();
        renderParameterPreview();
        renderPrimaryAction();
    });

    refs.snapshotGroupSelect.addEventListener('change', (event) => {
        const groups = filteredSnapshotGroups();
        const group = groups.find((entry) => entry.key === String(event.target.value || '')) || null;
        if (!group) {
            state.selectedSnapshotId = '';
            state.selectedSnapshotGroupKey = '';
            state.snapshotMode = 'new';
            renderAll();
            return;
        }
        const snapshot = group.latest || null;
        selectSnapshotMode({ mode: 'snapshot', snapshot, group });
        renderAll();
    });

    refs.snapshotVersionSelect.addEventListener('change', (event) => {
        const groups = filteredSnapshotGroups();
        const group = groups.find((entry) => entry.key === state.selectedSnapshotGroupKey) || groups[0] || null;
        if (!group) return;
        const snapshot = group.history.find((entry) => snapshotRowId(entry) === String(event.target.value || '')) || group.latest || null;
        selectSnapshotMode({ mode: 'snapshot', snapshot, group });
        renderAll();
    });

    refs.castrSelect.addEventListener('change', (event) => {
        state.selectedCastrKey = event.target.value || '';
        const selectedCastr = currentCastr();
        if (selectedCastr) {
            refs.renderFormat.value = selectedCastr.media_type || refs.renderFormat.value || 'PDF';
        }
        renderAll();
    });
    refs.castLlmPulser.addEventListener('change', (event) => {
        state.selectedLlmPulserKey = event.target.value || '';
        if (state.castModalOpen) {
            renderCastModal();
        }
    });

    refs.refreshCatalog.addEventListener('click', loadCatalog);
    refs.refreshSnapshots.addEventListener('click', loadSnapshotsForCurrentApplication);
    refs.refreshSaved.addEventListener('click', loadSavedResults);
    refs.refreshAgentConfigs.addEventListener('click', loadAgentConfigs);
    refs.launchAgentFromUser.addEventListener('click', () => openAgentConfigLaunchPopup(''));
    refs.generateResult.addEventListener('click', async () => {
        state.modalSourceHistoryId = '';
        if (state.snapshotMode === 'snapshot' && state.selectedSnapshotId) {
            openCastModal();
            return;
        }
        openParameterModal();
    });

    refs.closeParameterModal.addEventListener('click', closeParameterModal);
    refs.parameterModalCancel.addEventListener('click', closeParameterModal);
    refs.parameterModalSubmit.addEventListener('click', async () => {
        syncModalDraftFromDom();
        await createSnapshotOnly({ sourceHistoryId: state.modalSourceHistoryId });
    });
    refs.closeCastModal.addEventListener('click', closeCastModal);
    refs.castModalCancel.addEventListener('click', closeCastModal);
    refs.castModalSubmit.addEventListener('click', async () => {
        const personalization = syncCastDraftFromDom();
        await castSelectedSnapshot({
            sourceHistoryId: state.modalSourceHistoryId,
            snapshotId: state.selectedSnapshotId,
            personalizationOverride: personalization,
        });
    });

    document.addEventListener('input', (event) => {
        const target = event.target;
        if (!target.matches('[data-modal-param-name]')) return;
        const application = currentApplication();
        if (!application) return;
        const key = applicationKey(application);
        state.paramValuesByApplication[key] = state.paramValuesByApplication[key] || {};
        state.paramValuesByApplication[key][target.dataset.modalParamName] = target.type === 'checkbox' ? target.checked : target.value;
        renderParameterPreview();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && anyModalOpen()) {
            closeActiveModal();
        }
    });

    document.addEventListener('click', async (event) => {
        if (event.target.closest('[data-close-modal="true"]')) {
            closeActiveModal();
            return;
        }

        const saveButton = event.target.closest('#save-current-result');
        if (saveButton) {
            await saveCurrentResult();
            return;
        }

        const editCurrentButton = event.target.closest('#edit-current-result');
        if (editCurrentButton) {
            state.modalSourceHistoryId = '';
            const currentGroup = selectedSnapshotGroup();
            if (currentGroup) {
                selectSnapshotMode({ mode: 'new', group: currentGroup });
            } else {
                state.selectedSnapshotId = '';
                state.selectedSnapshotGroupKey = '';
                state.snapshotMode = 'new';
            }
            renderAll();
            openParameterModal();
            return;
        }

        const historyAction = event.target.closest('[data-history-action]');
        if (historyAction) {
            const entry = getHistoryEntryById(historyAction.dataset.historyId || '');
            if (!entry) return;

            const ready = await ensureHistorySelection(entry);
            if (!ready) return;

            state.modalSourceHistoryId = entry.id;
            if (historyAction.dataset.historyAction === 'rerun') {
                if (state.selectedSnapshotId) {
                    await castSelectedSnapshot({
                        sourceHistoryId: entry.id,
                        snapshotId: entry.snapshotId || state.selectedSnapshotId,
                        personalizationOverride: entry.personalization || {},
                    });
                } else {
                    await regenerateSnapshotAndResult({
                        sourceHistoryId: entry.id,
                        paramsOverride: entry.params || {},
                        personalizationOverride: entry.personalization || {},
                    });
                }
                return;
            }

            const currentGroup = selectedSnapshotGroup();
            if (currentGroup) {
                selectSnapshotMode({ mode: 'new', group: currentGroup });
            } else {
                state.selectedSnapshotId = '';
                state.selectedSnapshotGroupKey = '';
                state.snapshotMode = 'new';
            }
            renderAll();
            openParameterModal();
            return;
        }

        const snapshotAction = event.target.closest('[data-snapshot-action]');
        if (snapshotAction) {
            const groups = buildSnapshotGroups(state.snapshots);
            const group = groups.find((entry) => entry.key === String(snapshotAction.dataset.groupKey || '')) || null;
            if (snapshotAction.dataset.snapshotAction === 'new-empty') {
                state.selectedSnapshotId = '';
                state.selectedSnapshotGroupKey = '';
                state.snapshotMode = 'new';
                renderAll();
                openParameterModal();
                return;
            }
            if (!group) return;
            const selectedValue = refs.snapshotVersionSelect.value;
            const snapshot = group.history.find((entry) => snapshotRowId(entry) === String(selectedValue || snapshotAction.dataset.snapshotId || '')) || group.latest || null;
            if (snapshotAction.dataset.snapshotAction === 'use-latest' || snapshotAction.dataset.snapshotAction === 'use-version' || snapshotAction.dataset.snapshotAction === 'use-selected') {
                selectSnapshotMode({ mode: 'snapshot', snapshot, group });
                renderAll();
                return;
            }
            if (snapshotAction.dataset.snapshotAction === 'new-from-group') {
                selectSnapshotMode({ mode: 'new', group });
                renderAll();
                openParameterModal();
                return;
            }
        }

        const savedCard = event.target.closest('[data-card-type="saved"]');
        if (savedCard) {
            state.selectedSavedResultId = savedCard.dataset.savedId || '';
            renderSavedList();
            renderSavedDetail();
            return;
        }

        const plazaCard = event.target.closest('[data-card-type="plaza"]');
        if (plazaCard) {
            const nextPlaza = plazaCard.dataset.plazaUrl || '';
            state.plazaUrl = state.plazaUrl === nextPlaza ? '' : nextPlaza;
            refs.plazaFilter.value = state.plazaUrl;
            await loadCatalog();
            await loadAgentConfigs();
            return;
        }

        const launchAgentConfigButton = event.target.closest('[data-launch-agent-config]');
        if (launchAgentConfigButton) {
            openAgentConfigLaunchPopup(launchAgentConfigButton.dataset.launchAgentConfig || '');
        }
    });

    window.addEventListener('message', (event) => {
        if (event.origin !== window.location.origin) return;
        if (event.data?.type !== 'user-agent-config-launch') return;
        loadAgentConfigs();
        loadCatalog();
        const launch = event.data.launch && typeof event.data.launch === 'object' ? event.data.launch : {};
        const statusLabel = launch.status === 'already_running' ? 'Agent already running on plaza' : 'Agent launch reported healthy';
        setStatus(statusLabel, 'success');
    });

    refs.plazaFilter.innerHTML = `
        <option value="">All Plazas</option>
        ${initialPlazas.map((url) => `<option value="${escapeHtml(url)}">${escapeHtml(url)}</option>`).join('')}
    `;

    loadHistoryEntries();
    renderHistoryList();
    loadCatalog();
    loadAgentConfigs();
    loadSavedResults();
});
