from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser


router = APIRouter(prefix="/payments", tags=["Payments"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/checkout",
    response_model=schemas.PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def checkout(
    payment_data: schemas.PaymentCheckout,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.PaymentRead:
    """Confirm an advance demo payment without storing sensitive card data."""
    try:
        return crud.create_payment(database_session, current_user.id, payment_data)
    except ValueError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except PermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
