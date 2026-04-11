"""mcp-app CLI — remote admin and app CLI factories."""

import asyncio
import json
import os
from pathlib import Path
from types import ModuleType

import click


# --- Config helpers ---

def _config_dir(app_name: str | None = None) -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    name = app_name or "mcp-app"
    return Path(xdg) / name


def _load_setup(app_name: str | None = None) -> dict:
    path = _config_dir(app_name) / "setup.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_setup(data: dict, app_name: str | None = None):
    path = _config_dir(app_name) / "setup.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _resolve_url(url: str | None, app_name: str | None = None) -> str:
    result = url or os.environ.get("MCP_APP_URL") or _load_setup(app_name).get("url")
    if not result:
        raise click.ClickException(
            "No base URL. Use --url, set MCP_APP_URL, or run: mcp-app setup <url>"
        )
    return result


def _resolve_signing_key(key: str | None, app_name: str | None = None) -> str:
    result = key or os.environ.get("MCP_APP_SIGNING_KEY") or _load_setup(app_name).get("signing_key")
    if not result:
        raise click.ClickException(
            "No signing key. Use --signing-key, set MCP_APP_SIGNING_KEY, or include in setup."
        )
    return result


def _client(url: str | None, signing_key: str | None, app_name: str | None = None):
    from mcp_app.admin_client import RemoteAuthAdapter
    return RemoteAuthAdapter(
        _resolve_url(url, app_name),
        _resolve_signing_key(signing_key, app_name),
    )


def _run(coro):
    return asyncio.run(coro)


# --- Profile helpers ---

def _parse_profile_value(value: str) -> dict:
    if value.startswith("@"):
        path = Path(value[1:])
        if not path.exists():
            raise click.ClickException(f"Profile file not found: {path}")
        return json.loads(path.read_text())
    return json.loads(value)


def _collect_profile_from_flags(ctx: click.Context) -> dict | None:
    from mcp_app.context import get_profile_model
    model = get_profile_model()
    if not model:
        return None
    data = {}
    for field_name in model.model_fields:
        value = ctx.params.get(field_name.replace("-", "_"))
        if value is not None:
            data[field_name] = value
    return data if data else None


def _validate_profile(data: dict) -> dict:
    from mcp_app.context import get_profile_model
    model = get_profile_model()
    if model and data:
        obj = model(**data)
        return obj.model_dump()
    return data


def _profile_help_text() -> str:
    from mcp_app.context import get_profile_model
    model = get_profile_model()
    if not model:
        return ""
    lines = ["Required fields:"]
    for name, field in model.model_fields.items():
        req = "required" if field.is_required() else "optional"
        desc = field.description or ""
        type_name = field.annotation.__name__ if hasattr(field.annotation, '__name__') else str(field.annotation)
        lines.append(f"  {name} ({type_name}, {req}) {desc}")
    return "\n".join(lines)


# --- Main CLI (remote admin only) ---

@click.group()
def main():
    """mcp-app — remote admin for deployed instances."""
    pass


@main.command()
@click.argument("url")
@click.option("--signing-key", default=None, help="Signing key for admin auth.")
def setup(url, signing_key):
    """Configure connection to a deployed instance."""
    data = _load_setup()
    data["url"] = url
    if signing_key:
        data["signing_key"] = signing_key
    _save_setup(data)
    click.echo(f"Configured: {url}")


@main.command()
@click.option("--url", default=None)
@click.option("--signing-key", default=None)
def health(url, signing_key):
    """Check health of a deployed instance."""
    from mcp_app.admin_client import RemoteAuthAdapter
    resolved_url = _resolve_url(url)
    client = RemoteAuthAdapter(resolved_url, "unused")
    result = _run(client.health_check())
    click.echo(f"{result['status']} ({result['status_code']})")


@main.group()
def users():
    """Manage users on a deployed instance."""
    pass


@users.command("list")
@click.option("--url", default=None)
@click.option("--signing-key", default=None)
def users_list(url, signing_key):
    """List registered users."""
    result = _run(_client(url, signing_key).list())
    if not result:
        click.echo("No users.")
        return
    for user in result:
        status = " (revoked)" if user.revoke_after else ""
        click.echo(f"  {user.email}{status}")


@users.command("add")
@click.argument("email")
@click.option("--profile", "profile_str", default=None,
              help="Profile data as JSON string or @file.")
