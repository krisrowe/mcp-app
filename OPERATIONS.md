# Operations

> **Status: ROADMAP / DESIGN.** This document describes the
> intended operator experience for building, deploying, and
> managing mcp-app solutions. Most of it is not yet implemented;
> [#7](https://github.com/echomodel/mcp-app/issues/7) tracks the
> fleet/deploy implementation. Sections below are marked **(today)**
> when they describe behavior that exists in the current release,
> and **(design)** for everything else.
>
> This document supersedes [FLEET.md](FLEET.md). Where the two
> diverge, OPERATIONS.md is authoritative going forward. FLEET.md
> remains as a historical design artifact until the replacement
> is confirmed complete.

## Overview

mcp-app solutions are Python MCP servers built on a shared
framework. Operating them — deploying, managing users, checking
health, rotating tokens — follows a unified model regardless of
which solution, which deployment target, or how many solutions
an operator manages.

The model is a single substrate (a "fleet") that scales invisibly
from a solo operator with one solution to a team managing many
solutions across multiple environments. Simple cases never encounter
the fleet abstraction. Complex cases extend naturally through the
same commands.

## Operator Experience

The sections below walk through what typing `mcp-app deploy` feels
like at different scales. CLI is the primary interface; yaml and
state files are implementation detail.

### Solo operator, single solution

You have one mcp-app solution (e.g., `echofit`) and want to deploy
it to a cloud target of your choice.

**First time:**

```bash
cd ~/projects/echofit
mcp-app deploy
  → "deploy not configured for echofit. run 'mcp-app deploy configure'."

mcp-app deploy configure
  → wizard:
      Which deploy provider? [gapp / cloudrun / local-docker / other]
      Source? [echomodel/echofit]        (inferred from git remote)
      Ref?    [main]                     (inferred from default branch)
      Multi-environment setup? [n]

mcp-app deploy
  → pre-deploy summary, confirm, provider runs
```

At most four prompts in the wizard, most with sensible defaults.
Zero yaml editing. No fleet concept mentioned.

**Subsequent deploys:**

```bash
git push
mcp-app deploy                      # summary, confirm, ship
```

**Admin:**

```bash
mcp-app users add echofit alice@example.com
mcp-app health echofit
mcp-app tokens create echofit alice@example.com
```

### Solo operator, multiple solutions

You have two mcp-app solutions (e.g., `echofit` and `gwsa`) on your
machine, each deployed independently.

```bash
cd ~/projects/echofit
mcp-app deploy configure
mcp-app deploy

cd ~/projects/gwsa
mcp-app deploy configure
mcp-app deploy

mcp-app users add echofit alice@example.com
mcp-app users add gwsa bob@example.com
```

Same commands. Nothing changes. Each `configure` adds another entry
under the same invisible default fleet.

### Multi-environment (dev / staging / prod)

You want multiple deployments of the same solution — e.g., a `dev`
for iteration and a `prod` for the stable release.

```bash
cd ~/projects/echofit
mcp-app deploy configure --deployment dev
mcp-app deploy configure --deployment prod

mcp-app deploy echofit:dev
mcp-app deploy echofit:prod --ref v1.2.3

mcp-app users add echofit:prod alice@example.com    # prod users only
mcp-app users add echofit:dev alice@example.com     # dev users (separate roster)
```

The `solution:deployment` syntax is explicit when deployments are
configured. Solo-deployment solutions don't use it.

### Multi-fleet (team or multi-machine)

You have a shared team fleet (in git) alongside your personal local
fleet.

```bash
mcp-app fleets register https://github.com/acme/team-infra --name team
mcp-app fleets use team

mcp-app deploy echofit                  # deploys team's echofit
mcp-app deploy echofit --fleet personal # one-off cross-fleet op
```

`mcp-app fleets` commands appear only when an operator has a use
for multiple fleets. Before that, the default local fleet is the
only one and is invisible.

## CLI Reference

All commands share the same substrate: the active fleet (or the one
named by `--fleet`). Overrides never require per-invocation boilerplate
in the common case.

### Deploy verbs

```bash
mcp-app deploy [target]                         # deploy (cwd-inferred or explicit)
mcp-app deploy configure [target]               # first-time wizard or edit
mcp-app deploy config <field> set <value>       # per-attribute tweak
mcp-app deploy config show
mcp-app deploy show [target]                    # effective config + what would run
```

`target` is `solution` or `solution:deployment`. When omitted, cwd
inference resolves it if cwd is an mcp-app solution directory.

### Admin verbs

```bash
mcp-app users add <target> <email>              # register, return token
mcp-app users list <target>
mcp-app users revoke <target> <email>
mcp-app tokens create <target> <email>          # issue new token for existing user
mcp-app health <target>                         # liveness check
```

Each admin verb resolves the deployed instance's URL and signing
key through the active fleet. No `connect` step — the fleet entry
and provider together supply the URL and key on demand.

### Providers (fleet-scoped)

```bash
mcp-app providers list
mcp-app providers add <name> --package <spec>
mcp-app providers config <name> <field> set <value>
mcp-app providers remove <name>
```

`<spec>` is any pip install target: PyPI name, git URL, local
path. See [Provider Plugin Model](#provider-plugin-model).

### Deployments (fleet-scoped)

```bash
mcp-app deployments list [solution]
mcp-app deployments add <target>                # same as 'deploy configure --deployment X'
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

The `fleets` namespace is advanced. Solo operators with one
invisible default fleet never run these.

### Overrides

Available on any command that targets a deployment:

| Flag | Effect |
|------|--------|
| `--fleet <name>` | Use a specific fleet for this invocation. Active fleet is default. |
| `--deployment <name>` | Specify deployment when the solution has multiple. Alternative to `solution:deployment` syntax. |
| `--ref <ref>` | Deploy a specific git ref (branch, tag, sha). Overrides the ref in fleet entry. |

There is **no `--source` flag.** Source is locked to the fleet
entry at configure time. To deploy from a different source, edit
the fleet entry or configure a second deployment. This is
intentional — see [Source locking](#source-locking).

### cwd inference

When the current directory is an mcp-app solution (its
`pyproject.toml` has `[project.entry-points."mcp_app.apps"]`), the
CLI can infer the solution name from that entry point. This
applies to `deploy`, `deploy configure`, `deploy show`, `users`,
`tokens`, `health`, and any other command that takes a target.

**Rule:** cwd only resolves the solution positional when it's
omitted. cwd never silently changes what gets deployed. `--ref`,
`--fleet`, `--deployment` are always explicit.

When a solution has multiple deployments and cwd inference can't
pick one (no `default_deployment:` in the solution entry, no
`--deployment` flag, no `solution:deployment` target), the CLI
errors with the list of available deployments.

## Schema Reference

One yaml file (`fleet.yaml`) describes providers, defaults, and
solutions. Under `~/.config/mcp-app/fleets/<fleet-name>/fleet.yaml`
for the default local fleet; under a git repo for registered fleets.

### Top level

```yaml
providers:                  # provider declarations (fleet-scoped)
  <name>:
    package: <pip-spec>     # required: pip install target
    config: {...}           # optional: provider-specific base config

defaults:                   # fleet-wide defaults
  deploy: <provider-name>   # default provider for solutions
  runtime: mcp-app          # default runtime (mcp-app | none)

solutions:
  <solution-name>:
    source: <source>        # required
    ref: <ref>              # optional; repo default branch if omitted
    deploy: ...             # optional override block
    runtime: ...            # optional override
    env: {...}              # optional env vars
    secrets: {...}          # optional secret references
    deployments:            # optional multi-env block
      <deployment-name>:
        ref: ...
        deploy: ...
        env: ...
        secrets: ...
    default_deployment: dev # optional; used for cwd inference when deployments present
```

### Solution fields

| Field | Required? | Default | Inheritable? |
|-------|-----------|---------|-------------|
| `source` | yes | — | to deployments |
| `ref` | no | repo default branch | to deployments |
| `deploy.provider` | no | `defaults.deploy` | to deployments |
| `deploy.config` | no | `providers.<name>.config` | merges into deployments |
| `runtime` | no | `defaults.runtime` | to deployments |
| `env` | no | — | merges into deployments |
| `secrets` | no | — | merges into deployments |
| `deployments` | no | single-target deploy | — |
| `default_deployment` | no | — | — |

### Inheritance

Everything cascades from defaults → solution → deployment → CLI
override:

| Attribute | Chain (lowest → highest precedence) |
|-----------|--------------------------------------|
| `deploy.provider` | `defaults.deploy` → solution's → deployment's |
| `deploy.config` | `providers.<name>.config` → solution's → deployment's (merged) |
| `runtime` | `defaults.runtime` → solution's → deployment's |
| `env` | solution's → deployment's (merged) |
| `secrets` | solution's → deployment's (merged) |
| `ref` | repo default → solution's → deployment's → `--ref` |
| `source` | solution's → deployment's (rare) |

`env:` is never allowed at `defaults` or `providers` level — it's
always solution-specific.

### Source field forms

```yaml
# GitHub repo (cloned fresh each deploy)
source: owner/repo

# Git URL (any git remote)
source: git+https://github.com/owner/repo.git

# Pre-built container image (no build, deploy directly)
source: registry.io/image:tag

# Local path (deploys from filesystem; for dev)
source: /absolute/path/to/source
```

### Source locking

`source` lives only in the fleet entry. There is no per-invocation
`--source` flag, no `--use-working-tree` flag. This is deliberate:

- Every deploy corresponds to a real commit in a real source.
  Full traceability by construction.
- Operators can't accidentally deploy the wrong repo from the wrong
  directory.
- Image tagging follows from the resolved commit sha — reproducible
  and auditable.

To deploy a different source for one invocation, edit the fleet
entry temporarily or add a second deployment. To deploy an unpushed
branch, push it first (`git push origin HEAD:wip-branch`) and
`mcp-app deploy --ref wip-branch`.

## Config Ownership

Three layers own different kinds of configuration. Mixing them
causes drift and coupling. The rule: **each piece of config lives
with the layer that varies it.**

| Layer | Owns | Examples | Where it lives |
|-------|------|----------|----------------|
| Solution author | Config intrinsic to the app | Feature flags, fixed behaviors, API schema versions | Solution repo (App constructor args, pyproject, solution-local files) |
| Operator | Config that varies by operator or environment | `LOG_LEVEL`, per-env credentials, deploy target, refs | fleet.yaml |
| Provider | Config the provider needs to deploy | GCP project, k8s namespace, region, build args | `providers:` block in fleet.yaml |

Don't lift into fleet.yaml what doesn't actually vary. Env vars
that are always the same regardless of who deploys belong in the
solution. Env vars that change per operator or per deployment
belong in fleet. Provider-specific settings belong in provider
config.

Signing keys are the exceptional case: they always vary (unique per
deployment) but never touch disk. Provider's secret store owns
them, resolved on demand.

## Provider Plugin Model

Providers are pip-installable packages that handle the cloud- or
tool-specific deploy step. mcp-app never references any specific
provider by name in code.

### Entry point discovery

A provider declares itself in its own `pyproject.toml`:

```toml
[project.entry-points."mcp_app.providers"]
gapp = "mcp_app_gapp:GappProvider"
```

When the package is pip-installed, Python's metadata registry
records this. mcp-app discovers providers at runtime:

```python
from importlib.metadata import entry_points
providers = entry_points(group="mcp_app.providers")
provider_cls = providers[name].load()
```

The group name `mcp_app.providers` is the only hardcoded string in
mcp-app. Provider names come from `fleet.yaml`.

### Provider interface

```python
class DeployProvider:
    def deploy(self, request: DeployRequest) -> DeployResult:
        """
        Execute a deploy.
        Request includes: solution name, deployment name (optional),
        source, ref, resolved config (after inheritance), env,
        secrets references, runtime.
        Returns: exit code, streamed stdout/stderr, resolved URL.
        """

    def status(self, solution: str, deployment: str | None) -> Status:
        """Return current URL, last deployed ref/sha, health."""

    def resolve_signing_key(self, solution: str, deployment: str | None) -> str:
        """Fetch signing key from provider's secret store on demand."""
```

Providers receive fully-resolved configuration — fleet does the
inheritance and merging. Providers don't read fleet.yaml themselves.

### Package field — pip install target

The `package:` field accepts any pip-compatible install target:

```yaml
providers:
  # PyPI name
  gapp:
    package: mcp-app-gapp

  # PyPI with version constraint
  cloudrun:
    package: "mcp-app-cloudrun>=1.2,<2.0"

  # Git repo, HEAD
  custom:
    package: git+https://github.com/me/my-provider.git

  # Git repo, pinned ref
  custom-pinned:
    package: git+https://github.com/me/my-provider.git@v1.2.0

  # Local path (dev)
  custom-dev:
    package: ~/projects/my-provider
```

mcp-app passes the value unmodified to `pip install`. Community
providers, private providers, and forks all work through the same
mechanism.

### Who publishes providers

Three patterns, all identical from mcp-app's view:

1. **Framework author** publishes primary providers (e.g.,
   `mcp-app-gapp`).
2. **Community** publishes bridges to other platforms (e.g.,
   `mcp-app-hackerhost`, `mcp-app-fly`).
3. **Cloud vendors** publish native support (e.g., a provider
   package maintained by the platform itself).

All three register the same entry-point group. The operator
`pip install`s (or lets mcp-app lazily install) whichever they
want.

## State Ownership

mcp-app does **not** store per-solution runtime state locally.
Everything mcp-app persists is configuration (intent). Runtime
state (what's deployed, where, at what revision) lives with the
provider.

**Local files (operator machine):**

```
~/.config/mcp-app/
  fleets.yaml                            # registry: which fleets, which active
  fleets/<fleet-name>/
    fleet.yaml                           # the manifest (config, not state)
```

That's it. No `setup.json`, no `deploy.yaml`, no per-solution state
file. The framework today (pre-fleet) writes `~/.config/{app-name}/setup.json`
for admin connect state; that file is removed in the fleet-everywhere
model because the fleet manifest holds the same information plus more.

**Runtime state** (deployed URL, last sha, image tag, health,
secrets):

- Owned by the provider.
- Fetched by calling `provider.status(solution, deployment)` on
  demand.
- Signing keys resolved by `provider.resolve_signing_key(...)` —
  never cached on disk.
- Provider-internal caching is fine (in-memory per session, or
  its own cache file if the provider implements one) — that's the
  provider's choice.

This is why there is no `connect` step in the fleet-everywhere
model. The fleet entry tells the CLI which provider to ask; the
provider always knows where the deployed service lives.

## Operational Flows

### First deploy

Walkthrough from a clean machine:

```bash
$ mcp-app deploy
  → "deploy not configured for echofit. run 'mcp-app deploy configure'."

$ mcp-app deploy configure
  # silently creates ~/.config/mcp-app/fleets.yaml and the default fleet
  # prompts for provider (discovers installed; offers common options if none)
  # pip-installs chosen provider if not present
  # prompts for source (defaults to git remote), ref (defaults to main)
  # prompts for multi-environment (default: no)
  # writes providers + defaults + solution entry to fleet.yaml
  → "Configured. Run 'mcp-app deploy'."

$ mcp-app deploy
  → Pre-deploy summary:
      Deploy echofit
        source:   echomodel/echofit @ main → a3f1c2e
        provider: gapp
        runtime:  mcp-app
      Proceed? [y/N]
  → Provider runs. Output streams to terminal.
  → Provider returns exit 0 on success.
  → CLI prints next-step hints: users add, health.
```

### Redeploy

```bash
$ git push
$ mcp-app deploy
  → Pre-deploy summary (new sha resolved)
  → Confirm, run.
```

### Multi-environment deploy

```bash
$ mcp-app deploy configure --deployment dev
$ mcp-app deploy configure --deployment prod

$ mcp-app deploy echofit:dev
$ mcp-app deploy echofit:prod --ref v1.2.3
```

Each deployment has its own URL, signing key, and user roster.
Admin operations use the `solution:deployment` target explicitly.

### Secret lifecycle

Secrets are never operator-managed in fleet.yaml (only references
or directives). Provider handles creation and retrieval:

```yaml
solutions:
  echofit:
    secrets:
      SIGNING_KEY:
        generate: true          # provider creates at first deploy, reuses after
      THIRD_PARTY_API_KEY:
        value: third-party-key-v3   # reference to existing entry in provider's store
```

- `generate: true` → provider generates at first deploy, stores in
  its secret store, reuses thereafter.
- `value: <ref>` → provider resolves the reference. fleet.yaml
  never contains actual secret values.

Retrieval uses the operator's cloud auth (e.g., ADC for GCP). Keys
never land on disk.

### Pre-deploy summary

Always printed before executing a deploy:

```
Deploy echofit
  source:   echomodel/echofit @ main → a3f1c2e
  provider: gapp (project=my-proj, region=us-central1)
  target:   (new deployment) | https://echofit-xxx.a.run.app
  runtime:  mcp-app
  env:      LOG_LEVEL=INFO
  secrets:  SIGNING_KEY (generated), THIRD_PARTY_API_KEY (from ref)

Proceed? [y/N]
```

Shows:

- Resolved sha (not just the ref)
- Provider and its effective config
- Target URL (or "new" for first deploy)
- Env vars being passed (secrets redacted)

### Safety checks

Before the summary, the CLI performs soft checks:

- **Unpushed commits**: if source is a remote ref and local branch
  is ahead of origin, warn.
- **Uncommitted changes**: if source is a local path, warn about
  dirty working tree.
- **Stale refs**: if the requested ref doesn't exist in the
  remote, error.

Warnings are non-blocking by default. `--strict` promotes them to
errors (for CI). `--yes` skips the confirm for scripted runs.

## Skills and Agent Integration

Two agent-facing skills, designed to be platform-agnostic (Claude
Code, Gemini CLI, and others with skill systems).

### `deploy-mcp-app`

Fires on user intents like "deploy this," "ship this," "redeploy."

1. Detects mcp-app solution via `pyproject.toml` entry point.
2. Runs `mcp-app deploy`. If not configured, catches the error
   and runs `mcp-app deploy configure` interactively.
3. After success, prints next-step hints.

Does not encode any specific deploy tool. Providers handle
tool-specific mechanics; the skill just calls the CLI.

### `manage-mcp-app`

Fires on post-deploy intents like "add a user," "check health,"
"rotate a token."

1. Resolves solution/deployment from intent and cwd.
2. Runs the matching `mcp-app users ...`, `mcp-app health ...`, etc.
3. Returns the CLI's output.

### Framework test: README conformance

Part of the free test suite mcp-app ships. Asserts every mcp-app
solution's README links to the deploy-mcp-app skill so operators
cloning a solution learn the canonical deployment pattern:

```python
def test_readme_references_deploy_skill(app_root):
    readme = app_root / "README.md"
    content = readme.read_text()
    assert "deploy-mcp-app" in content or "# mcp-app:no-deployment-section" in content
```

## Design Principles

These are invariants the design preserves.

1. **Solution repo stays deploy-agnostic.** No Dockerfile required,
   no deploy config, no cloud references in the solution.
2. **CLI simplicity is the invariant.** Any new feature must extend
   through defaults/inference, never by requiring new mandatory CLI
   arguments for the simple case.
3. **One substrate.** Fleet is the only state layer. No parallel
   setup.json, deploy.yaml, or per-solution state files.
4. **Invisible until needed.** Solo operators never see fleet
   concepts. Vocabulary surfaces only when the operator reaches for
   the capability.
5. **No silent cwd influence on deploys.** cwd is a CLI ergonomic
   shortcut for solution identification; it never changes what
   gets deployed.
6. **Source locked, ref overridable.** Every deploy maps to a real
   commit. No working-tree escape hatch.
7. **Providers own runtime state.** mcp-app orchestrates; providers
   know where things are deployed.
8. **Secrets never on disk.** Provider secret stores handle it;
   resolved on demand.
9. **CLI is the only writer of config files.** Agents and skills
   call CLI verbs, not yaml files directly.

## Open Design Questions

Tracked for resolution during implementation. Not blocking on this
document.

### Provider invocation: cwd, clone, or checkout?

When a provider deploys, does it operate in the operator's cwd,
clone the source fresh to a temp dir, or checkout to a known
location? Different providers have different needs:

- `gapp` may internally invoke `gcloud builds submit --source .`
  which tars up the current directory.
- A direct `gcloud run deploy --source` does the same.
- An image-only source (`registry.io/image:tag`) needs no local
  filesystem.
- A git source (`owner/repo`) implies mcp-app (or the provider)
  clones fresh.

Resolution: the fleet probably shouldn't assume. The provider's
invocation contract needs to specify what it expects (cwd vs
checkout vs image). May need a capability declaration per provider
so fleet can prepare the right working directory.

### `package:` field spec

Explicitly support arbitrary pip-compatible install targets (git
URLs, local paths, etc.)? FLEET.md's prior design used PyPI-style
names throughout; this document proposes full pass-through. Needs
to be ratified in implementation.

### Non-happy-path UX contract

Provider errors (auth missing, secret not found, quota exceeded,
region unavailable) currently pass through as raw subprocess output.
Should providers expose typed error hints, or is subprocess
passthrough sufficient? Leaning passthrough — it's Unix-native and
agents can match on known tool errors.

### Concurrency

Two operators editing the same shared team fleet with
`generate: true` signing keys could race at first deploy. Provider
secret stores typically have conditional-create semantics, but the
fleet-level contract hasn't defined concurrency behavior.

### State surfacing

Although mcp-app doesn't store runtime state locally,
`mcp-app fleet list` and similar commands need to *show* state.
They'll call `provider.status()` for every solution. Providers may
have rate limits or latency. Design needs: caching policy (provider
vs CLI), timeout behavior, degraded display when a provider is
unreachable.

### Default provider for empty new fleet

When `mcp-app deploy configure` runs on a fresh machine and no
providers are installed, what should the wizard offer? Hardcoded
list of common options (gapp, cloudrun, local-docker) couples
mcp-app to specific providers. Alternative: read a community-
maintained directory of known providers. Or: operator must know
what they want and type a package spec.

## Relationship to Existing Documents

- **FLEET.md** (prior design): this document supersedes it.
  FLEET.md's provider plugin model, source field semantics, and
  fleet-registry concepts carry forward. FLEET.md's
  "solutions-as-deployments" naming, fleetless-vs-fleet distinction,
  and `cwd is never used` absolutism are revised here.
- **CONTRIBUTING.md**: architectural decisions remain. The
  "admin tooling rationalization" (#17), "agent-composed over
  provider-coupled" decisions, and "credentials are the SDK's
  concern" principles are unchanged.
- **README.md**: will link to this document for deployment
  guidance once implemented.
- **author-mcp-app skill**: describes the authoring loop; this
  document describes the operating loop. Independent concerns.

## Related Issues

- [#7](https://github.com/echomodel/mcp-app/issues/7) — Implement
  fleet commands and fleet/fleetless target resolution
- [#9](https://github.com/echomodel/mcp-app/issues/9) — Deployment
  matrix (closed; this document extends it)
- [#17](https://github.com/echomodel/mcp-app/issues/17) — Admin
  tooling rationalization
- [#19](https://github.com/echomodel/mcp-app/issues/19) — Bundling
  skill, tests, and version awareness
