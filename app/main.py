"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(
    title="Lotto Insec API",
    description=(
        "Backend API that synchronizes Lotto draw results from DhLottery and "
        "exposes them via REST endpoints for inspection and analysis."
    ),
    version="0.2.0",
)

app.include_router(api_router)
