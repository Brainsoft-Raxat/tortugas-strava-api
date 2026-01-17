# Scoring System Implementation Plan

## Overview
Implement time-based scoring system for Tortugas Running Club as specified in `/SCORING_SYSTEM.md`.

## Data We Already Have
- ✅ `moving_time` (seconds) - for base score
- ✅ `start_date_local` - for day/week grouping
- ✅ `type` - to filter "Run" activities
- ✅ `workout_type` - to detect races (1 = race)
- ✅ `athlete_id` - to group by athlete

## Implementation Approach

### Phase 1: Core Scoring Logic (Calculate on-demand)
No materialized scores table initially - calculate from activities table.

**Why?**
- Simpler for pilot
- Easy to adjust formula
- Always accurate
- Can add caching later if needed

### Phase 2: API Endpoints

```
GET /scoring/leaderboard/weekly?date=2026-01-13
  → Returns leaderboard for week containing that date
  → If no date, returns current week

GET /scoring/leaderboard/range?start=2026-01-01&end=2026-01-31
  → Returns leaderboard for date range (cumulative)

GET /scoring/athlete/{athlete_id}/breakdown?date=2026-01-13
  → Individual athlete score breakdown for specific week
  → Shows: base points, consistency bonus, race bonuses, daily activity details
```

## File Structure

```
src/scoring/
├── calculator.py    # Pure functions for score math
├── service.py       # Score aggregation, leaderboard queries
├── router.py        # API endpoints
└── schemas.py       # Response models (LeaderboardEntry, AthleteBreakdown)
```

## Implementation Details

### calculator.py
```python
# Pure functions (no database access)

def calculate_base_points(moving_time_seconds: int) -> float:
    """Convert moving time to points (1 point per minute)"""
    return moving_time_seconds / 60

def calculate_consistency_bonus(days_active: int) -> int:
    """Get bonus points based on unique days active in week"""
    BONUSES = {3: 150, 4: 350, 5: 450, 6: 450}
    return BONUSES.get(min(days_active, 6), 0)

def calculate_race_bonus(race_count: int) -> int:
    """Calculate race bonus (250 points per race)"""
    return race_count * 250

def get_week_boundaries(date: datetime) -> tuple[datetime, datetime]:
    """Get Monday 00:00 and next Monday 00:00 for given date (Astana time)"""
    # Returns (week_start, week_end)
```

### service.py
```python
class ScoringService:
    async def get_weekly_leaderboard(
        self,
        db: AsyncSession,
        date: datetime | None = None
    ) -> list[LeaderboardEntry]:
        """
        Calculate scores for all athletes for specified week.
        If date is None, use current week.

        Steps:
        1. Determine week boundaries
        2. Query all Run activities in that week
        3. Group by athlete_id
        4. For each athlete:
           - Sum moving_time → base points
           - Count unique days → consistency bonus
           - Count races (workout_type=1) → race bonus
        5. Sort by total descending
        """

    async def get_range_leaderboard(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime
    ) -> list[LeaderboardEntry]:
        """Calculate cumulative scores for date range"""

    async def get_athlete_breakdown(
        self,
        db: AsyncSession,
        athlete_id: int,
        date: datetime | None = None
    ) -> AthleteBreakdown:
        """
        Detailed breakdown for one athlete:
        - Daily activities with points
        - Base points total
        - Consistency bonus
        - Race bonuses
        - Weekly total
        """

scoring_service = ScoringService()
```

### router.py
```python
router = APIRouter(prefix="/scoring", tags=["scoring"])

@router.get("/leaderboard/weekly", response_model=list[LeaderboardEntry])
async def get_weekly_leaderboard(
    date: str | None = None,  # YYYY-MM-DD format
    db: AsyncSession = Depends(get_session)
):
    """Get leaderboard for specific week (or current week if no date)"""

@router.get("/leaderboard/range", response_model=list[LeaderboardEntry])
async def get_range_leaderboard(
    start: str,  # YYYY-MM-DD
    end: str,    # YYYY-MM-DD
    db: AsyncSession = Depends(get_session)
):
    """Get cumulative leaderboard for date range"""

@router.get("/athlete/{athlete_id}/breakdown", response_model=AthleteBreakdown)
async def get_athlete_breakdown(
    athlete_id: int,
    date: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    """Get detailed score breakdown for one athlete"""
```

