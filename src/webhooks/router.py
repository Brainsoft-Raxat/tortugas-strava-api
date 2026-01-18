"""Webhook endpoints for receiving Strava events."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.activities.service import activity_service
from src.config import get_settings
from src.core.request_context import get_request_id, set_request_id
from src.strava.schemas import WebhookEventSchema
from src.strava.service import strava_service

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

    # Parse and validate the event
    try:
        event = WebhookEventSchema.model_validate(body)
    except Exception as e:
        logger.error("Invalid webhook event", error=str(e), body=body)
        raise HTTPException(status_code=400, detail="Invalid event format")

    # Log event with structured fields
    logger.info(
        "Webhook event received",
        event_type=event.object_type,
        aspect_type=event.aspect_type,
        object_id=event.object_id,
        owner_id=event.owner_id,
    )

    # Get current request_id for background task context
    request_id = get_request_id()

    # Get session maker from app state for background tasks
    session_maker = request.state.session_maker

    # Queue event processing for background execution
    if event.object_type == "activity":
        logger.debug(
            "Queuing activity event for background processing",
            activity_id=event.object_id,
        )
        background_tasks.add_task(
            handle_activity_event_background, session_maker, event, request_id
        )
    elif event.object_type == "athlete":
        logger.debug(
            "Queuing athlete event for background processing", athlete_id=event.owner_id
        )
        background_tasks.add_task(
            handle_athlete_event_background, session_maker, event, request_id
        )
    else:
        logger.warning("Unknown object type", object_type=event.object_type)

    # Return immediately (Strava requires response within 2 seconds)
    return {"status": "success"}


async def handle_activity_event_background(
    session_maker: async_sessionmaker,
    event: WebhookEventSchema,
    request_id: str,
) -> None:
    """Background task wrapper for activity events.

    Creates its own database session since it runs after the request context.

    Parameters
    ----------
    session_maker : async_sessionmaker
        Database session maker
    event : WebhookEventSchema
        The webhook event to process
    request_id : str
        Request ID from the original HTTP request for tracking
    """
    # Set request_id in background task context
    set_request_id(request_id)

    logger.info(
        "Processing activity event in background",
        request_id=request_id,
        activity_id=event.object_id,
    )

    async with session_maker() as db:
        try:
            await handle_activity_event(db, event)
            logger.info(
                "Activity event processing completed",
                request_id=request_id,
                activity_id=event.object_id,
            )
        except Exception as e:
            logger.error(
                "Activity event processing failed",
                request_id=request_id,
                activity_id=event.object_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            await db.rollback()


async def handle_athlete_event_background(
    session_maker: async_sessionmaker,
    event: WebhookEventSchema,
    request_id: str,
) -> None:
    """Background task wrapper for athlete events.

    Creates its own database session since it runs after the request context.

    Parameters
    ----------
    session_maker : async_sessionmaker
        Database session maker
    event : WebhookEventSchema
        The webhook event to process
    request_id : str
        Request ID from the original HTTP request for tracking
    """
    # Set request_id in background task context
    set_request_id(request_id)

    logger.info(
        "Processing athlete event in background",
        request_id=request_id,
        athlete_id=event.owner_id,
    )

    async with session_maker() as db:
        try:
            await handle_athlete_event(db, event)
            logger.info(
                "Athlete event processing completed",
                request_id=request_id,
                athlete_id=event.owner_id,
            )
        except Exception as e:
            logger.error(
                "Athlete event processing failed",
                request_id=request_id,
                athlete_id=event.owner_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
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

    logger.info(
        "Processing activity event",
        aspect_type=event.aspect_type,
        activity_id=activity_id,
        athlete_id=athlete_id,
    )

    if event.aspect_type == "create":
        # New activity created - fetch and store it
        logger.info(
            "Fetching new activity from Strava",
            activity_id=activity_id,
            athlete_id=athlete_id,
        )

        try:
            # Get client for the athlete
            client = await strava_service.get_client_for_athlete(db, athlete_id)

            # Fetch the activity details
            activity_data = await client.get_activity(activity_id)

            logger.info(
                "Fetched activity from Strava",
                activity_id=activity_id,
                name=activity_data.name,
                distance=activity_data.distance,
                activity_type=activity_data.type,
            )

            # Store activity in database
            activity = await activity_service.create_activity(db, activity_data)
            logger.info("Activity stored in database", activity_id=activity.id)

        except Exception as e:
            logger.error(
                "Error fetching/storing activity",
                activity_id=activity_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    elif event.aspect_type == "update":
        # Activity updated
        logger.info(
            "Activity update event received",
            activity_id=activity_id,
            updates=event.updates,
        )

        try:
            # Fetch updated activity data
            client = await strava_service.get_client_for_athlete(db, athlete_id)
            activity_data = await client.get_activity(activity_id)

            # Update in database
            existing = await activity_service.get_activity(db, activity_id)
            if existing:
                await activity_service.update_activity(db, existing, activity_data)
                logger.info("Activity updated in database", activity_id=activity_id)
            else:
                # Activity not in DB yet, create it
                await activity_service.create_activity(db, activity_data)
                logger.info(
                    "Activity created from update event", activity_id=activity_id
                )

        except Exception as e:
            logger.error(
                "Error updating activity",
                activity_id=activity_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    elif event.aspect_type == "delete":
        # Activity deleted
        logger.info("Activity delete event received", activity_id=activity_id)

        try:
            deleted = await activity_service.delete_activity(db, activity_id)
            if deleted:
                logger.info("Activity deleted from database", activity_id=activity_id)
            else:
                logger.warning(
                    "Activity not found in database for deletion",
                    activity_id=activity_id,
                )
        except Exception as e:
            logger.error(
                "Error deleting activity",
                activity_id=activity_id,
                error=str(e),
                error_type=type(e).__name__,
            )


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

    logger.info(
        "Processing athlete event",
        aspect_type=event.aspect_type,
        athlete_id=athlete_id,
    )

    if event.aspect_type == "update":
        # Athlete profile updated
        logger.info(
            "Athlete update event received",
            athlete_id=athlete_id,
            updates=event.updates,
        )
        # TODO: Update athlete info in database

    # Note: Athletes don't have 'create' or 'delete' events
