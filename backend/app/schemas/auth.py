"""
Taurus Vision — Authentication & User Schemas

Request va response uchun Pydantic v2 schema lar.

QOIDALAR:
    - Parol hech qachon response da qaytarilmaydi
    - Hashed_password hech qachon response ga kirmaydi
    - Token schema lar OAuth2 standartiga mos
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator
import re

from app.models.user import UserRole


# =============================================================================
# USER SCHEMAS
# =============================================================================

class UserCreate(BaseModel):
    """
    Yangi foydalanuvchi yaratish uchun request schema.

    Faqat ADMIN roli bilan bajariladigan endpoint da ishlatiladi.
    """

    email: EmailStr
    username: str
    full_name: Optional[str] = None
    password: str
    role: UserRole = UserRole.VIEWER

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Username faqat lotin harflari, raqamlar va _ dan iborat bo'lishi kerak.

        Args:
            v: Tekshiriladigan username

        Returns:
            Kichik harflarga o'tkazilgan username

        Raises:
            ValueError: Noto'g'ri format
        """
        if not re.match(r"^[a-zA-Z0-9_]{3,50}$", v):
            raise ValueError(
                "Username faqat lotin harflari (a-z, A-Z), raqamlar (0-9) "
                "va pastki chiziq (_) dan iborat bo'lishi kerak. "
                "Uzunlik: 3-50 belgi."
            )
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Parol kuchliligi tekshiruvi.

        Talablar:
            - Kamida 8 belgi
            - Kamida 1 ta katta harf
            - Kamida 1 ta kichik harf
            - Kamida 1 ta raqam

        Args:
            v: Tekshiriladigan parol

        Returns:
            Parol (o'zgartirilmaydi)

        Raises:
            ValueError: Parol talablarga mos kelmasa
        """
        if len(v) < 8:
            raise ValueError("Parol kamida 8 belgidan iborat bo'lishi kerak.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Parol kamida 1 ta katta harf (A-Z) o'z ichiga olishi kerak.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Parol kamida 1 ta kichik harf (a-z) o'z ichiga olishi kerak.")
        if not re.search(r"\d", v):
            raise ValueError("Parol kamida 1 ta raqam (0-9) o'z ichiga olishi kerak.")
        return v

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """
    Foydalanuvchi ma'lumotlarini yangilash uchun schema.

    Barcha maydonlar ixtiyoriy — faqat jo'natilganlar yangilanadi.
    """

    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """
    Foydalanuvchi ma'lumotlari response schema.

    DIQQAT: hashed_password va refresh_token_hash hech qachon kirmaydi.
    """

    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    model_config = {"from_attributes": True}


# =============================================================================
# AUTH SCHEMAS
# =============================================================================

class LoginRequest(BaseModel):
    """
    Login request schema.

    Email YOKI username bilan login qilish mumkin.
    """

    # Email yoki username (ikkalasidan biri yetarli)
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_identifier(self) -> "LoginRequest":
        """
        Email yoki username dan kamida biri bo'lishi shart.

        Returns:
            Self — validatsiya o'tdi

        Raises:
            ValueError: Ikkala maydon ham bo'sh
        """
        if not self.email and not self.username:
            raise ValueError("Email yoki username kiritish majburiy.")
        return self


class TokenResponse(BaseModel):
    """
    Muvaffaqiyatli login response schema.

    OAuth2 Bearer token standartiga mos.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    # Access token qancha sekundda muddati tugaydi
    expires_in: int

    # Foydalanuvchi ma'lumotlari — frontendga qo'shimcha so'rov kerak emas
    user: UserResponse


class RefreshRequest(BaseModel):
    """Refresh token orqali yangi access token olish."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Parolni o'zgartirish uchun request schema."""

    current_password: str
    new_password: str


class AdminPasswordResetRequest(BaseModel):
    """
    Admin tomonidan boshqa foydalanuvchi parolini tiklash uchun schema.

    Joriy parol talab qilinmaydi — ADMIN huquqi tekshiruvi yetarli.
    """

    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """
        Yangi parol kuchliligi tekshiruvi.

        Args:
            v: Yangi parol

        Returns:
            Parol (o'zgartirilmaydi)

        Raises:
            ValueError: Parol kuchsiz
        """
        if len(v) < 8:
            raise ValueError("Parol kamida 8 belgidan iborat bo'lishi kerak.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Parol kamida 1 ta katta harf (A-Z) o'z ichiga olishi kerak.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Parol kamida 1 ta kichik harf (a-z) o'z ichiga olishi kerak.")
        if not re.search(r"\d", v):
            raise ValueError("Parol kamida 1 ta raqam (0-9) o'z ichiga olishi kerak.")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """
        Yangi parol kuchliligi tekshiruvi.

        Args:
            v: Yangi parol

        Returns:
            Parol (o'zgartirilmaydi)

        Raises:
            ValueError: Parol kuchsiz
        """
        if len(v) < 8:
            raise ValueError("Yangi parol kamida 8 belgidan iborat bo'lishi kerak.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Yangi parol kamida 1 ta katta harf o'z ichiga olishi kerak.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Yangi parol kamida 1 ta kichik harf o'z ichiga olishi kerak.")
        if not re.search(r"\d", v):
            raise ValueError("Yangi parol kamida 1 ta raqam o'z ichiga olishi kerak.")
        return v

# =============================================================================
# AUDIT LOG SCHEMAS
# =============================================================================

class AuditLogResponse(BaseModel):
    """Bitta audit log yozuvi response schema."""

    id: int
    event_type: str
    severity: str
    user_id: Optional[int]
    username: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    endpoint: Optional[str]
    http_method: Optional[str]
    details: Optional[dict]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Sahifalangan audit log ro'yxati."""

    items: list[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int