"""JWT verification — validates tokens, loads user record, sets context."""

import os
from dataclasses import dataclass

import jwt as pyjwt

from mcp_app.context import current_user, hydrate_profile
from mcp_app.models import UserRecord


@dataclass
class VerifiedToken:
    """Result of a successful token verification."""
    client_id: str
    scopes: list[str]
    expires_at: int | None = None


class JWTVerifier:
    """Validates JWTs, loads user record, sets current_user ContextVar.

    One store read per request — loads auth + profile together.

    Reads configuration from environment variables:
        SIGNING_KEY: JWT signing key (required). No default — must be set.
        JWT_AUD: Expected audience claim. If unset, audience is not checked.
    """

    def __init__(self, auth_store):
        self.auth_store = auth_store
        self.signing_key = os.environ.get("SIGNING_KEY")
        if not self.signing_key:
            raise RuntimeError(
                "SIGNING_KEY environment variable is required. "
                "Set it to a strong random value:\n"
                "  export SIGNING_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
            )
        self.audience = os.environ.get("JWT_AUD")

    async def verify_token(self, token: str) -> VerifiedToken | None:
        try:
            claims = pyjwt.decode(
                token,
                self.signing_key,
                algorithms=["HS256"],
                audience=self.audience,
            )
        except pyjwt.InvalidTokenError:
            return None

        email = claims.get("sub")
        if not email:
            return None

        # Load full user record — one store read
        user_record = await self.auth_store.get_full(email)
        if not user_record:
            return None

        if user_record.revoke_after and claims.get("iat", 0) < user_record.revoke_after:
            return None

        # Hydrate profile with registered Pydantic model if available
        user_record.profile = hydrate_profile(user_record.profile)

        # Set current_user ContextVar — available to all tool functions
        current_user.set(user_record)

        return VerifiedToken(
            client_id=email,
            scopes=claims.get("scopes", []),
            expires_at=claims.get("exp"),
        )
