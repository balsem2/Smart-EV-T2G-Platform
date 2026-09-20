from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator


class UserCreate(BaseModel):
    """Data accepted when registering a user."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserRead(BaseModel):
    """Public user data returned by the API."""

    id: int
    name: str | None
    email: EmailStr | None
    wallet_balance: float
    reward_points: int
    theme: Literal["light", "dark", "system"]
    onboarding_completed: bool

    model_config = ConfigDict(from_attributes=True)


class VehicleCreate(BaseModel):
    """A vehicle selected from the controlled EV catalogue."""

    catalog_id: int = Field(gt=0)
    vehicle_age: float = Field(ge=0, le=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class VehicleRead(BaseModel):
    """Vehicle data returned by the API."""

    id: int
    user_id: int | None
    catalog_id: int | None
    model: str | None
    battery_capacity: float | None
    vehicle_age: float | None

    model_config = ConfigDict(from_attributes=True)


class StationCreate(BaseModel):
    station_name: str = Field(min_length=1, max_length=150)
    city: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    charger_type: str = Field(min_length=1, max_length=50)
    power_kw: float = Field(gt=0, le=1000)
    operator: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class StationRead(BaseModel):
    id: int
    station_name: str | None
    city: str | None
    latitude: float | None
    longitude: float | None
    charger_type: str | None
    power_kw: float | None
    operator: str | None
    source: str | None
    total_chargers: int
    available_chargers: int
    operational_status: Literal["online", "offline", "maintenance"]
    availability_source: Literal["simulated", "live", "manual"]
    last_status_at: datetime | None

    @computed_field
    @property
    def occupied_chargers(self) -> int:
        return max(0, self.total_chargers - self.available_chargers)

    model_config = ConfigDict(from_attributes=True)


class StationStatusUpdate(BaseModel):
    total_chargers: int = Field(ge=1, le=100)
    available_chargers: int = Field(ge=0, le=100)
    operational_status: Literal["online", "offline", "maintenance"] = "online"
    availability_source: Literal["simulated", "live", "manual"] = "live"

    @model_validator(mode="after")
    def validate_availability(self) -> "StationStatusUpdate":
        if self.available_chargers > self.total_chargers:
            raise ValueError("available_chargers cannot exceed total_chargers")
        if self.operational_status != "online" and self.available_chargers != 0:
            raise ValueError("an offline or maintenance station cannot be available")
        return self


class VehicleCatalogRead(BaseModel):
    id: int
    model: str
    battery_capacity: float

    model_config = ConfigDict(from_attributes=True)


class ChargingRequestCreate(BaseModel):
    vehicle_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    current_soc: float = Field(ge=0, le=100)
    target_soc: float = Field(gt=0, le=100)
    departure_time: datetime

    @model_validator(mode="after")
    def validate_soc_range(self) -> "ChargingRequestCreate":
        if self.target_soc <= self.current_soc:
            raise ValueError("target_soc must be greater than current_soc")
        return self


class ChargingRequestRead(BaseModel):
    id: int
    user_id: int | None
    vehicle_id: int | None
    station_id: int | None
    current_soc: float | None
    target_soc: float | None
    departure_time: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OptimizationRun(BaseModel):
    mode: Literal["normal", "v1g", "v2g"] = "v1g"


class OptimizationSlot(BaseModel):
    timestamp: datetime
    action: Literal["charge", "discharge"]
    energy_kwh: float
    power_kw: float
    price_eur_per_mwh: float


class OptimizationResult(BaseModel):
    schedule_id: int
    request_id: int
    mode: Literal["normal", "v1g", "v2g"]
    predicted_energy_kwh: float
    predicted_duration_hours: float
    cost_eur: float
    saving_eur: float
    v2g_energy_kwh: float
    v2g_reward_eur: float
    start_time: datetime
    end_time: datetime
    slots: list[OptimizationSlot]
    wallet_balance: float
    reward_points: int
    forecast_source: Literal["machine_learning", "historical_baseline"]
    model_name: str


class PaymentCheckout(BaseModel):
    schedule_id: int = Field(gt=0)
    payment_method: Literal["test_card", "saved_card"] = "test_card"
    card_last4: str | None = Field(default=None, pattern=r"^\d{4}$")
    payment_method_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_payment_source(self) -> "PaymentCheckout":
        if self.payment_method == "test_card" and self.card_last4 is None:
            raise ValueError("card_last4 is required for a test card")
        if self.payment_method == "saved_card" and self.payment_method_id is None:
            raise ValueError("payment_method_id is required for a saved card")
        return self


class PaymentRead(BaseModel):
    id: int
    schedule_id: int
    amount: float
    currency: str
    payment_method: str
    card_last4: str
    status: Literal["paid", "refunded"]
    reference: str
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PaymentMethodCreate(BaseModel):
    cardholder_name: str = Field(min_length=2, max_length=100)
    brand: Literal["Visa", "Mastercard", "Other"]
    last4: str = Field(pattern=r"^\d{4}$")
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2026, le=2100)

    model_config = ConfigDict(str_strip_whitespace=True)


class PaymentMethodRead(BaseModel):
    id: int
    cardholder_name: str
    brand: str
    last4: str
    expiry_month: int
    expiry_year: int
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "PasswordChange":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from current password")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    theme: Literal["light", "dark", "system"] | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def require_change(self) -> "UserUpdate":
        if not any(
            value is not None
            for value in (self.name, self.email, self.theme)
        ):
            raise ValueError("At least one account field must be provided")
        return self


class RewardRead(BaseModel):
    id: int
    energy_returned: float | None
    reward: float | None
    transaction_time: datetime | None

    model_config = ConfigDict(from_attributes=True)
