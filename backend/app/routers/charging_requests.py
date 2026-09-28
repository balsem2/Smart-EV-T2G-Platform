from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser


router = APIRouter(prefix="/charging-requests", tags=["Charging Requests"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _canonical_connector(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _connectors_are_compatible(vehicle_connectors: str | None, station_connector: str | None) -> bool:
    if not vehicle_connectors or not station_connector:
        return True
    station_value = _canonical_connector(station_connector)
    return any(
        _canonical_connector(connector) in station_value
        or station_value in _canonical_connector(connector)
        for connector in vehicle_connectors.split(",")
        if connector.strip()
    )


@router.get("", response_model=list[schemas.ChargingRequestRead])
def get_charging_requests(
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> list[schemas.ChargingRequestRead]:
    return crud.list_charging_requests(database_session, user_id=current_user.id)


@router.post(
    "",
    response_model=schemas.ChargingRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_charging_request(
    request_data: schemas.ChargingRequestCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.ChargingRequestRead:
    vehicle = crud.get_vehicle(database_session, request_data.vehicle_id)
    if vehicle is None or not vehicle.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    if vehicle.user_id != current_user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The vehicle does not belong to this user.",
        )

    station = crud.get_station(database_session, request_data.station_id)
    if station is None or not station.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found.")
    if station.operational_status != "online" or station.available_chargers < 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The selected station currently has no available charger.",
        )
    if not _connectors_are_compatible(vehicle.connector_types, station.charger_type):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"The station connector ({station.charger_type}) is not compatible with "
            f"this vehicle ({vehicle.connector_types}).",
        )

    return crud.create_charging_request(
        database_session,
        request_data,
        current_user.id,
    )
