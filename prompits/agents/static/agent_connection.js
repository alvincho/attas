(function () {
    function byId(id) {
        return id ? document.getElementById(id) : null;
    }

    function resolveNode(target) {
        if (!target) return null;
        if (typeof target === 'string') return document.querySelector(target);
        if (target && target.nodeType === 1) return target;
        return null;
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

    function normalizeStatus(payload) {
        const raw = String(payload?.connection_status || '').trim().toLowerCase();
        if (raw === 'connected' || raw === 'disconnected' || raw === 'not_configured') {
            return raw;
        }
        if (!String(payload?.plaza_url || '').trim()) {
            return 'not_configured';
        }
        return 'disconnected';
    }

    function statusLabel(status) {
        if (status === 'connected') return 'Connected';
        if (status === 'not_configured') return 'No Plaza';
        return 'Disconnected';
    }

    function metaText(payload, status) {
        const plazaLabel = String(payload?.plaza_name || payload?.plaza_url || '').trim();
        if (status === 'not_configured') {
            return 'Local only';
        }
        return plazaLabel || 'No plaza';
    }

    function detailText(payload, status) {
        const plazaUrl = String(payload?.plaza_url || '').trim();
        const agentName = String(payload?.agent_name || 'This agent').trim();
        const heartbeatAge = formatHeartbeatAge(payload?.last_active);
        const error = String(payload?.error || '').trim();

        if (status === 'connected') {
            return `Connected to ${plazaUrl} as ${agentName}. Last heartbeat ${heartbeatAge} ago.`;
        }
        if (status === 'not_configured') {
            return 'This agent is running without a connected plaza.';
        }
        if (Number(payload?.last_active || 0) > 0) {
            return error || `Disconnected from ${plazaUrl}. Heartbeat lost ${heartbeatAge} ago.`;
        }
        return error || `Disconnected from ${plazaUrl}. No heartbeat has been reported yet.`;
    }

    function render(payload, refs) {
        const status = normalizeStatus(payload);
        if (refs.pill) {
            refs.pill.textContent = statusLabel(status);
            refs.pill.className = `agent-plaza-pill agent-plaza-pill-${status}`;
        }
        if (refs.meta) {
            refs.meta.textContent = metaText(payload, status);
        }
        if (refs.note) {
            refs.note.textContent = detailText(payload, status);
        }
    }

    function mount(options = {}) {
        const refs = {
            pill: byId(options.pillId || 'agent-plaza-pill'),
            meta: byId(options.metaId || 'agent-plaza-meta'),
            note: byId(options.noteId || 'agent-plaza-note'),
        };
        if (!refs.pill && !refs.meta && !refs.note) {
            return null;
        }

        const endpoint = options.endpoint || '/api/plaza_connection_status';
        const pollMs = Math.max(Number(options.pollMs || 15000), 5000);

        async function refresh() {
            try {
                const response = await fetch(endpoint);
                const payload = await response.json();
                if (!response.ok || !payload || payload.status !== 'success') {
                    throw new Error(payload?.detail || payload?.message || 'Failed to load plaza connection');
                }
                render(payload, refs);
            } catch (error) {
                render(
                    {
                        plaza_url: '',
                        agent_name: '',
                        agent_id: '',
                        last_active: 0,
                        connection_status: 'disconnected',
                        error: error.message || 'Failed to load plaza connection',
                    },
                    refs,
                );
            }
        }

        refresh();
        const timer = window.setInterval(refresh, pollMs);
        window.addEventListener(
            'beforeunload',
            () => {
                window.clearInterval(timer);
            },
            { once: true },
        );
        return { refresh };
    }

    function mountStickyHeader(options = {}) {
        const header = resolveNode(options.target || options.selector);
        if (!header) {
            return null;
        }

        const activeClass = String(options.activeClass || 'is-sticky').trim() || 'is-sticky';
        const topOffset = Math.max(Number(options.topOffset ?? 12), 0);
        let rafId = 0;

        function refresh() {
            rafId = 0;
            const isSticky = window.scrollY > 0 && header.getBoundingClientRect().top <= topOffset + 1;
            header.classList.toggle(activeClass, isSticky);
        }

        function scheduleRefresh() {
            if (rafId) return;
            rafId = window.requestAnimationFrame(refresh);
        }

        function destroy() {
            if (rafId) {
                window.cancelAnimationFrame(rafId);
                rafId = 0;
            }
            window.removeEventListener('scroll', scheduleRefresh);
            window.removeEventListener('resize', scheduleRefresh);
        }

        refresh();
        window.addEventListener('scroll', scheduleRefresh, { passive: true });
        window.addEventListener('resize', scheduleRefresh);
        window.addEventListener('beforeunload', destroy, { once: true });
        return { refresh, destroy };
    }

    window.agentConnection = { mount, mountStickyHeader };
})();
