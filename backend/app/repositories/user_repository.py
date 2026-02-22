"""
Taurus Vision — User Repository

Foydalanuvchilar bilan bog'liq barcha DB operatsiyalari.

QOIDA: Bu yerda faqat DB qo'ng'iroqlari — biznes logikasi yo'q.
Biznes logikasi AuthService da.
"""

import logging
from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class UserRepository:
    """
    User entity uchun barcha DB operatsiyalari.

    Args:
        db: AsyncSession (FastAPI Depends orqali keladi)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, user: User) -> User:
        """
        Yangi foydalanuvchini DB ga saqlash.

        DIQQAT: Uniqueness tekshiruvi Service da bajariladi —
        bu yerda faqat saqlash.

        Args:
            user: To'ldirilgan User ORM instance

        Returns:
            DB ga saqlangan User (id va timestamps bilan)

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
            logger.debug(f"[repo] Created user id={user.id} username={user.username}")
            return user
        except Exception as exc:
            logger.error(f"[repo] create user failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Foydalanuvchini saqlashda xato.",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — single
    # =========================================================================

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        ID bo'yicha foydalanuvchini olish.

        Args:
            user_id: Foydalanuvchi ID

        Returns:
            User instance yoki None

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_id({user_id}) failed: {exc}")
            raise DatabaseError(
                message=f"Foydalanuvchi id={user_id} ni olishda xato.",
                details={"error": str(exc)},
            ) from exc

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Email bo'yicha foydalanuvchini olish (case-insensitive).

        Login jarayonida ishlatiladi.

        Args:
            email: Foydalanuvchi email manzili

        Returns:
            User instance yoki None
        """
        try:
            result = await self.db.execute(
                select(User).where(
                    func.lower(User.email) == email.lower().strip()
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_email failed: {exc}")
            raise DatabaseError(
                message="Email bo'yicha qidirishda xato.",
                details={"error": str(exc)},
            ) from exc

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Username bo'yicha foydalanuvchini olish (case-insensitive).

        Args:
            username: Foydalanuvchi nomi

        Returns:
            User instance yoki None
        """
        try:
            result = await self.db.execute(
                select(User).where(
                    func.lower(User.username) == username.lower().strip()
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            logger.error(f"[repo] get_by_username failed: {exc}")
            raise DatabaseError(
                message="Username bo'yicha qidirishda xato.",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # READ — collection
    # =========================================================================

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        only_active: bool = False,
    ) -> Sequence[User]:
        """
        Barcha foydalanuvchilar ro'yxatini olish.

        Args:
            skip:        Sahifalash uchun offset
            limit:       Sahifa hajmi
            only_active: True = faqat faol foydalanuvchilar

        Returns:
            User instance lar ro'yxati
        """
        try:
            stmt = select(User)
            if only_active:
                stmt = stmt.where(User.is_active == True)  # noqa: E712
            stmt = stmt.order_by(User.id).offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as exc:
            logger.error(f"[repo] get_all users failed: {exc}")
            raise DatabaseError(
                message="Foydalanuvchilar ro'yxatini olishda xato.",
                details={"error": str(exc)},
            ) from exc

    async def count(self, only_active: bool = False) -> int:
        """
        Foydalanuvchilar sonini hisoblash.

        Args:
            only_active: True = faqat faol foydalanuvchilar

        Returns:
            Foydalanuvchilar soni
        """
        try:
            stmt = select(func.count()).select_from(User)
            if only_active:
                stmt = stmt.where(User.is_active == True)  # noqa: E712
            result = await self.db.execute(stmt)
            return result.scalar_one()
        except Exception as exc:
            logger.error(f"[repo] count users failed: {exc}")
            raise DatabaseError(
                message="Foydalanuvchilar sonini hisoblashda xato.",
                details={"error": str(exc)},
            ) from exc

    # =========================================================================
    # UPDATE — targeted (har bir operatsiya o'z vazifasiga ega)
    # =========================================================================

    async def save_refresh_token_hash(
        self,
        user_id: int,
        token_hash: Optional[str],
    ) -> None:
        """
        Refresh token hashini DB ga saqlash yoki o'chirish.

        Login da: token_hash = SHA-256(refresh_token)
        Logout da: token_hash = None

        Args:
            user_id:    Foydalanuvchi ID
            token_hash: Token hashi yoki None (logout)

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            user = await self.get_by_id(user_id)
            if user:
                user.refresh_token_hash = token_hash
                await self.db.flush()
                logger.debug(
                    f"[repo] Refresh token hash "
                    f"{'saved' if token_hash else 'cleared'} "
                    f"for user id={user_id}"
                )
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] save_refresh_token_hash failed: {exc}")
            raise DatabaseError(
                message="Refresh token saqlashda xato.",
                details={"error": str(exc)},
            ) from exc

    async def update_last_login(self, user_id: int) -> None:
        """
        Oxirgi login vaqtini hozirgi vaqtga yangilash.

        Har muvaffaqiyatli logindan keyin chaqiriladi.

        Args:
            user_id: Foydalanuvchi ID
        """
        from datetime import timezone
        try:
            from datetime import datetime
            user = await self.get_by_id(user_id)
            if user:
                user.last_login_at = datetime.now(timezone.utc)
                await self.db.flush()
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] update_last_login({user_id}) failed: {exc}")
            # Non-critical — loglaymiz, lekin xato tashlamaymiz

    async def update_password(
        self,
        user_id: int,
        new_hashed_password: str,
    ) -> None:
        """
        Foydalanuvchi parolini yangilash.

        DIQQAT: Bu yerga faqat HASHED parol kelishi kerak!
        Plain text parol hashing SecurityUtils da bajariladi.

        Args:
            user_id:             Foydalanuvchi ID
            new_hashed_password: Yangi bcrypt hash

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            user = await self.get_by_id(user_id)
            if user:
                user.hashed_password = new_hashed_password
                # Parol o'zgarganda barcha sessiyalar bekor qilinadi
                user.refresh_token_hash = None
                await self.db.flush()
                logger.debug(f"[repo] Password updated for user id={user_id}")
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] update_password({user_id}) failed: {exc}")
            raise DatabaseError(
                message="Parolni yangilashda xato.",
                details={"error": str(exc)},
            ) from exc

    async def update_profile(
        self,
        user_id: int,
        full_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[User]:
        """
        Foydalanuvchi profil ma'lumotlarini yangilash.

        Faqat None bo'lmagan maydonlar yangilanadi.

        Args:
            user_id:   Foydalanuvchi ID
            full_name: Yangi to'liq ism (None = o'zgartirilmaydi)
            role:      Yangi rol (None = o'zgartirilmaydi)
            is_active: Aktiv holati (None = o'zgartirilmaydi)

        Returns:
            Yangilangan User yoki None (topilmasa)

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            user = await self.get_by_id(user_id)
            if not user:
                return None

            if full_name is not None:
                user.full_name = full_name
            if role is not None:
                user.role = role
            if is_active is not None:
                user.is_active = is_active
                # Deaktivlanganda sessiyani ham o'chirish
                if not is_active:
                    user.refresh_token_hash = None

            await self.db.flush()
            await self.db.refresh(user)
            logger.debug(f"[repo] Profile updated for user id={user_id}")
            return user

        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"[repo] update_profile({user_id}) failed: {exc}")
            raise DatabaseError(
                message="Profilni yangilashda xato.",
                details={"error": str(exc)},
            ) from exc