@click.option("--url", default=None)
@click.option("--signing-key", default=None)
def users_add(email, profile_str, url, signing_key):
    """Register a user and get their token."""
    from datetime import datetime, timezone
    from mcp_app.models import UserAuthRecord

    profile = None
    if profile_str:
        profile = _parse_profile_value(profile_str)
        profile = _validate_profile(profile)

    result = _run(_client(url, signing_key).save(
        UserAuthRecord(email=email, created=datetime.now(timezone.utc)),
        profile=profile,
    ))
    click.echo(f"Registered: {result['email']}")
    if "token" in result:
        click.echo(f"Token: {result['token']}")


@users.command("revoke")
@click.argument("email")
@click.option("--url", default=None)
@click.option("--signing-key", default=None)
def users_revoke(email, url, signing_key):
    """Revoke a user's access."""
    _run(_client(url, signing_key).delete(email))
    click.echo(f"Revoked: {email}")


@main.group()
def tokens():
    """Manage tokens on a deployed instance."""
    pass


@tokens.command("create")
@click.argument("email")
@click.option("--url", default=None)
@click.option("--signing-key", default=None)
def tokens_create(email, url, signing_key):
    """Create a new token for an existing user."""
    result = _run(_client(url, signing_key).create_token(email))
    click.echo(f"Token for {result['email']}: {result['token']}")


@main.command("admin-tools")
def admin_tools():
    """Run MCP admin tools server over stdio."""
    from mcp_app.admin_tools import mcp as admin_mcp
    admin_mcp.run(transport="stdio")


# --- App CLI factories ---

def _get_auth_store(app_name: str):
    """Get the auth store based on connect config — local or remote."""
    cfg = _load_setup(app_name)
    if not cfg:
        raise click.ClickException(
            f"Not configured. Run:\n"
            f"  {app_name}-admin connect local\n"
            f"  {app_name}-admin connect <url> --signing-key xxx"
        )
    if cfg.get("mode") == "local":
        from mcp_app.data_store import FileSystemUserDataStore
        from mcp_app.bridge import DataStoreAuthAdapter
        return DataStoreAuthAdapter(FileSystemUserDataStore(app_name=app_name))
    else:
        from mcp_app.admin_client import RemoteAuthAdapter
        return RemoteAuthAdapter(
            _resolve_url(None, app_name),
            _resolve_signing_key(None, app_name),
        )


def create_mcp_cli(app_name: str, tools_module: ModuleType | None = None) -> click.Group:
    """Create the MCP server CLI for an app (serve, stdio).

    Args:
        app_name: App name (server name, store paths).
        tools_module: Python module containing async tool functions.
            If None, imported as {app_name}.mcp.tools.

    Usage:
        from my_app.mcp import tools
        mcp_cli = create_mcp_cli("my-app", tools_module=tools)

        # or with convention (single-package):
        mcp_cli = create_mcp_cli("my-app")
    """

    @click.group()
    def cli():
        """MCP server commands."""
        pass

    @cli.command()
    @click.option("--host", default="0.0.0.0")
    @click.option("--port", default=8080, type=int)
    def serve(host, port):
        """Run MCP server over HTTP."""
        import uvicorn
        import mcp_app
        from mcp_app.bootstrap import build_asgi

        resolved = _resolve_tools(app_name, tools_module)
        app, mcp, store = build_asgi(app_name, resolved)
        mcp_app._store = store
        uvicorn.run(app, host=host, port=port)

    @cli.command()
    @click.option("--user", required=True, help="User identity for this session.")
    def stdio(user):
        """Run MCP server over stdio."""
        from mcp_app.bootstrap import run_stdio

        resolved = _resolve_tools(app_name, tools_module)
        run_stdio(app_name, resolved, user)

    return cli


def _resolve_tools(app_name: str, tools_module: ModuleType | None) -> ModuleType:
    """Resolve tools module — use provided or import by convention."""
    if tools_module is not None:
        return tools_module
    import importlib
    module_name = f"{app_name.replace('-', '_')}.mcp.tools"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        raise click.ClickException(
            f"Could not import tools module '{module_name}'. "
            f"Pass tools_module explicitly to create_mcp_cli()."
        )


