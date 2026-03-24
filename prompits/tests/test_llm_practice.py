import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.practices.llm import LLMPractice
from prompits.tests.test_support import build_agent_from_config


def test_llm_practice_defaults_to_local_ollama():
    practice = LLMPractice()

    assert practice.provider == "ollama"
    assert practice.base_url == "http://127.0.0.1:11434/api/generate"
    assert practice.model == "llama3"
    assert practice.id == "llm"
    assert practice.path == "/llm"


def test_llm_practice_execute_uses_ollama_endpoint():
    practice = LLMPractice()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": "Local Ollama reply"}

    with patch("prompits.practices.chat.requests.post", return_value=response) as post_mock:
        result = practice.execute(prompt="ping")

    assert result["status"] == "success"
    assert result["response"] == "Local Ollama reply"
    assert result["provider"] == "ollama"
    assert result["model"] == "llama3"
    assert result["endpoint"] == "http://127.0.0.1:11434/api/generate"
    post_mock.assert_called_once_with(
        "http://127.0.0.1:11434/api/generate",
        json={"model": "llama3", "prompt": "ping", "stream": False},
        timeout=240,
    )


def test_llm_agent_config_mounts_llm_practice():
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../attas/configs/llm.agent")
    )

    agent = build_agent_from_config(config_path)

    practice_ids = {practice.id for practice in agent.practices}
    assert "chat-practice" in practice_ids
    assert "llm" in practice_ids

    llm_practice = next(practice for practice in agent.practices if practice.id == "llm")
    assert llm_practice.base_url == "http://127.0.0.1:11434/api/generate"
    assert llm_practice.model == "llama3"

    card_paths = {entry["id"]: entry["path"] for entry in agent.agent_card.get("practices", [])}
    assert card_paths["llm"] == "/llm"
