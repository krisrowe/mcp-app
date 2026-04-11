"""Remote auth adapter — implements UserAuthStore over HTTP.

Connects to a deployed mcp-app instance's /admin REST endpoints.
Mints admin JWTs locally using the signing key.
"""

from datetime import datetime, timezone, timedelta

import httpx
import jwt as pyjwt

from mcp_app.models import UserAuthRecord, UserRecord


class RemoteAuthAdapter:
    """UserAuthStore implementation backed by a remote mcp-app instance."""

    def __init__(self, base_url: str, signing_key: str,
                 http_client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.signing_key = signing_key
        self._http = http_client or httpx.AsyncClient()

    def _admin_token(self) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin",
            "scope": "admin",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        return pyjwt.encode(payload, self.signing_key, algorithm="HS256")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._admin_token()}"}

    async def health_check(self) -> dict:
        resp = await self._http.get(f"{self.base_url}/health", timeout=10)
        return {"status": "healthy", "status_code": resp.status_code}

    async def get(self, email: str) -> UserAuthRecord | None:
        users = await self.list()
        for u in users:
            if u.email == email:
                return u
        return None

    async def get_full(self, email: str) -> UserRecord | None:
        record = await self.get(email)
        if not record:
            return None
        return UserRecord(
            email=record.email,
            created=record.created,
            revoke_after=record.revoke_after,
        )

    async def list(self) -> list[UserAuthRecord]:
        resp = await self._http.get(
            f"{self.base_url}/admin/users",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return [UserAuthRecord(**u) for u in resp.json()]

    async def save(self, record: UserAuthRecord, profile: dict | None = None) -> dict:
        body = {"email": record.email}
        if profile is not None:
            body["profile"] = profile
        resp = await self._http.post(
            f"{self.base_url}/admin/users",
            headers=self._headers(),
            json=body,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    async def delete(self, email: str) -> None:
        resp = await self._http.delete(
            f"{self.base_url}/admin/users/{email}",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()

    async def create_token(self, email: str) -> dict:
        resp = await self._http.post(
            f"{self.base_url}/admin/tokens",
            headers=self._headers(),
            json={"email": email},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
