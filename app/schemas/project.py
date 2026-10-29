import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import Project

PROJECT_KEY_PATTERN = r"^[A-Za-z][A-Za-z0-9]{1,9}$"


def strip_project_name(name: str) -> str:
    stripped_name = name.strip()
    if not stripped_name:
        raise ValueError("name must not be blank")
    return stripped_name


class ProjectCreateRequest(BaseModel):
    key: str = Field(pattern=PROJECT_KEY_PATTERN)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("key")
    @classmethod
    def uppercase_key(cls, key: str) -> str:
        return key.upper()

    @field_validator("name")
    @classmethod
    def strip_name(cls, name: str) -> str:
        return strip_project_name(name)


class ProjectUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, name: str) -> str:
        return strip_project_name(name)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    owner_id: uuid.UUID
    member_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_project(cls, project: Project, member_count: int) -> "ProjectResponse":
        return cls(
            id=project.id,
            key=project.key,
            name=project.name,
            owner_id=project.owner_id,
            member_count=member_count,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
