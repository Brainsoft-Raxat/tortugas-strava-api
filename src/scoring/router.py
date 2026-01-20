"""API endpoints for scoring system."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.dependencies import get_session, verify_admin_api_key
from src.scoring.calculator import get_period_boundaries, get_week_boundaries
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
    period: str = Query(
        "this_week",
        description="Period to display: this_week, last_week, this_month, last_month, this_year, last_year, custom",
    ),
    start_date: str | None = Query(
        None,
        description="Start date for custom period (YYYY-MM-DD format). Required if period=custom.",
    ),
    end_date: str | None = Query(
        None,
        description="End date for custom period (YYYY-MM-DD format). Required if period=custom.",
    ),
    db: AsyncSession = Depends(get_session),
):
    """Display beautiful leaderboard dashboard (public, no auth required).

    Parameters
    ----------
    request : Request
        FastAPI request object (for template rendering)
    period : str
        Time period to display: this_week, last_week, this_month, last_month, this_year, last_year, custom
    start_date : str | None
        Start date for custom period (YYYY-MM-DD format)
    end_date : str | None
        End date for custom period (YYYY-MM-DD format)
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    TemplateResponse
        Rendered HTML dashboard
    """
    settings = get_settings()

    # Parse custom dates if provided
    custom_start = None
    custom_end = None
    if period == "custom":
        if not start_date or not end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required for custom period",
            )
        try:
            custom_start = datetime.strptime(start_date, "%Y-%m-%d")
            custom_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Expected YYYY-MM-DD",
            )

    # Get period boundaries
    try:
        period_start, period_end, period_label = get_period_boundaries(
            period, custom_start, custom_end
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get leaderboard using range query for all periods
    leaderboard = await scoring_service.get_range_leaderboard(db, period_start, period_end)

    return templates.TemplateResponse(
        "leaderboard.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "leaderboard": leaderboard,
            "period": period,
            "period_label": period_label,
            "period_start": period_start.strftime("%Y-%m-%d"),
            "period_end": (period_end - datetime.resolution).strftime("%Y-%m-%d"),
        },
    )


@public_router.get("/athlete/{athlete_id}", include_in_schema=False)
async def athlete_detail(
    request: Request,
    athlete_id: int,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Activities per page"),
    db: AsyncSession = Depends(get_session),
):
    """Display detailed athlete page with all activities (public, no auth required).

    Parameters
    ----------
    request : Request
        FastAPI request object (for template rendering)
    athlete_id : int
        Strava athlete ID
    page : int
        Page number (1-indexed)
    page_size : int
        Number of activities per page (1-100)
    db : AsyncSession
        Database session (injected)

    Returns
    -------
    TemplateResponse
        Rendered HTML athlete detail page
    """
    settings = get_settings()

    # Get this week's breakdown
    try:
        weekly_breakdown = await scoring_service.get_athlete_breakdown(
            db, athlete_id, None
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Get all-time stats and paginated activities
    try:
        all_time_stats = await scoring_service.get_athlete_all_time_stats(
            db, athlete_id, page, page_size
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return templates.TemplateResponse(
        "athlete_detail.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "athlete_id": athlete_id,
            "athlete_name": weekly_breakdown.athlete_name,
            "profile": weekly_breakdown.profile,
            "profile_medium": weekly_breakdown.profile_medium,
            # This week stats
            "week_start": weekly_breakdown.week_start,
            "week_end": weekly_breakdown.week_end,
            "week_total_points": weekly_breakdown.total_points,
            "week_base_points": weekly_breakdown.base_points,
            "week_consistency_bonus": weekly_breakdown.consistency_bonus,
            "week_race_bonus": weekly_breakdown.race_bonus,
            "week_days_active": weekly_breakdown.days_active,
            # All-time stats
            "all_time_total_points": all_time_stats["total_points"],
            "all_time_base_points": all_time_stats["base_points"],
            "all_time_bonuses": all_time_stats["consistency_bonus"]
            + all_time_stats["race_bonus"],
            "all_time_days_active": all_time_stats["days_active"],
            # Paginated activities
            "activities": all_time_stats["activities"],
            "total_activities": all_time_stats["total_count"],
            "page": page,
            "page_size": page_size,
            "total_pages": all_time_stats["total_pages"],
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
