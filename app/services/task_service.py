import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import TaskAssigneeNotMemberError, TaskNotFoundError
from app.models import NotificationType, Project, ProjectMember, Task, TaskStatus
from app.models.base import utc_now
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
from app.schemas.task_event import TaskEvent
from app.services import project_member_service, task_event_service


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
    task_event_service.publish_task_events(
        [task_event_service.build_assignment_event(task, creator.user_id, None)]
    )
    return task


def get_task(db: Session, project_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    if task is None:
        raise TaskNotFoundError
    return task


def should_rearm_overdue_check(
    task: Task, previous_due_date: datetime | None, previous_status: TaskStatus
) -> bool:
    is_due_date_changed = task.due_date != previous_due_date
    is_reopened = previous_status == TaskStatus.DONE and task.status != TaskStatus.DONE
    return is_due_date_changed or is_reopened


def update_task(
    db: Session, actor: ProjectMember, task: Task, update_request: TaskUpdateRequest
) -> Task:
    changes = update_request.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        ensure_assignee_is_member(db, task.project_id, changes["assignee_id"])
    previous_assignee_id = task.assignee_id
    previous_status = task.status
    previous_due_date = task.due_date
    for field_name, value in changes.items():
        setattr(task, field_name, value)
    if should_rearm_overdue_check(task, previous_due_date, previous_status):
        task.overdue_notified_at = None
    db.commit()
    task_event_service.publish_task_events(
        [
            task_event_service.build_assignment_event(task, actor.user_id, previous_assignee_id),
            task_event_service.build_status_event(task, actor.user_id, previous_status),
        ]
    )
    return task


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def notify_overdue_tasks(db: Session) -> int:
    now = utc_now()
    claimed_tasks = db.execute(
        update(Task)
        .where(
            Task.due_date < now,
            Task.status != TaskStatus.DONE,
            Task.overdue_notified_at.is_(None),
        )
        .values(overdue_notified_at=now)
        .returning(Task.id, Task.assignee_id)
        .execution_options(synchronize_session=False)
    ).all()
    db.commit()
    task_event_service.publish_task_events(
        [
            TaskEvent(type=NotificationType.TASK_OVERDUE, task_id=task_id, assignee_id=assignee_id)
            for task_id, assignee_id in claimed_tasks
        ]
    )
    return len(claimed_tasks)
