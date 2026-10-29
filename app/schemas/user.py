import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

BCRYPT_MAX_PASSWORD_BYTES = 72


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserSignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return normalize_email(email)

    @field_validator("username")
    @classmethod
    def strip_username(cls, username: str) -> str:
        stripped_username = username.strip()
        if not stripped_username:
            raise ValueError("username must not be blank")
        return stripped_username

    @field_validator("password")
    @classmethod
    def limit_password_bytes(cls, password: str) -> str:
        if len(password.encode()) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes")
        return password


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=BCRYPT_MAX_PASSWORD_BYTES)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return normalize_email(email)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    created_at: datetime
