import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    is_read: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    notifications, total = notification_service.list_notifications(
        db, current_user.id, is_read, limit, offset
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(notification) for notification in notifications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> NotificationResponse:
    notification = notification_service.mark_notification_read(db, current_user.id, notification_id)
    return NotificationResponse.model_validate(notification)
