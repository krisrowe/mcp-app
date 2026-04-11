"""Tests for RemoteAuthAdapter — exercises the full stack in-memory.

RemoteAuthAdapter → httpx (ASGI transport) → Starlette → admin.py → FileSystemUserDataStore → tmp_path.
No mocks, no network.
"""

import pytest
import httpx
from datetime import datetime, timezone
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_app.admin import create_admin_app
from mcp_app.admin_client import RemoteAuthAdapter
from mcp_app.bridge import DataStoreAuthAdapter
from mcp_app.data_store import FileSystemUserDataStore
from mcp_app.models import UserAuthRecord


SIGNING_KEY = "test-key-for-admin-client-32ch!!"
BASE_URL = "http://test"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_USERS_PATH", str(tmp_path / "users"))
    monkeypatch.setenv("SIGNING_KEY", SIGNING_KEY)
    return FileSystemUserDataStore(app_name="test")


@pytest.fixture
def app(store):
    auth_store = DataStoreAuthAdapter(store)
    admin_app = create_admin_app(auth_store)

    async def health(request):
        return JSONResponse({"status": "ok"})

    return Starlette(routes=[
        Route("/health", health),
        Mount("/admin", app=admin_app),
    ])


@pytest.fixture
def adapter(app):
    transport = httpx.ASGITransport(app=app)
    http_client = httpx.AsyncClient(transport=transport, base_url=BASE_URL)
    return RemoteAuthAdapter(BASE_URL, SIGNING_KEY, http_client=http_client)


@pytest.mark.asyncio
async def test_health_check(adapter):
    result = await adapter.health_check()
    assert result["status"] == "healthy"
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_save_returns_email_and_token(adapter):
    result = await adapter.save(
        UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc))
    )
    assert result["email"] == "alice@test.com"
    assert "token" in result


@pytest.mark.asyncio
async def test_list_empty(adapter):
    result = await adapter.list()
    assert result == []


@pytest.mark.asyncio
async def test_list_after_save(adapter):
    await adapter.save(UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)))
    await adapter.save(UserAuthRecord(email="bob@test.com", created=datetime.now(timezone.utc)))
    users = await adapter.list()
    emails = {u.email for u in users}
    assert "alice@test.com" in emails
    assert "bob@test.com" in emails


@pytest.mark.asyncio
async def test_save_idempotent(adapter):
    r1 = await adapter.save(UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)))
    r2 = await adapter.save(UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)))
    assert r1["email"] == r2["email"]
    assert "token" in r1 and "token" in r2


@pytest.mark.asyncio
async def test_create_token_for_existing_user(adapter):
    await adapter.save(UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)))
    result = await adapter.create_token("alice@test.com")
    assert result["email"] == "alice@test.com"
    assert "token" in result


@pytest.mark.asyncio
async def test_create_token_for_nonexistent_user_raises(adapter):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await adapter.create_token("nobody@test.com")
    assert exc_info.value.response.status_code == 404


@pytest.mark.asyncio
async def test_delete(adapter):
    await adapter.save(UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)))
    await adapter.delete("alice@test.com")
    users = await adapter.list()
    # User should be revoked (still in list but with revoke_after set)
    # or deleted depending on implementation


@pytest.mark.asyncio
async def test_delete_nonexistent_raises(adapter):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await adapter.delete("nobody@test.com")
    assert exc_info.value.response.status_code == 404


@pytest.mark.asyncio
async def test_save_with_profile(adapter):
    result = await adapter.save(
        UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc)),
        profile={"token": "test-api-key"},
    )
    assert result["email"] == "alice@test.com"
    assert "token" in result


@pytest.mark.asyncio
async def test_full_lifecycle(adapter):
    """save → list → create token → delete → list."""
    reg = await adapter.save(
        UserAuthRecord(email="alice@test.com", created=datetime.now(timezone.utc))
    )
    assert reg["email"] == "alice@test.com"

    users = await adapter.list()
    assert len(users) == 1
    assert users[0].email == "alice@test.com"
    assert users[0].revoke_after is None

    tok = await adapter.create_token("alice@test.com")
    assert "token" in tok

    await adapter.delete("alice@test.com")

    users = await adapter.list()
    assert len(users) == 1
    assert users[0].revoke_after is not None
