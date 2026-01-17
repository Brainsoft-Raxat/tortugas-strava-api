"""Async rate limiter for Strava API."""

import asyncio
import logging
from typing import Literal, Optional

from src.strava.schemas import RateLimitInfo

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """Async rate limiter that respects Strava's API limits.

    Strava rate limits:
    - Short-term: 600 requests per 15 minutes
    - Long-term: 30,000 requests per day
    """

    def __init__(self, priority: Literal["low", "medium", "high"] = "high"):
        """Initialize rate limiter.

        Parameters
        ----------
        priority : str
            - 'high': No throttling, only sleep when limit exceeded
            - 'medium': Spread requests evenly over 15-min window
            - 'low': Spread requests evenly over 24-hour window
        """
        self.priority = priority
        self.current_limits: Optional[RateLimitInfo] = None

    def update_limits(self, headers: dict[str, str]) -> None:
        """Update rate limit info from response headers.

        Parameters
        ----------
        headers : dict
            HTTP response headers from Strava API
        """
        # Normalize header keys to lowercase
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Try both header formats Strava uses
        usage_key = "x-ratelimit-usage"
        limit_key = "x-ratelimit-limit"

        if usage_key in headers_lower and limit_key in headers_lower:
            usage = [int(x) for x in headers_lower[usage_key].split(",")]
            limit = [int(x) for x in headers_lower[limit_key].split(",")]

            self.current_limits = RateLimitInfo(
                short_usage=usage[0],
                long_usage=usage[1],
                short_limit=limit[0],
                long_limit=limit[1],
            )
            logger.debug(f"Updated rate limits: {self.current_limits}")
        else:
            logger.warning("No rate limit headers found in response")

    async def wait_if_needed(self) -> None:
        """Sleep if rate limits require it based on priority."""
        if not self.current_limits:
            return

        limits = self.current_limits

        # Check if limits exceeded
        if limits.long_usage >= limits.long_limit:
            logger.warning(
                f"Long-term rate limit exceeded: {limits.long_usage}/{limits.long_limit}"
            )
            # Wait until next day (simplified - in prod calculate exact time)
            await asyncio.sleep(60)
            return

        if limits.short_usage >= limits.short_limit:
            logger.warning(
                f"Short-term rate limit exceeded: {limits.short_usage}/{limits.short_limit}"
            )
            # Wait until next 15-min window (simplified)
            await asyncio.sleep(30)
            return

        # Apply priority-based throttling
        if self.priority == "high":
            # No throttling
            return
        elif self.priority == "medium":
            # Spread evenly over 15 minutes
            remaining = limits.short_limit - limits.short_usage
            if remaining > 0:
                wait_time = 900 / remaining  # 900 seconds = 15 minutes
                await asyncio.sleep(min(wait_time, 2))  # Max 2 seconds
        elif self.priority == "low":
            # Spread evenly over 24 hours
            remaining = limits.long_limit - limits.long_usage
            if remaining > 0:
                wait_time = 86400 / remaining  # 86400 seconds = 24 hours
                await asyncio.sleep(min(wait_time, 5))  # Max 5 seconds
