"""API endpoints for scoring system."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.dependencies import get_session, verify_admin_api_key
from src.scoring.calculator import get_week_boundaries
from src.scoring.schemas import AthleteBreakdown, LeaderboardEntry
from src.scoring.service import scoring_service

# Setup Jinja2 templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Public router (no auth required)
public_router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
)

# Protected router (requires admin API key)
router = APIRouter(
    prefix="/scoring",
    tags=["scoring"],
    dependencies=[Depends(verify_admin_api_key)],
)


@public_router.get("/dashboard", include_in_schema=False)
async def leaderboard_dashboard(
    request: Request,
    date: str | None = Query(
        None,
        description="Date in YYYY-MM-DD format. If not provided, uses current week.",
    ),
    db: AsyncSession = Depends(get_session),
):
    """Display beautiful leaderboard dashboard (public, no auth required).

    Parameters
    ----------
    request : Request
        FastAPI request object (for template rendering)
    date : str | None
        Date in YYYY-MM-DD format within the week to query.
        If None, uses current date.
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    TemplateResponse
        Rendered HTML dashboard
    """
    settings = get_settings()

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

    # If no date provided, use current date
    if date_obj is None:
        date_obj = datetime.now()

    # Get week boundaries for display
    week_start, week_end = get_week_boundaries(date_obj)

    # Get leaderboard
    leaderboard = await scoring_service.get_weekly_leaderboard(db, date_obj)

    return templates.TemplateResponse(
        "leaderboard.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "leaderboard": leaderboard,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": (week_end - datetime.resolution).strftime("%Y-%m-%d"),
        },
    )


@public_router.get("/athlete/{athlete_id}", include_in_schema=False)
async def athlete_detail(
    request: Request,
    athlete_id: int,
    date: str | None = Query(
        None,
        description="Date in YYYY-MM-DD format. If not provided, uses current week.",
    ),
    db: AsyncSession = Depends(get_session),
):
    """Display detailed score breakdown for an athlete (public, no auth required).

    Parameters
    ----------
    request : Request
        FastAPI request object (for template rendering)
    athlete_id : int
        Strava athlete ID
    date : str | None
        Date in YYYY-MM-DD format within the week to query.
        If None, uses current date.
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    TemplateResponse
        Rendered HTML athlete detail page
    """
    settings = get_settings()

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

    # Get athlete breakdown
    try:
        breakdown = await scoring_service.get_athlete_breakdown(
            db, athlete_id, date_obj
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return templates.TemplateResponse(
        "athlete_detail.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "athlete_name": breakdown.athlete_name,
            "week_start": breakdown.week_start,
            "week_end": breakdown.week_end,
            "total_points": breakdown.total_points,
            "base_points": breakdown.base_points,
            "consistency_bonus": breakdown.consistency_bonus,
            "race_bonus": breakdown.race_bonus,
            "days_active": breakdown.days_active,
            "activities": breakdown.daily_activities,
        },
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
