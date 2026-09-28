from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser


router = APIRouter(prefix="/vehicles", tags=["Vehicles"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.VehicleRead])
def get_vehicles(
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> list[schemas.VehicleRead]:
    """List the authenticated user's vehicles."""
    return crud.list_vehicles(database_session, user_id=current_user.id)


@router.post(
    "",
    response_model=schemas.VehicleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle(
    vehicle_data: schemas.VehicleCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.VehicleRead:
    """Register a vehicle for the authenticated user."""
    try:
        return crud.create_vehicle(database_session, vehicle_data, current_user.id)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: int,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    """Remove one owned vehicle without deleting its historical sessions."""
    vehicle = crud.get_vehicle(database_session, vehicle_id)
    if vehicle is None or not vehicle.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    crud.remove_vehicle(database_session, vehicle)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
