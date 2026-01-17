"""Webhook endpoints for receiving Strava events."""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.activities.service import activity_service
from src.config import get_settings
from src.strava.schemas import WebhookEventSchema
from src.strava.service import strava_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/strava")
async def webhook_validation(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    """Handle Strava webhook validation (subscription callback).

    When you create a webhook subscription, Strava will send a GET request
    to this endpoint to validate that you control the callback URL.

    Expected query params from Strava:
    - hub.mode=subscribe
    - hub.challenge=<random_string>
    - hub.verify_token=<your_verify_token>

    You must respond with: {"hub.challenge": "<same_random_string>"}
    """
    logger.info(
        f"Webhook validation request: mode={hub_mode}, token={hub_verify_token}"
    )

    # Validate the verify token matches what you set
    if hub_verify_token != settings.STRAVA_VERIFY_TOKEN:
        logger.error(f"Invalid verify token: {hub_verify_token}")
        raise HTTPException(status_code=403, detail="Invalid verify token")

    # Validate mode
    if hub_mode != "subscribe":
        logger.error(f"Invalid hub mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub mode")

    # Return the challenge to confirm subscription
    logger.info("Webhook validation successful")
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle Strava webhook events.

    Strava sends POST requests here when activities are created/updated/deleted.
    Returns immediately (within 2 seconds as required by Strava) and processes
    events in the background.

    Event format:
    {
        "object_type": "activity",
        "object_id": 12345,
        "aspect_type": "create",
        "owner_id": 67890,
        "subscription_id": 1,
        "event_time": 1234567890
    }
    """
    body = await request.json()
    logger.info(f"Received webhook event: {body}")

    # Parse and validate the event
    try:
        event = WebhookEventSchema.model_validate(body)
    except Exception as e:
        logger.error(f"Invalid webhook event: {e}")
        raise HTTPException(status_code=400, detail="Invalid event format")

    # Get session maker from app state for background tasks
    session_maker = request.state.session_maker

    # Queue event processing for background execution
    if event.object_type == "activity":
        background_tasks.add_task(
            handle_activity_event_background, session_maker, event
        )
    elif event.object_type == "athlete":
        background_tasks.add_task(handle_athlete_event_background, session_maker, event)
    else:
        logger.warning(f"Unknown object type: {event.object_type}")

    # Return immediately (Strava requires response within 2 seconds)
    return {"status": "success"}


async def handle_activity_event_background(
    session_maker: async_sessionmaker,
    event: WebhookEventSchema,
) -> None:
    """Background task wrapper for activity events.

    Creates its own database session since it runs after the request context.
    """
    async with session_maker() as db:
        try:
            await handle_activity_event(db, event)
        except Exception as e:
            logger.error(
                f"Background activity event processing failed: {e}", exc_info=True
            )
            await db.rollback()


async def handle_athlete_event_background(
    session_maker: async_sessionmaker,
    event: WebhookEventSchema,
) -> None:
    """Background task wrapper for athlete events.

    Creates its own database session since it runs after the request context.
    """
    async with session_maker() as db:
        try:
            await handle_athlete_event(db, event)
        except Exception as e:
            logger.error(
                f"Background athlete event processing failed: {e}", exc_info=True
            )
            await db.rollback()


async def handle_activity_event(db: AsyncSession, event: WebhookEventSchema) -> None:
    """Handle activity-related webhook events.

    Parameters
    ----------
    db : AsyncSession
        Database session
    event : WebhookEventSchema
        The webhook event
    """
    athlete_id = event.owner_id
    activity_id = event.object_id

    logger.info(f"Activity {event.aspect_type}: ID={activity_id}, Athlete={athlete_id}")

    if event.aspect_type == "create":
        # New activity created - fetch and store it
        logger.info(f"Fetching new activity {activity_id} for athlete {athlete_id}")

        try:
            # Get client for the athlete
            client = await strava_service.get_client_for_athlete(db, athlete_id)

            # Fetch the activity details
            activity_data = await client.get_activity(activity_id)

            logger.info(
                f"Fetched activity: {activity_data.name} "
                f"({activity_data.distance}m, {activity_data.type})"
            )

            # Store activity in database
            activity = await activity_service.create_activity(db, activity_data)
            logger.info(f"Stored activity {activity.id} in database")

        except Exception as e:
            logger.error(f"Error fetching/storing activity {activity_id}: {e}")

    elif event.aspect_type == "update":
        # Activity updated
        logger.info(f"Activity {activity_id} updated: {event.updates}")

        try:
            # Fetch updated activity data
            client = await strava_service.get_client_for_athlete(db, athlete_id)
            activity_data = await client.get_activity(activity_id)

            # Update in database
            existing = await activity_service.get_activity(db, activity_id)
            if existing:
                await activity_service.update_activity(db, existing, activity_data)
                logger.info(f"Updated activity {activity_id} in database")
            else:
                # Activity not in DB yet, create it
                await activity_service.create_activity(db, activity_data)
                logger.info(f"Created activity {activity_id} from update event")

        except Exception as e:
            logger.error(f"Error updating activity {activity_id}: {e}")

    elif event.aspect_type == "delete":
        # Activity deleted
        logger.info(f"Activity {activity_id} deleted")

        try:
            deleted = await activity_service.delete_activity(db, activity_id)
            if deleted:
                logger.info(f"Deleted activity {activity_id} from database")
            else:
                logger.warning(f"Activity {activity_id} not found in database")
        except Exception as e:
            logger.error(f"Error deleting activity {activity_id}: {e}")


async def handle_athlete_event(db: AsyncSession, event: WebhookEventSchema) -> None:
    """Handle athlete-related webhook events.

    Parameters
    ----------
    db : AsyncSession
        Database session
    event : WebhookEventSchema
        The webhook event
    """
    athlete_id = event.owner_id

    logger.info(f"Athlete {event.aspect_type}: ID={athlete_id}")

    if event.aspect_type == "update":
        # Athlete profile updated
        logger.info(f"Athlete {athlete_id} updated: {event.updates}")
        # TODO: Update athlete info in database

    # Note: Athletes don't have 'create' or 'delete' events
