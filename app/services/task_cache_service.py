import hashlib
import json
import logging
import uuid

from redis import RedisError

from app.config import get_settings
from app.core.metrics import TASK_SEARCH_CACHE_LOOKUPS_TOTAL
from app.core.redis_client import get_redis_client
from app.schemas.task import TaskListResponse, TaskSearchRequest

logger = logging.getLogger(__name__)

TASK_SEARCH_KEY_PREFIX = "tasks:search:"


def build_search_cache_key(
    project_versions: list[tuple[uuid.UUID, int]], search_request: TaskSearchRequest
) -> str:
    cache_scope = {
        "projects": [
            [str(project_id), task_version] for project_id, task_version in project_versions
        ],
        "filters": search_request.model_dump(mode="json", exclude={"project_id"}),
    }
    serialized_scope = json.dumps(cache_scope, sort_keys=True, separators=(",", ":"))
    return TASK_SEARCH_KEY_PREFIX + hashlib.sha256(serialized_scope.encode()).hexdigest()


def read_cached_search(cache_key: str) -> TaskListResponse | None:
    try:
        cached_value = get_redis_client().get(cache_key)
    except RedisError:
        logger.warning("Task search cache read failed for %s", cache_key)
        TASK_SEARCH_CACHE_LOOKUPS_TOTAL.labels("error").inc()
        return None
    if cached_value is None:
        TASK_SEARCH_CACHE_LOOKUPS_TOTAL.labels("miss").inc()
        return None
    TASK_SEARCH_CACHE_LOOKUPS_TOTAL.labels("hit").inc()
    return TaskListResponse.model_validate_json(cached_value)


def write_cached_search(cache_key: str, search_response: TaskListResponse) -> None:
    try:
        get_redis_client().set(
            cache_key,
            search_response.model_dump_json(),
            ex=get_settings().task_search_cache_ttl_seconds,
        )
    except RedisError:
        logger.warning("Task search cache write failed for %s", cache_key)
