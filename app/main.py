from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import auth_router, ops_router

app = FastAPI(title="TaskFlow")


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    safe_errors = [
        {"loc": detail["loc"], "msg": detail["msg"], "type": detail["type"]}
        for detail in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": safe_errors}
    )


app.include_router(ops_router.router)
app.include_router(auth_router.router)
