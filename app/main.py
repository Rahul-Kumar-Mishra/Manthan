from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health/live",
    }


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}
