"""
Taurus Vision — Feed Repository (Sprint 20)

Faqat DB operatsiyalari. Biznes logika FeedService da.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_, func, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.feed import FeedStock, FeedRecord, FeedType
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class FeedStockRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, stock: FeedStock) -> FeedStock:
        try:
            self.db.add(stock)
            await self.db.flush()
            await self.db.refresh(stock)
            return stock
        except Exception as exc:
            raise DatabaseError(f"FeedStock yaratishda xato: {exc}") from exc

    async def get_by_id(self, stock_id: int) -> Optional[FeedStock]:
        result = await self.db.execute(
            select(FeedStock).where(FeedStock.id == stock_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        active_only: bool = True,
        feed_type:   Optional[FeedType] = None,
        low_only:    bool = False,
    ) -> list[FeedStock]:
        filters = []
        if active_only:
            filters.append(FeedStock.is_active == True)
        if feed_type:
            filters.append(FeedStock.feed_type == feed_type)

        query = select(FeedStock)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(FeedStock.feed_type.asc(), FeedStock.name.asc())

        result = await self.db.execute(query)
        stocks = list(result.scalars().all())

        if low_only:
            stocks = [s for s in stocks if s.is_low]
        return stocks

    async def get_low_stock(self) -> list[FeedStock]:
        """Minimal chegaradan past barcha aktiv zaxiralar."""
        result = await self.db.execute(
            select(FeedStock).where(
                and_(
                    FeedStock.is_active == True,
                    FeedStock.current_kg < FeedStock.min_threshold_kg,
                )
            ).order_by(FeedStock.current_kg.asc())
        )
        return list(result.scalars().all())

    async def get_expiring_soon(self, within_days: int = 7) -> list[FeedStock]:
        """Yaqin kunlarda muddati tugaydigan zaxiralar."""
        now    = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=within_days)
        result = await self.db.execute(
            select(FeedStock).where(
                and_(
                    FeedStock.is_active == True,
                    FeedStock.expiry_date.isnot(None),
                    FeedStock.expiry_date <= cutoff,
                    FeedStock.expiry_date >= now,
                )
            ).order_by(FeedStock.expiry_date.asc())
        )
        return list(result.scalars().all())

    async def save(self, stock: FeedStock) -> FeedStock:
        try:
            await self.db.flush()
            await self.db.refresh(stock)
            return stock
        except Exception as exc:
            raise DatabaseError(f"FeedStock saqlashda xato: {exc}") from exc

    async def reset_low_stock_flags(self) -> int:
        """Stok to'ldirilgan zaxiralar uchun low_stock_alerted ni False ga qaytarish."""
        result = await self.db.execute(
            update(FeedStock)
            .where(
                and_(
                    FeedStock.low_stock_alerted == True,
                    FeedStock.current_kg >= FeedStock.min_threshold_kg,
                )
            )
            .values(low_stock_alerted=False)
            .returning(FeedStock.id)
        )
        return len(result.fetchall())

    async def get_stats(self) -> dict:
        """Ombor umumiy statistikasi."""
        all_stocks = await self.get_all(active_only=False)
        active     = [s for s in all_stocks if s.is_active]
        low        = [s for s in active if s.is_low]
        expired    = [s for s in active if s.is_expired]

        total_kg  = sum(s.current_kg for s in active)
        total_val = sum(s.total_value_uzs or 0 for s in active) or None

        return {
            "total_stocks":       len(all_stocks),
            "active_stocks":      len(active),
            "low_stock_count":    len(low),
            "expired_count":      len(expired),
            "total_inventory_kg": total_kg,
            "total_value_uzs":    total_val,
            "low_stocks":         sorted(low, key=lambda s: s.current_kg)[:5],
        }


class FeedRecordRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, record: FeedRecord) -> FeedRecord:
        try:
            self.db.add(record)
            await self.db.flush()
            await self.db.refresh(record)
            return record
        except Exception as exc:
            raise DatabaseError(f"FeedRecord yaratishda xato: {exc}") from exc

    async def get_list(
        self,
        *,
        stock_id:   Optional[int] = None,
        animal_id:  Optional[int] = None,
        fed_by:     Optional[int] = None,
        from_date:  Optional[datetime] = None,
        to_date:    Optional[datetime] = None,
        limit:      int = 50,
        offset:     int = 0,
    ) -> tuple[list[FeedRecord], int]:
        filters = []
        if stock_id  is not None: filters.append(FeedRecord.stock_id  == stock_id)
        if animal_id is not None: filters.append(FeedRecord.animal_id == animal_id)
        if fed_by    is not None: filters.append(FeedRecord.fed_by    == fed_by)
        if from_date:             filters.append(FeedRecord.fed_at    >= from_date)
        if to_date:               filters.append(FeedRecord.fed_at    <= to_date)

        where = and_(*filters) if filters else True

        total = await self.db.scalar(
            select(func.count(FeedRecord.id)).where(where)
        ) or 0

        result = await self.db.execute(
            select(FeedRecord)
            .options(
                selectinload(FeedRecord.stock),
                selectinload(FeedRecord.animal),
                selectinload(FeedRecord.feeder),
            )
            .where(where)
            .order_by(desc(FeedRecord.fed_at))
            .limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def get_consumed_kg(
        self,
        from_date: datetime,
        to_date:   datetime,
    ) -> float:
        """Berilgan davr ichida jami iste'mol (kg)."""
        result = await self.db.scalar(
            select(func.coalesce(func.sum(FeedRecord.quantity_kg), 0.0))
            .where(
                and_(
                    FeedRecord.fed_at >= from_date,
                    FeedRecord.fed_at <= to_date,
                )
            )
        )
        return float(result or 0.0)

    async def get_daily_consumption(self, days: int = 7) -> list[dict]:
        """So'nggi N kunlik kunlik iste'mol."""
        from sqlalchemy import cast, Date as SQLDate

        now   = datetime.now(timezone.utc)
        since = now - timedelta(days=days)

        result = await self.db.execute(
            select(
                cast(FeedRecord.fed_at, SQLDate).label("date"),
                FeedRecord.stock_id,
                func.sum(FeedRecord.quantity_kg).label("total_kg"),
            )
            .join(FeedStock, FeedRecord.stock_id == FeedStock.id)
            .add_columns(FeedStock.feed_type)
            .where(FeedRecord.fed_at >= since)
            .group_by(
                cast(FeedRecord.fed_at, SQLDate),
                FeedRecord.stock_id,
                FeedStock.feed_type,
            )
            .order_by(cast(FeedRecord.fed_at, SQLDate).asc())
        )
        rows = result.fetchall()

        # Kunlar bo'yicha agregatsiya
        daily: dict[str, dict] = {}
        for row in rows:
            date_str = str(row.date)
            if date_str not in daily:
                daily[date_str] = {"date": date_str, "total_kg": 0.0, "by_type": {}}
            daily[date_str]["total_kg"]               += float(row.total_kg)
            ft = str(row.feed_type)
            daily[date_str]["by_type"][ft]             = daily[date_str]["by_type"].get(ft, 0.0) + float(row.total_kg)

        return list(daily.values())