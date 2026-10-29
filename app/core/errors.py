from fastapi import status


class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Request could not be processed"


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT


class ForbiddenError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN


class UnprocessableError(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class EmailAlreadyRegisteredError(ConflictError):
    detail = "Email already registered"


class UserNotFoundError(NotFoundError):
    detail = "User not found"


class ProjectNotFoundError(NotFoundError):
    detail = "Project not found"


class ProjectKeyAlreadyExistsError(ConflictError):
    detail = "Project key already in use"


class ProjectOwnerRequiredError(ForbiddenError):
    detail = "Only the project owner can do this"


class ProjectMemberNotFoundError(NotFoundError):
    detail = "Project member not found"


class ProjectMemberAlreadyExistsError(ConflictError):
    detail = "User is already a project member"


class ProjectOwnerRemovalError(ConflictError):
    detail = "The project owner cannot be removed"


class TaskNotFoundError(NotFoundError):
    detail = "Task not found"


class TaskAssigneeNotMemberError(UnprocessableError):
    detail = "Assignee must be a member of the project"
