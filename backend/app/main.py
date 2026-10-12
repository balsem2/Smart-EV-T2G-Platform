import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import ping_database
from app.energy_sync import run_energy_sync, sync_status
from app.routers import ai, assistant, auth, catalog, charging_requests, notifications, operator, optimization, payments, profile, reservations, stations, v2g_offers, vehicles


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = asyncio.Event()
    sync_task = None
    if settings.energy_sync_enabled and settings.database_url:
        sync_task = asyncio.create_task(run_energy_sync(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        if sync_task is not None:
            sync_task.cancel()
            await asyncio.gather(sync_task, return_exceptions=True)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the Smart EV Transportation-to-Grid platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://smart-ev.localhost:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assistant.router)
app.include_router(ai.router)
app.include_router(profile.router)
app.include_router(catalog.router)
app.include_router(vehicles.router)
app.include_router(stations.router)
app.include_router(v2g_offers.router)
app.include_router(charging_requests.router)
app.include_router(optimization.router)
app.include_router(payments.router)
app.include_router(reservations.router)
app.include_router(notifications.router)
app.include_router(operator.router)


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Confirm that the API process is running."""
    return {"status": "ok"}


@app.get("/health/db", tags=["System"])
def database_health_check() -> dict[str, str]:
    """Confirm that the API can connect to PostgreSQL."""
    try:
        ping_database()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured or is unavailable.",
        ) from exc

    return {"status": "ok", "database": "connected"}


@app.get("/health/energy-sync", tags=["System"])
def energy_sync_health_check() -> dict[str, str | int | None]:
    """Expose whether the automatic 15-minute source refresh is healthy."""
    return {
        **sync_status,
        "interval_seconds": settings.energy_sync_interval_seconds,
    }
