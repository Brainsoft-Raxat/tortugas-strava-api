from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UserResponse(BaseModel):
    id: int
    athlete_id: int
    firstname: str
    lastname: str
    profile: Optional[str] = None
    profile_medium: Optional[str] = None
    created_at: datetime
    token_expired: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    athlete_id: int
