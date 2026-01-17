"""FastAPI dependencies for accessing application state."""

from typing import AsyncIterator, cast

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import get_settings
from src.core.cache import FakeRedis

# Define API key header scheme for Swagger UI
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """
    Get database session from application state.

    Usage:
        @app.get("/users")
        async def get_users(session: AsyncSession = Depends(get_session)):
            ...
    """
    session_maker = cast(async_sessionmaker, request.state.session_maker)
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis(request: Request) -> FakeRedis:
    """
    Get Redis client from application state.

    Usage:
        @app.get("/cache/{key}")
        async def get_cache(key: str, redis: FakeRedis = Depends(get_redis)):
            ...
    """
    return cast(FakeRedis, request.state.redis)


async def verify_admin_api_key(api_key: str = Security(api_key_header)) -> None:
    """
    Verify admin API key from X-API-Key header.

    This dependency integrates with Swagger UI's "Authorize" button.
    Users can click Authorize once and the API key will be included
    in all subsequent requests.

    Usage (on individual routes):
        @app.get("/admin/users")
        async def admin_route(_: None = Depends(verify_admin_api_key)):
            ...

    Usage (on entire router):
        router = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin_api_key)])

    Raises
    ------
    HTTPException
        403 if API key is invalid or missing
    """
    settings = get_settings()
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
