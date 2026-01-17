"""Pydantic schemas for Strava API responses."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class AthleteSchema(BaseModel):
    """Athlete information from Strava."""

    id: int
    firstname: str
    lastname: str
    profile: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    sex: Optional[str] = None
    premium: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ClubSchema(BaseModel):
    """Club information from Strava."""

    id: int
    name: str
    sport_type: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    profile: Optional[str] = None
    member_count: Optional[int] = None


class ActivitySchema(BaseModel):
    """Activity information from Strava."""

    id: int
    name: str
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float
    type: str
    sport_type: str
    start_date: datetime
    start_date_local: datetime
    timezone: str
    athlete: dict[str, Any]
    achievement_count: Optional[int] = None
    kudos_count: Optional[int] = None
    comment_count: Optional[int] = None
    athlete_count: Optional[int] = None
    photo_count: Optional[int] = None
    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    workout_type: Optional[int] = None  # 0=default, 1=race, 2=long run, 3=workout


class WebhookSubscriptionSchema(BaseModel):
    """Webhook subscription response from Strava."""

    id: int
    application_id: int
    callback_url: str
    created_at: datetime
    updated_at: datetime


class WebhookCallbackSchema(BaseModel):
    """Webhook validation callback from Strava."""

    hub_mode: Literal["subscribe"]
    hub_verify_token: str
    hub_challenge: str

    class Config:
        # Allow field names with dots
        populate_by_name = True
        # Map 'hub.challenge' to 'hub_challenge'
        fields = {
            "hub_mode": {"alias": "hub.mode"},
            "hub_verify_token": {"alias": "hub.verify_token"},
            "hub_challenge": {"alias": "hub.challenge"},
        }


class WebhookEventSchema(BaseModel):
    """Webhook event update from Strava."""

    object_type: Literal["activity", "athlete"]
    object_id: int
    aspect_type: Literal["create", "update", "delete"]
    owner_id: int
    subscription_id: int
    event_time: int
    updates: Optional[dict[str, Any]] = None


class RateLimitInfo(BaseModel):
    """Rate limit information from response headers."""

    short_usage: int  # 15-minute usage
    long_usage: int  # Daily usage
    short_limit: int  # 15-minute limit
    long_limit: int  # Daily limit
