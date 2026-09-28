from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Reservation, Station, V2GOffer
from app.routers.v2g_offers import _confirm_delivery, _offer_response


router = APIRouter(prefix="/operator", tags=["Operator"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _managed_station(current_user: CurrentUser, database_session: Session) -> Station:
    if current_user.role not in {"operator", "admin"} or current_user.managed_station_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator access required.")
    station = database_session.get(Station, current_user.managed_station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Managed station not found.")
    return station


@router.get("/dashboard", response_model=schemas.OperatorDashboardRead)
def dashboard(database_session: DatabaseSession, current_user: CurrentUser):
    station = _managed_station(current_user, database_session)
    reservations = list(database_session.scalars(
        select(Reservation).where(Reservation.station_id == station.id).order_by(Reservation.start_time)
    ))
    offers = list(database_session.scalars(
        select(V2GOffer).where(V2GOffer.station_id == station.id).order_by(V2GOffer.export_start.desc())
    ))
    return schemas.OperatorDashboardRead(
        station=station,
        reservations=reservations,
        v2g_offers=[_offer_response(offer) for offer in offers],
        confirmed_reservations=sum(item.status == "confirmed" for item in reservations),
        pending_v2g_deliveries=sum(item.status == "accepted" for item in offers),
    )


@router.patch("/reservations/{reservation_id}", response_model=schemas.ReservationRead)
def update_reservation(
    reservation_id: int,
    payload: schemas.ReservationStatusUpdate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
):
    station = _managed_station(current_user, database_session)
    reservation = database_session.get(Reservation, reservation_id)
    if reservation is None or reservation.station_id != station.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found for this station.")
    reservation.status = payload.status
    crud.create_notification(
        database_session,
        reservation.user_id,
        "reservation",
        f"Reservation {payload.status}",
        f"The operator marked your reservation at {station.station_name} as {payload.status}.",
        "reservation",
        reservation.id,
    )
    database_session.commit()
    database_session.refresh(reservation)
    return reservation


@router.post("/v2g-offers/{offer_id}/confirm-delivery", response_model=schemas.V2GOfferRead)
def confirm_v2g_delivery(
    offer_id: int,
    payload: schemas.V2GDeliveryConfirmation,
    database_session: DatabaseSession,
    current_user: CurrentUser,
):
    station = _managed_station(current_user, database_session)
    offer = database_session.get(V2GOffer, offer_id)
    if offer is None or offer.station_id != station.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "V2G offer not found for this station.")
    return _confirm_delivery(database_session, offer, payload.delivered_energy_kwh)
