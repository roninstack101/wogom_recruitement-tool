# app/api/notifications.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Notification, User
from app.api.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationOut(BaseModel):
    id: int
    message: str
    type: str
    is_read: bool
    related_job_id: int | None = None
    created_at: str | None = None


def _notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "message": n.message,
        "type": n.type.value if hasattr(n.type, "value") else n.type,
        "is_read": n.is_read,
        "related_job_id": n.related_job_id,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("/", response_model=List[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current user (newest first)."""
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [_notif_to_dict(n) for n in notifs]


@router.get("/unread-count")
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the count of unread notifications."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read == False)
        .count()
    )
    return {"count": count}


@router.post("/{notif_id}/read")
def mark_read(
    notif_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}
