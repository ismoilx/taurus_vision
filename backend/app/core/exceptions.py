"""
Taurus Vision — Custom Exception Hierarchy

Barcha domain exception lar shu yerda aniqlanadi.
FastAPI exception handler lar ular orqali to'g'ri HTTP javoblarini qaytaradi.

EXCEPTION → HTTP STATUS MAP:
    EntityNotFoundError       → 404 Not Found
    EntityAlreadyExistsError  → 409 Conflict
    BusinessRuleViolationError→ 400 Bad Request
    ValidationError           → 422 Unprocessable Entity
    AuthenticationError       → 401 Unauthorized
    PermissionDeniedError     → 403 Forbidden
    DatabaseError             → 500 Internal Server Error
"""

from typing import Any, Optional


# =============================================================================
# BASE
# =============================================================================

class TaurusException(Exception):
    """
    Barcha Taurus Vision exception larining asosi.

    Args:
        message: Foydalanuvchiga ko'rsatiladigan xato tavsifi
        details: Qo'shimcha tafsilotlar (debug yoki frontend uchun)
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# =============================================================================
# DATA EXCEPTIONS (404, 409, 400, 422)
# =============================================================================

class EntityNotFoundError(TaurusException):
    """
    So'ralgan entity bazada topilmadi.

    HTTP 404 Not Found ga map qilinadi.

    IKKALA USULDA ISHLATISH MUMKIN:
        # 1. Qisqa yozuv (entity + identifier)
        raise EntityNotFoundError(entity="Animal", identifier=42)
        # → "Animal with identifier 42 not found"

        # 2. To'liq yozuv (message + details)
        raise EntityNotFoundError(
            message="Custom message",
            details={"field": "value"}
        )

    Args:
        entity:     Entity nomi (masalan: "Animal", "User")
        identifier: Entity identifikatori (id, tag_id va boshqalar)
        message:    To'g'ridan-to'g'ri xabar (entity/identifier bilan birga ishlatilmaydi)
        details:    Qo'shimcha tafsilotlar dict
    """

    def __init__(
        self,
        entity: Optional[str] = None,
        identifier: Any = None,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        if message is None:
            if entity and identifier is not None:
                message = f"{entity} with identifier '{identifier}' not found"
            elif entity:
                message = f"{entity} not found"
            else:
                message = "Entity not found"

        super().__init__(message=message, details=details or {})


class EntityAlreadyExistsError(TaurusException):
    """
    Yaratilayotgan entity allaqachon mavjud.

    HTTP 409 Conflict ga map qilinadi.

    Misol:
        raise EntityAlreadyExistsError(
            message="Animal with this tag already exists",
            details={"tag_id": "JNV-001"}
        )
    """
    pass


class BusinessRuleViolationError(TaurusException):
    """
    Biznes qoidasi buzildi.

    HTTP 400 Bad Request ga map qilinadi.

    Misol:
        raise BusinessRuleViolationError(
            message="Cannot modify sold animal",
            details={"status": "sold", "animal_id": 42}
        )
    """
    pass


class ValidationError(TaurusException):
    """
    Ma'lumot validatsiyadan o'tmadi.

    HTTP 422 Unprocessable Entity ga map qilinadi.

    Misol:
        raise ValidationError(
            message="Birth date cannot be in the future",
            details={"birth_date": "2030-01-01"}
        )
    """
    pass


# =============================================================================
# AUTH EXCEPTIONS (401, 403)
# =============================================================================

class AuthenticationError(TaurusException):
    """
    Autentifikatsiya muvaffaqiyatsiz.

    HTTP 401 Unauthorized ga map qilinadi.

    Quyidagi holatlarda ishlatiladi:
        - Token mavjud emas yoki noto'g'ri
        - Token muddati tugagan
        - Email/parol mos kelmadi
        - Foydalanuvchi deaktivlashtirilgan

    Misol:
        raise AuthenticationError("Invalid or expired token")
        raise AuthenticationError("Incorrect email or password")
    """
    pass


class PermissionDeniedError(TaurusException):
    """
    Foydalanuvchi bu amalni bajarishga ruxsati yo'q.

    HTTP 403 Forbidden ga map qilinadi.

    Misol:
        raise PermissionDeniedError(
            message="Only ADMIN can create users",
            details={"required_role": "ADMIN", "user_role": "VIEWER"}
        )
    """
    pass


# =============================================================================
# SYSTEM EXCEPTIONS (500)
# =============================================================================

class DatabaseError(TaurusException):
    """
    Database operatsiyasi muvaffaqiyatsiz yakunlandi.

    HTTP 500 Internal Server Error ga map qilinadi.

    Misol:
        raise DatabaseError(
            message="Failed to save animal",
            details={"error": str(exc)}
        )
    """
    pass