from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from hashlib import sha256
from secrets import token_urlsafe
import smtplib

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AccountToken, User


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_account_token(
    database_session: Session,
    user: User,
    purpose: str,
    lifetime_minutes: int,
) -> str:
    database_session.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=_now())
    )
    raw_token = token_urlsafe(32)
    database_session.add(AccountToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=sha256(raw_token.encode()).hexdigest(),
        expires_at=_now() + timedelta(minutes=lifetime_minutes),
    ))
    database_session.commit()
    return raw_token


def consume_account_token(
    database_session: Session,
    raw_token: str,
    purpose: str,
) -> User | None:
    token = database_session.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == sha256(raw_token.encode()).hexdigest(),
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > _now(),
        )
    )
    if token is None:
        return None
    token.used_at = _now()
    return database_session.get(User, token.user_id)


def send_account_email(recipient: str, subject: str, action_url: str, action_label: str) -> bool:
    """Send through SMTP when configured; development otherwise exposes the token."""
    if not settings.smtp_host:
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(f"{action_label}: {action_url}\n\nThis link expires automatically.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        return False
