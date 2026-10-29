import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import Task, TaskStatus


def strip_task_title(title: str) -> str:
    stripped_title = title.strip()
    if not stripped_title:
        raise ValueError("title must not be blank")
    return stripped_title


def normalize_due_date(due_date: datetime | None) -> datetime | None:
    if due_date is None:
        return None
    if due_date.tzinfo is None:
        return due_date.replace(tzinfo=UTC)
    return due_date.astimezone(UTC)


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, title: str) -> str:
        return strip_task_title(title)

    @field_validator("due_date")
    @classmethod
    def convert_due_date_to_utc(cls, due_date: datetime | None) -> datetime | None:
        return normalize_due_date(due_date)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, title: str | None) -> str | None:
        return None if title is None else strip_task_title(title)

    @field_validator("due_date")
    @classmethod
    def convert_due_date_to_utc(cls, due_date: datetime | None) -> datetime | None:
        return normalize_due_date(due_date)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field_name in ("title", "status"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class TaskResponse(BaseModel):
    id: uuid.UUID
    key: str
    number: int
    project_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    assignee_id: uuid.UUID | None
    due_date: datetime | None
    creator_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: Task) -> "TaskResponse":
        return cls(
            id=task.id,
            key=task.key,
            number=task.number,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            assignee_id=task.assignee_id,
            due_date=task.due_date,
            creator_id=task.creator_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class TaskSortField(StrEnum):
    DUE_DATE = "due_date"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TaskSearchRequest(BaseModel):
    project_id: list[uuid.UUID] = Field(default_factory=list)
    status: list[TaskStatus] = Field(default_factory=list)
    assignee_id: list[uuid.UUID] = Field(default_factory=list)
    is_unassigned: bool | None = None
    due_from: date | None = None
    due_to: date | None = None
    sort: TaskSortField = TaskSortField.CREATED_AT
    order: SortOrder = SortOrder.DESC
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("project_id", "status", "assignee_id")
    @classmethod
    def sort_and_deduplicate(cls, values: list) -> list:
        return sorted(set(values))

    @model_validator(mode="after")
    def check_due_range(self) -> Self:
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise ValueError("due_from must not be after due_to")
        return self


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    limit: int
    offset: int
