from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import src.core.cache  # noqa: F401
import src.core.database  # noqa: F401
from src.auth.router import router as auth_router
from src.config import get_settings
from src.core.lifespan import manager
from src.scoring.router import router as scoring_router
from src.sync.router import router as sync_router
from src.webhooks.router import router as webhook_router

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

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(scoring_router)
app.include_router(sync_router)
app.include_router(webhook_router)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def landing_page(request: Request):
    """Landing page with Strava authorization button"""
    return templates.TemplateResponse(
        "landing.html", {"request": request, "app_name": settings.APP_NAME}
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}
