"""Activity endpoints for querying stored activities."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.activities.service import activity_service
from src.dependencies import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/activities", tags=["activities"])


class ActivityResponse(BaseModel):
    """Activity response schema."""

    id: int
    athlete_id: int
    name: str
    type: str
    sport_type: str
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float
    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    start_date: str
    kudos_count: int
    comment_count: int

    class Config:
        from_attributes = True


@router.get("/recent", response_model=list[ActivityResponse])
async def get_recent_activities(
    limit: int = 50, db: AsyncSession = Depends(get_session)
):
    """Get recent activities across all athletes.

    Parameters
    ----------
    limit : int
        Maximum number of activities to return (default: 50)
    """
    activities = await activity_service.get_recent_activities(db, limit=limit)
    return activities


@router.get("/athlete/{athlete_id}", response_model=list[ActivityResponse])
async def get_athlete_activities(
    athlete_id: int,
    limit: int = 30,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
):
    """Get activities for a specific athlete.

    Parameters
    ----------
    athlete_id : int
        Strava athlete ID
    limit : int
        Maximum number of activities to return (default: 30)
    offset : int
        Number of activities to skip (default: 0)
    """
    activities = await activity_service.get_athlete_activities(
        db, athlete_id=athlete_id, limit=limit, offset=offset
    )
    return activities


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(activity_id: int, db: AsyncSession = Depends(get_session)):
    """Get a specific activity by ID.

    Parameters
    ----------
    activity_id : int
        Strava activity ID
    """
    activity = await activity_service.get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity
