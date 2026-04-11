"""mcp_app.testing — framework contract tests for mcp-app solutions.

Provides fixtures, contract tests, and audit tools that validate
any app built with mcp-app. Solutions include these tests alongside
their own business logic tests.

Usage in a solution's conftest.py:

    from mcp_app.testing import app_fixture
    # or import the App directly:
    # from my_app_mcp import app

The contract tests discover the app via the mcp_app.apps entry
point group, or solutions provide the fixture explicitly.
"""

from mcp_app.testing.fixtures import app_fixture, tmp_env, require_binary

__all__ = ["app_fixture", "tmp_env", "require_binary"]
