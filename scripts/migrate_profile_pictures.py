#!/usr/bin/env python3
"""
Migrate profile pictures for all authorized users.

This script fetches profile pictures from Strava for all authorized users
who don't currently have profile pictures in the database.

Usage:
    poetry run python scripts/migrate_profile_pictures.py

Features:
- Batch processing with progress tracking
- Skip users who already have pictures
- Comprehensive error handling
- Resume capability (can be interrupted and restarted)
- Uses MEDIUM priority rate limiting (spreads over 15min window)
"""
import asyncio
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.models import User
from src.config import get_settings
from src.strava.service import strava_service

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
)

# Create database engine and session maker
settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def migrate_profile_pictures():
    """Migrate profile pictures for all authorized users."""
    async with async_session_maker() as db:
        # Get all authorized users without profile pictures
        query = select(User).filter(User.authorized, User.profile.is_(None))
        result = await db.execute(query)
        users = result.scalars().all()

        total = len(users)
        if total == 0:
            logger.info("No users need profile picture migration")
            return 0, []

        logger.info(f"Migrating profile pictures for {total} users")

        success = 0
        errors = []

        for i, user in enumerate(users, 1):
            logger.info(
                f"[{i}/{total}] Processing user {user.id} ({user.firstname} {user.lastname})"
            )

            try:
                # Use MEDIUM priority (spreads over 15min, balances speed vs rate limits)
                client = await strava_service.get_client_for_athlete(
                    db, user.id, priority="medium"
                )

                # Fetch athlete data
                athlete = await client.get_athlete()

                # Update user
                user.profile = athlete.profile
                user.profile_medium = athlete.profile_medium
                await db.commit()

                logger.success(f"✓ Updated user {user.id}")
                success += 1

            except Exception as e:
                logger.error(f"✗ Failed to update user {user.id}: {e}")
                errors.append({"user_id": user.id, "error": str(e)})
                await db.rollback()
                continue

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Migration complete:")
        logger.info(f"  Success: {success}/{total}")
        logger.info(f"  Errors: {len(errors)}/{total}")

        if errors:
            logger.warning("\nFailed users (can retry manually):")
            for err in errors:
                logger.warning(f"  User {err['user_id']}: {err['error']}")

        return success, errors


async def show_migration_stats():
    """Show statistics about profile picture coverage."""
    async with async_session_maker() as db:
        # Total authorized users
        total_result = await db.execute(
            select(User).filter(User.authorized)
        )
        total = len(total_result.scalars().all())

        # Users with profile pictures
        with_profile_result = await db.execute(
            select(User).filter(User.authorized, User.profile.is_not(None))
        )
        with_profile = len(with_profile_result.scalars().all())

        # Calculate percentage
        percent = (with_profile / total * 100) if total > 0 else 0

        logger.info("\nProfile Picture Coverage:")
        logger.info(f"  Total authorized users: {total}")
        logger.info(f"  Users with pictures: {with_profile}")
        logger.info(f"  Coverage: {percent:.1f}%")


async def main():
    """Main entry point for the migration script."""
    try:
        logger.info("Profile Picture Migration Script")
        logger.info("=" * 60)

        # Show pre-migration stats
        await show_migration_stats()

        # Run migration
        logger.info("\nStarting migration...")
        success, errors = await migrate_profile_pictures()

        # Show post-migration stats
        await show_migration_stats()

        return 0 if len(errors) == 0 else 1
    finally:
        # Clean up database connection
        await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
