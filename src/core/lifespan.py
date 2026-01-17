"""
Lifespan manager for FastAPI
Allows registering multiple lifespan contexts with decorator syntax.
"""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI


class LifespanManager:
    """Manages multiple lifespan contexts for FastAPI applications."""

    def __init__(self):
        self._lifespans: list[Callable] = []

    def add(self, lifespan: Callable) -> Callable:
        """
        Decorator to register a lifespan context.

        Usage:
            @manager.add
            @asynccontextmanager
            async def setup_db():
                # startup
                yield {"db": db_connection}
                # shutdown
        """
        self._lifespans.append(lifespan)
        return lifespan

    @asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncIterator[dict[str, Any]]:
        """
        Execute all registered lifespans and merge their states.
        Called automatically by FastAPI.
        """
        async with AsyncExitStack() as stack:
            combined_state = {}

            for lifespan_func in self._lifespans:
                try:
                    context = lifespan_func(app)
                except TypeError:
                    context = lifespan_func()

                state = await stack.enter_async_context(context)
                if state:
                    combined_state.update(state)

            yield combined_state


manager = LifespanManager()
