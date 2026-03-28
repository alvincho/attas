(function () {
    const STORAGE_KEY = "attas-ui-preferences:v1";

    const THEMES = {
        paper: {
            label: "Enterprise",
            description: "Clean professional studio surfaces.",
            vars: {
                "--ui-theme-name": "Enterprise",
                "--ui-canvas": "#f8fafc",
                "--ui-canvas-glow-a": "rgba(148, 163, 184, 0.05)",
                "--ui-canvas-glow-b": "rgba(148, 163, 184, 0.05)",
                "--ui-panel": "#ffffff",
                "--ui-panel-strong": "#ffffff",
                "--ui-panel-soft": "#f1f5f9",
                "--ui-border": "#e2e8f0",
                "--ui-border-strong": "#cbd5e1",
                "--ui-text-primary": "#0f172a",
                "--ui-text-secondary": "#475569",
                "--ui-text-faint": "#94a3b8",
                "--ui-sidebar": "#1e293b",
                "--ui-sidebar-soft": "rgba(255, 255, 255, 0.05)",
                "--ui-shadow": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)"
            }
        },
        graphite: {
            label: "Graphite",
            description: "Neutral studio palette with softer light.",
            vars: {
                "--ui-theme-name": "Graphite",
                "--ui-canvas": "linear-gradient(180deg, #eceff3 0%, #dfe5eb 100%)",
                "--ui-canvas-glow-a": "rgba(51, 94, 201, 0.11)",
                "--ui-canvas-glow-b": "rgba(110, 124, 146, 0.12)",
                "--ui-panel": "rgba(250, 252, 255, 0.76)",
                "--ui-panel-strong": "rgba(255, 255, 255, 0.92)",
                "--ui-panel-soft": "rgba(247, 249, 252, 0.58)",
                "--ui-border": "rgba(41, 52, 68, 0.11)",
                "--ui-border-strong": "rgba(41, 52, 68, 0.2)",
                "--ui-text-primary": "#222d39",
                "--ui-text-secondary": "#677384",
                "--ui-text-faint": "#8f99a8",
                "--ui-sidebar": "rgba(33, 39, 48, 0.95)",
                "--ui-sidebar-soft": "rgba(255, 255, 255, 0.08)",
                "--ui-shadow": "0 28px 84px rgba(32, 38, 46, 0.16)"
            }
        },
        midnight: {
            label: "Midnight",
            description: "Dark surfaces for low-glare focused work.",
            vars: {
                "--ui-theme-name": "Midnight",
                "--ui-canvas": "linear-gradient(180deg, #10151c 0%, #161d27 100%)",
                "--ui-canvas-glow-a": "rgba(64, 112, 226, 0.24)",
                "--ui-canvas-glow-b": "rgba(28, 173, 155, 0.14)",
                "--ui-panel": "rgba(20, 26, 35, 0.78)",
                "--ui-panel-strong": "rgba(27, 34, 45, 0.94)",
                "--ui-panel-soft": "rgba(25, 32, 43, 0.58)",
                "--ui-border": "rgba(255, 255, 255, 0.08)",
                "--ui-border-strong": "rgba(255, 255, 255, 0.16)",
                "--ui-text-primary": "#eef2f8",
                "--ui-text-secondary": "#b5c0d0",
                "--ui-text-faint": "#8a97aa",
                "--ui-sidebar": "rgba(10, 13, 18, 0.97)",
                "--ui-sidebar-soft": "rgba(255, 255, 255, 0.06)",
                "--ui-shadow": "0 32px 90px rgba(0, 0, 0, 0.34)"
            }
        }
    };

    const ACCENTS = {
        slate: {
            label: "Slate",
            accent: "#0f172a",
            strong: "#020617",
            soft: "rgba(15, 23, 42, 0.08)",
            rgb: "15, 23, 42",
            support: "#475569"
        },
        indigo: {
            label: "Indigo",
            accent: "#4f46e5",
            strong: "#4338ca",
            soft: "rgba(79, 70, 229, 0.12)",
            rgb: "79, 70, 229",
            support: "#6366f1"
        },
        forest: {
            label: "Forest",
            accent: "#166534",
            strong: "#14532d",
            soft: "rgba(22, 101, 52, 0.12)",
            rgb: "22, 101, 52",
            support: "#22c55e"
        },
        crimson: {
            label: "Crimson",
            accent: "#991b1b",
            strong: "#7f1d1d",
            soft: "rgba(153, 27, 27, 0.12)",
            rgb: "153, 27, 27",
            support: "#ef4444"
        },
        cobalt: {
            label: "Cobalt",
            accent: "#1f7aff",
            strong: "#0056d6",
            soft: "rgba(31, 122, 255, 0.12)",
            rgb: "31, 122, 255",
            support: "#63b3ff"
        }
    };

    function safeParse(rawValue) {
        try {
            const parsed = JSON.parse(rawValue || "{}");
            return parsed && typeof parsed === "object" ? parsed : {};
        } catch (error) {
            return {};
        }
    }

    function getStoredPreferences() {
        return safeParse(window.localStorage.getItem(STORAGE_KEY));
    }

    function getPreferences() {
        const stored = getStoredPreferences();
        return {
            theme: THEMES[stored.theme] ? stored.theme : "paper",
            accent: ACCENTS[stored.accent] ? stored.accent : "cobalt"
        };
    }

    function persistPreferences(nextPreferences) {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextPreferences));
    }

    function applyPreferences(nextPreferences) {
        const prefs = {
            theme: THEMES[nextPreferences.theme] ? nextPreferences.theme : "paper",
            accent: ACCENTS[nextPreferences.accent] ? nextPreferences.accent : "cobalt"
        };
        const theme = THEMES[prefs.theme];
        const accent = ACCENTS[prefs.accent];
        const root = document.documentElement;
        const target = document.body || root;

        Object.entries(theme.vars).forEach(([key, value]) => root.style.setProperty(key, value));
        root.style.setProperty("--ui-accent-name", accent.label);
        root.style.setProperty("--ui-accent", accent.accent);
        root.style.setProperty("--ui-accent-strong", accent.strong);
        root.style.setProperty("--ui-accent-soft", accent.soft);
        root.style.setProperty("--ui-accent-rgb", accent.rgb);
        root.style.setProperty("--ui-support", accent.support);
        root.style.setProperty("--accent", accent.accent);
        root.style.setProperty("--accent-strong", accent.strong);
        root.style.setProperty("--accent-soft", accent.soft);
        root.style.setProperty("--accent-color", accent.accent);
        root.style.setProperty("--accent-glow", accent.soft);
        root.style.setProperty("--accent-rgb", accent.rgb);
        root.style.setProperty("--secondary", accent.support);
        root.style.setProperty("--gold", accent.support);

        root.dataset.uiTheme = prefs.theme;
        root.dataset.uiAccent = prefs.accent;
        target.dataset.uiTheme = prefs.theme;
        target.dataset.uiAccent = prefs.accent;

        const currentThemeNodes = document.querySelectorAll("[data-ui-current-theme]");
        currentThemeNodes.forEach((node) => {
            node.textContent = theme.label;
        });

        const currentAccentNodes = document.querySelectorAll("[data-ui-current-accent]");
        currentAccentNodes.forEach((node) => {
            node.textContent = accent.label;
        });

        syncControls(document);
        window.dispatchEvent(new CustomEvent("attas:preferenceschange", { detail: prefs }));
        return prefs;
    }

    function setPreferences(nextPreferences) {
        const prefs = {
            ...getPreferences(),
            ...(nextPreferences || {})
        };
        persistPreferences(prefs);
        return applyPreferences(prefs);
    }

    function resetPreferences() {
        const prefs = { theme: "paper", accent: "slate" };
        persistPreferences(prefs);
        return applyPreferences(prefs);
    }

    function syncControls(rootNode) {
        const prefs = getPreferences();
        rootNode.querySelectorAll("[data-ui-theme-option]").forEach((node) => {
            node.dataset.selected = String(node.dataset.uiThemeOption === prefs.theme);
            node.setAttribute("aria-pressed", String(node.dataset.uiThemeOption === prefs.theme));
        });
        rootNode.querySelectorAll("[data-ui-accent-option]").forEach((node) => {
            node.dataset.selected = String(node.dataset.uiAccentOption === prefs.accent);
            node.setAttribute("aria-pressed", String(node.dataset.uiAccentOption === prefs.accent));
        });
        rootNode.querySelectorAll("[data-ui-theme-input]").forEach((node) => {
            node.value = prefs.theme;
        });
        rootNode.querySelectorAll("[data-ui-accent-input]").forEach((node) => {
            node.value = prefs.accent;
        });
    }

    function bindSettingsControls(rootNode) {
        rootNode.addEventListener("click", (event) => {
            const themeOption = event.target.closest("[data-ui-theme-option]");
            if (themeOption) {
                setPreferences({ theme: themeOption.dataset.uiThemeOption });
                return;
            }

            const accentOption = event.target.closest("[data-ui-accent-option]");
            if (accentOption) {
                setPreferences({ accent: accentOption.dataset.uiAccentOption });
                return;
            }

            const resetTrigger = event.target.closest("[data-ui-reset-preferences]");
            if (resetTrigger) {
                resetPreferences();
                return;
            }

            const openTrigger = event.target.closest("[data-ui-open-preferences]");
            if (openTrigger) {
                event.preventDefault();
                openPreferencesPanel();
                return;
            }

            const closeTrigger = event.target.closest("[data-ui-close-preferences]");
            if (closeTrigger) {
                event.preventDefault();
                closePreferencesPanel();
            }
        });

        rootNode.addEventListener("change", (event) => {
            const themeInput = event.target.closest("[data-ui-theme-input]");
            if (themeInput) {
                setPreferences({ theme: themeInput.value });
                return;
            }

            const accentInput = event.target.closest("[data-ui-accent-input]");
            if (accentInput) {
                setPreferences({ accent: accentInput.value });
            }
        });
    }

    function buildThemeChoices() {
        return Object.entries(THEMES).map(([key, value]) => `
            <button
                class="ui-choice-btn"
                type="button"
                data-ui-theme-option="${key}"
                data-tooltip="${value.description}"
            >
                <span class="ui-choice-name">${value.label}</span>
                <span class="ui-choice-copy">${value.description}</span>
            </button>
        `).join("");
    }

    function buildAccentChoices() {
        return Object.entries(ACCENTS).map(([key, value]) => `
            <button
                class="ui-swatch"
                type="button"
                data-ui-accent-option="${key}"
                data-tooltip="Apply the ${value.label.toLowerCase()} accent across controls, badges, and calls to action."
                style="--swatch-color:${value.accent};"
            >
                <span class="ui-swatch-dot"></span>
                <span class="ui-swatch-name">${value.label}</span>
            </button>
        `).join("");
    }

    function ensurePreferencesPanel() {
        if (document.getElementById("ui-preferences-shell")) {
            return;
        }

        const shell = document.createElement("div");
        shell.id = "ui-preferences-shell";
        shell.className = "ui-preferences-shell";
        shell.hidden = true;
        shell.innerHTML = `
            <button class="ui-preferences-backdrop" type="button" aria-label="Close settings" data-ui-close-preferences></button>
            <aside class="ui-preferences-panel" role="dialog" aria-modal="true" aria-labelledby="ui-preferences-title">
                <div class="ui-preferences-header">
                    <div>
                        <p class="ui-preferences-kicker">Site Settings</p>
                        <h2 id="ui-preferences-title">Theme and color</h2>
                        <p class="ui-preferences-copy">Choose the surface tone and accent that should be used across this interface.</p>
                    </div>
                    <button class="ui-preferences-close" type="button" data-ui-close-preferences>Close</button>
                </div>
                <div class="ui-preferences-stack">
                    <section class="ui-preferences-block">
                        <div class="ui-preferences-block-head">
                            <div>
                                <h3>Theme</h3>
                                <div class="ui-preferences-meta">Current: <span data-ui-current-theme></span></div>
                            </div>
                        </div>
                        <div class="ui-choice-grid">${buildThemeChoices()}</div>
                    </section>
                    <section class="ui-preferences-block">
                        <div class="ui-preferences-block-head">
                            <div>
                                <h3>Accent</h3>
                                <div class="ui-preferences-meta">Current: <span data-ui-current-accent></span></div>
                            </div>
                        </div>
                        <div class="ui-swatch-grid">${buildAccentChoices()}</div>
                    </section>
                    <section class="ui-preferences-block">
                        <div class="ui-preferences-block-head">
                            <div>
                                <h3>Preview</h3>
                                <div class="ui-preferences-meta">A quick glance at the current visual system.</div>
                            </div>
                            <button class="ui-reset-btn" type="button" data-ui-reset-preferences>Reset</button>
                        </div>
                        <div class="ui-preview-shell">
                            <div class="ui-preview-row">
                                <span class="ui-preview-chip"><span class="ui-preview-accent"></span><span data-ui-current-theme></span></span>
                                <span class="ui-preview-chip">Accent: <span data-ui-current-accent></span></span>
                            </div>
                            <div class="ui-preferences-copy">Settings are stored in this browser and applied the next time the page opens.</div>
                        </div>
                    </section>
                </div>
            </aside>
        `;
        document.body.appendChild(shell);
        syncControls(shell);
    }

    function ensureLauncher() {
        if (document.body.dataset.uiLauncher === "disabled") {
            return;
        }
        if (document.getElementById("ui-settings-launcher")) {
            return;
        }
        const button = document.createElement("button");
        button.id = "ui-settings-launcher";
        button.className = "ui-settings-launcher";
        button.type = "button";
        button.dataset.uiOpenPreferences = "true";
        button.dataset.tooltip = "Open Site Settings to change the theme and accent color.";
        button.innerHTML = '<span class="ui-settings-launcher-mark">UI</span><span>Site Settings</span>';
        document.body.appendChild(button);
    }

    function openPreferencesPanel() {
        const shell = document.getElementById("ui-preferences-shell");
        if (!shell) return;
        shell.hidden = false;
        document.body.classList.add("modal-open");
    }

    function closePreferencesPanel() {
        const shell = document.getElementById("ui-preferences-shell");
        if (!shell) return;
        shell.hidden = true;
        document.body.classList.remove("modal-open");
    }

    function handleEscape(event) {
        if (event.key !== "Escape") return;
        closePreferencesPanel();
    }

    async function syncGlobalSettings() {
        try {
            // First try local agent sync endpoint, then fallback to relative /api/site-settings (for Plaza)
            let endpoint = "/api/local-site-settings";
            let response = await fetch(endpoint).catch(() => null);
            
            if (!response || response.status !== 200) {
                endpoint = "/api/site-settings";
                response = await fetch(endpoint).catch(() => null);
            }

            if (response && response.status === 200) {
                const data = await response.json();
                if (data.status === "success" && data.settings) {
                    applyGlobalSettings(data.settings);
                }
            }
        } catch (error) {
            console.warn("[attasTheme] Global settings sync failed:", error);
        }
    }

    function applyGlobalSettings(settings) {
        if (!settings) return;
        
        // 1. Apply Theme and Accent if present in global settings
        // These override local storage preferences when received from the Plaza.
        if (settings.theme || settings.accent) {
            const current = getPreferences();
            const next = {
                theme: settings.theme || current.theme,
                accent: settings.accent || current.accent
            };
            
            // Only apply if different to avoid unnecessary reflows
            if (next.theme !== current.theme || next.accent !== current.accent) {
                console.log("[attasTheme] Applying global theme/accent:", next);
                applyPreferences(next);
            }
        }

        // 2. Apply typography overrides
        if (!settings.typography) return;
        const root = document.documentElement;
        const typo = settings.typography;

        if (typo.title) {
            if (typo.title.size) root.style.setProperty("--ui-title-size", typo.title.size);
            if (typo.title.color) root.style.setProperty("--ui-title-color", typo.title.color);
            if (typo.title.weight) root.style.setProperty("--ui-title-weight", typo.title.weight);
        }
        if (typo.header) {
            if (typo.header.size) root.style.setProperty("--ui-header-size", typo.header.size);
            if (typo.header.color) root.style.setProperty("--ui-header-color", typo.header.color);
            if (typo.header.weight) root.style.setProperty("--ui-header-weight", typo.header.weight);
        }
        if (typo.content) {
            if (typo.content.size) root.style.setProperty("--ui-content-size", typo.content.size);
            if (typo.content.color) root.style.setProperty("--ui-content-color", typo.content.color);
            if (typo.content.weight) root.style.setProperty("--ui-content-weight", typo.content.weight);
        }
        
        console.log("[attasTheme] Applied global typography settings");
    }

    function init() {
        bindSettingsControls(document);
        ensurePreferencesPanel();
        ensureLauncher();
        applyPreferences(getPreferences());
        syncGlobalSettings(); // Fetch and apply global settings on load

        // Poll for global site settings periodically to catch updates from the Plaza
        // This ensures connected agents reflect style changes without manual refresh.
        setInterval(syncGlobalSettings, 15000);

        document.addEventListener("keydown", handleEscape);
    }

    window.attasTheme = {
        THEMES,
        ACCENTS,
        getPreferences,
        applyPreferences,
        setPreferences,
        resetPreferences,
        syncControls,
        bindSettingsControls,
        openPreferencesPanel,
        closePreferencesPanel,
        syncGlobalSettings
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
