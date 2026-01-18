from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings
from src.core.lifespan import manager


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""

    pass


settings = get_settings()


@manager.add
@asynccontextmanager
async def database_lifespan() -> AsyncIterator[dict]:
    """
    Manage database connection lifecycle.
    Creates connection pool on startup, disposes on shutdown.
    """
    logger.info("Initializing database connection pool")

    # Startup - create engine and session maker
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        # echo=settings.ENVIRONMENT == "local",
    )

    session_maker = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    logger.info("Database connection pool ready")

    # Yield state to be available in request.state
    yield {"session_maker": session_maker}

    # Shutdown - cleanup
    logger.info("Shutting down database connection pool")
    await engine.dispose()
    logger.info("Database disconnected")
