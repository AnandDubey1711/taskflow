from typing import Any

from sqlalchemy.exc import OperationalError

from app.db import DbSessionFactory
from app.schemas.task_event import TaskEvent
from app.services import notification_service, task_service, user_session_service
from app.worker.celery_app import celery_app
from app.worker.task_names import (
    CHECK_OVERDUE_TASKS,
    DELETE_EXPIRED_USER_SESSIONS,
    NOTIFY_TASK_EVENT,
)


@celery_app.task(
    name=NOTIFY_TASK_EVENT,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    max_retries=5,
)
def notify_task_event(event_payload: dict[str, Any]) -> None:
    task_event = TaskEvent.model_validate(event_payload)
    with DbSessionFactory() as db:
        notification_service.create_task_event_notifications(db, task_event)


@celery_app.task(name=CHECK_OVERDUE_TASKS)
def check_overdue_tasks() -> None:
    with DbSessionFactory() as db:
        task_service.notify_overdue_tasks(db)


@celery_app.task(name=DELETE_EXPIRED_USER_SESSIONS)
def delete_expired_user_sessions() -> None:
    with DbSessionFactory() as db:
        user_session_service.delete_expired_user_sessions(db)
