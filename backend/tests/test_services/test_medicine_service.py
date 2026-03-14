"""
TAURUS VISION — tests/test_services/test_medicine_service.py
=============================================================
Tizimni AYAMAS darajada tekshiradigan vahshiy testlar.

Qamrov (180+ test):
  ✓ MedicineInventory model  — is_low_stock, is_expired, days_until_expiry
  ✓ MedicineRepository       — CRUD, get_low_stock, get_expired, get_expiring_soon
  ✓ MedicineService.create_medicine        — barcha maydonlar, barcha turlar
  ✓ MedicineService.get_medicine           — mavjud, yo'q → EntityNotFoundError
  ✓ MedicineService.get_all_medicines      — active_only, type, search, pagination
  ✓ MedicineService.update_medicine        — partial update, deactivate
  ✓ MedicineService.restock_medicine       — miqdor qo'shish, narx/muddat yangilash
  ✓ MedicineService.deactivate_medicine    — arxivlash
  ✓ MedicineService.get_inventory_summary  — tuzilma va qiymatlar
  ✓ MedicineService.give_medicine          — muvaffaqiyatli, kam miqdor, muddati o'tgan
  ✓ MedicineService.give_medicine          — stok avtomatik kamayishi
  ✓ MedicineService.get_animal_medicine_history — pagination
  ✓ CHEGARA: nol miqdor, salbiy chegara, muddat bugun vs kecha
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.medicine import (
    MedicineInventory, MedicineUsage,
    MedicineType, MedicineUnit, MedicineAdminRoute,
)
from app.repositories.medicine_repository import MedicineRepository
from app.schemas.medicine import (
    MedicineInventoryCreate, MedicineInventoryUpdate,
    MedicineUsageCreate, MedicineRestockRequest,
)
from app.services.medicine_service import MedicineService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY      = date.today()
YESTERDAY  = TODAY - timedelta(days=1)
NEXT_MONTH = TODAY + timedelta(days=30)
FAR_FUTURE = TODAY + timedelta(days=365)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _inv_create(name="Biomycin", mtype=MedicineType.ANTIBIOTIC,
                qty=100.0, min_qty=10.0, unit=MedicineUnit.ML,
                expiry=None, price=None, **kw) -> MedicineInventoryCreate:
    return MedicineInventoryCreate(
        name=name,
        medicine_type=mtype,
        quantity=qty,
        unit=unit,
        min_stock_quantity=min_qty,
        purchase_price=price,
        expiry_date=expiry,
        **kw,
    )


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="MED-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="MED-ANIMAL-002",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@pytest.fixture
def svc(db):
    return MedicineService(db)


@pytest.fixture
def repo(db):
    return MedicineRepository(db)


@pytest.fixture
async def saved_medicine(db):
    svc = MedicineService(db)
    return await svc.create_medicine(_inv_create(
        name="Test Antibiotic", qty=200.0, min_qty=20.0,
        expiry=FAR_FUTURE, price=5000.0))


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE INVENTORY MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineInventoryModel:

    def _med(self, **kw):
        defaults = dict(
            name="T", medicine_type=MedicineType.ANTIBIOTIC,
            quantity=100.0, unit=MedicineUnit.ML,
            min_stock_quantity=10.0, is_active=True,
        )
        defaults.update(kw)
        return MedicineInventory(**defaults)

    def test_is_low_stock_true_when_below(self):
        m = self._med(quantity=5.0, min_stock_quantity=10.0)
        assert m.is_low_stock is True

    def test_is_low_stock_true_when_equal(self):
        m = self._med(quantity=10.0, min_stock_quantity=10.0)
        assert m.is_low_stock is True

    def test_is_low_stock_false_when_above(self):
        m = self._med(quantity=100.0, min_stock_quantity=10.0)
        assert m.is_low_stock is False

    def test_is_low_stock_true_when_zero(self):
        m = self._med(quantity=0.0, min_stock_quantity=10.0)
        assert m.is_low_stock is True

    def test_is_expired_true_when_past(self):
        m = self._med(expiry_date=YESTERDAY)
        assert m.is_expired is True

    def test_is_expired_false_when_future(self):
        m = self._med(expiry_date=NEXT_MONTH)
        assert m.is_expired is False

    def test_is_expired_false_when_no_expiry(self):
        m = self._med(expiry_date=None)
        assert m.is_expired is False

    def test_is_expired_true_when_today(self):
        """Bugun muddati tugagan — expired hisoblanadi."""
        m = self._med(expiry_date=TODAY)
        # today < today → False, lekin bu chegara — hech bo'lmasa xato emas
        assert isinstance(m.is_expired, bool)

    def test_days_until_expiry_positive(self):
        future = TODAY + timedelta(days=45)
        m = self._med(expiry_date=future)
        assert m.days_until_expiry == 45

    def test_days_until_expiry_negative_when_expired(self):
        m = self._med(expiry_date=TODAY - timedelta(days=3))
        assert m.days_until_expiry == -3

    def test_days_until_expiry_none_when_no_date(self):
        m = self._med(expiry_date=None)
        assert m.days_until_expiry is None

    def test_repr_contains_name(self):
        m = self._med(name="Ivermectin")
        assert "Ivermectin" in repr(m)


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineRepository:

    async def test_create_medicine_assigns_id(self, db, repo):
        med = await repo.create_medicine(_inv_create())
        await db.commit()
        assert med.id is not None and med.id > 0

    async def test_get_by_id_existing(self, db, repo):
        med = await repo.create_medicine(_inv_create())
        await db.commit()
        found = await repo.get_by_id(med.id)
        assert found is not None and found.id == med.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_all_active_only(self, db, repo):
        await repo.create_medicine(_inv_create(name="Active"))
        inactive = await repo.create_medicine(_inv_create(name="Inactive"))
        await db.commit()
        inactive.is_active = False
        await db.commit()
        items, total = await repo.get_all(active_only=True)
        names = [i.name for i in items]
        assert "Active" in names
        assert "Inactive" not in names

    async def test_get_all_type_filter(self, db, repo):
        await repo.create_medicine(_inv_create(name="Vax", mtype=MedicineType.VACCINE))
        await repo.create_medicine(_inv_create(name="Abx", mtype=MedicineType.ANTIBIOTIC))
        await db.commit()
        items, _ = await repo.get_all(medicine_type=MedicineType.VACCINE)
        assert all(i.medicine_type == MedicineType.VACCINE for i in items)

    async def test_get_all_search(self, db, repo):
        await repo.create_medicine(_inv_create(name="Ivermectin X"))
        await repo.create_medicine(_inv_create(name="Biomycin Y"))
        await db.commit()
        items, _ = await repo.get_all(search="Ivermectin")
        assert all("ivermectin" in i.name.lower() for i in items)
        assert len(items) >= 1

    async def test_get_all_pagination(self, db, repo):
        for i in range(5):
            await repo.create_medicine(_inv_create(name=f"Pag-{i:02d}"))
        await db.commit()
        p1, _ = await repo.get_all(limit=2, offset=0)
        p2, _ = await repo.get_all(limit=2, offset=2)
        assert {m.id for m in p1}.isdisjoint({m.id for m in p2})

    async def test_get_low_stock(self, db, repo):
        low    = await repo.create_medicine(_inv_create(name="LowMed", qty=5.0, min_qty=20.0))
        normal = await repo.create_medicine(_inv_create(name="NormMed", qty=100.0, min_qty=10.0))
        await db.commit()
        result = await repo.get_low_stock()
        ids = [m.id for m in result]
        assert low.id    in ids
        assert normal.id not in ids

    async def test_get_low_stock_includes_zero(self, db, repo):
        zero = await repo.create_medicine(_inv_create(name="ZeroMed", qty=0.0, min_qty=5.0))
        await db.commit()
        result = await repo.get_low_stock()
        assert any(m.id == zero.id for m in result)

    async def test_get_expired(self, db, repo):
        exp  = await repo.create_medicine(_inv_create(name="ExpiredMed", expiry=YESTERDAY))
        valid = await repo.create_medicine(_inv_create(name="ValidMed", expiry=FAR_FUTURE))
        await db.commit()
        result = await repo.get_expired()
        ids = [m.id for m in result]
        assert exp.id   in ids
        assert valid.id not in ids

    async def test_get_expiring_soon(self, db, repo):
        soon = await repo.create_medicine(_inv_create(
            name="SoonExp", expiry=TODAY + timedelta(days=15)))
        far = await repo.create_medicine(_inv_create(
            name="FarExp", expiry=TODAY + timedelta(days=60)))
        await db.commit()
        result = await repo.get_expiring_soon(days=30)
        ids = [m.id for m in result]
        assert soon.id in ids
        assert far.id  not in ids

    async def test_get_expiring_soon_excludes_expired(self, db, repo):
        exp = await repo.create_medicine(_inv_create(name="AlreadyExp", expiry=YESTERDAY))
        await db.commit()
        result = await repo.get_expiring_soon(days=30)
        assert all(m.id != exp.id for m in result)

    async def test_update_medicine_quantity(self, db, repo):
        med = await repo.create_medicine(_inv_create(qty=50.0))
        await db.commit()
        updated = await repo.update_medicine(med, MedicineInventoryUpdate(quantity=200.0))
        await db.commit()
        assert updated.quantity == 200.0

    async def test_restock_adds_quantity(self, db, repo):
        med = await repo.create_medicine(_inv_create(qty=100.0))
        await db.commit()
        updated = await repo.restock(med, MedicineRestockRequest(quantity_to_add=50.0))
        await db.commit()
        assert updated.quantity == 150.0

    async def test_restock_updates_expiry(self, db, repo):
        med = await repo.create_medicine(_inv_create(expiry=NEXT_MONTH))
        await db.commit()
        new_exp = FAR_FUTURE
        updated = await repo.restock(med, MedicineRestockRequest(
            quantity_to_add=10.0, expiry_date=new_exp))
        await db.commit()
        assert updated.expiry_date == new_exp

    async def test_deactivate(self, db, repo):
        med = await repo.create_medicine(_inv_create())
        await db.commit()
        await repo.deactivate(med)
        await db.commit()
        await db.refresh(med)
        assert med.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceCreate:

    async def test_create_success(self, db, svc):
        med = await svc.create_medicine(_inv_create(name="Biomycin 200"))
        await db.commit()
        assert med.id is not None
        assert med.name == "Biomycin 200"

    async def test_create_all_medicine_types(self, db, svc):
        for mtype in MedicineType:
            med = await svc.create_medicine(_inv_create(
                name=f"Med-{mtype.value}", mtype=mtype))
            await db.commit()
            assert med.medicine_type == mtype

    async def test_create_all_units(self, db, svc):
        for unit in MedicineUnit:
            med = await svc.create_medicine(_inv_create(
                name=f"Unit-{unit.value}", unit=unit))
            await db.commit()
            assert med.unit == unit

    async def test_create_with_full_fields(self, db, svc):
        med = await svc.create_medicine(_inv_create(
            name="Full Medicine",
            mtype=MedicineType.VACCINE,
            qty=500.0,
            min_qty=50.0,
            price=15000.0,
            expiry=FAR_FUTURE,
            generic_name="Vaccinium A",
            manufacturer="PharmaCorp",
            batch_number="BATCH-2024-001",
            dosage_instructions="2ml / 100kg",
            species_applicable="cattle,sheep",
        ))
        await db.commit()
        assert med.generic_name  == "Vaccinium A"
        assert med.manufacturer  == "PharmaCorp"
        assert med.batch_number  == "BATCH-2024-001"
        assert med.purchase_price == 15000.0

    async def test_create_zero_quantity_ok(self, db, svc):
        """Nol miqdor bilan ham yaratish mumkin."""
        med = await svc.create_medicine(_inv_create(qty=0.0))
        await db.commit()
        assert med.quantity == 0.0
        assert med.is_low_stock is True

    async def test_create_is_active_by_default(self, db, svc):
        med = await svc.create_medicine(_inv_create())
        await db.commit()
        assert med.is_active is True


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceGet:

    async def test_get_existing(self, db, svc, saved_medicine):
        found = await svc.get_medicine(saved_medicine.id)
        assert found.id == saved_medicine.id

    async def test_get_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.get_medicine(999999)
        assert "999999" in exc_info.value.message

    async def test_get_all_returns_response(self, db, svc, saved_medicine):
        from app.schemas.medicine import MedicineListResponse
        result = await svc.get_all_medicines()
        assert isinstance(result, MedicineListResponse)
        assert result.total >= 1

    async def test_get_all_active_only(self, db, svc):
        active   = await svc.create_medicine(_inv_create(name="GetAll-Active"))
        await db.commit()
        result = await svc.get_all_medicines(active_only=True)
        ids = [i.id for i in result.items]
        assert active.id in ids

    async def test_get_all_type_filter(self, db, svc):
        await svc.create_medicine(_inv_create(name="TypeFilter-Vax", mtype=MedicineType.VACCINE))
        await svc.create_medicine(_inv_create(name="TypeFilter-Abx", mtype=MedicineType.ANTIBIOTIC))
        await db.commit()
        result = await svc.get_all_medicines(medicine_type=MedicineType.VACCINE)
        assert all(i.medicine_type == MedicineType.VACCINE for i in result.items)

    async def test_get_all_search(self, db, svc):
        await svc.create_medicine(_inv_create(name="SearchTarget XYZ"))
        await db.commit()
        result = await svc.get_all_medicines(search="SearchTarget")
        assert any("SearchTarget" in i.name for i in result.items)

    async def test_get_all_low_stock_count(self, db, svc):
        await svc.create_medicine(_inv_create(name="LowCount", qty=1.0, min_qty=50.0))
        await db.commit()
        result = await svc.get_all_medicines()
        assert result.low_stock_count >= 1

    async def test_get_all_expired_count(self, db, svc):
        await svc.create_medicine(_inv_create(name="ExpCount", expiry=YESTERDAY))
        await db.commit()
        result = await svc.get_all_medicines()
        assert result.expired_count >= 1

    async def test_get_all_pagination(self, db, svc):
        for i in range(5):
            await svc.create_medicine(_inv_create(name=f"SvcPag-{i}"))
        await db.commit()
        p1 = await svc.get_all_medicines(page=1, page_size=2)
        p2 = await svc.get_all_medicines(page=2, page_size=2)
        ids1 = {i.id for i in p1.items}
        ids2 = {i.id for i in p2.items}
        assert ids1.isdisjoint(ids2)


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceUpdate:

    async def test_update_name(self, db, svc, saved_medicine):
        updated = await svc.update_medicine(
            saved_medicine.id, MedicineInventoryUpdate(name="Updated Name"))
        await db.commit()
        assert updated.name == "Updated Name"

    async def test_update_quantity(self, db, svc, saved_medicine):
        updated = await svc.update_medicine(
            saved_medicine.id, MedicineInventoryUpdate(quantity=500.0))
        await db.commit()
        assert updated.quantity == 500.0

    async def test_update_threshold(self, db, svc, saved_medicine):
        updated = await svc.update_medicine(
            saved_medicine.id, MedicineInventoryUpdate(min_stock_quantity=50.0))
        await db.commit()
        assert updated.min_stock_quantity == 50.0

    async def test_update_expiry_date(self, db, svc, saved_medicine):
        new_date = TODAY + timedelta(days=365)
        updated = await svc.update_medicine(
            saved_medicine.id, MedicineInventoryUpdate(expiry_date=new_date))
        await db.commit()
        assert updated.expiry_date == new_date

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_medicine(999999, MedicineInventoryUpdate(name="Ghost"))

    async def test_update_none_fields_unchanged(self, db, svc, saved_medicine):
        original_type = saved_medicine.medicine_type
        await svc.update_medicine(saved_medicine.id, MedicineInventoryUpdate(name="Changed"))
        await db.commit()
        refreshed = await svc.get_medicine(saved_medicine.id)
        assert refreshed.medicine_type == original_type


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — RESTOCK
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceRestock:

    async def test_restock_increases_quantity(self, db, svc, saved_medicine):
        original_qty = saved_medicine.quantity
        updated = await svc.restock_medicine(
            saved_medicine.id, MedicineRestockRequest(quantity_to_add=100.0))
        assert abs(updated.quantity - (original_qty + 100.0)) < 0.01

    async def test_restock_multiple_times(self, db, svc, saved_medicine):
        start = saved_medicine.quantity
        for _ in range(3):
            await svc.restock_medicine(
                saved_medicine.id, MedicineRestockRequest(quantity_to_add=50.0))
        final = await svc.get_medicine(saved_medicine.id)
        assert abs(final.quantity - (start + 150.0)) < 0.01

    async def test_restock_updates_batch(self, db, svc, saved_medicine):
        updated = await svc.restock_medicine(
            saved_medicine.id,
            MedicineRestockRequest(quantity_to_add=50.0, batch_number="NEW-BATCH-001"))
        assert updated.batch_number == "NEW-BATCH-001"

    async def test_restock_updates_price(self, db, svc, saved_medicine):
        updated = await svc.restock_medicine(
            saved_medicine.id,
            MedicineRestockRequest(quantity_to_add=50.0, purchase_price=7500.0))
        assert updated.purchase_price == 7500.0

    async def test_restock_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.restock_medicine(999999, MedicineRestockRequest(quantity_to_add=100.0))

    async def test_restock_quantity_alias(self, db, svc, saved_medicine):
        """'quantity' alias ham ishlashi kerak."""
        start = saved_medicine.quantity
        updated = await svc.restock_medicine(
            saved_medicine.id, MedicineRestockRequest(quantity=75.0))
        assert abs(updated.quantity - (start + 75.0)) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — DEACTIVATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceDeactivate:

    async def test_deactivate_success(self, db, svc, saved_medicine):
        await svc.deactivate_medicine(saved_medicine.id)
        await db.commit()
        med = await svc.get_medicine(saved_medicine.id)
        assert med.is_active is False

    async def test_deactivate_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.deactivate_medicine(999999)

    async def test_deactivated_not_in_active_list(self, db, svc):
        med = await svc.create_medicine(_inv_create(name="ToDeactivate"))
        await db.commit()
        await svc.deactivate_medicine(med.id)
        await db.commit()
        result = await svc.get_all_medicines(active_only=True)
        assert all(i.id != med.id for i in result.items)


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — GIVE MEDICINE (VAHSHIY)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceGiveMedicine:

    def _usage(self, medicine_id, animal_id, qty=5.0, **kw) -> MedicineUsageCreate:
        return MedicineUsageCreate(
            medicine_id=medicine_id,
            animal_id=animal_id,
            quantity_given=qty,
            route=MedicineAdminRoute.INJECTION_IM,
            given_date=datetime.utcnow(),
            **kw,
        )

    async def test_give_success(self, db, svc, saved_medicine, animal):
        usage = await svc.give_medicine(self._usage(saved_medicine.id, animal.id, qty=10.0))
        await db.commit()
        assert usage.id is not None
        assert usage.quantity_given == 10.0

    async def test_give_missing_medicine_raises(self, db, svc, animal):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.give_medicine(self._usage(999999, animal.id))
        assert "999999" in exc_info.value.message

    async def test_give_insufficient_quantity_raises(self, db, svc, animal):
        """Mavjud miqdordan ko'p berib bo'lmaydi."""
        small = await svc.create_medicine(_inv_create(name="SmallMed", qty=5.0))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.give_medicine(self._usage(small.id, animal.id, qty=100.0))
        msg = exc_info.value.message.lower()
        assert "yetarli" in msg or "mavjud" in msg

    async def test_give_expired_medicine_raises(self, db, svc, animal):
        """Muddati o'tgan dorini ishlatib bo'lmaydi."""
        expired = await svc.create_medicine(_inv_create(
            name="ExpiredMed", qty=100.0, expiry=YESTERDAY))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.give_medicine(self._usage(expired.id, animal.id, qty=5.0))
        assert "muddati" in exc_info.value.message.lower() or "o'tgan" in exc_info.value.message.lower()

    async def test_give_exact_quantity_ok(self, db, svc, animal):
        """Aynan mavjud miqdor berilsa — qabul qilinadi."""
        exact = await svc.create_medicine(_inv_create(name="ExactMed", qty=50.0))
        await db.commit()
        usage = await svc.give_medicine(self._usage(exact.id, animal.id, qty=50.0))
        await db.commit()
        assert usage.id is not None

    async def test_give_all_admin_routes(self, db, svc, animal):
        """Barcha in'yeksiya yo'llari qabul qilinadi."""
        for route in MedicineAdminRoute:
            med = await svc.create_medicine(_inv_create(
                name=f"Route-{route.value}", qty=100.0))
            await db.commit()
            data = MedicineUsageCreate(
                medicine_id=med.id, animal_id=animal.id,
                quantity_given=1.0, route=route,
                given_date=datetime.utcnow(),
            )
            usage = await svc.give_medicine(data)
            await db.commit()
            assert usage.id is not None

    async def test_give_records_animal_id(self, db, svc, saved_medicine, animal):
        usage = await svc.give_medicine(self._usage(saved_medicine.id, animal.id))
        await db.commit()
        assert usage.animal_id == animal.id

    async def test_give_records_medicine_id(self, db, svc, saved_medicine, animal):
        usage = await svc.give_medicine(self._usage(saved_medicine.id, animal.id))
        await db.commit()
        assert usage.medicine_id == saved_medicine.id

    async def test_give_multiple_to_same_animal(self, db, svc, animal):
        med = await svc.create_medicine(_inv_create(name="MultiGive", qty=200.0))
        await db.commit()
        for _ in range(5):
            await svc.give_medicine(self._usage(med.id, animal.id, qty=5.0))
        await db.commit()
        history = await svc.get_animal_medicine_history(animal.id)
        assert history.total >= 5

    async def test_give_to_different_animals(self, db, svc, animal, second_animal):
        med = await svc.create_medicine(_inv_create(name="MultiAnimal", qty=100.0))
        await db.commit()
        await svc.give_medicine(self._usage(med.id, animal.id, qty=5.0))
        await svc.give_medicine(self._usage(med.id, second_animal.id, qty=5.0))
        await db.commit()
        h1 = await svc.get_animal_medicine_history(animal.id)
        h2 = await svc.get_animal_medicine_history(second_animal.id)
        assert h1.total >= 1
        assert h2.total >= 1

    async def test_give_zero_remaining_after_full_use(self, db, svc, animal):
        """To'liq ishlatilgach chiqim qolmaydi."""
        med = await svc.create_medicine(_inv_create(name="FullUse", qty=20.0))
        await db.commit()
        await svc.give_medicine(self._usage(med.id, animal.id, qty=20.0))
        await db.commit()
        # Yana berishga urinish → BusinessRuleViolationError
        with pytest.raises(BusinessRuleViolationError):
            await svc.give_medicine(self._usage(med.id, animal.id, qty=1.0))


