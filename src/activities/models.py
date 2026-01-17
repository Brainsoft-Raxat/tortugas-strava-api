"""Activity database models."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.core.database import Base


class Activity(Base):
    """Strava activity stored in database.

    Core fields for club features (leaderboards, stats, feeds).
    Full Strava response stored in raw_data for extensibility.
    """

    __tablename__ = "activities"

    # Primary key - Strava's activity ID
    id = Column(BigInteger, primary_key=True)

    # Foreign key to users table
    athlete_id = Column(BigInteger, nullable=False, index=True)

    # Core activity info
    name = Column(String, nullable=False)
    type = Column(String, nullable=False, index=True)  # Run, Ride, Swim, etc.
    sport_type = Column(String, nullable=False)  # More specific than type
    workout_type = Column(
        Integer, nullable=True
    )  # 0=default, 1=race, 2=long run, 3=workout

    # Metrics
    distance = Column(Float, nullable=False)  # meters
    moving_time = Column(Integer, nullable=False)  # seconds
    elapsed_time = Column(Integer, nullable=False)  # seconds
    total_elevation_gain = Column(Float, nullable=False)  # meters

    # Speed metrics
    average_speed = Column(Float, nullable=True)  # m/s
    max_speed = Column(Float, nullable=True)  # m/s

    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False, index=True)  # UTC
    start_date_local = Column(DateTime(timezone=True), nullable=False)  # Local time
    timezone = Column(String, nullable=True)

    # Social metrics
    kudos_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    athlete_count = Column(
        Integer, default=1
    )  # Number of athletes (for group activities)

    # Flags
    manual = Column(Boolean, default=False)  # Manually created vs. GPS recorded
    private = Column(Boolean, default=False)
    flagged = Column(Boolean, default=False)  # Flagged by Strava

    # Full Strava API response (for extensibility)
    raw_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Activity(id={self.id}, name='{self.name}', type='{self.type}', distance={self.distance})>"
