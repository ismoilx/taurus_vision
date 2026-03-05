"""
Taurus Vision — Authentication Endpoints

/api/v1/auth/ prefix ostida joylashgan barcha autentifikatsiya endpointlari.

ENDPOINTS:
    POST /auth/login          — Tizimga kirish (token olish)
    POST /auth/refresh        — Access tokenni yangilash
    POST /auth/logout         — Tizimdan chiqish
    GET  /auth/me             — Joriy foydalanuvchi ma'lumotlari
    PUT  /auth/me             — Profil yangilash
    POST /auth/change-password— Parol o'zgartirish
    GET  /auth/users          — Barcha foydalanuvchilar (ADMIN)
    POST /auth/users          — Yangi foydalanuvchi (ADMIN)
    GET  /auth/users/{id}     — Foydalanuvchi detail (ADMIN)
    PUT  /auth/users/{id}     — Foydalanuvchi yangilash (ADMIN)
    POST /auth/users/{id}/deactivate — Bloklash (ADMIN)
    POST /auth/users/{id}/activate   — Blokdan chiqarish (ADMIN)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import (
    get_current_active_user,
    require_admin,
    CurrentUser,
    CurrentAdmin,
)
from app.services.auth_service import AuthService
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserCreate,
    UserUpdate,
    UserResponse,
    PasswordChangeRequest,
    AdminPasswordResetRequest,
    AuditLogResponse,
    AuditLogListResponse,
)
from app.models.user import User
from app.models.audit_log import AuditLog
from sqlalchemy import select, func, desc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# PUBLIC ENDPOINTS (token talab qilinmaydi)
# =============================================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Tizimga kirish",
    description=(
        "Email yoki username + parol bilan login. "
        "Muvaffaqiyatli bo'lsa access_token va refresh_token qaytariladi."
    ),
)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Foydalanuvchini autentifikatsiya qilish.

    Args:
        login_data: Email/username va parol
        request:    HTTP request (IP va User-Agent olish uchun)
        db:         DB session

    Returns:
        JWT token juftligi va foydalanuvchi ma'lumotlari

    Raises:
        401: Noto'g'ri hisob ma'lumotlari, bloklangan yoki faol bo'lmagan hisob
    """
    ip         = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("user-agent")
    service    = AuthService(db)
    return await service.login(login_data, ip=ip, user_agent=user_agent)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Access tokenni yangilash",
    description=(
        "Refresh token orqali yangi access token va refresh token olish. "
        "Token rotation: har yangilashda refresh token ham o'zgaradi."
    ),
)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Yangi token juftligini olish.

    Args:
        refresh_data: Refresh token
        db:           DB session

    Returns:
        Yangi JWT token juftligi

    Raises:
        401: Noto'g'ri, muddati tugagan yoki qayta ishlatiladigan refresh token
    """
    service = AuthService(db)
    return await service.refresh_access_token(refresh_data.refresh_token)


# =============================================================================
# AUTHENTICATED ENDPOINTS (token kerak)
# =============================================================================

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Tizimdan chiqish",
    description=(
        "Joriy sessiyani tugatish. "
        "Refresh token bekor qilinadi — keyingi so'rovlarda yangi login kerak."
    ),
)
async def logout(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Foydalanuvchini tizimdan chiqarish.

    Args:
        current_user: Joriy autentifikatsiya qilingan foydalanuvchi
        db:           DB session
    """
    service = AuthService(db)
    await service.logout(current_user.id)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Joriy foydalanuvchi",
    description="Token egasining profil ma'lumotlarini olish.",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """
    Joriy foydalanuvchi ma'lumotlarini qaytarish.

    Args:
        current_user: Joriy autentifikatsiya qilingan foydalanuvchi

    Returns:
        UserResponse (parol va token hash kirmaydi)
    """
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Profilni yangilash",
    description=(
        "Joriy foydalanuvchi full_name ni yangilash. "
        "Role va is_active faqat ADMIN tomonidan o'zgartiriladi."
    ),
)
async def update_me(
    update_data: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Joriy foydalanuvchi profilini yangilash.

    Args:
        update_data:  Yangilash ma'lumotlari
        current_user: Joriy foydalanuvchi
        db:           DB session

    Returns:
        Yangilangan UserResponse
    """
    service = AuthService(db)
    updated = await service.update_user(
        user_id=current_user.id,
        update_data=update_data,
        updated_by=current_user,
    )
    return UserResponse.model_validate(updated)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Parolni o'zgartirish",
    description=(
        "Joriy parolni yangi parol bilan almashtirish. "
        "Parol o'zgarganda barcha sessiyalar bekor qilinadi."
    ),
)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Foydalanuvchi parolini o'zgartirish.

    Args:
        password_data: Joriy va yangi parol
        current_user:  Joriy foydalanuvchi
        db:            DB session

    Raises:
        401: Joriy parol noto'g'ri
        400: Yangi parol joriy paroldan farqsiz
    """
    service = AuthService(db)
    await service.change_password(
        user_id=current_user.id,
        data=password_data,
        requesting_user=current_user,
    )


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@router.get(
    "/users",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Barcha foydalanuvchilar (ADMIN)",
    description="Tizim foydalanuvchilari ro'yxati. Faqat ADMIN.",
)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    only_active: bool = False,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Barcha foydalanuvchilar ro'yxatini olish.

    Args:
        skip:         Sahifalash offseti
        limit:        Sahifa hajmi (max 100)
        only_active:  Faqat faol foydalanuvchilar
        current_user: ADMIN tekshiruvi uchun
        db:           DB session

    Returns:
        {items: [UserResponse], total: int, skip: int, limit: int}
    """
    limit = min(limit, 100)
    service = AuthService(db)
    users, total = await service.get_all_users(
        requesting_user=current_user,
        skip=skip,
        limit=limit,
        only_active=only_active,
    )
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "skip":  skip,
        "limit": limit,
    }


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi foydalanuvchi yaratish (ADMIN)",
    description=(
        "Tizimga yangi foydalanuvchi qo'shish. "
        "Faqat ADMIN bajara oladi."
    ),
)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Yangi foydalanuvchi yaratish.

    Args:
        user_data:    Yangi foydalanuvchi ma'lumotlari
        current_user: ADMIN tekshiruvi uchun
        db:           DB session

    Returns:
        Yaratilgan UserResponse

    Raises:
        409: Email yoki username allaqachon mavjud
        403: ADMIN emas
    """
    service = AuthService(db)
    new_user = await service.create_user(
        user_data=user_data,
        created_by=current_user,
    )
    return UserResponse.model_validate(new_user)


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Foydalanuvchi detail (ADMIN)",
)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Foydalanuvchi ma'lumotlarini olish.

    Args:
        user_id:      Ko'riladigan foydalanuvchi ID
        current_user: ADMIN tekshiruvi uchun
        db:           DB session

    Returns:
        UserResponse

    Raises:
        404: Foydalanuvchi topilmadi
    """
    service = AuthService(db)
    user = await service.get_user_by_id(user_id)
    return UserResponse.model_validate(user)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Foydalanuvchi yangilash (ADMIN)",
)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Foydalanuvchi ma'lumotlarini yangilash.

    Args:
        user_id:      Yangilanadigan foydalanuvchi ID
        update_data:  Yangi ma'lumotlar
        current_user: ADMIN tekshiruvi uchun
        db:           DB session

    Returns:
        Yangilangan UserResponse
    """
    service = AuthService(db)
    updated = await service.update_user(
        user_id=user_id,
        update_data=update_data,
        updated_by=current_user,
    )
    return UserResponse.model_validate(updated)


