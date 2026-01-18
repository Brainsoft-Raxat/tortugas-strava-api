import time
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from src.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)

    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    email = Column(String, nullable=True)
    profile = Column(String, nullable=True)  # Large (124x124)
    profile_medium = Column(String, nullable=True)  # Medium (62x62)

    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_expires_at = Column(Integer, nullable=False)

    authorized = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def is_token_expired(self) -> bool:
        return time.time() > self.token_expires_at

    @property
    def athlete_id(self) -> int:
        """Alias for id to match Strava terminology"""
        return self.id

    @property
    def token_expired(self) -> bool:
        """Property for Pydantic serialization"""
        return self.is_token_expired()
