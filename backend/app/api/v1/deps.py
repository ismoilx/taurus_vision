"""
Taurus Vision — FastAPI Dependencies

Barcha endpointlar uchun umumiy dependency lar.

FOYDALANISH:
    from app.api.v1.deps import get_current_user, require_admin

    @router.get("/protected")
    async def my_endpoint(
        current_user: User = Depends(get_current_user),
    ):
        ...

    @router.delete("/admin-only")
    async def admin_endpoint(
        current_user: User = Depends(require_admin),
    ):
        ...

DEPENDENCY CHAIN:
    require_admin
        └── require_manager
                └── get_current_active_user
                        └── get_current_user
                                └── oauth2_scheme (Bearer token)
                                └── get_db (DB session)
"""

import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

# =============================================================================
# OAuth2 SCHEME
# =============================================================================

# tokenUrl — bu Swagger UI da "Authorize" tugmasi ishlaydigan endpoint
# Frontend uchun emas — faqat docs/swagger uchun
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    scheme_name="JWT Bearer Token",
    description="JWT access token. Login: POST /api/v1/auth/login",
)

# =============================================================================
# CORE DEPENDENCY
# =============================================================================

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT tokendan joriy foydalanuvchini olish.

    Har bir himoyalangan endpoint da ishlatiladi.
    Token muddati, imzosi va turi tekshiriladi.

    Args:
        token: Authorization: Bearer <token> headerdan olinadi
        db:    Async DB session

    Returns:
        Autentifikatsiya qilingan User instance

    Raises:
        HTTPException 401: Token yo'q, noto'g'ri yoki muddati tugagan
        HTTPException 401: Foydalanuvchi DB da topilmadi
    """
    # Token decode va tekshirish
    payload = decode_token(token)

    # Token turi tekshiruvi — refresh token bilan API ga kirish mumkin emas
    if payload.get("type") != "access":
        raise AuthenticationError(
            message="Access token talab qilinadi."
        )

    # User ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError(message="Token payload noto'g'ri.")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise AuthenticationError(message="Token payload noto'g'ri.")

    # DB dan foydalanuvchini olish
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        logger.warning(f"Token valid but user id={user_id} not found in DB")
        raise AuthenticationError(
            message="Foydalanuvchi topilmadi."
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Foydalanuvchi aktiv ekanligini tekshirish.

    get_current_user dan keyin chaqiriladi.
    Bloklangan foydalanuvchilar bu yerda to'xtatiladi.

    Args:
        current_user: get_current_user dan kelgan User

    Returns:
        Aktiv User

    Raises:
        HTTPException 401: Foydalanuvchi deaktivlashtirilgan
    """
    if not current_user.is_active:
        raise AuthenticationError(
            message="Hisobingiz bloklangan. Administrator bilan bog'laning."
        )
    return current_user


# =============================================================================
# ROLE-BASED DEPENDENCIES
# =============================================================================

async def require_manager(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    MANAGER yoki ADMIN roli talab qilinadi.

    O'zgartirish operatsiyalari uchun: jonivor qo'shish/tahrirlash,
    alert boshqarish va boshqalar.

    Args:
        current_user: get_current_active_user dan kelgan User

    Returns:
        MANAGER yoki ADMIN User

    Raises:
        HTTPException 403: Foydalanuvchi VIEWER
    """
    if not current_user.is_manager:
        raise PermissionDeniedError(
            message="Bu amal uchun MANAGER yoki ADMIN roli kerak.",
            details={"your_role": current_user.role.value},
        )
    return current_user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Faqat ADMIN roli talab qilinadi.

    Tizim sozlamalari, foydalanuvchi boshqaruvi va boshqalar.

    Args:
        current_user: get_current_active_user dan kelgan User

    Returns:
        ADMIN User

    Raises:
        HTTPException 403: Foydalanuvchi ADMIN emas
    """
    if not current_user.is_admin:
        raise PermissionDeniedError(
            message="Bu amal uchun faqat ADMIN roli kerak.",
            details={"your_role": current_user.role.value},
        )
    return current_user


# =============================================================================
# TYPE ALIASES (kodni yanada toza qilish uchun)
# =============================================================================

CurrentUser        = Annotated[User, Depends(get_current_active_user)]
CurrentManager     = Annotated[User, Depends(require_manager)]
CurrentAdmin       = Annotated[User, Depends(require_admin)]