@router.post(
    "/users/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Foydalanuvchini bloklash (ADMIN)",
    description=(
        "Foydalanuvchini o'chirmasdan bloklash. "
        "Bloklangan foydalanuvchi login qila olmaydi."
    ),
)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Foydalanuvchini deaktivlashtirish.

    Args:
        user_id:      Bloklanadigan foydalanuvchi ID
        current_user: ADMIN tekshiruvi uchun
        db:           DB session

    Raises:
        400: O'zini bloklashga urinish
    """
    if user_id == current_user.id:
        from app.core.exceptions import BusinessRuleViolationError
        raise BusinessRuleViolationError(
            message="O'zingizni bloklay olmaysiz."
        )

    service = AuthService(db)
    await service.update_user(
        user_id=user_id,
        update_data=UserUpdate(is_active=False),
        updated_by=current_user,
    )


@router.post(
    "/users/{user_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Foydalanuvchini blokdan chiqarish (ADMIN)",
)
async def activate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Bloklangan foydalanuvchini qayta faollashtirish.

    Args:
        user_id:      Faollashtirilayotgan foydalanuvchi ID
        current_user: ADMIN tekshiruvi uchun
        db:           DB session
    """
    service = AuthService(db)
    await service.update_user(
        user_id=user_id,
        update_data=UserUpdate(is_active=True),
        updated_by=current_user,
    )

