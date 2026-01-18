"""Pure functions for scoring calculations.

No database access - these are pure mathematical functions that can be tested
independently.
"""

from datetime import datetime, timedelta


def calculate_base_points(moving_time_seconds: int) -> int:
    """Convert moving time to points (1 point per minute, rounded).

    Parameters
    ----------
    moving_time_seconds : int
        Activity moving time in seconds

    Returns
    -------
    int
        Base points (1 point per minute, rounded to nearest integer)
    """
    return round(moving_time_seconds / 60)


def calculate_consistency_bonus(days_active: int) -> int:
    """Get bonus points based on unique days active in week.

    Parameters
    ----------
    days_active : int
        Number of unique days with at least one activity

    Returns
    -------
    int
        Consistency bonus points

    Notes
    -----
    Bonus structure:
    - 3 days: 150 points
    - 4 days: 350 points
    - 5 days: 400 points
    - 6+ days: 400
    1points (capped)
    """
    BONUSES = {3: 150, 4: 350, 5: 400, 6: 400}
    # Cap at 6 days
    capped_days = min(days_active, 6)
    return BONUSES.get(capped_days, 0)


def calculate_race_bonus(race_count: int) -> int:
    """Calculate race bonus (250 points per race).

    Parameters
    ----------
    race_count : int
        Number of races in the period

    Returns
    -------
    int
        Total race bonus points
    """
    return race_count * 250


def get_week_boundaries(date: datetime) -> tuple[datetime, datetime]:
    """Get Monday 00:00 and next Monday 00:00 for given date.

    Parameters
    ----------
    date : datetime
        Any date within the week

    Returns
    -------
    tuple[datetime, datetime]
        (week_start, week_end) where:
        - week_start is Monday 00:00:00
        - week_end is next Monday 00:00:00

    Notes
    -----
    Week runs from Monday 00:00 to Sunday 23:59:59.
    Returns start and end as timezone-naive datetimes, expecting the caller
    to use start_date_local from Strava which is already in athlete's local time.
    """
    # Get days since Monday (0=Monday, 6=Sunday)
    days_since_monday = date.weekday()

    # Get Monday at 00:00
    week_start = date - timedelta(days=days_since_monday)
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get next Monday at 00:00
    week_end = week_start + timedelta(days=7)

    return week_start, week_end
