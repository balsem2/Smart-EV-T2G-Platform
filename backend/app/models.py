from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wallet_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    theme: Mapped[str] = mapped_column(String(10), nullable=False, default="system")
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="driver")
    managed_station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id"), nullable=True
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user")
    charging_requests: Mapped[list["ChargingRequest"]] = relationship(
        back_populates="user"
    )
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="user"
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    cardholder_name: Mapped[str] = mapped_column(String(100), nullable=False)
    brand: Mapped[str] = mapped_column(String(20), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    expiry_month: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped[User] = relationship(back_populates="payment_methods")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    catalog_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicle_catalog.id"), nullable=True
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    battery_capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    connector_types: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vehicle_age: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_v2g: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User | None] = relationship(back_populates="vehicles")
    catalog: Mapped["VehicleCatalog | None"] = relationship()
    charging_requests: Mapped[list["ChargingRequest"]] = relationship(
        back_populates="vehicle"
    )


class VehicleCatalog(Base):
    __tablename__ = "vehicle_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    battery_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    connector_types: Mapped[str] = mapped_column(
        String(120), nullable=False, default="Type 2 AC"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    supports_v2g: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ChargingRequest(Base):
    __tablename__ = "charging_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehicles.id"), nullable=True
    )
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id"), nullable=True
    )
    current_soc: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_soc: Mapped[float | None] = mapped_column(Float, nullable=True)
    earliest_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    departure_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped[User | None] = relationship(back_populates="charging_requests")
    vehicle: Mapped[Vehicle | None] = relationship(
        back_populates="charging_requests"
    )
    station: Mapped["Station | None"] = relationship(
        back_populates="charging_requests"
    )
    predictions: Mapped[list["AIPrediction"]] = relationship(
        back_populates="charging_request"
    )
    schedules: Mapped[list["ChargingSchedule"]] = relationship(
        back_populates="charging_request"
    )


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    charger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    total_chargers: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    available_chargers: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    operational_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="online"
    )
    availability_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="simulated"
    )
    last_status_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    supports_v2g: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    charging_requests: Mapped[list[ChargingRequest]] = relationship(
        back_populates="station"
    )


class StationAvailabilityObservation(Base):
    """Timestamped charger telemetry used to train availability forecasts."""

    __tablename__ = "station_availability_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    total_chargers: Mapped[int] = mapped_column(Integer, nullable=False)
    available_chargers: Mapped[int] = mapped_column(Integer, nullable=False)
    operational_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)


class EnergyData(Base):
    __tablename__ = "energy_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    electricity_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    solar_generation: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_generation: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    shortwave_radiation: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_100m: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("charging_requests.id"), nullable=True
    )
    predicted_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    charging_request: Mapped[ChargingRequest | None] = relationship(
        back_populates="predictions"
    )


class ChargingSchedule(Base):
    __tablename__ = "charging_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int | None] = mapped_column(
        ForeignKey("charging_requests.id"), nullable=True
    )
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    variant: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    saving: Mapped[float | None] = mapped_column(Float, nullable=True)
    v2g_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    v2g_reward_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="quoted")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    charging_request: Mapped[ChargingRequest | None] = relationship(
        back_populates="schedules"
    )
    reward_events: Mapped[list["RewardEvent"]] = relationship(
        back_populates="schedule"
    )
    payment: Mapped["Payment | None"] = relationship(back_populates="schedule")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("charging_schedule.id"), nullable=False, unique=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    points_redeemed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_discount_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    reference: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local_demo")
    provider_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )

    schedule: Mapped[ChargingSchedule] = relationship(back_populates="payment")


class RewardEvent(Base):
    __tablename__ = "reward_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("charging_schedule.id"), nullable=True
    )
    energy_returned: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_type: Mapped[str] = mapped_column(String(20), nullable=False, default="v2g_export")
    saving_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transaction_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    schedule: Mapped[ChargingSchedule | None] = relationship(
        back_populates="reward_events"
    )


class V2GOffer(Base):
    __tablename__ = "v2g_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    current_soc: Mapped[float] = mapped_column(Float, nullable=False)
    minimum_soc: Mapped[float] = mapped_column(Float, nullable=False)
    export_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    reward_eur: Mapped[float] = mapped_column(Float, nullable=False)
    export_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    export_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    delivered_energy_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    credited_reward_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="offered")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("charging_schedule.id"), nullable=False, unique=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="info")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )


class AccountToken(Base):
    __tablename__ = "account_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )
