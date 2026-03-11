"""
Taurus Vision — Feed Management Schemas (Sprint 20)

API request/response validatsiya uchun Pydantic v2 schemalar.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.feed import FeedType, FeedUnit


# =============================================================================
# FEED STOCK SCHEMAS
# =============================================================================

class FeedStockCreate(BaseModel):
    name:             str       = Field(..., min_length=2, max_length=200)
    feed_type:        FeedType
    description:      Optional[str]      = None
    unit:             FeedUnit           = FeedUnit.KG
    current_kg:       Optional[float]    = Field(None, ge=0)
    quantity_kg:      Optional[float]    = Field(None, ge=0, description="Alias for current_kg")
    min_threshold_kg: float              = Field(100.0, ge=0)
    unit_cost_uzs:    Optional[int]      = Field(None, ge=0)
    price_per_kg:     Optional[float]    = Field(None, ge=0, description="Alias for unit_cost_uzs")
    supplier:         Optional[str]      = Field(None, max_length=200)
    purchase_date:    Optional[datetime] = None
    expiry_date:      Optional[datetime] = None
    notes:            Optional[str]      = None

    @model_validator(mode="after")
    def resolve_aliases(self) -> "FeedStockCreate":
        if self.current_kg is None:
            self.current_kg = self.quantity_kg if self.quantity_kg is not None else 0.0
        if self.current_kg is not None and self.current_kg < 0:
            raise ValueError("quantity_kg/current_kg must be >= 0")
        if self.unit_cost_uzs is None and self.price_per_kg is not None:
            self.unit_cost_uzs = int(self.price_per_kg)
        return self


class FeedStockUpdate(BaseModel):
    name:             Optional[str]      = Field(None, min_length=2, max_length=200)
    description:      Optional[str]      = None
    min_threshold_kg: Optional[float]    = Field(None, ge=0)
    unit_cost_uzs:    Optional[int]      = Field(None, ge=0)
    supplier:         Optional[str]      = Field(None, max_length=200)
    expiry_date:      Optional[datetime] = None
    is_active:        Optional[bool]     = None
    notes:            Optional[str]      = None

    @model_validator(mode="after")
    def at_least_one(self) -> "FeedStockUpdate":
        if not self.model_dump(exclude_none=True):
            raise ValueError("Kamida bitta maydon bo'lishi kerak.")
        return self


class FeedStockRestock(BaseModel):
    """Omborniga qo'shish (kirim)."""
    quantity_kg:   float           = Field(..., gt=0, description="Qo'shilayotgan miqdor (kg)")
    unit_cost_uzs: Optional[int]   = Field(None, ge=0, description="Yangi narx (ixtiyoriy)")
    supplier:      Optional[str]   = Field(None, max_length=200)
    purchase_date: Optional[datetime] = None
    expiry_date:   Optional[datetime] = None
    notes:         Optional[str]   = None


class FeedStockResponse(BaseModel):
    id:               int
    feed_type:        FeedType
    name:             str
    description:      Optional[str]    = None
    unit:             FeedUnit
    current_kg:       float
    min_threshold_kg: float
    unit_cost_uzs:    Optional[int]    = None
    supplier:         Optional[str]    = None
    purchase_date:    Optional[datetime] = None
    expiry_date:      Optional[datetime] = None
    is_active:        bool
    is_low:           bool
    is_expired:       bool
    stock_percent:    float
    total_value_uzs:  Optional[int]    = None
    low_stock_alerted: bool
    notes:            Optional[str]    = None
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class FeedStockListResponse(BaseModel):
    items: list[FeedStockResponse]
    total: int
    low_stock_count:   int
    expired_count:     int
    total_value_uzs:   Optional[int]


# =============================================================================
# FEED RECORD SCHEMAS
# =============================================================================

class FeedRecordCreate(BaseModel):
    stock_id:    int            = Field(..., gt=0)
    quantity_kg: float          = Field(..., gt=0, description="Berilgan miqdor (kg)")
    animal_id:   Optional[int]  = Field(None, gt=0, description="Jonivor ID (None = butun poda)")
    fed_at:      Optional[datetime] = Field(None, description="Vaqt (None = hozir)")
    notes:       Optional[str]  = Field(None, max_length=500)
    meta:        Optional[dict[str, Any]] = None

    @field_validator("fed_at")
    @classmethod
    def normalize_fed_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        from datetime import timezone
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class FeedRecordResponse(BaseModel):
    id:          int
    stock_id:    int
    animal_id:   Optional[int]    = None
    fed_by:      Optional[int]    = None
    quantity_kg: float
    fed_at:      datetime
    notes:       Optional[str]    = None
    meta:        Optional[dict]   = None

    # Joined
    stock_name:     Optional[str] = None
    feed_type:      Optional[str] = None
    animal_tag_id:  Optional[str] = None
    feeder_name:    Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}


class FeedRecordListResponse(BaseModel):
    items:       list[FeedRecordResponse]
    total:       int
    total_kg:    float
    page:        int
    page_size:   int
    total_pages: int


# =============================================================================
# STATISTICS
# =============================================================================

class DailyConsumption(BaseModel):
    date:    str
    total_kg: float
    by_type: dict[str, float]


class FeedStats(BaseModel):
    """Dashboard uchun ozuqa statistikasi."""
    total_stocks:       int
    active_stocks:      int
    low_stock_count:    int
    expired_count:      int
    total_inventory_kg: float
    total_value_uzs:    Optional[int]

    consumed_today_kg:    float
    consumed_this_week_kg: float

    low_stocks:   list[FeedStockResponse]   = Field(description="Kam bo'lgan ozuqalar (max 5)")
    daily_trend:  list[DailyConsumption]    = Field(description="So'nggi 7 kunlik iste'mol")