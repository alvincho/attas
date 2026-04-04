"""
Regression tests for File Storage Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_file_storage_pulser_agent_config_loads_via_shared_agent_factory`,
`test_file_storage_pulser_list_bucket_respects_visibility_scope`,
`test_file_storage_pulser_private_bucket_is_owner_scoped`, and
`test_file_storage_pulser_public_bucket_is_shared`, helping guard against regressions as
the packages evolve.
"""

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from botocore.exceptions import ClientError

from phemacast.pulsers.file_storage_pulser import FileStoragePulser
from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


class FakeS3Body:
    """Represent a fake s 3 body."""
    def __init__(self, payload: bytes):
        """Initialize the fake s 3 body."""
        self.payload = payload

    def read(self) -> bytes:
        """Read the value."""
        return self.payload


class FakeS3Client:
    """Represent a fake s 3 client."""
    def __init__(self):
        """Initialize the fake s 3 client."""
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        """Handle put object for the fake s 3 client."""
        self.objects[(Bucket, Key)] = bytes(Body)
        return {"ETag": "fake"}

    def get_object(self, Bucket, Key):
        """Return the object."""
        payload = self.objects.get((Bucket, Key))
        if payload is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": FakeS3Body(payload)}

    def head_object(self, Bucket, Key):
        """Handle head object for the fake s 3 client."""
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        """List the objects v 2."""
        keys = [
            key
            for (bucket, key), _payload in self.objects.items()
            if bucket == Bucket and key.startswith(Prefix)
        ]
        return {
            "Contents": [{"Key": key} for key in sorted(keys)],
            "IsTruncated": False,
        }


def _caller(agent_id: str, agent_name: str | None = None) -> dict[str, str]:
    """Internal helper for caller."""
    return {
        "agent_id": agent_id,
        "agent_name": agent_name or agent_id,
    }


def test_file_storage_pulser_private_bucket_is_owner_scoped(tmp_path):
    """
    Exercise the test_file_storage_pulser_private_bucket_is_owner_scoped regression
    scenario.
    """
    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )

    created = pulser.get_pulse_data(
        {
            "bucket_name": "owner-private",
            "visibility": "private",
            "_caller": _caller("agent-a", "Agent A"),
        },
        pulse_name="bucket_create",
    )
    saved = pulser.get_pulse_data(
        {
            "bucket_name": "owner-private",
            "object_key": "docs/hello.txt",
            "text": "hello from agent a",
            "_caller": _caller("agent-a", "Agent A"),
        },
        pulse_name="object_save",
    )
    browsed = pulser.get_pulse_data(
        {
            "bucket_name": "owner-private",
            "_caller": _caller("agent-a", "Agent A"),
        },
        pulse_name="bucket_browse",
    )
    denied = pulser.get_pulse_data(
        {
            "bucket_name": "owner-private",
            "object_key": "docs/hello.txt",
            "_caller": _caller("agent-b", "Agent B"),
        },
        pulse_name="object_load",
    )

    assert created["status"] == "created"
    assert created["owner_agent_id"] == "agent-a"
    assert saved["status"] == "saved"
    assert browsed["returned_count"] == 1
    assert browsed["objects"][0]["object_key"] == "docs/hello.txt"
    assert "private to its creating agent" in denied["error"]


