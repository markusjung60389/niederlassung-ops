import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal, current_revision, init_db
from .routers import ALL_ROUTERS
from .seed import seed_base_data

logger = logging.getLogger(__name__)

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_base_data(db)
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)

    logger.info(
        "Remscheid Ops API %s started (env=%s, auth_mode=%s, schema=%s, cors=%s)",
        VERSION,
        settings.app_env,
        settings.auth_mode,
        current_revision(),
        settings.cors_origins,
    )
    if settings.auth_mode == "dev":
        logger.warning(
            "AUTH_MODE=dev: callers authenticate with the X-User-Id header. "
            "Do not expose this deployment outside a trusted network."
        )
    yield


app = FastAPI(
    title="Remscheid Ops Platform API",
    version=VERSION,
    lifespan=lifespan,
    description=(
        "Ops, compliance and branch assessment API. Every /api endpoint requires an "
        "authenticated principal; see docs/azure-ad-setup.md for the identity providers."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Unauthenticated on purpose: used by the container healthcheck."""
    return {"status": "ok", "version": VERSION}


@app.get("/api/meta", tags=["meta"])
def meta() -> dict:
    return {
        "version": VERSION,
        "app_env": settings.app_env,
        "auth_mode": settings.auth_mode,
        "schema_revision": current_revision(),
        "timezone": settings.app_timezone,
    }
