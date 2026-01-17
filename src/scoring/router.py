"""API endpoints for scoring system."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_session, verify_admin_api_key
from src.scoring.schemas import AthleteBreakdown, LeaderboardEntry
from src.scoring.service import scoring_service

router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
    dependencies=[Depends(verify_admin_api_key)],
)


@router.get("/leaderboard/weekly", response_model=list[LeaderboardEntry])
async def get_weekly_leaderboard(
    date: str | None = Query(
        None,
        description="Date in YYYY-MM-DD format. If not provided, uses current week.",
    ),
    db: AsyncSession = Depends(get_session),
):
    """Get leaderboard for specific week (or current week if no date).

    Week runs from Monday 00:00 to Sunday 23:59:59.
    Returns athletes sorted by total points (descending).
    Only includes athletes with >0 points.

    Parameters
    ----------
    date : str | None
        Date in YYYY-MM-DD format within the week to query.
        If None, uses current date.
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    list[LeaderboardEntry]
        Leaderboard entries with scores and breakdowns

    Raises
    ------
    HTTPException
        400 if date format is invalid
    """
    # Parse date if provided
    date_obj = None
    if date is not None:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Expected YYYY-MM-DD",
            )

    # Get leaderboard
    leaderboard = await scoring_service.get_weekly_leaderboard(db, date_obj)

    return leaderboard


@router.get("/leaderboard/range", response_model=list[LeaderboardEntry])
async def get_range_leaderboard(
    start: str = Query(..., description="Start date in YYYY-MM-DD format (inclusive)"),
    end: str = Query(..., description="End date in YYYY-MM-DD format (exclusive)"),
    db: AsyncSession = Depends(get_session),
):
    """Get cumulative leaderboard for date range.

    Calculates total scores across all activities in the date range.
    Returns athletes sorted by total points (descending).
    Only includes athletes with >0 points.

    Parameters
    ----------
    start : str
        Start date in YYYY-MM-DD format (inclusive)
    end : str
        End date in YYYY-MM-DD format (exclusive)
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    list[LeaderboardEntry]
        Leaderboard entries with cumulative scores

    Raises
    ------
    HTTPException
        400 if date format is invalid or end date is before start date
    """
    # Parse dates
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Expected YYYY-MM-DD. Error: {e}",
        )

    # Validate date range
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # Get leaderboard
    leaderboard = await scoring_service.get_range_leaderboard(db, start_date, end_date)

    return leaderboard


@router.get("/athlete/{athlete_id}/breakdown", response_model=AthleteBreakdown)
async def get_athlete_breakdown(
    athlete_id: int,
    date: str | None = Query(
        None,
        description="Date in YYYY-MM-DD format. If not provided, uses current week.",
    ),
    db: AsyncSession = Depends(get_session),
):
    """Get detailed score breakdown for one athlete.

    Shows daily activities, base points, bonuses, and totals for a specific week.

    Parameters
    ----------
    athlete_id : int
        Strava athlete ID
    date : str | None
        Date in YYYY-MM-DD format within the week to query.
        If None, uses current date.
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    AthleteBreakdown
        Detailed breakdown with daily activities and score components

    Raises
    ------
    HTTPException
        400 if date format is invalid
        404 if athlete not found
    """
    # Parse date if provided
    date_obj = None
    if date is not None:
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date}. Expected YYYY-MM-DD",
            )

    # Get breakdown
    try:
        breakdown = await scoring_service.get_athlete_breakdown(
            db, athlete_id, date_obj
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return breakdown
