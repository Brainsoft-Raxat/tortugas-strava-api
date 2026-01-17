from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from stravalib import Client

from src.auth.schemas import UserResponse
from src.auth.service import auth_service
from src.config import get_settings
from src.dependencies import get_session, verify_admin_api_key
from src.strava.client import AsyncStravaClient

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["authentication"])

# Setup templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/authorize")
def authorize():
    """Redirect to Strava for authorization"""
    client = Client()
    url = client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri=settings.STRAVA_REDIRECT_URI,
        scope=["activity:read_all", "profile:read_all"],
    )
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(code: str, db: AsyncSession = Depends(get_session)):
    """Handle OAuth callback with club membership validation"""
    client = Client()

    try:
        token_response = client.exchange_code_for_token(
            client_id=settings.STRAVA_CLIENT_ID,
            client_secret=settings.STRAVA_CLIENT_SECRET,
            code=code,
        )

        # Create async client for validation
        async_client = AsyncStravaClient(access_token=token_response["access_token"])

        # Get athlete info
        athlete = await async_client.get_athlete()

        # Validate club membership
        clubs = await async_client.get_athlete_clubs()
        club_ids = [club.id for club in clubs]

        if settings.STRAVA_CLUB_ID not in club_ids:
            # Not a club member - deauthorize and reject
            await async_client.deauthorize()
            return RedirectResponse(
                url=(
                    "/auth/error?message=Not+a+club+member"
                    "&error=You+must+be+a+member+of+our+club"
                ),
                status_code=303,
            )

        # Club member - proceed with user creation/update
        existing_user = await auth_service.get_user_by_athlete_id(db, athlete.id)

        if existing_user:
            _ = await auth_service.update_tokens(
                db=db,
                user=existing_user,
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_at=token_response["expires_at"],
            )
            message = f"Welcome back, {athlete.firstname}!"
        else:
            _ = await auth_service.create_user(
                db=db,
                athlete_id=athlete.id,
                firstname=athlete.firstname,
                lastname=athlete.lastname,
                email=getattr(athlete, "email", None),
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                token_expires_at=token_response["expires_at"],
            )
            message = f"Welcome to Tortugas, {athlete.firstname}!"

        # Redirect to success page
        return RedirectResponse(
            url=f"/auth/success?message={message}&athlete_id={athlete.id}",
            status_code=303,
        )

    except Exception as e:
        # Handle any unexpected errors
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
    user = await auth_service.deauthorize_user(db, athlete_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "status": "success",
        "message": f"{user.firstname} {user.lastname} has been deauthorized",
        "athlete_id": athlete_id,
    }
