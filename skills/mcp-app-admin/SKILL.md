---
name: mcp-app-admin
description: "Operate and manage deployed MCP apps or solutions that use the mcp-app framework. Use when asked to verify a deployment, connect the admin CLI, retrieve a signing key, register or manage users, issue or revoke tokens, update a user's profile with a fresh credential, test a deployed service end-to-end, configure a deployed MCP server for use in Claude, Gemini, or other agent platforms, or troubleshoot post-deploy auth. Triggers on: verify deployment, test the deployed service, manage users, add a user, list users, revoke a user, update a token, refresh a credential, get the signing key, connect the admin CLI, configure MCP client, issue a new token, probe, register, and similar post-deploy operational tasks on running mcp-app services."
---

# mcp-app Admin

## Overview

This skill covers operating mcp-app solutions after deployment:
connecting the admin CLI, verifying the deployment end-to-end,
managing users and credentials, and registering MCP clients. It
applies regardless of how the solution was deployed — Cloud Run,
Docker, bare metal, or any other environment.

The `author-mcp-app` skill covers building, structuring, testing,
and deploying solutions. This skill picks up where deployment ends.
The hand-off point is: the app is deployed and running, the
operator needs to connect, verify, and manage it.

## Before You Start

**At the start of any session involving admin operations**, check
the current connection state before doing anything else:

```bash
my-solution-admin health        # remote — confirms URL and auth
my-solution-admin users list    # local or remote — confirms store access
```

Do not assume the admin CLI is pointed at the right target. The
connection may be stale from a previous session, pointed at a
different environment, or not configured at all. Verify first.

**Prefer the per-app admin CLI** (`my-solution-admin`) over the
generic CLI (`mcp-app`). The per-app CLI stores connection config
per app in `~/.config/{name}/setup.json` — each app remembers
its own target independently. The generic CLI stores one
connection at a time and overwrites on each `connect`.

The framework tracks one connection per app (a single deployment
environment, whether local or remote). If the same app is
deployed to multiple environments, `connect` switches between
them but only remembers the last one configured.

## Step 1: Retrieve the Signing Key

The signing key is required for admin operations on remote
instances. It's stored wherever the deployment process put it —
trace it back through the deployment tooling.

### How to find it

**Start with the deployment configuration.** Look at how the
solution was deployed and how `SIGNING_KEY` was configured:

- **gapp** with a generated secret — retrieve from GCP Secret
  Manager using the secret name from gapp config:
  ```bash
  gapp secrets get <secret-name> --raw
  ```

- **Cloud secret manager** (GCP, AWS, etc.) — the key was
  stored there by the deployment tool or manually:
  ```bash
  # GCP
  gcloud secrets versions access latest --secret=SECRET_ID --project=PROJECT_ID
  # AWS
  aws secretsmanager get-secret-value --secret-id SECRET_ID
  ```

- **Terraform** managing the secret — check Terraform state:
  ```bash
  terraform output -raw signing_key
  ```

- **Docker Compose** — check `docker-compose.yml` for the
  secret source (file path, env var, Docker secret).

- **CI/CD secrets** (GitHub Actions, GitLab CI) — these are
  write-only from the UI. If this is the only copy, generate
  a new key, update the CI secret, and redeploy.

- **Environment variable set manually** — check the process
  environment or the shell/systemd/supervisor config.

### If you can't find it

Generate a new one, store it wherever the deployment expects
it, redeploy, and re-register all users (existing tokens
become invalid):

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

## Step 2: Connect the Admin CLI

Check if the app's own admin CLI is available:

```bash
which my-solution-admin
```

If not found, install the package. Check `pyproject.toml` for
`[project.scripts]` to find the entry point name:

```bash
pipx install git+https://github.com/owner/my-solution.git
# or from a local clone:
pipx install -e .
```

Then connect:

```bash
# Per-app CLI (preferred) — local or remote
my-solution-admin connect local
my-solution-admin connect https://your-service --signing-key xxx

# Generic CLI (fallback) — remote only
mcp-app connect https://your-service --signing-key xxx
```

`connect local` is only available on the per-app CLI — the
generic CLI doesn't know which app's store to locate.

## Step 3: Verify the Deployment

Use `probe` for single-command end-to-end verification:

```bash
my-solution-admin probe
```

Output:
```
URL: https://your-service
Health: healthy
MCP: ok (probed as alice@example.com)
Tools (3):
  do_thing
  list_items
  get_status
```

