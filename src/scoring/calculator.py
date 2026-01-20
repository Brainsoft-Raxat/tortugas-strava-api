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
    - 6+ days: 400 points (capped)
    """
    BONUSES = {3: 300, 4: 350, 5: 400, 6: 400}
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


def get_period_boundaries(
    period: str, custom_start: datetime | None = None, custom_end: datetime | None = None
) -> tuple[datetime, datetime, str]:
    """Get date boundaries for specified period type.

    Parameters
    ----------
    period : str
        Period type: 'this_week', 'last_week', 'this_month', 'last_month', 'this_year', 'last_year', 'custom'
    custom_start : datetime | None
        Start date for custom period (required if period='custom')
    custom_end : datetime | None
        End date for custom period (required if period='custom')

    Returns
    -------
    tuple[datetime, datetime, str]
        (start_date, end_date, period_label) where:
        - start_date is the beginning of the period (inclusive)
        - end_date is the end of the period (exclusive)
        - period_label is a human-readable description

    Raises
    ------
    ValueError
        If period is 'custom' but custom_start or custom_end is missing
        If period is not one of the valid options
    """
    now = datetime.now()

    if period == "this_week":
        start, end = get_week_boundaries(now)
        label = f"{start.strftime('%Y-%m-%d')} - {(end - timedelta(days=1)).strftime('%Y-%m-%d')}"
        return start, end, label

    elif period == "last_week":
        # Get last week's Monday
        last_week = now - timedelta(days=7)
        start, end = get_week_boundaries(last_week)
        label = f"{start.strftime('%Y-%m-%d')} - {(end - timedelta(days=1)).strftime('%Y-%m-%d')}"
        return start, end, label

    elif period == "this_month":
        # Get first day of this month to now (or end of month if you want full month)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Get first day of next month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        label = start.strftime("%B %Y")
        return start, end, label

    elif period == "last_month":
        # Get first day of last month
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_this_month
        # Get first day of last month
        if first_of_this_month.month == 1:
            start = first_of_this_month.replace(year=first_of_this_month.year - 1, month=12)
        else:
            start = first_of_this_month.replace(month=first_of_this_month.month - 1)
        label = start.strftime("%B %Y")
        return start, end, label

    elif period == "this_year":
        # Get Jan 1 of this year to end of this year
        this_year = now.year
        start = datetime(this_year, 1, 1, 0, 0, 0)
        end = datetime(this_year + 1, 1, 1, 0, 0, 0)
        label = str(this_year)
        return start, end, label

    elif period == "last_year":
        # Get Jan 1 to Dec 31 of last year
        last_year = now.year - 1
        start = datetime(last_year, 1, 1, 0, 0, 0)
        end = datetime(last_year + 1, 1, 1, 0, 0, 0)
        label = str(last_year)
        return start, end, label

    elif period == "custom":
        if custom_start is None or custom_end is None:
            raise ValueError("custom_start and custom_end are required for custom period")
        start = custom_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = custom_end.replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"{start.strftime('%Y-%m-%d')} - {(end - timedelta(days=1)).strftime('%Y-%m-%d')}"
        return start, end, label

    else:
        raise ValueError(
            f"Invalid period: {period}. Must be one of: this_week, last_week, this_month, last_month, this_year, last_year, custom"
        )