def create_admin_cli(app_name: str) -> click.Group:
    """Create the admin CLI for an app (connect, users, tokens, health).

    Dynamically generates typed CLI flags from the registered profile
    model (if expand=True) or accepts --profile for object input.
    All user operations go through UserAuthStore — local or remote
    determined by connect config.

    Usage:
        admin_cli = create_admin_cli("my-app")
    """
    from mcp_app.context import get_profile_model, get_profile_expand

    @click.group()
    def cli():
        """Admin commands — user management and health."""
        pass

    @cli.command()
    @click.argument("target")
    @click.option("--signing-key", default=None)
    def connect(target, signing_key):
        """Configure admin target. Use 'local' or a URL.

        \b
        Examples:
          connect local
          connect https://my-app.run.app --signing-key xxx
        """
        if target == "local":
            _save_setup({"mode": "local"}, app_name=app_name)
            click.echo(f"Configured {app_name} for local access.")
        else:
            data = {"mode": "remote", "url": target}
            if signing_key:
                data["signing_key"] = signing_key
            _save_setup(data, app_name=app_name)
            click.echo(f"Configured {app_name}: {target}")

    @cli.command()
    def health():
        """Check health of the configured instance."""
        cfg = _load_setup(app_name)
        if cfg.get("mode") == "local":
            click.echo("Local mode — no remote health check.")
            return
        from mcp_app.admin_client import RemoteAuthAdapter
        adapter = RemoteAuthAdapter(
            _resolve_url(None, app_name),
            _resolve_signing_key(None, app_name),
        )
        result = _run(adapter.health_check())
        click.echo(f"{result['status']} ({result['status_code']})")

    @cli.group()
    def users():
        """Manage users."""
        pass

    @users.command("list")
    def users_list():
        """List registered users."""
        store = _get_auth_store(app_name)
        result = _run(store.list())
        if not result:
            click.echo("No users.")
            return
        for user in result:
            status = " (revoked)" if user.revoke_after else ""
            click.echo(f"  {user.email}{status}")

    # Build users add dynamically from profile model
    model = get_profile_model()
    expand = get_profile_expand()

    add_params = [click.Argument(["email"])]

    if model and expand:
        for field_name, field_info in model.model_fields.items():
            required = field_info.is_required()
            flag_name = f"--{field_name.replace('_', '-')}"
            add_params.append(click.Option(
                [flag_name],
                required=required,
                help=field_info.description or "",
            ))
    else:
        help_text = "Profile as JSON string or @file."
        if model:
            help_text += "\n" + _profile_help_text()
        add_params.append(click.Option(
            ["--profile"],
            default=None,
            help=help_text,
        ))

    @users.command("add", params=add_params)
    @click.pass_context
    def users_add(ctx, **kwargs):
        """Register a user."""
        from datetime import datetime, timezone
        from mcp_app.models import UserAuthRecord

        email = kwargs.pop("email")

        profile = None
        if model and expand:
            data = {k: v for k, v in kwargs.items() if v is not None}
            if data:
                profile = _validate_profile(data)
        elif "profile" in kwargs and kwargs["profile"]:
            profile = _parse_profile_value(kwargs["profile"])
            if profile:
                profile = _validate_profile(profile)

        store = _get_auth_store(app_name)
        result = _run(store.save(
            UserAuthRecord(email=email, created=datetime.now(timezone.utc)),
            profile=profile,
        ))
        click.echo(f"Added: {result['email']}")
        if "token" in result:
            click.echo(f"Token: {result['token']}")

    @users.command("revoke")
    @click.argument("email")
    def users_revoke(email):
        """Revoke a user's access."""
        store = _get_auth_store(app_name)
        _run(store.delete(email))
        click.echo(f"Revoked: {email}")

    @cli.group()
    def tokens():
        """Manage tokens."""
        pass

    @tokens.command("create")
    @click.argument("email")
    def tokens_create(email):
        """Create a new token for an existing user."""
        cfg = _load_setup(app_name)
        if cfg.get("mode") == "local":
            click.echo("Tokens are for remote instances only.")
            return
        from mcp_app.admin_client import RemoteAuthAdapter
        adapter = RemoteAuthAdapter(
            _resolve_url(None, app_name),
            _resolve_signing_key(None, app_name),
        )
        result = _run(adapter.create_token(email))
        click.echo(f"Token for {result['email']}: {result['token']}")

    return cli


if __name__ == "__main__":
    main()
