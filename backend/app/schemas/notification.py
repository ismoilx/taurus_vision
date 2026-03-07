"""
Taurus Vision — Notification Schemas (Pydantic v2)

Request va Response modellari — in-app bildirishnomalar uchun.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.notification import NotificationType, NotificationEntityType


# =============================================================================
# RESPONSE
# =============================================================================

class NotificationOut(BaseModel):
    """Bitta notification uchun response schema."""

    model_config = ConfigDict(from_attributes=True)

    id:           int
    user_id:      Optional[int]                          = None
    n_type:       NotificationType
    title:        str
    message:      str
    entity_type:  Optional[NotificationEntityType]       = None
    entity_id:    Optional[int]                          = None
    action_url:   Optional[str]                          = None
    is_read:      bool
    read_at:      Optional[datetime]                     = None
    is_dismissed: bool
    extra_data:   Optional[dict[str, Any]]               = None
    created_at:   datetime
    updated_at:   datetime


class NotificationListOut(BaseModel):
    """Paginatsiyalangan notification ro'yxati."""

    items:        list[NotificationOut]
    total:        int
    unread_count: int
    page:         int
    limit:        int
    has_more:     bool


class NotificationCountOut(BaseModel):
    """O'qilmagan notification soni — badge uchun."""

    unread_count: int
    total:        int


# =============================================================================
# REQUEST
# =============================================================================

class NotificationCreateRequest(BaseModel):
    """Admin tomonidan yangi notification yaratish."""

    user_id:     Optional[int]                          = Field(
        None,
        description="Manzil foydalanuvchi (None = barcha foydalanuvchilarga broadcast)",
    )
    n_type:      NotificationType                       = Field(
        NotificationType.INFO,
        description="Notification turi",
    )
    title:       str                                    = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Qisqa sarlavha",
    )
    message:     str                                    = Field(
        ...,
        min_length=2,
        max_length=2000,
        description="To'liq xabar matni",
    )
    entity_type: Optional[NotificationEntityType]       = Field(
        None,
        description="Bog'liq entity turi",
    )
    entity_id:   Optional[int]                          = Field(
        None,
        description="Bog'liq entity ID",
    )
    action_url:  Optional[str]                          = Field(
        None,
        max_length=255,
        description="Frontend havolasi (masalan: /animals/5)",
    )
    extra_data:  Optional[dict[str, Any]]               = Field(
        None,
        description="Qo'shimcha kontekst ma'lumotlari",
    )


class MarkReadRequest(BaseModel):
    """Bir nechta notificationni o'qilgan deb belgilash."""

    notification_ids: list[int] = Field(
        ...,
        min_length=1,
        description="O'qilgan deb belgilanadigan notification ID lar",
    )