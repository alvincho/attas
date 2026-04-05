"""
Pulser logic for `ads.pulser`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `ADSPulser`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import Pulser, validate_pulser_config_test_parameters
from prompits.core.pit import PitAddress

from ads.agents import ADS_PARTY, _resolve_ads_party
from ads.runtime import normalize_symbol, parse_datetime_value, read_ads_config
from ads.schema import (
    TABLE_DAILY_PRICE,
    TABLE_FINANCIAL_STATEMENTS,
    TABLE_FUNDAMENTALS,
    TABLE_NEWS,
    TABLE_RAW_DATA,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    TABLE_SECURITY_MASTER,
    ensure_ads_tables,
)

ADS_PULSE_NAME_ALIASES = {
    "company_fundamentals": "company_profile",
    "company_news": "news_article",
    "sec_companyfacts": "sec_companyfact",
    "sec_submissions": "sec_submission",
}


def _normalize_ads_pulse_name(name: str) -> str:
    """Internal helper to normalize the ADS pulse name."""
    normalized_name = str(name or "").strip()
    return ADS_PULSE_NAME_ALIASES.get(normalized_name, normalized_name)


def _first_non_empty(*values: Any) -> Any:
    """Internal helper for first non empty."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        if value not in ({}, [], ()):
            return value
    return None


def _as_mapping(value: Any) -> Dict[str, Any]:
    """Internal helper for as mapping."""
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_cik(value: Any) -> str:
    """Internal helper to normalize the cik."""
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits.zfill(10) if digits else ""


def _default_pulse_address(name: str) -> str:
    """Internal helper to return the default pulse address."""
    normalized_name = _normalize_ads_pulse_name(name) or "default_pulse"
    return f"plaza://pulse/{normalized_name}"


def _ads_table_for_pulse_name(name: str) -> str:
    """Internal helper to return the ADS table for the pulse name."""
    normalized_name = _normalize_ads_pulse_name(name)
    return {
        "security_master_lookup": TABLE_SECURITY_MASTER,
        "daily_price_history": TABLE_DAILY_PRICE,
        "company_profile": TABLE_FUNDAMENTALS,
        "financial_statements": TABLE_FINANCIAL_STATEMENTS,
        "news_article": TABLE_NEWS,
        "sec_companyfact": TABLE_SEC_COMPANYFACTS,
        "sec_submission": TABLE_SEC_SUBMISSIONS,
        "raw_collection_payload": TABLE_RAW_DATA,
    }.get(normalized_name, "")


