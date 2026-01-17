"""API routes for syncing activities."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_session, verify_admin_api_key
from src.sync.service import sync_service

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(verify_admin_api_key)],
)


class SyncRequest(BaseModel):
    """Request model for syncing activities."""

    after: datetime = Field(
        ...,
        description="Start date for syncing activities (ISO 8601 format)",
        examples=["2026-01-01T00:00:00Z"],
    )
    before: datetime | None = Field(
        None,
        description="End date for syncing activities. If not provided, syncs until now.",
        examples=["2026-01-18T00:00:00Z"],
    )


class SyncResponse(BaseModel):
    """Response model for sync operation."""

    athlete_id: int
    synced_count: int
    updated_count: int
    total_processed: int
    errors: list[str]
    pages_processed: int


@router.post("/activities/{athlete_id}", response_model=SyncResponse)
async def sync_athlete_activities(
    athlete_id: int,
    request: SyncRequest,
    db: AsyncSession = Depends(get_session),
):
    """Sync historical activities for an athlete.

    This endpoint fetches activities from Strava for a specific athlete
    within the given date range and stores them in the database.
    Useful for backfilling activities that occurred before webhook setup.

    Parameters
    ----------
    athlete_id : int
        Strava athlete ID
    request : SyncRequest
        Date range for syncing (after is required, before is optional)
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    SyncResponse
        Summary of sync operation including counts and any errors
    """
    result = await sync_service.sync_athlete_activities(
        db=db,
        athlete_id=athlete_id,
        after=request.after,
        before=request.before,
    )

    return SyncResponse(**result)
