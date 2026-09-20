from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["Authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def token_response(user) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_access_token(user.id),
        user=user,
    )


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: schemas.UserCreate,
    database_session: DatabaseSession,
) -> schemas.TokenResponse:
    if crud.get_user_by_email(database_session, str(user_data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered.")
    try:
        user = crud.create_user(database_session, user_data)
    except IntegrityError as error:
        database_session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Email is already registered.",
        ) from error
    return token_response(user)


@router.post("/login", response_model=schemas.TokenResponse)
def login(
    credentials: schemas.LoginRequest,
    database_session: DatabaseSession,
) -> schemas.TokenResponse:
    user = crud.get_user_by_email(database_session, str(credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password.",
        )
    return token_response(user)
