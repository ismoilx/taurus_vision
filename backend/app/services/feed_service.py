"""
Taurus Vision — Feed Management Service (Sprint 20)

JAVOBGARLIK:
    - Ozuqa zaxirasini boshqarish (kirim/chiqim)
    - Oziqlantiruv yozuvlarini saqlash + FeedStock.current_kg kamaytirish
    - Low stock va muddati o'tish alertlari
    - Statistika

KRITIK QOIDALAR:
    1. FeedRecord yaratilganda FeedStock.current_kg ATOMIK kamayishi kerak
       → service ichida bir tranzaksiyada bajariladi
    2. current_kg manfiy bo'lib qolmasin
       → BusinessRuleViolationError (yetarli emas)
    3. Low stock alert — har bir zaxira uchun faqat bir marta
       → FeedStock.low_stock_alerted flagi
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import FeedStock, FeedRecord, FeedType
from app.models.animal import Animal
from app.models.user import User
from app.repositories.feed_repository import FeedStockRepository, FeedRecordRepository
from app.schemas.feed import (
    FeedStockCreate, FeedStockUpdate, FeedStockRestock,
    FeedStockResponse, FeedStockListResponse,
    FeedRecordCreate, FeedRecordResponse, FeedRecordListResponse,
    FeedStats, DailyConsumption,
)
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

logger = logging.getLogger(__name__)


class FeedService:
    """
    Ozuqa boshqaruvi servisi.

    Usage:
        svc = FeedService(db)
        stock = await svc.create_stock(data)
        record = await svc.add_record(data, fed_by=user.id)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self._stocks    = FeedStockRepository(db)
        self._records   = FeedRecordRepository(db)

    # =========================================================================
    # STOCK — zaxira boshqaruvi
    # =========================================================================

    async def create_stock(
        self,
        data: FeedStockCreate,
    ) -> FeedStockResponse:
        """Yangi ozuqa zaxirasi yaratish."""
        stock = FeedStock(
            feed_type        = data.feed_type,
            name             = data.name,
            description      = data.description,
            unit             = data.unit,
            current_kg       = data.current_kg,
            min_threshold_kg = data.min_threshold_kg,
            unit_cost_uzs    = data.unit_cost_uzs,
            supplier         = data.supplier,
            purchase_date    = data.purchase_date,
            expiry_date      = data.expiry_date,
            notes            = data.notes,
        )
        saved = await self._stocks.create(stock)
        await self.db.commit()

        logger.info(
            f"[feed] Stock created | id={saved.id} | "
            f"type={saved.feed_type} | kg={saved.current_kg:.1f}"
        )
        return FeedStockResponse.model_validate(saved)

    async def get_stock(self, stock_id: int) -> FeedStockResponse:
        stock = await self._stocks.get_by_id(stock_id)
        if stock is None:
            raise EntityNotFoundError(f"Ozuqa zaxirasi ID={stock_id} topilmadi.")
        return FeedStockResponse.model_validate(stock)

    async def list_stocks(
        self,
        active_only: bool = True,
        feed_type:   Optional[FeedType] = None,
        low_only:    bool = False,
    ) -> FeedStockListResponse:
        stocks = await self._stocks.get_all(
            active_only=active_only,
            feed_type=feed_type,
            low_only=low_only,
        )
        items      = [FeedStockResponse.model_validate(s) for s in stocks]
        low_count  = sum(1 for s in stocks if s.is_low)
        exp_count  = sum(1 for s in stocks if s.is_expired)
        total_val  = sum(s.total_value_uzs or 0 for s in stocks) or None

        return FeedStockListResponse(
            items            = items,
            total            = len(items),
            low_stock_count  = low_count,
            expired_count    = exp_count,
            total_value_uzs  = total_val,
        )

    async def update_stock(
        self,
        stock_id: int,
        data:     FeedStockUpdate,
    ) -> FeedStockResponse:
        stock = await self._stocks.get_by_id(stock_id)
        if stock is None:
            raise EntityNotFoundError(f"Ozuqa zaxirasi ID={stock_id} topilmadi.")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(stock, field, value)

        # Agar yana to'ldirgan bo'lsa — alert flagini qaytarish
        if not stock.is_low and stock.low_stock_alerted:
            stock.low_stock_alerted = False

        saved = await self._stocks.save(stock)
        await self.db.commit()

        logger.info(f"[feed] Stock updated | id={stock_id}")
        return FeedStockResponse.model_validate(saved)

    async def restock(
        self,
        stock_id: int,
        data:     FeedStockRestock,
    ) -> FeedStockResponse:
        """
        Ombonga qo'shish (kirim).

        current_kg += data.quantity_kg
        Agar kirim narxi yoki yetkazib beruvchi berilsa — yangilanadi.
        """
        stock = await self._stocks.get_by_id(stock_id)
        if stock is None:
            raise EntityNotFoundError(f"Ozuqa zaxirasi ID={stock_id} topilmadi.")

        old_kg        = stock.current_kg
        stock.current_kg += data.quantity_kg

        if data.unit_cost_uzs is not None:
            stock.unit_cost_uzs = data.unit_cost_uzs
        if data.supplier:
            stock.supplier = data.supplier
        if data.purchase_date:
            stock.purchase_date = data.purchase_date
        if data.expiry_date:
            stock.expiry_date = data.expiry_date
        if data.notes:
            stock.notes = data.notes

        # To'ldirildi — alert flagini reset
        if not stock.is_low:
            stock.low_stock_alerted = False

        saved = await self._stocks.save(stock)
        await self.db.commit()

        logger.info(
            f"[feed] Restock | id={stock_id} | "
            f"{old_kg:.1f} → {saved.current_kg:.1f} kg (+{data.quantity_kg:.1f})"
        )
        return FeedStockResponse.model_validate(saved)

    # =========================================================================
    # RECORD — oziqlantiruv hodisasi
    # =========================================================================

    async def add_record(
        self,
        data:   FeedRecordCreate,
        fed_by: Optional[int] = None,
    ) -> FeedRecordResponse:
        """
        Oziqlantiruv yozuvini saqlash + FeedStock.current_kg kamaytirish.

        ATOMIK: ikkalasi bir tranzaksiyada.

        Raises:
            EntityNotFoundError:       stock yoki animal topilmasa
            BusinessRuleViolationError: yetarli ozuqa yo'q
        """
        # Stock tekshirish
        stock = await self._stocks.get_by_id(data.stock_id)
        if stock is None:
            raise EntityNotFoundError(f"Ozuqa zaxirasi ID={data.stock_id} topilmadi.")
        if not stock.is_active:
            raise BusinessRuleViolationError(
                f"'{stock.name}' zaxirasi arxivlangan. Avval faollashtiring."
            )

        # Yetarliligini tekshirish
        if stock.current_kg < data.quantity_kg:
            raise BusinessRuleViolationError(
                f"Yetarli ozuqa yo'q. "
                f"Mavjud: {stock.current_kg:.1f} kg, "
                f"so'ralgan: {data.quantity_kg:.1f} kg."
            )

        # Animal mavjudligini tekshirish
        if data.animal_id is not None:
            animal = await self.db.get(Animal, data.animal_id)
            if animal is None:
                raise EntityNotFoundError(f"Jonivor ID={data.animal_id} topilmadi.")

        # FeedRecord yaratish
        fed_at = data.fed_at or datetime.now(timezone.utc)
        record = FeedRecord(
            stock_id    = data.stock_id,
            animal_id   = data.animal_id,
            fed_by      = fed_by,
            quantity_kg = data.quantity_kg,
            fed_at      = fed_at,
            notes       = data.notes,
            meta        = data.meta,
        )
        saved_record = await self._records.create(record)

        # Stock miqdorini kamaytirish
        old_kg           = stock.current_kg
        stock.current_kg -= data.quantity_kg

        # Low stock alert kerakmi?
        alert_needed = stock.is_low and not stock.low_stock_alerted
        if alert_needed:
            stock.low_stock_alerted = True

        await self._stocks.save(stock)
        await self.db.commit()

        logger.info(
            f"[feed] Record added | id={saved_record.id} | "
            f"stock={stock.name} | "
            f"{old_kg:.1f} → {stock.current_kg:.1f} kg "
            f"(-{data.quantity_kg:.1f}) | "
            f"animal={data.animal_id or 'herd'}"
        )

        if alert_needed:
            await self._send_low_stock_alert(stock)

        return self._enrich_record(saved_record)

    async def list_records(
        self,
        *,
        stock_id:  Optional[int] = None,
        animal_id: Optional[int] = None,
        fed_by:    Optional[int] = None,
        from_date: Optional[datetime] = None,
        to_date:   Optional[datetime] = None,
        page:      int = 1,
        page_size: int = 30,
    ) -> FeedRecordListResponse:
        page_size = min(page_size, 100)
        offset    = (page - 1) * page_size

        items, total = await self._records.get_list(
            stock_id=stock_id, animal_id=animal_id, fed_by=fed_by,
            from_date=from_date, to_date=to_date,
            limit=page_size, offset=offset,
        )
        total_kg    = sum(r.quantity_kg for r in items)
        total_pages = max(1, -(-total // page_size))

        return FeedRecordListResponse(
            items       = [self._enrich_record(r) for r in items],
            total       = total,
            total_kg    = round(total_kg, 2),
            page        = page,
            page_size   = page_size,
            total_pages = total_pages,
        )

    # =========================================================================
    # STATS
    # =========================================================================

    async def get_stats(self) -> FeedStats:
        now        = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start  = today_start - timedelta(days=6)

        stock_stats   = await self._stocks.get_stats()
        consumed_today = await self._records.get_consumed_kg(today_start, now)
        consumed_week  = await self._records.get_consumed_kg(week_start, now)
        daily_trend    = await self._records.get_daily_consumption(days=7)

        return FeedStats(
            total_stocks        = stock_stats["total_stocks"],
            active_stocks       = stock_stats["active_stocks"],
            low_stock_count     = stock_stats["low_stock_count"],
            expired_count       = stock_stats["expired_count"],
            total_inventory_kg  = round(stock_stats["total_inventory_kg"], 1),
            total_value_uzs     = stock_stats["total_value_uzs"],
            consumed_today_kg   = round(consumed_today, 1),
            consumed_this_week_kg = round(consumed_week, 1),
            low_stocks          = [
                FeedStockResponse.model_validate(s)
                for s in stock_stats["low_stocks"]
            ],
            daily_trend         = [
                DailyConsumption(**d) for d in daily_trend
            ],
        )

    # =========================================================================
    # CELERY — low stock check
    # =========================================================================

    async def check_low_stock_alerts(self) -> dict:
        """
        Barcha aktiv zaxiralarni tekshirib, kam bo'lganlarga alert yuborish.
        Celery task tomonidan har 08:00 da chaqiriladi.

        Returns:
            {"checked": int, "alerts_sent": int, "reset": int}
        """
        low_stocks = await self._stocks.get_low_stock()
        alerts_sent = 0

        for stock in low_stocks:
            if not stock.low_stock_alerted:
                stock.low_stock_alerted = True
                await self._send_low_stock_alert(stock)
                alerts_sent += 1

        # To'ldirilgan zaxiralar uchun flagni reset
        reset = await self._stocks.reset_low_stock_flags()

        if alerts_sent or reset:
            await self.db.commit()

        logger.info(
            f"[feed] Low stock check | "
            f"low={len(low_stocks)} | alerts={alerts_sent} | reset={reset}"
        )
        return {
            "checked":    len(low_stocks),
            "alerts_sent": alerts_sent,
            "reset":       reset,
        }

    # =========================================================================
    # PRIVATE
    # =========================================================================

    def _enrich_record(self, record: FeedRecord) -> FeedRecordResponse:
        """FeedRecord → FeedRecordResponse (joined ma'lumotlar bilan)."""
        resp = FeedRecordResponse.model_validate(record)

        if record.stock:
            resp.stock_name = record.stock.name
            resp.feed_type  = record.stock.feed_type.value

        if record.animal:
            resp.animal_tag_id = getattr(record.animal, "tag_id", None)

        if record.feeder:
            resp.feeder_name = getattr(record.feeder, "full_name", None) \
                            or getattr(record.feeder, "username", None)

        return resp

    async def _send_low_stock_alert(self, stock: FeedStock) -> None:
        """Kam zaxira uchun alert yaratish."""
        try:
            from app.services.alert_service import AlertService
            from app.models.alert import AlertType, AlertSeverity

            pct        = stock.stock_percent
            is_critical = pct < 25

            await AlertService(self.db)._ensure_alert(
                animal_id   = None,
                alert_type  = AlertType.CUSTOM,
                title       = f"Ozuqa kam: {stock.name}",
                description = (
                    f"'{stock.name}' ({stock.feed_type.value}) zaxirasi "
                    f"minimal chegaradan past: "
                    f"{stock.current_kg:.1f} kg qoldi "
                    f"(chegara: {stock.min_threshold_kg:.1f} kg, "
                    f"{pct:.0f}%)."
                ),
                severity    = (
                    AlertSeverity.CRITICAL
                    if is_critical
                    else AlertSeverity.HIGH
                ),
                context={
                    "stock_id":       stock.id,
                    "stock_name":     stock.name,
                    "feed_type":      stock.feed_type.value,
                    "current_kg":     stock.current_kg,
                    "threshold_kg":   stock.min_threshold_kg,
                    "stock_percent":  pct,
                    "source":         "feed_service",
                },
            )
        except Exception as exc:
            logger.error(f"[feed] Low stock alert xatosi: stock={stock.id} | {exc}")