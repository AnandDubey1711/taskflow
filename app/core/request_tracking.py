import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.core.logging_config import request_id_context
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

logger = logging.getLogger("taskflow.request")

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")
UNMATCHED_ROUTE = "unmatched"


def resolve_request_id(request: Request) -> str:
    incoming_request_id = request.headers.get(REQUEST_ID_HEADER, "")
    if REQUEST_ID_PATTERN.fullmatch(incoming_request_id):
        return incoming_request_id
    return uuid.uuid4().hex


def resolve_route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", UNMATCHED_ROUTE)


def record_request(request: Request, status_code: int, started_at: float) -> None:
    duration_seconds = time.perf_counter() - started_at
    route_template = resolve_route_template(request)
    HTTP_REQUESTS_TOTAL.labels(request.method, route_template, str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(request.method, route_template).observe(duration_seconds)
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "route": route_template,
            "status": status_code,
            "duration_ms": round(duration_seconds * 1000, 2),
        },
    )


async def track_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = resolve_request_id(request)
    request_id_token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed")
            record_request(request, 500, started_at)
            raise
        record_request(request, response.status_code, started_at)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        request_id_context.reset(request_id_token)
