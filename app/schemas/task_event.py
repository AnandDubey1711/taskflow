import uuid

from pydantic import BaseModel, Field

from app.models import NotificationType, TaskStatus


class TaskEvent(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: NotificationType
    task_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    previous_assignee_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    previous_status: TaskStatus | None = None
    status: TaskStatus | None = None
