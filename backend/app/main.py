from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import ping_database
from app.routers import ai, auth, catalog, charging_requests, optimization, payments, profile, stations, vehicles


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the Smart EV Transportation-to-Grid platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(profile.router)
app.include_router(catalog.router)
app.include_router(vehicles.router)
app.include_router(stations.router)
app.include_router(charging_requests.router)
app.include_router(optimization.router)
app.include_router(payments.router)


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
