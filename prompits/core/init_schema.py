"""
Built-in schema declarations for `prompits.core.init_schema`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the core package defines the
shared abstractions that the rest of the runtime builds on.

Important callables in this file include `agent_practices_schema_dict`,
`agent_practices_table_schema`, `builtin_schema_cards`, and
`pulse_pulser_pairs_table_schema`, which capture the primary workflow implemented by
the module.
"""

from __future__ import annotations

from typing import Any, Dict, List

from prompits.core.schema import TableSchema


# Stable IDs for built-in schema pits.
SCHEMA_ID_PLAZA_CREDENTIALS = "3d07cb8a-11a7-4f7a-b95f-9f6ab3547a01"
SCHEMA_ID_PLAZA_LOGIN_HISTORY = "ac42f84f-f4e0-499e-9ee0-a7c127835d4b"
SCHEMA_ID_PLAZA_DIRECTORY = "27d8df89-0f4d-4d0d-bba8-cc9de4dd08f3"
SCHEMA_ID_AGENT_PRACTICES = "d8a3c4c9-68d1-447f-9f50-cb65d5762446"
SCHEMA_ID_PULSE_PULSER_PAIRS = "60b9df10-00b7-4a1b-9080-a1c66fe8e4f5"
SCHEMA_ID_PLAZA_UI_USERS = "0c9fd25c-a465-47a7-bca7-7f512c5606d8"
SCHEMA_ID_PLAZA_UI_AGENT_KEYS = "7e2d6f8c-32b8-4ec6-b1f4-8d9a2c64ef10"


def plaza_credentials_schema_dict() -> Dict[str, Any]:
    """Handle Plaza credentials schema dict."""
    return {
        "name": "plaza_credentials",
        "description": "Persisted Plaza credentials by agent and plaza URL",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "plaza_url": {"type": "string"},
            "agent_id": {"type": "string"},
            "agent_name": {"type": "string"},
            "api_key": {"type": "string"},
            "updated_at": {"type": "datetime"},
        },
    }


def plaza_login_history_schema_dict() -> Dict[str, Any]:
    """Handle Plaza login history schema dict."""
    return {
        "name": "plaza_login_history",
        "description": "Login/relogin events by agent_id",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "agent_id": {"type": "string"},
            "agent_name": {"type": "string"},
            "address": {"type": "string"},
            "event": {"type": "string"},
            "timestamp": {"type": "float"},
        },
    }


def plaza_directory_schema_dict() -> Dict[str, Any]:
    """Handle Plaza directory schema dict."""
    return {
        "name": "plaza_directory",
        "description": "Plaza directory entries",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "agent_id": {"type": "string"},
            "name": {"type": "string"},
            "type": {"type": "string"},
            "description": {"type": "string"},
            "owner": {"type": "string"},
            "address": {"type": "string"},
            "meta": {"type": "json"},
            "card": {"type": "json"},
            "updated_at": {"type": "datetime"},
        },
    }


def agent_practices_schema_dict() -> Dict[str, Any]:
    """Handle agent practices schema dict."""
    return {
        "name": "agent_practices",
        "description": "Persisted practice metadata by agent and practice id",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "agent_name": {"type": "string"},
            "practice_id": {"type": "string"},
            "practice_name": {"type": "string"},
            "practice_description": {"type": "string"},
            "practice_data": {"type": "json"},
            "is_deleted": {"type": "boolean"},
            "updated_at": {"type": "datetime"},
        },
    }


def pulse_pulser_pairs_schema_dict() -> Dict[str, Any]:
    """Handle pulse pulser pairs schema dict."""
    return {
        "name": "pulse_pulser_pairs",
        "description": "Pulse-to-pulser availability index for fast pulser lookup.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "pulse_id": {"type": "string"},
            "pulse_directory_id": {"type": "string"},
            "pulse_name": {"type": "string"},
            "pulse_address": {"type": "string"},
            "pulse_definition": {"type": "json"},
            "status": {"type": "string"},
            "is_complete": {"type": "boolean"},
            "completion_status": {"type": "string"},
            "completion_errors": {"type": "json"},
            "pulser_id": {"type": "string"},
            "pulser_directory_id": {"type": "string"},
            "pulser_name": {"type": "string"},
            "pulser_address": {"type": "string"},
            "input_schema": {"type": "json"},
            "updated_at": {"type": "datetime"},
        },
    }


def plaza_ui_users_schema_dict() -> Dict[str, Any]:
    """Handle Plaza UI users schema dict."""
    return {
        "name": "plaza_ui_users",
        "description": "Plaza UI users authenticated through Supabase Auth with local role assignments.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "username": {"type": "string"},
            "email": {"type": "string"},
            "display_name": {"type": "string"},
            "profile_public": {"type": "boolean"},
            "public_email": {"type": "boolean"},
            "role": {"type": "string"},
            "status": {"type": "string"},
            "auth_provider": {"type": "string"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
            "last_sign_in_at": {"type": "datetime"},
        },
    }


