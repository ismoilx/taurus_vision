"""
Taurus Vision — Finance Repository

JAVOBGARLIK: Faqat DB operatsiyalari (SELECT / INSERT / UPDATE / DELETE).
Biznes logika FinanceService da.

MUHIM:
    - Barcha metodlar async.
    - N+1 muammosi yo'q — selectinload ishlatiladi.
    - Barcha xatolar DatabaseError ga wrap qilinadi.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import select, and_, func, desc, asc, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finance import FinanceTransaction, TransactionType
from app.models.animal import Animal
from app.models.user import User
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class FinanceRepository:
    """
    Moliyaviy operatsiyalar uchun repository.

    Usage:
        repo = FinanceRepository(db)
        tx   = await repo.create(transaction)
        txs  = await repo.list_paginated(type="expense", page=1, size=20)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, tx: FinanceTransaction) -> FinanceTransaction:
        """
        Yangi operatsiya yaratish.

        Args:
            tx: to'ldirilgan FinanceTransaction instance

        Returns:
            DB ga saqlangan instance (id va timestamp bilan)

        Raises:
            DatabaseError: saqlashda xato
        """
        try:
            self.db.add(tx)
            await self.db.flush()
            await self.db.refresh(tx)
            return tx
        except Exception as exc:
            raise DatabaseError(f"FinanceTransaction yaratishda xato: {exc}") from exc

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, tx_id: int) -> Optional[FinanceTransaction]:
        """
        ID bo'yicha bitta operatsiya.

        Returns:
            FinanceTransaction | None
        """
        result = await self.db.execute(
            select(FinanceTransaction)
            .options(
                selectinload(FinanceTransaction.animal),
                selectinload(FinanceTransaction.creator),
            )
            .where(FinanceTransaction.id == tx_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        type:       Optional[str]  = None,
        category:   Optional[str]  = None,
        animal_id:  Optional[int]  = None,
        date_from:  Optional[date] = None,
        date_to:    Optional[date] = None,
        page:       int            = 1,
        size:       int            = 20,
        order_desc: bool           = True,
    ) -> tuple[list[FinanceTransaction], int]:
        """
        Filtrlanган va sahifalangan ro'yxat.

        Returns:
            (items, total_count) tuple
        """
        filters = []
        if type:
            filters.append(FinanceTransaction.type == type)
        if category:
            filters.append(FinanceTransaction.category == category)
        if animal_id is not None:
            filters.append(FinanceTransaction.animal_id == animal_id)
        if date_from:
            filters.append(FinanceTransaction.transaction_date >= date_from)
        if date_to:
            filters.append(FinanceTransaction.transaction_date <= date_to)

        where_clause = and_(*filters) if filters else True

        # Total count
        count_q = select(func.count(FinanceTransaction.id)).where(where_clause)
        total   = (await self.db.execute(count_q)).scalar_one()

        # Items
        order = desc(FinanceTransaction.transaction_date) if order_desc \
            else asc(FinanceTransaction.transaction_date)

        items_q = (
            select(FinanceTransaction)
            .options(
                selectinload(FinanceTransaction.animal),
                selectinload(FinanceTransaction.creator),
            )
            .where(where_clause)
            .order_by(order, desc(FinanceTransaction.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        items = list((await self.db.execute(items_q)).scalars().all())
        return items, total

    async def get_period_totals(
        self,
        date_from: date,
        date_to:   date,
    ) -> dict:
        """
        Davr uchun jami daromad va xarajat.

        Returns:
            {"income": int, "expense": int, "income_count": int, "expense_count": int}
        """
        result = await self.db.execute(
            select(
                FinanceTransaction.type,
                func.sum(FinanceTransaction.amount_uzs).label("total"),
                func.count(FinanceTransaction.id).label("cnt"),
            )
            .where(
                and_(
                    FinanceTransaction.transaction_date >= date_from,
                    FinanceTransaction.transaction_date <= date_to,
                )
            )
            .group_by(FinanceTransaction.type)
        )
        rows = result.all()
        out = {"income": 0, "expense": 0, "income_count": 0, "expense_count": 0}
        for row in rows:
            if row.type == "income":
                out["income"]       = row.total or 0
                out["income_count"] = row.cnt   or 0
            else:
                out["expense"]       = row.total or 0
                out["expense_count"] = row.cnt   or 0
        return out

    async def get_category_breakdown(
        self,
        tx_type:   str,
        date_from: date,
        date_to:   date,
    ) -> list[dict]:
        """
        Kategoriya bo'yicha jamlanma.

        Returns:
            [{"category": str, "amount": int, "count": int}, ...]
        """
        result = await self.db.execute(
            select(
                FinanceTransaction.category,
                func.sum(FinanceTransaction.amount_uzs).label("amount"),
                func.count(FinanceTransaction.id).label("cnt"),
            )
            .where(
                and_(
                    FinanceTransaction.type == tx_type,
                    FinanceTransaction.transaction_date >= date_from,
                    FinanceTransaction.transaction_date <= date_to,
                )
            )
            .group_by(FinanceTransaction.category)
            .order_by(desc("amount"))
        )
        return [
            {"category": r.category, "amount": r.amount or 0, "count": r.cnt or 0}
            for r in result.all()
        ]

    async def get_monthly_trends(
        self,
        months: int = 12,
    ) -> list[dict]:
        """
        Oxirgi N oy bo'yicha oylik trend.

        Returns:
            [{"year": int, "month": int, "type": str, "total": int}, ...]
        """
        from datetime import date as dt_date
        from dateutil.relativedelta import relativedelta

        today     = dt_date.today()
        date_from = today.replace(day=1) - relativedelta(months=months - 1)

        result = await self.db.execute(
            select(
                extract("year",  FinanceTransaction.transaction_date).label("yr"),
                extract("month", FinanceTransaction.transaction_date).label("mo"),
                FinanceTransaction.type,
                func.sum(FinanceTransaction.amount_uzs).label("total"),
            )
            .where(FinanceTransaction.transaction_date >= date_from)
            .group_by("yr", "mo", FinanceTransaction.type)
            .order_by("yr", "mo")
        )
        return [
            {
                "year":  int(r.yr),
                "month": int(r.mo),
                "type":  r.type,
                "total": r.total or 0,
            }
            for r in result.all()
        ]

    async def get_animal_totals(
        self,
        date_from: date,
        date_to:   date,
    ) -> list[dict]:
        """
        Jonivorlar bo'yicha daromad/xarajat jamlanmasi.

        Returns:
            [{"animal_id": int, "type": str, "total": int, "count": int}, ...]
        """
        result = await self.db.execute(
            select(
                FinanceTransaction.animal_id,
                FinanceTransaction.type,
                func.sum(FinanceTransaction.amount_uzs).label("total"),
                func.count(FinanceTransaction.id).label("cnt"),
            )
            .where(
                and_(
                    FinanceTransaction.animal_id.isnot(None),
                    FinanceTransaction.transaction_date >= date_from,
                    FinanceTransaction.transaction_date <= date_to,
                )
            )
            .group_by(FinanceTransaction.animal_id, FinanceTransaction.type)
            .order_by(FinanceTransaction.animal_id)
        )
        return [
            {
                "animal_id": r.animal_id,
                "type":      r.type,
                "total":     r.total or 0,
                "count":     r.cnt   or 0,
            }
            for r in result.all()
        ]

    async def get_animals_with_transactions(
        self,
        date_from: date,
        date_to:   date,
    ) -> list[Animal]:
        """
        Operatsiyalarda ishtirok etgan jonivorlar.

        Returns:
            Animal instances ro'yxati
        """
        subq = (
            select(FinanceTransaction.animal_id.distinct())
            .where(
                and_(
                    FinanceTransaction.animal_id.isnot(None),
                    FinanceTransaction.transaction_date >= date_from,
                    FinanceTransaction.transaction_date <= date_to,
                )
            )
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(Animal).where(Animal.id.in_(subq))
        )
        return list(result.scalars().all())

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update(
        self,
        tx:     FinanceTransaction,
        fields: dict,
    ) -> FinanceTransaction:
        """
        Operatsiyani yangilash.

        Args:
            tx:     mavjud instance
            fields: yangilanadigan maydonlar dict

        Returns:
            yangilangan instance

        Raises:
            DatabaseError: yangilashda xato
        """
        try:
            for key, val in fields.items():
                if val is not None:
                    setattr(tx, key, val)
            await self.db.flush()
            await self.db.refresh(tx)
            return tx
        except Exception as exc:
            raise DatabaseError(f"FinanceTransaction yangilashda xato: {exc}") from exc

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete(self, tx: FinanceTransaction) -> None:
        """
        Operatsiyani o'chirish (hard delete).

        Args:
            tx: o'chiriladigan instance

        Raises:
            DatabaseError: o'chirishda xato
        """
        try:
            await self.db.delete(tx)
            await self.db.flush()
        except Exception as exc:
            raise DatabaseError(f"FinanceTransaction o'chirishda xato: {exc}") from exc