"""
Taurus Vision — Feed Management API Endpoints (Sprint 20)

STOCK:
    GET    /feed/stocks/           — Barcha zaxiralar
    POST   /feed/stocks/           — Yangi zaxira (manager+)
    GET    /feed/stocks/stats      — Dashboard statistikasi
    GET    /feed/stocks/{id}       — Bitta zaxira
    PATCH  /feed/stocks/{id}       — Tahrirlash (manager+)
    POST   /feed/stocks/{id}/restock — Ombonga qo'shish (manager+)

RECORDS:
    GET    /feed/records/          — Oziqlantiruv tarixi
    POST   /feed/records/          — Yangi oziqlantiruv yozuvi
"""

import logging
from datetime import datetime
from typing import Optional, Annotated

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, require_manager
from app.core.database import get_db
from app.models.feed import FeedType
from app.models.user import User
from app.schemas.feed import (
    FeedStockCreate, FeedStockUpdate, FeedStockRestock,
    FeedStockResponse, FeedStockListResponse,
    FeedRecordCreate, FeedRecordResponse, FeedRecordListResponse,
    FeedStats,
)
from app.services.feed_service import FeedService

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/feed", tags=["Feed Management"])

CurrentUser    = Annotated[User, Depends(get_current_active_user)]
CurrentManager = Annotated[User, Depends(require_manager)]
DB             = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# STOCK
# =============================================================================

@router.get("/stocks/", response_model=FeedStockListResponse)
async def list_stocks(
    db:          DB,
    user:        CurrentUser,
    active_only: bool              = Query(True),
    feed_type:   Optional[FeedType] = Query(None),
    low_only:    bool              = Query(False, description="Faqat kam bo'lganlar"),
) -> FeedStockListResponse:
    """Barcha ozuqa zaxiralari."""
    return await FeedService(db).list_stocks(
        active_only=active_only,
        feed_type=feed_type,
        low_only=low_only,
    )


@router.get("/stocks/stats", response_model=FeedStats)
async def get_feed_stats(db: DB, user: CurrentUser) -> FeedStats:
    """Dashboard uchun ozuqa statistikasi — inventar + iste'mol trendlari."""
    return await FeedService(db).get_stats()


@router.post("/stocks/", response_model=FeedStockResponse, status_code=201)
async def create_stock(
    db:   DB,
    user: CurrentManager,
    data: FeedStockCreate = Body(...),
) -> FeedStockResponse:
    """Yangi ozuqa zaxirasi. Faqat manager/admin."""
    return await FeedService(db).create_stock(data)


@router.get("/stocks/{stock_id}", response_model=FeedStockResponse)
async def get_stock(stock_id: int, db: DB, user: CurrentUser) -> FeedStockResponse:
    """Bitta ozuqa zaxirasi."""
    return await FeedService(db).get_stock(stock_id)


@router.patch("/stocks/{stock_id}", response_model=FeedStockResponse)
async def update_stock(
    stock_id: int,
    db:       DB,
    user:     CurrentManager,
    data:     FeedStockUpdate = Body(...),
) -> FeedStockResponse:
    """Zaxira ma'lumotlarini yangilash. Miqdor uchun /restock ishlatilsin."""
    return await FeedService(db).update_stock(stock_id, data)


@router.post("/stocks/{stock_id}/restock", response_model=FeedStockResponse)
async def restock(
    stock_id: int,
    db:       DB,
    user:     CurrentManager,
    data:     FeedStockRestock = Body(...),
) -> FeedStockResponse:
    """
    Ombonga qo'shish (kirim).

    current_kg += quantity_kg.
    Yetkazib beruvchi va narx ixtiyoriy yangilanadi.
    """
    return await FeedService(db).restock(stock_id, data)


# =============================================================================
# RECORDS
# =============================================================================

@router.get("/records/", response_model=FeedRecordListResponse)
async def list_records(
    db:        DB,
    user:      CurrentUser,
    stock_id:  Optional[int] = Query(None),
    animal_id: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date:   Optional[datetime] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> FeedRecordListResponse:
    """
    Oziqlantiruv tarixi.

    Filtrlar: stock_id, animal_id, from_date, to_date.
    Sahifalangan, yangi → eski tartibda.
    """
    return await FeedService(db).list_records(
        stock_id=stock_id,
        animal_id=animal_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )


@router.post("/records/", response_model=FeedRecordResponse, status_code=201)
async def add_record(
    db:   DB,
    user: CurrentUser,
    data: FeedRecordCreate = Body(...),
) -> FeedRecordResponse:
    """
    Oziqlantiruv yozuvi qo'shish.

    FeedStock.current_kg avtomatik kamayadi.
    Yetarli miqdor bo'lmasa — 400 qaytadi.
    Har qanday autentifikatsiyalangan foydalanuvchi amalga oshirishi mumkin.
    """
    return await FeedService(db).add_record(data, fed_by=user.id)