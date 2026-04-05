"""
Regression tests for the single-command public demo launcher.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import demo_launcher


def test_available_demo_ids_match_expected_wrappers():
    """Every supported launcher ID should map to a checked-in wrapper script."""
    expected = {
        "hello-plaza": REPO_ROOT / "demos" / "hello-plaza" / "run-demo.sh",
        "data-pipeline": REPO_ROOT / "demos" / "data-pipeline" / "run-demo.sh",
        "personal-research-workbench": REPO_ROOT / "demos" / "personal-research-workbench" / "run-demo.sh",
        "file-storage": REPO_ROOT / "demos" / "pulsers" / "file-storage" / "run-demo.sh",
        "yfinance": REPO_ROOT / "demos" / "pulsers" / "yfinance" / "run-demo.sh",
        "llm": REPO_ROOT / "demos" / "pulsers" / "llm" / "run-demo.sh",
        "analyst-insights": REPO_ROOT / "demos" / "pulsers" / "analyst-insights" / "run-demo.sh",
        "finance-briefings": REPO_ROOT / "demos" / "pulsers" / "finance-briefings" / "run-demo.sh",
        "ads": REPO_ROOT / "demos" / "pulsers" / "ads" / "run-demo.sh",
    }

    assert set(demo_launcher.available_demo_ids()) == set(expected)
    for path in expected.values():
        assert path.exists(), f"Missing launcher wrapper: {path}"


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


def test_full_readme_html_renders_source_path_and_title():
    """The full README route should render the local markdown into an HTML shell."""
    spec = demo_launcher.resolve_demo_spec("hello-plaza", {})
    html = demo_launcher._build_full_readme_html(spec)

    assert "Hello Plaza README" in html
    assert str(REPO_ROOT / "demos" / "hello-plaza" / "README.md") in html
    assert "English README Reference" in html
