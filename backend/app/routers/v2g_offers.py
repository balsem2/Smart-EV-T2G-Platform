from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import floor
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import RewardEvent, Station, User, V2GOffer
from app.routers.charging_requests import _connectors_are_compatible


router = APIRouter(prefix="/v2g-offers", tags=["V2G Offers"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _offer_response(offer: V2GOffer) -> schemas.V2GOfferRead:
    return schemas.V2GOfferRead(
        id=offer.id,
        vehicle_id=offer.vehicle_id,
        station_id=offer.station_id,
        current_soc=offer.current_soc,
        minimum_soc=offer.minimum_soc,
        export_energy_kwh=offer.export_energy_kwh,
        reward_eur=offer.reward_eur,
        export_start=offer.export_start.replace(tzinfo=timezone.utc),
        export_end=offer.export_end.replace(tzinfo=timezone.utc),
        delivered_energy_kwh=offer.delivered_energy_kwh,
        credited_reward_eur=offer.credited_reward_eur,
        status=offer.status,
    )


def _round_up_to_quarter(value: datetime) -> datetime:
    rounded = value.replace(second=0, microsecond=0)
    remainder = rounded.minute % 15
    if remainder:
        rounded += timedelta(minutes=15 - remainder)
    return rounded


@router.post("", response_model=schemas.V2GOfferRead, status_code=status.HTTP_201_CREATED)
def create_offer(
    offer_data: schemas.V2GOfferCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.V2GOfferRead:
    vehicle = crud.get_vehicle(database_session, offer_data.vehicle_id)
    if vehicle is None or not vehicle.active or vehicle.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found.")
    if not vehicle.supports_v2g:
        raise HTTPException(status.HTTP_409_CONFLICT, "This vehicle is not configured as V2G compatible.")
    station = database_session.get(Station, offer_data.station_id)
    if station is None or not station.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found.")
    if not station.supports_v2g:
        raise HTTPException(status.HTTP_409_CONFLICT, "This station does not support bidirectional V2G.")
    if station.operational_status != "online" or station.available_chargers < 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "This V2G station is currently unavailable.")
    if not _connectors_are_compatible(vehicle.connector_types, station.charger_type):
        raise HTTPException(status.HTTP_409_CONFLICT, "Vehicle and V2G station connectors are not compatible.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = _round_up_to_quarter(now)
    if offer_data.available_until <= start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Available until must be in the future.")

    surplus = vehicle.battery_capacity * (offer_data.current_soc - offer_data.minimum_soc) / 100
    export_energy = min(surplus, vehicle.battery_capacity * 0.05, 5.0)
    if export_energy < 0.25:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough battery energy above your reserve for a V2G offer.")

    price_profile: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in crud.list_energy_data(database_session):
        if row.timestamp is not None and row.electricity_price is not None:
            price_profile[(row.timestamp.hour, row.timestamp.minute)].append(row.electricity_price)
    candidates = []
    candidate = start
    while candidate + timedelta(minutes=15) <= offer_data.available_until:
        values = price_profile.get((candidate.hour, candidate.minute))
        if values:
            candidates.append((sum(values) / len(values), candidate))
        candidate += timedelta(minutes=15)
    if not candidates:
        raise HTTPException(status.HTTP_409_CONFLICT, "No grid-service period is available before your deadline.")

    price, export_start = max(candidates, key=lambda item: item[0])
    reward = round(max(price, 0) * export_energy / 1000, 2)
    offer = V2GOffer(
        user_id=current_user.id,
        vehicle_id=vehicle.id,
        station_id=station.id,
        current_soc=offer_data.current_soc,
        minimum_soc=offer_data.minimum_soc,
        export_energy_kwh=round(export_energy, 2),
        reward_eur=reward,
        export_start=export_start,
        export_end=export_start + timedelta(minutes=15),
        status="offered",
    )
    database_session.add(offer)
    database_session.commit()
    database_session.refresh(offer)
    return _offer_response(offer)


@router.post("/{offer_id}/accept", response_model=schemas.V2GOfferRead)
def accept_offer(
    offer_id: int,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.V2GOfferRead:
    offer = database_session.get(V2GOffer, offer_id)
    if offer is None or offer.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "V2G offer not found.")
    if offer.status != "offered":
        raise HTTPException(status.HTTP_409_CONFLICT, "This V2G offer has already been answered.")
    offer.status = "accepted"
    crud.create_notification(
        database_session,
        current_user.id,
        "v2g",
        "V2G offer accepted",
        "Your export is scheduled. The reward will be released only after meter confirmation.",
        "v2g_offer",
        offer.id,
    )
    database_session.commit()
    database_session.refresh(offer)
    return _offer_response(offer)


def _confirm_delivery(
    database_session: Session,
    offer: V2GOffer,
    delivered_energy_kwh: float,
) -> schemas.V2GOfferRead:
    if offer.status != "accepted":
        raise HTTPException(status.HTTP_409_CONFLICT, "This offer is not awaiting meter confirmation.")
    delivered = min(delivered_energy_kwh, offer.export_energy_kwh)
    reward = round(offer.reward_eur * delivered / offer.export_energy_kwh, 2)
    points = floor(delivered * 10 + 0.5)
    user = database_session.get(User, offer.user_id)
    offer.status = "completed"
    offer.delivered_energy_kwh = round(delivered, 2)
    offer.credited_reward_eur = reward
    database_session.add(RewardEvent(
        schedule_id=None,
        reward_type="v2g_export",
        energy_returned=round(delivered, 2),
        reward=reward,
        saving_eur=0,
        points=points,
    ))
    user.wallet_balance = round(user.wallet_balance + reward, 2)
    user.reward_points += points
    crud.create_notification(
        database_session,
        user.id,
        "reward",
        "V2G delivery confirmed",
        f"Meter data confirmed {delivered:.2f} kWh. €{reward:.2f} and {points} points were credited.",
        "v2g_offer",
        offer.id,
    )
    database_session.commit()
    database_session.refresh(offer)
    return _offer_response(offer)


@router.post("/{offer_id}/confirm-delivery", response_model=schemas.V2GOfferRead)
def confirm_metered_delivery(
    offer_id: int,
    confirmation: schemas.V2GDeliveryConfirmation,
    database_session: DatabaseSession,
    station_key: Annotated[str | None, Header(alias="X-Station-Key")] = None,
) -> schemas.V2GOfferRead:
    """Production-style callback: only trusted charger/meter telemetry can settle a reward."""
    if station_key is None or not compare_digest(station_key, settings.station_api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid station API key.")
    offer = database_session.get(V2GOffer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "V2G offer not found.")
    return _confirm_delivery(database_session, offer, confirmation.delivered_energy_kwh)


@router.post("/{offer_id}/simulate-delivery", response_model=schemas.V2GOfferRead)
def simulate_metered_delivery(
    offer_id: int,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.V2GOfferRead:
    """Development-only stand-in for a bidirectional charger's meter callback."""
    if settings.app_env != "development":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Meter simulation is disabled.")
    offer = database_session.get(V2GOffer, offer_id)
    if offer is None or offer.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "V2G offer not found.")
    return _confirm_delivery(database_session, offer, offer.export_energy_kwh)


@router.post("/{offer_id}/decline", response_model=schemas.V2GOfferRead)
def decline_offer(
    offer_id: int,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.V2GOfferRead:
    offer = database_session.get(V2GOffer, offer_id)
    if offer is None or offer.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "V2G offer not found.")
    if offer.status != "offered":
        raise HTTPException(status.HTTP_409_CONFLICT, "This V2G offer has already been answered.")
    offer.status = "declined"
    database_session.commit()
    database_session.refresh(offer)
    return _offer_response(offer)
