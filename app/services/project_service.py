import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.errors import ProjectKeyAlreadyExistsError
from app.models import Project, ProjectMember, ProjectRole, User
from app.schemas.project import ProjectCreateRequest, ProjectUpdateRequest


def create_project(db: Session, owner: User, create_request: ProjectCreateRequest) -> Project:
    project = Project(key=create_request.key, name=create_request.name, owner_id=owner.id)
    project.members.append(ProjectMember(user_id=owner.id, role=ProjectRole.OWNER))
    db.add(project)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ProjectKeyAlreadyExistsError from error
    return project


def count_project_members(db: Session, project_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id)
        )
        or 0
    )


def list_projects_for_user(db: Session, user: User) -> list[tuple[Project, int]]:
    user_membership = aliased(ProjectMember)
    member_count = (
        select(func.count(ProjectMember.user_id))
        .where(ProjectMember.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Project, member_count)
        .join(user_membership, user_membership.project_id == Project.id)
        .where(user_membership.user_id == user.id)
        .order_by(Project.created_at)
    ).all()
    return [(project, project_member_count) for project, project_member_count in rows]


def update_project(db: Session, project: Project, update_request: ProjectUpdateRequest) -> Project:
    project.name = update_request.name
    db.commit()
    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()


def bump_task_version(db: Session, project_id: uuid.UUID) -> None:
    db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(task_version=Project.task_version + 1)
        .execution_options(synchronize_session=False)
    )
