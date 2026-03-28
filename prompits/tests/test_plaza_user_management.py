import os
import sys
import types

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
        self.oauth_codes = {}
        self.counter = 0
        self.refresh_counter = 0

    def _public_user(self, user: dict) -> dict:
        return {key: value for key, value in user.items() if key != "password"}

    def _create_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str = "",
        user_metadata: dict | None = None,
        provider: str = "password",
    ) -> dict:
        if email in self.user_ids_by_email:
            raise HTTPException(status_code=400, detail="Email already exists")
        self.counter += 1
        user_id = f"user-{self.counter}"
        metadata = dict(user_metadata or {})
        if display_name and not metadata.get("display_name"):
            metadata["display_name"] = display_name
        user = {
            "id": user_id,
            "email": email,
            "password": password,
            "user_metadata": metadata,
            "app_metadata": {"provider": provider, "providers": [provider]},
        }
        self.users_by_id[user_id] = user
        self.user_ids_by_email[email] = user_id
        return user

    def sign_up(self, email: str, password: str, display_name: str = "", user_metadata: dict | None = None):
        user = self._create_user(
            email=email,
            password=password,
            display_name=display_name,
            user_metadata=user_metadata,
        )
        user_id = user["id"]
        token = f"token-{user_id}"
        session = {"access_token": token, "refresh_token": f"refresh-{user_id}"}
        self.tokens[token] = user_id
        return {
            "user": self._public_user(user),
            "session": session,
        }

    def admin_create_user(self, attributes: dict):
        user = self._create_user(
            email=attributes["email"],
            password=attributes["password"],
            display_name=(attributes.get("user_metadata") or {}).get("display_name", ""),
            user_metadata=attributes.get("user_metadata") or {},
            provider="password",
        )
        return self._public_user(user)

    def list_users(self):
        return [self._public_user(user) for user in self.users_by_id.values()]

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
            "user": self._public_user(user),
            "session": session,
        }

    def get_user(self, access_token: str):
        user_id = self.tokens.get(access_token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = self.users_by_id[user_id]
        return self._public_user(user)

    def refresh_session(self, refresh_token: str):
        user_id = str(refresh_token or "").replace("refresh-", "", 1)
        if not user_id or user_id not in self.users_by_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        self.refresh_counter += 1
        access_token = f"token-{user_id}-refresh-{self.refresh_counter}"
        session = {"access_token": access_token, "refresh_token": refresh_token}
        self.tokens[access_token] = user_id
        return {
            "user": self._public_user(self.users_by_id[user_id]),
            "session": session,
        }

    def update_user(self, access_token: str, attributes: dict):
        user_id = self.tokens.get(access_token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = self.users_by_id[user_id]
        if "password" in attributes:
            user["password"] = attributes["password"]
        metadata = attributes.get("data")
        if isinstance(metadata, dict):
            next_metadata = dict(user.get("user_metadata") or {})
            next_metadata.update(metadata)
            user["user_metadata"] = next_metadata
        return self._public_user(user)

    def register_oauth_user(self, *, auth_code: str, email: str, username: str, display_name: str, provider: str):
        existing_id = self.user_ids_by_email.get(email)
        if existing_id:
            user = self.users_by_id[existing_id]
            user["user_metadata"].update({"username": username, "display_name": display_name})
            user["app_metadata"] = {"provider": provider, "providers": [provider]}
        else:
            user = self._create_user(
                email=email,
                password=f"oauth-{provider}",
                display_name=display_name,
                user_metadata={"username": username, "display_name": display_name},
                provider=provider,
            )
        self.oauth_codes[auth_code] = user["id"]
        return self._public_user(user)

    def exchange_code(self, auth_code: str):
        user_id = self.oauth_codes.get(auth_code)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid auth code")
        user = self.users_by_id[user_id]
        token = f"token-{user_id}"
        session = {"access_token": token, "refresh_token": f"refresh-{user_id}"}
        self.tokens[token] = user_id
        return {
            "user": self._public_user(user),
            "session": session,
        }


class FakeSupabaseModel:
    def __init__(self, **payload):
        self._payload = dict(payload)
        for key, value in payload.items():
            setattr(self, key, value)

    def dict(self):
        return dict(self._payload)


class FakeSupabaseAdmin:
    def __init__(self, auth_store: FakeSupabaseAuth):
        self.auth_store = auth_store

    def create_user(self, attributes):
        user = self.auth_store.admin_create_user(attributes)
        return FakeSupabaseModel(user=FakeSupabaseModel(**user))

    def list_users(self, page=None, per_page=None):
        return [FakeSupabaseModel(**user) for user in self.auth_store.list_users()]


class FakeSupabaseAuthApi:
    def __init__(self, auth_store: FakeSupabaseAuth):
        self.auth_store = auth_store
        self.admin = FakeSupabaseAdmin(auth_store)

    def sign_up(self, credentials):
        response = self.auth_store.sign_up(
            credentials["email"],
            credentials["password"],
            (credentials.get("options") or {}).get("data", {}).get("display_name", ""),
            (credentials.get("options") or {}).get("data") or {},
        )
        return FakeSupabaseModel(
            user=FakeSupabaseModel(**response["user"]),
            session=FakeSupabaseModel(**response["session"]),
        )

    def sign_in_with_password(self, credentials):
        response = self.auth_store.sign_in(credentials["email"], credentials["password"])
        return FakeSupabaseModel(
            user=FakeSupabaseModel(**response["user"]),
            session=FakeSupabaseModel(**response["session"]),
        )

    def get_user(self, access_token):
        user = self.auth_store.get_user(access_token)
        return FakeSupabaseModel(user=FakeSupabaseModel(**user))

    def exchange_code_for_session(self, params):
        response = self.auth_store.exchange_code(params["auth_code"])
        return FakeSupabaseModel(
            user=FakeSupabaseModel(**response["user"]),
            session=FakeSupabaseModel(**response["session"]),
        )


class FakeSupabaseClient:
    def __init__(self, auth_store: FakeSupabaseAuth):
        self.auth = FakeSupabaseAuthApi(auth_store)


@pytest.fixture
def plaza_client(monkeypatch):
    pool = InMemoryPool()
    pool.url = "https://example.supabase.co"
    pool.key = "publishable-key"
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    fake_auth = FakeSupabaseAuth()
    monkeypatch.setenv("PROMPITS_PUBLIC_URL", "http://127.0.0.1:8011")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr(
        agent,
        "_supabase_sign_up",
        lambda email, password, display_name=None, metadata=None: fake_auth.sign_up(
            email,
            password,
            display_name or "",
            metadata or {},
        ),
    )
    monkeypatch.setattr(agent, "_supabase_sign_in", lambda email, password: fake_auth.sign_in(email, password))
    monkeypatch.setattr(agent, "_get_supabase_user", lambda access_token: fake_auth.get_user(access_token))
    monkeypatch.setattr(agent, "_supabase_refresh_session", lambda refresh_token: fake_auth.refresh_session(refresh_token))
    monkeypatch.setattr(agent, "_supabase_update_user", lambda *, access_token, attributes: fake_auth.update_user(access_token, attributes))
    monkeypatch.setattr(
        agent,
        "_supabase_exchange_code_for_session",
        lambda *, auth_code, code_verifier, redirect_to=None: fake_auth.exchange_code(auth_code),
    )
    monkeypatch.setattr(agent, "_create_supabase_admin_user", lambda attributes: fake_auth.admin_create_user(attributes))

    with TestClient(agent.app) as client:
        yield client, agent, fake_auth


def test_plaza_user_management_roles_and_permissions(plaza_client):
    client, agent, fake_auth = plaza_client
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-page="users"' in resp.text
    assert "Role-based access for admin and user accounts" in resp.text

    config_resp = client.get("/api/ui_auth/config")
    assert config_resp.status_code == 200
    assert config_resp.json()["default_admin_ready"] is True

    admin_signin = client.post(
        "/api/ui_auth/signin",
        json={"identifier": "admin", "password": "admin"},
    )
    assert admin_signin.status_code == 200
    admin_payload = admin_signin.json()
    assert admin_payload["user"]["role"] == "admin"
    assert admin_payload["user"]["username"] == "admin"
    admin_token = admin_payload["session"]["access_token"]

    member_signup = client.post(
        "/api/ui_auth/signup",
        json={"username": "member", "password": "pw-member", "display_name": "Member One"},
    )
    assert member_signup.status_code == 200
    member_payload = member_signup.json()
    assert member_payload["user"]["role"] == "user"
    assert member_payload["user"]["username"] == "member"
    member_token = member_payload["session"]["access_token"]

    list_resp = client.get("/api/ui_users", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()["users"]) == 2

    member_id = member_payload["user"]["id"]
    promote_resp = client.patch(
        f"/api/ui_users/{member_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin", "status": "active", "display_name": "Admin Two"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["user"]["role"] == "admin"

    me_resp = client.get("/api/ui_auth/me", headers={"Authorization": f"Bearer {member_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["role"] == "admin"

    user_signup = client.post(
        "/api/ui_auth/signup",
        json={"username": "viewer", "password": "pw-viewer", "display_name": "Viewer One"},
    )
    assert user_signup.status_code == 200
    user_id = user_signup.json()["user"]["id"]
    user_token = user_signup.json()["session"]["access_token"]

    forbidden = client.patch(
        f"/api/ui_users/{member_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"role": "user"},
    )
    assert forbidden.status_code == 403

    self_list = client.get("/api/ui_users", headers={"Authorization": f"Bearer {user_token}"})
    assert self_list.status_code == 200
    assert len(self_list.json()["users"]) == 1
    assert self_list.json()["users"][0]["id"] == user_id
    assert agent._find_ui_user_by_username("admin")["role"] == "admin"
    assert fake_auth.user_ids_by_email["admin@plaza.local"]


def test_plaza_oauth_redirect_and_callback_syncs_user(plaza_client):
    client, agent, fake_auth = plaza_client

    start_resp = client.get("/api/ui_auth/oauth/google/start?next=/plazas", follow_redirects=False)
    assert start_resp.status_code == 307
    assert "provider=google" in start_resp.headers["location"]
    assert "code_challenge=" in start_resp.headers["location"]
    assert "redirect_to=http%3A%2F%2F127.0.0.1%3A8011%2Fapi%2Fui_auth%2Foauth%2Fcallback" in start_resp.headers["location"]

    state = start_resp.headers["location"].split("state=", 1)[1].split("&", 1)[0]
    fake_auth.register_oauth_user(
        auth_code="oauth-google-code",
        email="octocat@example.com",
        username="octocat",
        display_name="Octo Cat",
        provider="google",
    )

    callback_resp = client.get(f"/api/ui_auth/oauth/callback?code=oauth-google-code&state={state}")
    assert callback_resp.status_code == 200
    assert "localStorage.setItem('plaza.ui.authSession'" in callback_resp.text
    assert "Signed in with Google." in callback_resp.text

    oauth_user = agent._find_ui_user_by_username("octocat")
    assert oauth_user is not None
    assert oauth_user["auth_provider"] == "google"


def test_profile_update_and_password_change(plaza_client):
    client, agent, fake_auth = plaza_client

    signup = client.post(
        "/api/ui_auth/signup",
        json={"username": "member", "password": "pw-member", "display_name": "Member One"},
    )
    assert signup.status_code == 200
    payload = signup.json()
    user_id = payload["user"]["id"]
    token = payload["session"]["access_token"]

    profile_resp = client.patch(
        "/api/ui_auth/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Member Prime"},
    )
    assert profile_resp.status_code == 200
    assert profile_resp.json()["user"]["display_name"] == "Member Prime"
    assert agent._get_ui_user(user_id)["display_name"] == "Member Prime"

    wrong_password_resp = client.post(
        "/api/ui_auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrong-password", "new_password": "pw-member-2"},
    )
    assert wrong_password_resp.status_code == 400
    assert "Current password is incorrect" in wrong_password_resp.json()["detail"]

    change_password_resp = client.post(
        "/api/ui_auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "pw-member", "new_password": "pw-member-2"},
    )
    assert change_password_resp.status_code == 200
    assert change_password_resp.json()["message"] == "Password updated."

    with pytest.raises(HTTPException):
        fake_auth.sign_in("member@plaza.local", "pw-member")
    assert fake_auth.sign_in("member@plaza.local", "pw-member-2")["session"]["access_token"] == token


def test_oauth_profile_cannot_change_password(plaza_client):
    client, _agent, fake_auth = plaza_client

    start_resp = client.get("/api/ui_auth/oauth/google/start?next=/profile", follow_redirects=False)
    state = start_resp.headers["location"].split("state=", 1)[1].split("&", 1)[0]
    fake_auth.register_oauth_user(
        auth_code="oauth-profile-google-code",
        email="profile-oauth@example.com",
        username="profile-oauth",
        display_name="Profile OAuth",
        provider="google",
    )
    callback_resp = client.get(f"/api/ui_auth/oauth/callback?code=oauth-profile-google-code&state={state}")
    assert callback_resp.status_code == 200

    oauth_signin = fake_auth.exchange_code("oauth-profile-google-code")
    token = oauth_signin["session"]["access_token"]
    response = client.post(
        "/api/ui_auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "anything", "new_password": "new-secret"},
    )

    assert response.status_code == 400
    assert "password accounts" in response.json()["detail"]


def test_ui_auth_config_does_not_rebootstrap_after_startup(plaza_client, monkeypatch):
    client, agent, _fake_auth = plaza_client

    def fail_bootstrap():
        raise AssertionError("config route should not call default admin bootstrap")

    monkeypatch.setattr(agent, "_bootstrap_default_admin_if_needed", fail_bootstrap)

    response = client.get("/api/ui_auth/config")

    assert response.status_code == 200
    assert response.json()["auth_enabled"] is True


def test_default_admin_bootstrap_does_not_list_supabase_users(plaza_client, monkeypatch):
    _client, agent, fake_auth = plaza_client

    def fail_list_users():
        raise AssertionError("default admin bootstrap should not list all Supabase users")

    monkeypatch.setattr(fake_auth, "list_users", fail_list_users)

    agent._bootstrap_default_admin_if_needed()

    admin_user = agent._find_ui_user_by_username("admin")
    assert admin_user is not None
    assert admin_user["role"] == "admin"


def test_ui_auth_refresh_keeps_session_active(plaza_client):
    client, _agent, _fake_auth = plaza_client

    signin = client.post(
        "/api/ui_auth/signin",
        json={"identifier": "admin", "password": "admin"},
    )
    assert signin.status_code == 200
    signin_payload = signin.json()

    refresh = client.post(
        "/api/ui_auth/refresh",
        json={"refresh_token": signin_payload["session"]["refresh_token"]},
    )

    assert refresh.status_code == 200
    refresh_payload = refresh.json()
    assert refresh_payload["user"]["username"] == "admin"
    assert refresh_payload["session"]["refresh_token"] == signin_payload["session"]["refresh_token"]
    assert refresh_payload["session"]["access_token"] != signin_payload["session"]["access_token"]


def test_build_supabase_client_prefers_publishable_key_for_auth(monkeypatch):
    pool = InMemoryPool()
    pool.url = "https://example.supabase.co"
    pool.key = "service-role-from-pool"
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)

    captured = {}

    def fake_create_client(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return {"url": url, "key": key, "options": options}

    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-from-env")
    monkeypatch.setitem(sys.modules, "supabase", types.SimpleNamespace(create_client=fake_create_client))

    client = agent._build_supabase_client()

    assert client["url"] == "https://example.supabase.co"
    assert captured["key"] == "publishable-from-env"


def test_build_supabase_client_prefers_service_role_for_server_access(monkeypatch):
    pool = InMemoryPool()
    pool.url = "https://example.supabase.co"
    pool.key = "publishable-from-pool"
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)

    captured = {}

    def fake_create_client(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return {"url": url, "key": key, "options": options}

    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-from-env")
    monkeypatch.setitem(sys.modules, "supabase", types.SimpleNamespace(create_client=fake_create_client))

    client = agent._build_supabase_client(use_service_role=True)

    assert client["url"] == "https://example.supabase.co"
    assert captured["key"] == "service-role-from-env"


def test_get_supabase_pool_config_falls_back_to_env(monkeypatch):
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=InMemoryPool())

    monkeypatch.setenv("SUPABASE_URL", "https://env-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "env-service-role")

    assert agent._get_supabase_pool_config() == {
        "url": "https://env-project.supabase.co",
        "key": "env-service-role",
    }
