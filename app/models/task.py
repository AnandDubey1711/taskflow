import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UtcDateTime, utc_now
from app.models.project import Project
from app.models.user import User

OVERDUE_CANDIDATE_CONDITION = "status <> 'done' AND overdue_notified_at IS NULL"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_tasks_project_id_number"),
        Index("ix_tasks_project_id_status", "project_id", "status"),
        Index("ix_tasks_project_id_assignee_id", "project_id", "assignee_id"),
        Index("ix_tasks_project_id_due_date", "project_id", "due_date"),
        Index("ix_tasks_project_id_created_at", "project_id", "created_at"),
        Index(
            "ix_tasks_overdue_candidates",
            "due_date",
            postgresql_where=text(OVERDUE_CANDIDATE_CONDITION),
            sqlite_where=text(OVERDUE_CANDIDATE_CONDITION),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            native_enum=False,
            length=20,
            values_callable=lambda statuses: [task_status.value for task_status in statuses],
        ),
        nullable=False,
        default=TaskStatus.TODO,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    overdue_notified_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    creator_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])

    @property
    def key(self) -> str:
        return f"{self.project.key}-{self.number}"
