"""Strava service layer for managing athlete clients."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.service import auth_service
from src.strava.client import AsyncStravaClient
from src.strava.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)


class StravaService:
    """Service layer for Strava API operations.

    Handles token management, client instantiation, and business logic.
    """

    async def get_client_for_athlete(
        self,
        db: AsyncSession,
        athlete_id: int,
        priority: str = "high",
    ) -> AsyncStravaClient:
        """Get an authenticated Strava client for a specific athlete.

        Automatically handles token refresh if needed.

        Parameters
        ----------
        db : AsyncSession
            Database session
        athlete_id : int
            Strava athlete ID
        priority : str
            Rate limiter priority ('high', 'medium', 'low')

        Returns
        -------
        AsyncStravaClient
            Authenticated client for the athlete

        Raises
        ------
        TokenExpired
            If token is expired and cannot be refreshed
        """
        # Get user from database
        user = await auth_service.get_user_by_athlete_id(db, athlete_id)
        if not user:
            raise ValueError(f"Athlete {athlete_id} not found in database")

        # Check if token needs refresh
        if user.is_token_expired():
            logger.info(f"Token expired for athlete {athlete_id}, refreshing...")
            user = await auth_service.refresh_token_if_needed(db, user)

        # Create client with user's access token
        rate_limiter = AsyncRateLimiter(priority=priority)
        return AsyncStravaClient(
            access_token=user.access_token, rate_limiter=rate_limiter
        )

    async def get_client_for_user(
        self, user: User, priority: str = "high"
    ) -> AsyncStravaClient:
        """Get an authenticated Strava client for a User object.

        Use this when you already have a User object and don't need
        to refresh the token.

        Parameters
        ----------
        user : User
            User model with valid access_token
        priority : str
            Rate limiter priority ('high', 'medium', 'low')

        Returns
        -------
        AsyncStravaClient
            Authenticated client
        """
        rate_limiter = AsyncRateLimiter(priority=priority)
        return AsyncStravaClient(
            access_token=user.access_token, rate_limiter=rate_limiter
        )


strava_service = StravaService()
