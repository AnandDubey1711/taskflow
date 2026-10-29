import uuid
from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ProjectNotFoundError, ProjectOwnerRequiredError
from app.db import get_db
from app.models import ProjectMember, ProjectRole, Task, User, UserSession
from app.services import project_member_service, task_service, user_session_service

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def raise_unauthorized(detail: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_session(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserSession:
    if credentials is None:
        raise_unauthorized("Not authenticated")
    user_session = user_session_service.resolve_user_session(db, credentials.credentials)
    if user_session is None:
        raise_unauthorized("Invalid or expired session")
    return user_session


CurrentUserSession = Annotated[UserSession, Depends(get_current_user_session)]


def get_current_user(user_session: CurrentUserSession) -> User:
    return user_session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_project_member(
    project_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> ProjectMember:
    project_member = project_member_service.get_project_member(db, project_id, current_user.id)
    if project_member is None:
        raise ProjectNotFoundError
    return project_member


CurrentProjectMember = Annotated[ProjectMember, Depends(require_project_member)]


def require_project_owner(project_member: CurrentProjectMember) -> ProjectMember:
    if project_member.role != ProjectRole.OWNER:
        raise ProjectOwnerRequiredError
    return project_member


CurrentProjectOwner = Annotated[ProjectMember, Depends(require_project_owner)]


def require_project_task(
    task_id: uuid.UUID, project_member: CurrentProjectMember, db: DbSession
) -> Task:
    return task_service.get_task(db, project_member.project_id, task_id)


CurrentProjectTask = Annotated[Task, Depends(require_project_task)]
