"""
Taurus Vision — Finance Service

JAVOBGARLIK:
    - Moliyaviy operatsiyalarni CRUD
    - Dashboard summary hisoblash
    - Oylik trendlar
    - Jonivorlar ROI hisoboti
    - O'tgan davr bilan taqqoslash

QOIDALAR:
    1. Barcha hisob-kitoblar bu yerda — Repository faqat DB dan o'qiydi.
    2. amount_uzs har doim musbat saqlanadi — type field belgini belgilaydi.
    3. ROI = (daromad - xarajat) / xarajat × 100 (xarajat 0 bo'lsa → 0.0).
    4. Kelajak sanaga operatsiya kiritib bo'lmaydi (schema darajasida).

CATEGORIES LABELS (O'zbek):
    expense: feed → Yem, veterinary → Veterinariya, equipment → Uskunalar,
             labor → Mehnat, utilities → Kommunal, transport → Tashish, other → Boshqa
    income:  animal_sale → Jonivor sotish, milk_sale → Sut, meat_sale → Go'sht,
             wool_sale → Jun, subsidy → Subsidiya, other → Boshqa
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import FinanceTransaction, TransactionType
from app.repositories.finance_repository import FinanceRepository
from app.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionUpdate,
    FinanceTransactionResponse,
    FinanceTransactionListResponse,
    FinanceSummary,
    FinanceCategoryStat,
    FinanceTrends,
    MonthlyTrend,
    ROIReport,
    AnimalROI,
)
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Kategoriya nomlari (O'zbek tili)
# ---------------------------------------------------------------------------
EXPENSE_LABELS: dict[str, str] = {
    "feed":       "Yem va ozuqa",
    "veterinary": "Veterinariya",
    "equipment":  "Uskunalar",
    "labor":      "Mehnat",
    "utilities":  "Kommunal",
    "transport":  "Tashish",
    "other":      "Boshqa",
}

INCOME_LABELS: dict[str, str] = {
    "animal_sale": "Jonivor sotish",
    "milk_sale":   "Sut",
    "meat_sale":   "Go'sht",
    "wool_sale":   "Jun",
    "subsidy":     "Subsidiya",
    "other":       "Boshqa",
}

MONTH_LABELS_UZ = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]


def _roi(income: int, expense: int) -> float:
    """ROI foiz. Xarajat 0 bo'lsa → 0.0."""
    if expense == 0:
        return 0.0
    return round((income - expense) / expense * 100, 2)


def _pct_change(new: int, old: int) -> Optional[float]:
    """Foiz o'zgarish. old=0 → None."""
    if old == 0:
        return None
    return round((new - old) / old * 100, 1)


def _tx_to_response(tx: FinanceTransaction) -> FinanceTransactionResponse:
    """ORM → Response schema."""
    return FinanceTransactionResponse(
        id               = tx.id,
        type             = tx.type,
        category         = tx.category,
        amount_uzs       = tx.amount_uzs,
        amount_usd       = tx.amount_usd,
        description      = tx.description,
        notes            = tx.notes,
        transaction_date = tx.transaction_date,
        payment_method   = tx.payment_method,
        receipt_number   = tx.receipt_number,
        animal_id        = tx.animal_id,
        animal_tag       = tx.animal.tag_id       if tx.animal  else None,
        created_by       = tx.created_by,
        creator_name     = tx.creator.full_name   if tx.creator else None,
        meta             = tx.meta,
        created_at       = tx.created_at,
        updated_at       = tx.updated_at,
    )


