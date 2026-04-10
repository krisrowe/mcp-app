"""Data models for user records."""

from datetime import datetime
from pydantic import BaseModel


class UserAuthRecord(BaseModel):
    """Auth-specific data for a user. This is what the auth framework
    stores and retrieves — not app data like food logs or orders."""

    email: str
    created: datetime | None = None
    revoke_after: float | None = None


class UserRecord(BaseModel):
    """Full user record — auth fields + app profile.

    Loaded once at auth time, set on the current_user ContextVar.
    The profile field holds whatever the app stored at registration
    time — mcp-app does not interpret it.
    """

    email: str
    created: datetime | None = None
    revoke_after: float | None = None
    profile: dict | None = None
