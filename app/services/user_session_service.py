from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import generate_session_token, hash_session_token
from app.models import User, UserSession
from app.models.base import utc_now


def create_user_session(db: Session, user: User) -> str:
    token = generate_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_session_token(token)))
    db.commit()
    return token


def is_user_session_expired(user_session: UserSession, now: datetime) -> bool:
    settings = get_settings()
    is_idle_too_long = now - user_session.last_seen_at > timedelta(
        hours=settings.session_idle_hours
    )
    is_too_old = now - user_session.created_at > timedelta(days=settings.session_max_days)
    return is_idle_too_long or is_too_old


def resolve_user_session(db: Session, token: str) -> UserSession | None:
    user_session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    if user_session is None:
        return None
    now = utc_now()
    if is_user_session_expired(user_session, now):
        delete_user_session(db, user_session)
        return None
    touch_interval = timedelta(minutes=get_settings().session_touch_minutes)
    if now - user_session.last_seen_at > touch_interval:
        user_session.last_seen_at = now
        db.commit()
    return user_session


def delete_user_session(db: Session, user_session: UserSession) -> None:
    db.delete(user_session)
    db.commit()


def delete_expired_user_sessions(db: Session) -> int:
    settings = get_settings()
    now = utc_now()
    deleted_session_ids = db.scalars(
        delete(UserSession)
        .where(
            or_(
                UserSession.last_seen_at < now - timedelta(hours=settings.session_idle_hours),
                UserSession.created_at < now - timedelta(days=settings.session_max_days),
            )
        )
        .returning(UserSession.id)
        .execution_options(synchronize_session=False)
    ).all()
    db.commit()
    return len(deleted_session_ids)
