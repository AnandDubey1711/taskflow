import logging

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.dependencies import DbSession
from app.core.redis_client import get_redis_client
from app.schemas.health import ComponentStatus, HealthResponse, HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ops"])


def check_database(db: DbSession) -> ComponentStatus:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return ComponentStatus.DOWN
    return ComponentStatus.OK


def check_redis() -> ComponentStatus:
    try:
        get_redis_client().ping()
    except RedisError:
        logger.warning("Redis health check failed")
        return ComponentStatus.DOWN
    return ComponentStatus.OK


@router.get("/health", response_model=HealthResponse)
def get_health(response: Response, db: DbSession) -> HealthResponse:
    database_status = check_database(db)
    redis_status = check_redis()
    if database_status == ComponentStatus.DOWN:
        overall_status = HealthStatus.DOWN
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif redis_status == ComponentStatus.DOWN:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.OK
    return HealthResponse(status=overall_status, database=database_status, redis=redis_status)


@router.get("/metrics")
def get_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
