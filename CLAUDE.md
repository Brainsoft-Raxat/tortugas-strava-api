# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Strava Platform (Tortugas) is a FastAPI-based application that integrates with the Strava API to track cycling activities for a club. It uses OAuth for authentication, webhooks to receive activity events, and stores data asynchronously with SQLAlchemy.

## Common Commands

```bash
# Development server
just run                    # Start FastAPI with auto-reload
just run --port 8080        # Run on custom port

# Database migrations
just mm "description"       # Create new migration (autogenerate)
just migrate                # Apply pending migrations
just downgrade -1           # Rollback one migration

# Linting
just lint                   # Format with ruff + fix issues
just ruff                   # Check only (no fixes)
just ruff --fix             # Fix issues without formatting

# Docker (if configured)
just up                     # Start containers
just build                  # Build containers
just ps                     # Show running containers
just kill                   # Stop all containers
```

## Architecture

### Application Structure

The application uses a layered service architecture:

- **Routers** (`src/*/router.py`) - FastAPI endpoints, request/response handling
- **Services** (`src/*/service.py`) - Business logic, orchestration between layers
- **Models** (`src/*/models.py`) - SQLAlchemy ORM models
- **Schemas** (`src/*/schemas.py`) - Pydantic models for validation/serialization

### Core Modules

**`src/core/lifespan.py`** - Custom lifespan manager that allows multiple lifespan contexts to be registered via decorator (`@manager.add`). Database and cache connections are initialized here.

**`src/core/database.py`** - SQLAlchemy async engine setup. Uses lifespan pattern to manage connection pool. All models inherit from `Base` (DeclarativeBase).

**`src/config.py`** - Settings loaded from `.env` via Pydantic. Cached via `@lru_cache()`. Accessed via `get_settings()`.

**`src/dependencies.py`** - FastAPI dependency injection providers (database sessions, cache connections).

### Domain Modules

**`src/auth/`** - OAuth flow with Strava
- `router.py`: `/auth/authorize` (redirect to Strava), `/auth/callback` (handle OAuth response)
- `service.py`: Token management, user CRUD, automatic token refresh via `refresh_token_if_needed()`
- `models.py`: User model with `is_token_expired()` helper

**`src/strava/`** - Async Strava API client
- `client.py`: Low-level HTTP client using httpx (`AsyncStravaClient`)
- `service.py`: High-level service with token management (`strava_service.get_client_for_athlete()`)
- `rate_limiter.py`: Async rate limiting with 3 priority levels (high/medium/low) to respect Strava's 600/15min and 30k/day limits
- `schemas.py`: Pydantic models for Strava API responses
- `exceptions.py`: Custom exceptions (ObjectNotFound, AccessUnauthorized, RateLimitExceeded)

**`src/activities/`** - Activity data management
- `service.py`: CRUD operations for activities (`create_activity()`, `update_activity()`, `delete_activity()`)
- `models.py`: Activity model with JSON `raw_data` field to store full Strava response

**`src/webhooks/`** - Strava webhook handlers
- `router.py`:
  - `GET /webhooks/strava` - Webhook validation (returns challenge token)
  - `POST /webhooks/strava` - Event handler (create/update/delete activities)
- Automatically fetches and stores activities when webhook events are received

### Key Patterns

1. **Async Everything**: All I/O is async (database, HTTP, etc.). Use `AsyncSession` for DB, `httpx.AsyncClient` for HTTP.

2. **Service Layer Pattern**: Always use services for business logic, never put it in routers. Example:
   ```python
   # Good
   client = await strava_service.get_client_for_athlete(db, athlete_id)

   # Bad - don't instantiate clients directly in routes
   client = AsyncStravaClient(access_token=user.access_token)
   ```

3. **Token Management**: The `strava_service.get_client_for_athlete()` automatically checks token expiration and refreshes if needed. Always use this instead of creating clients manually.

4. **Rate Limiting**: Use priority levels when creating Strava clients:
   - `high` (default): No throttling, for user-facing requests
   - `medium`: Spread over 15-min window, for background jobs
   - `low`: Spread over 24-hour window, for bulk syncs

5. **Lifespan Management**: To add new startup/shutdown logic, use the decorator pattern:
   ```python
   from src.core.lifespan import manager

   @manager.add
   @asynccontextmanager
   async def my_resource():
       # startup
       resource = await setup_resource()
       yield {"my_resource": resource}
       # shutdown
       await resource.cleanup()
   ```

## Database

- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic with autogenerate
- **Connection**: Managed via lifespan context in `src/core/database.py`
- **Session**: Injected via `Depends(get_session)`

Migration workflow:
1. Modify models in `src/*/models.py`
2. Run `just mm "description"` to autogenerate migration
3. Review generated file in `alembic/versions/`
4. Run `just migrate` to apply

## Environment Variables

Required in `.env`:
- `DATABASE_URL` - Async SQLAlchemy URL (e.g., `sqlite+aiosqlite:///data/strava.db`)
- `STRAVA_CLIENT_ID` - From Strava API settings
- `STRAVA_CLIENT_SECRET` - From Strava API settings
- `STRAVA_REDIRECT_URI` - OAuth callback URL (e.g., `http://localhost:8000/auth/callback`)
- `STRAVA_VERIFY_TOKEN` - Token for webhook validation

Optional:
- `WEBHOOK_BASE_URL` - Public URL for webhooks (required for webhook functionality)
- `ENVIRONMENT` - `local` (default), `staging`, or `production`
- `CORS_ORIGINS` - List of allowed origins (default: `["*"]`)

## Testing Endpoints

- `GET /health` - Health check
- `GET /test-db` - Verify database connection
- `GET /test-cache/{key}` - Test cache read
- `POST /test-cache/{key}` - Test cache write
- `GET /test-strava/{athlete_id}` - Fetch athlete's recent activities

## Strava Webhook Setup

1. Set `WEBHOOK_BASE_URL` in `.env` to your public URL
2. Create subscription via Strava API or using the async client:
   ```python
   client = AsyncStravaClient(access_token="...")
   await client.create_webhook_subscription(
       client_id=settings.STRAVA_CLIENT_ID,
       client_secret=settings.STRAVA_CLIENT_SECRET,
       callback_url=settings.webhook_callback_url,
       verify_token=settings.STRAVA_VERIFY_TOKEN
   )
   ```
3. Strava validates via GET request to `/webhooks/strava`
4. Events are received via POST to `/webhooks/strava`

## Code Style

- Formatting: Ruff (replaces Black)
- Type hints: Use for all function signatures
- Imports: Absolute imports from `src/` (not relative)
- Docstrings: NumPy style with Parameters/Returns/Raises sections
