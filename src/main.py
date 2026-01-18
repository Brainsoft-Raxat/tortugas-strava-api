from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

import src.core.cache  # noqa: F401
import src.core.database  # noqa: F401
import src.core.logging_config  # noqa: F401 - registers logging lifespan
from src.auth.router import router as auth_router
from src.config import get_settings
from src.core.logging_config import configure_logging
from src.core.lifespan import manager
from src.core.middleware import LoggingMiddleware, RequestContextMiddleware
from src.core.request_context import get_request_id
from src.dependencies import get_session
from src.scoring.calculator import get_week_boundaries
from src.scoring.router import public_router as scoring_public_router
from src.scoring.router import router as scoring_router
from src.scoring.service import scoring_service
from src.sync.router import router as sync_router
from src.webhooks.router import router as webhook_router

# Configure logging FIRST (before app creation and settings access)
configure_logging()

settings = get_settings()

# Setup Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files
static_dir = Path(__file__).parent / "static"

app_configs = {
    "title": settings.APP_NAME,
    "version": "1.0.0",
    "lifespan": manager,
}

if settings.ENVIRONMENT not in ("local", "staging"):
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)

# Add middleware (order matters - last added runs first)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestContextMiddleware)  # Must run before logging

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(scoring_public_router)
app.include_router(scoring_router)
app.include_router(sync_router)
app.include_router(webhook_router)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with structured logging.

    Parameters
    ----------
    request : Request
        The HTTP request that caused the exception
    exc : Exception
        The unhandled exception

    Returns
    -------
    JSONResponse
        Error response with request_id for tracking
    """
    request_id = get_request_id()
    logger.error(
        "Unhandled exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


@app.get("/")
async def home(request: Request, db: AsyncSession = Depends(get_session)):
    """Main page showing leaderboard dashboard"""
    date_obj = datetime.now()
    week_start, week_end = get_week_boundaries(date_obj)
    leaderboard = await scoring_service.get_weekly_leaderboard(db, date_obj)

    return templates.TemplateResponse(
        "leaderboard.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "leaderboard": leaderboard,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": (week_end - datetime.resolution).strftime("%Y-%m-%d"),
        },
    )


@app.get("/authorize")
async def authorize_page(request: Request):
    """Authorization page with Strava connect button"""
    return templates.TemplateResponse(
        "landing.html", {"request": request, "app_name": settings.APP_NAME}
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}
