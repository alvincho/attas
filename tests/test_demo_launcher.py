"""
Regression tests for the single-command public demo launcher.
"""

from __future__ import annotations

import os
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import demo_launcher


class FakeJSONResponse:
    """Minimal requests-style JSON response for launcher probe tests."""

    def __init__(self, payload: dict[str, object], *, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict[str, object]:
        """Return the stored JSON payload."""
        return dict(self._payload)


def test_available_demo_ids_match_expected_launch_commands():
    """Every supported launcher ID should expose a direct Python launch command."""
    python_label = Path(sys.executable).name or "python"
    expected = {
        "hello-plaza": f"{python_label} -m scripts.demo_launcher hello-plaza",
        "data-pipeline": f"{python_label} -m scripts.demo_launcher data-pipeline",
        "personal-research-workbench": f"{python_label} -m scripts.demo_launcher personal-research-workbench",
        "file-storage": f"{python_label} -m scripts.demo_launcher file-storage",
        "yfinance": f"{python_label} -m scripts.demo_launcher yfinance",
        "llm": f"{python_label} -m scripts.demo_launcher llm",
        "analyst-insights": f"{python_label} -m scripts.demo_launcher analyst-insights",
        "finance-briefings": f"{python_label} -m scripts.demo_launcher finance-briefings",
        "ads": f"{python_label} -m scripts.demo_launcher ads",
    }

    assert set(demo_launcher.available_demo_ids()) == set(expected)
    for demo_id, command in expected.items():
        spec = demo_launcher.resolve_demo_spec(demo_id, {})
        assert spec.run_script_path == command


def test_service_commands_are_direct_python_invocations():
    """Managed demo services should launch directly via Python instead of shell wrappers."""
    for demo_id in demo_launcher.available_demo_ids():
        spec = demo_launcher.resolve_demo_spec(demo_id, {})
        for service in spec.services:
            assert service.command[0] == sys.executable
            assert "/bin/sh" not in service.command


def test_llm_demo_defaults_to_openai_when_api_key_exists():
    """The LLM launcher should pick OpenAI first when an API key is present."""
    spec = demo_launcher.resolve_demo_spec("llm", {"OPENAI_API_KEY": "demo-key"})
    assert any(service.name == "DemoOpenAIPulser" for service in spec.services)
    assert any(page.url == "http://127.0.0.1:8262/" for page in spec.browser_pages)


def test_llm_demo_falls_back_to_ollama_without_api_key():
    """The LLM launcher should fall back to Ollama when no API key is present."""
    spec = demo_launcher.resolve_demo_spec("llm", {})
    assert any(service.name == "DemoOllamaPulser" for service in spec.services)
    assert any(page.url == "http://127.0.0.1:8263/" for page in spec.browser_pages)


def test_analyst_demo_advanced_mode_adds_personal_agent_flow():
    """Advanced analyst mode should add the prompted flow and personal agent."""
    spec = demo_launcher.resolve_demo_spec("analyst-insights", {"DEMO_ANALYST_MODE": "advanced"})
    service_names = {service.name for service in spec.services}
    page_urls = {page.url for page in spec.browser_pages}

    assert "DemoAnalystPromptedNewsPulser" in service_names
    assert "Phemacast Personal Agent" in service_names
    assert "http://127.0.0.1:8061/" in page_urls
    assert "http://127.0.0.1:8270/" in page_urls


def test_finance_briefings_launcher_is_self_contained():
    """Finance briefings should carry its own Plaza instead of borrowing another demo's registry."""
    spec = demo_launcher.resolve_demo_spec("finance-briefings", {})
    service_names = {service.name for service in spec.services}
    health_urls = {service.health_url for service in spec.services}

    assert "finance-briefing-demo-plaza" in service_names
    assert "DemoFinancialBriefingPulser" in service_names
    assert "http://127.0.0.1:8272/health" in health_urls
    assert "http://127.0.0.1:8271/health" in health_urls


def test_all_registry_services_expect_plaza_health_identity():
    """Plaza-backed registries report `agent=Plaza` on `/health` regardless of config filename."""
    for demo_id in demo_launcher.available_demo_ids():
        spec = demo_launcher.resolve_demo_spec(demo_id, {})
        registry_services = [service for service in spec.services if service.kind == "registry"]
        for service in registry_services:
            assert service.expected_agent == "Plaza"


def test_all_supported_demos_have_windows_batch_wrappers():
    """Every supported demo should ship a Windows batch launcher next to its README."""
    for demo_id in demo_launcher.available_demo_ids():
        spec = demo_launcher.resolve_demo_spec(demo_id, {})
        wrapper_path = Path(spec.readme_path).resolve().parent / "run_demo.bat"

        assert wrapper_path.exists(), f"missing Windows wrapper for {demo_id}"

        content = wrapper_path.read_text(encoding="utf-8")
        assert "@echo off" in content
        assert "setlocal" in content
        assert "pushd" in content
        assert "where py >nul 2>&1" in content
        assert "py -3 -m scripts.demo_launcher" in content
        assert "python -m scripts.demo_launcher" in content
        assert f"scripts.demo_launcher {demo_id} %*" in content
        if "demos/pulsers/" in spec.readme_path.replace("\\", "/"):
            assert r"%~dp0..\..\.." in content
        else:
            assert r"%~dp0..\.." in content


def test_demo_pages_are_manual_links_on_the_guide():
    """Demo specs should expose UI pages as guide links instead of auto-opening them."""
    for demo_id in demo_launcher.available_demo_ids():
        spec = demo_launcher.resolve_demo_spec(demo_id, {})
        assert all(page.auto_open is False for page in spec.browser_pages)


def test_demo_companion_configs_target_their_local_plaza_ports():
    """Demo companion agents should point at the Plaza port owned by their own demo."""
    expected_paths = {
        "hello-plaza": [
            "demos/hello-plaza/worker.agent",
            "demos/hello-plaza/user.agent",
        ],
        "personal-research-workbench": [
            "demos/personal-research-workbench/file-storage.pulser",
            "demos/personal-research-workbench/yfinance.pulser",
            "demos/personal-research-workbench/technical-analysis.pulser",
        ],
        "file-storage": ["demos/pulsers/file-storage/file-storage.pulser"],
        "yfinance": ["demos/pulsers/yfinance/yfinance.pulser"],
        "llm": [
            "demos/pulsers/llm/openai.pulser",
            "demos/pulsers/llm/ollama.pulser",
        ],
        "analyst-insights": [
            "demos/pulsers/analyst-insights/analyst-insights.pulser",
            "demos/pulsers/analyst-insights/news-wire.pulser",
            "demos/pulsers/analyst-insights/ollama.pulser",
            "demos/pulsers/analyst-insights/analyst-news-ollama.pulser",
        ],
        "finance-briefings": ["demos/pulsers/finance-briefings/finance-briefings.pulser"],
    }

    for demo_id, relative_paths in expected_paths.items():
        spec = demo_launcher.resolve_demo_spec(
            demo_id,
            {"DEMO_ANALYST_MODE": "advanced"} if demo_id == "analyst-insights" else {},
        )
        registry = next(service for service in spec.services if service.kind == "registry")
        expected_plaza_url = registry.ui_url.rstrip("/")

        for relative_path in relative_paths:
            payload = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
            assert payload["plaza_url"] == expected_plaza_url, relative_path


def test_demo_saved_diagrams_use_workbench_ports():
    """Saved workbench diagrams should target the current workbench Plaza and pulser ports."""
    plaza_expected = "http://127.0.0.1:8241"
    yfinance_expected = "http://127.0.0.1:8243"
    technical_expected = "http://127.0.0.1:8244"
    plaza_only_paths = [
        REPO_ROOT / "demos" / "files" / "diagrams" / "map_phemar" / "map_phemar.phemar",
        REPO_ROOT / "demos" / "files" / "diagrams" / "map_phemar" / "pool" / "phemas" / "phema-mnh8up4z-qnv7op.json",
    ]
    indicator_paths = [
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-adx-14-diagram.json",
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-bollinger-bandwidth-diagram.json",
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-ema-50-diagram.json",
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-macd-histogram-diagram.json",
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-obv-diagram.json",
        REPO_ROOT / "demos" / "files" / "diagrams" / "ohlc-to-sma-20-diagram.json",
    ]

    for path in plaza_only_paths:
        text = path.read_text(encoding="utf-8")
        assert plaza_expected in text
        assert "127.0.0.1:8011" not in text

    for path in indicator_paths:
        text = path.read_text(encoding="utf-8")
        assert plaza_expected in text
        assert yfinance_expected in text
        assert technical_expected in text
        assert "127.0.0.1:8011" not in text
        assert "127.0.0.1:8020" not in text
        assert "127.0.0.1:8033" not in text


def test_demo_registry_ports_stay_unique():
    """Dedicated demo Plazas should keep distinct ports to avoid cross-demo reuse."""
    registry_urls = {}
    for demo_id in demo_launcher.available_demo_ids():
        spec = demo_launcher.resolve_demo_spec(
            demo_id,
            {"DEMO_ANALYST_MODE": "advanced"} if demo_id == "analyst-insights" else {},
        )
        for service in spec.services:
            if service.kind == "registry":
                registry_urls[demo_id] = service.ui_url.rstrip("/")

    assert registry_urls == {
        "hello-plaza": "http://127.0.0.1:8211",
        "personal-research-workbench": "http://127.0.0.1:8241",
        "file-storage": "http://127.0.0.1:8256",
        "yfinance": "http://127.0.0.1:8251",
        "llm": "http://127.0.0.1:8261",
        "analyst-insights": "http://127.0.0.1:8266",
        "finance-briefings": "http://127.0.0.1:8272",
    }


def test_demo_launcher_sets_personal_agent_plaza_envs():
    """Launcher-managed personal-agent UIs should inherit the right demo Plaza URL."""
    workbench_spec = demo_launcher.resolve_demo_spec("personal-research-workbench", {})
    workbench_ui = next(service for service in workbench_spec.services if service.name == "Phemacast Personal Agent")
    assert workbench_ui.env["PHEMACAST_PERSONAL_AGENT_PLAZA_URL"] == "http://127.0.0.1:8241"

    analyst_spec = demo_launcher.resolve_demo_spec("analyst-insights", {"DEMO_ANALYST_MODE": "advanced"})
    analyst_ui = next(service for service in analyst_spec.services if service.name == "Phemacast Personal Agent")
    assert analyst_ui.env["PHEMACAST_PERSONAL_AGENT_PLAZA_URL"] == "http://127.0.0.1:8266"


def test_plaza_backed_create_agent_services_require_registration_checks():
    """Single-registry demos should wait for Plaza directory registration on create-agent services."""
    hello_spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    worker = next(service for service in hello_spec.services if service.name == "demo-worker")
    user_ui = next(service for service in hello_spec.services if service.name == "demo-user-ui")
    plaza = next(service for service in hello_spec.services if service.name == "demo-plaza")

    assert worker.registration_plaza_url == "http://127.0.0.1:8211/"
    assert user_ui.registration_plaza_url == "http://127.0.0.1:8211/"
    assert plaza.registration_plaza_url == ""

    workbench_spec = demo_launcher.resolve_demo_spec("personal-research-workbench", {})
    personal_agent = next(service for service in workbench_spec.services if service.name == "Phemacast Personal Agent")
    demo_pulser = next(service for service in workbench_spec.services if service.name == "DemoSystemPulser")

    assert demo_pulser.registration_plaza_url == "http://127.0.0.1:8241/"
    assert personal_agent.registration_plaza_url == ""

    ads_spec = demo_launcher.resolve_demo_spec("ads", {})
    assert all(not service.registration_plaza_url for service in ads_spec.services)


def test_probe_service_waits_for_live_plaza_registration(monkeypatch):
    """A healthy agent should stay non-ready until Plaza lists it on the expected address."""
    spec = demo_launcher.resolve_demo_spec("personal-research-workbench", {})
    service = next(service for service in spec.services if service.name == "DemoSystemPulser")

    def fake_get(url, timeout=None, params=None):
        if url == service.health_url:
            return FakeJSONResponse({"agent": "DemoSystemPulser"})
        if url == "http://127.0.0.1:8241/api/plazas_status":
            assert params == {"live_only": "1"}
            return FakeJSONResponse({"status": "success", "plazas": [{"agents": []}]})
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(demo_launcher.requests, "get", fake_get)

    probe = demo_launcher._probe_service(service)

    assert probe.live is True
    assert probe.ready is False
    assert "waiting for Plaza registration" in probe.detail


def test_probe_service_requires_matching_live_plaza_address(monkeypatch):
    """Plaza registration should only count when the directory entry points at this service address."""
    spec = demo_launcher.resolve_demo_spec("personal-research-workbench", {})
    service = next(service for service in spec.services if service.name == "DemoSystemPulser")

    def fake_get(url, timeout=None, params=None):
        if url == service.health_url:
            return FakeJSONResponse({"agent": "DemoSystemPulser"})
        if url == "http://127.0.0.1:8241/api/plazas_status":
            return FakeJSONResponse(
                {
                    "status": "success",
                    "plazas": [
                        {
                            "agents": [
                                {
                                    "name": "DemoSystemPulser",
                                    "card": {"address": "http://127.0.0.1:9999"},
                                }
                            ]
                        }
                    ],
                }
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(demo_launcher.requests, "get", fake_get)

    probe = demo_launcher._probe_service(service)

    assert probe.live is True
    assert probe.ready is False
    assert "instead of http://127.0.0.1:8242" in probe.detail


def test_probe_service_accepts_matching_live_plaza_registration(monkeypatch):
    """Plaza-backed services should become ready once live registration matches the service address."""
    spec = demo_launcher.resolve_demo_spec("personal-research-workbench", {})
    service = next(service for service in spec.services if service.name == "DemoSystemPulser")

    def fake_get(url, timeout=None, params=None):
        if url == service.health_url:
            return FakeJSONResponse({"agent": "DemoSystemPulser"})
        if url == "http://127.0.0.1:8241/api/plazas_status":
            return FakeJSONResponse(
                {
                    "status": "success",
                    "plazas": [
                        {
                            "agents": [
                                {
                                    "name": "DemoSystemPulser",
                                    "card": {"address": "http://127.0.0.1:8242"},
                                }
                            ]
                        }
                    ],
                }
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(demo_launcher.requests, "get", fake_get)

    probe = demo_launcher._probe_service(service)

    assert probe.live is True
    assert probe.ready is True
    assert "registered in Plaza" in probe.detail


def test_launcher_opens_only_the_guide_page(monkeypatch):
    """Auto-open behavior should open the guide page once and leave demo UIs manual."""
    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    state = demo_launcher.LauncherState(spec)
    state.set_urls("http://127.0.0.1:9999/", "http://127.0.0.1:9999/full-readme")

    opened_urls: list[str] = []
    monkeypatch.setattr(demo_launcher.webbrowser, "open_new_tab", opened_urls.append)

    demo_launcher._open_browser_pages(state, spec, open_browser=True)

    assert opened_urls == ["http://127.0.0.1:9999/"]


def test_windows_health_probe_timeout_defaults_higher_for_fresh_boots(monkeypatch):
    """Windows defaults should allow slower first-run localhost health checks."""
    monkeypatch.setattr(demo_launcher.os, "name", "nt", raising=False)
    monkeypatch.delenv("DEMO_HEALTH_PROBE_TIMEOUT_SEC", raising=False)

    assert demo_launcher._health_probe_timeout_sec() == pytest.approx(2.0)


def test_windows_service_startup_timeout_scales_up(monkeypatch):
    """Windows defaults should give slow first-run services more time to become healthy."""
    monkeypatch.setattr(demo_launcher.os, "name", "nt", raising=False)
    monkeypatch.delenv("DEMO_STARTUP_TIMEOUT_MULTIPLIER", raising=False)

    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    plaza = next(service for service in spec.services if service.name == "demo-plaza")

    assert plaza.timeout_sec == pytest.approx(25.0)
    assert demo_launcher._service_startup_timeout_sec(plaza) == pytest.approx(75.0)


def test_registry_services_expose_plaza_ui_links_on_guide_pages():
    """Registry-backed demos should expose the Plaza root URL in both services and page links."""
    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})

    registry_services = [service for service in spec.services if service.kind == "registry"]
    assert registry_services
    assert registry_services[0].ui_url == "http://127.0.0.1:8211/"
    assert any(page.label == "Plaza UI" and page.url == "http://127.0.0.1:8211/" for page in spec.browser_pages)


def test_main_page_html_contains_languages_and_status_routes():
    """The guide page should embed every requested language option and the live status endpoints."""
    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    html = demo_launcher._build_main_page_html(spec)

    for _, label in demo_launcher.LANGUAGE_OPTIONS:
        assert label in html
    assert "/api/status" in html
    assert "/full-readme" in html
    assert "Single-Command Demo Launcher" in html
    assert "function renderMetaValue" in html
    assert 'class="meta-link"' in html
    assert "renderMetaValue(service.healthUrl, { preferLink: true })" in html
    assert "renderMetaValue(page.url, { preferLink: true })" in html
    assert "Plaza UI" in html
    assert "http://127.0.0.1:8211/" in html


def test_full_readme_html_renders_source_path_and_title():
    """The full README route should render the local markdown into an HTML shell."""
    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    html = demo_launcher._build_full_readme_html(spec)

    assert "Hello Plaza README" in html
    assert str(REPO_ROOT / "demos" / "hello-plaza" / "README.md") in html
    assert "English README Reference" in html