def test_file_storage_pulser_public_bucket_is_shared(tmp_path):
    """
    Exercise the test_file_storage_pulser_public_bucket_is_shared regression
    scenario.
    """
    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )

    pulser.get_pulse_data(
        {
            "bucket_name": "shared-assets",
            "visibility": "public",
            "_caller": _caller("agent-a"),
        },
        pulse_name="bucket_create",
    )
    pulser.get_pulse_data(
        {
            "bucket_name": "shared-assets",
            "object_key": "docs/readme.txt",
            "text": "public text",
            "_caller": _caller("agent-a"),
        },
        pulse_name="object_save",
    )
    save_from_other = pulser.get_pulse_data(
        {
            "bucket_name": "shared-assets",
            "object_key": "data/info.json",
            "data": {"source": "agent-b", "ok": True},
            "_caller": _caller("agent-b"),
        },
        pulse_name="object_save",
    )
    browse_from_other = pulser.get_pulse_data(
        {
            "bucket_name": "shared-assets",
            "_caller": _caller("agent-b"),
        },
        pulse_name="bucket_browse",
    )
    load_from_other = pulser.get_pulse_data(
        {
            "bucket_name": "shared-assets",
            "object_key": "data/info.json",
            "response_format": "json",
            "_caller": _caller("agent-b"),
        },
        pulse_name="object_load",
    )

    assert save_from_other["status"] == "saved"
    assert browse_from_other["returned_count"] == 2
    assert sorted(entry["object_key"] for entry in browse_from_other["objects"]) == ["data/info.json", "docs/readme.txt"]
    assert load_from_other["data"] == {"ok": True, "source": "agent-b"}


def test_file_storage_pulser_list_bucket_respects_visibility_scope(tmp_path):
    """
    Exercise the test_file_storage_pulser_list_bucket_respects_visibility_scope
    regression scenario.
    """
    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )

    pulser.get_pulse_data(
        {
            "bucket_name": "owner-private",
            "visibility": "private",
            "_caller": _caller("agent-a", "Agent A"),
        },
        pulse_name="bucket_create",
    )
    pulser.get_pulse_data(
        {
            "bucket_name": "shared-team",
            "visibility": "public",
            "_caller": _caller("agent-a", "Agent A"),
        },
        pulse_name="bucket_create",
    )
    pulser.get_pulse_data(
        {
            "bucket_name": "other-private",
            "visibility": "private",
            "_caller": _caller("agent-b", "Agent B"),
        },
        pulse_name="bucket_create",
    )

    listed_for_agent_a = pulser.get_pulse_data(
        {"_caller": _caller("agent-a", "Agent A")},
        pulse_name="list_bucket",
    )
    listed_for_agent_b = pulser.get_pulse_data(
        {"_caller": _caller("agent-b", "Agent B")},
        pulse_name="list_bucket",
    )
    listed_public_only = pulser.get_pulse_data(
        {"visibility": "public", "_caller": _caller("agent-b", "Agent B")},
        pulse_name="list_bucket",
    )

    assert listed_for_agent_a["visibility_filter"] == "all"
    assert sorted(bucket["bucket_name"] for bucket in listed_for_agent_a["buckets"]) == ["owner-private", "shared-team"]
    assert sorted(bucket["bucket_name"] for bucket in listed_for_agent_b["buckets"]) == ["other-private", "shared-team"]
    assert listed_public_only["returned_count"] == 1
    assert listed_public_only["buckets"][0]["bucket_name"] == "shared-team"
    assert listed_public_only["buckets"][0]["visibility"] == "public"


def test_file_storage_pulser_supports_binary_blob_objects(tmp_path):
    """
    Exercise the test_file_storage_pulser_supports_binary_blob_objects regression
    scenario.
    """
    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )

    pulser.get_pulse_data(
        {
            "bucket_name": "media-assets",
            "visibility": "public",
            "_caller": _caller("agent-a"),
        },
        pulse_name="bucket_create",
    )
    saved = pulser.get_pulse_data(
        {
            "bucket_name": "media-assets",
            "object_key": "clips/demo.pdf",
            "base64_data": "JVBERi0xLjQKYmxvYgo=",
            "content_type": "application/pdf",
            "_caller": _caller("agent-a"),
        },
        pulse_name="object_save",
    )
    loaded = pulser.get_pulse_data(
        {
            "bucket_name": "media-assets",
            "object_key": "clips/demo.pdf",
            "response_format": "base64",
            "_caller": _caller("agent-b"),
        },
        pulse_name="object_load",
    )

    assert saved["status"] == "saved"
    assert saved["content_type"] == "application/pdf"
    assert loaded["content_type"] == "application/pdf"
    assert loaded["base64_data"] == "JVBERi0xLjQKYmxvYgo="
    assert base64.b64decode(loaded["base64_data"]) == b"%PDF-1.4\nblob\n"


