from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession
from app.services.user_session_service import resolve_user_session

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def raise_unauthorized(detail: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_session(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserSession:
    if credentials is None:
        raise_unauthorized("Not authenticated")
    user_session = resolve_user_session(db, credentials.credentials)
    if user_session is None:
        raise_unauthorized("Invalid or expired session")
    return user_session


CurrentUserSession = Annotated[UserSession, Depends(get_current_user_session)]


def get_current_user(user_session: CurrentUserSession) -> User:
    return user_session.user


CurrentUser = Annotated[User, Depends(get_current_user)]