# =============================================================================
# ADMIN PASSWORD RESET
# =============================================================================

@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Foydalanuvchi parolini admin tomonidan tiklash (ADMIN)",
    description=(
        "Admin boshqa foydalanuvchi parolini joriy parolini bilmasdan tiklaydi. "
        "Admin o'z parolini bu endpoint orqali o'zgartira olmaydi."
    ),
)
async def admin_reset_password(
    user_id: int,
    data: AdminPasswordResetRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Admin tomonidan boshqa foydalanuvchi parolini tiklash.

    Args:
        user_id:      Paroli tiklanadigan foydalanuvchi ID
        data:         Yangi parol ma'lumotlari
        current_user: ADMIN tekshiruvi uchun
        db:           DB session
    """
    from app.core.exceptions import (
        EntityNotFoundError,
        PermissionDeniedError,
        BusinessRuleViolationError,
    )
    service = AuthService(db)
    try:
        await service.admin_reset_password(
            user_id=user_id,
            new_password=data.new_password,
            admin_user=current_user,
        )
    except EntityNotFoundError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except (PermissionDeniedError, BusinessRuleViolationError) as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# AUDIT LOG (ADMIN only)
# =============================================================================

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Xavfsizlik audit loglari (ADMIN)",
    description=(
        "Tizimda ro'y bergan barcha xavfsizlik voqealarini ko'rish. "
        "Filtr: event_type, severity, user_id, sana oralig'i."
    ),
)
async def get_audit_logs(
    page: int = 1,
    size: int = 50,
    event_type: str | None = None,
    severity: str | None = None,
    username: str | None = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    Sahifalangan audit log ro'yxati.

    Args:
        page:       Sahifa raqami (1 dan boshlanadi)
        size:       Sahifa hajmi (max 100)
        event_type: Voqea turi filtri (LOGIN_SUCCESS, LOGIN_FAILED, ...)
        severity:   Jiddiylik filtri (info, warning, critical)
        username:   Foydalanuvchi nomi bo'yicha filtr
        current_user: ADMIN tekshiruvi
        db:         DB session

    Returns:
        AuditLogListResponse — sahifalangan ro'yxat
    """
    size = min(size, 100)
    offset = (page - 1) * size

    # Asosiy query
    query = select(AuditLog).order_by(desc(AuditLog.occurred_at))

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if severity:
        query = query.where(AuditLog.severity == severity)
    if username:
        query = query.where(AuditLog.username.ilike(f"%{username}%"))

    # Total hisoblash
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Sahifalash
    query = query.offset(offset).limit(size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=max(1, -(-total // size)),  # ceiling division
    )