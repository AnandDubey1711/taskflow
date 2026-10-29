import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ProjectMemberAlreadyExistsError,
    ProjectMemberNotFoundError,
    ProjectOwnerRemovalError,
    ProjectOwnerRequiredError,
    UserNotFoundError,
)
from app.models import Project, ProjectMember, ProjectRole, Task, User


def get_project_member(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    return db.get(ProjectMember, (project_id, user_id))


def list_project_members(db: Session, project_id: uuid.UUID) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.joined_at)
        )
    )


def add_project_member(db: Session, project: Project, email: str) -> ProjectMember:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise UserNotFoundError
    if get_project_member(db, project.id, user.id) is not None:
        raise ProjectMemberAlreadyExistsError
    project_member = ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.MEMBER)
    db.add(project_member)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ProjectMemberAlreadyExistsError from error
    return project_member


def remove_project_member(db: Session, actor: ProjectMember, user_id: uuid.UUID) -> None:
    is_self_removal = actor.user_id == user_id
    if actor.role != ProjectRole.OWNER and not is_self_removal:
        raise ProjectOwnerRequiredError
    project_member = get_project_member(db, actor.project_id, user_id)
    if project_member is None:
        raise ProjectMemberNotFoundError
    if project_member.role == ProjectRole.OWNER:
        raise ProjectOwnerRemovalError
    db.execute(
        update(Task)
        .where(Task.project_id == actor.project_id, Task.assignee_id == user_id)
        .values(assignee_id=None)
        .execution_options(synchronize_session="fetch")
    )
    db.delete(project_member)
    db.commit()
