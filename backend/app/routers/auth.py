from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.account_security import consume_account_token, create_account_token, send_account_email
from app.config import settings
from app.database import get_db
from app.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["Authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def token_response(user, verification_token: str | None = None) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_access_token(user.id),
        user=user,
        verification_token=verification_token if settings.app_env == "development" else None,
    )


@router.post(
    "/register",
    response_model=schemas.RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: schemas.UserCreate,
    database_session: DatabaseSession,
) -> schemas.RegistrationResponse:
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
    verification_token = create_account_token(database_session, user, "verify_email", 24 * 60)
    sent = send_account_email(
        user.email,
        "Verify your Smart EV email",
        f"{settings.frontend_url}/?verify_token={verification_token}",
        "Verify email",
    )
    return schemas.RegistrationResponse(
        email=user.email,
        message="Account created. Verify your email before signing in.",
        development_token=(
            verification_token if settings.app_env == "development" and not sent else None
        ),
    )


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
    if not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Verify your email before signing in.",
        )
    return token_response(user)


@router.post("/verify-email", response_model=schemas.AuthActionResponse)
def verify_email(payload: schemas.AccountTokenRequest, database_session: DatabaseSession):
    user = consume_account_token(database_session, payload.token, "verify_email")
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification link is invalid or expired.")
    from datetime import datetime, timezone
    user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    database_session.commit()
    return schemas.AuthActionResponse(message="Email verified successfully.")


@router.post("/resend-verification", response_model=schemas.AuthActionResponse)
def resend_verification(payload: schemas.EmailRequest, database_session: DatabaseSession):
    user = crud.get_user_by_email(database_session, str(payload.email))
    development_token = None
    if user is not None and not user.email_verified:
        token = create_account_token(database_session, user, "verify_email", 24 * 60)
        sent = send_account_email(
            user.email,
            "Verify your Smart EV email",
            f"{settings.frontend_url}/?verify_token={token}",
            "Verify email",
        )
        if settings.app_env == "development" and not sent:
            development_token = token
    return schemas.AuthActionResponse(
        message="If the account needs verification, a new link has been issued.",
        development_token=development_token,
    )


@router.post("/forgot-password", response_model=schemas.AuthActionResponse)
def forgot_password(payload: schemas.EmailRequest, database_session: DatabaseSession):
    user = crud.get_user_by_email(database_session, str(payload.email))
    development_token = None
    if user is not None:
        token = create_account_token(database_session, user, "reset_password", 30)
        sent = send_account_email(
            user.email,
            "Reset your Smart EV password",
            f"{settings.frontend_url}/?reset_token={token}",
            "Reset password",
        )
        if settings.app_env == "development" and not sent:
            development_token = token
    return schemas.AuthActionResponse(
        message="If this email exists, a password reset link has been issued.",
        development_token=development_token,
    )


@router.post("/reset-password", response_model=schemas.AuthActionResponse)
def reset_password(payload: schemas.PasswordResetConfirm, database_session: DatabaseSession):
    user = consume_account_token(database_session, payload.token, "reset_password")
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link is invalid or expired.")
    user.password_hash = hash_password(payload.new_password)
    database_session.commit()
    return schemas.AuthActionResponse(message="Password reset successfully. You can now log in.")
