"""
Regression tests for Plaza Relay Mailbox.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_plaza_relay_defaults_to_mailbox_for_generic_messages` and
`test_plaza_relay_uses_explicit_practice_path_when_receiver_advertises_one`, helping
guard against regressions as the packages evolve.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.practices.plaza import PlazaPractice


class FakeRelayResponse:
    """Response model for fake relay payloads."""
    def __init__(self, payload):
        """Initialize the fake relay response."""
        self._payload = payload
        self.content = b'{"status":"ok"}'

    def raise_for_status(self):
        """Return the raise for the status."""
        return None

    def json(self):
        """Handle JSON for the fake relay response."""
        return dict(self._payload)


def _build_plaza_client():
    """Internal helper to build the Plaza client."""
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(
        SimpleNamespace(
            name="Plaza",
            pool=None,
            host="127.0.0.1",
            port=8011,
            agent_card={
                "name": "Plaza",
                "role": "coordinator",
                "tags": ["plaza"],
                "address": "http://127.0.0.1:8011",
                "pit_type": "Agent",
            },
        )
    )
    practice.mount(app)
    relay_practice = next(endpoint for endpoint in practice.endpoint_practices if endpoint.id == "relay")
    return TestClient(app), relay_practice


def test_plaza_relay_defaults_to_mailbox_for_generic_messages():
    """
    Exercise the test_plaza_relay_defaults_to_mailbox_for_generic_messages
    regression scenario.
    """
    client, relay_practice = _build_plaza_client()
    relay_practice._client.post = AsyncMock(return_value=FakeRelayResponse({"status": "received"}))

    sender = client.post("/register", json={"agent_name": "sender", "address": "http://sender"})
    assert sender.status_code == 200
    sender_token = sender.json()["token"]

    receiver = client.post(
        "/register",
        json={
            "agent_name": "receiver",
            "address": "http://receiver",
            "card": {"name": "receiver", "practices": [{"id": "mailbox", "path": "/mailbox"}]},
        },
    )
    assert receiver.status_code == 200

    relayed = client.post(
        "/relay",
        json={"receiver": "receiver", "content": {"text": "hi"}, "msg_type": "message"},
        headers={"Authorization": f"Bearer {sender_token}"},
    )
    assert relayed.status_code == 200
    relay_practice._client.post.assert_awaited_once()
    assert relay_practice._client.post.await_args.args[0] == "http://receiver/mailbox"


def test_plaza_relay_uses_explicit_practice_path_when_receiver_advertises_one():
    """
    Exercise the
    test_plaza_relay_uses_explicit_practice_path_when_receiver_advertises_one
    regression scenario.
    """
    client, relay_practice = _build_plaza_client()
    relay_practice._client.post = AsyncMock(return_value=FakeRelayResponse({"status": "ok"}))

    sender = client.post("/register", json={"agent_name": "sender", "address": "http://sender"})
    assert sender.status_code == 200
    sender_token = sender.json()["token"]

    receiver = client.post(
        "/register",
        json={
            "agent_name": "receiver",
            "address": "http://receiver",
            "card": {"name": "receiver", "practices": [{"id": "echo-practice", "path": "/echo"}]},
        },
    )
    assert receiver.status_code == 200

    relayed = client.post(
        "/relay",
        json={"receiver": "receiver", "content": {"text": "hi"}, "msg_type": "echo-practice"},
        headers={"Authorization": f"Bearer {sender_token}"},
    )
    assert relayed.status_code == 200
    relay_practice._client.post.assert_awaited_once()
    assert relay_practice._client.post.await_args.args[0] == "http://receiver/echo"
