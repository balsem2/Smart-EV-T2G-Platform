from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import settings
from app.database import get_db


router = APIRouter(prefix="/stations", tags=["Stations"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.StationRead])
def get_stations(database_session: DatabaseSession) -> list[schemas.StationRead]:
    return crud.list_stations(database_session)


@router.post("/{station_id}/status", response_model=schemas.StationRead)
def receive_station_status(
    station_id: int,
    status_data: schemas.StationStatusUpdate,
    database_session: DatabaseSession,
    station_key: Annotated[str | None, Header(alias="X-Station-Key")] = None,
) -> schemas.StationRead:
    """Receive a simulator update today and an OCPP adapter update later."""
    if station_key is None or not compare_digest(station_key, settings.station_api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid station API key.")
    station = crud.get_station(database_session, station_id)
    if station is None or not station.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active station not found.")
    return crud.update_station_status(database_session, station, status_data)
