"""Mots de passe, sessions opaques et contrôle du rôle."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ACCESS_DENIED, UNAUTHENTICATED, ApiError
from app.db.models import AppSession, AppUser, UserRole
from app.modules.audit.service import record_event


IDLE_LIMIT = timedelta(minutes=30)
ABSOLUTE_LIMIT = timedelta(hours=8)
LOCK_TIME = timedelta(minutes=15)
SALT_BYTES = 16


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


_DUMMY_HASH = hash_password("nonexistent-account")


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt" or int(n) > 2**16 or int(r) > 8 or int(p) > 2:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Actor:
    user_id: str
    username: str
    roles: frozenset[str]
    session: AppSession


def authenticate(db: Session, username: str, password: str, correlation_id: str) -> tuple[str, str, Actor]:
    now = datetime.now(timezone.utc)
    user = db.scalar(select(AppUser).where(AppUser.username == username).with_for_update())
    password_ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    locked = bool(user and user.locked_until and _utc(user.locked_until) > now)
    if not user or not user.is_active or not password_ok or locked:
        if user and not locked:
            user.failed_attempts += 1
            if user.failed_attempts >= 5:
                user.locked_until = now + LOCK_TIME
                user.failed_attempts = 0
        record_event(db, actor_user_id=user.id if user else None, action="auth.login",
                     resource_type="session", resource_id=None, outcome="denied", correlation_id=correlation_id)
        db.commit()
        raise ApiError(*UNAUTHENTICATED)
    user.failed_attempts = 0
    user.locked_until = None
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    session = AppSession(token_hash=token_hash(session_token), user_id=user.id,
                         csrf_hash=token_hash(csrf_token), created_at=now,
                         last_seen_at=now, expires_at=now + ABSOLUTE_LIMIT)
    db.add(session)
    roles = frozenset(db.scalars(select(UserRole.role_name).where(UserRole.user_id == user.id)))
    record_event(db, actor_user_id=user.id, action="auth.login", resource_type="session",
                 resource_id=None, outcome="allowed", correlation_id=correlation_id)
    db.commit()
    return session_token, csrf_token, Actor(user.id, user.username, roles, session)


def current_actor(db: Session, request: Request) -> Actor:
    token = request.cookies.get("app_session")
    if not token or len(token) > 128:
        raise ApiError(*UNAUTHENTICATED)
    session = db.get(AppSession, token_hash(token))
    now = datetime.now(timezone.utc)
    if not session or _utc(session.expires_at) <= now or _utc(session.last_seen_at) + IDLE_LIMIT <= now:
        raise ApiError(*UNAUTHENTICATED)
    user = db.get(AppUser, session.user_id)
    if not user or not user.is_active:
        raise ApiError(*UNAUTHENTICATED)
    session.last_seen_at = now
    roles = frozenset(db.scalars(select(UserRole.role_name).where(UserRole.user_id == user.id)))
    return Actor(user.id, user.username, roles, session)


def require_role(actor: Actor, allowed: set[str]) -> None:
    if not actor.roles.intersection(allowed):
        raise ApiError(*ACCESS_DENIED)


def require_csrf(request: Request, actor: Actor, app_origin: str) -> None:
    origin = request.headers.get("origin")
    supplied = request.headers.get("x-csrf-token", "")
    if origin != app_origin or not supplied or len(supplied) > 128:
        raise ApiError(*ACCESS_DENIED)
    if not hmac.compare_digest(token_hash(supplied), actor.session.csrf_hash):
        raise ApiError(*ACCESS_DENIED)
