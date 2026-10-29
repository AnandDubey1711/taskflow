from fastapi import APIRouter, status

from app.core.dependencies import CurrentProjectMember, CurrentProjectTask, DbSession
from app.schemas.task import TaskCreateRequest, TaskResponse, TaskUpdateRequest
from app.services import task_service

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
def create_task(
    create_request: TaskCreateRequest, project_member: CurrentProjectMember, db: DbSession
) -> TaskResponse:
    task = task_service.create_task(db, project_member, create_request)
    return TaskResponse.from_task(task)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task: CurrentProjectTask) -> TaskResponse:
    return TaskResponse.from_task(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    update_request: TaskUpdateRequest,
    task: CurrentProjectTask,
    project_member: CurrentProjectMember,
    db: DbSession,
) -> TaskResponse:
    updated_task = task_service.update_task(db, project_member, task, update_request)
    return TaskResponse.from_task(updated_task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task: CurrentProjectTask, db: DbSession) -> None:
    task_service.delete_task(db, task)
