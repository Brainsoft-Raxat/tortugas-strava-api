"""Service layer for scoring calculations."""

from datetime import datetime
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activities.models import Activity
from src.auth.models import User
from src.scoring.calculator import (
    calculate_base_points,
    calculate_consistency_bonus,
    calculate_race_bonus,
    get_week_boundaries,
)
from src.scoring.schemas import AthleteBreakdown, DailyActivity, LeaderboardEntry


class ScoringService:
    """Service for calculating athlete scores and leaderboards."""

    async def get_weekly_leaderboard(
        self, db: AsyncSession, date: datetime | None = None
    ) -> list[LeaderboardEntry]:
        """Calculate scores for all athletes for specified week.

        Parameters
        ----------
        db : AsyncSession
            Database session
        date : datetime | None
            Date within the week to calculate scores for.
            If None, uses current date.

        Returns
        -------
        list[LeaderboardEntry]
            Leaderboard entries sorted by total points (descending).
            Only includes athletes with >0 points.
        """
        # Use current date if not specified
        if date is None:
            date = datetime.now()

        # Get week boundaries
        week_start, week_end = get_week_boundaries(date)

        # Query all Run activities for the week
        result = await db.execute(
            select(Activity)
            .filter(
                Activity.type == "Run",
                Activity.start_date_local >= week_start,
                Activity.start_date_local < week_end,
            )
            .order_by(Activity.athlete_id, Activity.start_date_local)
        )
        activities = list(result.scalars().all())

        # Group activities by athlete
        athlete_activities = {
            athlete_id: list(group)
            for athlete_id, group in groupby(activities, key=lambda a: a.athlete_id)
        }

        # Get all athlete IDs and fetch their user info
        athlete_ids = list(athlete_activities.keys())
        if not athlete_ids:
            return []

        user_result = await db.execute(select(User).filter(User.id.in_(athlete_ids)))
        users = {user.id: user for user in user_result.scalars().all()}

        # Calculate scores for each athlete
        leaderboard: list[LeaderboardEntry] = []

        for athlete_id, athlete_acts in athlete_activities.items():
            # Skip if user not found
            user = users.get(athlete_id)
            if user is None:
                continue

            # Calculate base points
            base_points = sum(
                calculate_base_points(activity.moving_time) for activity in athlete_acts
            )

            # Calculate total time (in hours) and distance (in km)
            total_time_seconds = sum(activity.moving_time for activity in athlete_acts)
            total_time = total_time_seconds / 3600  # Convert to hours
            total_distance_meters = sum(activity.distance for activity in athlete_acts)
            total_distance = total_distance_meters / 1000  # Convert to km

            # Calculate average pace (min/km)
            avg_pace = None
            if total_distance > 0:
                avg_pace = (total_time_seconds / 60) / total_distance  # min/km

            # Count unique days
            unique_dates = {
                activity.start_date_local.date() for activity in athlete_acts
            }
            days_active = len(unique_dates)

            # Count races (workout_type == 1)
            race_count = sum(
                1 for activity in athlete_acts if activity.workout_type == 1
            )

            # Calculate bonuses
            consistency_bonus = calculate_consistency_bonus(days_active)
            race_bonus = calculate_race_bonus(race_count)

            # Calculate total
            total_points = base_points + consistency_bonus + race_bonus

            # Only include athletes with >0 points
            if total_points > 0:
                entry = LeaderboardEntry(
                    athlete_id=athlete_id,
                    athlete_name=f"{user.firstname} {user.lastname}",
                    base_points=base_points,
                    consistency_bonus=consistency_bonus,
                    race_bonus=race_bonus,
                    total_points=total_points,
                    days_active=days_active,
                    race_count=race_count,
                    total_time=total_time,
                    total_distance=total_distance,
                    avg_pace=avg_pace,
                )
                leaderboard.append(entry)

        # Sort by total points descending
        leaderboard.sort(key=lambda x: x.total_points, reverse=True)

        return leaderboard

    async def get_range_leaderboard(
        self, db: AsyncSession, start_date: datetime, end_date: datetime
    ) -> list[LeaderboardEntry]:
        """Calculate cumulative scores for date range.

        Parameters
        ----------
        db : AsyncSession
            Database session
        start_date : datetime
            Start of date range (inclusive)
        end_date : datetime
            End of date range (exclusive)

        Returns
        -------
        list[LeaderboardEntry]
            Leaderboard entries sorted by total points (descending).
            Only includes athletes with >0 points.
        """
        # Query all Run activities in the date range
        result = await db.execute(
            select(Activity)
            .filter(
                Activity.type == "Run",
                Activity.start_date_local >= start_date,
                Activity.start_date_local < end_date,
            )
            .order_by(Activity.athlete_id, Activity.start_date_local)
        )
        activities = list(result.scalars().all())

        # Group activities by athlete
        athlete_activities = {
            athlete_id: list(group)
            for athlete_id, group in groupby(activities, key=lambda a: a.athlete_id)
        }

        # Get all athlete IDs and fetch their user info
        athlete_ids = list(athlete_activities.keys())
        if not athlete_ids:
            return []

        user_result = await db.execute(select(User).filter(User.id.in_(athlete_ids)))
        users = {user.id: user for user in user_result.scalars().all()}

        # Calculate scores for each athlete
        leaderboard: list[LeaderboardEntry] = []

        for athlete_id, athlete_acts in athlete_activities.items():
            # Skip if user not found
            user = users.get(athlete_id)
            if user is None:
                continue

            # Calculate base points
            base_points = sum(
                calculate_base_points(activity.moving_time) for activity in athlete_acts
            )

            # Calculate total time (in hours) and distance (in km)
            total_time_seconds = sum(activity.moving_time for activity in athlete_acts)
            total_time = total_time_seconds / 3600  # Convert to hours
            total_distance_meters = sum(activity.distance for activity in athlete_acts)
            total_distance = total_distance_meters / 1000  # Convert to km

            # Calculate average pace (min/km)
            avg_pace = None
            if total_distance > 0:
                avg_pace = (total_time_seconds / 60) / total_distance  # min/km

            # Count unique days
            unique_dates = {
                activity.start_date_local.date() for activity in athlete_acts
            }
            days_active = len(unique_dates)

            # Count races (workout_type == 1)
            race_count = sum(
                1 for activity in athlete_acts if activity.workout_type == 1
            )

            # Calculate bonuses
            consistency_bonus = calculate_consistency_bonus(days_active)
            race_bonus = calculate_race_bonus(race_count)

            # Calculate total
            total_points = base_points + consistency_bonus + race_bonus

            # Only include athletes with >0 points
            if total_points > 0:
                entry = LeaderboardEntry(
                    athlete_id=athlete_id,
                    athlete_name=f"{user.firstname} {user.lastname}",
                    base_points=base_points,
                    consistency_bonus=consistency_bonus,
                    race_bonus=race_bonus,
                    total_points=total_points,
                    days_active=days_active,
                    race_count=race_count,
                    total_time=total_time,
                    total_distance=total_distance,
                    avg_pace=avg_pace,
                )
                leaderboard.append(entry)

        # Sort by total points descending
        leaderboard.sort(key=lambda x: x.total_points, reverse=True)

        return leaderboard

    async def get_athlete_breakdown(
        self, db: AsyncSession, athlete_id: int, date: datetime | None = None
    ) -> AthleteBreakdown:
        """Get detailed score breakdown for one athlete.

        Parameters
        ----------
        db : AsyncSession
            Database session
        athlete_id : int
            Strava athlete ID
        date : datetime | None
            Date within the week to calculate breakdown for.
            If None, uses current date.

        Returns
        -------
        AthleteBreakdown
            Detailed breakdown with daily activities and score components

        Raises
        ------
        ValueError
            If athlete not found in users table
        """
        # Use current date if not specified
        if date is None:
            date = datetime.now()

        # Get week boundaries
        week_start, week_end = get_week_boundaries(date)

        # Get athlete/user info
        user_result = await db.execute(select(User).filter(User.id == athlete_id))
        user = user_result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"Athlete {athlete_id} not found")

        # Query all Run activities for this athlete in the week
        result = await db.execute(
            select(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.type == "Run",
                Activity.start_date_local >= week_start,
                Activity.start_date_local < week_end,
            )
            .order_by(Activity.start_date_local)
        )
        activities = list(result.scalars().all())

        # Build daily activities list
        daily_activities: list[DailyActivity] = []
        for activity in activities:
            moving_time_minutes = activity.moving_time / 60
            distance_km = activity.distance / 1000  # Convert meters to km

            # Calculate pace (min/km)
            pace = None
            if distance_km > 0:
                pace = moving_time_minutes / distance_km

            points = calculate_base_points(activity.moving_time)
            is_race = activity.workout_type == 1

            daily_activity = DailyActivity(
                date=activity.start_date_local.strftime("%Y-%m-%d"),
                activity_id=activity.id,
                name=activity.name,
                moving_time_minutes=moving_time_minutes,
                distance_km=distance_km,
                pace=pace,
                points=points,
                is_race=is_race,
            )
            daily_activities.append(daily_activity)

        # Calculate totals
        base_points = sum(activity.points for activity in daily_activities)

        # Count unique days
        unique_dates = {
            datetime.fromisoformat(activity.date).date()
            for activity in daily_activities
        }
        days_active = len(unique_dates)

        # Count races
        race_count = sum(1 for activity in daily_activities if activity.is_race)

        # Calculate bonuses
        consistency_bonus = calculate_consistency_bonus(days_active)
        race_bonus = calculate_race_bonus(race_count)

        # Calculate total
        total_points = base_points + consistency_bonus + race_bonus

        breakdown = AthleteBreakdown(
            athlete_id=athlete_id,
            athlete_name=f"{user.firstname} {user.lastname}",
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=(week_end - datetime.resolution).strftime("%Y-%m-%d"),
            daily_activities=daily_activities,
            base_points=base_points,
            consistency_bonus=consistency_bonus,
            race_bonus=race_bonus,
            total_points=total_points,
            days_active=days_active,
        )

        return breakdown


# Singleton instance
scoring_service = ScoringService()
