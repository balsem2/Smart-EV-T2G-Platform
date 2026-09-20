from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser


router = APIRouter(prefix="/charging-requests", tags=["Charging Requests"])
DatabaseSession = Annotated[Session, Depends(get_db)]


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
    if vehicle is None:
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

    return crud.create_charging_request(
        database_session,
        request_data,
        current_user.id,
    )
