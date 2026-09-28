from datetime import datetime, timezone
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
    role: Literal["driver", "operator", "admin"] = "driver"
    managed_station_id: int | None = None
    email_verified: bool = False

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
    connector_types: str | None
    vehicle_age: float | None
    supports_v2g: bool = False

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
    supports_v2g: bool = False

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
    connector_types: str
    supports_v2g: bool = False

    model_config = ConfigDict(from_attributes=True)


class ChargingRequestCreate(BaseModel):
    vehicle_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    current_soc: float = Field(ge=0, le=100)
    target_soc: float = Field(gt=0, le=100)
    earliest_start_time: datetime | None = None
    departure_time: datetime

    @model_validator(mode="after")
    def validate_soc_range(self) -> "ChargingRequestCreate":
        if self.target_soc <= self.current_soc:
            raise ValueError("target_soc must be greater than current_soc")
        if self.earliest_start_time is not None and self.earliest_start_time.tzinfo is not None:
            self.earliest_start_time = self.earliest_start_time.astimezone(timezone.utc).replace(
                tzinfo=None
            )
        if self.departure_time.tzinfo is not None:
            self.departure_time = self.departure_time.astimezone(timezone.utc).replace(
                tzinfo=None
            )
        if self.earliest_start_time is not None and self.departure_time <= self.earliest_start_time:
            raise ValueError("departure_time must be after earliest_start_time")
        return self


class ChargingRequestRead(BaseModel):
    id: int
    user_id: int | None
    vehicle_id: int | None
    station_id: int | None
    current_soc: float | None
    target_soc: float | None
    earliest_start_time: datetime | None
    departure_time: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OptimizationRun(BaseModel):
    mode: Literal["normal", "v1g", "v2g"] = "v1g"
    variant: Literal["balanced", "lowest_cost", "greenest"] = "balanced"


class V2GOfferCreate(BaseModel):
    vehicle_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    current_soc: float = Field(gt=0, le=100)
    minimum_soc: float = Field(ge=0, lt=100)
    available_until: datetime

    @model_validator(mode="after")
    def validate_reserve(self) -> "V2GOfferCreate":
        if self.current_soc <= self.minimum_soc:
            raise ValueError("Current SoC must be above the minimum battery reserve.")
        if self.available_until.tzinfo is not None:
            self.available_until = self.available_until.astimezone(timezone.utc).replace(tzinfo=None)
        return self


class V2GOfferRead(BaseModel):
    id: int
    vehicle_id: int
    station_id: int
    current_soc: float
    minimum_soc: float
    export_energy_kwh: float
    reward_eur: float
    export_start: datetime
    export_end: datetime
    delivered_energy_kwh: float | None
    credited_reward_eur: float | None
    status: Literal["offered", "accepted", "completed", "declined"]

    model_config = ConfigDict(from_attributes=True)


class V2GDeliveryConfirmation(BaseModel):
    delivered_energy_kwh: float = Field(gt=0)


class ReservationRead(BaseModel):
    id: int
    user_id: int
    vehicle_id: int
    station_id: int
    schedule_id: int
    start_time: datetime
    end_time: datetime
    status: Literal["confirmed", "completed", "cancelled"]
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ReservationStatusUpdate(BaseModel):
    status: Literal["confirmed", "completed", "cancelled"]


class NotificationRead(BaseModel):
    id: int
    type: str
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: int | None
    read_at: datetime | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OperatorDashboardRead(BaseModel):
    station: StationRead
    reservations: list[ReservationRead]
    v2g_offers: list[V2GOfferRead]
    confirmed_reservations: int
    pending_v2g_deliveries: int


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
    variant: Literal["balanced", "lowest_cost", "greenest"]
    predicted_energy_kwh: float
    predicted_duration_hours: float
    cost_eur: float
    net_cost_eur: float
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
    redeem_points: bool = False

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
    original_amount: float
    amount: float
    points_redeemed: int
    points_discount_eur: float
    currency: str
    payment_method: str
    card_last4: str
    status: Literal["paid", "refunded"]
    reference: str
    provider: str = "local_demo"
    invoice_url: str | None = None
    invoice_pdf: str | None = None
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


class EmailRequest(BaseModel):
    email: EmailStr


class AccountTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)


class PasswordResetConfirm(AccountTokenRequest):
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordResetConfirm":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")
        return self


class AuthActionResponse(BaseModel):
    message: str
    development_token: str | None = None


class RegistrationResponse(AuthActionResponse):
    email: EmailStr


class StripeCheckoutCreate(BaseModel):
    schedule_id: int = Field(gt=0)
    redeem_points: bool = False


class StripeCheckoutRead(BaseModel):
    configured: bool
    checkout_url: str | None = None
    session_id: str | None = None


class InvoiceRead(BaseModel):
    payment_id: int
    reference: str
    issued_at: datetime | None
    customer_name: str | None
    customer_email: EmailStr | None
    station_name: str | None
    vehicle_model: str | None
    start_time: datetime | None
    end_time: datetime | None
    original_amount: float
    points_discount_eur: float
    amount_paid: float
    currency: str
    provider: str
    invoice_url: str | None
    invoice_pdf: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead
    verification_token: str | None = None


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
    reward_type: Literal["v1g_saving", "v2g_export"]
    saving_eur: float
    points: int
    energy_returned: float | None
    reward: float | None
    transaction_time: datetime | None

    model_config = ConfigDict(from_attributes=True)
