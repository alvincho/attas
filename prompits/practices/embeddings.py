"""
Embeddings module for `prompits.practices.embeddings`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the practices package bundles
reusable behaviors that agents can mount or execute remotely.

Core types exposed here include `EmbeddingPractice`, which carry the main behavior or
state managed by this module.
"""

import logging
import requests
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from prompits.core.practice import Practice
from prompits.core.message import Message

logger = logging.getLogger(__name__)

class EmbeddingPractice(Practice):
    """
    Practice that exposes LLM embedding generation capability to agents.
    
    Supports Ollama and OpenAI providers.
    """

    def __init__(self, provider: str = "ollama", config: Optional[Dict[str, Any]] = None):
        """Initialize the embedding practice."""
        super().__init__(
            name="EmbeddingPractice",
            description=f"Enables text embedding generation via {provider}.",
            id="embedding-practice",
            tags=["llm", "embeddings", provider],
            examples=["POST /embeddings {'input': 'The quick brown fox jumps over the lazy dog'}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={
                "input": {
                    "type": "text",
                    "description": "Enter the text to generate embeddings for.",
                    "placeholder": "Enter your sentence here..."
                },
                "model": {
                    "type": "string",
                    "description": "Optional model override for this request."
                }
            }
        )
        self.provider = provider.lower()
        self.config = config or {}
        
        self.base_url = self.config.get("base_url")
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model")

        if self.provider == "ollama":
            if not self.base_url: self.base_url = "http://localhost:11434/api/embeddings"
            if not self.model: self.model = "mxbai-embed-large"  # Common Ollama embedding model
        elif self.provider == "openai":
            if not self.base_url: self.base_url = "https://api.openai.com/v1/embeddings"
            if not self.model: self.model = "text-embedding-3-small"
        else:
            raise ValueError(f"Unsupported Embedding provider: {self.provider}")

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post("/embeddings")
        async def generate_embeddings(message: Message):
            """Route handler for POST /embeddings."""
            content = message.content
            if not isinstance(content, dict) or ("input" not in content and "text" not in content):
                raise HTTPException(status_code=400, detail="Input text is required for embeddings.")
            
            try:
                result = await run_in_threadpool(self.execute, **content)
                return result
            except Exception as e:
                logger.error(f"[EmbeddingPractice] Error in embedding execution: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        """Handle execute for the embedding practice."""
        text = kwargs.get("input") or kwargs.get("text")
        if not text:
            return {"status": "error", "message": "Input text is required"}
            
        provider = kwargs.get("provider", self.provider).lower()
        model = kwargs.get("model", self.model)
        
        logger.info(f"[EmbeddingPractice] Generating embeddings via {provider} ({model})...")
        
        try:
            if provider == "ollama":
                embeddings = self._call_ollama_embeddings(text, model=model)
            elif provider == "openai":
                embeddings = self._call_openai_embeddings(text, model=model)
            else:
                return {"status": "error", "message": f"Unsupported provider: {provider}"}
            
            return {
                "status": "success", 
                "embeddings": embeddings,
                "model": model,
                "provider": provider
            }
        except Exception as e:
            logger.error(f"[EmbeddingPractice] Execution error with {provider}: {e}")
            return {"status": "error", "message": str(e)}

    def _call_ollama_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        """Internal helper for call ollama embeddings."""
        payload = {
            "model": model or self.model,
            "prompt": text
        }
        resp = requests.post(self.base_url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("embedding", [])

    def _call_openai_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        """Internal helper for call OpenAI embeddings."""
        if not self.api_key:
            raise ValueError("OpenAI API key missing in config.")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self.model,
            "input": text
        }
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
