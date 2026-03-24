import os
import sys

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.core.plaza import PlazaAgent
from prompits.core.pool import Pool, PoolCap
from prompits.practices.plaza import PlazaPractice


class InMemoryPool(Pool):
    def __init__(self):
        super().__init__(
            "mem",
            "memory pool",
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.tables = {}
        self.connect()

    def connect(self):
        self.is_connected = True
        return True

    def disconnect(self):
        self.is_connected = False
        return True

    def _CreateTable(self, table_name, schema):
        self.tables.setdefault(table_name, {})
        return True

    def _TableExists(self, table_name):
        return table_name in self.tables

    def _Insert(self, table_name, data):
        self.tables.setdefault(table_name, {})
        row_id = data.get("id") or data.get("agent_id")
        self.tables[table_name][row_id] = dict(data)
        return True

    def _Query(self, query, params=None):
        return []

    def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
        table = self.tables.get(table_name, {})
        rows = list(table.values())
        if isinstance(id_or_where, dict):
            return [dict(row) for row in rows if all(row.get(key) == value for key, value in id_or_where.items())]
        return [dict(row) for row in rows]

    def store_memory(self, content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None):
        memory_table = table_name or self.MEMORY_TABLE
        if not self._TableExists(memory_table):
            self._CreateTable(memory_table, self.memory_table_schema())
        record = self._normalize_memory_record(content, memory_id, metadata, tags, memory_type)
        self._Insert(memory_table, record)
        return record

    def search_memory(self, query, limit=10, table_name=None):
        if not query:
            return []
        memory_table = table_name or self.MEMORY_TABLE
        rows = self._GetTableData(memory_table) if self._TableExists(memory_table) else []
        lowered = query.lower()
        return [row for row in rows if lowered in self._memory_search_text(row)][: max(int(limit), 0)]

    def create_table_practice(self):
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Create a table in the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "schema": {"type": "object"}},
            tags=["pool", "memory", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a table exists in the in-memory pool.",
            parameters={"table_name": {"type": "string"}},
            tags=["pool", "memory", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert one row into the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "data": {"type": "object"}},
            tags=["pool", "memory", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a query against the in-memory pool.",
            parameters={"query": {"type": "string"}, "params": {"type": "object"}},
            tags=["pool", "memory", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "id_or_where": {"type": "object"}, "table_schema": {"type": "object"}},
            tags=["pool", "memory", "read"],
            executor=lambda table_name, id_or_where=None, table_schema=None, **_: self._GetTableData(
                table_name,
                id_or_where,
                self._coerce_table_schema(table_schema),
            ),
        )

    def connect_practice(self):
        return self._build_operation_practice(
            operation_id="pool-connect",
            name="Pool Connect",
            description="Connect the in-memory pool.",
            parameters={},
            tags=["pool", "memory", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Disconnect the in-memory pool.",
            parameters={},
            tags=["pool", "memory", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the in-memory pool.",
            parameters={
                "content": {"type": "string"},
                "memory_id": {"type": "string"},
                "metadata": {"type": "object"},
                "tags": {"type": "array"},
                "memory_type": {"type": "string"},
                "table_name": {"type": "string"},
            },
            tags=["pool", "memory", "store"],
            executor=lambda content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None, **_: self.store_memory(
                content=content,
                memory_id=memory_id,
                metadata=metadata,
                tags=tags,
                memory_type=memory_type,
                table_name=table_name,
            ),
        )

    def search_memory_practice(self):
        return self._build_operation_practice(
            operation_id="pool-search-memory",
            name="Pool Search Memory",
            description="Search stored memory records in the in-memory pool.",
            parameters={"query": {"type": "string"}, "limit": {"type": "integer"}, "table_name": {"type": "string"}},
            tags=["pool", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )


class FakeSupabaseAuth:
    def __init__(self):
        self.users_by_id = {}
        self.user_ids_by_email = {}
        self.tokens = {}
        self.counter = 0

    def sign_up(self, email: str, password: str, display_name: str = ""):
        if email in self.user_ids_by_email:
            raise HTTPException(status_code=400, detail="Email already exists")
        self.counter += 1
        user_id = f"user-{self.counter}"
        user = {
            "id": user_id,
            "email": email,
            "password": password,
            "user_metadata": {"display_name": display_name},
        }
        self.users_by_id[user_id] = user
        self.user_ids_by_email[email] = user_id
        token = f"token-{user_id}"
        session = {"access_token": token, "refresh_token": f"refresh-{user_id}"}
        self.tokens[token] = user_id
        return {
            "user": {k: v for k, v in user.items() if k != "password"},
            "session": session,
        }

    def sign_in(self, email: str, password: str):
        user_id = self.user_ids_by_email.get(email)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unknown email")
        user = self.users_by_id[user_id]
        if user["password"] != password:
            raise HTTPException(status_code=401, detail="Invalid password")
        token = f"token-{user_id}"
        session = {"access_token": token, "refresh_token": f"refresh-{user_id}"}
        self.tokens[token] = user_id
        return {
            "user": {k: v for k, v in user.items() if k != "password"},
            "session": session,
        }

    def get_user(self, access_token: str):
        user_id = self.tokens.get(access_token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = self.users_by_id[user_id]
        return {k: v for k, v in user.items() if k != "password"}


@pytest.fixture
def plaza_client(monkeypatch):
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    fake_auth = FakeSupabaseAuth()
    monkeypatch.setattr(agent, "_has_supabase_auth", lambda: True)
    monkeypatch.setattr(agent, "_has_supabase_service_role", lambda: False)
    monkeypatch.setattr(agent, "_supabase_sign_up", lambda email, password, display_name=None: fake_auth.sign_up(email, password, display_name or ""))
    monkeypatch.setattr(agent, "_supabase_sign_in", lambda email, password: fake_auth.sign_in(email, password))
    monkeypatch.setattr(agent, "_get_supabase_user", lambda access_token: fake_auth.get_user(access_token))

    with TestClient(agent.app) as client:
        yield client


def test_plaza_user_management_roles_and_permissions(plaza_client):
    resp = plaza_client.get("/")
    assert resp.status_code == 200
    assert 'data-page="users"' in resp.text
    assert "Role-based access for admin, moderator, and user" in resp.text

    admin_signup = plaza_client.post(
        "/api/ui_auth/signup",
        json={"email": "admin@example.com", "password": "pw-admin", "display_name": "Admin One"},
    )
    assert admin_signup.status_code == 200
    admin_payload = admin_signup.json()
    assert admin_payload["user"]["role"] == "admin"
    admin_token = admin_payload["session"]["access_token"]

    member_signup = plaza_client.post(
        "/api/ui_auth/signup",
        json={"email": "member@example.com", "password": "pw-member", "display_name": "Member One"},
    )
    assert member_signup.status_code == 200
    member_payload = member_signup.json()
    assert member_payload["user"]["role"] == "user"
    member_token = member_payload["session"]["access_token"]

    list_resp = plaza_client.get("/api/ui_users", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()["users"]) == 2

    member_id = member_payload["user"]["id"]
    promote_resp = plaza_client.patch(
        f"/api/ui_users/{member_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "moderator", "status": "active", "display_name": "Moderator One"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["user"]["role"] == "moderator"

    me_resp = plaza_client.get("/api/ui_auth/me", headers={"Authorization": f"Bearer {member_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["role"] == "moderator"

    user_signup = plaza_client.post(
        "/api/ui_auth/signup",
        json={"email": "viewer@example.com", "password": "pw-viewer", "display_name": "Viewer One"},
    )
    assert user_signup.status_code == 200
    user_id = user_signup.json()["user"]["id"]
    user_token = user_signup.json()["session"]["access_token"]

    forbidden = plaza_client.patch(
        f"/api/ui_users/{user_id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"role": "admin"},
    )
    assert forbidden.status_code == 403

    self_list = plaza_client.get("/api/ui_users", headers={"Authorization": f"Bearer {user_token}"})
    assert self_list.status_code == 200
    assert len(self_list.json()["users"]) == 1
    assert self_list.json()["users"][0]["id"] == user_id
