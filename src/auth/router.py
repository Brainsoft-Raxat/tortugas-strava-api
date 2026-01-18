from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from stravalib import Client

from src.auth.schemas import UserResponse
from src.auth.service import auth_service
from src.config import get_settings
from src.dependencies import get_session, verify_admin_api_key
from src.strava.client import AsyncStravaClient
from src.sync.service import sync_service

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["authentication"])

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/authorize")
def authorize():
    """Redirect to Strava for authorization"""
    logger.info("Authorization flow initiated")

    client = Client()
    url = client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri=settings.STRAVA_REDIRECT_URI,
        scope=["activity:read_all", "profile:read_all"],
    )

    logger.debug("Generated authorization URL", url=url)
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(
    code: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Handle OAuth callback with club membership validation"""
    logger.info("OAuth callback received", has_code=bool(code))

    client = Client()

    try:
        logger.debug("Exchanging authorization code for token")
        token_response = client.exchange_code_for_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            code=code,
        )

        # Create async client for validation
        async_client = AsyncStravaClient(access_token=token_response["access_token"])

        # Get athlete info
        athlete = await async_client.get_athlete()
        logger.info(
            "Retrieved athlete info",
            athlete_id=athlete.id,
            name=f"{athlete.firstname} {athlete.lastname}",
        )

        # Validate club membership
        logger.debug("Checking club membership", athlete_id=athlete.id)
        clubs = await async_client.get_athlete_clubs()
        club_ids = [club.id for club in clubs]

        # Debug: Log detailed club information
        logger.info(
            "Clubs returned by Strava API",
            athlete_id=athlete.id,
            club_count=len(clubs),
            clubs_data=[{"id": club.id, "name": club.name} for club in clubs],
        )

        if settings.STRAVA_CLUB_ID not in club_ids:
            # Not a club member - deauthorize and reject
            logger.warning(
                "Club membership validation failed",
                athlete_id=athlete.id,
                clubs=club_ids,
                required_club=settings.STRAVA_CLUB_ID,
            )
            await async_client.deauthorize()
            return RedirectResponse(
                url=(
                    "/auth/error?message=Not+a+club+member"
                    "&error=You+must+be+a+member+of+our+club"
                ),
                status_code=303,
            )

        logger.info("Club membership validated", athlete_id=athlete.id)

        # Club member - proceed with user creation/update
        existing_user = await auth_service.get_user_by_athlete_id(db, athlete.id)

        if existing_user:
            logger.info("Updating existing user", athlete_id=athlete.id)
            user = await auth_service.update_tokens(
                db=db,
                user=existing_user,
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_at=token_response["expires_at"],
            )
            # Update profile pictures on re-authorization
            _ = await auth_service.update_profile_pictures(
                db=db,
                user=user,
                profile=athlete.profile,
                profile_medium=athlete.profile_medium,
            )
            message = f"Welcome back, {athlete.firstname}!"
        else:
            logger.info("Creating new user", athlete_id=athlete.id)
            _ = await auth_service.create_user(
                db=db,
                athlete_id=athlete.id,
                firstname=athlete.firstname,
                lastname=athlete.lastname,
                email=getattr(athlete, "email", None),
                profile=athlete.profile,
                profile_medium=athlete.profile_medium,
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                token_expires_at=token_response["expires_at"],
            )
            message = f"Welcome to Tortugas, {athlete.firstname}!"

            # Backfill activities from 2026-01-01 for new users
            logger.info(
                "Triggering background sync for new user",
                athlete_id=athlete.id,
                after="2026-01-01",
            )
            background_tasks.add_task(
                sync_service.sync_athlete_activities,
                db=db,
                athlete_id=athlete.id,
                after=datetime(2026, 1, 1),
            )

        logger.info(
            "OAuth flow completed successfully",
            athlete_id=athlete.id,
            is_new_user=not bool(existing_user),
        )

        # Redirect to success page
        return RedirectResponse(
            url=f"/auth/success?message={message}&athlete_id={athlete.id}",
            status_code=303,
        )

    except Exception as e:
        # Handle any unexpected errors
        logger.error(
            "OAuth callback failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return RedirectResponse(
            url=f"/auth/error?message=Authorization+failed&error={str(e)}",
            status_code=303,
        )


@router.get("/success")
async def success_page(request: Request, message: str, athlete_id: int):
    """Success page after successful authorization"""
    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "message": message,
            "athlete_id": athlete_id,
        },
    )


@router.get("/error")
async def error_page(request: Request, message: str, error: str):
    """Error page when authorization fails"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "message": message,
            "error": error,
        },
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_session),
    _: None = Depends(verify_admin_api_key),
):
    """List all authorized users (requires admin API key)"""
    users = await auth_service.list_authorized_users(db)
    return users


@router.delete("/deauthorize/{athlete_id}")
async def deauthorize_user(
    athlete_id: int,
    db: AsyncSession = Depends(get_session),
    _: None = Depends(verify_admin_api_key),
):
    """
    De-authorize a user and remove their access tokens (requires admin API key).

    This marks the user as unauthorized and clears their Strava tokens.
    The user will need to re-authorize to access the application again.
    """
    logger.info("Deauthorization requested", athlete_id=athlete_id)

    user = await auth_service.deauthorize_user(db, athlete_id)
    if not user:
        logger.warning("Deauthorization failed - user not found", athlete_id=athlete_id)
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(
        "User deauthorized successfully",
        athlete_id=athlete_id,
        name=f"{user.firstname} {user.lastname}",
    )

    return {
        "status": "success",
        "message": f"{user.firstname} {user.lastname} has been deauthorized",
        "athlete_id": athlete_id,
    }
