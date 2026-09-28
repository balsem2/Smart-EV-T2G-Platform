from math import floor
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import stripe

from app import crud, schemas
from app.config import settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import ChargingRequest, ChargingSchedule, Payment, Station, User, Vehicle


router = APIRouter(prefix="/payments", tags=["Payments"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _stripe_ready() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_secret_key.startswith("sk_test_"))


@router.get("", response_model=list[schemas.PaymentRead])
def list_payments(database_session: DatabaseSession, current_user: CurrentUser):
    return list(database_session.scalars(
        select(Payment).where(Payment.user_id == current_user.id).order_by(Payment.created_at.desc())
    ))


@router.get("/stripe/status", response_model=schemas.StripeCheckoutRead)
def stripe_status() -> schemas.StripeCheckoutRead:
    return schemas.StripeCheckoutRead(configured=_stripe_ready())


@router.post("/stripe/checkout-session", response_model=schemas.StripeCheckoutRead)
def create_stripe_checkout_session(
    payload: schemas.StripeCheckoutCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.StripeCheckoutRead:
    if not _stripe_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe test mode is not configured.")
    schedule = database_session.get(ChargingSchedule, payload.schedule_id)
    request = database_session.get(ChargingRequest, schedule.request_id) if schedule else None
    if schedule is None or request is None or request.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charging plan not found.")
    if database_session.scalar(select(Payment).where(Payment.schedule_id == schedule.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This charging plan has already been paid.")
    original_amount = round(max(schedule.cost or 0, 0), 2)
    points = min(floor(original_amount), current_user.reward_points // 100) * 100 if payload.redeem_points else 0
    amount = round(original_amount - points / 100, 2)
    if amount < 0.5:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stripe requires at least €0.50. Use local demo checkout for this plan.")
    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=current_user.email,
            client_reference_id=str(current_user.id),
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": f"Smart EV {schedule.mode.upper()} charging reservation"},
                    "unit_amount": int(round(amount * 100)),
                },
                "quantity": 1,
            }],
            invoice_creation={"enabled": True},
            metadata={
                "schedule_id": str(schedule.id),
                "user_id": str(current_user.id),
                "redeem_points": "true" if payload.redeem_points else "false",
            },
            success_url=f"{settings.frontend_url}/?stripe_session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/?stripe_cancelled=1",
        )
    except stripe.StripeError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Stripe test checkout failed: {error.user_message or str(error)}") from error
    return schemas.StripeCheckoutRead(configured=True, checkout_url=session.url, session_id=session.id)


@router.post("/stripe/confirm/{session_id}", response_model=schemas.PaymentRead)
def confirm_stripe_checkout(
    session_id: str,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.PaymentRead:
    existing = database_session.scalar(select(Payment).where(Payment.provider_session_id == session_id))
    if existing is not None:
        if existing.user_id != current_user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found.")
        return existing
    if not _stripe_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe test mode is not configured.")
    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["invoice"])
    except stripe.StripeError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stripe session could not be verified.") from error
    if session.payment_status != "paid" or str(session.client_reference_id) != str(current_user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stripe has not confirmed this payment.")
    schedule_id = int(session.metadata["schedule_id"])
    invoice = session.invoice if getattr(session, "invoice", None) else None
    data = SimpleNamespace(
        schedule_id=schedule_id,
        payment_method="stripe_checkout",
        payment_method_id=None,
        card_last4="test",
        redeem_points=session.metadata.get("redeem_points") == "true",
    )
    try:
        return crud.create_payment(
            database_session,
            current_user.id,
            data,
            provider="stripe_test",
            provider_session_id=session.id,
            invoice_url=getattr(invoice, "hosted_invoice_url", None),
            invoice_pdf=getattr(invoice, "invoice_pdf", None),
        )
    except (ValueError, PermissionError, RuntimeError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error


@router.get("/{payment_id}/invoice", response_model=schemas.InvoiceRead)
def get_invoice(payment_id: int, database_session: DatabaseSession, current_user: CurrentUser):
    payment = database_session.get(Payment, payment_id)
    if payment is None or payment.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found.")
    schedule = database_session.get(ChargingSchedule, payment.schedule_id)
    request = database_session.get(ChargingRequest, schedule.request_id) if schedule else None
    station = database_session.get(Station, request.station_id) if request and request.station_id else None
    vehicle = database_session.get(Vehicle, request.vehicle_id) if request and request.vehicle_id else None
    return schemas.InvoiceRead(
        payment_id=payment.id,
        reference=payment.reference,
        issued_at=payment.created_at,
        customer_name=current_user.name,
        customer_email=current_user.email,
        station_name=station.station_name if station else None,
        vehicle_model=vehicle.model if vehicle else None,
        start_time=schedule.start_time if schedule else None,
        end_time=schedule.end_time if schedule else None,
        original_amount=payment.original_amount,
        points_discount_eur=payment.points_discount_eur,
        amount_paid=payment.amount,
        currency=payment.currency,
        provider=payment.provider,
        invoice_url=payment.invoice_url,
        invoice_pdf=payment.invoice_pdf,
    )


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
