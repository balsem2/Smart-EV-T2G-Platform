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

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user")
    charging_requests: Mapped[list["ChargingRequest"]] = relationship(
        back_populates="user"
    )
    payment_methods: Mapped[list["PaymentMethod"]] = relationship(
        back_populates="user"
    )


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
    vehicle_age: Mapped[float | None] = mapped_column(Float, nullable=True)

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
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


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

    charging_requests: Mapped[list[ChargingRequest]] = relationship(
        back_populates="station"
    )


class EnergyData(Base):
    __tablename__ = "energy_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    electricity_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    solar_generation: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_generation: Mapped[float | None] = mapped_column(Float, nullable=True)


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
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    saving: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="quoted")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    charging_request: Mapped[ChargingRequest | None] = relationship(
        back_populates="schedules"
    )
    v2g_transactions: Mapped[list["V2GTransaction"]] = relationship(
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
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")
    reference: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )

    schedule: Mapped[ChargingSchedule] = relationship(back_populates="payment")


class V2GTransaction(Base):
    __tablename__ = "v2g_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("charging_schedule.id"), nullable=True
    )
    energy_returned: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    transaction_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    schedule: Mapped[ChargingSchedule | None] = relationship(
        back_populates="v2g_transactions"
    )
