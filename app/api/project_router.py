from fastapi import APIRouter, status

from app.core.dependencies import CurrentProjectMember, CurrentProjectOwner, CurrentUser, DbSession
from app.schemas.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
def create_project(
    create_request: ProjectCreateRequest, db: DbSession, current_user: CurrentUser
) -> ProjectResponse:
    project = project_service.create_project(db, current_user, create_request)
    return ProjectResponse.from_project(project, member_count=1)


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: DbSession, current_user: CurrentUser) -> list[ProjectResponse]:
    return [
        ProjectResponse.from_project(project, member_count)
        for project, member_count in project_service.list_projects_for_user(db, current_user)
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_member: CurrentProjectMember, db: DbSession) -> ProjectResponse:
    project = project_member.project
    member_count = project_service.count_project_members(db, project.id)
    return ProjectResponse.from_project(project, member_count)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    update_request: ProjectUpdateRequest, project_owner: CurrentProjectOwner, db: DbSession
) -> ProjectResponse:
    project = project_service.update_project(db, project_owner.project, update_request)
    member_count = project_service.count_project_members(db, project.id)
    return ProjectResponse.from_project(project, member_count)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_owner: CurrentProjectOwner, db: DbSession) -> None:
    project_service.delete_project(db, project_owner.project)