def plaza_ui_agent_keys_schema_dict() -> Dict[str, Any]:
    """Handle Plaza UI agent keys schema dict."""
    return {
        "name": "plaza_ui_agent_keys",
        "description": "Named Plaza owner keys that let UI users claim ownership for registered agents.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "user_id": {"type": "string"},
            "username": {"type": "string"},
            "display_name": {"type": "string"},
            "email": {"type": "string"},
            "name": {"type": "string"},
            "secret": {"type": "string"},
            "status": {"type": "string"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
            "last_used_at": {"type": "datetime"},
        },
    }


def plaza_credentials_table_schema() -> TableSchema:
    """Return the Plaza credentials table schema."""
    return TableSchema(plaza_credentials_schema_dict())


def plaza_login_history_table_schema() -> TableSchema:
    """Return the Plaza login history table schema."""
    return TableSchema(plaza_login_history_schema_dict())


def plaza_directory_table_schema() -> TableSchema:
    """Return the Plaza directory table schema."""
    return TableSchema(plaza_directory_schema_dict())


def agent_practices_table_schema() -> TableSchema:
    """Return the agent practices table schema."""
    return TableSchema(agent_practices_schema_dict())


def pulse_pulser_pairs_table_schema() -> TableSchema:
    """Return the pulse pulser pairs table schema."""
    return TableSchema(pulse_pulser_pairs_schema_dict())


def plaza_ui_users_table_schema() -> TableSchema:
    """Return the Plaza UI users table schema."""
    return TableSchema(plaza_ui_users_schema_dict())


def plaza_ui_agent_keys_table_schema() -> TableSchema:
    """Return the Plaza UI agent keys table schema."""
    return TableSchema(plaza_ui_agent_keys_schema_dict())


def builtin_schema_cards(plaza_url: str) -> List[Dict[str, Any]]:
    """Return the builtin schema cards."""
    normalized_plaza = (plaza_url or "").rstrip("/")
    return [
        {
            "schema_id": SCHEMA_ID_PLAZA_CREDENTIALS,
            "name": "Schema: plaza_credentials",
            "card": {
                "name": "Schema: plaza_credentials",
                "description": "Built-in table schema for persisted Plaza credentials.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table"],
                "pit_address": {"pit_id": SCHEMA_ID_PLAZA_CREDENTIALS, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "plaza_credentials", "schema_kind": "table", "schema": plaza_credentials_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_PLAZA_LOGIN_HISTORY,
            "name": "Schema: plaza_login_history",
            "card": {
                "name": "Schema: plaza_login_history",
                "description": "Built-in table schema for Plaza login/relogin history.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table"],
                "pit_address": {"pit_id": SCHEMA_ID_PLAZA_LOGIN_HISTORY, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "plaza_login_history", "schema_kind": "table", "schema": plaza_login_history_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_PLAZA_DIRECTORY,
            "name": "Schema: plaza_directory",
            "card": {
                "name": "Schema: plaza_directory",
                "description": "Built-in table schema for the Plaza searchable directory.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table"],
                "pit_address": {"pit_id": SCHEMA_ID_PLAZA_DIRECTORY, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "plaza_directory", "schema_kind": "table", "schema": plaza_directory_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_AGENT_PRACTICES,
            "name": "Schema: agent_practices",
            "card": {
                "name": "Schema: agent_practices",
                "description": "Built-in table schema for persisted agent practice metadata.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table"],
                "pit_address": {"pit_id": SCHEMA_ID_AGENT_PRACTICES, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "agent_practices", "schema_kind": "table", "schema": agent_practices_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_PULSE_PULSER_PAIRS,
            "name": "Schema: pulse_pulser_pairs",
            "card": {
                "name": "Schema: pulse_pulser_pairs",
                "description": "Built-in table schema for pulse-to-pulser availability records.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table"],
                "pit_address": {"pit_id": SCHEMA_ID_PULSE_PULSER_PAIRS, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "pulse_pulser_pairs", "schema_kind": "table", "schema": pulse_pulser_pairs_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_PLAZA_UI_USERS,
            "name": "Schema: plaza_ui_users",
            "card": {
                "name": "Schema: plaza_ui_users",
                "description": "Built-in table schema for Plaza UI users and role assignments.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table", "auth"],
                "pit_address": {"pit_id": SCHEMA_ID_PLAZA_UI_USERS, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "plaza_ui_users", "schema_kind": "table", "schema": plaza_ui_users_schema_dict()},
            },
        },
        {
            "schema_id": SCHEMA_ID_PLAZA_UI_AGENT_KEYS,
            "name": "Schema: plaza_ui_agent_keys",
            "card": {
                "name": "Schema: plaza_ui_agent_keys",
                "description": "Built-in table schema for Plaza UI user-managed agent owner keys.",
                "pit_type": "Schema",
                "owner": "Plaza",
                "tags": ["schema", "system", "table", "auth"],
                "pit_address": {"pit_id": SCHEMA_ID_PLAZA_UI_AGENT_KEYS, "plazas": [normalized_plaza] if normalized_plaza else []},
                "meta": {"schema_name": "plaza_ui_agent_keys", "schema_kind": "table", "schema": plaza_ui_agent_keys_schema_dict()},
            },
        },
    ]
