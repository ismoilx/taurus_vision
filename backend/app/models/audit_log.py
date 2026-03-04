"""
Taurus Vision — Security Audit Log Model

Tizimda ro'y beradigan barcha xavfsizlikka oid voqealar yoziladi.
Bu jadval append-only — faqat INSERT qilinadi, UPDATE va DELETE yo'q.

MUHIM:
    - Bu jadvaldagi yozuvlarni HECH QACHON o'chirish yoki o'zgartirish mumkin emas.
    - Forensics va compliance uchun zarur.
"""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, JSON, Index, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel   # id (PK) + created_at + updated_at


# =============================================================================
# ENUM
# =============================================================================

class AuditEventType(str, enum.Enum):
    """Xavfsizlik audit voqea turlari."""
    LOGIN_SUCCESS     = "LOGIN_SUCCESS"
    LOGIN_FAILED      = "LOGIN_FAILED"
    LOGIN_LOCKED      = "LOGIN_LOCKED"
    LOGOUT            = "LOGOUT"
    TOKEN_REFRESH     = "TOKEN_REFRESH"
    PASSWORD_CHANGED  = "PASSWORD_CHANGED"
    USER_CREATED      = "USER_CREATED"
    USER_UPDATED      = "USER_UPDATED"
    USER_ACTIVATED    = "USER_ACTIVATED"
    USER_DEACTIVATED  = "USER_DEACTIVATED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SUSPICIOUS        = "SUSPICIOUS"


class AuditSeverity(str, enum.Enum):
    """Voqea jiddiylik darajasi."""
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


# =============================================================================
# MODEL
# =============================================================================

class AuditLog(BaseModel):
    """
    Xavfsizlik audit log yozuvi.

    BaseModel dan meros: id (PK, autoincrement), created_at, updated_at.

    Attributes:
        event_type:  Voqea turi (AuditEventType)
        severity:    Jiddiylik darajasi
        user_id:     Harakat qilgan foydalanuvchi ID (nullable)
        username:    Foydalanuvchi nomi (user o'chirilsa ham qolsin)
        ip_address:  So'rov yuborgan IP manzili
        user_agent:  Brauzer/klient User-Agent
        endpoint:    HTTP so'rov yo'li
        http_method: HTTP metod
        details:     Qo'shimcha ma'lumotlar (JSON)
        occurred_at: Voqea aniq UTC vaqti
    """

    __tablename__ = "audit_logs"

    # Voqea turi va jiddiylik
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="AuditEventType qiymati",
    )
    severity: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AuditSeverity.INFO.value,
        comment="info / warning / critical",
    )

    # Kim qildi
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Harakat qilgan foydalanuvchi ID (nullable)",
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Foydalanuvchi nomi — user o'chirilsa ham saqlansin",
    )

    # Qayerdan
    ip_address: Mapped[str] = mapped_column(
        String(45),       # IPv6 uchun maksimal uzunlik
        nullable=False,
        index=True,
        comment="So'rov yuborgan IP manzili",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Brauzer / klient User-Agent",
    )

    # Nima so'raldi
    endpoint: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="HTTP so'rov yo'li",
    )
    http_method: Mapped[Optional[str]] = mapped_column(
        String(8),
        nullable=True,
        comment="HTTP metod: GET, POST, ...",
    )

    # Tafsilotlar
    details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Qo'shimcha kontekst (JSON)",
    )

    # Voqea vaqti (created_at dan alohida — aniqroq nom)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Voqea UTC vaqti",
    )

    # ==========================================================================
    # QO'SHIMCHA INDEKSLAR
    # ==========================================================================

    __table_args__ = (
        Index("ix_audit_ip_time",    "ip_address", "occurred_at"),
        Index("ix_audit_user_time",  "user_id",    "occurred_at"),
        Index("ix_audit_event_time", "event_type", "occurred_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} "
            f"event={self.event_type} "
            f"user={self.username!r} "
            f"ip={self.ip_address}>"
        )