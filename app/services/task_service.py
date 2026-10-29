import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import TaskAssigneeNotMemberError, TaskNotFoundError
from app.models import Project, ProjectMember, Task
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
from app.services import project_member_service


def ensure_assignee_is_member(
    db: Session, project_id: uuid.UUID, assignee_id: uuid.UUID | None
) -> None:
    if assignee_id is None:
        return
    if project_member_service.get_project_member(db, project_id, assignee_id) is None:
        raise TaskAssigneeNotMemberError


def allocate_task_number(db: Session, project_id: uuid.UUID) -> int:
    return db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(last_task_number=Project.last_task_number + 1)
        .returning(Project.last_task_number)
    ).scalar_one()


def create_task(db: Session, creator: ProjectMember, create_request: TaskCreateRequest) -> Task:
    ensure_assignee_is_member(db, creator.project_id, create_request.assignee_id)
    task = Task(
        project_id=creator.project_id,
        number=allocate_task_number(db, creator.project_id),
        title=create_request.title,
        description=create_request.description,
        status=create_request.status,
        assignee_id=create_request.assignee_id,
        due_date=create_request.due_date,
        creator_id=creator.user_id,
    )
    db.add(task)
    db.commit()
    return task


def get_task(db: Session, project_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    if task is None:
        raise TaskNotFoundError
    return task


def update_task(db: Session, task: Task, update_request: TaskUpdateRequest) -> Task:
    changes = update_request.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        ensure_assignee_is_member(db, task.project_id, changes["assignee_id"])
    for field_name, value in changes.items():
        setattr(task, field_name, value)
    db.commit()
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()
