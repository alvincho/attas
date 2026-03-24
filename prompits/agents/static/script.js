document.addEventListener('DOMContentLoaded', () => {
    // --- Global Elements ---
    const tickerInput = document.getElementById('ticker-input');
    const fetchBtn = document.getElementById('fetch-btn');
    const emptyState = document.querySelector('.empty-state');
    const stockCard = document.getElementById('stock-card');
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsPanel = document.getElementById('settings-panel');
    const llmProvider = document.getElementById('llm-provider');
    const llmModel = document.getElementById('llm-model');
    const displayTicker = document.getElementById('display-ticker');
    const displayPrice = document.getElementById('display-price');
    const displayChange = document.getElementById('display-change');
    const displayVolume = document.getElementById('display-volume');
    const displayTime = document.getElementById('display-time');
    const displayInsight = document.getElementById('display-insight');
    const refreshInsightBtn = document.getElementById('refresh-insight-btn');

    // --- Template Page Elements ---
    const analystSelect = document.getElementById('analyst-select');
    const savedTemplatesSelect = document.getElementById('saved-templates-select');
    const templatePrompt = document.getElementById('template-prompt');
    const generateBtn = document.getElementById('generate-template-btn');
    const previewContainer = document.getElementById('preview-content');
    const saveActions = document.getElementById('save-actions');
    const saveNameInput = document.getElementById('save-name');
    const saveBtn = document.getElementById('save-template-btn');
    const chatMessages = document.getElementById('template-chat-messages');
    const clearChatBtn = document.getElementById('clear-chat-btn');

    let currentGeneratedTemplate = null;
    let chatHistory = []; // Local history state if needed, though backend handles it too

    // --- Timer Utility ---
    class Timer {
        constructor(duration, onTick, onComplete) {
            this.duration = duration;
            this.remaining = duration;
            this.onTick = onTick;
            this.onComplete = onComplete;
            this.interval = null;
        }

        start() {
            this.stop();
            this.remaining = this.duration;
            this.onTick(this.remaining);
            this.interval = setInterval(() => {
                this.remaining--;
                this.onTick(this.remaining);
                if (this.remaining <= 0) {
                    this.stop();
                    if (this.onComplete) this.onComplete();
                }
            }, 1000);
        }

        stop() {
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
            }
        }
    }

    const MAX_TIME = 240;
    let activeTimers = new Map();

    function startCountdown(buttonId) {
        const btn = document.getElementById(buttonId);
        if (!btn) return;

        const countdownText = btn.querySelector('.countdown-text');
        const loader = btn.querySelector('.loader');

        btn.disabled = true;
        countdownText?.classList.remove('hidden');
        loader?.classList.add('active');

        const timer = new Timer(MAX_TIME, (seconds) => {
            if (countdownText) countdownText.textContent = `${seconds}s`;
        }, () => {
            stopCountdown(buttonId);
        });

        timer.start();
        activeTimers.set(buttonId, timer);
    }

    function stopCountdown(buttonId) {
        const btn = document.getElementById(buttonId);
        if (!btn) return;

        const countdownText = btn.querySelector('.countdown-text');

        btn.disabled = false;
        countdownText?.classList.add('hidden');

        const timer = activeTimers.get(buttonId);
        if (timer) {
            timer.stop();
            activeTimers.delete(buttonId);
        }
    }

    // --- Page Navigation ---
    const navLinks = document.querySelectorAll('.nav-links li');
    const pages = document.querySelectorAll('.page');

    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const pageId = link.getAttribute('data-page');
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            pages.forEach(p => p.classList.remove('active'));
            document.getElementById(`${pageId}-page`).classList.add('active');

            if (pageId === 'templates') {
                loadTemplatesPageData();
            } else if (pageId === 'layouts') {
                loadLayouts();
            } else if (pageId === 'pieces') {
                loadPiecesPage();
            }
        });
    });

    // --- Dashboard Logic ---
    settingsToggle?.addEventListener('click', () => {
        settingsPanel.classList.toggle('hidden');
        if (!settingsPanel.classList.contains('hidden')) {
            updateModelDropdown();
        }
    });

    llmProvider?.addEventListener('change', updateModelDropdown);

    async function updateModelDropdown() {
        const provider = llmProvider.value;
        llmModel.innerHTML = '<option value="">Loading models...</option>';
        llmModel.disabled = true;

        try {
            const response = await fetch(`/api/list_models?provider=${provider}`);
            const result = await response.json();
            if (result.status === 'success') {
                llmModel.innerHTML = '';
                result.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    if (provider === 'ollama' && model === 'gemma3:27b') option.selected = true;
                    if (provider === 'openai' && model === 'gpt-4o') option.selected = true;
                    llmModel.appendChild(option);
                });
            } else {
                llmModel.innerHTML = `<option value="">Error: ${result.message}</option>`;
            }
        } catch (error) {
            llmModel.innerHTML = '<option value="">Connection error</option>';
        } finally {
            llmModel.disabled = false;
        }
    }

    async function fetchStockData() {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) return;

        fetchBtn.classList.add('loading');
        startCountdown('fetch-btn');

        try {
            const response = await fetch('/api/fetch_stock', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker })
            });
            const result = await response.json();
            if (result.status === 'success') {
                updateUI(result.data);
                fetchAIInsight(ticker);
            } else {
                alert(result.message || 'Failed to fetch data');
            }
        } catch (error) {
            alert('Error connecting to the agent.');
        } finally {
            fetchBtn.classList.remove('loading');
            stopCountdown('fetch-btn');
        }
    }

    async function fetchAIInsight(ticker) {
        displayInsight.innerHTML = '<div class="insight-placeholder">Analyzing market sentiment...</div>';
        displayInsight.classList.add('insight-loading');

        try {
            const response = await fetch('/api/chat_insight', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker,
                    provider: llmProvider.value,
                    model: llmModel.value
                })
            });
            const result = await response.json();
            if (result.status === 'success') {
                displayInsight.textContent = result.response;
            } else {
                displayInsight.textContent = "Error: " + (result.message || "Failed");
            }
        } catch (error) {
            displayInsight.textContent = "Error connecting to AI service.";
        } finally {
            displayInsight.classList.remove('insight-loading');
        }
    }

    function updateUI(data) {
        emptyState.classList.add('hidden');
        stockCard.classList.remove('hidden');
        displayTicker.textContent = data.ticker;
        displayPrice.textContent = data.price.toLocaleString(undefined, { minimumFractionDigits: 2 });
        const changeValue = data.change;
        displayChange.textContent = (changeValue >= 0 ? '+' : '') + changeValue.toFixed(2) + '%';
        displayChange.className = changeValue >= 0 ? 'up' : 'down';
        displayVolume.textContent = data.volume.toLocaleString();
        displayTime.textContent = new Date(data.timestamp).toLocaleTimeString();
    }

    // --- Templates Logic ---
    async function loadTemplatesPageData() {
        fetchAnalysts();
        fetchSavedTemplates();
    }

    async function fetchAnalysts() {
        try {
            const response = await fetch('/api/list_analysts');
            const result = await response.json();
            if (result.status === 'success') {
                analystSelect.innerHTML = result.analysts.length > 0
                    ? result.analysts.map(a => `<option value="${a.name}">${a.name}</option>`).join('')
                    : '<option value="">No analysts found</option>';
            }
        } catch (e) { console.error('Error fetching analysts:', e); }
    }

    async function fetchSavedTemplates() {
        try {
            const response = await fetch('/api/list_templates');
            const result = await response.json();
            if (result.status === 'success') {
                savedTemplatesSelect.innerHTML = '<option value="">Select a template...</option>' +
                    result.templates.map(t => `<option value="${t.name}">${t.name}</option>`).join('');
            }
        } catch (e) { console.error('Error fetching templates:', e); }
    }

    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `<p>${text}</p>`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function mergeTemplates(newTemplate) {
        if (!newTemplate) return;
        if (!currentGeneratedTemplate || !currentGeneratedTemplate.blocks) {
            currentGeneratedTemplate = newTemplate;
            if (!currentGeneratedTemplate.blocks) currentGeneratedTemplate.blocks = [];
            return;
        }

        // Keep report title if it matches or if new one is generic
        if (newTemplate.report_title && newTemplate.report_title !== "Report Template") {
            currentGeneratedTemplate.report_title = newTemplate.report_title;
        }

        const existingBlocks = currentGeneratedTemplate.blocks;
        const newBlocks = Array.isArray(newTemplate.blocks) ? newTemplate.blocks : [];

        // Merging by UUID or Name
        newBlocks.forEach(newBlock => {
            if (!newBlock || !newBlock.name) return; // Skip invalid blocks

            const index = existingBlocks.findIndex(b =>
                (b.uuid && newBlock.uuid && b.uuid === newBlock.uuid) ||
                (b.name && b.name.toLowerCase() === newBlock.name.toLowerCase())
            );

            if (index !== -1) {
                // Update existing block while preserving state
                existingBlocks[index] = { ...existingBlocks[index], ...newBlock };
            } else {
                // Append new block
                existingBlocks.push(newBlock);
            }
        });
    }

    async function sendChatPrompt(reset = false) {
        const prompt = templatePrompt.value.trim();
        const analystName = analystSelect.value;
        if (!prompt && !reset) return;
        if (!analystName) return alert('Please select an analyst');

        if (!reset) {
            appendMessage('user', prompt);
            templatePrompt.value = '';
        }

        startCountdown('generate-template-btn');

        try {
            const response = await fetch('/api/suggest_template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, analyst_name: analystName, reset })
            });
            const result = await response.json();
            if (result.status === 'success') {
                appendMessage('assistant', result.analysis);
                if (result.template) {
                    mergeTemplates(result.template);
                    renderTemplatePreview(currentGeneratedTemplate);
                    saveActions.classList.remove('hidden');
                }
            } else {
                appendMessage('assistant', `Error: ${result.message}`);
            }
        } catch (e) {
            appendMessage('assistant', 'Connection error');
        } finally {
            stopCountdown('generate-template-btn');
        }
    }

    generateBtn?.addEventListener('click', () => sendChatPrompt(false));
    templatePrompt?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatPrompt(false);
    });

    clearChatBtn?.addEventListener('click', () => {
        chatMessages.innerHTML = '<div class="message assistant"><p>Session reset. How can I help with your report template?</p></div>';
        currentGeneratedTemplate = null;
        previewContainer.innerHTML = '<div class="empty-preview"><span class="icon-reports"></span><p>Select or generate a template to preview</p></div>';
        saveActions.classList.add('hidden');
        sendChatPrompt(true); // Tell backend to reset
    });

    analystSelect?.addEventListener('change', () => {
        // Auto-reset when changing analyst
        chatMessages.innerHTML = `<div class="message assistant"><p>Connected to ${analystSelect.value}. Tell me what kind of report you need.</p></div>`;
        sendChatPrompt(true);
    });

    function renderTemplatePreview(template) {
        if (!template) return;
        const title = template.report_title || 'Untitled Report';
        let html = `<div class="report-title-preview">${title}</div>`;

        if (Array.isArray(template.blocks)) {
            template.blocks.forEach((block, index) => {
                if (!block) return;
                const blockId = block.uuid || block.id || `piece-${index}`;
                const blockName = block.name || block.title || 'Untitled Piece';
                const blockDesc = block.description || 'No description provided.';
                const displayTypes = Array.isArray(block.recommended_display_types)
                    ? block.recommended_display_types.join(', ')
                    : (block.suggested_presence || 'text');

                html += `
                    <div class="block-preview" data-id="${blockId}">
                        <div class="block-header">
                            <h4>${blockName}</h4>
                            <div class="block-actions">
                                <span class="block-type">${displayTypes}</span>
                                <button class="save-as-piece-btn" data-block-index="${index}" title="Save as Piece">💾</button>
                                <button class="remove-block-btn" title="Remove Piece">✕</button>
                            </div>
                        </div>
                        <div class="block-desc">${blockDesc}</div>
                        ${block.detail_of_processing ? `<div class="block-hint">Algorithm: ${block.detail_of_processing}</div>` : ''}
                        ${block.data_source_hint ? `<div class="block-hint">Source: ${block.data_source_hint}</div>` : ''}
                    </div>
                `;
            });
        }
        previewContainer.innerHTML = html;
    }

    // Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const simulationContainer = document.getElementById('simulation-container');
    const simulationControls = document.getElementById('simulation-controls');
    const regenerateSimBtn = document.getElementById('regenerate-sim-btn');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');

            tabBtns.forEach(b => b.classList.toggle('active', b === btn));
            tabPanes.forEach(p => p.classList.toggle('active', p.getAttribute('data-pane') === target));

            if (target === 'simulation') {
                simulationControls.classList.remove('hidden');
                if (currentGeneratedTemplate && !currentGeneratedTemplate.simulation) {
                    fetchSimulation();
                } else if (currentGeneratedTemplate?.simulation) {
                    renderSimulatedReport(currentGeneratedTemplate.simulation);
                }
            } else {
                simulationControls.classList.add('hidden');
            }
        });
    });

    regenerateSimBtn?.addEventListener('click', () => {
        if (currentGeneratedTemplate) {
            fetchSimulation();
        }
    });

    async function fetchSimulation() {
        const analystName = analystSelect.value;
        if (!analystName || !currentGeneratedTemplate) return;

        simulationContainer.innerHTML = '<div class="empty-preview"><span class="loader"></span><p>Generating simulation...</p></div>';

        try {
            const response = await fetch('/api/simulate_report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ template: currentGeneratedTemplate, analyst_name: analystName })
            });
            const result = await response.json();
            if (result.status === 'success') {
                currentGeneratedTemplate.simulation = result.simulation;
                renderSimulatedReport(result.simulation);
            }
        } catch (err) {
            simulationContainer.innerHTML = '<div class="empty-preview"><p>Connection error</p></div>';
        }
    }

    let chartInstances = [];

    function renderSimulatedReport(simulation) {
        if (!simulation || !simulation.blocks) return;

        // Cleanup old charts
        chartInstances.forEach(c => c.destroy());
        chartInstances = [];

        let html = `<div class="report-title-preview">${simulation.report_title || 'Simulation'}</div>`;

        simulation.blocks.forEach((block, index) => {
            html += `<div class="sim-block">`;
            html += `<h3>${block.name || block.title}</h3>`;

            const type = (block.type || 'text').toLowerCase();
            const content = block.content || {};

            if (type === 'chart') {
                const chartId = `sim-chart-${index}`;
                html += `<div class="sim-chart-container"><canvas id="${chartId}"></canvas></div>`;
            } else if (type === 'table') {
                html += `<table class="sim-table">`;
                const rows = Array.isArray(content.rows) ? content.rows : [];
                if (rows.length > 0) {
                    html += `<thead><tr>`;
                    Object.keys(rows[0]).forEach(key => html += `<th>${key}</th>`);
                    html += `</tr></thead><tbody>`;
                    rows.forEach(row => {
                        html += `<tr>`;
                        Object.values(row).forEach(val => html += `<td>${val}</td>`);
                        html += `</tr>`;
                    });
                    html += `</tbody>`;
                }
                html += `</table>`;
            } else if (type === 'list') {
                const items = Array.isArray(content.items) ? content.items : [];
                html += `<ul class="sim-list">`;
                items.forEach(item => html += `<li>${item}</li>`);
                html += `</ul>`;
            } else {
                html += `<div class="sim-text">${content.text || content}</div>`;
            }

            html += `</div>`;
        });

        simulationContainer.innerHTML = html;

        // Initialize Charts after DOM updated
        simulation.blocks.forEach((block, index) => {
            if (block.type.toLowerCase() === 'chart' && block.content && block.content.data) {
                const ctx = document.getElementById(`sim-chart-${index}`);
                if (ctx) {
                    const labels = block.content.data.map(d => d.label);
                    const values = block.content.data.map(d => d.value);

                    const chart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: block.name || block.title,
                                data: values,
                                backgroundColor: 'rgba(99, 102, 241, 0.5)',
                                borderColor: 'rgb(99, 102, 241)',
                                borderWidth: 2,
                                borderRadius: 5
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' } },
                                x: { grid: { display: false } }
                            }
                        }
                    });
                    chartInstances.push(chart);
                }
            }
        });
    }

    previewContainer?.addEventListener('click', async (e) => {
        if (e.target.classList.contains('remove-block-btn')) {
            const blockDiv = e.target.closest('.block-preview');
            const blockId = blockDiv.getAttribute('data-id');
            const analystName = analystSelect.value;

            if (!blockId || !analystName) return;

            // Optimistic UI removal
            blockDiv.style.opacity = '0.5';
            blockDiv.style.pointerEvents = 'none';

            try {
                const response = await fetch('/api/remove_block', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ block_id: blockId, analyst_name: analystName })
                });
                const result = await response.json();
                console.log('Remove Block Result:', result);
                if (result && result.status === 'success') {
                    currentGeneratedTemplate = result.template;
                    renderTemplatePreview(result.template);
                    appendMessage('assistant', `Block removed. Session updated.`);
                } else {
                    const errorMsg = (result && (result.message || result.detail)) || 'Unknown analyst error';
                    alert('Failed to remove block: ' + errorMsg);
                    blockDiv.style.opacity = '1';
                    blockDiv.style.pointerEvents = 'auto';
                }
            } catch (err) {
                alert('Connection error');
                blockDiv.style.opacity = '1';
                blockDiv.style.pointerEvents = 'auto';
            }
        }
    });

    saveBtn?.addEventListener('click', async () => {
        const name = saveNameInput.value.trim();
        if (!name || !currentGeneratedTemplate) return alert('Please enter a name');

        try {
            const response = await fetch('/api/save_template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, template: currentGeneratedTemplate })
            });
            const result = await response.json();
            if (result.status === 'success') {
                alert('Template saved!');
                saveActions.classList.add('hidden');
                saveNameInput.value = '';
                fetchSavedTemplates();
            } else {
                alert('Save failed: ' + result.message);
            }
        } catch (e) { alert('Connection error'); }
    });

    savedTemplatesSelect?.addEventListener('change', async (e) => {
        const name = e.target.value;
        if (!name) return;
        try {
            const response = await fetch('/api/list_templates');
            const result = await response.json();
            const template = result.templates.find(t => t.name === name);
            if (template) {
                currentGeneratedTemplate = template.content;
                renderTemplatePreview(template.content);
                saveActions.classList.add('hidden');
            }
        } catch (e) { console.error('Error loading template:', e); }
    });

    // --- Layout Management ---
    let currentLayout = null;
    let availablePieces = [];
    let selectedLayoutItem = null;

    async function loadLayouts() {
        try {
            const response = await fetch('/api/layouts');
            const result = await response.json();
            if (result.status === 'success') {
                renderLayoutsGrid(result.layouts);
            }
        } catch (e) {
            console.error('Error loading layouts:', e);
        }
    }

    function renderLayoutsGrid(layouts) {
        const grid = document.getElementById('layouts-grid');
        if (!grid) return;

        if (layouts.length === 0) {
            grid.innerHTML = '<div class="empty-state"><p>No layouts yet. Create your first layout!</p></div>';
            return;
        }

        grid.innerHTML = layouts.map(layout => `
            <div class="layout-card" data-uuid="${layout.uuid}">
                <div class="layout-card-header">
                    <h3>${layout.name || 'Untitled Layout'}</h3>
                    <div class="layout-card-actions">
                        <button class="icon-btn edit-layout" data-uuid="${layout.uuid}" title="Edit">
                            <span class="icon-edit"></span>
                        </button>
                        <button class="icon-btn delete-layout" data-uuid="${layout.uuid}" title="Delete">
                            <span class="icon-delete"></span>
                        </button>
                    </div>
                </div>
                <div class="layout-card-body">
                    <p class="layout-item-count">${layout.items?.length || 0} pieces</p>
                    <div class="layout-preview">
                        ${renderLayoutPreview(layout)}
                    </div>
                </div>
            </div>
        `).join('');

        // Attach event listeners
        grid.querySelectorAll('.edit-layout').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const uuid = e.currentTarget.dataset.uuid;
                openLayoutEditor(uuid);
            });
        });

        grid.querySelectorAll('.delete-layout').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const uuid = e.currentTarget.dataset.uuid;
                if (confirm('Are you sure you want to delete this layout?')) {
                    await deleteLayout(uuid);
                }
            });
        });
    }

    function renderLayoutPreview(layout) {
        if (!layout.items || layout.items.length === 0) {
            return '<p class="preview-empty">Empty layout</p>';
        }
        return layout.items.slice(0, 3).map(item =>
            `<div class="preview-item">${item.order}</div>`
        ).join('');
    }

    async function openLayoutEditor(uuid = null) {
        const modal = document.getElementById('layout-editor-modal');
        const canvas = document.getElementById('layout-canvas');
        const nameInput = document.getElementById('layout-name-input');

        // Load pieces
        await loadPieces();

        if (uuid) {
            // Load existing layout
            try {
                const response = await fetch(`/api/layout/${uuid}`);
                const result = await response.json();
                if (result.status === 'success') {
                    currentLayout = result.layout;
                    nameInput.value = currentLayout.name || '';
                    renderLayoutCanvas(currentLayout);
                }
            } catch (e) {
                console.error('Error loading layout:', e);
            }
        } else {
            // Create new layout
            currentLayout = {
                uuid: generateUUID(),
                name: '',
                items: []
            };
            nameInput.value = '';
            canvas.innerHTML = '';
        }

        modal.classList.add('show');
    }

    async function loadPieces() {
        try {
            const response = await fetch('/api/pieces');
            const result = await response.json();
            if (result.status === 'success') {
                availablePieces = result.pieces;
                renderPiecesLibrary(result.pieces);
            }
        } catch (e) {
            console.error('Error loading pieces:', e);
        }
    }

    function renderPiecesLibrary(pieces) {
        const library = document.getElementById('pieces-library');
        if (!library) return;

        library.innerHTML = pieces.map(piece => `
            <div class="piece-item" draggable="true" data-piece-uuid="${piece.uuid}">
                <div class="piece-icon"></div>
                <div class="piece-info">
                    <h4>${piece.name}</h4>
                    <p>${piece.description}</p>
                </div>
            </div>
        `).join('');

        // Add drag event listeners
        library.querySelectorAll('.piece-item').forEach(item => {
            item.addEventListener('dragstart', handlePieceDragStart);
        });
    }

    function renderLayoutCanvas(layout) {
        const canvas = document.getElementById('layout-canvas');
        if (!canvas) return;

        canvas.innerHTML = layout.items.map((item, index) => `
            <div class="layout-item" data-index="${index}" data-piece-uuid="${item.piece_uuid}"
                 style="order: ${item.order}; width: ${item.width || '100%'}; height: ${item.height || 'auto'};">
                <div class="layout-item-header">
                    <span>${getPieceName(item.piece_uuid)}</span>
                    <button class="remove-item" data-index="${index}">&times;</button>
                </div>
                <div class="layout-item-body">
                    Order: ${item.order} | Width: ${item.width || '100%'}
                </div>
            </div>
        `).join('');

        // Add event listeners
        canvas.querySelectorAll('.layout-item').forEach(item => {
            item.addEventListener('click', () => selectLayoutItem(item));
        });

        canvas.querySelectorAll('.remove-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(e.currentTarget.dataset.index);
                removeLayoutItem(index);
            });
        });
    }

    function getPieceName(uuid) {
        const piece = availablePieces.find(p => p.uuid === uuid);
        return piece ? piece.name : 'Unknown Piece';
    }

    function handlePieceDragStart(e) {
        e.dataTransfer.setData('piece-uuid', e.currentTarget.dataset.pieceUuid);
    }

    function selectLayoutItem(itemElement) {
        document.querySelectorAll('.layout-item').forEach(el => el.classList.remove('selected'));
        itemElement.classList.add('selected');

        const index = parseInt(itemElement.dataset.index);
        selectedLayoutItem = currentLayout.items[index];
        renderPropertiesPanel(selectedLayoutItem, index);
    }

    function renderPropertiesPanel(item, index) {
        const panel = document.getElementById('properties-panel');
        if (!panel) return;

        panel.innerHTML = `
            <div class="property-group">
                <label>Order</label>
                <input type="number" id="prop-order" value="${item.order}" min="0">
            </div>
            <div class="property-group">
                <label>Width</label>
                <input type="text" id="prop-width" value="${item.width || '100%'}">
            </div>
            <div class="property-group">
                <label>Height</label>
                <input type="text" id="prop-height" value="${item.height || 'auto'}">
            </div>
            <div class="property-group">
                <label>X Position</label>
                <input type="number" id="prop-x" value="${item.x || 0}">
            </div>
            <div class="property-group">
                <label>Y Position</label>
                <input type="number" id="prop-y" value="${item.y || 0}">
            </div>
            <button id="apply-properties" class="primary-btn">Apply</button>
        `;

        document.getElementById('apply-properties').addEventListener('click', () => {
            currentLayout.items[index].order = parseInt(document.getElementById('prop-order').value);
            currentLayout.items[index].width = document.getElementById('prop-width').value;
            currentLayout.items[index].height = document.getElementById('prop-height').value;
            currentLayout.items[index].x = parseInt(document.getElementById('prop-x').value) || null;
            currentLayout.items[index].y = parseInt(document.getElementById('prop-y').value) || null;
            renderLayoutCanvas(currentLayout);
        });
    }

    function removeLayoutItem(index) {
        currentLayout.items.splice(index, 1);
        renderLayoutCanvas(currentLayout);
        document.getElementById('properties-panel').innerHTML = '<p class="placeholder-text">Select an item to edit properties</p>';
    }

    async function saveLayout() {
        const nameInput = document.getElementById('layout-name-input');
        currentLayout.name = nameInput.value || 'Untitled Layout';

        try {
            const response = await fetch('/api/layout/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ layout: currentLayout })
            });
            const result = await response.json();
            if (result.status === 'success') {
                alert('Layout saved successfully!');
                closeLayoutEditor();
                loadLayouts();
            } else {
                alert('Error: ' + result.message);
            }
        } catch (e) {
            console.error('Error saving layout:', e);
            alert('Failed to save layout');
        }
    }

    async function deleteLayout(uuid) {
        try {
            const response = await fetch(`/api/layout/${uuid}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.status === 'success') {
                loadLayouts();
            } else {
                alert('Error: ' + result.message);
            }
        } catch (e) {
            console.error('Error deleting layout:', e);
        }
    }

    function closeLayoutEditor() {
        document.getElementById('layout-editor-modal').classList.remove('show');
        currentLayout = null;
        selectedLayoutItem = null;
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Layout page event listeners
    document.getElementById('create-layout-btn')?.addEventListener('click', () => openLayoutEditor());
    document.getElementById('save-layout-btn')?.addEventListener('click', saveLayout);
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', closeLayoutEditor);
    });

    // Canvas drop zone
    const canvas = document.getElementById('layout-canvas');
    if (canvas) {
        canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            canvas.classList.add('drag-over');
        });

        canvas.addEventListener('dragleave', () => {
            canvas.classList.remove('drag-over');
        });

        canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            canvas.classList.remove('drag-over');

            const pieceUuid = e.dataTransfer.getData('piece-uuid');
            if (pieceUuid && currentLayout) {
                const newItem = {
                    piece_uuid: pieceUuid,
                    order: currentLayout.items.length,
                    width: '100%',
                    height: 'auto',
                    x: null,
                    y: null,
                    style: {}
                };
                currentLayout.items.push(newItem);
                renderLayoutCanvas(currentLayout);
            }
        });
    }

    // Grid toggle
    document.getElementById('toggle-grid-btn')?.addEventListener('click', () => {
        canvas?.classList.toggle('show-grid');
    });

    // Layout search
    document.getElementById('layout-search')?.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        document.querySelectorAll('.layout-card').forEach(card => {
            const name = card.querySelector('h3').textContent.toLowerCase();
            card.style.display = name.includes(searchTerm) ? 'block' : 'none';
        });
    });

    // --- Piece Management ---
    let currentPiece = null;
    let allPieces = [];

    async function loadPiecesPage() {
        try {
            const response = await fetch('/api/pieces');
            const result = await response.json();
            if (result.status === 'success') {
                allPieces = result.pieces;
                renderPiecesGrid(result.pieces);
            }
        } catch (e) {
            console.error('Error loading pieces:', e);
        }
    }

    function renderPiecesGrid(pieces) {
        const grid = document.getElementById('pieces-grid');
        if (!grid) return;

        if (pieces.length === 0) {
            grid.innerHTML = '<div class="empty-state"><p>No pieces yet. Create your first piece!</p></div>';
            return;
        }

        grid.innerHTML = pieces.map(piece => `
            <div class="piece-card" data-uuid="${piece.uuid}">
                <div class="piece-card-header">
                    <h3>${piece.name || 'Untitled Piece'}</h3>
                    <div class="piece-card-actions">
                        <button class="icon-btn edit-piece" data-uuid="${piece.uuid}" title="Edit">
                            <span class="icon-edit"></span>
                        </button>
                        <button class="icon-btn delete-piece" data-uuid="${piece.uuid}" title="Delete">
                            <span class="icon-delete"></span>
                        </button>
                    </div>
                </div>
                <div class="piece-card-body">
                    <p class="piece-description">${piece.description || 'No description'}</p>
                    <div class="piece-meta">
                        <span class="piece-display-types">${(piece.recommended_display_types || []).join(', ')}</span>
                    </div>
                </div>
            </div>
        `).join('');

        // Attach event listeners
        grid.querySelectorAll('.edit-piece').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const uuid = e.currentTarget.dataset.uuid;
                openPieceEditor(uuid);
            });
        });

        grid.querySelectorAll('.delete-piece').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const uuid = e.currentTarget.dataset.uuid;
                if (confirm('Are you sure you want to delete this piece?')) {
                    await deletePiece(uuid);
                }
            });
        });
    }

    function openPieceEditor(uuid = null) {
        const modal = document.getElementById('piece-editor-modal');

        if (uuid) {
            // Load existing piece
            const piece = allPieces.find(p => p.uuid === uuid);
            if (piece) {
                currentPiece = piece;
                populatePieceForm(piece);
            }
        } else {
            // Create new piece
            currentPiece = { uuid: generateUUID() };
            clearPieceForm();
        }

        modal.classList.add('show');
    }

    function populatePieceForm(piece) {
        document.getElementById('piece-name').value = piece.name || '';
        document.getElementById('piece-description').value = piece.description || '';
        document.getElementById('piece-processing').value = piece.detail_of_processing || '';
        document.getElementById('piece-input-schema').value = JSON.stringify(piece.input_schema || {}, null, 2);
        document.getElementById('piece-output-schema').value = JSON.stringify(piece.output_schema || {}, null, 2);
        document.getElementById('piece-example-input').value = JSON.stringify(piece.example_input || {}, null, 2);
        document.getElementById('piece-example-data').value = JSON.stringify(piece.example_data || {}, null, 2);

        // Set display types
        document.querySelectorAll('.display-type').forEach(cb => {
            cb.checked = (piece.recommended_display_types || []).includes(cb.value);
        });
    }

    function clearPieceForm() {
        document.getElementById('piece-name').value = '';
        document.getElementById('piece-description').value = '';
        document.getElementById('piece-processing').value = '';
        document.getElementById('piece-input-schema').value = '{}';
        document.getElementById('piece-output-schema').value = '{}';
        document.getElementById('piece-example-input').value = '{}';
        document.getElementById('piece-example-data').value = '{}';
        document.querySelectorAll('.display-type').forEach(cb => cb.checked = false);
    }

    async function savePiece() {
        try {
            const piece = {
                uuid: currentPiece.uuid,
                name: document.getElementById('piece-name').value,
                description: document.getElementById('piece-description').value,
                detail_of_processing: document.getElementById('piece-processing').value,
                input_schema: JSON.parse(document.getElementById('piece-input-schema').value || '{}'),
                output_schema: JSON.parse(document.getElementById('piece-output-schema').value || '{}'),
                example_input: JSON.parse(document.getElementById('piece-example-input').value || '{}'),
                example_data: JSON.parse(document.getElementById('piece-example-data').value || '{}'),
                recommended_display_types: Array.from(document.querySelectorAll('.display-type:checked')).map(cb => cb.value)
            };

            if (!piece.name || !piece.description || !piece.detail_of_processing) {
                alert('Please fill in all required fields (Name, Description, Detail of Processing)');
                return;
            }

            const response = await fetch('/api/piece/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ piece })
            });
            const result = await response.json();

            if (result.status === 'success') {
                alert('Piece saved successfully!');
                closePieceEditor();
                loadPiecesPage();
            } else {
                alert('Error: ' + result.message);
            }
        } catch (e) {
            console.error('Error saving piece:', e);
            alert('Failed to save piece: ' + e.message);
        }
    }

    async function deletePiece(uuid) {
        try {
            const response = await fetch(`/api/piece/${uuid}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.status === 'success') {
                loadPiecesPage();
            } else {
                alert('Error: ' + result.message);
            }
        } catch (e) {
            console.error('Error deleting piece:', e);
        }
    }

    function closePieceEditor() {
        document.getElementById('piece-editor-modal').classList.remove('show');
        currentPiece = null;
    }

    // Save template block as piece
    async function saveBlockAsPiece(blockIndex) {
        if (!currentGeneratedTemplate || !currentGeneratedTemplate.blocks) return;

        const block = currentGeneratedTemplate.blocks[blockIndex];
        if (!block) return;

        // Pre-populate piece editor with block data
        currentPiece = {
            uuid: generateUUID(),
            name: block.name || block.title || 'Untitled Piece',
            description: block.description || '',
            detail_of_processing: block.detail_of_processing || '',
            input_schema: block.input_schema || {},
            output_schema: block.output_schema || {},
            example_input: block.example_input || {},
            example_data: block.example_data || {},
            recommended_display_types: block.recommended_display_types || ['text']
        };

        populatePieceForm(currentPiece);
        document.getElementById('piece-editor-modal').classList.add('show');
    }

    // Event listeners for pieces page
    document.getElementById('create-piece-btn')?.addEventListener('click', () => openPieceEditor());
    document.getElementById('save-piece-btn')?.addEventListener('click', savePiece);
    document.querySelectorAll('.close-piece-modal').forEach(btn => {
        btn.addEventListener('click', closePieceEditor);
    });

    // Piece search
    document.getElementById('piece-search')?.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        document.querySelectorAll('.piece-card').forEach(card => {
            const name = card.querySelector('h3').textContent.toLowerCase();
            const desc = card.querySelector('.piece-description').textContent.toLowerCase();
            card.style.display = (name.includes(searchTerm) || desc.includes(searchTerm)) ? 'block' : 'none';
        });
    });

    // Save as piece button handler (delegated)
    previewContainer?.addEventListener('click', (e) => {
        if (e.target.classList.contains('save-as-piece-btn')) {
            const blockIndex = parseInt(e.target.dataset.blockIndex);
            saveBlockAsPiece(blockIndex);
        }
    });

    // --- Init ---
    fetchBtn?.addEventListener('click', fetchStockData);
    refreshInsightBtn?.addEventListener('click', () => {
        const ticker = displayTicker.textContent;
        if (ticker && ticker !== '--') {
            fetchAIInsight(ticker);
        }
    });
    tickerInput?.addEventListener('keypress', (e) => { if (e.key === 'Enter') fetchStockData(); });
});
