# Async Strava Client

A lightweight, fully async Strava API client built for the Tortugas club platform.

## Architecture

```
src/strava/
├── __init__.py           # Public exports
├── client.py             # Low-level HTTP client
├── service.py            # High-level service with token management
├── schemas.py            # Pydantic models for API responses
├── exceptions.py         # Custom exceptions
├── rate_limiter.py       # Async rate limiting
└── README.md             # This file
```

## Usage

### Basic Usage (Service Layer)

The service layer automatically handles token refresh and database integration:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.strava.service import strava_service

async def get_athlete_activities(db: AsyncSession, athlete_id: int):
    # Get authenticated client (auto-refreshes token if needed)
    client = await strava_service.get_client_for_athlete(db, athlete_id)

    # Fetch athlete's recent activities
    activities = await client.get_activities(per_page=10)

    for activity in activities:
        print(f"{activity.name}: {activity.distance}m")
```

### Direct Client Usage

For more control, use the client directly:

```python
from src.strava.client import AsyncStravaClient

async def fetch_activity(access_token: str, activity_id: int):
    client = AsyncStravaClient(access_token=access_token)
    activity = await client.get_activity(activity_id)
    return activity
```

### Rate Limiting

Configure rate limiting priority:

```python
# High priority: No throttling (default)
client = await strava_service.get_client_for_athlete(db, athlete_id, priority="high")

# Medium priority: Spread requests over 15-min window
client = await strava_service.get_client_for_athlete(db, athlete_id, priority="medium")

# Low priority: Spread requests over 24-hour window
client = await strava_service.get_client_for_athlete(db, athlete_id, priority="low")
```

## Available Endpoints

### Athlete
- `get_athlete()` - Get authenticated athlete info

### Activities
- `get_activities(before=None, after=None, page=1, per_page=30)` - List activities
- `get_activity(activity_id)` - Get activity details

### Webhooks
- `create_webhook_subscription()` - Create webhook subscription
- `list_webhook_subscriptions()` - List subscriptions
- `delete_webhook_subscription()` - Delete subscription

## Webhooks

Webhook endpoints are defined in `src/webhooks/router.py`:

- `GET /webhooks/strava` - Validation callback (Strava sends this when you create subscription)
- `POST /webhooks/strava` - Event handler (Strava sends activity events here)

### Setting Up Webhooks

1. Make sure your callback URL is publicly accessible
2. Set `STRAVA_VERIFY_TOKEN` in your `.env`
3. Create a subscription:

```python
client = AsyncStravaClient(access_token="...")
subscription = await client.create_webhook_subscription(
    client_id=YOUR_CLIENT_ID,
    client_secret=YOUR_CLIENT_SECRET,
    callback_url="https://yourdomain.com/webhooks/strava",
    verify_token="tortugas"  # Should match STRAVA_VERIFY_TOKEN
)
```

4. Strava will send a GET request to validate
5. Once validated, Strava will POST events when athletes create/update/delete activities

## Error Handling

```python
from src.strava.exceptions import (
    ObjectNotFound,
    AccessUnauthorized,
    RateLimitExceeded,
    StravaException
)

try:
    activity = await client.get_activity(12345)
except ObjectNotFound:
    print("Activity not found")
except AccessUnauthorized:
    print("Token invalid or expired")
except RateLimitExceeded:
    print("Hit rate limit")
except StravaException as e:
    print(f"API error: {e}")
```

## Testing

Test the async client:

```bash
# Start server
just run

# Test fetching activities (in another terminal)
curl http://localhost:8000/test-strava/135390765
```

## Strava Rate Limits

- **Short-term**: 600 requests per 15 minutes
- **Long-term**: 30,000 requests per day

The rate limiter automatically reads these from response headers and throttles accordingly.

## Why Async?

- **Non-blocking**: Other requests can be processed while waiting for Strava API
- **Performance**: Can fetch data for multiple athletes concurrently
- **Scalability**: Better suited for background jobs and webhooks

### Example: Sync All Athletes (Parallel)

```python
import asyncio

async def sync_all_athletes(db: AsyncSession):
    users = await auth_service.list_authorized_users(db)

    # Fetch activities for all athletes in parallel
    tasks = [
        fetch_athlete_activities(db, user.id)
        for user in users
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

With sync code, this would take `num_athletes * avg_request_time`. With async, it takes roughly `avg_request_time` total!
