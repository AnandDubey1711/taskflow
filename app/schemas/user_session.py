from pydantic import BaseModel

from app.schemas.user import UserResponse


class UserSessionResponse(BaseModel):
    token: str
    user: UserResponse
