"""Tests for mcp-app bootstrap — tool discovery, store building, app building."""

import os
import sys
import pytest
from pathlib import Path
from types import ModuleType

from mcp_app.bootstrap import (
    _resolve_class,
    _discover_tools_from_module,
    _build_mcp,
    _build_store,
    build_asgi,
    STORE_ALIASES,
    MIDDLEWARE_ALIASES,
)


# --- Class resolution ---

def test_resolve_alias():
    cls = _resolve_class("filesystem", STORE_ALIASES)
    from mcp_app.data_store import FileSystemUserDataStore
    assert cls is FileSystemUserDataStore


def test_resolve_module_path():
    cls = _resolve_class("mcp_app.data_store.FileSystemUserDataStore", STORE_ALIASES)
    from mcp_app.data_store import FileSystemUserDataStore
    assert cls is FileSystemUserDataStore


def test_resolve_unknown_alias():
    with pytest.raises(ValueError, match="Unknown alias"):
        _resolve_class("nonexistent", STORE_ALIASES)


def test_resolve_middleware_alias():
    cls = _resolve_class("user-identity", MIDDLEWARE_ALIASES)
    from mcp_app.middleware import JWTMiddleware
    assert cls is JWTMiddleware


# --- Tool discovery ---

def test_discover_tools_from_module(tmp_path):
    """Create a temp module with async functions and discover them."""
    mod_dir = tmp_path / "test_tools_pkg"
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("")
    (mod_dir / "tools.py").write_text(
        "async def public_tool() -> dict:\n"
        "    return {'ok': True}\n\n"
        "async def another_tool(x: int) -> dict:\n"
        "    return {'x': x}\n\n"
        "async def _private() -> dict:\n"
        "    return {}\n\n"
        "def sync_func() -> dict:\n"
        "    return {}\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        import importlib
        mod = importlib.import_module("test_tools_pkg.tools")
        tools = _discover_tools_from_module(mod)
        names = [f.__name__ for f in tools]
        assert "public_tool" in names
        assert "another_tool" in names
        assert "_private" not in names
        assert "sync_func" not in names
    finally:
        sys.path.remove(str(tmp_path))


# --- Store building ---

def test_build_store_filesystem(tmp_path):
    os.environ["APP_USERS_PATH"] = str(tmp_path / "users")
    try:
        store = _build_store("test-app")
        assert store.base == tmp_path / "users"
    finally:
        del os.environ["APP_USERS_PATH"]


def test_build_store_default_name():
    store = _build_store("mcp-app")
    assert "mcp-app" in str(store.base)


# --- MCP building ---

def test_build_mcp_registers_tools(tmp_path):
    mod_dir = tmp_path / "mcp_test_pkg"
    mod_dir.mkdir()
    (mod_dir / "__init__.py").write_text("")
    (mod_dir / "tools.py").write_text(
        "async def greet(name: str) -> dict:\n"
        "    \"\"\"Say hello.\"\"\"\n"
        "    return {'message': f'hello {name}'}\n"
    )
    sys.path.insert(0, str(tmp_path))
    try:
        import importlib
        mod = importlib.import_module("mcp_test_pkg.tools")
        mcp = _build_mcp("test", mod)
        tool_names = [t.name for t in mcp._tool_manager.list_tools()]
        assert "greet" in tool_names
    finally:
        sys.path.remove(str(tmp_path))


# --- Full app building ---

def test_build_asgi_creates_app(tmp_path):
    os.environ["APP_USERS_PATH"] = str(tmp_path / "users")
    os.environ["SIGNING_KEY"] = "test-key-32chars-minimum-length!!"
    try:
        mod_dir = tmp_path / "asgi_test_pkg"
        mod_dir.mkdir()
        (mod_dir / "__init__.py").write_text("")
        (mod_dir / "tools.py").write_text(
            "async def ping() -> dict:\n"
            "    return {'pong': True}\n"
        )
        sys.path.insert(0, str(tmp_path))
        import importlib
        mod = importlib.import_module("asgi_test_pkg.tools")
        app, mcp, store = build_asgi("test", mod)
        assert app is not None
        assert len(mcp._tool_manager.list_tools()) == 1
        sys.path.remove(str(tmp_path))
    finally:
        del os.environ["APP_USERS_PATH"]
        del os.environ["SIGNING_KEY"]
