"""Strava API exceptions."""


class StravaException(Exception):
    """Base exception for Strava API errors."""

    pass


class ObjectNotFound(StravaException):
    """Raised when a requested object is not found (404)."""

    pass


class AccessUnauthorized(StravaException):
    """Raised when access is unauthorized (401)."""

    pass


class RateLimitExceeded(StravaException):
    """Raised when rate limit is exceeded."""

    pass


class TokenExpired(StravaException):
    """Raised when access token has expired."""

    pass
