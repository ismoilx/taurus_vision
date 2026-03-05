"""
Taurus Vision — Finance Schemas (Pydantic v2)

Request/Response modellari moliyaviy modul uchun.

QOIDALAR:
    - amount_uzs: musbat butun son (manfiy qiymat qabul qilinmaydi)
    - category validatsiyasi type ga bog'liq (service darajasida)
    - transaction_date: kelajak sanaga ruxsat yo'q
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# BASE
# =============================================================================

class FinanceBase(BaseModel):
    """Umumiy maydonlar."""
    type:             str  = Field(...,  description="income | expense")
    category:         str  = Field(...,  max_length=30)
    amount_uzs:       int  = Field(...,  gt=0, description="Miqdor (UZS, musbat)")
    amount_usd:       Optional[float] = Field(None, gt=0)
    description:      str  = Field(...,  min_length=2, max_length=500)
    notes:            Optional[str]   = Field(None, max_length=2000)
    transaction_date: date = Field(...,  description="Operatsiya sanasi")
    payment_method:   str  = Field("cash", description="cash | transfer | credit")
    receipt_number:   Optional[str]   = Field(None, max_length=100)
    animal_id:        Optional[int]   = Field(None, gt=0)
    meta:             Optional[dict[str, Any]] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("income", "expense"):
            raise ValueError("type faqat 'income' yoki 'expense' bo'lishi mumkin")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment(cls, v: str) -> str:
        if v not in ("cash", "transfer", "credit"):
            raise ValueError("payment_method: cash | transfer | credit")
        return v

    @field_validator("transaction_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Kelajak sanaga operatsiya kiritib bo'lmaydi")
        return v

    @model_validator(mode="after")
    def validate_category(self) -> "FinanceBase":
        """
        type ga mos kategoriyani tekshirish.
        income  → IncomeCategory
        expense → ExpenseCategory
        """
        income_cats  = {"animal_sale", "milk_sale", "meat_sale", "wool_sale", "subsidy", "other"}
        expense_cats = {"feed", "veterinary", "equipment", "labor", "utilities", "transport", "other"}

        if self.type == "income" and self.category not in income_cats:
            raise ValueError(
                f"Daromad uchun noto'g'ri kategoriya: '{self.category}'. "
                f"Mumkin: {sorted(income_cats)}"
            )
        if self.type == "expense" and self.category not in expense_cats:
            raise ValueError(
                f"Xarajat uchun noto'g'ri kategoriya: '{self.category}'. "
                f"Mumkin: {sorted(expense_cats)}"
            )
        return self


# =============================================================================
# CREATE
# =============================================================================

class FinanceTransactionCreate(FinanceBase):
    """Yangi operatsiya yaratish."""
    pass


# =============================================================================
# UPDATE
# =============================================================================

class FinanceTransactionUpdate(BaseModel):
    """Mavjud operatsiyani yangilash (barcha maydonlar ixtiyoriy)."""
    category:         Optional[str]   = Field(None, max_length=30)
    amount_uzs:       Optional[int]   = Field(None, gt=0)
    amount_usd:       Optional[float] = Field(None, gt=0)
    description:      Optional[str]   = Field(None, min_length=2, max_length=500)
    notes:            Optional[str]   = Field(None, max_length=2000)
    transaction_date: Optional[date]  = None
    payment_method:   Optional[str]   = Field(None)
    receipt_number:   Optional[str]   = Field(None, max_length=100)
    animal_id:        Optional[int]   = Field(None, gt=0)
    meta:             Optional[dict[str, Any]] = None

    @field_validator("transaction_date")
    @classmethod
    def not_future(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Kelajak sanaga operatsiya kiritib bo'lmaydi")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ("cash", "transfer", "credit"):
            raise ValueError("payment_method: cash | transfer | credit")
        return v


# =============================================================================
# RESPONSE
# =============================================================================

class FinanceTransactionResponse(BaseModel):
    """Javob: bitta operatsiya."""
    id:               int
    type:             str
    category:         str
    amount_uzs:       int
    amount_usd:       Optional[float]
    description:      str
    notes:            Optional[str]
    transaction_date: date
    payment_method:   str
    receipt_number:   Optional[str]
    animal_id:        Optional[int]
    animal_tag:       Optional[str]   # animal.tag_id (join orqali)
    created_by:       Optional[int]
    creator_name:     Optional[str]   # user.full_name
    meta:             Optional[dict[str, Any]]
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class FinanceTransactionListResponse(BaseModel):
    """Javob: operatsiyalar ro'yxati."""
    items:   list[FinanceTransactionResponse]
    total:   int
    page:    int
    size:    int
    pages:   int


# =============================================================================
# SUMMARY / DASHBOARD
# =============================================================================

class FinanceCategoryStat(BaseModel):
    """Bitta kategoriya statistikasi."""
    category:    str
    label:       str           # O'zbek tilida nom
    amount_uzs:  int
    percent:     float         # Umumiy xarajat/daromaddan foizi
    count:       int           # Operatsiyalar soni


class FinanceSummary(BaseModel):
    """Dashboard uchun asosiy ko'rsatkichlar."""
    period_label:    str            # Masalan: "Mart 2026"
    date_from:       date
    date_to:         date

    # Asosiy raqamlar
    total_income:    int            # Jami daromad (UZS)
    total_expense:   int            # Jami xarajat (UZS)
    net_profit:      int            # Foyda = daromad - xarajat
    roi_percent:     float          # ROI = foyda/xarajat × 100

    # Tranzaksiyalar soni
    income_count:    int
    expense_count:   int

    # Kategoriya bo'yicha
    expense_by_category: list[FinanceCategoryStat]
    income_by_category:  list[FinanceCategoryStat]

    # O'tgan davr bilan taqqoslash (None = birinchi davr)
    prev_income:     Optional[int]
    prev_expense:    Optional[int]
    prev_profit:     Optional[int]
    income_change_pct:  Optional[float]   # +10.5 → 10.5% o'sdi
    expense_change_pct: Optional[float]
    profit_change_pct:  Optional[float]


class MonthlyTrend(BaseModel):
    """Oylik trend uchun bitta nuqta."""
    month:       str    # "2026-03"
    month_label: str    # "Mart 2026"
    income:      int
    expense:     int
    profit:      int


class FinanceTrends(BaseModel):
    """6/12 oylik trend."""
    months: list[MonthlyTrend]
    total_income:  int
    total_expense: int
    total_profit:  int


# =============================================================================
# ROI (Jonivor bo'yicha)
# =============================================================================

class AnimalROI(BaseModel):
    """Bitta jonivorning ROI ko'rsatkichi."""
    animal_id:    int
    tag_id:       str
    species:      str
    total_income: int
    total_expense: int
    net_profit:   int
    roi_percent:  float
    tx_count:     int


class ROIReport(BaseModel):
    """Barcha jonivorlar ROI hisoboti."""
    date_from:     date
    date_to:       date
    animals:       list[AnimalROI]
    farm_income:   int      # Jonivorga bog'liq bo'lmagan daromad
    farm_expense:  int      # Jonivorga bog'liq bo'lmagan xarajat
    total_income:  int
    total_expense: int
    total_profit:  int
    overall_roi:   float