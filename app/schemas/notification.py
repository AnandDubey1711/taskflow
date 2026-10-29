import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    message: str
    task_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    limit: int
    offset: int
