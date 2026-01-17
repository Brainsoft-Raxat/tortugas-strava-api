"""Async Strava API client."""

import logging
from typing import Any, Optional

import httpx

from src.strava.exceptions import (
    AccessUnauthorized,
    ObjectNotFound,
    RateLimitExceeded,
    StravaException,
)
from src.strava.rate_limiter import AsyncRateLimiter
from src.strava.schemas import (
    ActivitySchema,
    AthleteSchema,
    ClubSchema,
    WebhookSubscriptionSchema,
)

logger = logging.getLogger(__name__)


class AsyncStravaClient:
    """Async HTTP client for Strava API v3.

    This client handles low-level HTTP requests to Strava's API.
    It supports automatic rate limiting and error handling.
    """

    BASE_URL = "https://www.strava.com/api/v3"

    def __init__(
        self,
        access_token: str,
        rate_limiter: Optional[AsyncRateLimiter] = None,
    ):
        """Initialize Strava API client.

        Parameters
        ----------
        access_token : str
            Valid Strava access token for the athlete
        rate_limiter : AsyncRateLimiter, optional
            Custom rate limiter. If None, uses default high-priority limiter.
        """
        self.access_token = access_token
        self.rate_limiter = rate_limiter or AsyncRateLimiter(priority="high")

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated request to Strava API.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, PUT, DELETE)
        endpoint : str
            API endpoint (e.g., '/athlete')
        params : dict, optional
            Query parameters
        json_data : dict, optional
            JSON body for POST/PUT requests

        Returns
        -------
        dict or list
            Parsed JSON response

        Raises
        ------
        ObjectNotFound
            When resource not found (404)
        AccessUnauthorized
            When access is unauthorized (401)
        RateLimitExceeded
            When rate limit exceeded (429)
        StravaException
            For other API errors
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Add access token to params
        if params is None:
            params = {}
        params["access_token"] = self.access_token

        logger.debug(f"{method} {url} with params {params}")

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method, url=url, params=params, json=json_data, timeout=30.0
            )

            # Update rate limits from response headers
            self.rate_limiter.update_limits(dict(response.headers))

            # Handle errors
            await self._handle_errors(response)

            # Apply rate limiting for next request
            await self.rate_limiter.wait_if_needed()

            # Handle empty responses (204 No Content)
            if response.status_code == 204:
                return {}

            return response.json()

    async def _handle_errors(self, response: httpx.Response) -> None:
        """Handle HTTP errors from Strava API.

        Parameters
        ----------
        response : httpx.Response
            HTTP response object

        Raises
        ------
        ObjectNotFound, AccessUnauthorized, RateLimitExceeded, StravaException
        """
        if response.is_success:
            return

        # Try to get error message from response
        try:
            error_data = response.json()
            error_msg = error_data.get("message", response.text)
        except Exception:
            error_msg = response.text

        # Raise appropriate exception
        if response.status_code == 404:
            raise ObjectNotFound(f"Not found: {error_msg}")
        elif response.status_code == 401:
            raise AccessUnauthorized(f"Unauthorized: {error_msg}")
        elif response.status_code == 429:
            raise RateLimitExceeded(f"Rate limit exceeded: {error_msg}")
        elif 400 <= response.status_code < 500:
            raise StravaException(f"Client error {response.status_code}: {error_msg}")
        elif 500 <= response.status_code < 600:
            raise StravaException(f"Server error {response.status_code}: {error_msg}")
        else:
            raise StravaException(f"Unknown error {response.status_code}: {error_msg}")

    # =========================================================================
    # Athlete Endpoints
    # =========================================================================

    async def get_athlete(self) -> AthleteSchema:
        """Get the currently authenticated athlete.

        Returns
        -------
        AthleteSchema
            Athlete information
        """
        data = await self._request("GET", "/athlete")
        return AthleteSchema.model_validate(data)

    async def get_athlete_clubs(self) -> list[ClubSchema]:
        """Get clubs the authenticated athlete belongs to.

        Returns
        -------
        list[ClubSchema]
            List of clubs the athlete is a member of
        """
        data = await self._request("GET", "/athlete/clubs")
        return [ClubSchema.model_validate(club) for club in data]

    async def deauthorize(self) -> None:
        """Revoke the current access token.

        This deauthorizes the application and invalidates the access token.
        Used to revoke access for athletes who are not club members.
        """
        await self._request("POST", "/oauth/deauthorize")

    # =========================================================================
    # Activity Endpoints
    # =========================================================================

    async def get_activities(
        self,
        before: Optional[int] = None,
        after: Optional[int] = None,
        page: int = 1,
        per_page: int = 30,
    ) -> list[ActivitySchema]:
        """List athlete activities.

        Parameters
        ----------
        before : int, optional
            Epoch timestamp to use for filtering activities before
        after : int, optional
            Epoch timestamp to use for filtering activities after
        page : int
            Page number (default: 1)
        per_page : int
            Number of items per page (default: 30, max: 200)

        Returns
        -------
        list[ActivitySchema]
            List of activities
        """
        params = {"page": page, "per_page": min(per_page, 200)}
        if before:
            params["before"] = before
        if after:
            params["after"] = after

        data = await self._request("GET", "/athlete/activities", params=params)
        return [ActivitySchema.model_validate(item) for item in data]

    async def get_activity(self, activity_id: int) -> ActivitySchema:
        """Get details of a specific activity.

        Parameters
        ----------
        activity_id : int
            The ID of the activity

        Returns
        -------
        ActivitySchema
            Activity details
        """
        data = await self._request("GET", f"/activities/{activity_id}")
        return ActivitySchema.model_validate(data)

    # =========================================================================
    # Webhook Subscription Endpoints
    # =========================================================================

    async def create_webhook_subscription(
        self,
        client_id: int,
        client_secret: str,
        callback_url: str,
        verify_token: str,
    ) -> WebhookSubscriptionSchema:
        """Create a webhook event subscription.

        Parameters
        ----------
        client_id : int
            Application's client ID
        client_secret : str
            Application's client secret
        callback_url : str
            URL where Strava will send webhook events
        verify_token : str
            Token to verify webhook requests

        Returns
        -------
        WebhookSubscriptionSchema
            Created subscription
        """
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "callback_url": callback_url,
            "verify_token": verify_token,
        }
        data = await self._request("POST", "/push_subscriptions", params=params)
        return WebhookSubscriptionSchema.model_validate(data)

    async def list_webhook_subscriptions(
        self, client_id: int, client_secret: str
    ) -> list[WebhookSubscriptionSchema]:
        """List all webhook subscriptions.

        Parameters
        ----------
        client_id : int
            Application's client ID
        client_secret : str
            Application's client secret

        Returns
        -------
        list[WebhookSubscriptionSchema]
            List of subscriptions
        """
        params = {"client_id": client_id, "client_secret": client_secret}
        data = await self._request("GET", "/push_subscriptions", params=params)
        return [WebhookSubscriptionSchema.model_validate(item) for item in data]

    async def delete_webhook_subscription(
        self, subscription_id: int, client_id: int, client_secret: str
    ) -> None:
        """Delete a webhook subscription.

        Parameters
        ----------
        subscription_id : int
            ID of subscription to delete
        client_id : int
            Application's client ID
        client_secret : str
            Application's client secret
        """
        params = {"client_id": client_id, "client_secret": client_secret}
        await self._request(
            "DELETE", f"/push_subscriptions/{subscription_id}", params=params
        )
