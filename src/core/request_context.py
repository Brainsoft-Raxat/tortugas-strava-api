"""Request context management using contextvars.

This module manages request-scoped context variables, primarily the request_id
which is used to trace all logs and operations related to a single HTTP request.

Context variables are async-safe and automatically propagate through async call chains
without requiring explicit parameter passing.
"""

import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable to store the current request ID
# This automatically propagates through async calls
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context.

    Returns
    -------
    Optional[str]
        The current request ID, or None if not set
    """
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in the current context.

    Parameters
    ----------
    request_id : str
        The request ID to set
    """
    request_id_var.set(request_id)


def generate_request_id() -> str:
    """Generate a new unique request ID.

    Returns
    -------
    str
        A new UUID v4 as a string
    """
    return str(uuid.uuid4())
