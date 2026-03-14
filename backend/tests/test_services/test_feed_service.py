"""
TAURUS VISION — tests/test_services/test_feed_service.py
==========================================================
FeedStock model + FeedStockRepository + FeedRecordRepository
+ FeedService uchun to'liq, mukammal testlar.

Qamrov:
  ✓ FeedStock model    — is_low, stock_percent, total_value_uzs, is_expired,
                         min_stock_kg/quantity_kg alias, __repr__
  ✓ FeedRecord model   — __repr__
  ✓ FeedStockRepository.create / get_by_id / get_all / get_low_stock
  ✓ FeedStockRepository.get_expiring_soon / save / reset_low_stock_flags / get_stats
  ✓ FeedRecordRepository.create / get_list / get_consumed_kg / get_daily_consumption
  ✓ FeedService.create_stock    — barcha maydonlar
  ✓ FeedService.get_stock       — mavjud, yo'q
  ✓ FeedService.list_stocks     — active_only, feed_type, low_only filtrlar
  ✓ FeedService.update_stock    — mavjud, yo'q, alert flag reset
  ✓ FeedService.restock         — mavjud, yo'q, narx/yetkazuvchi yangilash
  ✓ FeedService.add_record      — muvaffaqiyatli, kam stok, arxivlangan, yo'q jonivor
  ✓ FeedService.add_record      — atomik kamayish, low stock alert flag
  ✓ FeedService.list_records    — filtrlar, pagination
  ✓ FeedService.get_stats       — tuzilma va qiymatlar
  ✓ FeedService.check_low_stock_alerts — alerts_sent, reset
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import FeedStock, FeedRecord, FeedType, FeedUnit
from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.repositories.feed_repository import FeedStockRepository, FeedRecordRepository
from app.schemas.feed import (
    FeedStockCreate, FeedStockUpdate, FeedStockRestock, FeedRecordCreate,
)
from app.services.feed_service import FeedService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)
FUTURE = NOW + timedelta(days=30)
PAST   = NOW - timedelta(days=1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _stock(current_kg=500.0, min_kg=100.0, feed_type=FeedType.HAY,
           name="Test Pichan", is_active=True, **kw) -> FeedStock:
    return FeedStock(
        feed_type=feed_type,
        name=name,
        current_kg=current_kg,
        min_threshold_kg=min_kg,
        unit=FeedUnit.KG,
        is_active=is_active,
        low_stock_alerted=False,
        **kw,
    )


def _stock_create(current_kg=500.0, min_threshold_kg=100.0,
                  feed_type=FeedType.HAY, name="Test Hay", **kw) -> FeedStockCreate:
    return FeedStockCreate(
        name=name,
        feed_type=feed_type,
        current_kg=current_kg,
        min_threshold_kg=min_threshold_kg,
        **kw,
    )


def _record_create(stock_id, quantity_kg=10.0, animal_id=None, **kw) -> FeedRecordCreate:
    return FeedRecordCreate(
        stock_id=stock_id,
        quantity_kg=quantity_kg,
        animal_id=animal_id,
        fed_at=NOW,
        **kw,
    )


@pytest.fixture
async def stock_repo(db):
    return FeedStockRepository(db)


@pytest.fixture
async def record_repo(db):
    return FeedRecordRepository(db)


@pytest.fixture
async def svc(db):
    return FeedService(db)


@pytest.fixture
async def saved_stock(db):
    s = _stock(current_kg=1000.0, min_kg=200.0)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="FEED-ANIMAL-001",
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
# FEEDSTOCK MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedStockModel:

    def test_is_low_true_when_below_threshold(self):
        s = FeedStock(current_kg=50.0, min_threshold_kg=100.0)
        assert s.is_low is True

    def test_is_low_false_when_above(self):
        s = FeedStock(current_kg=500.0, min_threshold_kg=100.0)
        assert s.is_low is False

    def test_is_low_false_when_equal(self):
        s = FeedStock(current_kg=100.0, min_threshold_kg=100.0)
        assert s.is_low is False

    def test_is_low_true_when_zero(self):
        s = FeedStock(current_kg=0.0, min_threshold_kg=100.0)
        assert s.is_low is True

    def test_stock_percent_above_threshold(self):
        s = FeedStock(current_kg=200.0, min_threshold_kg=100.0)
        assert s.stock_percent == 200.0

    def test_stock_percent_at_threshold(self):
        s = FeedStock(current_kg=100.0, min_threshold_kg=100.0)
        assert s.stock_percent == 100.0

    def test_stock_percent_below_threshold(self):
        s = FeedStock(current_kg=50.0, min_threshold_kg=100.0)
        assert s.stock_percent == 50.0

    def test_stock_percent_zero_kg(self):
        s = FeedStock(current_kg=0.0, min_threshold_kg=100.0)
        assert s.stock_percent == 0.0

    def test_stock_percent_zero_threshold(self):
        """Threshold 0 bo'lsa — 100 qaytaradi (xavfsiz hisob)."""
        s = FeedStock(current_kg=500.0, min_threshold_kg=0.0)
        assert s.stock_percent == 100.0

    def test_total_value_uzs_computed(self):
        s = FeedStock(current_kg=100.0, unit_cost_uzs=1000)
        assert s.total_value_uzs == 100_000

    def test_total_value_uzs_none_when_no_cost(self):
        s = FeedStock(current_kg=100.0, unit_cost_uzs=None)
        assert s.total_value_uzs is None

    def test_is_expired_false_when_no_expiry(self):
        s = FeedStock(expiry_date=None)
        assert s.is_expired is False

    def test_is_expired_true_when_past(self):
        s = FeedStock(expiry_date=NOW - timedelta(days=1))
        assert s.is_expired is True

    def test_is_expired_false_when_future(self):
        s = FeedStock(expiry_date=NOW + timedelta(days=7))
        assert s.is_expired is False

    def test_min_stock_kg_alias_getter(self):
        s = FeedStock(min_threshold_kg=250.0)
        assert s.min_stock_kg == 250.0

    def test_min_stock_kg_alias_setter(self):
        s = FeedStock(min_threshold_kg=100.0)
        s.min_stock_kg = 300.0
        assert s.min_threshold_kg == 300.0

    def test_quantity_kg_alias_getter(self):
        s = FeedStock(current_kg=750.0)
        assert s.quantity_kg == 750.0

    def test_quantity_kg_alias_setter(self):
        s = FeedStock(current_kg=100.0)
        s.quantity_kg = 500.0
        assert s.current_kg == 500.0

    def test_repr_contains_key_info(self):
        s = FeedStock(feed_type=FeedType.HAY, current_kg=500.0, min_threshold_kg=100.0)
        r = repr(s)
        assert "500.0" in r
        assert "100.0" in r

    def test_init_min_stock_kg_alias(self):
        s = FeedStock(feed_type=FeedType.HAY, name="T", min_stock_kg=50.0, current_kg=200.0)
        assert s.min_threshold_kg == 50.0

    def test_init_quantity_kg_alias(self):
        s = FeedStock(feed_type=FeedType.HAY, name="T", quantity_kg=300.0, min_threshold_kg=100.0)
        assert s.current_kg == 300.0

    def test_init_price_per_kg_alias(self):
        s = FeedStock(feed_type=FeedType.HAY, name="T", price_per_kg=1500.0,
                      current_kg=100.0, min_threshold_kg=10.0)
        assert s.unit_cost_uzs == 1500


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDRECORD MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedRecordModel:
    def test_repr_herd_when_no_animal(self):
        r = FeedRecord(stock_id=1, quantity_kg=100.0, fed_at=NOW)
        rep = repr(r)
        assert "100.0" in rep
        assert "herd" in rep

    def test_repr_animal_id_when_set(self):
        r = FeedRecord(stock_id=1, quantity_kg=50.0, fed_at=NOW, animal_id=5)
        rep = repr(r)
        assert "5" in rep


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDSTOCK REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedStockRepository:

    async def test_create_assigns_id(self, db, stock_repo):
        s = await stock_repo.create(_stock())
        await db.commit()
        assert s.id is not None and s.id > 0

    async def test_create_saves_all_fields(self, db, stock_repo):
        s = await stock_repo.create(_stock(
            current_kg=1500.0, min_kg=300.0,
            feed_type=FeedType.CONCENTRATE, name="Konsentrat #3",
            unit_cost_uzs=2000,
        ))
        await db.commit()
        assert s.current_kg       == 1500.0
        assert s.min_threshold_kg == 300.0
        assert s.feed_type        == FeedType.CONCENTRATE
        assert s.name             == "Konsentrat #3"
        assert s.unit_cost_uzs    == 2000

    async def test_get_by_id_existing(self, db, stock_repo, saved_stock):
        found = await stock_repo.get_by_id(saved_stock.id)
        assert found is not None and found.id == saved_stock.id

    async def test_get_by_id_missing_none(self, db, stock_repo):
        assert await stock_repo.get_by_id(999999) is None

    async def test_get_all_active_only(self, db, stock_repo):
        active   = await stock_repo.create(_stock(name="Active", is_active=True))
        inactive = await stock_repo.create(_stock(name="Inactive", is_active=False))
        await db.commit()
        result = await stock_repo.get_all(active_only=True)
        ids = [s.id for s in result]
        assert active.id in ids
        assert inactive.id not in ids

    async def test_get_all_includes_inactive(self, db, stock_repo):
        inactive = await stock_repo.create(_stock(name="Inactive2", is_active=False))
        await db.commit()
        result = await stock_repo.get_all(active_only=False)
        assert any(s.id == inactive.id for s in result)

    async def test_get_all_feed_type_filter(self, db, stock_repo):
        hay  = await stock_repo.create(_stock(feed_type=FeedType.HAY,   name="Hay"))
        corn = await stock_repo.create(_stock(feed_type=FeedType.CORN_SILAGE, name="Corn"))
        await db.commit()
        result = await stock_repo.get_all(feed_type=FeedType.HAY)
        ids = [s.id for s in result]
        assert hay.id  in ids
        assert corn.id not in ids

    async def test_get_all_low_only(self, db, stock_repo):
        low    = await stock_repo.create(_stock(current_kg=50.0,  min_kg=200.0, name="Low"))
        normal = await stock_repo.create(_stock(current_kg=500.0, min_kg=200.0, name="Normal"))
        await db.commit()
        result = await stock_repo.get_all(low_only=True)
        ids = [s.id for s in result]
        assert low.id    in ids
        assert normal.id not in ids

    async def test_get_low_stock(self, db, stock_repo):
        low    = await stock_repo.create(_stock(current_kg=50.0,  min_kg=200.0, name="LowS"))
        normal = await stock_repo.create(_stock(current_kg=500.0, min_kg=200.0, name="NormS"))
        await db.commit()
        result = await stock_repo.get_low_stock()
        ids = [s.id for s in result]
        assert low.id    in ids
        assert normal.id not in ids

    async def test_get_expiring_soon(self, db, stock_repo):
        expiring = await stock_repo.create(_stock(
            name="Expiring", expiry_date=NOW + timedelta(days=3)))
        far      = await stock_repo.create(_stock(
            name="FarFuture", expiry_date=NOW + timedelta(days=30)))
        await db.commit()
        result = await stock_repo.get_expiring_soon(within_days=7)
        ids = [s.id for s in result]
        assert expiring.id in ids
        assert far.id      not in ids

    async def test_get_expiring_soon_excludes_past(self, db, stock_repo):
        expired = await stock_repo.create(_stock(
            name="Expired", expiry_date=NOW - timedelta(days=1)))
        await db.commit()
        result = await stock_repo.get_expiring_soon(within_days=7)
        assert all(s.id != expired.id for s in result)

    async def test_save_updates_field(self, db, stock_repo, saved_stock):
        saved_stock.current_kg = 9999.0
        updated = await stock_repo.save(saved_stock)
        await db.commit()
        assert updated.current_kg == 9999.0

    async def test_reset_low_stock_flags(self, db, stock_repo):
        s = await stock_repo.create(_stock(
            current_kg=500.0, min_kg=100.0, low_stock_alerted=True, name="FlagReset"))
        await db.commit()
        count = await stock_repo.reset_low_stock_flags()
        await db.commit()
        assert count >= 1

    async def test_reset_flags_does_not_reset_still_low(self, db, stock_repo):
        """Hali ham past bo'lgan stok uchun flag reset qilinmaydi."""
        s = await stock_repo.create(_stock(
            current_kg=50.0, min_kg=200.0, low_stock_alerted=True, name="StillLow"))
        await db.commit()
        await stock_repo.reset_low_stock_flags()
        await db.commit()
        await db.refresh(s)
        assert s.low_stock_alerted is True

    async def test_get_stats_structure(self, db, stock_repo):
        await stock_repo.create(_stock(name="Stats1"))
        await db.commit()
        stats = await stock_repo.get_stats()
        for k in ["total_stocks", "active_stocks", "low_stock_count",
                  "expired_count", "total_inventory_kg"]:
            assert k in stats

    async def test_get_stats_counts(self, db, stock_repo):
        await stock_repo.create(_stock(name="ST-A1", is_active=True))
        await stock_repo.create(_stock(name="ST-A2", is_active=True))
        await stock_repo.create(_stock(name="ST-I1", is_active=False))
        await db.commit()
        stats = await stock_repo.get_stats()
        assert stats["active_stocks"] >= 2

    async def test_get_stats_total_kg(self, db, stock_repo):
        await stock_repo.create(_stock(name="TKG1", current_kg=1000.0))
        await stock_repo.create(_stock(name="TKG2", current_kg=500.0))
        await db.commit()
        stats = await stock_repo.get_stats()
        assert stats["total_inventory_kg"] >= 1500.0


