"""Import mcp-app's test suite so pytest runs it against the app
defined in conftest.py.

This file is identical in every mcp-app solution. The imports pull
in tests for auth, user admin, JWT enforcement, CLI wiring, tool
protocol, and SDK coverage. conftest.py is the only file that
changes per solution — it provides the app fixture.
"""

from mcp_app.testing.iam.test_auth_enforcement import *  # noqa: F401,F403
from mcp_app.testing.iam.test_admin_local import *  # noqa: F401,F403
from mcp_app.testing.iam.test_admin_errors import *  # noqa: F401,F403
from mcp_app.testing.wiring.test_app_wiring import *  # noqa: F401,F403
from mcp_app.testing.tools.test_sdk_coverage_audit import *  # noqa: F401,F403
from mcp_app.testing.health.test_health import *  # noqa: F401,F403
