from typing import Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from stravalib import Client

from src.activities.models import Activity
from src.auth.models import User
from src.config import get_settings

settings = get_settings()


class AuthService:
    def __init__(self):
        self.client_id = settings.STRAVA_CLIENT_ID
        self.client_secret = settings.STRAVA_CLIENT_SECRET

    async def get_user_by_athlete_id(
        self, db: AsyncSession, athlete_id: int
    ) -> Optional[User]:
        result = await db.execute(select(User).filter(User.id == athlete_id))
        return result.scalar_one_or_none()

    async def create_user(self, db: AsyncSession, athlete_id: int, **kwargs) -> User:
        try:
            user = User(id=athlete_id, **kwargs)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise e

    async def update_tokens(
        self,
        db: AsyncSession,
        user: User,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ) -> User:
        try:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.token_expires_at = expires_at
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise e

    async def update_profile_pictures(
        self,
        db: AsyncSession,
        user: User,
        profile: Optional[str],
        profile_medium: Optional[str],
    ) -> User:
        """Update user's profile pictures from Strava."""
        try:
            user.profile = profile
            user.profile_medium = profile_medium
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise e

    async def refresh_token_if_needed(self, db: AsyncSession, user: User) -> User:
        if user.is_token_expired():
            client = Client()
            try:
                token_response = client.refresh_access_token(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    refresh_token=user.refresh_token,
                )
            except Exception as e:
                raise ValueError("Failed to refresh token") from e

            await self.update_tokens(
                db=db,
                user=user,
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_at=token_response["expires_at"],
            )

        return user

    async def list_authorized_users(self, db: AsyncSession) -> list[User]:
        result = await db.execute(select(User).filter(User.authorized))
        return list(result.scalars().all())

    async def deauthorize_user(
        self, db: AsyncSession, athlete_id: int
    ) -> Optional[User]:
        """
        De-authorize a user by calling Strava's deauthorize endpoint.

        This will:
        1. Revoke all tokens on Strava's side
        2. Remove the app from the athlete's connected apps
        3. Delete all activities for this athlete from our database
        4. Delete the user from our database

        Parameters
        ----------
        db : AsyncSession
            Database session
        athlete_id : int
            Strava athlete ID

        Returns
        -------
        Optional[User]
            The deauthorized user data, or None if not found
        """
        user = await self.get_user_by_athlete_id(db, athlete_id)
        if not user:
            return None

        # Call Strava's deauthorization endpoint
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://www.strava.com/oauth/deauthorize",
                    params={"access_token": user.access_token},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                # Log but continue - we still want to deauthorize locally
                # even if Strava's endpoint fails (token might be expired)
                print(f"Strava deauthorize failed: {e}")

        # Delete user's activities and user record from database
        try:
            # First delete all activities for this athlete
            await db.execute(delete(Activity).where(Activity.athlete_id == athlete_id))

            # Then delete the user
            await db.delete(user)
            await db.commit()
            return user
        except Exception as e:
            await db.rollback()
            raise e


auth_service = AuthService()