This hits `/health` for liveness, then does an MCP `tools/list`
round-trip using a short-lived token minted for an existing
user. If it reports tools, the app is fully operational —
health, admin auth, user auth, MCP layer, and tool wiring all
work.

If no users are registered yet, probe reports liveness only
and tells you it can't do the MCP round-trip. Register a user
first (Step 4), then probe again.

For structured output (agent consumption):
```bash
my-solution-admin probe --json
```

### Manual verification (if probe isn't enough)

```bash
# Liveness
curl https://your-service/health

# Admin auth
my-solution-admin users list

# User auth — tools/list with a user token
curl -X POST https://your-service/ \
  -H "Authorization: Bearer USER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```

## Step 4: Manage Users

### Register a new user

```bash
# Data-owning app — no profile needed
my-solution-admin users add alice@example.com

# API-proxy app — profile via typed flags
my-solution-admin users add alice@example.com --token api-key-xxx
```

`users add` rejects existing users. If the user already exists,
use `update-profile` instead.

To discover what profile fields the app expects, check the
`--help` output — field names and descriptions are generated
from the app's Pydantic profile model:

```bash
my-solution-admin users add --help
```

### Update credentials

```bash
# Typed key (expand=True apps) — key is validated, tab-completable
my-solution-admin users update-profile alice@example.com token new-api-key

# JSON merge (expand=False apps)
my-solution-admin users update-profile alice@example.com '{"token": "new-key"}'
```

Use this to rotate backend credentials without re-registering
the user. Only the specified field is changed — other profile
fields are preserved.

### Other user operations

```bash
# List all users
my-solution-admin users list

# Revoke a user (invalidates all their tokens immediately)
my-solution-admin users revoke alice@example.com

# Issue a new token for an existing user
my-solution-admin tokens create alice@example.com
```

### Token lifecycle

- Tokens are long-lived by default (~10 years) because MCP
  clients cannot refresh tokens automatically.
- Revocation is the primary access control — `users revoke`
  sets a cutoff timestamp, and all tokens issued before that
  moment are rejected.
- After revoking, issue a new token with `tokens create` to
  reactivate the user.
- The token from `users add` or `tokens create` is what the
  user configures in their MCP client.

## Step 5: Register MCP Clients

Use `register` to generate ready-to-paste commands:

```bash
# With a real token (mints one for the user)
my-solution-admin register --user alice@example.com

# With a placeholder (operator substitutes later)
my-solution-admin register
```

This outputs commands for Claude Code, Gemini CLI, and the
Claude.ai URL form, with the URL and token already substituted.

For structured output:
```bash
my-solution-admin register --user alice@example.com --json
```

Filter by client or scope:
```bash
my-solution-admin register --user alice@example.com --client claude --scope user
```

### Manual registration (if register isn't available)

**stdio (local):**
```bash
claude mcp add my-solution -- my-solution-mcp stdio --user local
gemini mcp add my-solution -- my-solution-mcp stdio --user local
```

**HTTP (remote):**
```bash
claude mcp add --transport http my-solution \
  https://your-service/ \
  --header "Authorization: Bearer USER_TOKEN"
```

**Claude.ai / Claude mobile:**
```
https://your-service/?token=USER_TOKEN
```

## When to Use the Generic CLI

If the app's own admin CLI (`my-solution-admin`) isn't installed
— e.g., managing a deployed instance from a machine without the
app's repo — use the generic `mcp-app` CLI:

```bash
mcp-app connect https://your-service --signing-key xxx
mcp-app users add alice@example.com --profile '{"token": "xxx"}'
mcp-app probe
mcp-app register my-solution --user alice@example.com
```

The generic CLI works but doesn't have typed profile flags or
`connect local`. Always prefer the per-app CLI when available.

## Important Notes

- **`connect` and `deploy` are independent.** Deploying a
  service does not automatically connect the admin CLI to it.
  After deploying, explicitly run `connect` before admin
  operations.
- **User management is an mcp-app concern**, not a deployment
  tool concern. Admin endpoints and the CLI are part of the
  framework.
- **Admin tokens are generated locally** using the signing
  key — they don't pass through the deployed service.
- **The signing key retrieval method depends on the deployment
  tooling.** This skill can't prescribe a single command —
  investigate the deployment configuration to trace where the
  key lives.
