"""JWT identity middleware — validates tokens, verifier sets current_user."""

import json
from urllib.parse import parse_qs

from mcp_app.verifier import JWTVerifier


class JWTMiddleware:
    """Validates JWT from Authorization header or ?token= query param.

    The verifier handles user record loading and setting the
    current_user ContextVar. This middleware just extracts the token
    and delegates to the verifier.

    Rejects with 401/403 on failure. Passes through /health.
    """

    def __init__(self, app, verifier: JWTVerifier, store=None):
        self.app = app
        self.verifier = verifier

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if path == "/health":
            return await self.app(scope, receive, send)

        token = _extract_token(scope)
        if not token:
            return await _send_error(send, 401, "Missing authentication token")

        access = await self.verifier.verify_token(token)
        if not access:
            return await _send_error(send, 403, "Invalid or revoked token")

        await self.app(scope, receive, send)


def _extract_token(scope: dict) -> str | None:
    """Extract JWT from Authorization header or ?token= query param."""
    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    if auth.startswith("Bearer "):
        return auth[7:]

    query_string = scope.get("query_string", b"").decode()
    if query_string:
        params = parse_qs(query_string)
        tokens = params.get("token", [])
        if tokens:
            return tokens[0]

    return None


async def _send_error(send, status: int, message: str) -> None:
    """Send a JSON error response."""
    body = json.dumps({"error": message}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
