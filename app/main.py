"""Application entry point."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    redirect_slashes=False,
)

app.include_router(router)
