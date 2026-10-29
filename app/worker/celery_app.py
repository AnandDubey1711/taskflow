from celery import Celery
from celery.schedules import crontab

from app.config import get_settings
from app.worker.task_names import (
    CHECK_OVERDUE_TASKS,
    DELETE_EXPIRED_USER_SESSIONS,
)

settings = get_settings()

celery_app = Celery("taskflow", broker=settings.redis_url, include=["app.worker.tasks"])

celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        CHECK_OVERDUE_TASKS: {
            "task": CHECK_OVERDUE_TASKS,
            "schedule": settings.overdue_check_seconds,
        },
        DELETE_EXPIRED_USER_SESSIONS: {
            "task": DELETE_EXPIRED_USER_SESSIONS,
            "schedule": crontab(hour=3, minute=0),
        },
    },
)
