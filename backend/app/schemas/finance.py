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
    type:             Optional[str]  = Field(None,  description="income | expense")
    transaction_type: Optional[str]  = Field(None,  description="Alias for type: income | expense")
    category:         str  = Field(...,  max_length=30)
    amount_uzs:       Optional[int]  = Field(None,  gt=0, description="Miqdor (UZS, musbat)")
    amount:           Optional[float]= Field(None,  gt=0, description="Alias for amount_uzs")
    amount_usd:       Optional[float]= Field(None, gt=0)
    currency:         Optional[str]  = Field(None, description="Valyuta (UZS default, ignored)")
    description:      Optional[str]  = Field(None,  min_length=2, max_length=500)
    notes:            Optional[str]   = Field(None, max_length=2000)
    transaction_date: date = Field(...,  description="Operatsiya sanasi")
    payment_method:   str  = Field("cash", description="cash | transfer | credit")
    receipt_number:   Optional[str]   = Field(None, max_length=100)
    animal_id:        Optional[int]   = Field(None, gt=0)
    meta:             Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def resolve_aliases(self) -> "FinanceBase":
        # transaction_type → type
        if self.type is None and self.transaction_type is not None:
            self.type = self.transaction_type
        if self.type is None:
            raise ValueError("'type' yoki 'transaction_type' maydoni talab qilinadi")
        # amount → amount_uzs
        if self.amount_uzs is None and self.amount is not None:
            self.amount_uzs = int(self.amount)
        if self.amount_uzs is None:
            raise ValueError("'amount_uzs' yoki 'amount' maydoni talab qilinadi")
        if self.description is None:
            self.description = "-"
        return self

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v) -> Optional[str]:
        if v is None:
            return v
        if v not in ("income", "expense"):
            raise ValueError("type faqat 'income' yoki 'expense' bo'lishi mumkin")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment(cls, v: str) -> str:
        if v not in ("cash", "transfer", "credit"):
            raise ValueError("payment_method: cash | transfer | credit")
        return v

    @field_validator("transaction_date", mode="before")
    @classmethod
    def not_future(cls, v) -> date:
        # ISO datetime string → date (test sends full ISO datetime)
        if isinstance(v, str):
            try:
                # "2026-03-12T10:00:00+00:00" → date
                from datetime import datetime as dt
                parsed = dt.fromisoformat(v.replace("Z", "+00:00"))
                v = parsed.date()
            except ValueError:
                try:
                    from datetime import date as d
                    v = d.fromisoformat(v[:10])
                except ValueError:
                    raise ValueError("transaction_date: yaroqli sana formati talab qilinadi")
        elif isinstance(v, datetime):
            v = v.date()
        if isinstance(v, date) and v > date.today():
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
    transaction_type: Optional[str] = None   # alias for type
    category:         str
    amount_uzs:       int
    amount:           Optional[float] = None  # alias for amount_uzs
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

    @model_validator(mode="after")
    def populate_aliases(self) -> "FinanceTransactionResponse":
        if self.transaction_type is None:
            self.transaction_type = self.type
        if self.amount is None:
            self.amount = float(self.amount_uzs)
        return self


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