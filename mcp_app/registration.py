"""Client registration command generation for deployed mcp-app instances.

Produces the exact commands an operator (or agent) pastes into each MCP
client (Claude Code, Gemini CLI) and the URL form used by Claude.ai, for
a given deployed service URL and bearer token.
"""

from __future__ import annotations

import shutil
import subprocess

CLIENTS = ("claude", "gemini", "claude.ai")
SCOPES = ("user", "project")

TOKEN_PLACEHOLDER = "<YOUR_PAT>"


def _claude_cmd(name: str, url: str, token: str, scope: str) -> str:
    return (
        f'claude mcp add --transport http '
        f'--header "Authorization: Bearer {token}" '
        f'-s {scope} {name} {url}'
    )


def _gemini_cmd(name: str, url: str, token: str, scope: str) -> str:
    return (
        f'gemini mcp add {name} {url} '
        f'--scope {scope} --transport http '
        f'--header "Authorization: Bearer {token}"'
    )


def _claude_ai_url(url: str, token: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}token={token}"


def _is_registered(client: str, name: str, scope: str) -> bool | None:
    """Check whether the service is already registered at the given scope.

    Returns True/False on a successful check, or None if detection was not
    possible (CLI missing, errored, or the output could not be parsed).
    """
    try:
        if client == "claude":
            if not shutil.which("claude"):
                return None
            proc = subprocess.run(
                ["claude", "mcp", "list", "-s", scope],
                capture_output=True, text=True, timeout=5,
            )
        elif client == "gemini":
            if not shutil.which("gemini"):
                return None
            proc = subprocess.run(
                ["gemini", "mcp", "list", "--scope", scope],
                capture_output=True, text=True, timeout=5,
            )
        else:
            return None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return any(name in line.split() for line in proc.stdout.splitlines())


def generate_registrations(
    name: str,
    url: str,
    token: str | None = None,
    clients: list[str] | None = None,
    scopes: list[str] | None = None,
    detect_registered: bool = False,
) -> dict:
    """Produce ready-to-paste client registration commands.

    Args:
        name: MCP server name the client will know the service by.
        url: Deployed service base URL. Must end with '/'.
        token: User bearer token. If None, a placeholder is emitted so the
            operator can substitute after minting a token.
        clients: Subset of {"claude", "gemini", "claude.ai"}. Default: all.
        scopes: Subset of {"user", "project"}. Default: all. Ignored for
            claude.ai (always a URL form).
        detect_registered: If True, shell out to each CLI's list command to
            note whether the name is already registered at that scope.

    Returns:
        Dict with 'url', 'name', 'token', and an 'entries' list of
        {client, scope, command, registered} records.
    """
    if not url.endswith("/"):
        url = url + "/"
    clients = list(clients) if clients else list(CLIENTS)
    scopes = list(scopes) if scopes else list(SCOPES)
    tok = token or TOKEN_PLACEHOLDER
    entries = []

    for client in clients:
        if client == "claude.ai":
            entries.append({
                "client": "claude.ai",
                "scope": None,
                "command": _claude_ai_url(url, tok),
                "registered": None,
            })
            continue
        for scope in scopes:
            if client == "claude":
                cmd = _claude_cmd(name, url, tok, scope)
            elif client == "gemini":
                cmd = _gemini_cmd(name, url, tok, scope)
            else:
                continue
            registered = (
                _is_registered(client, name, scope) if detect_registered else None
            )
            entries.append({
                "client": client,
                "scope": scope,
                "command": cmd,
                "registered": registered,
            })

    return {
        "url": url,
        "name": name,
        "token_provided": token is not None,
        "entries": entries,
    }


def format_registrations(result: dict) -> str:
    """Render the output of generate_registrations() as human text."""
    lines = []
    for e in result["entries"]:
        client = e["client"]
        scope = e["scope"]
        reg = e["registered"]
        if scope is None:
            label = f"{client} (manual)"
        else:
            status = (
                "registered" if reg is True
                else "not registered" if reg is False
                else "status unknown"
            )
            label = f"{client} ({scope} scope, {status})"
        lines.append(f"{label}:")
        lines.append(f"  {e['command']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
