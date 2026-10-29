import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotificationNotFoundError
from app.models import Notification, NotificationType, Task, User
from app.models.base import utc_now
from app.schemas.task_event import TaskEvent

logger = logging.getLogger(__name__)

UNKNOWN_USERNAME = "Someone"


def resolve_recipient_ids(task_event: TaskEvent, task: Task) -> set[uuid.UUID]:
    if task_event.type == NotificationType.TASK_OVERDUE:
        return {task.assignee_id or task.project.owner_id}
    if task_event.type == NotificationType.TASK_STATUS_CHANGED:
        candidate_ids = {task_event.actor_id, task_event.assignee_id}
    else:
        candidate_ids = {
            task_event.actor_id,
            task_event.previous_assignee_id,
            task_event.assignee_id,
        }
    return {candidate_id for candidate_id in candidate_ids if candidate_id is not None}


def build_message(task_event: TaskEvent, task: Task, usernames: dict[uuid.UUID, str]) -> str:
    def username_of(user_id: uuid.UUID | None) -> str:
        return usernames.get(user_id, UNKNOWN_USERNAME) if user_id else UNKNOWN_USERNAME

    actor = username_of(task_event.actor_id)
    previous_assignee = username_of(task_event.previous_assignee_id)
    assignee = username_of(task_event.assignee_id)
    match task_event.type:
        case NotificationType.TASK_ASSIGNED:
            return f"{actor} assigned {task.key} to {assignee}"
        case NotificationType.TASK_REASSIGNED:
            return f"{actor} reassigned {task.key} from {previous_assignee} to {assignee}"
        case NotificationType.TASK_UNASSIGNED:
            return f"{actor} unassigned {previous_assignee} from {task.key}"
        case NotificationType.TASK_STATUS_CHANGED:
            return (
                f"{actor} moved {task.key} from {task_event.previous_status} to {task_event.status}"
            )
        case NotificationType.TASK_OVERDUE:
            return f"Due date for {task.key} has passed"


def create_task_event_notifications(db: Session, task_event: TaskEvent) -> list[Notification]:
    task = db.get(Task, task_event.task_id)
    if task is None:
        logger.info("Skipping event %s: task no longer exists", task_event.event_id)
        return []
    recipient_ids = resolve_recipient_ids(task_event, task)
    mentioned_ids = recipient_ids | {
        user_id
        for user_id in (
            task_event.actor_id,
            task_event.previous_assignee_id,
            task_event.assignee_id,
        )
        if user_id is not None
    }
    usernames = {
        user.id: user.username
        for user in db.scalars(select(User).where(User.id.in_(mentioned_ids)))
    }
    message = build_message(task_event, task, usernames)
    notifications = [
        Notification(
            user_id=recipient_id,
            task_id=task.id,
            event_id=task_event.event_id,
            type=task_event.type,
            message=message,
        )
        for recipient_id in recipient_ids
    ]
    db.add_all(notifications)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("Skipping event %s: notifications already created", task_event.event_id)
        return []
    for notification in notifications:
        logger.info(
            "notification user=%s type=%s task=%s message=%r",
            notification.user_id,
            notification.type.value,
            task.key,
            notification.message,
        )
    return notifications


def list_notifications(
    db: Session, user_id: uuid.UUID, is_read: bool | None, limit: int, offset: int
) -> tuple[list[Notification], int]:
    conditions = [Notification.user_id == user_id]
    if is_read is True:
        conditions.append(Notification.read_at.is_not(None))
    if is_read is False:
        conditions.append(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(Notification).where(*conditions)) or 0
    notifications = db.scalars(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id)
        .limit(limit)
        .offset(offset)
    )
    return list(notifications), total


def mark_notification_read(
    db: Session, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if notification is None:
        raise NotificationNotFoundError
    if notification.read_at is None:
        notification.read_at = utc_now()
        db.commit()
    return notification
