from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from prompits.core.message import Message
from prompits.practices.chat import ChatPractice


class LLMPractice(ChatPractice):
    """
    Dedicated LLM practice with a stable `/llm` endpoint.

    This wraps the broader ChatPractice provider logic but exposes a separate
    practice id so agents can advertise a specific LLM capability without
    colliding with the default `chat-practice` that BaseAgent mounts.
    """

    DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

    def __init__(
        self,
        provider: str = "ollama",
        config: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        merged_config = dict(config or {})
        if base_url:
            merged_config["base_url"] = base_url
        if model:
            merged_config["model"] = model
        if api_key:
            merged_config["api_key"] = api_key

        if provider.lower() == "ollama":
            merged_config.setdefault("base_url", self.DEFAULT_OLLAMA_URL)
            merged_config.setdefault("model", "llama3")

        super().__init__(provider=provider, config=merged_config)

        self.name = "LLMPractice"
        self.description = f"Routes prompts to the configured {self.provider} backend."
        self.id = "llm"
        self.tags = ["llm", "generation", self.provider]
        self.examples = [
            "POST /llm {'prompt': 'Summarize NVDA earnings'}",
        ]
        self.parameters = {
            "prompt": {
                "type": "text",
                "description": "Prompt to send to the configured LLM backend.",
                "placeholder": "Explain retrieval-augmented generation in 3 bullets.",
            },
            "model": {
                "type": "string",
                "description": "Optional model override for this request.",
            },
        }

    def mount(self, app):
        router = APIRouter()

        @router.post("/llm")
        async def llm(message: Message):
            content = message.content
            if isinstance(content, str):
                content = {"prompt": content}

            if not isinstance(content, dict):
                raise HTTPException(status_code=400, detail="LLM content must be a string or JSON object.")

            result = await run_in_threadpool(self.execute, **content)
            if result.get("status") == "error":
                raise HTTPException(status_code=500, detail=result.get("message", "LLM execution failed"))
            return result

        @router.get("/llm_models")
        async def llm_models(provider: Optional[str] = None):
            selected_provider = (provider or self.provider).lower()
            try:
                if selected_provider == "ollama":
                    models = await run_in_threadpool(self._list_ollama_models)
                elif selected_provider == "openai":
                    models = await run_in_threadpool(self._list_openai_models)
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported provider: {selected_provider}")
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            return {"status": "success", "provider": selected_provider, "models": models}

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        payload = dict(kwargs)
        if "prompt" not in payload and isinstance(payload.get("content"), str):
            payload["prompt"] = payload["content"]

        provider = str(payload.get("provider", self.provider)).lower()
        model = payload.get("model", self.model)
        result = super().execute(**payload)
        if result.get("status") == "success":
            result["provider"] = provider
            result["model"] = model
            result["endpoint"] = self.base_url
        return result
