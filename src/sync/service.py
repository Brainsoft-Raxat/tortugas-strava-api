"""Sync service for backfilling activities from Strava."""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.activities.service import activity_service
from src.strava.service import strava_service

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing historical activities from Strava."""

    async def sync_athlete_activities(
        self,
        db: AsyncSession,
        athlete_id: int,
        after: datetime,
        before: datetime | None = None,
    ) -> dict:
        """Sync activities for an athlete within a date range.

        Parameters
        ----------
        db : AsyncSession
            Database session
        athlete_id : int
            Strava athlete ID
        after : datetime
            Start date for syncing activities (inclusive)
        before : datetime | None
            End date for syncing activities (inclusive).
            If None, uses current time.

        Returns
        -------
        dict
            Summary of sync operation with counts and errors
        """
        # Convert datetimes to Unix timestamps (Strava API requirement)
        after_timestamp = int(after.timestamp())
        before_timestamp = int(before.timestamp()) if before else None

        logger.info(
            f"Starting activity sync for athlete {athlete_id} "
            f"from {after} to {before or 'now'}"
        )

        # Get Strava client with low priority (bulk operation)
        client = await strava_service.get_client_for_athlete(
            db, athlete_id, priority="low"
        )

        synced_count = 0
        updated_count = 0
        errors = []
        page = 1

        try:
            while True:
                # Fetch activities page by page (max 200 per page)
                activities = await client.get_activities(
                    after=after_timestamp,
                    before=before_timestamp,
                    page=page,
                    per_page=200,
                )

                # No more activities to fetch
                if not activities:
                    logger.info(f"No more activities found on page {page}")
                    break

                logger.info(
                    f"Fetched {len(activities)} activities on page {page} "
                    f"for athlete {athlete_id}"
                )

                # Store each activity
                for activity_data in activities:
                    try:
                        # Check if activity exists
                        existing = await activity_service.get_activity(
                            db, activity_data.id
                        )

                        if existing:
                            # Update existing activity
                            await activity_service.update_activity(
                                db, existing, activity_data
                            )
                            updated_count += 1
                        else:
                            # Create new activity
                            await activity_service.create_activity(db, activity_data)
                            synced_count += 1

                    except Exception as e:
                        error_msg = (
                            f"Failed to sync activity {activity_data.id}: {str(e)}"
                        )
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Move to next page
                page += 1

        except Exception as e:
            error_msg = f"Error during sync on page {page}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        logger.info(
            f"Activity sync completed for athlete {athlete_id}: "
            f"{synced_count} created, {updated_count} updated, "
            f"{len(errors)} errors"
        )

        return {
            "athlete_id": athlete_id,
            "synced_count": synced_count,
            "updated_count": updated_count,
            "total_processed": synced_count + updated_count,
            "errors": errors,
            "pages_processed": page - 1,
        }


sync_service = SyncService()
