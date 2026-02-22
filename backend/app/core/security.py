"""
Taurus Vision — Security Utilities

JWT token yaratish/tekshirish va parol hashing funksiyalari.

PAROL HASHING:
    bcrypt to'g'ridan-to'g'ri (passlib ishlatilmaydi — versiya muammosi).
    Cost factor: 12.

JWT TOKENS:
    Access token:  qisqa muddatli (60 daqiqa), stateless
    Refresh token: uzoq muddatli (7 kun), DB da hash saqlanadi
    Algoritm:      HS256
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# bcrypt cost factor
_BCRYPT_ROUNDS = 12


# =============================================================================
# PASSWORD FUNCTIONS
# =============================================================================

def hash_password(plain_password: str) -> str:
    """
    Parolni bcrypt bilan hash qilish.

    Args:
        plain_password: Foydalanuvchi kiritgan parol

    Returns:
        bcrypt hash string ($2b$ prefiksi bilan)
    """
    password_bytes = plain_password.encode("utf-8")
    salt           = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed         = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Parolni bcrypt hash bilan solishtirish.

    Constant-time comparison — timing attack ga qarshi himoyalangan.

    Args:
        plain_password:  Foydalanuvchi kiritgan parol
        hashed_password: DB da saqlangan bcrypt hash

    Returns:
        True — parol to'g'ri, False — noto'g'ri
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# =============================================================================
# TOKEN FUNCTIONS
# =============================================================================

def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    JWT access token yaratish.

    Args:
        user_id:       Foydalanuvchi ID
        role:          UserRole qiymati (masalan: "admin")
        expires_delta: Token amal qilish muddati

    Returns:
        Imzolangan JWT string
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub":  str(user_id),
        "type": "access",
        "role": role,
        "exp":  expire,
        "iat":  datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: int, role: str) -> str:
    """
    JWT refresh token yaratish.

    Args:
        user_id: Foydalanuvchi ID
        role:    UserRole qiymati

    Returns:
        Imzolangan JWT string
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload: dict[str, Any] = {
        "sub":  str(user_id),
        "type": "refresh",
        "role": role,
        "exp":  expire,
        "iat":  datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    JWT tokenni tekshirish va payload ni qaytarish.

    Args:
        token: JWT string

    Returns:
        Token payload dict

    Raises:
        AuthenticationError: Token noto'g'ri yoki muddati tugagan
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(
            message="Token muddati tugagan. Qayta login qiling."
        )
    except jwt.InvalidTokenError as exc:
        logger.warning(f"Invalid token: {exc}")
        raise AuthenticationError(
            message="Noto'g'ri yoki buzilgan token."
        )


def hash_token(token: str) -> str:
    """
    Token ni SHA-256 bilan hash qilish (DB da saqlash uchun).

    Args:
        token: Xom JWT string

    Returns:
        64 belgilik hex digest
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_token_expires_in() -> int:
    """Access token amal qilish muddatini sekundlarda qaytarish."""
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60