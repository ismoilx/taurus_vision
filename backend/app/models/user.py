"""
Taurus Vision — User Database Model

Tizim foydalanuvchilari: ferma menejerlari, veterinarlar, ma'murlar.

ROLLAR:
    ADMIN   — To'liq huquq: foydalanuvchi boshqarish, tizim sozlamalari
    MANAGER — Jonivorlar, kameralar, alertlarni boshqarish; hisobotlar
    VIEWER  — Faqat ko'rish huquqi: dashboard, monitoring, hisobotlar

XAVFSIZLIK:
    - Parol hech qachon ochiq (plain text) saqlanmaydi
    - Faqat bcrypt hash saqlanadi
    - Refresh token dan faqat SHA-256 hash saqlanadi
    - last_login_at orqali suspicous activity kuzatiladi
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Enum as SQLEnum, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """
    Foydalanuvchi roli — ruxsatlarni belgilaydi.

    Hierarchy (eng kichikdan kattaga):
        VIEWER < MANAGER < ADMIN
    """

    ADMIN   = "admin"    # To'liq huquq
    MANAGER = "manager"  # Operatsional boshqaruv
    VIEWER  = "viewer"   # Faqat ko'rish


class User(BaseModel):
    """
    Tizim foydalanuvchisi.

    FastAPI JWT auth tizimi uchun asosiy model.
    Barcha API so'rovlari shu model orqali autentifikatsiya qilinadi.
    """

    __tablename__ = "users"

    # =========================================================================
    # IDENTITY
    # =========================================================================

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email manzili — login uchun ishlatiladi",
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Noyob foydalanuvchi nomi (lotin harflari, raqamlar, _)",
    )

    full_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        comment="To'liq ism — ko'rsatish uchun",
    )

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash — plain text hech qachon saqlanmaydi",
    )

    # Refresh token dan SHA-256 hash — to'g'ridan-to'g'ri token saqlanmaydi
    # None = foydalanuvchi tizimdan chiqgan
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="SHA-256(refresh_token) — logout qilganda NULL ga o'rnatiladi",
    )

    # =========================================================================
    # AUTHORIZATION
    # =========================================================================

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.VIEWER,
        comment="Foydalanuvchi roli: admin | manager | viewer",
    )

    # =========================================================================
    # STATUS
    # =========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False = foydalanuvchi bloklangan (o'chirilmaydi, faqat deaktivlanadi)",
    )

    # =========================================================================
    # AUDIT
    # =========================================================================

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Oxirgi muvaffaqiyatli login vaqti (UTC)",
    )

    # =========================================================================
    # MULTI-FARM
    # =========================================================================

    current_farm_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Foydalanuvchi hozir ishlayotgan ferma ID si",
    )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"<User("
            f"id={self.id}, "
            f"username='{self.username}', "
            f"role={self.role.value}, "
            f"active={self.is_active}"
            f")>"
        )

    @property
    def is_admin(self) -> bool:
        """ADMIN roli tekshiruvi."""
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        """MANAGER yoki yuqori roli tekshiruvi."""
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)

    def has_permission(self, required_role: UserRole) -> bool:
        """
        Berilgan rol uchun ruxsat tekshiruvi.

        Hierarchy: VIEWER < MANAGER < ADMIN

        Args:
            required_role: Talab qilinadigan minimal rol

        Returns:
            True — agar foydalanuvchi kerakli ruxsatga ega bo'lsa
        """
        hierarchy = {
            UserRole.VIEWER:  0,
            UserRole.MANAGER: 1,
            UserRole.ADMIN:   2,
        }
        return hierarchy.get(self.role, -1) >= hierarchy.get(required_role, 99)