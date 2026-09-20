from secrets import token_hex

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AIPrediction,
    ChargingRequest,
    ChargingSchedule,
    EnergyData,
    Payment,
    PaymentMethod,
    Station,
    User,
    V2GTransaction,
    Vehicle,
    VehicleCatalog,
)
from app.schemas import (
    ChargingRequestCreate,
    StationCreate,
    UserCreate,
    VehicleCreate,
)
from app.security import hash_password, verify_password


def list_users(database_session: Session) -> list[User]:
    """Return all users in a stable order."""
    statement = select(User).order_by(User.id)
    return list(database_session.scalars(statement))


def get_user_by_email(database_session: Session, email: str) -> User | None:
    """Find a user by email without case sensitivity."""
    statement = select(User).where(func.lower(User.email) == email.lower())
    return database_session.scalar(statement)


def create_user(database_session: Session, user_data: UserCreate) -> User:
    """Hash the password, persist the user, and return the saved record."""
    user = User(
        name=user_data.name,
        email=str(user_data.email).lower(),
        password_hash=hash_password(user_data.password),
    )
    database_session.add(user)
    database_session.commit()
    database_session.refresh(user)
    return user


def get_user(database_session: Session, user_id: int) -> User | None:
    """Return one user by primary key."""
    return database_session.get(User, user_id)


def list_vehicles(
    database_session: Session,
    user_id: int | None = None,
) -> list[Vehicle]:
    """Return all vehicles, optionally filtered by owner."""
    statement = select(Vehicle).order_by(Vehicle.id)
    if user_id is not None:
        statement = statement.where(Vehicle.user_id == user_id)
    return list(database_session.scalars(statement))


def create_vehicle(
    database_session: Session,
    vehicle_data: VehicleCreate,
    user_id: int,
) -> Vehicle:
    """Persist a vehicle selected from the controlled catalogue."""
    catalog_vehicle = database_session.get(VehicleCatalog, vehicle_data.catalog_id)
    if catalog_vehicle is None or not catalog_vehicle.active:
        raise ValueError("The selected vehicle is not available in the catalogue.")
    vehicle = Vehicle(
        user_id=user_id,
        catalog_id=catalog_vehicle.id,
        model=catalog_vehicle.model,
        battery_capacity=catalog_vehicle.battery_capacity,
        vehicle_age=vehicle_data.vehicle_age,
    )
    database_session.add(vehicle)
    user = database_session.get(User, user_id)
    if user is not None:
        user.onboarding_completed = True
    database_session.commit()
    database_session.refresh(vehicle)
    return vehicle


def get_vehicle(database_session: Session, vehicle_id: int) -> Vehicle | None:
    return database_session.get(Vehicle, vehicle_id)


def list_vehicle_catalog(database_session: Session) -> list[VehicleCatalog]:
    statement = (
        select(VehicleCatalog)
        .where(VehicleCatalog.active.is_(True))
        .order_by(VehicleCatalog.model)
    )
    return list(database_session.scalars(statement))


def list_stations(database_session: Session) -> list[Station]:
    statement = (
        select(Station)
        .where(Station.active.is_(True))
        .order_by(Station.city, Station.station_name)
    )
    return list(database_session.scalars(statement))


def get_station(database_session: Session, station_id: int) -> Station | None:
    return database_session.get(Station, station_id)


def update_station_status(
    database_session: Session,
    station: Station,
    status_data,
) -> Station:
    for field, value in status_data.model_dump().items():
        setattr(station, field, value)
    station.last_status_at = func.now()
    database_session.commit()
    database_session.refresh(station)
    return station


def create_station(
    database_session: Session,
    station_data: StationCreate,
) -> Station:
    station = Station(**station_data.model_dump())
    database_session.add(station)
    database_session.commit()
    database_session.refresh(station)
    return station


def list_charging_requests(
    database_session: Session,
    user_id: int | None = None,
) -> list[ChargingRequest]:
    statement = select(ChargingRequest).order_by(ChargingRequest.id)
    if user_id is not None:
        statement = statement.where(ChargingRequest.user_id == user_id)
    return list(database_session.scalars(statement))


def create_charging_request(
    database_session: Session,
    request_data: ChargingRequestCreate,
    user_id: int,
) -> ChargingRequest:
    charging_request = ChargingRequest(user_id=user_id, **request_data.model_dump())
    database_session.add(charging_request)
    database_session.commit()
    database_session.refresh(charging_request)
    return charging_request


def get_charging_request(
    database_session: Session,
    request_id: int,
) -> ChargingRequest | None:
    return database_session.get(ChargingRequest, request_id)


