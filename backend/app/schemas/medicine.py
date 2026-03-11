"""
Taurus Vision — Dori-Darmon Ombori Sxemalari

REQUEST / RESPONSE sxemalari Pydantic v2 bilan.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.models.medicine import MedicineType, MedicineUnit, MedicineAdminRoute


# =============================================================================
# MEDICINE INVENTORY
# =============================================================================

class MedicineInventoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=300, description="Dori nomi")
    generic_name: Optional[str] = Field(None, max_length=300, description="Umumiy nomi")
    medicine_type: MedicineType = Field(..., description="Dori turi")
    manufacturer: Optional[str] = Field(None, max_length=200, description="Ishlab chiqaruvchi")
    batch_number: Optional[str] = Field(None, max_length=100, description="Partiya raqami")
    quantity: float = Field(..., ge=0, description="Joriy miqdor")
    unit: MedicineUnit = Field(default=MedicineUnit.ML, description="O'lchov birligi")
    min_stock_quantity: float = Field(default=10.0, ge=0, description="Minimal qoldiq chegarasi")
    purchase_price: Optional[float] = Field(None, ge=0, description="Xarid narxi (so'm)")
    expiry_date: Optional[date] = Field(None, description="Yaroqlilik muddati")
    storage_temp_min: Optional[float] = Field(None, description="Saqlash harorati min °C")
    storage_temp_max: Optional[float] = Field(None, description="Saqlash harorati max °C")
    dosage_instructions: Optional[str] = Field(None, description="Berish ko'rsatmasi")
    notes: Optional[str] = Field(None, description="Izoh")
    species_applicable: Optional[str] = Field(None, description="Qo'llanma turlar (cattle,sheep...)")


class MedicineInventoryCreate(MedicineInventoryBase):
    pass


class MedicineInventoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=300)
    generic_name: Optional[str] = Field(None, max_length=300)
    medicine_type: Optional[MedicineType] = None
    manufacturer: Optional[str] = Field(None, max_length=200)
    batch_number: Optional[str] = Field(None, max_length=100)
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[MedicineUnit] = None
    min_stock_quantity: Optional[float] = Field(None, ge=0)
    purchase_price: Optional[float] = Field(None, ge=0)
    expiry_date: Optional[date] = None
    storage_temp_min: Optional[float] = None
    storage_temp_max: Optional[float] = None
    dosage_instructions: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    species_applicable: Optional[str] = None


class MedicineInventoryResponse(MedicineInventoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_low_stock: bool
    is_expired: bool
    days_until_expiry: Optional[int]
    created_at: datetime
    updated_at: datetime


class MedicineRestockRequest(BaseModel):
    """Ombor to'ldirish."""
    quantity_to_add: Optional[float] = Field(None, gt=0, description="Qo'shiladigan miqdor")
    quantity:        Optional[float] = Field(None, gt=0, description="Alias for quantity_to_add")

    @model_validator(mode="after")
    def resolve_quantity(self) -> "MedicineRestockRequest":
        if self.quantity_to_add is None and self.quantity is not None:
            self.quantity_to_add = self.quantity
        if self.quantity_to_add is None:
            raise ValueError("'quantity_to_add' yoki 'quantity' maydoni talab qilinadi")
        return self
    batch_number: Optional[str] = Field(None, description="Yangi partiya raqami")
    expiry_date: Optional[date] = Field(None, description="Yangi muddat")
    purchase_price: Optional[float] = Field(None, ge=0, description="Narxi")
    notes: Optional[str] = Field(None, description="Izoh")


# =============================================================================
# MEDICINE USAGE
# =============================================================================

class MedicineUsageBase(BaseModel):
    medicine_id: int = Field(..., description="Dori ID si")
    animal_id: int = Field(..., description="Jonivor ID si")
    health_record_id: Optional[int] = Field(None, description="Davolash yozuvi ID si")
    given_date: datetime = Field(default_factory=datetime.utcnow, description="Berilgan vaqt")
    quantity_given: float = Field(..., gt=0, description="Berilgan miqdor")
    admin_route: Optional[MedicineAdminRoute] = Field(None, description="Berish yo'li")
    given_by: Optional[str] = Field(None, max_length=200, description="Kim berdi")
    next_dose_date: Optional[date] = Field(None, description="Keyingi doza sanasi")
    withdrawal_date: Optional[date] = Field(None, description="Karantin tugash sanasi")
    notes: Optional[str] = Field(None, description="Izoh")


class MedicineUsageCreate(MedicineUsageBase):
    pass


class MedicineUsageResponse(MedicineUsageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medicine_name: Optional[str] = None
    medicine_unit: Optional[str] = None
    is_in_withdrawal: bool
    created_at: datetime


# =============================================================================
# LISTS & SUMMARY
# =============================================================================

class MedicineListResponse(BaseModel):
    items: List[MedicineInventoryResponse]
    total: int
    low_stock_count: int
    expired_count: int
    expiring_soon_count: int  # 30 kun ichida


class MedicineUsageListResponse(BaseModel):
    items: List[MedicineUsageResponse]
    total: int


class MedicineInventorySummary(BaseModel):
    """Veterinariya ombori umumiy holati."""
    total_medicines: int
    active_medicines: int
    low_stock_items: List[MedicineInventoryResponse]
    expired_items: List[MedicineInventoryResponse]
    expiring_soon_items: List[MedicineInventoryResponse]
    total_value: float  # Jami qiymat (so'm)