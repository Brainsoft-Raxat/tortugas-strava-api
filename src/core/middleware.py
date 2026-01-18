"""FastAPI middleware for request context and logging.

This module provides two middleware components:
1. RequestContextMiddleware: Generates and injects request_id into context
2. LoggingMiddleware: Logs HTTP requests and responses with timing information

Middleware should be added to the FastAPI app in this order:
    app.add_middleware(RequestContextMiddleware)  # Must be first
    app.add_middleware(LoggingMiddleware)
"""

import json
import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.request_context import generate_request_id, get_request_id, set_request_id

# Max body size to log (in bytes) - avoid logging huge payloads
MAX_BODY_LOG_SIZE = 10000  # 10KB


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and inject request_id into context.

    For each incoming request:
    1. Generates a unique UUID request_id
    2. Injects it into the contextvars context
    3. Adds X-Request-ID header to the response

    The request_id automatically propagates through all async calls
    and can be accessed via get_request_id() anywhere in the request lifecycle.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and inject request_id.

        Parameters
        ----------
        request : Request
            The incoming HTTP request
        call_next : callable
            The next middleware or route handler

        Returns
        -------
        Response
            The HTTP response with X-Request-ID header added
        """
        # Generate and set request ID in context
        request_id = generate_request_id()
        set_request_id(request_id)

        # Process request
        response = await call_next(request)

        # Add request ID to response headers for client tracing
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses.

    Logs:
    - Request started: method, path, query params, client IP
    - Request completed: status code, duration in milliseconds

    All logs include the request_id from context for tracing.
    Skips logging for /health endpoint to reduce noise.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with logging.

        Parameters
        ----------
        request : Request
            The incoming HTTP request
        call_next : callable
            The next middleware or route handler

        Returns
        -------
        Response
            The HTTP response
        """
        # Skip logging for health checks to reduce noise
        if request.url.path == "/health":
            return await call_next(request)

        request_id = get_request_id()
        start_time = time.time()

        # Read request body if present (for POST/PUT/PATCH requests)
        body_data = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                # Read body (this consumes the stream)
                body_bytes = await request.body()

                # Only log if not too large
                if len(body_bytes) <= MAX_BODY_LOG_SIZE:
                    # Try to parse as JSON
                    try:
                        body_data = json.loads(body_bytes)
                    except json.JSONDecodeError:
                        # If not JSON, log as string (truncated if needed)
                        body_data = body_bytes.decode("utf-8", errors="replace")[:500]
                else:
                    body_data = f"<body too large: {len(body_bytes)} bytes>"

            except Exception as e:
                body_data = f"<error reading body: {str(e)}>"

        # Log incoming request
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
        }
        if body_data is not None:
            log_data["body"] = body_data

        logger.info("Request started", **log_data)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        return response
