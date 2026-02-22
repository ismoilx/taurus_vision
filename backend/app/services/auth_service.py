"""
Taurus Vision — Authentication Service

Autentifikatsiya va foydalanuvchi boshqaruvi uchun barcha biznes logikasi.

JAVOBGARLIK:
    - Foydalanuvchi login/logout
    - Token yaratish va yangilash
    - Foydalanuvchi CRUD (ADMIN huquqi bilan)
    - Parol o'zgartirish

QOIDA:
    - DB bilan muloqot faqat UserRepository orqali
    - Security operatsiyalari security.py orqali
    - Endpoint lar bu servisni chaqiradi, to'g'ridan-to'g'ri DB emas
"""

import logging
from datetime import timezone, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    PasswordChangeRequest,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    get_token_expires_in,
)
from app.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    EntityNotFoundError,
    EntityAlreadyExistsError,
    BusinessRuleViolationError,
)

logger = logging.getLogger(__name__)


class AuthService:
    """
    Autentifikatsiya va foydalanuvchi boshqaruvi servisi.

    Args:
        db: AsyncSession (FastAPI Depends orqali keladi)

    Usage:
        service = AuthService(db)
        token_response = await service.login(login_data)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = UserRepository(db)

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    async def login(self, login_data: LoginRequest) -> TokenResponse:
        """
        Foydalanuvchini tizimga kiritish.

        Jarayon:
            1. Email yoki username bo'yicha foydalanuvchini topish
            2. Parolni tekshirish (bcrypt verify)
            3. Aktiv holatini tekshirish
            4. Access va refresh token yaratish
            5. Refresh token hashini DB ga saqlash
            6. last_login_at ni yangilash

        Args:
            login_data: Email/username + parol

        Returns:
            TokenResponse (access_token, refresh_token, user ma'lumotlari)

        Raises:
            AuthenticationError: Noto'g'ri hisob ma'lumotlari yoki bloklangan hisob
        """
        # 1. Foydalanuvchini topish
        user: Optional[User] = None

        if login_data.email:
            user = await self._repo.get_by_email(login_data.email)
        elif login_data.username:
            user = await self._repo.get_by_username(login_data.username)

        # 2. Tekshirish — xato tafsilotlarini ochmaymiz (xavfsizlik uchun)
        if not user or not verify_password(login_data.password, user.hashed_password):
            logger.warning(
                "Failed login attempt",
                extra={
                    "identifier": login_data.email or login_data.username,
                    "reason": "invalid_credentials",
                },
            )
            raise AuthenticationError(
                message="Email/username yoki parol noto'g'ri."
            )

        # 3. Aktiv holat tekshiruvi
        if not user.is_active:
            logger.warning(
                f"Login attempt by inactive user id={user.id}"
            )
            raise AuthenticationError(
                message="Hisobingiz bloklangan. Administrator bilan bog'laning."
            )

        # 4. Tokenlar yaratish
        access_token  = create_access_token(user_id=user.id, role=user.role.value)
        refresh_token = create_refresh_token(user_id=user.id, role=user.role.value)

        # 5. Refresh token hashini saqlash
        await self._repo.save_refresh_token_hash(user.id, hash_token(refresh_token))

        # 6. Login vaqtini yangilash
        await self._repo.update_last_login(user.id)

        await self.db.commit()

        logger.info(
            "User logged in",
            extra={
                "user_id":  user.id,
                "username": user.username,
                "role":     user.role.value,
            },
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=get_token_expires_in(),
            user=UserResponse.model_validate(user),
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh token orqali yangi access token olish.

        Jarayon:
            1. Refresh token ni decode qilish va tekshirish
            2. Token turi "refresh" ekanligini tekshirish
            3. Foydalanuvchini DB dan olish
            4. DB dagi hash bilan solishtirish
            5. Yangi token juftligini yaratish

        Args:
            refresh_token: Oldingi login da olingan refresh token

        Returns:
            Yangi TokenResponse

        Raises:
            AuthenticationError: Noto'g'ri yoki muddati tugagan refresh token
        """
        # 1. Token decode
        try:
            payload = decode_token(refresh_token)
        except AuthenticationError:
            raise AuthenticationError(
                message="Refresh token noto'g'ri yoki muddati tugagan."
            )

        # 2. Token turi tekshiruvi
        if payload.get("type") != "refresh":
            raise AuthenticationError(
                message="Refresh token talab qilinadi, access token berildi."
            )

        # 3. Foydalanuvchini DB dan olish
        user_id = int(payload["sub"])
        user = await self._repo.get_by_id(user_id)

        if not user or not user.is_active:
            raise AuthenticationError(
                message="Foydalanuvchi topilmadi yoki bloklangan."
            )

        # 4. Hash mosligini tekshirish
        # Bu tekshiruv logout dan keyin eski tokenlar ishlamasligini ta'minlaydi
        stored_hash = user.refresh_token_hash
        if not stored_hash or stored_hash != hash_token(refresh_token):
            logger.warning(
                f"Refresh token hash mismatch for user id={user.id} "
                "(possible token reuse attack)"
            )
            raise AuthenticationError(
                message="Refresh token yaroqsiz. Qayta login qiling."
            )

        # 5. Yangi token juftligi
        new_access_token  = create_access_token(user_id=user.id, role=user.role.value)
        new_refresh_token = create_refresh_token(user_id=user.id, role=user.role.value)

        # Eski refresh tokenni yangi bilan almashtirish (token rotation)
        await self._repo.save_refresh_token_hash(user.id, hash_token(new_refresh_token))
        await self.db.commit()

        logger.debug(f"Token refreshed for user id={user.id}")

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=get_token_expires_in(),
            user=UserResponse.model_validate(user),
        )

    async def logout(self, user_id: int) -> None:
        """
        Foydalanuvchini tizimdan chiqarish.

        Refresh token hashini o'chirish orqali barcha sessiyalarni bekor qiladi.
        Access token muddati tugaguncha texnik jihatdan valid bo'lib qoladi
        (bu stateless JWT ning o'ziga xos xususiyati).

        Args:
            user_id: Tizimdan chiqayotgan foydalanuvchi ID
        """
        await self._repo.save_refresh_token_hash(user_id, None)
        await self.db.commit()
        logger.info(f"User id={user_id} logged out")

    # =========================================================================
    # USER MANAGEMENT (ADMIN only)
    # =========================================================================

    async def create_user(
        self,
        user_data: UserCreate,
        created_by: User,
    ) -> User:
        """
        Yangi foydalanuvchi yaratish.

        Faqat ADMIN roli bilan bajariladigan operatsiya.

        Args:
            user_data:  Yangi foydalanuvchi ma'lumotlari
            created_by: Bu amalni bajaruvchi foydalanuvchi (huquq tekshiruvi uchun)

        Returns:
            Yaratilgan User instance

        Raises:
            PermissionDeniedError:    Yaratuvchi ADMIN emas
            EntityAlreadyExistsError: Email yoki username allaqachon mavjud
        """
        # Huquq tekshiruvi
        if not created_by.is_admin:
            raise PermissionDeniedError(
                message="Yangi foydalanuvchi yaratish faqat ADMIN uchun mumkin.",
                details={"your_role": created_by.role.value},
            )

        # Uniqueness tekshiruvi
        if await self._repo.get_by_email(user_data.email):
            raise EntityAlreadyExistsError(
                message="Bu email bilan foydalanuvchi allaqachon mavjud.",
                details={"email": user_data.email},
            )

        if await self._repo.get_by_username(user_data.username):
            raise EntityAlreadyExistsError(
                message="Bu username allaqachon band.",
                details={"username": user_data.username},
            )

        # User yaratish
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hash_password(user_data.password),
            role=user_data.role,
            is_active=True,
        )

        created = await self._repo.create(new_user)
        await self.db.commit()

        logger.info(
            "New user created",
            extra={
                "new_user_id":  created.id,
                "username":     created.username,
                "role":         created.role.value,
                "created_by":   created_by.id,
            },
        )

        return created

    async def update_user(
        self,
        user_id: int,
        update_data: UserUpdate,
        updated_by: User,
    ) -> User:
        """
        Foydalanuvchi ma'lumotlarini yangilash.

        ADMIN: istalgan foydalanuvchini yangilay oladi.
        Oddiy foydalanuvchi: faqat o'zini yangilay oladi (full_name).

        Args:
            user_id:     Yangilanadigan foydalanuvchi ID
            update_data: Yangi ma'lumotlar
            updated_by:  Amal bajaruvchi foydalanuvchi

        Returns:
            Yangilangan User

        Raises:
            PermissionDeniedError: Ruxsat yo'q
            EntityNotFoundError:   Foydalanuvchi topilmadi
        """
        # Huquq tekshiruvi
        if not updated_by.is_admin and updated_by.id != user_id:
            raise PermissionDeniedError(
                message="Boshqa foydalanuvchini faqat ADMIN yangilay oladi.",
            )

        # ADMIN bo'lmagan foydalanuvchi role yoki is_active ni o'zgartira olmaydi
        if not updated_by.is_admin:
            if update_data.role is not None:
                raise PermissionDeniedError(
                    message="Rolni faqat ADMIN o'zgartira oladi.",
                )
            if update_data.is_active is not None:
                raise PermissionDeniedError(
                    message="Aktiv holatni faqat ADMIN o'zgartira oladi.",
                )

        updated = await self._repo.update_profile(
            user_id=user_id,
            full_name=update_data.full_name,
            role=update_data.role,
            is_active=update_data.is_active,
        )

        if not updated:
            raise EntityNotFoundError(entity="User", identifier=user_id)

        await self.db.commit()

        logger.info(
            f"User id={user_id} updated by user id={updated_by.id}"
        )

        return updated

    async def change_password(
        self,
        user_id: int,
        data: PasswordChangeRequest,
        requesting_user: User,
    ) -> None:
        """
        Foydalanuvchi parolini o'zgartirish.

        Joriy parol talab qilinadi (foydalanuvchi o'zi uchun).
        ADMIN boshqa foydalanuvchi parolini o'zgartirsa ham
        joriy parolni bilishi kerak.

        Args:
            user_id:          Paroli o'zgartirilayotgan foydalanuvchi ID
            data:             Joriy va yangi parol
            requesting_user:  So'rov yuboruvchi foydalanuvchi

        Raises:
            PermissionDeniedError: Boshqa foydalanuvchi paroli (ADMIN emas)
            AuthenticationError:   Joriy parol noto'g'ri
            EntityNotFoundError:   Foydalanuvchi topilmadi
        """
        # Foydalanuvchi faqat o'z parolini o'zgartira oladi (ADMIN istisno)
        if requesting_user.id != user_id and not requesting_user.is_admin:
            raise PermissionDeniedError(
                message="Faqat o'z parolingizni o'zgartira olasiz."
            )

        # Foydalanuvchini topish
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(entity="User", identifier=user_id)

        # Joriy parolni tekshirish
        if not verify_password(data.current_password, user.hashed_password):
            raise AuthenticationError(
                message="Joriy parol noto'g'ri."
            )

        # Yangi parol joriy paroldan farqli bo'lishi kerak
        if verify_password(data.new_password, user.hashed_password):
            raise BusinessRuleViolationError(
                message="Yangi parol joriy paroldan farqli bo'lishi kerak."
            )

        # Parolni yangilash
        await self._repo.update_password(user_id, hash_password(data.new_password))
        await self.db.commit()

        logger.info(f"Password changed for user id={user_id}")

    # =========================================================================
    # QUERY
    # =========================================================================

    async def get_user_by_id(self, user_id: int) -> User:
        """
        ID bo'yicha foydalanuvchini olish.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            User instance

        Raises:
            EntityNotFoundError: Foydalanuvchi topilmadi
        """
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise EntityNotFoundError(entity="User", identifier=user_id)
        return user

    async def get_all_users(
        self,
        requesting_user: User,
        skip: int = 0,
        limit: int = 100,
        only_active: bool = False,
    ) -> tuple[list[User], int]:
        """
        Barcha foydalanuvchilar ro'yxatini olish (ADMIN only).

        Args:
            requesting_user: So'rov yuboruvchi (ADMIN tekshiruvi uchun)
            skip:            Sahifalash offseti
            limit:           Sahifa hajmi
            only_active:     Faqat faol foydalanuvchilar

        Returns:
            (users list, total count)

        Raises:
            PermissionDeniedError: ADMIN emas
        """
        if not requesting_user.is_admin:
            raise PermissionDeniedError(
                message="Foydalanuvchilar ro'yxatini faqat ADMIN ko'ra oladi."
            )

        users = list(await self._repo.get_all(
            skip=skip,
            limit=limit,
            only_active=only_active,
        ))
        total = await self._repo.count(only_active=only_active)

        return users, total