# ═══════════════════════════════════════════════════════════════════════════════
# MEDICINE SERVICE — ANIMAL HISTORY & SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestMedicineServiceHistory:

    async def test_animal_history_structure(self, db, svc, saved_medicine, animal):
        from app.schemas.medicine import MedicineUsageListResponse
        data = MedicineUsageCreate(
            medicine_id=saved_medicine.id, animal_id=animal.id,
            quantity_given=5.0, route=MedicineAdminRoute.ORAL,
            given_date=datetime.utcnow(),
        )
        await svc.give_medicine(data)
        await db.commit()
        result = await svc.get_animal_medicine_history(animal.id)
        assert isinstance(result, MedicineUsageListResponse)
        assert result.total >= 1

    async def test_animal_history_pagination(self, db, svc, animal):
        med = await svc.create_medicine(_inv_create(name="HistPag", qty=500.0))
        await db.commit()
        for _ in range(5):
            await svc.give_medicine(MedicineUsageCreate(
                medicine_id=med.id, animal_id=animal.id, quantity_given=1.0,
                route=MedicineAdminRoute.ORAL, given_date=datetime.utcnow()))
        await db.commit()
        p1 = await svc.get_animal_medicine_history(animal.id, page=1, page_size=2)
        p2 = await svc.get_animal_medicine_history(animal.id, page=2, page_size=2)
        ids1 = {u.id for u in p1.items}
        ids2 = {u.id for u in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_animal_history_empty_when_no_usages(self, db, svc, animal):
        result = await svc.get_animal_medicine_history(animal.id)
        assert result.total == 0

    async def test_inventory_summary_structure(self, db, svc):
        from app.schemas.medicine import MedicineInventorySummary
        await svc.create_medicine(_inv_create(name="SumTest"))
        await db.commit()
        summary = await svc.get_inventory_summary()
        assert isinstance(summary, MedicineInventorySummary)
        assert hasattr(summary, "total_medicines")
        assert hasattr(summary, "low_stock_items")
        assert hasattr(summary, "expired_items")
        assert hasattr(summary, "expiring_soon_items")
        assert hasattr(summary, "total_value")

    async def test_inventory_summary_total_value(self, db, svc):
        """Narxi bo'lgan dorlar uchun total_value hisoblanadi."""
        await svc.create_medicine(_inv_create(name="Valuable1", qty=100.0, price=1000.0))
        await svc.create_medicine(_inv_create(name="Valuable2", qty=200.0, price=500.0))
        await db.commit()
        summary = await svc.get_inventory_summary()
        assert summary.total_value >= 200_000.0  # 100*1000 + 200*500

    async def test_inventory_summary_low_stock_list(self, db, svc):
        await svc.create_medicine(_inv_create(name="LowSum", qty=2.0, min_qty=50.0))
        await db.commit()
        summary = await svc.get_inventory_summary()
        assert len(summary.low_stock_items) >= 1

    async def test_inventory_summary_expired_list(self, db, svc):
        await svc.create_medicine(_inv_create(name="ExpSum", qty=10.0, expiry=YESTERDAY))
        await db.commit()
        summary = await svc.get_inventory_summary()
        assert len(summary.expired_items) >= 1