"""
TAURUS VISION — tests/test_services/test_finance_service.py
=============================================================
FinanceRepository + FinanceService uchun to'liq, mukammal testlar.

Qamrov:
  ✓ Yordamchi funksiyalar   — _roi(), _pct_change(), MONTH_LABELS_UZ
  ✓ FinanceRepository.create
  ✓ FinanceRepository.get_by_id
  ✓ FinanceRepository.list_paginated  — barcha filtrlar, pagination
  ✓ FinanceRepository.get_period_totals
  ✓ FinanceRepository.get_category_breakdown
  ✓ FinanceRepository.get_monthly_trends
  ✓ FinanceRepository.update / delete
  ✓ FinanceService.create             — barcha maydonlar
  ✓ FinanceService.get_by_id          — mavjud, yo'q
  ✓ FinanceService.list_transactions  — filtrlar, sahifalash
  ✓ FinanceService.update             — mavjud, yo'q
  ✓ FinanceService.delete             — mavjud, yo'q
  ✓ FinanceService.get_summary        — income, expense, profit, roi, kategoriyalar
  ✓ FinanceService.get_monthly_trends — oylar to'liq, trend tuzilma
  ✓ FinanceService.get_roi_report     — jonivor ROI, ferma umumiy
  ✓ EXPENSE_LABELS / INCOME_LABELS    — barcha kategoriyalar
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import FinanceTransaction, TransactionType, ExpenseCategory, IncomeCategory
from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.repositories.finance_repository import FinanceRepository
from app.schemas.finance import (
    FinanceTransactionCreate, FinanceTransactionUpdate,
)
from app.services.finance_service import (
    FinanceService, _roi, _pct_change, EXPENSE_LABELS, INCOME_LABELS,
)
from app.core.exceptions import EntityNotFoundError

pytestmark = pytest.mark.asyncio

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
MONTH_START = TODAY.replace(day=1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _tx(type_="expense", category="feed", amount=1_000_000,
        tx_date=None, animal_id=None, **kw) -> FinanceTransaction:
    return FinanceTransaction(
        type=type_,
        category=category,
        amount_uzs=amount,
        description="Test transaction",
        transaction_date=tx_date or TODAY,
        payment_method="cash",
        animal_id=animal_id,
        **kw,
    )


def _tx_create(type_="expense", category="feed", amount=1_000_000,
               tx_date=None, **kw) -> FinanceTransactionCreate:
    return FinanceTransactionCreate(
        type=type_,
        category=category,
        amount_uzs=amount,
        description="Test",
        transaction_date=tx_date or TODAY,
        payment_method="cash",
        **kw,
    )


@pytest.fixture
def repo(db):
    return FinanceRepository(db)


@pytest.fixture
def svc(db):
    return FinanceService(db)


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="FIN-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


# ═══════════════════════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:

    def test_roi_positive(self):
        assert _roi(income=1_500_000, expense=1_000_000) == 50.0

    def test_roi_negative(self):
        assert _roi(income=500_000, expense=1_000_000) == -50.0

    def test_roi_zero_when_expense_zero(self):
        assert _roi(income=1_000_000, expense=0) == 0.0

    def test_roi_zero_when_break_even(self):
        assert _roi(income=1_000_000, expense=1_000_000) == 0.0

    def test_roi_large_profit(self):
        roi = _roi(income=3_000_000, expense=1_000_000)
        assert roi == 200.0

    def test_pct_change_increase(self):
        assert _pct_change(new=110, old=100) == 10.0

    def test_pct_change_decrease(self):
        assert _pct_change(new=90, old=100) == -10.0

    def test_pct_change_none_when_old_zero(self):
        assert _pct_change(new=100, old=0) is None

    def test_pct_change_zero_when_same(self):
        assert _pct_change(new=100, old=100) == 0.0

    def test_expense_labels_all_present(self):
        for cat in ["feed", "veterinary", "equipment", "labor",
                    "utilities", "transport", "other"]:
            assert cat in EXPENSE_LABELS
            assert isinstance(EXPENSE_LABELS[cat], str)

    def test_income_labels_all_present(self):
        for cat in ["animal_sale", "milk_sale", "meat_sale",
                    "wool_sale", "subsidy", "other"]:
            assert cat in INCOME_LABELS
            assert isinstance(INCOME_LABELS[cat], str)

    def test_expense_labels_uzbek(self):
        assert EXPENSE_LABELS["feed"] == "Yem va ozuqa"
        assert EXPENSE_LABELS["veterinary"] == "Veterinariya"

    def test_income_labels_uzbek(self):
        assert INCOME_LABELS["milk_sale"] == "Sut"
        assert INCOME_LABELS["animal_sale"] == "Jonivor sotish"


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE REPOSITORY — CREATE & GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceRepoCreateGet:

    async def test_create_assigns_id(self, db, repo):
        tx = await repo.create(_tx())
        await db.commit()
        assert tx.id is not None and tx.id > 0

    async def test_create_saves_fields(self, db, repo):
        tx = await repo.create(_tx(
            type_="income", category="milk_sale", amount=5_000_000,
            tx_date=TODAY, description="Sut sotildi",
        ))
        await db.commit()
        assert tx.type        == "income"
        assert tx.category    == "milk_sale"
        assert tx.amount_uzs  == 5_000_000

    async def test_get_by_id_existing(self, db, repo):
        tx = await repo.create(_tx())
        await db.commit()
        found = await repo.get_by_id(tx.id)
        assert found is not None and found.id == tx.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_create_income_type(self, db, repo):
        tx = await repo.create(_tx(type_="income", category="milk_sale"))
        await db.commit()
        assert tx.type == "income"

    async def test_create_expense_type(self, db, repo):
        tx = await repo.create(_tx(type_="expense", category="feed"))
        await db.commit()
        assert tx.type == "expense"


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE REPOSITORY — LIST PAGINATED
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceRepoListPaginated:

    async def test_list_all(self, db, repo):
        for _ in range(3):
            await repo.create(_tx())
        await db.commit()
        items, total = await repo.list_paginated()
        assert total >= 3

    async def test_filter_by_type_income(self, db, repo):
        await repo.create(_tx(type_="income", category="milk_sale"))
        await repo.create(_tx(type_="expense", category="feed"))
        await db.commit()
        items, total = await repo.list_paginated(type="income")
        assert all(t.type == "income" for t in items)
        assert total >= 1

    async def test_filter_by_type_expense(self, db, repo):
        await repo.create(_tx(type_="expense", category="feed"))
        await db.commit()
        items, total = await repo.list_paginated(type="expense")
        assert all(t.type == "expense" for t in items)

    async def test_filter_by_category(self, db, repo):
        await repo.create(_tx(category="veterinary"))
        await repo.create(_tx(category="feed"))
        await db.commit()
        items, total = await repo.list_paginated(category="veterinary")
        assert all(t.category == "veterinary" for t in items)
        assert total >= 1

    async def test_filter_by_date_from(self, db, repo):
        old_date = TODAY - timedelta(days=30)
        await repo.create(_tx(tx_date=old_date, amount=999))
        await repo.create(_tx(tx_date=TODAY, amount=1_000_000))
        await db.commit()
        items, total = await repo.list_paginated(date_from=TODAY - timedelta(days=5))
        assert all(t.transaction_date >= TODAY - timedelta(days=5) for t in items)

    async def test_filter_by_date_to(self, db, repo):
        await repo.create(_tx(tx_date=YESTERDAY))
        await repo.create(_tx(tx_date=TODAY))
        await db.commit()
        items, _ = await repo.list_paginated(date_to=YESTERDAY)
        assert all(t.transaction_date <= YESTERDAY for t in items)

    async def test_filter_by_animal_id(self, db, repo, animal):
        await repo.create(_tx(animal_id=animal.id))
        await repo.create(_tx(animal_id=None))
        await db.commit()
        items, total = await repo.list_paginated(animal_id=animal.id)
        assert all(t.animal_id == animal.id for t in items)

    async def test_pagination(self, db, repo):
        for _ in range(5):
            await repo.create(_tx())
        await db.commit()
        p1, _ = await repo.list_paginated(page=1, size=2)
        p2, _ = await repo.list_paginated(page=2, size=2)
        assert {t.id for t in p1}.isdisjoint({t.id for t in p2})

    async def test_returns_tuple(self, db, repo):
        result = await repo.list_paginated()
        assert isinstance(result, tuple) and len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE REPOSITORY — PERIOD TOTALS & CATEGORY BREAKDOWN
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceRepoPeriodTotals:

    async def test_period_totals_structure(self, db, repo):
        totals = await repo.get_period_totals(MONTH_START, TODAY)
        for k in ["income", "expense", "income_count", "expense_count"]:
            assert k in totals

    async def test_period_totals_income(self, db, repo):
        await repo.create(_tx(type_="income", amount=3_000_000))
        await repo.create(_tx(type_="income", amount=2_000_000))
        await db.commit()
        totals = await repo.get_period_totals(MONTH_START, TODAY)
        assert totals["income"] >= 5_000_000

    async def test_period_totals_expense(self, db, repo):
        await repo.create(_tx(type_="expense", amount=1_500_000))
        await db.commit()
        totals = await repo.get_period_totals(MONTH_START, TODAY)
        assert totals["expense"] >= 1_500_000

    async def test_period_totals_count(self, db, repo):
        for _ in range(3):
            await repo.create(_tx(type_="income", category="milk_sale", amount=1_000_000))
        await db.commit()
        totals = await repo.get_period_totals(MONTH_START, TODAY)
        assert totals["income_count"] >= 3

    async def test_period_totals_zero_when_no_data(self, db, repo):
        future = TODAY + timedelta(days=365)
        totals = await repo.get_period_totals(future, future + timedelta(days=30))
        assert totals["income"] == 0 and totals["expense"] == 0

    async def test_category_breakdown_expense(self, db, repo):
        await repo.create(_tx(type_="expense", category="feed",       amount=1_000_000))
        await repo.create(_tx(type_="expense", category="feed",       amount=2_000_000))
        await repo.create(_tx(type_="expense", category="veterinary", amount=500_000))
        await db.commit()
        rows = await repo.get_category_breakdown("expense", MONTH_START, TODAY)
        cats = {r["category"]: r for r in rows}
        assert "feed" in cats
        assert cats["feed"]["amount"] >= 3_000_000
        assert cats["feed"]["count"]  >= 2

    async def test_category_breakdown_income(self, db, repo):
        await repo.create(_tx(type_="income", category="milk_sale", amount=5_000_000))
        await db.commit()
        rows = await repo.get_category_breakdown("income", MONTH_START, TODAY)
        cats = {r["category"]: r for r in rows}
        assert "milk_sale" in cats

    async def test_category_breakdown_structure(self, db, repo):
        await repo.create(_tx(type_="expense", category="feed", amount=1_000_000))
        await db.commit()
        rows = await repo.get_category_breakdown("expense", MONTH_START, TODAY)
        for row in rows:
            assert "category" in row and "amount" in row and "count" in row


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE REPOSITORY — UPDATE & DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceRepoUpdateDelete:

    async def test_update_amount(self, db, repo):
        tx = await repo.create(_tx(amount=1_000_000))
        await db.commit()
        updated = await repo.update(tx, {"amount_uzs": 2_000_000})
        await db.commit()
        assert updated.amount_uzs == 2_000_000

    async def test_update_description(self, db, repo):
        tx = await repo.create(_tx())
        await db.commit()
        updated = await repo.update(tx, {"description": "Updated"})
        await db.commit()
        assert updated.description == "Updated"

    async def test_delete_removes(self, db, repo):
        tx = await repo.create(_tx())
        await db.commit()
        tid = tx.id
        await repo.delete(tx)
        await db.commit()
        assert await repo.get_by_id(tid) is None


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceCreate:

    async def test_create_success(self, db, svc):
        data = _tx_create(type_="expense", category="feed", amount=1_000_000)
        resp = await svc.create(data)
        await db.commit()
        assert resp.id is not None

    async def test_create_returns_response(self, db, svc):
        from app.schemas.finance import FinanceTransactionResponse
        resp = await svc.create(_tx_create())
        assert isinstance(resp, FinanceTransactionResponse)

    async def test_create_income(self, db, svc):
        resp = await svc.create(_tx_create(
            type_="income", category="milk_sale", amount=5_000_000))
        assert resp.type == "income"

    async def test_create_expense(self, db, svc):
        resp = await svc.create(_tx_create(
            type_="expense", category="veterinary", amount=2_000_000))
        assert resp.type == "expense"

    async def test_create_all_expense_categories(self, db, svc):
        for cat in ["feed", "veterinary", "equipment", "labor",
                    "utilities", "transport", "other"]:
            resp = await svc.create(_tx_create(type_="expense", category=cat, amount=100_000))
            await db.commit()
            assert resp.category == cat

    async def test_create_all_income_categories(self, db, svc):
        for cat in ["animal_sale", "milk_sale", "meat_sale",
                    "wool_sale", "subsidy", "other"]:
            resp = await svc.create(_tx_create(type_="income", category=cat, amount=100_000))
            await db.commit()
            assert resp.category == cat

    async def test_create_with_animal_id(self, db, svc, animal):
        resp = await svc.create(_tx_create(
            type_="income", category="milk_sale",
            amount=1_000_000, animal_id=animal.id))
        assert resp.animal_id == animal.id

    async def test_create_with_created_by(self, db, svc):
        resp = await svc.create(_tx_create(), created_by=42)
        assert resp.created_by == 42

    async def test_create_saves_payment_method(self, db, svc):
        resp = await svc.create(_tx_create(payment_method="transfer"))
        assert resp.payment_method == "transfer"


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — GET & LIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceGetList:

    async def test_get_by_id_existing(self, db, svc):
        created = await svc.create(_tx_create())
        found = await svc.get_by_id(created.id)
        assert found.id == created.id

    async def test_get_by_id_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.get_by_id(999999)
        assert "999999" in exc_info.value.message

    async def test_list_returns_response(self, db, svc):
        from app.schemas.finance import FinanceTransactionListResponse
        await svc.create(_tx_create())
        result = await svc.list_transactions()
        assert isinstance(result, FinanceTransactionListResponse)
        assert result.total >= 1

    async def test_list_type_filter(self, db, svc):
        await svc.create(_tx_create(type_="income", category="milk_sale"))
        await svc.create(_tx_create(type_="expense", category="feed"))
        result = await svc.list_transactions(type="income")
        assert all(t.type == "income" for t in result.items)

    async def test_list_category_filter(self, db, svc):
        await svc.create(_tx_create(category="veterinary"))
        await svc.create(_tx_create(category="feed"))
        result = await svc.list_transactions(category="veterinary")
        assert all(t.category == "veterinary" for t in result.items)

    async def test_list_date_filter(self, db, svc):
        old = TODAY - timedelta(days=60)
        await svc.create(_tx_create(tx_date=old, amount=999_999))
        await svc.create(_tx_create(amount=1_000_000))
        result = await svc.list_transactions(date_from=TODAY - timedelta(days=10))
        for tx in result.items:
            assert tx.transaction_date >= TODAY - timedelta(days=10)

    async def test_list_animal_filter(self, db, svc, animal):
        await svc.create(_tx_create(type_="income", category="milk_sale",
                                     animal_id=animal.id))
        await svc.create(_tx_create())
        result = await svc.list_transactions(animal_id=animal.id)
        assert all(t.animal_id == animal.id for t in result.items)

    async def test_list_pagination(self, db, svc):
        for _ in range(5):
            await svc.create(_tx_create())
        p1 = await svc.list_transactions(page=1, size=2)
        p2 = await svc.list_transactions(page=2, size=2)
        ids1 = {t.id for t in p1.items}
        ids2 = {t.id for t in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_list_size_capped_at_100(self, db, svc):
        result = await svc.list_transactions(size=500)
        assert result.size <= 100

    async def test_list_total_pages_calculated(self, db, svc):
        for _ in range(5):
            await svc.create(_tx_create())
        result = await svc.list_transactions(page=1, size=2)
        assert result.pages >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — UPDATE & DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceUpdateDelete:

    async def test_update_amount(self, db, svc):
        created = await svc.create(_tx_create(amount=1_000_000))
        updated = await svc.update(created.id, FinanceTransactionUpdate(amount_uzs=2_000_000))
        assert updated.amount_uzs == 2_000_000

    async def test_update_description(self, db, svc):
        created = await svc.create(_tx_create())
        updated = await svc.update(created.id,
            FinanceTransactionUpdate(description="Updated description"))
        assert updated.description == "Updated description"

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update(999999, FinanceTransactionUpdate(description="Ghost"))

    async def test_delete_success(self, db, svc):
        created = await svc.create(_tx_create())
        await svc.delete(created.id)
        with pytest.raises(EntityNotFoundError):
            await svc.get_by_id(created.id)

    async def test_delete_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete(999999)


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceSummary:

    async def test_summary_structure(self, db, svc):
        from app.schemas.finance import FinanceSummary
        summary = await svc.get_summary(MONTH_START, TODAY)
        assert isinstance(summary, FinanceSummary)
        for k in ["total_income", "total_expense", "net_profit",
                  "roi_percent", "period_label"]:
            assert hasattr(summary, k)

    async def test_summary_income_total(self, db, svc):
        await svc.create(_tx_create(type_="income", category="milk_sale",  amount=3_000_000))
        await svc.create(_tx_create(type_="income", category="animal_sale", amount=2_000_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        assert summary.total_income >= 5_000_000

    async def test_summary_expense_total(self, db, svc):
        await svc.create(_tx_create(type_="expense", category="feed",       amount=1_500_000))
        await svc.create(_tx_create(type_="expense", category="veterinary", amount=500_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        assert summary.total_expense >= 2_000_000

    async def test_summary_net_profit_positive(self, db, svc):
        await svc.create(_tx_create(type_="income",  category="milk_sale", amount=5_000_000))
        await svc.create(_tx_create(type_="expense", category="feed",      amount=2_000_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        assert summary.net_profit >= 3_000_000

    async def test_summary_net_profit_negative(self, db, svc):
        """Xarajat daromaddan ko'p bo'lsa foyda manfiy."""
        # Maxsus davr ishlatamiz — boshqa testlar ta'sirini kamaytirish uchun
        future_start = TODAY + timedelta(days=100)
        future_end   = TODAY + timedelta(days=130)
        repo = FinanceRepository(db)
        await repo.create(_tx(type_="income",  category="milk_sale", amount=1_000_000,
                               tx_date=future_start))
        await repo.create(_tx(type_="expense", category="feed",      amount=5_000_000,
                               tx_date=future_start))
        await db.commit()
        summary = await svc.get_summary(future_start, future_end)
        assert summary.net_profit < 0

    async def test_summary_roi_zero_when_no_expense(self, db, svc):
        future_start = TODAY + timedelta(days=200)
        future_end   = TODAY + timedelta(days=230)
        summary = await svc.get_summary(future_start, future_end)
        assert summary.roi_percent == 0.0

    async def test_summary_expense_by_category(self, db, svc):
        await svc.create(_tx_create(type_="expense", category="feed",       amount=2_000_000))
        await svc.create(_tx_create(type_="expense", category="veterinary", amount=1_000_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        cats = {c.category for c in summary.expense_by_category}
        assert "feed" in cats or "veterinary" in cats

    async def test_summary_income_by_category(self, db, svc):
        await svc.create(_tx_create(type_="income", category="milk_sale", amount=4_000_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        cats = {c.category for c in summary.income_by_category}
        assert "milk_sale" in cats

    async def test_summary_category_percent_sums_100(self, db, svc):
        """Expense kategoriyalar protsenti 100 bo'lishi kerak."""
        future_start = TODAY + timedelta(days=300)
        repo = FinanceRepository(db)
        await repo.create(_tx(type_="expense", category="feed",       amount=3_000_000, tx_date=future_start))
        await repo.create(_tx(type_="expense", category="veterinary", amount=1_000_000, tx_date=future_start))
        await repo.create(_tx(type_="expense", category="labor",      amount=1_000_000, tx_date=future_start))
        await db.commit()
        summary = await svc.get_summary(future_start, future_start + timedelta(days=30))
        total_pct = sum(c.percent for c in summary.expense_by_category)
        assert abs(total_pct - 100.0) < 0.5

    async def test_summary_period_label_same_month(self, db, svc):
        """Bir oylik davr uchun oy nomi kelishi kerak."""
        first = TODAY.replace(day=1)
        last  = (first.replace(month=first.month % 12 + 1, day=1)
                 - timedelta(days=1)) if first.month < 12 else date(first.year, 12, 31)
        summary = await svc.get_summary(first, last)
        # O'zbek oy nomi bo'lishi kerak
        assert any(m in summary.period_label
                   for m in ["Yanvar","Fevral","Mart","Aprel","May","Iyun",
                              "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"])

    async def test_summary_counts(self, db, svc):
        for _ in range(2):
            await svc.create(_tx_create(type_="income",  category="milk_sale", amount=1_000_000))
        for _ in range(3):
            await svc.create(_tx_create(type_="expense", category="feed",      amount=1_000_000))
        summary = await svc.get_summary(MONTH_START, TODAY)
        assert summary.income_count  >= 2
        assert summary.expense_count >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — MONTHLY TRENDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceMonthlyTrends:

    async def test_trends_structure(self, db, svc):
        from app.schemas.finance import FinanceTrends
        trends = await svc.get_monthly_trends(months=3)
        assert isinstance(trends, FinanceTrends)
        assert hasattr(trends, "months")
        assert hasattr(trends, "total_income")
        assert hasattr(trends, "total_expense")
        assert hasattr(trends, "total_profit")

    async def test_trends_month_count(self, db, svc):
        """12 oy so'ralsa — 12 ta MonthlyTrend qaytadi."""
        trends = await svc.get_monthly_trends(months=12)
        assert len(trends.months) == 12

    async def test_trends_6_months(self, db, svc):
        trends = await svc.get_monthly_trends(months=6)
        assert len(trends.months) == 6

    async def test_trends_month_label_format(self, db, svc):
        trends = await svc.get_monthly_trends(months=3)
        for m in trends.months:
            # format: "2024-01"
            assert len(m.month) == 7
            assert "-" in m.month
            # month_label O'zbek bo'lishi kerak
            assert any(uz in m.month_label
                       for uz in ["Yanvar","Fevral","Mart","Aprel","May","Iyun",
                                  "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"])

    async def test_trends_includes_data(self, db, svc):
        await svc.create(_tx_create(type_="income", category="milk_sale", amount=3_000_000))
        await svc.create(_tx_create(type_="expense", category="feed",     amount=1_000_000))
        trends = await svc.get_monthly_trends(months=1)
        # Joriy oy ma'lumotlarni o'z ichiga olishi kerak
        assert trends.total_income  >= 3_000_000
        assert trends.total_expense >= 1_000_000

    async def test_trends_profit_computed(self, db, svc):
        await svc.create(_tx_create(type_="income",  category="milk_sale", amount=5_000_000))
        await svc.create(_tx_create(type_="expense", category="feed",      amount=2_000_000))
        trends = await svc.get_monthly_trends(months=1)
        assert trends.total_profit == trends.total_income - trends.total_expense

    async def test_trends_month_profit(self, db, svc):
        await svc.create(_tx_create(type_="income",  category="milk_sale", amount=4_000_000))
        await svc.create(_tx_create(type_="expense", category="feed",      amount=1_000_000))
        trends = await svc.get_monthly_trends(months=1)
        for m in trends.months:
            assert m.profit == m.income - m.expense


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE SERVICE — ROI REPORT
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinanceServiceROIReport:

    async def test_roi_report_structure(self, db, svc):
        from app.schemas.finance import ROIReport
        report = await svc.get_roi_report(MONTH_START, TODAY)
        assert isinstance(report, ROIReport)
        for k in ["date_from", "date_to", "animals", "total_income",
                  "total_expense", "total_profit", "overall_roi"]:
            assert hasattr(report, k)

    async def test_roi_report_with_animal_transactions(self, db, svc, animal):
        await svc.create(_tx_create(
            type_="income", category="milk_sale", amount=5_000_000, animal_id=animal.id))
        await svc.create(_tx_create(
            type_="expense", category="feed",     amount=2_000_000, animal_id=animal.id))
        report = await svc.get_roi_report(MONTH_START, TODAY)
        animal_ids = [a.animal_id for a in report.animals]
        assert animal.id in animal_ids

    async def test_roi_report_animal_roi_computed(self, db, svc, animal):
        await svc.create(_tx_create(
            type_="income",  category="milk_sale", amount=3_000_000, animal_id=animal.id))
        await svc.create(_tx_create(
            type_="expense", category="feed",      amount=1_000_000, animal_id=animal.id))
        report = await svc.get_roi_report(MONTH_START, TODAY)
        animal_entry = next((a for a in report.animals if a.animal_id == animal.id), None)
        assert animal_entry is not None
        assert animal_entry.total_income  >= 3_000_000
        assert animal_entry.total_expense >= 1_000_000
        assert animal_entry.net_profit    >= 2_000_000
        assert animal_entry.roi_percent   == 200.0

    async def test_roi_report_sorted_by_roi(self, db, svc, animal, db_session=None):
        """ROI bo'yicha eng yaxshi jonivor birinchi."""
        a2 = Animal(tag_id="FIN-ANIMAL-002", species=AnimalSpecies.SHEEP,
                    gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
                    acquisition_date=datetime(2022, 1, 1))
        db.add(a2)
        await db.commit()
        await db.refresh(a2)
        # Jonivor 1: ROI 200%
        await svc.create(_tx_create(type_="income",  category="milk_sale", amount=3_000_000, animal_id=animal.id))
        await svc.create(_tx_create(type_="expense", category="feed",      amount=1_000_000, animal_id=animal.id))
        # Jonivor 2: ROI 50%
        await svc.create(_tx_create(type_="income",  category="milk_sale", amount=1_500_000, animal_id=a2.id))
        await svc.create(_tx_create(type_="expense", category="feed",      amount=1_000_000, animal_id=a2.id))
        report = await svc.get_roi_report(MONTH_START, TODAY)
        if len(report.animals) >= 2:
            rois = [a.roi_percent for a in report.animals]
            assert rois == sorted(rois, reverse=True)

    async def test_roi_report_overall_roi(self, db, svc):
        future_start = TODAY + timedelta(days=400)
        repo = FinanceRepository(db)
        await repo.create(_tx(type_="income",  category="milk_sale", amount=4_000_000, tx_date=future_start))
        await repo.create(_tx(type_="expense", category="feed",      amount=2_000_000, tx_date=future_start))
        await db.commit()
        report = await svc.get_roi_report(future_start, future_start + timedelta(days=30))
        assert report.overall_roi == 100.0  # (4M - 2M) / 2M * 100

    async def test_roi_report_empty_returns_zero_roi(self, db, svc):
        future = TODAY + timedelta(days=500)
        report = await svc.get_roi_report(future, future + timedelta(days=30))
        assert report.overall_roi == 0.0
        assert len(report.animals) == 0

    async def test_roi_report_total_profit(self, db, svc):
        future_start = TODAY + timedelta(days=600)
        repo = FinanceRepository(db)
        await repo.create(_tx(type_="income",  category="milk_sale", amount=6_000_000, tx_date=future_start))
        await repo.create(_tx(type_="expense", category="feed",      amount=3_000_000, tx_date=future_start))
        await db.commit()
        report = await svc.get_roi_report(future_start, future_start + timedelta(days=30))
        assert report.total_profit == report.total_income - report.total_expense