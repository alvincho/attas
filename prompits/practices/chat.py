import logging
import requests
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from prompits.core.practice import Practice
from prompits.core.message import Message

logger = logging.getLogger(__name__)

class ChatPractice(Practice):
    """
    Practice that exposes LLM chat completion capability to agents.

    Supports provider-specific execution paths (currently Ollama and OpenAI)
    while presenting one stable practice interface (`execute`, `/chat`).
    """

    def __init__(self, provider: str = "ollama", config: Optional[Dict[str, Any]] = None):
        """
        Initialize ChatPractice.
        :param provider: "openai" or "ollama"
        :param config: Configuration dictionary for the provider (API keys, base URLs, etc.)
        """
        super().__init__(
            name="ChatPractice",
            description=f"Enables LLM interaction via {provider}.",
            id="chat-practice",
            tags=["llm", "chat", provider],
            examples=["POST /chat {'prompt': 'Tell me a joke'}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={
                "prompt": {
                    "type": "text",
                    "description": "Enter your prompt or paragraph for the LLM",
                    "placeholder": "Write a short summary about AI..."
                }
            }
        )
        self.provider = provider.lower()
        self.config = config or {}
        
        # Initialize all potential attributes to avoid AttributeErrors during dynamic switching
        self.base_url = self.config.get("base_url")
        self.api_key = self.config.get("api_key")
        self.model = self.config.get("model")

        # Default endpoint configurations if not provided in config
        if self.provider == "ollama":
            if not self.base_url: self.base_url = "http://localhost:11434/api/generate"
            if not self.model: self.model = "llama3"
        elif self.provider == "openai":
            if not self.base_url: self.base_url = "https://api.openai.com/v1/chat/completions"
            if not self.model: self.model = "gpt-4o"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def mount(self, app):
        """Mount chat interaction and model-listing routes."""
        router = APIRouter()

        @router.post("/chat")
        async def chat(message: Message):
            # Forward to agent for general message handling
            if self.agent:
                self.agent.receive(message)
                
            content = message.content
            if not isinstance(content, dict) or "prompt" not in content:
                # If no prompt, just return success since we already forwarded to agent
                return {"status": "received", "data": "Message routed through agent.receive"}
            
            # Use execute for standardized logic
            try:
                result = await run_in_threadpool(self.execute, **content)
                return result
            except Exception as e:
                logger.error(f"[ChatPractice] Error in chat execution: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @router.get("/list_models")
        async def list_models(provider: str = "ollama"):
            provider = provider.lower()
            try:
                if provider == "ollama":
                    models = await run_in_threadpool(self._list_ollama_models)
                elif provider == "openai":
                    models = await run_in_threadpool(self._list_openai_models)
                else:
                    return {"status": "error", "message": f"Unsupported provider: {provider}"}
                return {"status": "success", "models": models}
            except Exception as e:
                logger.error(f"[ChatPractice] Error listing models for {provider}: {e}")
                return {"status": "error", "message": str(e)}

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        """Run a chat completion call through the selected provider and model."""
        prompt = kwargs.get("prompt")
        if not prompt:
            return {"status": "error", "message": "Prompt is required"}
            
        provider = kwargs.get("provider", self.provider).lower()
        model = kwargs.get("model", self.model)
        
        logger.info(f"[ChatPractice] Executing prompt via {provider} ({model}): {prompt[:50]}...")
        
        try:
            if provider == "ollama":
                response_text = self._call_ollama(prompt, model=model)
            elif provider == "openai":
                response_text = self._call_openai(prompt, model=model)
            else:
                return {"status": "error", "message": f"Unsupported provider: {provider}"}
            
            return {"status": "success", "response": response_text}
        except Exception as e:
            logger.error(f"[ChatPractice] Execution error with {provider}: {e}")
            return {"status": "error", "message": str(e)}

    def _get_system_prompt(self) -> str:
        """Build role-conditioned system prompt from bound agent metadata."""
        if not self.agent:
            return ""
        
        name = self.agent.name
        # safer access to agent_card attributes
        card = getattr(self.agent, "agent_card", {})
        role = card.get("role", "agent")
        tags = ", ".join(card.get("tags", []))
        
        return f"You are {name}, a {role} agent in the attas network. Your tags are: [{tags}]. Answer as this agent."

    def _call_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        """Call local/remote Ollama generation endpoint and handle model fallback."""
        model_to_use = model or self.model
        
        # Inject system prompt for context
        system_instruction = self._get_system_prompt()
        full_prompt = f"System: {system_instruction}\nUser: {prompt}" if system_instruction else prompt

        payload = {
            "model": model_to_use,
            "prompt": full_prompt,
            "stream": False
        }
        
        try:
            resp = requests.post(self.base_url, json=payload, timeout=240)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"[ChatPractice] Model '{model_to_use}' not found (404). Attempting fallback...")
                try:
                    available = self._list_ollama_models()
                    if available:
                        fallback_model = available[0]
                        logger.warning(f"[ChatPractice] Falling back to available model: '{fallback_model}'")
                        payload["model"] = fallback_model
                        resp = requests.post(self.base_url, json=payload, timeout=240)
                        resp.raise_for_status()
                        
                        # Update default model for future calls to avoid 404s
                        self.model = fallback_model
                    else:
                        raise ValueError(f"Model '{model_to_use}' not found and no other models available.")
                except Exception as fallback_err:
                    logger.error(f"[ChatPractice] Fallback failed: {fallback_err}")
                    raise e
            else:
                raise

        return resp.json().get("response", "")

    def _call_openai(self, prompt: str, model: Optional[str] = None) -> str:
        """Call OpenAI Chat Completions API using configured API key/base URL."""
        if not self.api_key:
            raise ValueError("OpenAI API key missing in config.")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        system_instruction = self._get_system_prompt()
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model or self.model,
            "messages": messages
        }
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=240)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _list_ollama_models(self) -> List[str]:
        # Ollama tags endpoint: http://localhost:11434/api/tags
        tags_url = self.base_url.replace("/api/generate", "/api/tags")
        resp = requests.get(tags_url, timeout=5)
        resp.raise_for_status()
        models_data = resp.json().get("models", [])
        return [m["name"] for m in models_data]

    def _list_openai_models(self) -> List[str]:
        # Simple static list for common models if no API key is present or for better UX
        # Alternatively fetch from https://api.openai.com/v1/models
        if not self.api_key:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=5)
            resp.raise_for_status()
            models_data = resp.json().get("data", [])
            # Filter to typical chat models
            return sorted([m["id"] for m in models_data if "gpt" in m["id"]])
        except:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
