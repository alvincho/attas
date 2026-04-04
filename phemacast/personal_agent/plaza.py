"""
Plaza integration and web runtime for `phemacast.personal_agent.plaza`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Key definitions include `PlazaProxyError`, `run_plaza_pulser_test`,
`fetch_plaza_catalog`, and `normalize_plaza_url`, which provide the main entry points
used by neighboring modules and tests.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from typing import Any, Dict, List, Optional

import httpx


class PlazaProxyError(RuntimeError):
    """Exception raised for Plaza proxy failures."""
    def __init__(self, message: str, status_code: int = 502):
        """Initialize the Plaza proxy error."""
        super().__init__(message)
        self.status_code = status_code


KNOWN_PLAZA_PATH_SUFFIXES = (
    "/api/plazas_status",
    "/api/pulsers/test",
    "/.well-known/agent-card",
    "/health",
    "/search",
)


def normalize_plaza_url(plaza_url: str) -> str:
    """Normalize the Plaza URL."""
    value = str(plaza_url or "").strip()
    if not value:
        raise ValueError("plaza_url is required.")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    for suffix in KNOWN_PLAZA_PATH_SUFFIXES:
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    normalized = urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))
    return normalized.rstrip("/")


def _load_json(response: httpx.Response) -> Dict[str, Any]:
    """Internal helper to load the JSON."""
    if not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_catalog_pulse(entry: Any) -> Optional[Dict[str, Any]]:
    """Internal helper to normalize the catalog pulse."""
    if not isinstance(entry, dict):
        return None
    pulse_name = str(entry.get("pulse_name") or entry.get("name") or "").strip()
    pulse_address = str(entry.get("pulse_address") or entry.get("pit_address") or entry.get("address") or "").strip()
    pulse_id = str(entry.get("pulse_id") or entry.get("pit_id") or "").strip()
    if not pulse_name and not pulse_address and not pulse_id:
        return None
    pulse_definition = entry.get("pulse_definition") if isinstance(entry.get("pulse_definition"), dict) else {}
    description = str(entry.get("description") or pulse_definition.get("description") or "").strip()
    return {
        "pulse_id": pulse_id,
        "pulse_name": pulse_name,
        "pulse_address": pulse_address,
        "description": description,
        "input_schema": entry.get("input_schema") if isinstance(entry.get("input_schema"), dict) else {},
        "output_schema": entry.get("output_schema") if isinstance(entry.get("output_schema"), dict) else {},
        "pulse_definition": pulse_definition,
        "test_data": entry.get("test_data") if isinstance(entry.get("test_data"), dict) else {},
        "tags": list(entry.get("tags") or []),
    }


def _create_http_client() -> httpx.AsyncClient:
    """Internal helper to create the HTTP client."""
    return httpx.AsyncClient(follow_redirects=True, trust_env=False)


def _format_request_error(action: str, plaza_url: str, exc: Exception) -> str:
    """Internal helper to format the request error."""
    if isinstance(exc, httpx.TimeoutException):
        return f"{action} timed out while contacting Plaza at {plaza_url}."
    return f"{action} failed while contacting Plaza at {plaza_url}: {str(exc)}"


async def _probe_plaza_health(plaza_url: str) -> bool:
    """Internal helper for probe Plaza health."""
    try:
        async with _create_http_client() as client:
            response = await client.get(f"{plaza_url}/health", timeout=8.0)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


def _normalize_practice(entry: Any) -> Optional[Dict[str, Any]]:
    """Internal helper to normalize the practice."""
    if not isinstance(entry, dict):
        return None
    practice_id = str(entry.get("id") or "").strip()
    if not practice_id:
        return None
    return {
        "id": practice_id,
        "name": str(entry.get("name") or practice_id),
        "path": str(entry.get("path") or ""),
        "tags": list(entry.get("tags") or []),
    }


def _normalize_supported_pulse(entry: Any) -> Optional[Dict[str, Any]]:
    """Internal helper to normalize the supported pulse."""
    if not isinstance(entry, dict):
        return None
    pulse_name = str(entry.get("pulse_name") or entry.get("name") or "").strip()
    pulse_address = str(entry.get("pulse_address") or entry.get("address") or "").strip()
    if not pulse_name and not pulse_address:
        return None
    pulse_definition = entry.get("pulse_definition") if isinstance(entry.get("pulse_definition"), dict) else {}
    test_data = entry.get("test_data") if isinstance(entry.get("test_data"), dict) else {}
    if not test_data and isinstance(pulse_definition.get("test_data"), dict):
        test_data = dict(pulse_definition.get("test_data") or {})
    return {
        "pulse_id": str(entry.get("pulse_id") or "").strip(),
        "pulse_name": pulse_name,
        "pulse_address": pulse_address,
        "description": str(entry.get("description") or ""),
        "input_schema": entry.get("input_schema") if isinstance(entry.get("input_schema"), dict) else {},
        "output_schema": entry.get("output_schema") if isinstance(entry.get("output_schema"), dict) else {},
        "pulse_definition": pulse_definition,
        "test_data": test_data,
        "test_data_path": str(entry.get("test_data_path") or pulse_definition.get("test_data_path") or "").strip(),
    }


def _default_practice_id(practices: List[Dict[str, Any]]) -> str:
    """Internal helper to return the default practice ID."""
    preferred = next((entry["id"] for entry in practices if entry.get("id") == "get_pulse_data"), None)
    return preferred or (practices[0]["id"] if practices else "get_pulse_data")


def _supported_pulse_dedupe_key(entry: Dict[str, Any]) -> str:
    """Internal helper to return the supported pulse dedupe key."""
    return str(entry.get("pulse_id") or entry.get("pulse_address") or entry.get("pulse_name") or "").strip().lower()


def _catalog_pulse_dedupe_key(entry: Dict[str, Any]) -> str:
    """Internal helper to return the catalog pulse dedupe key."""
    return str(entry.get("pulse_name") or entry.get("pulse_id") or entry.get("pulse_address") or "").strip().lower()


def _supported_pulse_preference_key(entry: Dict[str, Any]) -> tuple:
    """Internal helper to return the supported pulse preference key."""
    return (
        1 if entry.get("pulse_definition") else 0,
        len(entry.get("output_schema") or {}),
        len(entry.get("input_schema") or {}),
        len(entry.get("test_data") or {}),
        len(str(entry.get("description") or "")),
    )


def _dedupe_supported_pulses(pulses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Internal helper for dedupe supported pulses."""
    deduped: Dict[str, Dict[str, Any]] = {}
    for pulse in pulses:
        key = _supported_pulse_dedupe_key(pulse)
        if not key:
            continue
        existing = deduped.get(key)
        if not existing or _supported_pulse_preference_key(pulse) > _supported_pulse_preference_key(existing):
            deduped[key] = pulse
    return list(deduped.values())


