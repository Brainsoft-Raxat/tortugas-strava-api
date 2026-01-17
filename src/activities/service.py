"""Activity service for CRUD operations."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activities.models import Activity
from src.strava.schemas import ActivitySchema

logger = logging.getLogger(__name__)


class ActivityService:
    """Service for managing activities in the database."""

    async def get_activity(
        self, db: AsyncSession, activity_id: int
    ) -> Optional[Activity]:
        """Get activity by ID.

        Parameters
        ----------
        db : AsyncSession
            Database session
        activity_id : int
            Strava activity ID

        Returns
        -------
        Activity | None
            Activity if found, None otherwise
        """
        result = await db.execute(select(Activity).filter(Activity.id == activity_id))
        return result.scalar_one_or_none()

    async def create_activity(
        self, db: AsyncSession, activity_data: ActivitySchema
    ) -> Activity:
        """Create activity from Strava API response.

        Parameters
        ----------
        db : AsyncSession
            Database session
        activity_data : ActivitySchema
            Validated activity data from Strava API

        Returns
        -------
        Activity
            Created activity
        """
        # Check if activity already exists
        existing = await self.get_activity(db, activity_data.id)
        if existing:
            logger.warning(f"Activity {activity_data.id} already exists, updating")
            return await self.update_activity(db, existing, activity_data)

        # Create new activity
        activity = Activity(
            id=activity_data.id,
            athlete_id=activity_data.athlete["id"],
            name=activity_data.name,
            type=activity_data.type,
            sport_type=activity_data.sport_type,
            workout_type=activity_data.workout_type,
            distance=activity_data.distance,
            moving_time=activity_data.moving_time,
            elapsed_time=activity_data.elapsed_time,
            total_elevation_gain=activity_data.total_elevation_gain,
            average_speed=activity_data.average_speed,
            max_speed=activity_data.max_speed,
            start_date=activity_data.start_date,
            start_date_local=activity_data.start_date_local,
            timezone=activity_data.timezone,
            kudos_count=activity_data.kudos_count or 0,
            comment_count=activity_data.comment_count or 0,
            athlete_count=activity_data.athlete_count or 1,
            # Store full response for future use
            raw_data=activity_data.model_dump(mode="json"),
        )

        db.add(activity)
        await db.commit()
        await db.refresh(activity)

        logger.info(
            f"Created activity {activity.id}: {activity.name} "
            f"({activity.distance}m, {activity.type})"
        )
        return activity

    async def update_activity(
        self, db: AsyncSession, activity: Activity, activity_data: ActivitySchema
    ) -> Activity:
        """Update existing activity.

        Parameters
        ----------
        db : AsyncSession
            Database session
        activity : Activity
            Existing activity to update
        activity_data : ActivitySchema
            New activity data from Strava API

        Returns
        -------
        Activity
            Updated activity
        """
        # Update fields
        activity.name = activity_data.name
        activity.type = activity_data.type
        activity.sport_type = activity_data.sport_type
        activity.workout_type = activity_data.workout_type
        activity.distance = activity_data.distance
        activity.moving_time = activity_data.moving_time
        activity.elapsed_time = activity_data.elapsed_time
        activity.total_elevation_gain = activity_data.total_elevation_gain
        activity.average_speed = activity_data.average_speed
        activity.max_speed = activity_data.max_speed
        activity.kudos_count = activity_data.kudos_count or 0
        activity.comment_count = activity_data.comment_count or 0
        activity.athlete_count = activity_data.athlete_count or 1
        activity.raw_data = activity_data.model_dump(mode="json")
        activity.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(activity)

        logger.info(f"Updated activity {activity.id}: {activity.name}")
        return activity

    async def delete_activity(self, db: AsyncSession, activity_id: int) -> bool:
        """Delete activity.

        Parameters
        ----------
        db : AsyncSession
            Database session
        activity_id : int
            Activity ID to delete

        Returns
        -------
        bool
            True if deleted, False if not found
        """
        activity = await self.get_activity(db, activity_id)
        if not activity:
            logger.warning(f"Activity {activity_id} not found for deletion")
            return False

        await db.delete(activity)
        await db.commit()

        logger.info(f"Deleted activity {activity_id}")
        return True

    async def get_athlete_activities(
        self,
        db: AsyncSession,
        athlete_id: int,
        limit: int = 30,
        offset: int = 0,
    ) -> list[Activity]:
        """Get activities for a specific athlete.

        Parameters
        ----------
        db : AsyncSession
            Database session
        athlete_id : int
            Athlete ID
        limit : int
            Max number of activities to return
        offset : int
            Number of activities to skip

        Returns
        -------
        list[Activity]
            List of activities
        """
        result = await db.execute(
            select(Activity)
            .filter(Activity.athlete_id == athlete_id)
            .order_by(Activity.start_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_recent_activities(
        self, db: AsyncSession, limit: int = 50
    ) -> list[Activity]:
        """Get recent activities across all athletes.

        Parameters
        ----------
        db : AsyncSession
            Database session
        limit : int
            Max number of activities to return

        Returns
        -------
        list[Activity]
            List of recent activities
        """
        result = await db.execute(
            select(Activity).order_by(Activity.start_date.desc()).limit(limit)
        )
        return list(result.scalars().all())


activity_service = ActivityService()
