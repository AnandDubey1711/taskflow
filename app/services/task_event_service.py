import logging
import uuid

from kombu.exceptions import OperationalError

from app.models import NotificationType, Task, TaskStatus
from app.schemas.task_event import TaskEvent
from app.worker.celery_app import celery_app
from app.worker.task_names import NOTIFY_TASK_EVENT

logger = logging.getLogger(__name__)

PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.2}


def build_assignment_event(
    task: Task, actor_id: uuid.UUID, previous_assignee_id: uuid.UUID | None
) -> TaskEvent | None:
    if previous_assignee_id == task.assignee_id:
        return None
    if previous_assignee_id is None:
        event_type = NotificationType.TASK_ASSIGNED
    elif task.assignee_id is None:
        event_type = NotificationType.TASK_UNASSIGNED
    else:
        event_type = NotificationType.TASK_REASSIGNED
    return TaskEvent(
        type=event_type,
        task_id=task.id,
        actor_id=actor_id,
        previous_assignee_id=previous_assignee_id,
        assignee_id=task.assignee_id,
    )


def build_status_event(
    task: Task, actor_id: uuid.UUID, previous_status: TaskStatus
) -> TaskEvent | None:
    if previous_status == task.status:
        return None
    return TaskEvent(
        type=NotificationType.TASK_STATUS_CHANGED,
        task_id=task.id,
        actor_id=actor_id,
        assignee_id=task.assignee_id,
        previous_status=previous_status,
        status=task.status,
    )


def publish_task_events(task_events: list[TaskEvent | None]) -> None:
    for task_event in task_events:
        if task_event is None:
            continue
        try:
            celery_app.send_task(
                NOTIFY_TASK_EVENT,
                args=[task_event.model_dump(mode="json")],
                retry=True,
                retry_policy=PUBLISH_RETRY_POLICY,
            )
        except OperationalError:
            logger.exception("Failed to enqueue task event %s", task_event.event_id)