def _dedupe_catalog_pulses(pulses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Internal helper for dedupe catalog pulses."""
    deduped: Dict[str, Dict[str, Any]] = {}
    for pulse in pulses:
        key = _catalog_pulse_dedupe_key(pulse)
        if not key:
            continue
        existing = deduped.get(key)
        if not existing or _supported_pulse_preference_key(pulse) > _supported_pulse_preference_key(existing):
            deduped[key] = pulse
    return list(deduped.values())


def _normalize_pulser(agent: Any, plaza_name: str) -> Optional[Dict[str, Any]]:
    """Internal helper to normalize the pulser."""
    if not isinstance(agent, dict):
        return None
    card = agent.get("card") if isinstance(agent.get("card"), dict) else {}
    meta = agent.get("meta") if isinstance(agent.get("meta"), dict) else {}
    pit_type = str(agent.get("pit_type") or card.get("pit_type") or agent.get("type") or card.get("type") or "").strip()
    if pit_type != "Pulser":
        return None

    practices = [
        normalized
        for normalized in (_normalize_practice(entry) for entry in (card.get("practices") or []))
        if normalized
    ]
    supported_pulses = [
        normalized
        for normalized in (_normalize_supported_pulse(entry) for entry in (meta.get("supported_pulses") or []))
        if normalized
    ]
    supported_pulses = _dedupe_supported_pulses(supported_pulses)

    return {
        "agent_id": str(agent.get("agent_id") or card.get("agent_id") or "").strip(),
        "name": str(agent.get("name") or card.get("name") or "Unnamed Pulser"),
        "address": str(card.get("address") or agent.get("address") or "").strip(),
        "description": str(agent.get("description") or card.get("description") or ""),
        "owner": str(agent.get("owner") or card.get("owner") or ""),
        "practice_id": _default_practice_id(practices),
        "practices": practices,
        "supported_pulses": supported_pulses,
        "last_active": float(agent.get("last_active") or 0),
        "plaza_name": plaza_name,
        "pulse_count": len(supported_pulses),
    }


def _pulser_dedupe_key(pulser: Dict[str, Any]) -> str:
    """Internal helper to return the pulser dedupe key."""
    return str(pulser.get("name") or pulser.get("address") or pulser.get("agent_id") or "").strip().lower()


def _is_loopback_url(value: str) -> bool:
    """Return whether the value is a loopback URL."""
    try:
        host = urlsplit(str(value or "")).hostname or ""
    except ValueError:
        return False
    return host in {"127.0.0.1", "localhost"}


def _pulser_preference_key(pulser: Dict[str, Any]) -> tuple:
    """Internal helper to return the pulser preference key."""
    unique_pulse_count = len(_dedupe_supported_pulses(list(pulser.get("supported_pulses") or [])))
    return (
        1 if _is_loopback_url(str(pulser.get("address") or "")) else 0,
        float(pulser.get("last_active") or 0),
        unique_pulse_count,
        int(pulser.get("pulse_count") or 0),
        len(str(pulser.get("description") or "")),
    )


def _dedupe_pulsers(pulsers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Internal helper for dedupe pulsers."""
    deduped: Dict[str, Dict[str, Any]] = {}
    for pulser in pulsers:
        key = _pulser_dedupe_key(pulser)
        if not key:
            continue
        existing = deduped.get(key)
        if not existing or _pulser_preference_key(pulser) > _pulser_preference_key(existing):
            deduped[key] = pulser
    return list(deduped.values())


def _normalize_catalog(payload: Dict[str, Any], plaza_url: str, catalog_pulse_rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Internal helper to normalize the catalog."""
    plazas = payload.get("plazas") if isinstance(payload.get("plazas"), list) else []
    pulser_rows: List[Dict[str, Any]] = []
    plaza_summaries: List[Dict[str, Any]] = []

    for plaza in plazas:
        if not isinstance(plaza, dict):
            continue
        card = plaza.get("card") if isinstance(plaza.get("card"), dict) else {}
        plaza_name = str(card.get("name") or plaza.get("url") or "Plaza")
        plaza_summaries.append(
            {
                "name": plaza_name,
                "url": str(plaza.get("url") or plaza_url),
                "online": bool(plaza.get("online", True)),
            }
        )
        for agent in plaza.get("agents") or []:
            pulser = _normalize_pulser(agent, plaza_name)
            if not pulser:
                continue
            pulser_rows.append(pulser)

    pulser_rows = _dedupe_pulsers(pulser_rows)
    pulser_rows.sort(key=lambda entry: (entry["name"].lower(), entry["address"].lower()))
    if catalog_pulse_rows:
        catalog_pulses = _dedupe_catalog_pulses(catalog_pulse_rows)
    else:
        catalog_pulses = _dedupe_catalog_pulses(
            [
                pulse
                for pulser in pulser_rows
                for pulse in pulser["supported_pulses"]
            ]
        )
    catalog_pulses.sort(key=lambda entry: (str(entry.get("pulse_name") or "").lower(), str(entry.get("pulse_address") or "").lower()))
    pulse_keys = {
        pulse["pulse_address"] or pulse["pulse_name"] or pulse["pulse_id"]
        for pulse in catalog_pulses
        if pulse["pulse_address"] or pulse["pulse_name"] or pulse["pulse_id"]
    }
    return {
        "status": "success",
        "connected": True,
        "plaza_url": plaza_url,
        "plazas": plaza_summaries,
        "pulses": catalog_pulses,
        "pulsers": pulser_rows,
        "pulser_count": len(pulser_rows),
        "pulse_count": len(pulse_keys),
    }


async def fetch_plaza_catalog(plaza_url: str) -> Dict[str, Any]:
    """Fetch the Plaza catalog."""
    normalized_url = normalize_plaza_url(plaza_url)
    pulses_response: Optional[httpx.Response] = None
    try:
        async with _create_http_client() as client:
            response = await client.get(
                f"{normalized_url}/api/plazas_status",
                params={"pit_type": "Pulser"},
                timeout=20.0,
            )
            try:
                pulses_response = await client.get(
                    f"{normalized_url}/api/plaza/pulses",
                    timeout=20.0,
                )
            except httpx.HTTPError:
                pulses_response = None
    except httpx.HTTPError as exc:
        raise PlazaProxyError(_format_request_error("Catalog request", normalized_url, exc)) from exc

    data = _load_json(response)
    pulses_data = _load_json(pulses_response) if pulses_response is not None else {}
    if response.status_code >= 400:
        detail = data.get("detail") or data.get("message") or "Failed to fetch Plaza catalog."
        if response.status_code == 404 and await _probe_plaza_health(normalized_url):
            detail = f"Plaza at {normalized_url} is online, but this instance does not expose /api/plazas_status."
        raise PlazaProxyError(detail, status_code=response.status_code)
    catalog_pulses = []
    if pulses_response is not None and pulses_response.status_code < 400:
        catalog_pulses = [
            normalized
            for normalized in (_normalize_catalog_pulse(entry) for entry in (pulses_data.get("pulses") or []))
            if normalized
        ]
    return _normalize_catalog(data, normalized_url, catalog_pulses)


async def run_plaza_pulser_test(plaza_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the Plaza pulser test."""
    normalized_url = normalize_plaza_url(plaza_url)
    try:
        async with _create_http_client() as client:
            response = await client.post(f"{normalized_url}/api/pulsers/test", json=payload, timeout=30.0)
    except httpx.HTTPError as exc:
        raise PlazaProxyError(_format_request_error("Pulser test", normalized_url, exc)) from exc

    data = _load_json(response)
    if response.status_code >= 400:
        raise PlazaProxyError(
            data.get("detail") or data.get("message") or "Pulser execution failed.",
            status_code=response.status_code,
        )
    if not data:
        data = {"status": "success", "result": {}}
    data.setdefault("status", "success")
    return data


__all__ = [
    "PlazaProxyError",
    "_normalize_catalog",
    "fetch_plaza_catalog",
    "normalize_plaza_url",
    "run_plaza_pulser_test",
]
