"""mcp_app.testing — verification tests for mcp-app solutions.

Provides test modules organized by subsystem that any mcp-app solution
can import and run against itself:

    from mcp_app.testing.iam import *       # auth, user admin, JWT
    from mcp_app.testing.wiring import *    # App object, CLI groups, tool protocol
    from mcp_app.testing.tools import *     # SDK coverage audit
    from mcp_app.testing.http import *      # health endpoint

The solution provides one fixture (conftest.py returning its App
instance) and gets all tests for free.
"""

from mcp_app.testing.fixtures import app_fixture, tmp_env, require_binary

__all__ = ["app_fixture", "tmp_env", "require_binary"]
