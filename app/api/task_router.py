from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.dependencies import (
    CurrentProjectMember,
    CurrentProjectTask,
    CurrentUser,
    DbSession,
)
from app.schemas.task import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskSearchRequest,
    TaskUpdateRequest,
)
from app.services import task_service

router = APIRouter(tags=["tasks"])


@router.post(
    "/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskResponse
)
def create_task(
    create_request: TaskCreateRequest, project_member: CurrentProjectMember, db: DbSession
) -> TaskResponse:
    task = task_service.create_task(db, project_member, create_request)
    return TaskResponse.from_task(task)


@router.get("/projects/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def get_task(task: CurrentProjectTask) -> TaskResponse:
    return TaskResponse.from_task(task)


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    update_request: TaskUpdateRequest,
    task: CurrentProjectTask,
    project_member: CurrentProjectMember,
    db: DbSession,
) -> TaskResponse:
    updated_task = task_service.update_task(db, project_member, task, update_request)
    return TaskResponse.from_task(updated_task)


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task: CurrentProjectTask, db: DbSession) -> None:
    task_service.delete_task(db, task)


@router.get("/tasks", response_model=TaskListResponse)
def search_tasks(
    search_request: Annotated[TaskSearchRequest, Query()],
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
) -> TaskListResponse:
    search_response, is_cache_hit = task_service.search_tasks(db, current_user.id, search_request)
    response.headers["X-Cache"] = "HIT" if is_cache_hit else "MISS"
    return search_response
