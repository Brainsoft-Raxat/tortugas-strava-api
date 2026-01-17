from pydantic import BaseModel
from datetime import datetime


class UserResponse(BaseModel):
    id: int
    athlete_id: int
    firstname: str
    lastname: str
    created_at: datetime
    token_expired: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int
    athlete_id: int
