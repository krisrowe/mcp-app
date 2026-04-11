"""Import framework verification tests so pytest discovers them here.

The `app` fixture from conftest.py is available to all imported tests.
"""

from mcp_app.testing.wiring.test_app_wiring import *  # noqa: F401,F403
from mcp_app.testing.iam.test_auth_enforcement import *  # noqa: F401,F403
from mcp_app.testing.iam.test_admin_local import *  # noqa: F401,F403
from mcp_app.testing.iam.test_admin_errors import *  # noqa: F401,F403
from mcp_app.testing.tools.test_sdk_coverage_audit import *  # noqa: F401,F403
from mcp_app.testing.http.test_health import *  # noqa: F401,F403
