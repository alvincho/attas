"""
OpenAI pulser implementation for the Pulsers area.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. Within Attas, these modules define finance-
oriented pulse providers and transformation steps.

Core types exposed here include `OpenAIPulser`, which carry the main behavior or state
managed by this module.
"""

import os
import json
import logging
import requests
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from prompits.core.pit import PitAddress

load_dotenv()
from phemacast.agents.pulser import Pulser, validate_pulser_config_test_parameters
from prompits.practices.embeddings import EmbeddingPractice

logger = logging.getLogger(__name__)

class OpenAIPulser(Pulser):
    """
    Pulser agent that provides LLM-backed pulse delivery.
    
    Exposes:
    - Pulse: llm_chat
    - Practice: EmbeddingPractice (for /embeddings)
    - Route: /list_models for editor-side provider discovery
    """

    DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    def __init__(self, *args, **kwargs):
        """Initialize the open ai pulser."""
        kwargs['auto_register'] = False
        super().__init__(*args, **kwargs)
        
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self._setup_ui_routes()
        
        api_key = self.raw_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        base_url = self.raw_config.get("base_url")
        model = self.raw_config.get("model")
        
        practice_config = {
            "base_url": base_url,
            "model": model,
            "api_key": api_key
        }
        
        provider = self._detect_provider(base_url)
            
        self.add_practice(EmbeddingPractice(provider=provider, config=practice_config))
        
        logger.info(f"[OpenAIPulser] Initialized as '{provider}' with llm_chat pulse and embeddings.")

    @staticmethod
    def _detect_provider(base_url: Optional[str]) -> str:
        """Internal helper for detect provider."""
        if base_url and "openai.com" in str(base_url).lower():
            return "openai"
        return "ollama"

    def _list_ollama_models(self) -> list[str]:
        """Internal helper to list the ollama models."""
        base_url = str(self.raw_config.get("base_url") or self.DEFAULT_OLLAMA_URL)
        tags_url = base_url.replace("/api/generate", "/api/tags")
        response = requests.get(tags_url, timeout=5)
        response.raise_for_status()
        models_data = response.json().get("models", [])
        return [str(model.get("name") or "") for model in models_data if str(model.get("name") or "").strip()]

    def _list_openai_models(self) -> list[str]:
        """Internal helper to list the OpenAI models."""
        api_key = self.raw_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return list(self.DEFAULT_OPENAI_MODELS)
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
            response.raise_for_status()
            models_data = response.json().get("data", [])
            models = sorted(
                str(model.get("id") or "")
                for model in models_data
                if "gpt" in str(model.get("id") or "")
            )
            return models or list(self.DEFAULT_OPENAI_MODELS)
        except Exception:
            return list(self.DEFAULT_OPENAI_MODELS)

    def _load_config_document(self) -> Dict[str, Any]:
        """Internal helper to load the config document."""
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or {})

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the config document."""
        normalized = self._normalize_config_document(config)
        try:
            validate_pulser_config_test_parameters(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if self.config_path:
            with self.config_path.open("w", encoding="utf-8") as fh:
                json.dump(normalized, fh, indent=4)
            self.raw_config = dict(normalized)
            self.apply_pulser_config(normalized)
            return self._build_editor_config_document(normalized)
        self.raw_config = dict(config)
        return self._build_editor_config_document(config)

    def _build_editor_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the editor config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "attas.pulsers.openai_pulser.OpenAIPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", self.agent_card.get("role", "pulser"))
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        document["api_key"] = document.get("api_key", self.raw_config.get("api_key"))
        document["api_keys"] = list(document.get("api_keys") or self.raw_config.get("api_keys") or [])
        document["supported_pulses"] = [
            self._normalize_editor_pulse(pulse, document)
            for pulse in (document.get("supported_pulses") or self.supported_pulses or [])
            if isinstance(pulse, dict)
        ]
        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "attas.pulsers.openai_pulser.OpenAIPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", self.agent_card.get("role", "pulser"))
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        pulses = [pulse for pulse in (document.get("supported_pulses") or self.supported_pulses or []) if isinstance(pulse, dict)]
        if pulses:
            primary = dict(pulses[0])
            pulse_api = dict(primary.get("api") or {})
            pulse_extra = dict(primary)
            pulse_extra.pop("api", None)
            pulse_extra.pop("test_data", None)
            pulse_extra.pop("test_payload", None)
            pulse_extra.pop("sample_input", None)
            if pulse_api.get("url"):
                document["base_url"] = pulse_api.get("url")
            if primary.get("test_data", {}).get("model"):
                document["model"] = primary["test_data"]["model"]
            elif pulse_extra.get("model"):
                document["model"] = pulse_extra["model"]
        document["supported_pulses"] = [self._normalize_saved_pulse(pulse, document) for pulse in pulses]
        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _normalize_editor_pulse(self, pulse: Dict[str, Any], document: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the editor pulse."""
        normalized = dict(pulse)
        pulse_api = dict(normalized.get("api") or {})
        if not pulse_api.get("url") and document.get("base_url"):
            pulse_api["url"] = document["base_url"]
        pulse_api.setdefault("method", "POST")
        normalized["api"] = pulse_api
        test_data = dict(normalized.get("test_data") or normalized.get("test_payload") or normalized.get("sample_input") or {})
        if document.get("model") and "model" not in test_data:
            test_data["model"] = document["model"]
        if "prompt" not in test_data:
            test_data["prompt"] = "Say hello in one sentence."
        normalized["test_data"] = test_data
        return normalized

    def _normalize_saved_pulse(self, pulse: Dict[str, Any], document: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the saved pulse."""
        normalized = dict(pulse)
        pulse_api = dict(normalized.get("api") or {})
        pulse_address = PitAddress.from_value(normalized.get("pulse_address"))
        if pulse_address.pit_id:
            normalized["pulse_address"] = pulse_address.to_ref()
        normalized.pop("output_schema", None)
        if pulse_api.get("url"):
            document["base_url"] = pulse_api["url"]
        normalized.pop("api", None)
        test_data = dict(normalized.get("test_data") or {})
        model = test_data.pop("model", None)
        if model:
            document["model"] = model
        normalized["test_data"] = test_data
        return normalized

    def _setup_ui_routes(self) -> None:
        """Internal helper to set up the UI routes."""
        @self.app.get("/")
        async def editor_ui(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="attas/pulsers/templates/openai_pulser_editor.html",
                context={
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_config():
            """Route handler for GET /api/config."""
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/list_models")
        async def list_models(provider: str = ""):
            """Route handler for GET /list_models."""
            selected_provider = str(provider or self._detect_provider(self.raw_config.get("base_url"))).strip().lower()
            try:
                if selected_provider == "openai":
                    models = await run_in_threadpool(self._list_openai_models)
                elif selected_provider == "ollama":
                    models = await run_in_threadpool(self._list_ollama_models)
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported provider: {selected_provider}")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            return {"status": "success", "provider": selected_provider, "models": models}

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
        async def save_config(request: Request):
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
        async def test_pulse(request: Request):
            """Exercise the test_pulse regression scenario."""
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
                runner = self.__class__(config=runtime_config, auto_register=False)
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
                    "fetch": {
                        "provider": result.get("provider") if isinstance(result, dict) else None,
                        "base_url": runner.raw_config.get("base_url"),
                    },
                    "mapping": mapping_rules,
                    "raw_payload": raw_payload,
                    "result": result,
                }
            return response

        @self.app.post("/api/model-info")
        async def model_info(request: Request):
            """Route handler for POST /api/model-info."""
            payload = await request.json()
            model = payload.get("model")
            base_url = self.raw_config.get("base_url") or "http://localhost:11434/api/generate"
            
            # This is specific to Ollama.
            if "ollama" in base_url or "11434" in base_url or "generate" in base_url:
                show_url = base_url.replace("/generate", "/show")
                try:
                    resp = requests.post(show_url, json={"name": model}, timeout=10)
                    resp.raise_for_status()
                    return {"status": "success", "info": resp.json()}
                except Exception as e:
                    return {"status": "error", "message": f"Could not fetch info: {e}"}
            else:
                return {"status": "error", "message": "Model info fetching is only supported for Ollama endpoints currently."}

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle pulse requests. Specifically implementation for 'llm_chat'.
        """
        if pulse_name == "llm_chat":
            return self._handle_llm_chat(input_data)
            
        return super().fetch_pulse_payload(pulse_name, input_data, pulse_definition)

    def _handle_llm_chat(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the LLM chat."""
        prompt = input_data.get("prompt")
        if not prompt:
            return {"error": "Prompt is required for llm_chat pulse."}

        model = input_data.get("model") or self.raw_config.get("model", "llama3")
        base_url = self.raw_config.get("base_url") or "http://localhost:11434/api/generate"
        api_key = self.raw_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        
        is_openai = "openai.com" in base_url.lower()
        provider = "openai" if is_openai else "ollama"
        
        logger.info(f"[OpenAIPulser] Pulse llm_chat ({provider}): {prompt[:50]}... using {model}")

        headers = {}
        if is_openai:
            if not api_key:
                return {"error": "OpenAI API key missing in config or environment."}
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False
            }
        
        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=240)
            resp.raise_for_status()
            response_json = resp.json()
            
            if is_openai:
                content = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                content = response_json.get("response", "")
                
            return {
                "response": content,
                "model": model,
                "provider": provider
            }
        except Exception as e:
            logger.error(f"[OpenAIPulser] Error in llm_chat ({provider}): {e}")
            return {"error": str(e)}
