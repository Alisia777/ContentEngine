from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupabaseAdminUser:
    user_id: str
    email: str
    display_name: str | None = None


@dataclass(frozen=True)
class TeamInviteResult:
    user_profile_id: int
    membership_id: int
    email: str
    role: str
    invited: bool
    membership_created: bool


@dataclass(frozen=True)
class TeamMemberView:
    membership_id: int
    user_profile_id: int
    email: str
    display_name: str | None
    role: str
    status: str
    profile_active: bool
    created_at: object
    updated_at: object
