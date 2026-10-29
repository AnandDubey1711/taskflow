from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import EmailAlreadyRegisteredError
from app.core.security import get_dummy_password_hash, hash_password, verify_password
from app.models import User
from app.schemas.user import UserSignupRequest


def create_user(db: Session, signup_request: UserSignupRequest) -> User:
    user = User(
        email=signup_request.email,
        username=signup_request.username,
        password_hash=hash_password(signup_request.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise EmailAlreadyRegisteredError from error
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, get_dummy_password_hash())
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
