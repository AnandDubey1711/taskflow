import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Index, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UtcDateTime, utc_now


class NotificationType(StrEnum):
    TASK_ASSIGNED = "task_assigned"
    TASK_REASSIGNED = "task_reassigned"
    TASK_UNASSIGNED = "task_unassigned"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_OVERDUE = "task_overdue"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_notifications_event_id_user_id"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            length=30,
            values_callable=lambda types: [notification_type.value for notification_type in types],
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
