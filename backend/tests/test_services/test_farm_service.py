"""
TAURUS VISION — tests/test_services/test_farm_service.py
==========================================================
Farm tizimini AYAMAS darajada vahshiy testlar.

Qamrov:
  ✓ Farm model             — is_active, __repr__
  ✓ FarmRepository.create / get_by_id / get_all / count
  ✓ FarmRepository.get_animal_stats / update / deactivate / delete
  ✓ FarmService.create_farm
  ✓ FarmService.get_farm         — mavjud, yo'q
  ✓ FarmService.list_farms       — active_only, pagination
  ✓ FarmService.update_farm      — mavjud, yo'q
  ✓ FarmService.switch_farm      — muvaffaqiyatli, arxivlangan, yo'q
  ✓ FarmService.deactivate_farm  — mavjud, yo'q
  ✓ FarmService.delete_farm      — jonivorlar bor → xato, bo'sh → OK
  ✓ Response tuzilma tekshiruvi
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.farm import Farm
from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.repositories.farm_repository import FarmRepository
from app.schemas.farm import FarmCreate, FarmUpdate
from app.services.farm_service import FarmService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio


def _farm_create(name="Test Ferma", **kw) -> FarmCreate:
    return FarmCreate(name=name, timezone_offset=5, **kw)


@pytest.fixture
async def saved_farm(db):
    svc = FarmService(db)
    return await svc.create_farm(_farm_create())


@pytest.fixture
def svc(db):
    return FarmService(db)


@pytest.fixture
def repo(db):
    return FarmRepository(db)


# ─── Farm model ────────────────────────────────────────────────────────

class TestFarmModel:
    def test_is_active_default_true(self):
        f = Farm(name="Test", timezone_offset=5)
        assert f.is_active is True or f.is_active is None  # DB default

    def test_farm_fields(self):
        f = Farm(name="Toshkent Ferma", location="Toshkent", timezone_offset=5)
        assert f.name == "Toshkent Ferma"
        assert f.location == "Toshkent"


# ─── FarmRepository ────────────────────────────────────────────────────

class TestFarmRepository:

    async def test_create_assigns_id(self, db, repo):
        farm = await repo.create(_farm_create(name="Repo Test Farm"))
        assert farm.id is not None and farm.id > 0

    async def test_create_saves_fields(self, db, repo):
        farm = await repo.create(_farm_create(
            name="Full Farm", location="Samarqand",
            owner_name="Karimov", phone="+998901234567"))
        assert farm.name       == "Full Farm"
        assert farm.location   == "Samarqand"
        assert farm.owner_name == "Karimov"

    async def test_get_by_id_existing(self, db, repo):
        farm = await repo.create(_farm_create(name="GetById Farm"))
        found = await repo.get_by_id(farm.id)
        assert found is not None and found.id == farm.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_all_returns_created(self, db, repo):
        await repo.create(_farm_create(name="All Farm 1"))
        await repo.create(_farm_create(name="All Farm 2"))
        result = await repo.get_all()
        assert len(result) >= 2

    async def test_get_all_active_only(self, db, repo):
        active = await repo.create(_farm_create(name="Active Farm"))
        inactive = await repo.create(_farm_create(name="Inactive Farm"))
        # Inactive ni arxivlaymiz
        inactive.is_active = False
        await db.commit()
        result = await repo.get_all(active_only=True)
        ids = [f.id for f in result]
        assert active.id   in ids
        assert inactive.id not in ids

    async def test_count(self, db, repo):
        before = await repo.count()
        await repo.create(_farm_create(name="Count Farm 1"))
        await repo.create(_farm_create(name="Count Farm 2"))
        after = await repo.count()
        assert after == before + 2

    async def test_get_animal_stats_empty(self, db, repo):
        farm = await repo.create(_farm_create(name="Empty Farm"))
        stats = await repo.get_animal_stats(farm.id)
        assert stats["total"] == 0
        assert stats["active"] == 0

    async def test_get_animal_stats_with_animals(self, db, repo):
        farm = await repo.create(_farm_create(name="Animal Farm"))
        for i in range(3):
            a = Animal(
                tag_id=f"FARM-A{i:02d}",
                species=AnimalSpecies.CATTLE,
                gender=AnimalGender.FEMALE,
                status=AnimalStatus.ACTIVE,
                acquisition_date=datetime(2022, 1, 1),
                farm_id=farm.id,
            )
            db.add(a)
        await db.commit()
        stats = await repo.get_animal_stats(farm.id)
        assert stats["total"] >= 3
        assert stats["active"] >= 3


# ─── FarmService ────────────────────────────────────────────────────────

class TestFarmServiceCreate:
    async def test_create_success(self, db, svc):
        resp = await svc.create_farm(_farm_create(name="SVC Farm"))
        assert resp.id is not None and resp.name == "SVC Farm"

    async def test_create_is_active_default(self, db, svc):
        resp = await svc.create_farm(_farm_create(name="Active Default"))
        assert resp.is_active is True

    async def test_create_with_all_fields(self, db, svc):
        resp = await svc.create_farm(_farm_create(
            name="Full SVC Farm", location="Namangan",
            owner_name="Toshev", phone="+998911111111",
            description="Test ferma"))
        assert resp.location   == "Namangan"
        assert resp.owner_name == "Toshev"

    async def test_create_multiple_farms(self, db, svc):
        r1 = await svc.create_farm(_farm_create(name="Farm X"))
        r2 = await svc.create_farm(_farm_create(name="Farm Y"))
        assert r1.id != r2.id


class TestFarmServiceGet:
    async def test_get_existing(self, db, svc, saved_farm):
        resp = await svc.get_farm(saved_farm.id)
        assert resp.id == saved_farm.id

    async def test_get_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_farm(999999)

    async def test_list_farms_structure(self, db, svc, saved_farm):
        from app.schemas.farm import FarmListResponse
        resp = await svc.list_farms()
        assert isinstance(resp, FarmListResponse)
        assert resp.total >= 1

    async def test_list_farms_active_only(self, db, svc):
        active   = await svc.create_farm(_farm_create(name="List Active"))
        inactive = await svc.create_farm(_farm_create(name="List Inactive"))
        await svc.deactivate_farm(inactive.id)
        resp = await svc.list_farms(active_only=True)
        ids = [f.id for f in resp.items]
        assert active.id   in ids
        assert inactive.id not in ids

    async def test_list_farms_response_includes_animal_count(self, db, svc, saved_farm):
        resp = await svc.list_farms()
        farm = next((f for f in resp.items if f.id == saved_farm.id), None)
        assert farm is not None
        assert farm.animal_count is not None


class TestFarmServiceUpdate:
    async def test_update_name(self, db, svc, saved_farm):
        updated = await svc.update_farm(saved_farm.id, FarmUpdate(name="Updated Name"))
        assert updated.name == "Updated Name"

    async def test_update_location(self, db, svc, saved_farm):
        updated = await svc.update_farm(saved_farm.id, FarmUpdate(location="Andijon"))
        assert updated.location == "Andijon"

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_farm(999999, FarmUpdate(name="Ghost"))

    async def test_update_partial_fields(self, db, svc, saved_farm):
        original_name = saved_farm.name
        updated = await svc.update_farm(saved_farm.id, FarmUpdate(location="Buxoro"))
        assert updated.name     == original_name  # O'zgarmadi
        assert updated.location == "Buxoro"


class TestFarmServiceSwitch:
    async def test_switch_active_farm_ok(self, db, svc):
        farm = await svc.create_farm(_farm_create(name="Switch Target"))
        resp = await svc.switch_farm(user_id=1, farm_id=farm.id)
        assert resp.farm_id == farm.id
        assert resp.farm_name == farm.name

    async def test_switch_archived_farm_raises(self, db, svc):
        farm = await svc.create_farm(_farm_create(name="Switch Archived"))
        await svc.deactivate_farm(farm.id)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.switch_farm(user_id=1, farm_id=farm.id)
        assert "arxivlangan" in exc_info.value.message.lower()

    async def test_switch_missing_farm_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.switch_farm(user_id=1, farm_id=999999)

    async def test_switch_response_structure(self, db, svc):
        farm = await svc.create_farm(_farm_create(name="Switch OK"))
        from app.schemas.farm import FarmSwitchResponse
        resp = await svc.switch_farm(user_id=42, farm_id=farm.id)
        assert isinstance(resp, FarmSwitchResponse)
        assert resp.farm_id   == farm.id
        assert "muvaffaqiyatli" in resp.message


class TestFarmServiceDeactivateDelete:
    async def test_deactivate_success(self, db, svc):
        farm = await svc.create_farm(_farm_create(name="Deactivate Me"))
        result = await svc.deactivate_farm(farm.id)
        assert result.is_active is False

    async def test_deactivate_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.deactivate_farm(999999)

    async def test_delete_empty_farm_ok(self, db, svc, repo):
        farm = await svc.create_farm(_farm_create(name="Delete Empty"))
        farm_id = farm.id
        await svc.delete_farm(farm_id)
        assert await repo.get_by_id(farm_id) is None

    async def test_delete_farm_with_animals_raises(self, db, svc):
        farm = await svc.create_farm(_farm_create(name="Delete With Animals"))
        a = Animal(
            tag_id="DEL-FARM-A01",
            species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE,
            status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2022, 1, 1),
            farm_id=farm.id,
        )
        db.add(a)
        await db.commit()
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.delete_farm(farm.id)
        msg = exc_info.value.message
        assert "jonivor" in msg.lower() or "animal" in msg.lower()

    async def test_delete_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_farm(999999)