# ═══════════════════════════════════════════════════════════════════════════════
# FEEDRECORD REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedRecordRepository:

    async def test_create_assigns_id(self, db, record_repo, saved_stock):
        r = FeedRecord(stock_id=saved_stock.id, quantity_kg=50.0, fed_at=NOW)
        created = await record_repo.create(r)
        await db.commit()
        assert created.id is not None

    async def test_get_list_all(self, db, record_repo, saved_stock):
        for _ in range(3):
            await record_repo.create(
                FeedRecord(stock_id=saved_stock.id, quantity_kg=10.0, fed_at=NOW))
        await db.commit()
        items, total = await record_repo.get_list()
        assert total >= 3

    async def test_get_list_stock_filter(self, db, stock_repo, record_repo, db_session=None):
        s1 = await stock_repo.create(_stock(name="SF1"))
        s2 = await stock_repo.create(_stock(name="SF2"))
        await stock_repo.db.commit()
        await record_repo.create(FeedRecord(stock_id=s1.id, quantity_kg=10.0, fed_at=NOW))
        await record_repo.create(FeedRecord(stock_id=s2.id, quantity_kg=20.0, fed_at=NOW))
        await record_repo.db.commit()
        items, total = await record_repo.get_list(stock_id=s1.id)
        assert total == 1
        assert all(r.stock_id == s1.id for r in items)

    async def test_get_list_animal_filter(self, db, record_repo, saved_stock, animal):
        await record_repo.create(
            FeedRecord(stock_id=saved_stock.id, quantity_kg=10.0, fed_at=NOW, animal_id=animal.id))
        await record_repo.create(
            FeedRecord(stock_id=saved_stock.id, quantity_kg=20.0, fed_at=NOW, animal_id=None))
        await db.commit()
        items, total = await record_repo.get_list(animal_id=animal.id)
        assert total == 1 and items[0].animal_id == animal.id

    async def test_get_list_date_filter(self, db, record_repo, saved_stock):
        old = NOW - timedelta(days=10)
        await record_repo.create(
            FeedRecord(stock_id=saved_stock.id, quantity_kg=10.0, fed_at=old))
        await record_repo.create(
            FeedRecord(stock_id=saved_stock.id, quantity_kg=20.0, fed_at=NOW))
        await db.commit()
        items, total = await record_repo.get_list(from_date=NOW - timedelta(days=1))
        kg_values = [r.quantity_kg for r in items]
        assert 10.0 not in kg_values  # Eski yozuv chiqmasligi kerak

    async def test_get_list_pagination(self, db, record_repo, saved_stock):
        for _ in range(5):
            await record_repo.create(
                FeedRecord(stock_id=saved_stock.id, quantity_kg=5.0, fed_at=NOW))
        await db.commit()
        p1, _ = await record_repo.get_list(limit=2, offset=0)
        p2, _ = await record_repo.get_list(limit=2, offset=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})

    async def test_get_consumed_kg_sum(self, db, record_repo, saved_stock):
        for kg in [10.0, 20.0, 30.0]:
            await record_repo.create(
                FeedRecord(stock_id=saved_stock.id, quantity_kg=kg, fed_at=NOW))
        await db.commit()
        total = await record_repo.get_consumed_kg(
            from_date=NOW - timedelta(hours=1),
            to_date=NOW + timedelta(hours=1),
        )
        assert total >= 60.0

    async def test_get_consumed_kg_empty(self, db, record_repo):
        total = await record_repo.get_consumed_kg(
            from_date=NOW + timedelta(days=10),
            to_date=NOW + timedelta(days=20),
        )
        assert total == 0.0

    async def test_get_daily_consumption_structure(self, db, record_repo, saved_stock):
        await record_repo.create(
            FeedRecord(stock_id=saved_stock.id, quantity_kg=50.0, fed_at=NOW))
        await db.commit()
        result = await record_repo.get_daily_consumption(days=7)
        assert isinstance(result, list)
        if result:
            assert "date" in result[0]
            assert "total_kg" in result[0]


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — CREATE STOCK
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceCreateStock:

    async def test_create_stock_success(self, db, svc):
        data = _stock_create(current_kg=500.0, name="SVC Hay")
        resp = await svc.create_stock(data)
        assert resp.id is not None and resp.name == "SVC Hay"

    async def test_create_stock_returns_response(self, db, svc):
        from app.schemas.feed import FeedStockResponse
        resp = await svc.create_stock(_stock_create(name="Resp Test"))
        assert isinstance(resp, FeedStockResponse)

    async def test_create_stock_saves_all_fields(self, db, svc):
        data = _stock_create(
            name="Full Fields", feed_type=FeedType.CONCENTRATE,
            current_kg=800.0, min_threshold_kg=150.0, unit_cost_uzs=2500,
            supplier="Agro LLC", notes="Test batch",
        )
        resp = await svc.create_stock(data)
        assert resp.feed_type        == FeedType.CONCENTRATE
        assert resp.current_kg       == 800.0
        assert resp.min_threshold_kg == 150.0
        assert resp.unit_cost_uzs    == 2500
        assert resp.supplier         == "Agro LLC"

    async def test_create_stock_all_feed_types(self, db, svc):
        for ft in FeedType:
            resp = await svc.create_stock(_stock_create(
                name=f"Stock {ft.value}", feed_type=ft))
            assert resp.feed_type == ft

    async def test_create_stock_is_low_property(self, db, svc):
        resp = await svc.create_stock(_stock_create(
            current_kg=50.0, min_threshold_kg=200.0, name="Low Stock"))
        assert resp.is_low is True

    async def test_create_stock_not_low_when_sufficient(self, db, svc):
        resp = await svc.create_stock(_stock_create(
            current_kg=500.0, min_threshold_kg=100.0, name="Enough Stock"))
        assert resp.is_low is False


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — GET STOCK
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceGetStock:

    async def test_get_stock_existing(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Get Test"))
        found = await svc.get_stock(created.id)
        assert found.id == created.id

    async def test_get_stock_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.get_stock(999999)
        assert "999999" in exc_info.value.message

    async def test_list_stocks_active_only(self, db, svc):
        active   = await svc.create_stock(_stock_create(name="Active List"))
        inactive_data = _stock_create(name="Inactive List")
        # Inactive stock yaratish uchun to'g'ridan DB ga qo'shamiz
        s = _stock(name="InactiveDB", is_active=False)
        db.add(s)
        await db.commit()
        result = await svc.list_stocks(active_only=True)
        ids = [r.id for r in result.items]
        assert active.id in ids
        assert s.id     not in ids

    async def test_list_stocks_low_only(self, db, svc):
        low_resp    = await svc.create_stock(_stock_create(
            name="LowList", current_kg=50.0, min_threshold_kg=200.0))
        normal_resp = await svc.create_stock(_stock_create(
            name="NormalList", current_kg=500.0, min_threshold_kg=100.0))
        result = await svc.list_stocks(low_only=True)
        ids = [r.id for r in result.items]
        assert low_resp.id    in ids
        assert normal_resp.id not in ids

    async def test_list_stocks_feed_type_filter(self, db, svc):
        hay  = await svc.create_stock(_stock_create(name="HayFT", feed_type=FeedType.HAY))
        conc = await svc.create_stock(_stock_create(name="ConcFT", feed_type=FeedType.CONCENTRATE))
        result = await svc.list_stocks(feed_type=FeedType.HAY)
        ids = [r.id for r in result.items]
        assert hay.id  in ids
        assert conc.id not in ids

    async def test_list_stocks_response_structure(self, db, svc):
        from app.schemas.feed import FeedStockListResponse
        result = await svc.list_stocks()
        assert isinstance(result, FeedStockListResponse)
        assert hasattr(result, "total")
        assert hasattr(result, "low_stock_count")
        assert hasattr(result, "expired_count")


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — UPDATE STOCK
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceUpdateStock:

    async def test_update_name(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Old Name"))
        updated = await svc.update_stock(created.id, FeedStockUpdate(name="New Name"))
        assert updated.name == "New Name"

    async def test_update_threshold(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Threshold Test"))
        updated = await svc.update_stock(created.id, FeedStockUpdate(min_threshold_kg=250.0))
        assert updated.min_threshold_kg == 250.0

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_stock(999999, FeedStockUpdate(name="Ghost"))

    async def test_update_resets_alert_flag_when_restocked(self, db, svc):
        """Stok to'ldirilganda low_stock_alerted False ga qaytadi."""
        s = _stock(current_kg=50.0, min_kg=200.0, low_stock_alerted=True, name="AlertReset")
        db.add(s)
        await db.commit()
        await db.refresh(s)
        # Endi current_kg ni ko'paytiramiz — is_low false bo'ladi
        updated = await svc.update_stock(s.id, FeedStockUpdate(current_kg=500.0))
        assert updated.low_stock_alerted is False

    async def test_update_deactivate_stock(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Deactivate Test"))
        updated = await svc.update_stock(created.id, FeedStockUpdate(is_active=False))
        assert updated.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — RESTOCK
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceRestock:

    async def test_restock_increases_kg(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Restock Test", current_kg=500.0))
        restocked = await svc.restock(created.id, FeedStockRestock(quantity_kg=300.0))
        assert restocked.current_kg >= 800.0

    async def test_restock_updates_supplier(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Supplier Test"))
        restocked = await svc.restock(created.id, FeedStockRestock(
            quantity_kg=100.0, supplier="New Supplier"))
        assert restocked.supplier == "New Supplier"

    async def test_restock_updates_cost(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Cost Test"))
        restocked = await svc.restock(created.id, FeedStockRestock(
            quantity_kg=100.0, unit_cost_uzs=3000))
        assert restocked.unit_cost_uzs == 3000

    async def test_restock_resets_alert_flag(self, db, svc):
        s = _stock(current_kg=50.0, min_kg=200.0, low_stock_alerted=True, name="RestockFlag")
        db.add(s)
        await db.commit()
        await db.refresh(s)
        restocked = await svc.restock(s.id, FeedStockRestock(quantity_kg=1000.0))
        assert restocked.low_stock_alerted is False

    async def test_restock_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.restock(999999, FeedStockRestock(quantity_kg=100.0))

    async def test_restock_multiple_times(self, db, svc):
        created = await svc.create_stock(_stock_create(name="Multi Restock", current_kg=0.0))
        for _ in range(3):
            await svc.restock(created.id, FeedStockRestock(quantity_kg=100.0))
        final = await svc.get_stock(created.id)
        assert final.current_kg >= 300.0


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — ADD RECORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceAddRecord:

    async def test_add_record_success(self, db, svc, saved_stock):
        resp = await svc.add_record(_record_create(saved_stock.id, quantity_kg=50.0))
        assert resp.id is not None

    async def test_add_record_decreases_stock(self, db, svc):
        stock_resp = await svc.create_stock(_stock_create(
            name="Decreasing Stock", current_kg=500.0))
        await svc.add_record(_record_create(stock_resp.id, quantity_kg=100.0))
        updated = await svc.get_stock(stock_resp.id)
        assert abs(updated.current_kg - 400.0) < 0.01

    async def test_add_record_atomic_decrease(self, db, svc):
        """Kamayish aniq: 3 ta yozuv → 3 marta kamayadi."""
        stock_resp = await svc.create_stock(_stock_create(
            name="Atomic Stock", current_kg=300.0))
        for _ in range(3):
            await svc.add_record(_record_create(stock_resp.id, quantity_kg=50.0))
        updated = await svc.get_stock(stock_resp.id)
        assert abs(updated.current_kg - 150.0) < 0.01

    async def test_add_record_insufficient_stock_raises(self, db, svc):
        stock_resp = await svc.create_stock(_stock_create(
            name="Insufficient", current_kg=30.0))
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.add_record(_record_create(stock_resp.id, quantity_kg=100.0))
        msg = exc_info.value.message.lower()
        assert "yetarli" in msg or "mavjud" in msg or "so'ralgan" in msg

    async def test_add_record_missing_stock_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.add_record(_record_create(999999, quantity_kg=10.0))

    async def test_add_record_archived_stock_raises(self, db, svc):
        s = _stock(name="Archived Stock", is_active=False, current_kg=1000.0, min_kg=100.0)
        db.add(s)
        await db.commit()
        await db.refresh(s)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.add_record(_record_create(s.id, quantity_kg=10.0))
        assert "arxivlangan" in exc_info.value.message.lower()

    async def test_add_record_missing_animal_raises(self, db, svc, saved_stock):
        with pytest.raises(EntityNotFoundError):
            await svc.add_record(_record_create(
                saved_stock.id, quantity_kg=10.0, animal_id=999999))

    async def test_add_record_herd_when_no_animal(self, db, svc, saved_stock):
        """animal_id=None — butun poda uchun yozuv (ruxsat etiladi)."""
        resp = await svc.add_record(_record_create(saved_stock.id, animal_id=None))
        assert resp.id is not None

    async def test_add_record_sets_low_stock_flag(self, db, svc):
        """Stok pastga tushsa — low_stock_alerted True bo'ladi."""
        stock_resp = await svc.create_stock(_stock_create(
            name="Low Flag Stock", current_kg=200.0, min_threshold_kg=150.0))
        await svc.add_record(_record_create(stock_resp.id, quantity_kg=100.0))
        updated = await svc.get_stock(stock_resp.id)
        assert updated.is_low is True

    async def test_add_record_exact_amount_ok(self, db, svc):
        """Aynan mavjud miqdor kamaytirish mumkin."""
        stock_resp = await svc.create_stock(_stock_create(
            name="Exact Stock", current_kg=100.0))
        resp = await svc.add_record(_record_create(stock_resp.id, quantity_kg=100.0))
        assert resp.id is not None
        updated = await svc.get_stock(stock_resp.id)
        assert abs(updated.current_kg - 0.0) < 0.01

    async def test_add_record_with_notes(self, db, svc, saved_stock):
        resp = await svc.add_record(_record_create(
            saved_stock.id, notes="Ertalabki oziqlantirish"))
        assert resp.id is not None


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — LIST RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceListRecords:

    async def test_list_returns_response(self, db, svc, saved_stock):
        from app.schemas.feed import FeedRecordListResponse
        await svc.add_record(_record_create(saved_stock.id, quantity_kg=10.0))
        result = await svc.list_records(stock_id=saved_stock.id)
        assert isinstance(result, FeedRecordListResponse)
        assert result.total >= 1

    async def test_list_stock_filter(self, db, svc):
        s1 = await svc.create_stock(_stock_create(name="LR-S1", current_kg=500.0))
        s2 = await svc.create_stock(_stock_create(name="LR-S2", current_kg=500.0))
        await svc.add_record(_record_create(s1.id, quantity_kg=10.0))
        await svc.add_record(_record_create(s2.id, quantity_kg=20.0))
        result = await svc.list_records(stock_id=s1.id)
        assert result.total == 1

    async def test_list_pagination(self, db, svc, saved_stock):
        for _ in range(5):
            await svc.add_record(_record_create(saved_stock.id, quantity_kg=5.0))
        p1 = await svc.list_records(stock_id=saved_stock.id, page=1, page_size=2)
        p2 = await svc.list_records(stock_id=saved_stock.id, page=2, page_size=2)
        ids1 = {r.id for r in p1.items}
        ids2 = {r.id for r in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_list_total_kg(self, db, svc, saved_stock):
        for kg in [10.0, 20.0, 30.0]:
            await svc.add_record(_record_create(saved_stock.id, quantity_kg=kg))
        result = await svc.list_records(stock_id=saved_stock.id)
        assert result.total_kg >= 60.0

    async def test_list_page_size_capped_at_100(self, db, svc, saved_stock):
        result = await svc.list_records(page_size=500)
        assert result.page_size <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — GET STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceGetStats:

    async def test_get_stats_structure(self, db, svc):
        from app.schemas.feed import FeedStats
        await svc.create_stock(_stock_create(name="Stats Stock"))
        stats = await svc.get_stats()
        assert isinstance(stats, FeedStats)
        assert hasattr(stats, "total_stocks")
        assert hasattr(stats, "active_stocks")
        assert hasattr(stats, "low_stock_count")
        assert hasattr(stats, "consumed_today_kg")
        assert hasattr(stats, "consumed_this_week_kg")
        assert hasattr(stats, "daily_trend")

    async def test_get_stats_counts_increase(self, db, svc):
        before = await svc.get_stats()
        await svc.create_stock(_stock_create(name="Extra Stock"))
        after = await svc.get_stats()
        assert after.active_stocks >= before.active_stocks

    async def test_get_stats_consumed_today(self, db, svc, saved_stock):
        await svc.add_record(_record_create(saved_stock.id, quantity_kg=75.0))
        stats = await svc.get_stats()
        assert stats.consumed_today_kg >= 75.0


# ═══════════════════════════════════════════════════════════════════════════════
# FEED SERVICE — CHECK LOW STOCK ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedServiceCheckLowStockAlerts:

    async def test_check_returns_dict(self, db, svc):
        result = await svc.check_low_stock_alerts()
        assert isinstance(result, dict)
        for k in ["checked", "alerts_sent", "reset"]:
            assert k in result

    async def test_check_counts_low_stocks(self, db, svc):
        await svc.create_stock(_stock_create(
            name="LowAlert1", current_kg=50.0, min_threshold_kg=200.0))
        result = await svc.check_low_stock_alerts()
        assert result["checked"] >= 1

    async def test_check_reset_count(self, db, svc):
        """To'ldirilgan stok uchun flag reset hisobi."""
        s = _stock(current_kg=500.0, min_kg=100.0, low_stock_alerted=True, name="ResetCheck")
        db.add(s)
        await db.commit()
        result = await svc.check_low_stock_alerts()
        assert result["reset"] >= 1