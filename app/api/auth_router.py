from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, CurrentUserSession, DbSession
from app.models import User
from app.schemas.user import UserLoginRequest, UserResponse, UserSignupRequest
from app.schemas.user_session import UserSessionResponse
from app.services import user_service, user_session_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def signup_user(signup_request: UserSignupRequest, db: DbSession) -> User:
    return user_service.create_user(db, signup_request)


@router.post("/login", response_model=UserSessionResponse)
def login_user(login_request: UserLoginRequest, db: DbSession) -> UserSessionResponse:
    user = user_service.authenticate_user(db, login_request.email, login_request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = user_session_service.create_user_session(db, user)
    return UserSessionResponse(token=token, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(user_session: CurrentUserSession, db: DbSession) -> None:
    user_session_service.delete_user_session(db, user_session)


@router.get("/me", response_model=UserResponse)
def get_authenticated_user(current_user: CurrentUser) -> User:
    return current_user