def list_energy_data(database_session: Session) -> list[EnergyData]:
    statement = select(EnergyData).order_by(EnergyData.timestamp)
    return list(database_session.scalars(statement))


def list_recent_energy_data(
    database_session: Session,
    limit: int = 3_000,
) -> list[EnergyData]:
    statement = select(EnergyData).order_by(EnergyData.timestamp.desc()).limit(limit)
    return list(reversed(list(database_session.scalars(statement))))


def save_optimization(
    database_session: Session,
    request_id: int,
    result: dict,
) -> ChargingSchedule:
    charging_request = database_session.get(ChargingRequest, request_id)
    if charging_request is None:
        raise ValueError("Charging request not found.")

    prediction = AIPrediction(
        request_id=request_id,
        predicted_energy=result["energy_needed"],
        predicted_duration=result["predicted_duration"],
        confidence=None,
        model_name=result.get("model_name", "daily-profile-baseline-v1"),
    )
    schedule = ChargingSchedule(
        request_id=request_id,
        mode=result["mode"],
        start_time=result["start_time"],
        end_time=result["end_time"],
        energy=result["energy_needed"],
        cost=result["cost"],
        saving=result["saving"],
    )
    database_session.add_all([prediction, schedule])
    database_session.flush()

    database_session.commit()
    database_session.refresh(schedule)
    return schedule


def create_payment(
    database_session: Session,
    user_id: int,
    payment_data,
) -> Payment:
    schedule = database_session.get(ChargingSchedule, payment_data.schedule_id)
    if schedule is None:
        raise ValueError("Charging plan not found.")
    charging_request = database_session.get(ChargingRequest, schedule.request_id)
    if charging_request is None or charging_request.user_id != user_id:
        raise PermissionError("This charging plan does not belong to the user.")
    existing = database_session.scalar(
        select(Payment).where(Payment.schedule_id == schedule.id)
    )
    if existing is not None:
        raise RuntimeError("This charging plan has already been paid.")

    card_last4 = payment_data.card_last4
    if payment_data.payment_method == "saved_card":
        saved_method = database_session.get(PaymentMethod, payment_data.payment_method_id)
        if saved_method is None or saved_method.user_id != user_id:
            raise PermissionError("Saved payment method not found for this user.")
        card_last4 = saved_method.last4

    payment = Payment(
        schedule_id=schedule.id,
        user_id=user_id,
        amount=round(schedule.cost or 0, 2),
        currency="EUR",
        payment_method=payment_data.payment_method,
        card_last4=card_last4,
        status="paid",
        reference=f"SEV-{token_hex(6).upper()}",
    )
    schedule.status = "confirmed"
    database_session.add(payment)
    database_session.commit()
    database_session.refresh(payment)
    return payment


def update_user(
    database_session: Session,
    user: User,
    user_data,
) -> User:
    changes = user_data.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
    for field, value in changes.items():
        setattr(user, field, value)
    database_session.commit()
    database_session.refresh(user)
    return user


def change_user_password(
    database_session: Session,
    user: User,
    password_data,
) -> User:
    if not verify_password(password_data.current_password, user.password_hash):
        raise PermissionError("Current password is incorrect.")
    user.password_hash = hash_password(password_data.new_password)
    database_session.commit()
    database_session.refresh(user)
    return user


def get_default_payment_method(
    database_session: Session,
    user_id: int,
) -> PaymentMethod | None:
    return database_session.scalar(
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user_id, PaymentMethod.is_default.is_(True))
        .order_by(PaymentMethod.id.desc())
    )


def save_default_payment_method(
    database_session: Session,
    user_id: int,
    method_data,
) -> PaymentMethod:
    for existing in database_session.scalars(
        select(PaymentMethod).where(PaymentMethod.user_id == user_id)
    ):
        existing.is_default = False
    method = PaymentMethod(
        user_id=user_id,
        **method_data.model_dump(),
        provider_token=f"demo_pm_{token_hex(12)}",
        is_default=True,
    )
    database_session.add(method)
    database_session.commit()
    database_session.refresh(method)
    return method


def list_user_rewards(
    database_session: Session,
    user_id: int,
) -> list[V2GTransaction]:
    statement = (
        select(V2GTransaction)
        .join(ChargingSchedule, V2GTransaction.schedule_id == ChargingSchedule.id)
        .join(ChargingRequest, ChargingSchedule.request_id == ChargingRequest.id)
        .where(ChargingRequest.user_id == user_id)
        .order_by(V2GTransaction.transaction_time.desc())
    )
    return list(database_session.scalars(statement))
