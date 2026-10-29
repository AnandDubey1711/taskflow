import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.models import ProjectMember, ProjectRole
from app.schemas.user import normalize_email


class ProjectMemberCreateRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return normalize_email(email)


class ProjectMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    username: str
    role: ProjectRole
    joined_at: datetime

    @classmethod
    def from_project_member(cls, project_member: ProjectMember) -> "ProjectMemberResponse":
        return cls(
            user_id=project_member.user_id,
            email=project_member.user.email,
            username=project_member.user.username,
            role=project_member.role,
            joined_at=project_member.joined_at,
        )
