import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import get_settings
from app.core.exceptions import Unauthorized

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_rehash_needed = _hasher.check_needs_rehash


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, stored: str) -> bool:
    try:
        return _hasher.verify(stored, raw)
    except VerificationError:
        return False


def password_needs_rehash(stored: str) -> bool:
    try:
        return _rehash_needed(stored)
    except Exception:
        return False


def _encode(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    settings = get_settings()
    expire_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    token = _encode(
        {
            "sub": user_id,
            "role": role,
            "type": "access",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int(expire_at.timestamp()),
        }
    )
    return token, settings.access_token_minutes * 60


def create_refresh_token() -> tuple[str, str, datetime]:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    return raw, digest_token(raw), expires_at


def digest_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise Unauthorized("令牌无效或已过期") from exc
    if payload.get("type") != "access":
        raise Unauthorized("令牌类型不正确")
    return payload
