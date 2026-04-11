"""mcp-app's test suite for implementing apps.

These test modules ship with mcp-app and run against YOUR app —
not against the framework itself. They check that auth, user admin,
JWT enforcement, CLI wiring, tool protocol compliance, and SDK
coverage all work for your specific implementation.

How it works: your app's tests/framework/ directory has two files.
test_framework.py imports from these modules (identical across all
apps). conftest.py provides the app fixture pointing at YOUR App
object (the only file that differs per app).

Subsystem packages:
    mcp_app.testing.iam      — auth enforcement, user admin, JWT
    mcp_app.testing.wiring   — App object, CLI groups, tool protocol
    mcp_app.testing.tools    — SDK test coverage audit
    mcp_app.testing.health   — health endpoint

In the broader testing world, this pattern is sometimes called a
conformance suite, compliance suite, or TCK (Test Compatibility Kit).
"""

from mcp_app.testing.fixtures import app_fixture, tmp_env, require_binary

__all__ = ["app_fixture", "tmp_env", "require_binary"]
