"""
Taurus Vision — Finance API Endpoints

TRANSACTIONS:
    GET    /finance/transactions         — Ro'yxat (filter, pagination)
    POST   /finance/transactions         — Yangi operatsiya [MANAGER+]
    GET    /finance/transactions/{id}    — Bitta operatsiya
    PATCH  /finance/transactions/{id}    — Tahrirlash [MANAGER+]
    DELETE /finance/transactions/{id}    — O'chirish [MANAGER+]

ANALYTICS:
    GET    /finance/summary              — Dashboard summary
    GET    /finance/trends               — Oylik trendlar
    GET    /finance/roi                  — Jonivorlar ROI hisoboti

RUXSATLAR:
    GET    — barcha autentifikatsiyalangan foydalanuvchilar
    POST / PATCH / DELETE — faqat MANAGER va ADMIN
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, require_manager
from app.core.database import get_db
from app.models.user import User
from app.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    FinanceTransactionResponse,
    FinanceTransactionListResponse,
    FinanceSummary,
    FinanceTrends,
    ROIReport,
)
from app.services.finance_service import FinanceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/finance", tags=["Finance"])

CurrentUser    = Annotated[User, Depends(get_current_active_user)]
CurrentManager = Annotated[User, Depends(require_manager)]
DB             = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# TRANSACTIONS
# =============================================================================

@router.get(
    "/transactions",
    response_model=FinanceTransactionListResponse,
    summary="Operatsiyalar ro'yxati",
    description=(
        "Moliyaviy operatsiyalarni filtrlash, sahifalash va saralash. "
        "type, category, animal_id, sana oraliq bo'yicha filtr."
    ),
)
async def list_transactions(
    db:        DB,
    user:      CurrentUser,
    type:      Optional[str]  = Query(None, description="income | expense"),
    category:  Optional[str]  = Query(None, description="Kategoriya"),
    animal_id: Optional[int]  = Query(None, description="Jonivor ID"),
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi (YYYY-MM-DD)"),
    date_to:   Optional[date] = Query(None, description="Tugash sanasi (YYYY-MM-DD)"),
    page:      int            = Query(1,    ge=1),
    size:      int            = Query(20,   ge=1, le=100),
) -> FinanceTransactionListResponse:
    """Barcha operatsiyalar (filtrlangan, sahifalangan)."""
    return await FinanceService(db).list_transactions(
        type      = type,
        category  = category,
        animal_id = animal_id,
        date_from = date_from,
        date_to   = date_to,
        page      = page,
        size      = size,
    )


@router.post(
    "/transactions",
    response_model=FinanceTransactionResponse,
    status_code=201,
    summary="Yangi operatsiya",
    description="Daromad yoki xarajat operatsiyasi qo'shish. MANAGER+ talab.",
)
async def create_transaction(
    db:   DB,
    user: CurrentManager,
    data: FinanceTransactionCreate,
) -> FinanceTransactionResponse:
    """Yangi moliyaviy operatsiya yaratish."""
    return await FinanceService(db).create(data, created_by=user.id)


@router.get(
    "/transactions/{tx_id}",
    response_model=FinanceTransactionResponse,
    summary="Bitta operatsiya",
)
async def get_transaction(
    db:    DB,
    user:  CurrentUser,
    tx_id: int,
) -> FinanceTransactionResponse:
    """ID bo'yicha bitta operatsiya."""
    return await FinanceService(db).get_by_id(tx_id)


@router.patch(
    "/transactions/{tx_id}",
    response_model=FinanceTransactionResponse,
    summary="Operatsiyani tahrirlash",
    description="Mavjud operatsiyaning istalgan maydonini yangilash. MANAGER+ talab.",
)
async def update_transaction(
    db:    DB,
    user:  CurrentManager,
    tx_id: int,
    data:  FinanceTransactionUpdate,
) -> FinanceTransactionResponse:
    """Operatsiyani yangilash."""
    return await FinanceService(db).update(tx_id, data)


@router.delete(
    "/transactions/{tx_id}",
    status_code=204,
    summary="Operatsiyani o'chirish",
    description="Moliyaviy operatsiyani butunlay o'chirish. MANAGER+ talab.",
)
async def delete_transaction(
    db:    DB,
    user:  CurrentManager,
    tx_id: int,
) -> None:
    """Operatsiyani o'chirish."""
    await FinanceService(db).delete(tx_id)


# =============================================================================
# ANALYTICS
# =============================================================================

@router.get(
    "/summary",
    response_model=FinanceSummary,
    summary="Moliyaviy xulosa",
    description=(
        "Dashboard uchun asosiy ko'rsatkichlar: jami daromad, xarajat, foyda, ROI, "
        "kategoriya taqsimoti va o'tgan davr bilan taqqoslash."
    ),
)
async def get_summary(
    db:        DB,
    user:      CurrentUser,
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi"),
    date_to:   Optional[date] = Query(None, description="Tugash sanasi"),
) -> FinanceSummary:
    """
    Moliyaviy xulosa.

    Agar sana berilmasa — joriy oy ishlatiladi.
    """
    today = date.today()
    if not date_from:
        date_from = today.replace(day=1)
    if not date_to:
        date_to = today
    return await FinanceService(db).get_summary(date_from, date_to)


@router.get(
    "/trends",
    response_model=FinanceTrends,
    summary="Oylik trendlar",
    description="Oxirgi N oy bo'yicha daromad/xarajat/foyda trendi (6 yoki 12 oy).",
)
async def get_trends(
    db:     DB,
    user:   CurrentUser,
    months: int = Query(12, ge=3, le=24, description="Necha oy ko'rsatilsin"),
) -> FinanceTrends:
    """Oylik moliyaviy trendlar."""
    return await FinanceService(db).get_monthly_trends(months=months)


@router.get(
    "/roi",
    response_model=ROIReport,
    summary="Jonivorlar ROI hisoboti",
    description=(
        "Har bir jonivor uchun daromad/xarajat/ROI tahlili. "
        "Jonivorga bog'liq bo'lmagan operatsiyalar alohida ko'rsatiladi."
    ),
)
async def get_roi_report(
    db:        DB,
    user:      CurrentUser,
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi"),
    date_to:   Optional[date] = Query(None, description="Tugash sanasi"),
) -> ROIReport:
    """
    Jonivorlar bo'yicha ROI hisoboti.

    Agar sana berilmasa — joriy yil ishlatiladi.
    """
    today     = date.today()
    date_from = date_from or today.replace(month=1, day=1)
    date_to   = date_to   or today
    return await FinanceService(db).get_roi_report(date_from, date_to)