from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import (
    auth_router,
    notification_router,
    ops_router,
    project_member_router,
    project_router,
    task_router,
)
from app.core.errors import DomainError
from app.core.logging_config import configure_logging
from app.core.request_tracking import track_request

configure_logging()

app = FastAPI(title="TaskFlow")

app.middleware("http")(track_request)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    safe_errors = [
        {"loc": detail["loc"], "msg": detail["msg"], "type": detail["type"]}
        for detail in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": safe_errors}
    )


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


app.include_router(ops_router.router)
app.include_router(auth_router.router)
app.include_router(project_router.router)
app.include_router(project_member_router.router)
app.include_router(task_router.router)
app.include_router(notification_router.router)
