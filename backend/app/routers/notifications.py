from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import Notification


router = APIRouter(prefix="/notifications", tags=["Notifications"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[schemas.NotificationRead])
def list_notifications(database_session: DatabaseSession, current_user: CurrentUser):
    return list(database_session.scalars(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(50)
    ))


@router.patch("/{notification_id}/read", response_model=schemas.NotificationRead)
def mark_read(notification_id: int, database_session: DatabaseSession, current_user: CurrentUser):
    notification = database_session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    notification.read_at = notification.read_at or datetime.now(timezone.utc).replace(tzinfo=None)
    database_session.commit()
    database_session.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(database_session: DatabaseSession, current_user: CurrentUser) -> Response:
    database_session.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    database_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
