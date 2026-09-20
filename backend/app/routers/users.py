from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db


router = APIRouter(prefix="/users", tags=["Users"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.UserRead])
def get_users(database_session: DatabaseSession) -> list[schemas.UserRead]:
    """List the users stored in PostgreSQL."""
    return crud.list_users(database_session)


@router.post(
    "",
    response_model=schemas.UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: schemas.UserCreate,
    database_session: DatabaseSession,
) -> schemas.UserRead:
    """Register a user while keeping the password out of the response."""
    if crud.get_user_by_email(database_session, str(user_data.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    return crud.create_user(database_session, user_data)
