"""
Taurus Vision — Integration Schemas (Pydantic v2)

APIKey va Webhook uchun request/response modellari.

XAVFSIZLIK QOIDALARI:
  - key_hash, secret hech qachon response da qaytarilmaydi
  - raw_key faqat CREATE response da bir marta qaytariladi
  - Keyingi GET so'rovlarda faqat display_key (to'ldirilgan *) ko'rinadi
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, HttpUrl


# ─────────────────────────────────────────────────────────────────────────────
# VALID SCOPES & EVENTS
# ─────────────────────────────────────────────────────────────────────────────

VALID_SCOPES = {
    "read:animals", "read:sensors", "read:alerts",
    "read:detections", "read:finance",
    "write:sensors", "write:detections",
    "admin",
}

VALID_EVENTS = {
    "alert.created", "alert.critical",
    "detection.animal", "weight.anomaly",
    "sensor.anomaly", "adi.critical", "animal.not_seen",
}


# =============================================================================
# API KEY
# =============================================================================

class APIKeyCreate(BaseModel):
    name:        str            = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scopes:      list[str]      = Field(..., min_length=1)
    expires_at:  Optional[datetime] = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_SCOPES
        if invalid:
            raise ValueError(f"Noto'g'ri scope(lar): {invalid}. Mumkin: {sorted(VALID_SCOPES)}")
        return list(set(v))


class APIKeyResponse(BaseModel):
    id:            int
    name:          str
    description:   Optional[str]
    key_prefix:    str
    display_key:   str           # "tv_live_ab12cd34_****************"
    scopes:        list[str]
    is_active:     bool
    expires_at:    Optional[datetime]
    last_used_at:  Optional[datetime]
    request_count: int
    created_by:    Optional[int]
    creator_name:  Optional[str]
    created_at:    datetime
    updated_at:    datetime
    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    """Faqat CREATE da qaytariladi — raw_key bir marta ko'rsatiladi."""
    raw_key: str = Field(..., description="Bu kalit QAYTA KO'RSATILMAYDI — hoziroq saqlang")


class APIKeyUpdate(BaseModel):
    name:        Optional[str]      = Field(None, min_length=2, max_length=100)
    description: Optional[str]      = Field(None, max_length=500)
    is_active:   Optional[bool]     = None
    expires_at:  Optional[datetime] = None


class APIKeyListResponse(BaseModel):
    items: list[APIKeyResponse]
    total: int


# =============================================================================
# WEBHOOK
# =============================================================================

class WebhookCreate(BaseModel):
    name:        str            = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    url:         str            = Field(..., description="HTTPS URL")
    events:      list[str]      = Field(..., min_length=1)

    @field_validator("url")
    @classmethod
    def must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Webhook URL HTTPS bo'lishi shart (https:// bilan boshlanishi kerak)")
        if len(v) > 500:
            raise ValueError("URL 500 belgidan oshmasligi kerak")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_EVENTS
        if invalid:
            raise ValueError(f"Noto'g'ri voqea(lar): {invalid}. Mumkin: {sorted(VALID_EVENTS)}")
        return list(set(v))


class WebhookUpdate(BaseModel):
    name:        Optional[str]      = Field(None, min_length=2, max_length=100)
    description: Optional[str]      = Field(None, max_length=500)
    url:         Optional[str]      = None
    events:      Optional[list[str]]= None
    is_active:   Optional[bool]     = None

    @field_validator("url")
    @classmethod
    def must_be_https(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith("https://"):
            raise ValueError("Webhook URL HTTPS bo'lishi shart")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v:
            invalid = set(v) - VALID_EVENTS
            if invalid:
                raise ValueError(f"Noto'g'ri voqea(lar): {invalid}")
        return v


class WebhookResponse(BaseModel):
    id:                int
    name:              str
    description:       Optional[str]
    url:               str
    events:            list[str]
    is_active:         bool
    failure_count:     int
    success_count:     int
    last_triggered_at: Optional[datetime]
    last_status_code:  Optional[int]
    last_error:        Optional[str]
    health_status:     str
    created_by:        Optional[int]
    creator_name:      Optional[str]
    created_at:        datetime
    updated_at:        datetime
    model_config = {"from_attributes": True}


class WebhookListResponse(BaseModel):
    items: list[WebhookResponse]
    total: int


class WebhookTestResponse(BaseModel):
    success:     bool
    status_code: Optional[int]
    latency_ms:  Optional[int]
    error:       Optional[str]


# =============================================================================
# CONSTANTS (frontend uchun)
# =============================================================================

class IntegrationMeta(BaseModel):
    """Frontend uchun mavjud scope va voqealar ro'yxati."""
    scopes: list[dict[str, str]]
    events: list[dict[str, str]]


SCOPE_META = [
    {"value": "read:animals",    "label": "Jonivorlarni o'qish",    "group": "O'qish"},
    {"value": "read:sensors",    "label": "Sensorlarni o'qish",     "group": "O'qish"},
    {"value": "read:alerts",     "label": "Alertlarni o'qish",      "group": "O'qish"},
    {"value": "read:detections", "label": "Deteksiyalarni o'qish",  "group": "O'qish"},
    {"value": "read:finance",    "label": "Moliyani o'qish",        "group": "O'qish"},
    {"value": "write:sensors",   "label": "Sensor ma'lumot yuborish","group": "Yozish (IoT)"},
    {"value": "write:detections","label": "Deteksiya natijasi yuborish","group": "Yozish (IoT)"},
    {"value": "admin",           "label": "Admin (barcha huquqlar)","group": "Admin"},
]

EVENT_META = [
    {"value": "alert.created",    "label": "Har qanday yangi alert",     "icon": "🔔"},
    {"value": "alert.critical",   "label": "Kritik/Yuqori alert",        "icon": "🚨"},
    {"value": "detection.animal", "label": "Jonivor aniqlandi (YOLO)",   "icon": "👁"},
    {"value": "weight.anomaly",   "label": "Vazn anomaliyasi (>5%)",     "icon": "⚖️"},
    {"value": "sensor.anomaly",   "label": "Sensor anomaliyasi",         "icon": "📡"},
    {"value": "adi.critical",     "label": "ADI kritik darajada (< 30)", "icon": "📉"},
    {"value": "animal.not_seen",  "label": "Jonivor 24 soat ko'rinmadi","icon": "❓"},
]