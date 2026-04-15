# Operations

> **Status: ROADMAP / DESIGN.** This document describes the
> intended operator experience for building, deploying, and
> managing mcp-app solutions. Most of it is not yet implemented;
> [#7](https://github.com/echomodel/mcp-app/issues/7) tracks the
> fleet/deploy implementation. Sections are marked **(today)**
> when they describe behavior that exists in the current release,
> and **(design)** for everything else.
>
> This document supersedes [FLEET.md](FLEET.md). Where the two
> diverge, OPERATIONS.md is authoritative going forward. FLEET.md
> remains as a historical design artifact until the replacement
> is confirmed complete.

## Overview

Operating an mcp-app solution — deploying, managing users, checking
health, rotating tokens — follows a unified model regardless of
which solution, how you deploy, or how many solutions you manage.

A single substrate (a "fleet") scales invisibly from a solo operator
with one solution to a team managing many solutions across multiple
environments. Simple cases never encounter fleet vocabulary. Complex
cases extend naturally through the same commands.

The default and most universal pattern is the **`manual` provider**:
mcp-app stores just the admin URL and a reference to the signing
key, and the operator deploys however they want (ssh+tarball,
`gcloud run deploy`, `docker compose`, a private CI pipeline, a
custom web UI — anything). More opinionated providers
(gapp, cloudrun, k8s, script-runner, github-actions) exist and plug
into the same mechanism. Echomodel advocates gapp as a polished
deployment experience on top; every solution works with `manual`
without it.

## Operator Experience

### Solo, single solution — manual provider (the universal path)

You have one mcp-app solution. You've deployed it somewhere yourself
(or you're about to), and you want mcp-app to handle user and token
management.

```bash
cd ~/projects/echofit
mcp-app connect echofit https://my-service.example.com
  → "signing key for echofit: ___"    (prompts; stores in OS keyring)

mcp-app users add echofit alice@example.com
  → (returns token)

mcp-app health echofit
  → {"status": "ok"}
```

Two commands to get from nothing to managing users. No provider
install, no fleet vocabulary, no config file editing. `connect` is
sugar: it writes a minimal fleet entry with the `manual` provider
under the hood.

### Solo, single solution — with a deploy provider

You want mcp-app to run your deploys, not just manage users.

```bash
cd ~/projects/echofit
mcp-app deploy
  → "deploy not configured for echofit. run 'mcp-app deploy configure'."

mcp-app deploy configure
  → wizard:
      Which provider? (installed: manual, script-runner, cloudrun)
      [any provider-declared config fields, prompted with hints/defaults]
      Source [echomodel/echofit]            (inferred from git remote)
      Ref [main]                            (inferred from default branch)
      Multi-environment? [n]

mcp-app deploy
  → pre-deploy summary, confirm, provider runs
```

Wizard's prompts come from the chosen provider's self-described
schema. mcp-app itself knows nothing about GCP projects or k8s
namespaces — the provider declares what it needs, the wizard asks.

### Solo, multiple solutions

```bash
cd ~/projects/echofit && mcp-app deploy configure && mcp-app deploy
cd ~/projects/gwsa   && mcp-app deploy configure && mcp-app deploy

mcp-app users add echofit alice@example.com
mcp-app users add gwsa bob@example.com
```

Same commands. Each solution gets its own entry in the same invisible
default fleet.

### Multi-environment

```bash
cd ~/projects/echofit
mcp-app deploy configure --deployment dev
mcp-app deploy configure --deployment prod

mcp-app deploy echofit:dev
mcp-app deploy echofit:prod --ref v1.2.3

mcp-app users add echofit:prod alice@example.com   # prod users only
mcp-app users add echofit:dev  alice@example.com   # dev users (separate roster)
```

`solution:deployment` syntax is only required when deployments are
configured. Solo-deployment solutions don't use it.

### Multi-fleet

```bash
mcp-app fleets register https://github.com/acme/team-infra --name team
mcp-app fleets use team

mcp-app deploy echofit                   # deploys team's echofit
mcp-app deploy echofit --fleet personal  # one-off cross-fleet op
```

`mcp-app fleets` commands appear only when an operator has use for
multiple fleets. Before that, the default local fleet is the only
one and is invisible.

## CLI Reference

### Connect — the simplest path

```bash
mcp-app connect <solution> <url> [--signing-key <value>]
```

Creates or updates a fleet entry using the `manual` provider. If
`--signing-key` is omitted, prompts for it (stored in OS keyring).
Can be re-run to update url or re-supply the signing key.

### Deploy

```bash
mcp-app deploy [target] [--ref <ref>] [--fleet <name>] [--deployment <name>]
mcp-app deploy configure [target]                       # first-time wizard
mcp-app deploy config <field> set <value> [target]      # per-attribute tweak
mcp-app deploy config show [target]
mcp-app deploy show [target]                            # what would run
```

`target` is `solution` or `solution:deployment`. When omitted, cwd
inference resolves it if the current directory is an mcp-app
solution (its `pyproject.toml` declares `[project.entry-points."mcp_app.apps"]`).

### Admin

```bash
mcp-app users add <target> <email>
mcp-app users list <target>
mcp-app users revoke <target> <email>
mcp-app tokens create <target> <email>
mcp-app health <target>
```

All admin verbs resolve URL from the fleet entry (or via
`provider.status()`) and signing key from the provider's resolver
(keyring, cloud secret store, etc.).

### Providers

```bash
mcp-app providers list
mcp-app providers describe <name>                       # JSON schema
mcp-app providers add <name> --package <pip-spec>
mcp-app providers config <name> <field> set <value>
mcp-app providers remove <name>
```

Builtins (`manual`, `script-runner`) appear in `list` without
declaration. Pip-installable providers appear once installed.

### Deployments

```bash
mcp-app deployments list [solution]
mcp-app deployments add <target>                        # alias of 'deploy configure --deployment X'
mcp-app deployments remove <target>
```

### Fleets (advanced)

```bash
mcp-app fleets list
mcp-app fleets current
mcp-app fleets use <name>
mcp-app fleets register <url> --name <name> [--path <path>]
mcp-app fleets remove <name>
```

### Config (secrets and machine-level settings)

```bash
mcp-app config secrets list
mcp-app config secrets set <target> <field> [--stdin]
mcp-app config secrets show <target> <field>            # references only; values redacted
mcp-app config secrets export [--out <path>]
mcp-app config secrets import <path>

mcp-app config signing-key-store set [keyring|file|env]
```

Use `--stdin` for CI/non-interactive secret injection:

```bash
echo "$CI_KEY" | mcp-app config secrets set echofit signing_key --stdin
mcp-app deploy echofit
```

No magic environment variable name schemes.

### Overrides

| Flag | Effect |
|------|--------|
| `--fleet <name>` | Use a specific fleet for this invocation. |
| `--deployment <name>` | Specify deployment when solution has multiple. Alternative to `solution:deployment` syntax. |
| `--ref <ref>` | Deploy a specific git ref. Overrides fleet-entry ref. |

No `--source` flag, no `--use-working-tree`. Source is locked to
the fleet entry for reproducibility. See [Source locking](#source-locking).

### cwd inference

When cwd is an mcp-app solution, `target` is optional on every
command. pyproject's `mcp_app.apps` entry-point name resolves the
solution. When a solution has multiple deployments and no
`default_deployment` is set, the CLI errors with the list of
available deployments — cwd never silently picks one.

## Schema Reference

### Top level

```yaml
providers:                  # pip-installable provider declarations (builtins omitted)
  <name>:
    package: <pip-spec>     # reserved; pip install target
    <any other key>: ...    # passed to provider as base config

defaults:                   # optional fleet-wide defaults
  deploy: <provider-name>
  runtime: mcp-app          # mcp-app | none

solutions:
  <solution-name>:
    source: <source>
    ref: <ref>              # optional
    deploy: ...             # see below
    runtime: ...            # optional; overrides default
    env: {...}              # optional
    secrets: {...}          # optional
    deployments:            # optional multi-env
      <deployment-name>: ...
    default_deployment: <name>  # optional
```

### Flattened `deploy:` block

Under `deploy:`, only `provider:` and `notes:` are reserved.
Everything else is provider config (what the provider's `describe()`
declares):

```yaml
deploy:
  provider: <name>          # reserved; which provider
  notes: |                  # reserved; optional operator context
    ...any hints for humans and agents...
  <any other key>: ...      # provider config field
  <another key>: ...        # provider config field
```

If `provider:` is omitted, defaults to the value from
`defaults.deploy`, and if that's unset, to the `manual` builtin.

The same flattening applies to top-level `providers.<name>:`:
`package:` is reserved, every other key is base provider config.

### `notes:` — operator context for any provider

Optional free-form text on any `deploy:` block (solution or
deployment level). Not consumed by mcp-app. Printed in the pre-deploy
summary and shown to agents and humans running a deploy. Useful for:

- **`manual` provider**: operator explains how to deploy, because
  mcp-app won't do it.
- **Any provider**: operator leaves hints, skill names to invoke, or
  contingencies.

Examples:

```yaml
# manual with instruction for the next human/agent
deploy:
  provider: manual
  url: https://my-service.example.com
  notes: |
    To deploy, run ./deploy from the repo root. Hits our internal
    build pipeline.
```

```yaml
# manual acknowledging no agent-friendly path exists
deploy:
  provider: manual
  url: https://my-service.example.com
  notes: |
    Deployed via the internal thingamigger (no CLI or API). Agents
    should stop here and let the human take over.
```

```yaml
# hint for an agent with additional skills available
deploy:
  provider: cloudrun
  project: my-proj
  region: us-central1
  notes: |
    If the my-company-deploy skill is installed, prefer that over
    direct cloudrun provider invocation — it handles our internal
    approval workflow.
```

```yaml
# pointer to a runbook
deploy:
  provider: script-runner
  script: scripts/deploy.sh
  notes: |
    See runbooks/echofit-deploy.md for rollback procedure.
```

### Solution fields

| Field | Required | Default | Inherits? |
|-------|----------|---------|-----------|
| `source` | yes | — | to deployments |
| `ref` | no | repo default branch | to deployments |
| `deploy.provider` | no | `defaults.deploy` → `manual` | to deployments |
| `deploy.<config field>` | depends on provider's schema | provider's own default (if any) | to deployments (merged) |
| `deploy.notes` | no | — | to deployments (overrideable) |
| `runtime` | no | `defaults.runtime` → `mcp-app` | to deployments |
| `env` | no | — | to deployments (merged) |
| `secrets` | no | — | to deployments (merged) |
| `deployments` | no | single-target deploy | — |
| `default_deployment` | no | — | — |

### Inheritance order

Every attribute cascades lowest → highest precedence:

1. Defaults and root provider config
2. Solution-level
3. Deployment-level
4. CLI override flags

Provider `config` fields merge across levels (deployment overrides
solution overrides root). `env` and `secrets` also merge.

`env:` is never allowed at fleet `defaults` or root `providers:`
level — it's always solution-specific. Similarly, `source:` only
makes sense at solution or deployment level.

### Minimum valid fleet.yaml

Just enough for manage-only (manual provider implicit):

```yaml
solutions:
  echofit:
    deploy:
      url: https://my-service.example.com
```

Three lines. No `providers:` block, no `defaults:`, no
`provider:` field. Signing key lives in keyring.

For a deployed-through-mcp-app solution using cloudrun:

```yaml
providers:
  cloudrun:
    package: mcp-app-cloudrun
    region: us-central1

defaults:
  deploy: cloudrun

solutions:
  echofit:
    source: echomodel/echofit
    deploy:
      project: my-proj      # cloudrun config field; region inherited
```

### Source field forms

```yaml
source: owner/repo                              # GitHub (clone fresh)
source: git+https://github.com/owner/repo.git   # arbitrary git remote
source: registry.io/image:tag                   # pre-built image
source: /absolute/path/to/source                # local path (dev)
```

### Source locking

`source` lives only in the fleet entry. There is no `--source` or
`--use-working-tree` flag. Every deploy corresponds to a real
commit in the configured source. Operators can't accidentally
deploy the wrong thing from the wrong directory. Image tagging
follows from resolved commit sha — reproducible and auditable.

To deploy an unpushed branch: `git push origin HEAD:wip-branch && mcp-app deploy --ref wip-branch`.

## Config Ownership

Three layers own different kinds of configuration. Mixing them
causes drift. The rule: **each piece of config lives with the layer
that varies it.**

| Layer | Owns | Examples | Where it lives |
|-------|------|----------|----------------|
| Solution author | Config intrinsic to the app | Feature flags, fixed behaviors, API schema versions | Solution repo (App constructor args, pyproject) |
| Operator | Config that varies by operator or environment | `LOG_LEVEL`, per-env credentials, deploy target, refs | fleet.yaml |
| Provider | Config the provider needs to deploy | GCP project, k8s namespace, region, build args | `providers:` block or `deploy:` block in fleet.yaml |

Don't lift into fleet.yaml what doesn't actually vary. Operator-
varying config belongs in fleet; solution-intrinsic config stays
in the repo; provider-specific settings belong in provider config.

Signing keys are the exceptional case: they always vary (unique
per deployment) but never touch disk in plaintext. Keyring or
cloud secret store holds them, resolved on demand.

## Provider Plugin Model

### Builtin providers

These ship with mcp-app itself. No pip install, no `providers:`
declaration needed:

- **`manual`** — stores URL + signing-key reference. Does nothing
  at deploy time. Supports `notes:` for operator context.
- **`script-runner`** — runs an operator-supplied script from the
  source checkout.

### Pip-installable providers

Anyone can publish one as a pip package that registers under
`entry_points(group="mcp_app.providers")`. Operator installs via
`mcp-app providers add <name> --package <pip-spec>`. Examples of
providers echomodel might publish or recommend:

- **`mcp-app-cloudrun`** — direct `gcloud run deploy --source`
  with no intermediaries.
- **`mcp-app-gapp`** — bridge to gapp; operator gets gapp's full
  feature set. Neither mcp-app nor gapp know about each other.
- **`mcp-app-docker`** — local or remote Docker / docker-compose.
- **`mcp-app-ssh`** — rsync/tar a checkout to a VM, run a restart
  command.
- **`mcp-app-github-actions`** — dispatch a GitHub Actions
  workflow and wait for completion.
- **`mcp-app-k8s`** — render and apply a k8s manifest.

Community or vendors publish whatever bridges they want.

### `package:` field accepts any pip install target

```yaml
providers:
  cloudrun:
    package: mcp-app-cloudrun                                  # PyPI
  cloudrun-pinned:
    package: "mcp-app-cloudrun>=1.2,<2.0"                      # version constraint
  custom:
    package: git+https://github.com/me/my-provider.git@v1.2.0  # git
  custom-dev:
    package: ~/projects/my-provider                            # local path
```

mcp-app passes the value unmodified to `pip install`.

### Self-describing schema

Every provider exposes its config requirements via `describe()`:

```python
class ManualProvider(DeployProvider):
    @classmethod
    def describe(cls):
        return ProviderSchema(
            name="manual",
            description="No deployment; operator deploys externally",
            config_fields=[
                Field("url",         type="string", required=True,
                      hint="admin endpoint URL"),
                Field("signing_key", type="secret", required=True,
                      hint="admin signing key"),
            ],
        )
```

The skill and CLI use this to prompt operators. `type: "secret"`
fields are stored via the machine's configured secret backend
(keyring / file / env) and referenced, not embedded, in fleet.yaml.

### Provider interface

```python
class DeployProvider:
    @classmethod
    def describe(cls) -> ProviderSchema:
        """Return config schema; used by skill/CLI for prompting."""

    def deploy(self, request: DeployRequest) -> DeployResult:
        """Execute a deploy. Provider gets fully-resolved context."""

    def status(self, solution: str, deployment: str | None) -> Status:
        """Return current URL, last deployed ref/sha, health."""

    def resolve_signing_key(self, solution: str, deployment: str | None) -> str:
        """Fetch signing key from provider's secret store on demand."""
```

Providers receive fully-resolved configuration — fleet handles
inheritance and merging. Providers don't read fleet.yaml.

### DeployRequest shape

```python
DeployRequest(
    solution="echofit",
    deployment="dev" | None,
    source=Source(
        url="echomodel/echofit",
        ref="main",
        sha="a3f1c2e",
        checkout="/tmp/mcp-app-XXX" | None,   # fresh clone, if fleet did one
    ),
    config={...},                             # resolved provider config
    env={...},                                # merged runtime env vars
    secrets={...},                            # refs; provider resolves values
    runtime="mcp-app",
    notes="...",                              # if set, for logs/summary
    fleet_name="default",
)
```

## Builtin Provider Details

### `manual`

```yaml
solutions:
  echofit:
    deploy:
      provider: manual                            # optional; default
      url: https://my-service.example.com
      notes: |                                    # optional
        To redeploy, run `./scripts/deploy.sh` from repo root.
```

`describe()` reports:

| Field | Type | Required | Hint |
|-------|------|----------|------|
| url | string | yes | admin endpoint URL |
| signing_key | secret | yes | admin signing key |

`deploy()` does nothing — raises or returns success with "manual
deploy; operator handles it externally." `notes:` content prints
to the terminal when someone runs `mcp-app deploy echofit`, so
both humans and agents see it.

`status()` returns the stored URL. `resolve_signing_key()` fetches
from keyring.

### `script-runner`

```yaml
solutions:
  echofit:
    deploy:
      provider: script-runner
      script: scripts/deploy.sh                   # repo-relative (default) or absolute
      project: my-proj                            # any other fields forwarded as input
      region: us-central1
```

At deploy time, the provider:

1. Clones the source to a checkout.
2. Serializes the DeployRequest to JSON.
3. Pipes the JSON to the script via stdin (preferred over temp
   file — secrets stay off disk):

   ```bash
   scripts/deploy.sh < /dev/stdin
   ```

4. Streams script stdout/stderr to the operator's terminal.
5. Parses `::mcp-app::key=value` markers from stdout to extract
   the deployed URL (and anything else the script chooses to
   emit).
6. Returns success/failure based on script exit code.

Example script:

```bash
#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
project=$(echo "$input" | jq -r .config.project)
region=$(echo "$input"  | jq -r .config.region)
solution=$(echo "$input" | jq -r .solution)
sha=$(echo "$input"      | jq -r .source.sha)

gcloud run deploy "$solution" --source . \
    --project "$project" --region "$region"

url=$(gcloud run services describe "$solution" \
        --project "$project" --region "$region" \
        --format='value(status.url)')
echo "::mcp-app::url=$url"
```

All deployment-varying values live in fleet.yaml. The script is
generic; operators can commit it to the solution repo or keep it
in operator-local config.

## Operational Flows

### First deploy (from a clean machine)

```bash
$ cd ~/projects/echofit
$ mcp-app deploy
  → "deploy not configured for echofit. run 'mcp-app deploy configure'."

$ mcp-app deploy configure
  # silently creates the default fleet if none exists
  # discovers installed providers via entry_points
  # prompts: Which provider? [manual / script-runner / cloudrun / other]
  # [provider-declared fields follow, each prompted with hint and default]
  # prompts: Source [echomodel/echofit] (from git remote)
  # prompts: Ref    [main]              (from default branch)
  # prompts: Multi-environment? [n]
  → "Configured. Run 'mcp-app deploy'."

$ mcp-app deploy
  → Pre-deploy summary:
      Deploy echofit
        source:   echomodel/echofit @ main → a3f1c2e
        provider: cloudrun (project=my-proj, region=us-central1)
        runtime:  mcp-app
        notes:    (if set)
      Proceed? [y/N]
  → Provider runs. Output streams to terminal.
  → CLI prints next-step hints (users add, health).
```

### First-time manage-only (no mcp-app deploy)

You deployed echofit yourself via your own tooling. Now you want
mcp-app to handle users.

```bash
$ mcp-app connect echofit https://my-service.example.com
  → "signing key for echofit: ___"
  → (stored in keyring)

$ mcp-app users add echofit alice@example.com
  → (returns token)
```

Equivalent fleet.yaml written under the hood:

```yaml
solutions:
  echofit:
    deploy:
      url: https://my-service.example.com
```

### Redeploy

```bash
$ git push
$ mcp-app deploy
  → Pre-deploy summary (new sha)
  → Confirm, run.
```

### Lazy prompt for missing fields

First use of a command on a new machine (e.g., cloned team fleet,
new laptop):

```bash
$ mcp-app users add echofit alice@example.com
  → "signing key for echofit not found on this machine."
  → "enter signing key: ___"
  → (stored in keyring, runs the admin call)
```

Non-secret missing fields prompt the same way but write back to
fleet.yaml.

Non-interactive contexts (CI, `--yes`, no tty): the CLI errors
with a clear instruction on how to supply the value via
`mcp-app config secrets set` or `mcp-app deploy config ... set`.

### Multi-env deploy

```bash
$ mcp-app deploy configure --deployment dev
$ mcp-app deploy configure --deployment prod

$ mcp-app deploy echofit:dev
$ mcp-app deploy echofit:prod --ref v1.2.3
```

Each deployment has its own URL, signing key, and user roster.

### Pre-deploy summary

Always printed before deploy executes:

```
Deploy echofit
  source:   echomodel/echofit @ main → a3f1c2e
  provider: cloudrun (project=my-proj, region=us-central1)
  target:   https://echofit-xxx.a.run.app   (or: "new deployment")
  runtime:  mcp-app
  env:      LOG_LEVEL=INFO
  secrets:  signing_key (stored), third_party_api_key (stored)
  notes:    To rollback, run scripts/rollback.sh from repo root.

Proceed? [y/N]
```

### Safety checks

Before the summary:

- **Unpushed commits** — if the source is a remote ref and local
  branch is ahead of origin, warn.
- **Uncommitted changes** — if the source is a local path, warn
  about dirty working tree.
- **Stale refs** — if the requested ref doesn't exist in the
  remote, error.

Warnings are non-blocking by default. `--strict` promotes them to
errors (CI). `--yes` skips the confirm (scripts).

## Secret Storage

Secrets never appear in fleet.yaml. Three backends, operator-selectable:

| Mode | Backend | When to use |
|------|---------|-------------|
| `keyring` (default) | OS keychain (macOS Keychain / Windows Credential Manager / Linux Secret Service) | Desktop operators; one-machine ops |
| `file` | `~/.config/mcp-app/secrets/<solution>.key` (0600 perms) | Headless Linux, servers |
| `env` | Read from a named env var at resolution time | CI / ephemeral containers |

`keyring` is default. Falls back **loudly** if the backend is
unavailable — never silently to plaintext.

Change mode:

```bash
mcp-app config signing-key-store set file
```

Canonical keyring coordinates are computed internally:
`service=mcp-app/<fleet>/<solution>`, `user=<field-name>`. Operator
never types these. Reattaching (new machine, cloned fleet) works
automatically because the coordinates are deterministic — mcp-app
checks keyring and prompts if missing.

Non-interactive secret injection uses CLI verbs, not magic env vars:

```bash
echo "$KEY" | mcp-app config secrets set echofit signing_key --stdin
```

## State Ownership

mcp-app does **not** store per-solution runtime state locally.
Everything it persists is configuration (intent). Runtime state
(what's deployed, where, at what revision) lives with the provider.

**Local files:**

```
~/.config/mcp-app/
  fleets.yaml                          # registry: which fleets, which active
  fleets/<fleet-name>/
    fleet.yaml                         # manifest (config, not state)
  secrets/<solution>.key               # only in file mode; 0600
```

**Runtime state** (URL, last sha, image tag, health):

- Owned by the provider.
- Fetched via `provider.status(solution, deployment)` on demand.
- Signing keys resolved via `provider.resolve_signing_key(...)`,
  never cached on disk.
- Provider-internal caching (in-session memoization, its own cache
  file) is the provider's choice.

No `connect` step maps to disk state beyond the fleet entry. Admin
ops always ask the provider for fresh values.

## Skills and Agent Integration

### The agent's open/closed configure flow

`deploy-mcp-app` (or any agent) figures out how to configure a
provider by asking mcp-app, not by knowing providers itself:

1. `mcp-app providers list --format json` → names of installed providers
2. Operator picks one
3. `mcp-app providers describe <name> --format json` → schema
4. Agent prompts operator for each `config_field`, showing hint and
   default
5. Agent calls `mcp-app deploy configure <target> --provider <name> --config-json '...'`

The agent has no provider-specific knowledge. New providers plug
in without skill changes.

### `deploy-mcp-app` skill

Fires on user intents like "deploy this." Thin orchestrator:

1. Detect mcp-app solution via pyproject entry point.
2. Run `mcp-app deploy`. On "not configured," branch to configure.
3. Configure flow above; then run `mcp-app deploy` for real.
4. Surface `notes:` to the user when the configure already has
   manual-with-notes, so they understand how the deploy happens.

No tool-specific knowledge. Providers handle the mechanics.

### `manage-mcp-app` skill

Fires on post-deploy intents: "add a user," "check health," "rotate
a token." Maps to `mcp-app users/tokens/health <target> ...`.

### Framework test — README conformance

Every mcp-app solution's README should mention the `deploy-mcp-app`
skill so operators cloning the repo discover the pattern:

```python
def test_readme_references_deploy_skill(app_root):
    content = (app_root / "README.md").read_text()
    assert "deploy-mcp-app" in content or "# mcp-app:no-deployment-section" in content
```

Opt-out marker for stdio-only or personal solutions.

## Design Principles

1. **Solution repo stays deploy-agnostic.** No Dockerfile required,
   no deploy config, no cloud references in the solution.
2. **CLI simplicity is the invariant.** New features extend through
   defaults/inference, never by requiring new mandatory CLI
   arguments for the simple case.
3. **Manual is the universal default.** Every mcp-app can be
   managed without installing any provider.
4. **One substrate.** Fleet is the only state layer. No parallel
   setup.json, deploy.yaml, or per-solution state files.
5. **Invisible until needed.** Solo operators never see fleet
   concepts. Vocabulary surfaces only when the operator reaches
   for the capability.
6. **No silent cwd influence on deploys.** cwd is a CLI ergonomic
   shortcut for target identification; it never changes what
   gets deployed.
7. **Source locked, ref overridable.** Every deploy maps to a real
   commit. No working-tree escape hatch.
8. **Providers own runtime state.** mcp-app orchestrates; providers
   know where things are deployed.
9. **Secrets never in yaml, never silently on disk in plaintext.**
   Keyring default, explicit opt-in for file / env modes.
10. **CLI is the only writer of config files.** Agents and skills
    call CLI verbs, not yaml directly.
11. **Self-describing providers.** Schema for configure-time prompts
    comes from the provider. mcp-app and skills stay open/closed.
12. **Operator can always leave a note.** `notes:` on any `deploy:`
    block documents context for future humans and agents.

## Open Design Questions

Tracked for resolution during implementation.

### Provider invocation: checkout vs cwd vs image

When a provider deploys, does it operate in the operator's cwd,
a fresh clone, or an image? Different providers have different
needs. Resolution: provider's `describe()` also declares its
invocation contract (needs checkout / needs image / self-clones).

### `package:` field pass-through

Explicitly support git URLs, local paths, version constraints in
addition to PyPI names? Leaning yes, pass through to pip verbatim.
Needs to be ratified in implementation.

### Non-happy-path UX contract

Provider errors (auth missing, secret not found, quota) currently
pass through as raw subprocess output. Typed error hints vs passthrough
— leaning passthrough, because agents can match on known tool errors
and operators get the tool's own error text.

### Concurrency

Two operators editing the same shared team fleet with `generate: true`
signing keys could race at first deploy. Provider secret stores
typically have conditional-create semantics, but the fleet-level
contract hasn't defined concurrency behavior.

### State surfacing cost

`mcp-app fleet list` and similar will call `provider.status()` for
every solution. Providers may have rate limits or latency. Need:
caching policy, timeout behavior, degraded display.

### Default provider suggestions on empty machine

When `mcp-app deploy configure` runs with no providers installed,
what options does the wizard offer beyond `manual` and `script-runner`?
Hardcoded list couples mcp-app to specific providers. Leaning on
a community-maintained directory or just asking operator for a
pip spec.

## Relationship to Existing Documents

- **FLEET.md** (prior design): this document supersedes it.
  FLEET.md's provider plugin model, source field semantics, and
  fleet-registry concepts carry forward. FLEET.md's
  "solutions-as-deployments" naming, fleetless-vs-fleet distinction,
  and nested `config:` shape are revised here.
- **CONTRIBUTING.md**: architectural decisions remain. The
  "admin tooling rationalization" (#17), "agent-composed over
  provider-coupled" decisions, and "credentials are the SDK's
  concern" principles are unchanged.
- **README.md**: will link to this document once implemented.
- **author-mcp-app** skill: describes the authoring loop; this
  document describes the operating loop.

## Related Issues

- [#7](https://github.com/echomodel/mcp-app/issues/7) — Implement
  fleet commands
- [#9](https://github.com/echomodel/mcp-app/issues/9) — Deployment
  matrix (closed)
- [#17](https://github.com/echomodel/mcp-app/issues/17) — Admin
  tooling rationalization
- [#19](https://github.com/echomodel/mcp-app/issues/19) — Bundling
  skill, tests, and version awareness
