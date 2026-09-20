from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
