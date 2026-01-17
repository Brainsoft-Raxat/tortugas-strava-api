"""Pydantic schemas for scoring API responses."""

from pydantic import BaseModel, ConfigDict


class LeaderboardEntry(BaseModel):
    """Single entry in the leaderboard.

    Attributes
    ----------
    athlete_id : int
        Strava athlete ID
    athlete_name : str
        Full name (firstname + lastname from User table)
    base_points : int
        Points from total moving time (rounded)
    consistency_bonus : int
        Bonus for running on multiple days
    race_bonus : int
        Bonus for race activities
    total_points : int
        Sum of all point components
    days_active : int
        Number of unique days with activities
    race_count : int
        Number of race activities
    """

    athlete_id: int
    athlete_name: str
    base_points: int
    consistency_bonus: int
    race_bonus: int
    total_points: int
    days_active: int
    race_count: int

    model_config = ConfigDict(from_attributes=True)


class DailyActivity(BaseModel):
    """Single activity with scoring details.

    Attributes
    ----------
    date : str
        Activity date in YYYY-MM-DD format
    activity_id : int
        Strava activity ID
    name : str
        Activity name/title
    moving_time_minutes : float
        Moving time in minutes (exact)
    points : int
        Base points earned from this activity (rounded)
    is_race : bool
        Whether this is a race activity
    """

    date: str
    activity_id: int
    name: str
    moving_time_minutes: float
    points: int
    is_race: bool


class AthleteBreakdown(BaseModel):
    """Detailed score breakdown for a single athlete.

    Attributes
    ----------
    athlete_id : int
        Strava athlete ID
    athlete_name : str
        Full name (firstname + lastname from User table)
    week_start : str
        Start of week in YYYY-MM-DD format
    week_end : str
        End of week in YYYY-MM-DD format
    daily_activities : list[DailyActivity]
        All activities in the period
    base_points : int
        Total points from moving time (rounded)
    consistency_bonus : int
        Bonus for running on multiple days
    race_bonus : int
        Bonus for race activities
    total_points : int
        Sum of all point components
    days_active : int
        Number of unique days with activities
    """

    athlete_id: int
    athlete_name: str
    week_start: str
    week_end: str
    daily_activities: list[DailyActivity]
    base_points: int
    consistency_bonus: int
    race_bonus: int
    total_points: int
    days_active: int
