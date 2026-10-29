import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.errors import TaskAssigneeNotMemberError, TaskNotFoundError
from app.models import NotificationType, Project, ProjectMember, Task, TaskStatus
from app.models.base import utc_now
from app.schemas.task import (
    SortOrder,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskSearchRequest,
    TaskSortField,
    TaskUpdateRequest,
)
from app.schemas.task_event import TaskEvent
from app.services import (
    project_member_service,
    project_service,
    task_cache_service,
    task_event_service,
)


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
    project_service.bump_task_version(db, creator.project_id)
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


TASK_SORT_COLUMNS: dict[TaskSortField, InstrumentedAttribute] = {
    TaskSortField.DUE_DATE: Task.due_date,
    TaskSortField.CREATED_AT: Task.created_at,
    TaskSortField.UPDATED_AT: Task.updated_at,
    TaskSortField.TITLE: Task.title,
}


def start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def list_searchable_project_versions(
    db: Session, user_id: uuid.UUID, requested_project_ids: list[uuid.UUID]
) -> list[tuple[uuid.UUID, int]]:
    query = (
        select(Project.id, Project.task_version)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
        .order_by(Project.id)
    )
    if requested_project_ids:
        query = query.where(Project.id.in_(requested_project_ids))
    return [(project_id, task_version) for project_id, task_version in db.execute(query)]


def build_search_conditions(
    project_ids: list[uuid.UUID], search_request: TaskSearchRequest
) -> list[ColumnElement[bool]]:
    conditions = [Task.project_id.in_(project_ids)]
    if search_request.status:
        conditions.append(Task.status.in_(search_request.status))
    assignee_conditions = []
    if search_request.assignee_id:
        assignee_conditions.append(Task.assignee_id.in_(search_request.assignee_id))
    if search_request.is_unassigned is True:
        assignee_conditions.append(Task.assignee_id.is_(None))
    if assignee_conditions:
        conditions.append(or_(*assignee_conditions))
    if search_request.is_unassigned is False:
        conditions.append(Task.assignee_id.is_not(None))
    if search_request.due_from:
        conditions.append(Task.due_date >= start_of_day(search_request.due_from))
    if search_request.due_to:
        conditions.append(Task.due_date < start_of_day(search_request.due_to + timedelta(days=1)))
    return conditions


def query_tasks(
    db: Session, project_ids: list[uuid.UUID], search_request: TaskSearchRequest
) -> tuple[list[Task], int]:
    conditions = build_search_conditions(project_ids, search_request)
    total = db.scalar(select(func.count()).select_from(Task).where(*conditions)) or 0
    sort_column = TASK_SORT_COLUMNS[search_request.sort]
    sort_expression = (
        sort_column.asc() if search_request.order == SortOrder.ASC else sort_column.desc()
    )
    tasks = db.scalars(
        select(Task)
        .where(*conditions)
        .order_by(sort_expression.nulls_last(), Task.id)
        .limit(search_request.limit)
        .offset(search_request.offset)
    )
    return list(tasks), total


def search_tasks(
    db: Session, user_id: uuid.UUID, search_request: TaskSearchRequest
) -> tuple[TaskListResponse, bool]:
    project_versions = list_searchable_project_versions(db, user_id, search_request.project_id)
    if not project_versions:
        empty_response = TaskListResponse(
            items=[], total=0, limit=search_request.limit, offset=search_request.offset
        )
        return empty_response, False
    cache_key = task_cache_service.build_search_cache_key(project_versions, search_request)
    cached_response = task_cache_service.read_cached_search(cache_key)
    if cached_response is not None:
        return cached_response, True
    project_ids = [project_id for project_id, _ in project_versions]
    tasks, total = query_tasks(db, project_ids, search_request)
    search_response = TaskListResponse(
        items=[TaskResponse.from_task(task) for task in tasks],
        total=total,
        limit=search_request.limit,
        offset=search_request.offset,
    )
    task_cache_service.write_cached_search(cache_key, search_response)
    return search_response, False


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
    project_service.bump_task_version(db, task.project_id)
    db.commit()
    task_event_service.publish_task_events(
        [
            task_event_service.build_assignment_event(task, actor.user_id, previous_assignee_id),
            task_event_service.build_status_event(task, actor.user_id, previous_status),
        ]
    )
    return task


def delete_task(db: Session, task: Task) -> None:
    project_service.bump_task_version(db, task.project_id)
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
