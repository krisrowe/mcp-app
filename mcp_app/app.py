"""App — single composition root for mcp-app solutions.

Declares an app's identity and wiring once. Both runtime entry
points (serve, stdio, admin) and tooling (tests, audits, deploy)
derive from this one object.
"""

from dataclasses import dataclass, field
from functools import cached_property
from types import ModuleType

import click


@dataclass
class App:
    """An mcp-app solution.

    Args:
        name: App name (server name, store paths, CLI prefixes).
        tools_module: Python module containing async tool functions.
        sdk_package: The SDK package (for test tooling to find SDK
            tests). Optional — not needed for runtime.
        store_backend: Store alias or module path. Default: "filesystem".
        middleware: Custom middleware list. None = user-identity (default).
            Empty list = no auth.
        profile_model: Pydantic BaseModel for typed user profile.
            None = no profile (data-owning apps).
        profile_expand: If True, admin CLI generates individual flags
            from profile model fields. If False, accepts --profile
            as JSON or @file.
    """

    name: str
    tools_module: ModuleType
    sdk_package: ModuleType | None = None
    store_backend: str = "filesystem"
    middleware: list[str] | None = None
    profile_model: type | None = None
    profile_expand: bool = True

    def __post_init__(self):
        if self.profile_model is not None:
            from mcp_app.context import register_profile
            register_profile(self.profile_model, expand=self.profile_expand)

    @cached_property
    def mcp_cli(self) -> click.Group:
        """Click group for MCP server commands (serve, stdio)."""
        from mcp_app.cli import create_mcp_cli
        return create_mcp_cli(self.name, tools_module=self.tools_module)

    @cached_property
    def admin_cli(self) -> click.Group:
        """Click group for admin commands (connect, users, tokens, health)."""
        from mcp_app.cli import create_admin_cli
        return create_admin_cli(self.name)

    def build_asgi(self):
        """Build the full ASGI app. Returns (app, mcp, store)."""
        from mcp_app.bootstrap import build_asgi
        return build_asgi(
            self.name,
            self.tools_module,
            store_backend=self.store_backend,
            middleware=self.middleware,
        )

    def run_stdio(self, user: str) -> None:
        """Build and run stdio transport."""
        from mcp_app.bootstrap import run_stdio
        run_stdio(
            self.name,
            self.tools_module,
            user,
            store_backend=self.store_backend,
        )