### schemas.py
```python
class LeaderboardEntry(BaseModel):
    athlete_id: int
    athlete_name: str  # firstname + lastname from User
    base_points: float
    consistency_bonus: int
    race_bonus: int
    total_points: float
    days_active: int
    race_count: int

    model_config = ConfigDict(from_attributes=True)

class DailyActivity(BaseModel):
    date: str  # YYYY-MM-DD
    activity_id: int
    name: str
    moving_time_minutes: float
    points: float
    is_race: bool

class AthleteBreakdown(BaseModel):
    athlete_id: int
    athlete_name: str
    week_start: str
    week_end: str
    daily_activities: list[DailyActivity]
    base_points: float
    consistency_bonus: int
    race_bonus: int
    total_points: float
    days_active: int
```

## Key Query Pattern

```python
# Get all Run activities for a week
activities = await db.execute(
    select(Activity)
    .filter(
        Activity.type == "Run",
        Activity.start_date_local >= week_start,
        Activity.start_date_local < week_end
    )
    .order_by(Activity.athlete_id, Activity.start_date_local)
)
activities = list(activities.scalars().all())

# Group by athlete
from itertools import groupby
athlete_activities = {
    athlete_id: list(group)
    for athlete_id, group in groupby(activities, key=lambda a: a.athlete_id)
}

# Calculate for each athlete
for athlete_id, athlete_acts in athlete_activities.items():
    base = sum(calculate_base_points(a.moving_time) for a in athlete_acts)
    days = len(set(a.start_date_local.date() for a in athlete_acts))
    races = sum(1 for a in athlete_acts if a.workout_type == 1)

    consistency = calculate_consistency_bonus(days)
    race_bonus = calculate_race_bonus(races)
    total = base + consistency + race_bonus
```

## Timezone Handling

**Decision**: Use `start_date_local` directly
- Strava already provides this in athlete's local timezone
- For Tortugas club members, this is Astana time (UTC+5)
- Week boundaries: Monday 00:00 to Sunday 23:59:59 in local time

```python
from datetime import datetime, timedelta

def get_week_start(date: datetime) -> datetime:
    """Get Monday 00:00 for week containing date"""
    days_since_monday = date.weekday()  # 0=Monday, 6=Sunday
    monday = date - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)
```

## Integration with Webhooks

**Future enhancement** (not in initial implementation):
- Add score recalculation triggers in webhook handlers
- When activity created/updated/deleted, recalculate that athlete's current week score
- Store in cache for faster leaderboard queries

## Testing Plan

1. **Unit tests** for calculator functions
2. **Integration tests** for service methods with test database
3. **Manual testing** with sample data:
   - Create test activities for different athletes
   - Verify base points calculation
   - Verify consistency bonuses (3, 4, 5, 6+ days)
   - Verify race bonus detection

## Requirements Clarifications

- ✅ Leaderboard: Only include athletes with >0 points
- ✅ Athlete names: Join with User table to get firstname + lastname
- ✅ Missing athletes: Skip activities where athlete_id not in users table
- ✅ Pagination: Not needed (small club size)

## Next Steps

1. Create `src/scoring/` module structure
2. Implement calculator.py (pure functions)
3. Implement service.py (database queries)
4. Implement schemas.py (response models)
5. Implement router.py (API endpoints)
6. Register router in main.py
7. Manual testing with test data
8. Document API endpoints

---

**Status**: Ready for implementation
**Estimated complexity**: Medium (2-3 hours of focused work)
**Dependencies**: None (all required data already in database)
