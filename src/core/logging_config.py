"""Logging configuration using loguru.

This module configures structured logging with environment-specific formatters:
- Local: Colorized console output with source file:line numbers
- Production: JSON structured logs for parsing by log aggregation tools

Also intercepts standard library logging from third-party libraries.
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from loguru import logger

from src.config import get_settings
from src.core.lifespan import manager


def sink_serializer(message):
    """Custom sink that serializes records to clean JSON."""
    record = message.record
    # Build minimal log record with only essential fields
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
    }

    # Add all extra fields (this is where our custom fields go)
    if record["extra"]:
        # Filter out internal loguru fields
        for key, value in record["extra"].items():
            if not key.startswith("_"):
                subset[key] = value

    # Add exception info if present
    if record["exception"]:
        exc_type, exc_value, exc_tb = record["exception"]
        subset["exception"] = {
            "type": exc_type.__name__ if exc_type else None,
            "value": str(exc_value),
        }

    print(json.dumps(subset), file=sys.stderr)


def configure_logging() -> None:
    """Configure loguru logger based on environment settings.

    Removes default handler and configures:
    - Local: Colorized console with readable format
    - Production: JSON serialization for log aggregators

    Also intercepts standard logging from third-party libraries
    (SQLAlchemy, httpx, uvicorn, etc.) and routes to loguru.
    """
    settings = get_settings()

    # Remove default handler
    logger.remove()

    if settings.ENVIRONMENT == "local":
        # Colorized console output with source information
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=settings.LOG_LEVEL,
            colorize=True,
        )
    else:
        # JSON format for production (parse with jq, CloudWatch, Datadog, etc.)
        # Uses custom sink to serialize only essential fields
        logger.add(
            sink_serializer,
            level=settings.LOG_LEVEL,
        )

    # Intercept standard library logging from third-party libraries
    class InterceptHandler(logging.Handler):
        """Handler that intercepts standard logging and routes to loguru."""

        def emit(self, record: logging.LogRecord) -> None:
            """Emit a log record by routing to loguru.

            Parameters
            ----------
            record : logging.LogRecord
                The log record to emit
            """
            # Get corresponding loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger_opt = logger.opt(depth=depth, exception=record.exc_info)
            logger_opt.log(level, record.getMessage())

    # Replace standard logging handlers with our interceptor
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Set levels for noisy third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING
    )  # Reduce access log noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@manager.add
@asynccontextmanager
async def logging_lifespan() -> AsyncIterator[dict]:
    """Log application startup and shutdown events.

    This lifespan context logs when the application starts and stops,
    providing visibility into the application lifecycle.
    """
    settings = get_settings()

    # Startup
    logger.info(
        "Application starting",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        log_level=settings.LOG_LEVEL,
    )

    yield {}

    # Shutdown
    logger.info("Application shutting down")
