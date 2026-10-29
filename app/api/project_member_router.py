import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentProjectMember, CurrentProjectOwner, DbSession
from app.schemas.project_member import ProjectMemberCreateRequest, ProjectMemberResponse
from app.services import project_member_service

router = APIRouter(prefix="/projects/{project_id}/members", tags=["project members"])


@router.get("", response_model=list[ProjectMemberResponse])
def list_project_members(
    project_member: CurrentProjectMember, db: DbSession
) -> list[ProjectMemberResponse]:
    return [
        ProjectMemberResponse.from_project_member(member)
        for member in project_member_service.list_project_members(db, project_member.project_id)
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectMemberResponse)
def add_project_member(
    create_request: ProjectMemberCreateRequest, project_owner: CurrentProjectOwner, db: DbSession
) -> ProjectMemberResponse:
    added_member = project_member_service.add_project_member(
        db, project_owner.project, create_request.email
    )
    return ProjectMemberResponse.from_project_member(added_member)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    user_id: uuid.UUID, project_member: CurrentProjectMember, db: DbSession
) -> None:
    project_member_service.remove_project_member(db, project_member, user_id)