def _ensure_pulse_addresses(pulses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Internal helper to ensure the pulse addresses exists."""
    resolved_pulses: List[Dict[str, Any]] = []
    for pulse in pulses:
        if not isinstance(pulse, Mapping):
            continue
        resolved = dict(pulse)
        configured_name = str(resolved.get("name") or resolved.get("pulse_name") or "").strip()
        pulse_name = _normalize_ads_pulse_name(configured_name)
        aliases = [
            str(alias).strip()
            for alias in list(resolved.get("aliases") or [])
            if str(alias).strip()
        ]
        if configured_name and configured_name != pulse_name and configured_name not in aliases:
            aliases.append(configured_name)
        if pulse_name:
            resolved["name"] = pulse_name
            resolved["pulse_name"] = pulse_name
        if aliases:
            resolved["aliases"] = aliases
        legacy_address = f"plaza://pulse/{configured_name}" if configured_name else ""
        if pulse_name and str(resolved.get("pulse_address") or "").strip() == legacy_address and legacy_address != _default_pulse_address(pulse_name):
            resolved["pulse_address"] = _default_pulse_address(pulse_name)
        if pulse_name and not str(resolved.get("pulse_address") or "").strip():
            resolved["pulse_address"] = _default_pulse_address(pulse_name)
        if pulse_name and not str(resolved.get("ads_table") or "").strip():
            ads_table = _ads_table_for_pulse_name(pulse_name)
            if ads_table:
                resolved["ads_table"] = ads_table
        resolved_pulses.append(resolved)
    return resolved_pulses


def _default_supported_pulses() -> List[Dict[str, Any]]:
    """Internal helper to return the default supported pulses."""
    return [
        {
            "name": "security_master_lookup",
            "description": "Look up normalized security master rows collected by ADS.",
            "pulse_address": _default_pulse_address("security_master_lookup"),
            "tags": ["ads", "security-master", "instruments"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "count": {"type": "integer"},
                },
                "required": ["items", "count"],
            },
            "ads_table": TABLE_SECURITY_MASTER,
            "test_data": {"symbol": "AAPL", "limit": 1},
        },
        {
            "name": "daily_price_history",
            "description": "Return daily OHLCV history collected by ADS.",
            "pulse_address": _default_pulse_address("daily_price_history"),
            "tags": ["ads", "prices", "ohlcv"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["symbol"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "prices": {"type": "array"},
                    "count": {"type": "integer"},
                },
                "required": ["symbol", "prices", "count"],
            },
            "ads_table": TABLE_DAILY_PRICE,
            "test_data": {"symbol": "AAPL", "limit": 5},
        },
        {
            "name": "company_profile",
            "description": "Return company profile data derived from ADS fundamentals and security master rows.",
            "pulse_address": _default_pulse_address("company_profile"),
            "tags": ["ads", "company-profile", "fundamentals"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                },
                "required": ["symbol"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "company_name": {"type": "string"},
                    "legal_name": {"type": "string"},
                    "sector": {"type": "string"},
                    "industry": {"type": "string"},
                    "headquarters_country": {"type": "string"},
                    "website": {"type": "string"},
                    "exchange": {"type": "string"},
                    "currency": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["symbol", "company_name"],
            },
            "ads_table": TABLE_FUNDAMENTALS,
            "aliases": ["company_fundamentals"],
            "test_data": {"symbol": "AAPL"},
        },
        {
            "name": "financial_statements",
            "description": "Return normalized financial statement rows collected by ADS.",
            "pulse_address": _default_pulse_address("financial_statements"),
            "tags": ["ads", "financial-statements"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "statement_type": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["symbol"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "items": {"type": "array"},
                    "count": {"type": "integer"},
                },
                "required": ["symbol", "items", "count"],
            },
            "ads_table": TABLE_FINANCIAL_STATEMENTS,
            "test_data": {"symbol": "AAPL", "statement_type": "income_statement", "limit": 5},
        },
        {
            "name": "news_article",
            "description": "Return normalized ADS news articles, optionally filtered by symbol.",
            "pulse_address": _default_pulse_address("news_article"),
            "tags": ["ads", "news"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "number_of_articles": {"type": "integer", "minimum": 1},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "number_of_articles": {"type": "integer"},
                    "articles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "headline": {"type": "string"},
                                "published_at": {"type": "string"},
                                "publisher": {"type": "string"},
                                "summary": {"type": "string"},
                                "url": {"type": "string"},
                                "sentiment_label": {"type": "string"},
                            },
                        },
                    },
                    "source": {"type": "string"},
                },
                "required": ["articles"],
            },
            "ads_table": TABLE_NEWS,
            "aliases": ["company_news"],
            "test_data": {"number_of_articles": 2},
        },
        {
            "name": "raw_collection_payload",
            "description": "Return raw payloads associated with ADS jobs.",
            "pulse_address": _default_pulse_address("raw_collection_payload"),
            "tags": ["ads", "raw-data"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "items": {"type": "array"},
                    "count": {"type": "integer"},
                },
                "required": ["items", "count"],
            },
            "ads_table": TABLE_RAW_DATA,
            "test_data": {"job_id": "ads-job:demo", "limit": 1},
        },
        {
            "name": "sec_companyfact",
            "description": "Return raw SEC EDGAR companyfacts rows collected by ADS.",
            "pulse_address": _default_pulse_address("sec_companyfact"),
            "tags": ["ads", "sec", "edgar", "raw"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "cik": {"type": "string"},
                    "symbol": {"type": "string"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "cik": {"type": "string"},
                    "symbol": {"type": "string"},
                    "companyfact": {"type": "object"},
                    "count": {"type": "integer"},
                },
                "required": ["companyfact", "count"],
            },
            "ads_table": TABLE_SEC_COMPANYFACTS,
            "aliases": ["sec_companyfacts"],
            "test_data": {"symbol": "AAPL"},
        },
        {
            "name": "sec_submission",
            "description": "Return raw SEC EDGAR submissions rows collected by ADS.",
            "pulse_address": _default_pulse_address("sec_submission"),
            "tags": ["ads", "sec", "edgar", "raw"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "cik": {"type": "string"},
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "cik": {"type": "string"},
                    "symbol": {"type": "string"},
                    "items": {"type": "array"},
                    "count": {"type": "integer"},
                },
                "required": ["items", "count"],
            },
            "ads_table": TABLE_SEC_SUBMISSIONS,
            "aliases": ["sec_submissions"],
            "test_data": {"symbol": "AAPL", "limit": 1},
        },
    ]


class ADSPulser(Pulser):
    """Represent an ADS pulser."""
    def __init__(
        self,
        config: Any = None,
        *,
        config_path: Any = None,
        name: str | None = None,
        host: str | None = None,
        port: int | None = None,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        supported_pulses: List[Dict[str, Any]] | None = None,
        auto_register: bool | None = None,
    ):
        """Initialize the ADS pulser."""
        if pool is None:
            raise ValueError("ADSPulser requires a pool so it can read ADS datasets.")

        loaded_config = read_ads_config(config_path or config)
        ads_settings = loaded_config.get("ads") if isinstance(loaded_config.get("ads"), Mapping) else {}
        resolved_name = str(name or loaded_config.get("name") or "ADSPulser")
        resolved_host = str(host or loaded_config.get("host") or "127.0.0.1")
        try:
            resolved_port = int(port if port is not None else loaded_config.get("port") or 8062)
        except (TypeError, ValueError):
            resolved_port = 8062
        resolved_plaza_url = str(plaza_url or loaded_config.get("plaza_url") or "").strip() or None
        resolved_auto_register = bool(
            auto_register if auto_register is not None else ads_settings.get("auto_register", False)
        )
        resolved_supported_pulses = (
            supported_pulses
            or loaded_config.get("supported_pulses")
            or _default_supported_pulses()
        )
        resolved_supported_pulses = _ensure_pulse_addresses(list(resolved_supported_pulses))
        card = dict(agent_card or loaded_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card["party"] = _resolve_ads_party(loaded_config, card)
        card["role"] = str(loaded_config.get("role") or card.get("role") or "pulser")
        card["description"] = str(
            loaded_config.get("description")
            or card.get("description")
            or "Serves normalized Attas Data Services datasets as Plaza pulses."
        )
        tags = list(loaded_config.get("tags") or card.get("tags") or [])
        for tag in ("ads", "pulser", "data-services"):
            if tag not in tags:
                tags.append(tag)
        card["tags"] = tags
        meta = dict(card.get("meta") or {})
        meta.setdefault("party", card["party"] or ADS_PARTY)
        card["meta"] = meta

        ensure_ads_tables(pool)
        super().__init__(
            config=loaded_config or {"name": card["name"]},
            config_path=config_path,
            name=card["name"],
            host=resolved_host,
            port=resolved_port,
            plaza_url=resolved_plaza_url,
            agent_card=card,
            pool=pool,
            supported_pulses=resolved_supported_pulses,
            auto_register=resolved_auto_register,
        )
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self.last_fetch_debug: Dict[str, Any] = {}
        self._setup_ads_pulser_routes()

    def _setup_ads_pulser_routes(self) -> None:
        """Internal helper to set up the ADS pulser routes."""
        @self.app.get("/")
        async def ads_pulser_ui(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="phemacast/pulsers/templates/api_pulser_editor.html",
                context={
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_ads_pulser_config():
            """Route handler for GET /api/config."""
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plaza/pulses")
        async def get_plaza_pulses(search: str = ""):
            """Route handler for GET /api/plaza/pulses."""
            rows = await run_in_threadpool(self._search_plaza_directory, pit_type="Pulse", name=search.strip() or None)
            pulses = []
            for row in rows or []:
                card = row.get("card") or {}
                meta = card.get("meta") or {}
                pit_address = PitAddress.from_value(card.get("pit_address"))
                pulses.append(
                    {
                        "pit_address": pit_address.to_ref(reference_plaza=self.plaza_url),
                        "pit_id": pit_address.pit_id,
                        "name": card.get("name") or row.get("name"),
                        "description": card.get("description") or row.get("description") or meta.get("description", ""),
                        "tags": list(card.get("tags") or meta.get("tags") or []),
                        "output_schema": meta.get("output_schema") if isinstance(meta.get("output_schema"), dict) else {},
                    }
                )
            return {"status": "success", "pulses": pulses}

        @self.app.post("/api/config")
        async def save_ads_pulser_config(request: Request):
            """Route handler for POST /api/config."""
            payload = await request.json()
            config = payload.get("config") if isinstance(payload, dict) and isinstance(payload.get("config"), dict) else payload
            if not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="Config payload must be a JSON object.")
            saved = await run_in_threadpool(self._save_config_document, config)
            return {
                "status": "success",
                "config": saved,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.post("/api/test-pulse")
        async def test_ads_pulser_pulse(request: Request):
            """Exercise the test_ads_pulser_pulse regression scenario."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Test payload must be a JSON object.")

            pulse_name = payload.get("pulse_name")
            params = payload.get("params") or {}
            config = payload.get("config")
            include_debug = bool(payload.get("debug"))
            if not pulse_name:
                raise HTTPException(status_code=400, detail="pulse_name is required.")
            if not isinstance(params, dict):
                raise HTTPException(status_code=400, detail="params must be a JSON object.")
            if config is not None and not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="config must be a JSON object when provided.")

            def _run_test_sync():
                """Internal helper to run the test sync."""
                runtime_config = config if isinstance(config, dict) else self._load_config_document()
                runner = self.__class__(config=runtime_config, pool=self.pool, auto_register=False)
                pulse_definition = runner.resolve_pulse_definition(pulse_name=str(pulse_name))
                raw_payload = runner.fetch_pulse_payload(str(pulse_name), params, pulse_definition) or {}
                mapping_rules = pulse_definition.get("mapping") or runner.mapping
                if isinstance(raw_payload, dict) and raw_payload.get("error"):
                    result = raw_payload
                elif mapping_rules:
                    result = runner.transform(
                        raw_payload,
                        pulse_name=str(pulse_name),
                        pulse_address=pulse_definition.get("pulse_address"),
                        output_schema=pulse_definition.get("output_schema"),
                        mapping=mapping_rules,
                    )
                else:
                    result = raw_payload
                return runner, pulse_definition, raw_payload, mapping_rules, result

            try:
                runner, pulse_definition, raw_payload, mapping_rules, result = await run_in_threadpool(_run_test_sync)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            response = {
                "status": "success",
                "pulse_name": str(pulse_name),
                "params": params,
                "result": result,
            }
            if include_debug:
                response["debug"] = {
                    "pulse_definition": pulse_definition,
                    "fetch": dict(runner.last_fetch_debug or {}),
                    "mapping": mapping_rules,
                    "raw_payload": raw_payload,
                    "result": result,
                }
            return response

    def _load_config_document(self) -> Dict[str, Any]:
        """Internal helper to load the config document."""
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the config document."""
        if not self.config_path:
            raise HTTPException(status_code=400, detail="This ADSPulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        try:
            validate_pulser_config_test_parameters(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

        self.raw_config = dict(normalized)
        self.apply_pulser_config(normalized)
        return self._build_editor_config_document(normalized)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "ads.pulser.ADSPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        document["supported_pulses"] = _ensure_pulse_addresses([
            self._normalize_config_pulse(pulse)
            for pulse in (document.get("supported_pulses") or self.supported_pulses or [])
            if isinstance(pulse, dict)
        ])
        if "ads" in self.raw_config and "ads" not in document:
            document["ads"] = dict(self.raw_config["ads"])
        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _build_editor_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the editor config document."""
        document = self._normalize_config_document(config)
        if self.supported_pulses:
            document["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        return document

    @staticmethod
    def _normalize_config_pulse(pulse: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config pulse."""
        normalized = dict(pulse)
        pulse_address = PitAddress.from_value(normalized.get("pulse_address"))
        if pulse_address.pit_id:
            normalized["pulse_address"] = pulse_address.to_ref()
            normalized.pop("output_schema", None)
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "ads.pulser.ADSPulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "supported_pulses": [dict(pulse) for pulse in self.supported_pulses],
            "ads": dict(self.raw_config.get("ads") or {}),
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    def _rows_for_table(self, table_name: str, *, symbol: str = "") -> List[Dict[str, Any]]:
        """Internal helper to return the rows for the table."""
        normalized_symbol = normalize_symbol(symbol)
        if normalized_symbol:
            return self.pool._GetTableData(table_name, {"symbol": normalized_symbol}) or []
        return self.pool._GetTableData(table_name) or []

    def _rows_for_where(self, table_name: str, where: Mapping[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Internal helper to return the rows for the where."""
        if isinstance(where, Mapping) and where:
            return self.pool._GetTableData(table_name, dict(where)) or []
        return self.pool._GetTableData(table_name) or []

    @staticmethod
    def _limit_rows(rows: List[Dict[str, Any]], limit: Any) -> List[Dict[str, Any]]:
        """Internal helper to return the limit rows."""
        try:
            normalized_limit = max(int(limit), 0)
        except (TypeError, ValueError):
            return rows
        return rows[:normalized_limit] if normalized_limit else rows

    @staticmethod
    def _sort_sec_submission_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Internal helper to return the sort SEC submission rows."""
        rows.sort(
            key=lambda row: (
                bool(row.get("is_primary")),
                parse_datetime_value(row.get("updated_at")),
                str(row.get("file_name") or ""),
            ),
            reverse=True,
        )
        return rows

    def fetch_pulse_payload(
        self,
        pulse_name: str,
        input_data: Dict[str, Any],
        pulse_definition: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch the pulse payload."""
        resolved_name = _normalize_ads_pulse_name(str(pulse_definition.get("name") or pulse_name or "").strip())
        symbol = normalize_symbol(input_data.get("symbol"))
        limit = input_data.get("limit")
        self.last_fetch_debug = {
            "pulse_name": resolved_name,
            "symbol": symbol,
            "limit": limit,
            "ads_table": pulse_definition.get("ads_table"),
        }

        if resolved_name == "security_master_lookup":
            rows = self._rows_for_table(TABLE_SECURITY_MASTER, symbol=symbol)
            rows.sort(key=lambda row: (str(row.get("symbol") or ""), str(row.get("name") or "")))
            limited_rows = self._limit_rows(rows, limit)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            return {"items": limited_rows, "count": len(limited_rows)}

        if resolved_name == "daily_price_history":
            rows = self._rows_for_table(TABLE_DAILY_PRICE, symbol=symbol)
            start_date = str(input_data.get("start_date") or "").strip()
            end_date = str(input_data.get("end_date") or "").strip()
            self.last_fetch_debug["start_date"] = start_date
            self.last_fetch_debug["end_date"] = end_date
            if start_date:
                rows = [row for row in rows if str(row.get("trade_date") or "") >= start_date]
            if end_date:
                rows = [row for row in rows if str(row.get("trade_date") or "") <= end_date]
            rows.sort(key=lambda row: str(row.get("trade_date") or ""), reverse=True)
            limited_rows = self._limit_rows(rows, limit)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            return {"symbol": symbol, "prices": limited_rows, "count": len(limited_rows)}

        if resolved_name == "company_profile":
            if not symbol:
                self.last_fetch_debug["error"] = "symbol is required"
                return {"error": "symbol is required"}
            rows = self._rows_for_table(TABLE_FUNDAMENTALS, symbol=symbol)
            rows.sort(key=lambda row: str(row.get("as_of_date") or ""), reverse=True)
            latest = rows[0] if rows else {}
            security_master_rows = self._rows_for_table(TABLE_SECURITY_MASTER, symbol=symbol)
            security_master_rows.sort(
                key=lambda row: (
                    str(row.get("updated_at") or ""),
                    str(row.get("name") or ""),
                ),
                reverse=True,
            )
            security_master = security_master_rows[0] if security_master_rows else {}
            fundamentals_data = _as_mapping(latest.get("data"))
            security_master_metadata = _as_mapping(security_master.get("metadata"))
            company_name = _first_non_empty(
                security_master.get("name"),
                fundamentals_data.get("company_name"),
                fundamentals_data.get("companyName"),
                fundamentals_data.get("short_name"),
                fundamentals_data.get("shortName"),
                symbol,
            )
            self.last_fetch_debug["row_count"] = len(rows)
            return {
                "symbol": symbol,
                "company_name": company_name,
                "legal_name": _first_non_empty(
                    fundamentals_data.get("legal_name"),
                    fundamentals_data.get("legalName"),
                    fundamentals_data.get("long_name"),
                    fundamentals_data.get("longName"),
                    company_name,
                ),
                "sector": _first_non_empty(latest.get("sector"), fundamentals_data.get("sector")),
                "industry": _first_non_empty(latest.get("industry"), fundamentals_data.get("industry")),
                "headquarters_country": _first_non_empty(
                    fundamentals_data.get("headquarters_country"),
                    fundamentals_data.get("headquartersCountry"),
                    fundamentals_data.get("country"),
                ),
                "website": _first_non_empty(
                    fundamentals_data.get("website"),
                    fundamentals_data.get("official_site"),
                    fundamentals_data.get("officialSite"),
                    fundamentals_data.get("OfficialSite"),
                    security_master_metadata.get("website"),
                ),
                "exchange": _first_non_empty(security_master.get("exchange"), fundamentals_data.get("exchange")),
                "currency": _first_non_empty(security_master.get("currency"), latest.get("currency"), fundamentals_data.get("currency")),
                "source": _first_non_empty(latest.get("provider"), security_master.get("provider"), "ads"),
            }

        if resolved_name == "financial_statements":
            rows = self._rows_for_table(TABLE_FINANCIAL_STATEMENTS, symbol=symbol)
            statement_type = str(input_data.get("statement_type") or "").strip().lower()
            self.last_fetch_debug["statement_type"] = statement_type
            if statement_type:
                rows = [
                    row
                    for row in rows
                    if str(row.get("statement_type") or "").strip().lower() == statement_type
                ]
            rows.sort(key=lambda row: str(row.get("period_end") or ""), reverse=True)
            limited_rows = self._limit_rows(rows, limit)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            return {"symbol": symbol, "items": limited_rows, "count": len(limited_rows)}

        if resolved_name == "news_article":
            requested_number_of_articles = input_data.get("number_of_articles")
            if requested_number_of_articles in (None, ""):
                requested_number_of_articles = limit
            if requested_number_of_articles in (None, ""):
                number_of_articles = 10
            else:
                try:
                    number_of_articles = int(requested_number_of_articles)
                except (TypeError, ValueError):
                    self.last_fetch_debug["error"] = "number_of_articles must be a positive integer"
                    response = {"error": "number_of_articles must be a positive integer"}
                    if symbol:
                        response["symbol"] = symbol
                    return response
                if number_of_articles <= 0:
                    self.last_fetch_debug["error"] = "number_of_articles must be a positive integer"
                    response = {"error": "number_of_articles must be a positive integer"}
                    if symbol:
                        response["symbol"] = symbol
                    return response
            self.last_fetch_debug["number_of_articles"] = number_of_articles
            rows = self._rows_for_table(TABLE_NEWS, symbol=symbol)
            rows.sort(key=lambda row: parse_datetime_value(row.get("published_at")), reverse=True)
            limited_rows = self._limit_rows(rows, number_of_articles)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            articles = []
            for row in limited_rows:
                article = {
                    "headline": row.get("headline"),
                    "published_at": row.get("published_at"),
                    "publisher": row.get("source"),
                    "summary": row.get("summary"),
                    "url": row.get("url"),
                }
                article_data = _as_mapping(row.get("data"))
                sentiment_label = _first_non_empty(
                    article_data.get("sentiment_label"),
                    article_data.get("overall_sentiment_label"),
                )
                if sentiment_label:
                    article["sentiment_label"] = sentiment_label
                articles.append({key: value for key, value in article.items() if value not in (None, "")})
            response = {
                "number_of_articles": number_of_articles,
                "articles": articles,
                "source": "ads",
            }
            if symbol:
                response["symbol"] = symbol
            return response

        if resolved_name == "sec_companyfact":
            cik = _normalize_cik(input_data.get("cik"))
            resolved_symbol = symbol
            self.last_fetch_debug["cik"] = cik
            if not cik and not resolved_symbol:
                self.last_fetch_debug["error"] = "cik or symbol is required"
                return {"error": "cik or symbol is required"}
            submission_rows: List[Dict[str, Any]] = []
            if not cik and resolved_symbol:
                submission_rows = self._sort_sec_submission_rows(
                    self._rows_for_where(TABLE_SEC_SUBMISSIONS, {"symbol": resolved_symbol})
                )
                if submission_rows:
                    cik = _normalize_cik(submission_rows[0].get("cik"))
                    resolved_symbol = normalize_symbol(submission_rows[0].get("symbol")) or resolved_symbol
            companyfact_rows = self._rows_for_where(TABLE_SEC_COMPANYFACTS, {"cik": cik}) if cik else []
            companyfact_rows.sort(
                key=lambda row: (
                    parse_datetime_value(row.get("updated_at")),
                    str(row.get("file_name") or ""),
                ),
                reverse=True,
            )
            companyfact = companyfact_rows[0] if companyfact_rows else {}
            self.last_fetch_debug["row_count"] = 1 if companyfact else 0
            return {
                "cik": cik,
                "symbol": resolved_symbol,
                "companyfact": companyfact,
                "count": 1 if companyfact else 0,
            }

        if resolved_name == "sec_submission":
            cik = _normalize_cik(input_data.get("cik"))
            resolved_symbol = symbol
            self.last_fetch_debug["cik"] = cik
            if not cik and not resolved_symbol:
                self.last_fetch_debug["error"] = "cik or symbol is required"
                return {"error": "cik or symbol is required"}
            if cik:
                rows = self._rows_for_where(TABLE_SEC_SUBMISSIONS, {"cik": cik})
                if not resolved_symbol:
                    sorted_rows = self._sort_sec_submission_rows(list(rows))
                    if sorted_rows:
                        resolved_symbol = normalize_symbol(sorted_rows[0].get("symbol"))
                    rows = sorted_rows
                else:
                    rows = self._sort_sec_submission_rows(list(rows))
            else:
                rows = self._sort_sec_submission_rows(
                    self._rows_for_where(TABLE_SEC_SUBMISSIONS, {"symbol": resolved_symbol})
                )
                if rows:
                    cik = _normalize_cik(rows[0].get("cik"))
            limited_rows = self._limit_rows(rows, limit)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            return {
                "cik": cik,
                "symbol": resolved_symbol,
                "items": limited_rows,
                "count": len(limited_rows),
            }

        if resolved_name == "raw_collection_payload":
            job_id = str(input_data.get("job_id") or "").strip()
            self.last_fetch_debug["job_id"] = job_id
            rows = self.pool._GetTableData(TABLE_RAW_DATA, {"job_id": job_id}) if job_id else self.pool._GetTableData(TABLE_RAW_DATA)
            rows = rows or []
            rows.sort(key=lambda row: parse_datetime_value(row.get("collected_at")), reverse=True)
            limited_rows = self._limit_rows(rows, limit)
            self.last_fetch_debug["row_count"] = len(limited_rows)
            return {"items": limited_rows, "count": len(limited_rows)}

        self.last_fetch_debug["error"] = f"Unsupported ADS pulse '{resolved_name}'."
        return {"error": f"Unsupported ADS pulse '{resolved_name}'."}


ADSPuler = ADSPulser
