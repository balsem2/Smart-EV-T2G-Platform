from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db


router = APIRouter(prefix="/catalog", tags=["Catalogue"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/vehicles", response_model=list[schemas.VehicleCatalogRead])
def get_vehicle_catalog(
    database_session: DatabaseSession,
) -> list[schemas.VehicleCatalogRead]:
    """Return the only EV models accepted when a vehicle is registered."""
    return crud.list_vehicle_catalog(database_session)
