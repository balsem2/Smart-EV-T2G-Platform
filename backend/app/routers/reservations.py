from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Reservation


router = APIRouter(prefix="/reservations", tags=["Reservations"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.ReservationRead])
def list_reservations(
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> list[Reservation]:
    return list(database_session.scalars(
        select(Reservation)
        .where(Reservation.user_id == current_user.id)
        .order_by(Reservation.start_time.desc())
    ))


@router.delete("/{reservation_id}", response_model=schemas.ReservationRead)
def cancel_reservation(
    reservation_id: int,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> Reservation:
    reservation = database_session.get(Reservation, reservation_id)
    if reservation is None or reservation.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    if reservation.status != "confirmed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a confirmed reservation can be cancelled.")
    reservation.status = "cancelled"
    crud.create_notification(
        database_session,
        current_user.id,
        "reservation",
        "Reservation cancelled",
        "The charging slot was released. This academic demo does not process card refunds.",
        "reservation",
        reservation.id,
    )
    database_session.commit()
    database_session.refresh(reservation)
    return reservation
