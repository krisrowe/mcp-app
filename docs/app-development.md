# Building an App with mcp-app

How to wire up an app that uses mcp-app for identity, user
management, and MCP server hosting.

## The `App` Object

The `App` class is the single composition root for your solution.
It serves two purposes:

1. **Runtime configuration** — declares your app's name, tools
   module, store, profile model, and middleware. CLIs (serve,
   stdio, admin) derive from it automatically.
2. **Testability** — `mcp_app.testing` discovers your `App` and
   runs auth, admin, wiring, and tool coverage tests against it.
   The test suite passing is the definitive confirmation that
   your app is correctly built.

Everything mcp-app needs from your app goes in `__init__.py`:

**Data-owning app** (no per-user credentials):

```python
# my_app/__init__.py
from mcp_app import App
from my_app.mcp import tools

app = App(name="my-app", tools_module=tools)
```

**API-proxy app** (per-user backend credentials):

```python
# my_app/__init__.py
from pydantic import BaseModel
from mcp_app import App
from my_app.mcp import tools

class Profile(BaseModel):
    token: str

app = App(
    name="my-app",
    tools_module=tools,
    profile_model=Profile,
    profile_expand=True,
)
```

`profile_expand=True` generates typed CLI flags (`--token`) on
the admin CLI. `profile_expand=False` accepts profile as JSON
or `@file`.

## pyproject.toml Entry Points

```toml
[project]
name = "my-app"
dependencies = ["mcp-app"]

[project.scripts]
my-app = "my_app.cli:cli"               # app's own CLI (optional)
my-app-mcp = "my_app:app.mcp_cli"       # serve, stdio
my-app-admin = "my_app:app.admin_cli"    # connect, users, tokens, health

[project.entry-points."mcp_app.apps"]
my-app = "my_app:app"
```

One `pipx install my-app` creates all three commands. The
`mcp_app.apps` entry point lets the test suite and tooling
discover the app.

### Multi-package repos

If SDK, MCP, and CLI are separate installable packages, put the
`App` object in the MCP package (where mcp-app is a dependency):

```python
# mcp/my_app_mcp/__init__.py
from mcp_app import App
from my_app_mcp import tools
import my_app

app = App(name="my-app", tools_module=tools, sdk_package=my_app)
```

```toml
# mcp/pyproject.toml
[project.scripts]
my-app-mcp = "my_app_mcp:app.mcp_cli"
my-app-admin = "my_app_mcp:app.admin_cli"

[project.entry-points."mcp_app.apps"]
my-app = "my_app_mcp:app"
```

## User Management Workflow

### First-time setup

```bash
# Local (filesystem store on this machine)
my-app-admin connect local

# Remote (deployed instance)
my-app-admin connect https://my-app.run.app --signing-key xxx
```

Saves mode to `~/.config/{app-name}/setup.json`. All subsequent
user commands route automatically.

### Managing users

```bash
# API-proxy app with expand=True — typed flags
my-app-admin users add alice@example.com --token xxx

# Data-owning app — no profile needed
my-app-admin users add alice@example.com

# API-proxy app with expand=False — JSON blob
my-app-admin users add alice@example.com --profile '{"client_id":"...","refresh_token":"..."}'
# or from file
my-app-admin users add alice@example.com --profile @creds.json

# List and revoke
my-app-admin users list
my-app-admin users revoke alice@example.com

# Health check (remote only)
my-app-admin health
```

### How routing works

`connect local` makes user commands write directly to the
filesystem store (`~/.local/share/{app-name}/users/`).

`connect <url>` makes user commands call the remote instance's
`/admin` REST API via HTTP.

Both use the `UserAuthStore` protocol — `DataStoreAuthAdapter`
for local, `RemoteAuthAdapter` for remote. The CLI calls the
same interface regardless of mode.

## Running the MCP Server

### Development (from venv)

```bash
pip install -e .
my-app-mcp serve                   # HTTP on port 8080
my-app-mcp stdio --user local      # stdio
```

### Installed app (from anywhere)

```bash
pipx install my-app
my-app-mcp serve                   # HTTP
my-app-mcp stdio --user local      # stdio
my-app-mcp stdio --user alice      # different user
```

No config files — the app name and tools module are wired in
Python via `create_mcp_cli`. Works from any directory.

### Registering with MCP clients

```bash
# Claude Code — installed app, stdio
claude mcp add my-app -- my-app-mcp stdio --user local

# Claude Code — remote HTTP
claude mcp add --transport http my-app \
  https://my-app.run.app/ \
  --header "Authorization: Bearer USER_TOKEN"

# Claude.ai — remote URL (works across web, mobile, Claude Code)
https://my-app.run.app/?token=USER_TOKEN
```

## Reading User Identity in the SDK

```python
from mcp_app.context import current_user

user = current_user.get()
user.email       # "alice@example.com" or "local"
user.profile     # typed Pydantic model (API-proxy) or None (data-owning)
```

Set automatically by:
- **HTTP**: identity middleware validates JWT, loads user record
- **stdio**: CLI loads user record using `--user` flag
- **Tests**: set directly in fixtures

### Data-owning app SDK

```python
from mcp_app.context import current_user
from mcp_app import get_store

class MySDK:
    def save_entry(self, data):
        user = current_user.get()
        store = get_store()
        store.save(user.email, "entries/today", data)
```

Or manage storage however the app chooses — `current_user.get().email`
is the identity, the app decides how to use it.

### API-proxy app SDK

```python
from mcp_app.context import current_user
import httpx

class MySDK:
    def list_items(self):
        user = current_user.get()
        token = user.profile.token
        resp = httpx.get("https://api.example.com/items",
                         headers={"Authorization": f"Bearer {token}"})
        return resp.json()
```

## Testing

### Set current_user in test fixtures

```python
from mcp_app.context import current_user
from mcp_app.models import UserRecord

@pytest.fixture(autouse=True)
def test_user():
    token = current_user.set(UserRecord(email="test-user"))
    yield
    current_user.reset(token)
```

### Full-stack HTTP test

```python
import httpx

@pytest.fixture
def app_client(app, tmp_path):
    os.environ["APP_USERS_PATH"] = str(tmp_path / "users")
    os.environ["SIGNING_KEY"] = "test-key-32chars-minimum-length!!"
    asgi_app, mcp, store = app.build_asgi()
    transport = httpx.ASGITransport(app=asgi_app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
```

If it works in httpx ASGI transport, it works in Docker.

## Confirming Your App Works

The definitive confirmation that your app is correctly built is
that mcp-app's test suite passes against it. These tests check
auth enforcement, user admin, JWT handling, CLI wiring, tool
protocol compliance, and SDK test coverage — the mission-critical
operational functionality that mcp-app provides.

### 1. Create `tests/framework/conftest.py`

```python
import pytest
from my_app import app

@pytest.fixture(scope="session")
def app():
    return app
```

### 2. Create `tests/framework/test_framework.py`

```python
from mcp_app.testing.iam import *
from mcp_app.testing.wiring import *
from mcp_app.testing.tools import *
from mcp_app.testing.health import *
```

This file is identical across all mcp-app solutions. The
`conftest.py` is the only file that changes — it points the
tests at your specific `App` object.

### 3. Run

```bash
pytest tests/
```

Zero failures means: auth works, admin works, tools are wired,
identity is enforced, and the SDK has test coverage for every
tool. Your app is correctly built on mcp-app.