def test_remote_use_practice_injects_verified_caller_context_into_get_pulse_data(tmp_path):
    """
    Exercise the
    test_remote_use_practice_injects_verified_caller_context_into_get_pulse_data
    regression scenario.
    """
    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )
    pulser.direct_auth_token = "shared-secret"

    with TestClient(pulser.app) as client:
        response = client.post(
            "/use_practice/get_pulse_data",
            json={
                "sender": "worker-1",
                "receiver": "file-storage",
                "msg_type": "get_pulse_data",
                "content": {
                    "pulse_name": "bucket_create",
                    "params": {
                        "bucket_name": "remote-owned",
                        "visibility": "private",
                    },
                },
                "caller_agent_address": {"pit_id": "worker-1", "plazas": []},
                "caller_plaza_token": None,
                "caller_direct_token": "shared-secret",
            },
        )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["owner_agent_id"] == "worker-1"
    assert result["owner_agent_name"] == "worker-1"


def test_file_storage_pulser_agent_config_loads_via_shared_agent_factory():
    """
    Exercise the
    test_file_storage_pulser_agent_config_loads_via_shared_agent_factory regression
    scenario.
    """
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "file_storage.pulser"
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "file-storage-token",
                "expires_in": 3600,
                "agent_id": "file-storage-id",
                "api_key": "file-storage-key",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeResponse([], status_code=200),
    ):
        agent = build_agent_from_config(str(config_path))

    assert isinstance(agent, FileStoragePulser)
    assert agent.name == "FileStoragePulser"
    assert agent.agent_id == "file-storage-id"
    assert agent.agent_card["party"] == "System"
    assert agent.agent_card["meta"]["party"] == "System"
    assert agent.agent_card["meta"]["storage_backend"] == "filesystem"
    assert {pulse["name"] for pulse in agent.supported_pulses} == {
        "bucket_create",
        "list_bucket",
        "bucket_browse",
        "object_save",
        "object_load",
    }
    assert sent_payloads[0]["url"] == "http://127.0.0.1:8011/register"
    assert sent_payloads[0]["payload"]["pit_type"] == "Pulser"


def test_file_storage_pulser_supports_s3_backend_via_logical_namespace(monkeypatch):
    """
    Exercise the test_file_storage_pulser_supports_s3_backend_via_logical_namespace
    regression scenario.
    """
    fake_client = FakeS3Client()
    monkeypatch.setattr(
        "phemacast.pulsers.file_storage_pulser.boto3.client",
        lambda *args, **kwargs: fake_client,
    )

    pulser = FileStoragePulser(
        config={
            "storage": {
                "type": "s3",
                "bucket": "backend-root",
                "prefix": "workspace-a",
            }
        },
        auto_register=False,
    )

    pulser.get_pulse_data(
        {
            "bucket_name": "s3-shared",
            "visibility": "public",
            "_caller": _caller("agent-a"),
        },
        pulse_name="bucket_create",
    )
    pulser.get_pulse_data(
        {
            "bucket_name": "s3-shared",
            "object_key": "snapshots/report.json",
            "data": {"value": 42},
            "_caller": _caller("agent-a"),
        },
        pulse_name="object_save",
    )
    loaded = pulser.get_pulse_data(
        {
            "bucket_name": "s3-shared",
            "object_key": "snapshots/report.json",
            "response_format": "json",
            "_caller": _caller("agent-b"),
        },
        pulse_name="object_load",
    )

    assert pulser.backend.backend_type == "s3"
    assert loaded["data"] == {"value": 42}
    assert ("backend-root", "workspace-a/data/s3-shared/snapshots/report.json") in fake_client.objects