class FinanceService:
    """
    Moliyaviy modul uchun asosiy servis.

    Usage:
        svc = FinanceService(db)
        tx  = await svc.create(data, created_by=user.id)
        summary = await svc.get_summary(date_from, date_to)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = FinanceRepository(db)

    # =========================================================================
    # CRUD
    # =========================================================================

    async def create(
        self,
        data:       FinanceTransactionCreate,
        created_by: Optional[int] = None,
    ) -> FinanceTransactionResponse:
        """
        Yangi operatsiya yaratish.

        Args:
            data:       validated request body
            created_by: joriy foydalanuvchi ID

        Returns:
            FinanceTransactionResponse

        Raises:
            BusinessRuleViolationError: kelajak sana
        """
        try:
            tx = FinanceTransaction(
                type             = data.type,
                category         = data.category,
                amount_uzs       = data.amount_uzs,
                amount_usd       = data.amount_usd,
                description      = data.description,
                notes            = data.notes,
                transaction_date = data.transaction_date,
                payment_method   = data.payment_method,
                receipt_number   = data.receipt_number,
                animal_id        = data.animal_id,
                meta             = data.meta,
                created_by       = created_by,
            )
            saved = await self.repo.create(tx)
            # Relationships yuklash uchun qayta o'qish
            saved = await self.repo.get_by_id(saved.id)
            logger.info(
                "Finance transaction created",
                extra={"extra_data": {
                    "id": saved.id, "type": saved.type,
                    "amount": saved.amount_uzs, "by": created_by,
                }},
            )
            return _tx_to_response(saved)
        except Exception as exc:
            logger.error(f"create finance tx error: {exc}")
            raise

    async def get_by_id(self, tx_id: int) -> FinanceTransactionResponse:
        """
        ID bo'yicha operatsiya.

        Raises:
            EntityNotFoundError: topilmasa
        """
        tx = await self.repo.get_by_id(tx_id)
        if not tx:
            raise EntityNotFoundError(f"Operatsiya #{tx_id} topilmadi")
        return _tx_to_response(tx)

    async def list_transactions(
        self,
        *,
        type:       Optional[str]  = None,
        category:   Optional[str]  = None,
        animal_id:  Optional[int]  = None,
        date_from:  Optional[date] = None,
        date_to:    Optional[date] = None,
        page:       int            = 1,
        size:       int            = 20,
    ) -> FinanceTransactionListResponse:
        """
        Filtrlangan va sahifalangan ro'yxat.

        Args:
            type:      "income" | "expense" | None
            category:  kategoriya string | None
            animal_id: jonivor ID | None
            date_from: boshlanish sanasi
            date_to:   tugash sanasi
            page:      sahifa (1 dan boshlaydi)
            size:      sahifa hajmi (max 100)

        Returns:
            FinanceTransactionListResponse
        """
        size     = min(size, 100)
        items, total = await self.repo.list_paginated(
            type      = type,
            category  = category,
            animal_id = animal_id,
            date_from = date_from,
            date_to   = date_to,
            page      = page,
            size      = size,
        )
        pages = max(1, math.ceil(total / size))
        return FinanceTransactionListResponse(
            items = [_tx_to_response(tx) for tx in items],
            total = total,
            page  = page,
            size  = size,
            pages = pages,
        )

    async def update(
        self,
        tx_id:   int,
        data:    FinanceTransactionUpdate,
    ) -> FinanceTransactionResponse:
        """
        Operatsiyani yangilash.

        Raises:
            EntityNotFoundError: topilmasa
        """
        tx = await self.repo.get_by_id(tx_id)
        if not tx:
            raise EntityNotFoundError(f"Operatsiya #{tx_id} topilmadi")

        fields = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
        updated = await self.repo.update(tx, fields)
        updated = await self.repo.get_by_id(updated.id)
        logger.info(f"Finance tx #{tx_id} updated: {list(fields.keys())}")
        return _tx_to_response(updated)

    async def delete(self, tx_id: int) -> None:
        """
        Operatsiyani o'chirish.

        Raises:
            EntityNotFoundError: topilmasa
        """
        tx = await self.repo.get_by_id(tx_id)
        if not tx:
            raise EntityNotFoundError(f"Operatsiya #{tx_id} topilmadi")
        await self.repo.delete(tx)
        logger.info(f"Finance tx #{tx_id} deleted")

    # =========================================================================
    # SUMMARY
    # =========================================================================

    async def get_summary(
        self,
        date_from: date,
        date_to:   date,
    ) -> FinanceSummary:
        """
        Davr uchun moliyaviy xulosa.

        Includes:
            - Jami daromad, xarajat, foyda, ROI
            - Kategoriya taqsimoti
            - O'tgan davr bilan taqqoslash

        Args:
            date_from: davr boshlanishi
            date_to:   davr tugashi (inclusive)

        Returns:
            FinanceSummary
        """
        # Joriy davr
        totals  = await self.repo.get_period_totals(date_from, date_to)
        income  = totals["income"]
        expense = totals["expense"]
        profit  = income - expense
        roi     = _roi(income, expense)

        # Kategoriyalar
        exp_cats = await self.repo.get_category_breakdown("expense", date_from, date_to)
        inc_cats = await self.repo.get_category_breakdown("income",  date_from, date_to)

        def make_cat_stats(rows: list[dict], labels: dict, total: int) -> list[FinanceCategoryStat]:
            result = []
            for r in rows:
                pct = round(r["amount"] / total * 100, 1) if total > 0 else 0.0
                result.append(FinanceCategoryStat(
                    category   = r["category"],
                    label      = labels.get(r["category"], r["category"].replace("_", " ").title()),
                    amount_uzs = r["amount"],
                    percent    = pct,
                    count      = r["count"],
                ))
            return result

        # O'tgan davr (xuddi shunday uzunlik)
        delta     = date_to - date_from
        prev_to   = date_from - relativedelta(days=1)
        prev_from = prev_to - delta
        prev      = await self.repo.get_period_totals(prev_from, prev_to)
        p_income  = prev["income"]
        p_expense = prev["expense"]
        p_profit  = p_income - p_expense

        # Davr nomi
        if date_from.month == date_to.month and date_from.year == date_to.year:
            period_label = f"{MONTH_LABELS_UZ[date_from.month]} {date_from.year}"
        else:
            period_label = f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"

        return FinanceSummary(
            period_label         = period_label,
            date_from            = date_from,
            date_to              = date_to,
            total_income         = income,
            total_expense        = expense,
            net_profit           = profit,
            roi_percent          = roi,
            income_count         = totals["income_count"],
            expense_count        = totals["expense_count"],
            expense_by_category  = make_cat_stats(exp_cats, EXPENSE_LABELS, expense),
            income_by_category   = make_cat_stats(inc_cats, INCOME_LABELS,  income),
            prev_income          = p_income  if (p_income or p_expense) else None,
            prev_expense         = p_expense if (p_income or p_expense) else None,
            prev_profit          = p_profit  if (p_income or p_expense) else None,
            income_change_pct    = _pct_change(income,  p_income)  if (p_income or p_expense) else None,
            expense_change_pct   = _pct_change(expense, p_expense) if (p_income or p_expense) else None,
            profit_change_pct    = _pct_change(profit,  p_profit)  if (p_income or p_expense) else None,
        )

    # =========================================================================
    # TRENDS
    # =========================================================================

    async def get_monthly_trends(self, months: int = 12) -> FinanceTrends:
        """
        Oxirgi N oy bo'yicha oylik trendlar.

        Args:
            months: necha oy (6 yoki 12)

        Returns:
            FinanceTrends
        """
        rows = await self.repo.get_monthly_trends(months=months)

        # Strukturalash: {(year, month): {"income": int, "expense": int}}
        bucket: dict[tuple[int, int], dict[str, int]] = {}
        for r in rows:
            key = (r["year"], r["month"])
            if key not in bucket:
                bucket[key] = {"income": 0, "expense": 0}
            bucket[key][r["type"]] = r["total"]

        # Barcha oylarni to'ldirish (ma'lumot yo'q oylar ham 0 bilan)
        from dateutil.relativedelta import relativedelta as rd
        today     = date.today()
        first_day = today.replace(day=1) - rd(months=months - 1)

        trend_list = []
        total_income = total_expense = 0
        cur = first_day
        while cur <= today:
            key     = (cur.year, cur.month)
            inc     = bucket.get(key, {}).get("income",  0)
            exp     = bucket.get(key, {}).get("expense", 0)
            profit  = inc - exp
            total_income  += inc
            total_expense += exp

            trend_list.append(MonthlyTrend(
                month       = f"{cur.year}-{cur.month:02d}",
                month_label = f"{MONTH_LABELS_UZ[cur.month]} {cur.year}",
                income      = inc,
                expense     = exp,
                profit      = profit,
            ))
            cur = (cur + rd(months=1)).replace(day=1)

        return FinanceTrends(
            months        = trend_list,
            total_income  = total_income,
            total_expense = total_expense,
            total_profit  = total_income - total_expense,
        )

    # =========================================================================
    # ROI REPORT
    # =========================================================================

    async def get_roi_report(
        self,
        date_from: date,
        date_to:   date,
    ) -> ROIReport:
        """
        Jonivorlar bo'yicha ROI hisoboti.

        Jonivorga bog'liq bo'lmagan operatsiyalar "ferma umumiy" sifatida ajratiladi.

        Returns:
            ROIReport
        """
        # Barcha jonivor totallari
        animal_rows = await self.repo.get_animal_totals(date_from, date_to)

        # Jonivorlar ma'lumoti
        animals_list = await self.repo.get_animals_with_transactions(date_from, date_to)
        animals_map  = {a.id: a for a in animals_list}

        # animal_id → {income, expense, tx_count}
        animal_agg: dict[int, dict] = {}
        for r in animal_rows:
            aid = r["animal_id"]
            if aid not in animal_agg:
                animal_agg[aid] = {"income": 0, "expense": 0, "tx_count": 0}
            animal_agg[aid][r["type"]] += r["total"]
            animal_agg[aid]["tx_count"] += r["count"]

        roi_list: list[AnimalROI] = []
        for aid, agg in animal_agg.items():
            animal = animals_map.get(aid)
            roi_list.append(AnimalROI(
                animal_id    = aid,
                tag_id       = animal.tag_id if animal else f"#{aid}",
                species      = animal.species if animal else "unknown",
                total_income = agg["income"],
                total_expense= agg["expense"],
                net_profit   = agg["income"] - agg["expense"],
                roi_percent  = _roi(agg["income"], agg["expense"]),
                tx_count     = agg["tx_count"],
            ))

        # ROI bo'yicha tartiblash (eng yaxshi birinchi)
        roi_list.sort(key=lambda x: x.roi_percent, reverse=True)

        # Ferma umumiy (animal_id=None)
        all_totals   = await self.repo.get_period_totals(date_from, date_to)
        animal_income = sum(a.total_income  for a in roi_list)
        animal_expense= sum(a.total_expense for a in roi_list)
        farm_income  = all_totals["income"]  - animal_income
        farm_expense = all_totals["expense"] - animal_expense
        total_income = all_totals["income"]
        total_expense= all_totals["expense"]

        return ROIReport(
            date_from     = date_from,
            date_to       = date_to,
            animals       = roi_list,
            farm_income   = max(farm_income,  0),
            farm_expense  = max(farm_expense, 0),
            total_income  = total_income,
            total_expense = total_expense,
            total_profit  = total_income - total_expense,
            overall_roi   = _roi(total_income, total_expense),
        )