"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.sql_runner import ensure_database_tables

tags_metadata = [
    {
        "name": "system",
        "description": "Infra endpoints for health checks and diagnostics.",
    },
    {
        "name": "lotto",
        "description": (
            "Operations for retrieving Lotto draw data, synchronizing storage, "
            "and inspecting historical results."
        ),
    },
    {
        "name": "analysis",
        "description": (
            "Statistical summaries derived from locally stored Lotto draw data."
        ),
    },
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Ensure necessary tables exist before serving traffic."""

    ensure_database_tables()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Lotto Insec API",
    description=(
        "Backend API that synchronizes Lotto draw results from DhLottery and "
        "exposes them via REST endpoints for inspection and analysis."
    ),
    version="0.2.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.include_router(api_router)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
