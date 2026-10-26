from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.audit import router as audit_router
from backend.api.healthz import router as healthz_router
from backend.api.internal import router as internal_router
from backend.api.slack import router as slack_router
from backend.api.v1.incidents import router as incidents_router
from backend.api.v1.overview import router as overview_router
from backend.core.config import get_settings
from backend.core.limiter import limiter
from backend.core.logging import configure_logging, logger

settings = get_settings()
configure_logging(settings.environment)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("app_startup", environment=settings.environment)
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(healthz_router)
app.include_router(internal_router)
app.include_router(overview_router, prefix=settings.api_v1_prefix)
app.include_router(incidents_router, prefix=settings.api_v1_prefix)
app.include_router(slack_router, prefix=settings.api_v1_prefix)
app.include_router(audit_router, prefix=settings.api_v1_prefix)

@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "Warden backend is running"}
