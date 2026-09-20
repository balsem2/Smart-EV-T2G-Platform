from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser


router = APIRouter(prefix="/me", tags=["Account"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=schemas.UserRead)
def get_profile(current_user: CurrentUser) -> schemas.UserRead:
    return current_user


@router.patch("", response_model=schemas.UserRead)
def update_profile(
    user_data: schemas.UserUpdate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.UserRead:
    if user_data.email is not None:
        existing = crud.get_user_by_email(database_session, str(user_data.email))
        if existing is not None and existing.id != current_user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered.")
    return crud.update_user(database_session, current_user, user_data)


@router.get("/rewards", response_model=list[schemas.RewardRead])
def get_rewards(
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> list[schemas.RewardRead]:
    return crud.list_user_rewards(database_session, current_user.id)


@router.post("/change-password", response_model=schemas.UserRead)
def change_password(
    password_data: schemas.PasswordChange,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.UserRead:
    try:
        return crud.change_user_password(database_session, current_user, password_data)
    except PermissionError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


@router.get(
    "/payment-method",
    response_model=schemas.PaymentMethodRead | None,
)
def get_payment_method(
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.PaymentMethodRead | None:
    return crud.get_default_payment_method(database_session, current_user.id)


@router.post(
    "/payment-method",
    response_model=schemas.PaymentMethodRead,
    status_code=status.HTTP_201_CREATED,
)
def save_payment_method(
    method_data: schemas.PaymentMethodCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.PaymentMethodRead:
    return crud.save_default_payment_method(
        database_session,
        current_user.id,
        method_data,
    )
