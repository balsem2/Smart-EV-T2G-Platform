from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.models import User
from app.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


def get_current_user(
    database_session: DatabaseSession,
    credentials: BearerCredentials,
) -> User:
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise authentication_error

    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise authentication_error from error

    user = crud.get_user(database_session, user_id)
    if user is None:
        raise authentication_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
