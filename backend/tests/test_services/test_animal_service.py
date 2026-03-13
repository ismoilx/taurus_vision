"""
TAURUS VISION — tests/test_services/test_animal_service.py
============================================================
AnimalRepository + AnimalService uchun to'liq, vahshiy testlar.

Qamrov:
  ✓ Animal model helpers     — age_days, age_months, is_active, mark_detected
  ✓ AnimalRepository.create              — yaratish, barcha maydonlar
  ✓ AnimalRepository.bulk_create         — ko'plik, bo'sh list, tartib
  ✓ AnimalRepository.get_by_id          — mavjud, yo'q, manfiy
  ✓ AnimalRepository.get_by_tag_id      — case-insensitive, yo'q
  ✓ AnimalRepository.get_existing_tags  — to'plam, bo'sh input
  ✓ AnimalRepository.get_all            — filtrlar, pagination
  ✓ AnimalRepository.count              — species, status filtrlari
  ✓ AnimalRepository.update             — partial update, yo'q ID
  ✓ AnimalRepository.delete             — o'chirish, yo'q ID
  ✓ AnimalRepository.get_first_active   — aktiv/aktiv yo'q
  ✓ AnimalRepository.increment_detection_count
  ✓ AnimalRepository.advanced_search    — barcha filtrlar, sort, pagination
  ✓ AnimalRepository.search_by_text     — ilike qidiruv, case-insensitive
  ✓ AnimalService.create_animal         — noyob, duplicate tag
  ✓ AnimalService.get_animal            — mavjud, yo'q
  ✓ AnimalService.get_animals           — filtrlash, pagination
  ✓ AnimalService.get_animal_by_tag     — mavjud, yo'q
  ✓ AnimalService.update_animal         — muvaffaqiyatli, arxivlangan, yo'q
  ✓ AnimalService.delete_animal         — muvaffaqiyatli, arxivlangan, yo'q
  ✓ AnimalService.import_from_csv       — to'g'ri, xato, limit, sarlavha
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.repositories.animal import AnimalRepository
from app.schemas.animal import AnimalCreate, AnimalUpdate
from app.services.animal import AnimalService, _MAX_IMPORT_ROWS
from app.core.exceptions import (
    EntityAlreadyExistsError,
    EntityNotFoundError,
    BusinessRuleViolationError,
)

pytestmark = pytest.mark.asyncio

_NOW = datetime(2024, 6, 1, tzinfo=timezone.utc)


def _make_create(**kwargs) -> AnimalCreate:
    defaults = dict(
        tag_id="TST-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=_NOW,
    )
    defaults.update(kwargs)
    return AnimalCreate(**defaults)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def repo(db):
    return AnimalRepository(db)


@pytest.fixture
async def svc(db):
    return AnimalService(db)


@pytest.fixture
async def sample_animal(db):
    repo = AnimalRepository(db)
    a = await repo.create(_make_create(tag_id="SMPL-001", species=AnimalSpecies.CATTLE))
    await db.commit()
    await db.refresh(a)
    return a


@pytest.fixture
async def sample_animals(db):
    repo = AnimalRepository(db)
    animals = await repo.bulk_create([
        _make_create(tag_id="SA-001", species=AnimalSpecies.CATTLE),
        _make_create(tag_id="SA-002", species=AnimalSpecies.SHEEP),
        _make_create(tag_id="SA-003", species=AnimalSpecies.GOAT),
    ])
    await db.commit()
    for a in animals:
        await db.refresh(a)
    return animals


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL MODEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalModelHelpers:

    def test_is_active_when_active(self):
        assert Animal(status=AnimalStatus.ACTIVE).is_active is True

    def test_is_active_false_for_other_statuses(self):
        for s in [AnimalStatus.SOLD, AnimalStatus.DECEASED,
                  AnimalStatus.SICK, AnimalStatus.QUARANTINE]:
            assert Animal(status=s).is_active is False

    def test_age_days_none_without_birth_date(self):
        assert Animal(birth_date=None).age_days is None

    def test_age_days_correct(self):
        birth = datetime.utcnow() - timedelta(days=100)
        days = Animal(birth_date=birth).age_days
        assert 99 <= days <= 101

    def test_age_months_none_without_birth_date(self):
        assert Animal(birth_date=None).age_months is None

    def test_age_months_approx(self):
        birth = datetime.utcnow() - timedelta(days=365)
        months = Animal(birth_date=birth).age_months
        assert 11.5 <= months <= 12.5

    def test_mark_detected_sets_first_and_last(self):
        ts = datetime.utcnow()
        a = Animal(total_detections=0)
        a.mark_detected(ts)
        assert a.first_detected_at == ts
        assert a.last_detected_at  == ts
        assert a.total_detections  == 1

    def test_mark_detected_preserves_first(self):
        first_ts = datetime.utcnow() - timedelta(hours=1)
        a = Animal(total_detections=1, first_detected_at=first_ts, last_detected_at=first_ts)
        second_ts = datetime.utcnow()
        a.mark_detected(second_ts)
        assert a.first_detected_at == first_ts
        assert a.last_detected_at  == second_ts
        assert a.total_detections  == 2

    def test_mark_detected_uses_utcnow_as_default(self):
        before = datetime.utcnow()
        a = Animal(total_detections=0)
        a.mark_detected()
        after = datetime.utcnow()
        assert before <= a.last_detected_at <= after

    def test_mark_detected_increments_repeatedly(self):
        a = Animal(total_detections=0)
        for i in range(1, 6):
            a.mark_detected()
            assert a.total_detections == i

    def test_repr_contains_tag_species_status(self):
        a = Animal(tag_id="JNV-001", species=AnimalSpecies.CATTLE, status=AnimalStatus.ACTIVE)
        r = repr(a)
        assert "JNV-001" in r and "cattle" in r and "active" in r


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryCreate:

    async def test_create_returns_id(self, db, repo):
        a = await repo.create(_make_create(tag_id="CRT-001"))
        await db.commit()
        assert a.id is not None and a.id > 0

    async def test_create_saves_all_fields(self, db, repo):
        data = _make_create(
            tag_id="CRT-002", species=AnimalSpecies.SHEEP,
            gender=AnimalGender.MALE, breed="Merino",
            notes="Test", status=AnimalStatus.QUARANTINE,
        )
        a = await repo.create(data)
        await db.commit()
        assert a.species == AnimalSpecies.SHEEP
        assert a.gender  == AnimalGender.MALE
        assert a.breed   == "Merino"
        assert a.notes   == "Test"
        assert a.status  == AnimalStatus.QUARANTINE

    async def test_create_tag_id_uppercased_by_schema(self, db, repo):
        a = await repo.create(_make_create(tag_id="low-001"))
        await db.commit()
        assert a.tag_id == "LOW-001"

    async def test_create_default_status_active(self, db, repo):
        a = await repo.create(AnimalCreate(
            tag_id="DEF-001", species=AnimalSpecies.GOAT, acquisition_date=_NOW))
        await db.commit()
        assert a.status == AnimalStatus.ACTIVE

    async def test_create_five_animals_unique_ids(self, db, repo):
        ids = [
            (await repo.create(_make_create(tag_id=f"MUL-{i:03d}"))).id
            for i in range(5)
        ]
        await db.commit()
        assert len(set(ids)) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — BULK CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryBulkCreate:

    async def test_bulk_empty_returns_empty(self, db, repo):
        assert await repo.bulk_create([]) == []

    async def test_bulk_returns_all_with_ids(self, db, repo):
        data = [_make_create(tag_id=f"BLK-{i:03d}") for i in range(3)]
        result = await repo.bulk_create(data)
        await db.commit()
        assert len(result) == 3
        assert all(a.id is not None for a in result)

    async def test_bulk_order_preserved(self, db, repo):
        tags = ["BLK-A01", "BLK-A02", "BLK-A03"]
        result = await repo.bulk_create([_make_create(tag_id=t) for t in tags])
        await db.commit()
        assert [a.tag_id for a in result] == tags

    async def test_bulk_large_batch(self, db, repo):
        data = [_make_create(tag_id=f"BIG-{i:04d}") for i in range(50)]
        result = await repo.bulk_create(data)
        await db.commit()
        assert len(result) == 50


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryGet:

    async def test_get_by_id_existing(self, db, repo, sample_animal):
        a = await repo.get_by_id(sample_animal.id)
        assert a is not None and a.id == sample_animal.id

    async def test_get_by_id_none_for_missing(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_by_id_none_for_negative(self, db, repo):
        assert await repo.get_by_id(-1) is None

    async def test_get_by_id_none_for_zero(self, db, repo):
        assert await repo.get_by_id(0) is None

    async def test_get_by_tag_id_exact(self, db, repo, sample_animal):
        a = await repo.get_by_tag_id(sample_animal.tag_id)
        assert a is not None and a.id == sample_animal.id

    async def test_get_by_tag_id_case_insensitive(self, db, repo):
        created = await repo.create(_make_create(tag_id="TAG-CASE-001"))
        await db.commit()
        for variant in ["tag-case-001", "TAG-CASE-001", "Tag-Case-001"]:
            found = await repo.get_by_tag_id(variant)
            assert found is not None and found.id == created.id

    async def test_get_by_tag_id_none_for_missing(self, db, repo):
        assert await repo.get_by_tag_id("PHANTOM-999") is None

    async def test_get_existing_tags_empty_input(self, db, repo):
        assert await repo.get_existing_tags([]) == set()

    async def test_get_existing_tags_finds_correct(self, db, repo):
        await repo.create(_make_create(tag_id="EXT-001"))
        await db.commit()
        result = await repo.get_existing_tags(["EXT-001", "EXT-002"])
        assert "EXT-001" in result
        assert "EXT-002" not in result

    async def test_get_existing_tags_none_existing(self, db, repo):
        result = await repo.get_existing_tags(["NON-001", "NON-002"])
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — GET ALL & COUNT
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryGetAll:

    async def test_get_all_returns_created(self, db, repo, sample_animals):
        result = await repo.get_all()
        assert len(result) >= 3

    async def test_get_all_species_cattle_filter(self, db, repo, sample_animals):
        cattle = await repo.get_all(species="cattle")
        assert all(a.species == AnimalSpecies.CATTLE for a in cattle)

    async def test_get_all_invalid_species_no_error(self, db, repo, sample_animals):
        # Noma'lum species — xato bo'lmaydi, e'tiborga olinmaydi
        result = await repo.get_all(species="dragon")
        assert isinstance(result, (list, type(result)))

    async def test_get_all_status_filter(self, db, repo):
        await repo.create(_make_create(tag_id="QRN-001", status=AnimalStatus.QUARANTINE))
        await db.commit()
        quarantine = await repo.get_all(status=AnimalStatus.QUARANTINE)
        assert all(a.status == AnimalStatus.QUARANTINE for a in quarantine)
        assert len(quarantine) >= 1

    async def test_get_all_skip(self, db, repo, sample_animals):
        all_a   = await repo.get_all(skip=0, limit=100)
        skipped = await repo.get_all(skip=1, limit=100)
        assert len(skipped) == len(all_a) - 1

    async def test_get_all_limit(self, db, repo, sample_animals):
        assert len(await repo.get_all(limit=2)) <= 2

    async def test_get_all_limit_zero(self, db, repo, sample_animals):
        assert len(await repo.get_all(limit=0)) == 0

    async def test_count_matches_get_all(self, db, repo, sample_animals):
        total = await repo.count()
        animals = await repo.get_all(limit=1000)
        assert total == len(animals)

    async def test_count_by_species(self, db, repo, sample_animals):
        cattle_count = await repo.count(species="cattle")
        cattle_list  = await repo.get_all(species="cattle", limit=1000)
        assert cattle_count == len(cattle_list)

    async def test_count_by_status(self, db, repo):
        await repo.create(_make_create(tag_id="ST1-001", status=AnimalStatus.SICK))
        await repo.create(_make_create(tag_id="ST1-002", status=AnimalStatus.SICK))
        await db.commit()
        assert await repo.count(status=AnimalStatus.SICK) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryUpdate:

    async def test_update_single_field(self, db, repo, sample_animal):
        updated = await repo.update(sample_animal.id, AnimalUpdate(breed="Holstein"))
        await db.commit()
        assert updated.breed == "Holstein"

    async def test_update_status(self, db, repo, sample_animal):
        updated = await repo.update(sample_animal.id, AnimalUpdate(status=AnimalStatus.QUARANTINE))
        await db.commit()
        assert updated.status == AnimalStatus.QUARANTINE

    async def test_update_multiple_fields(self, db, repo, sample_animal):
        upd = AnimalUpdate(breed="Jersey", notes="Tekshirildi", status=AnimalStatus.SICK)
        updated = await repo.update(sample_animal.id, upd)
        await db.commit()
        assert updated.breed  == "Jersey"
        assert updated.notes  == "Tekshirildi"
        assert updated.status == AnimalStatus.SICK

    async def test_update_none_fields_unchanged(self, db, repo, sample_animal):
        original_species = sample_animal.species
        await repo.update(sample_animal.id, AnimalUpdate(breed="Changed"))
        await db.commit()
        fresh = await repo.get_by_id(sample_animal.id)
        assert fresh.species == original_species

    async def test_update_nonexistent_returns_none(self, db, repo):
        assert await repo.update(999999, AnimalUpdate(breed="Ghost")) is None


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryDelete:

    async def test_delete_existing_returns_true(self, db, repo, sample_animal):
        result = await repo.delete(sample_animal.id)
        await db.commit()
        assert result is True

    async def test_deleted_not_found(self, db, repo, sample_animal):
        aid = sample_animal.id
        await repo.delete(aid)
        await db.commit()
        assert await repo.get_by_id(aid) is None

    async def test_delete_nonexistent_returns_false(self, db, repo):
        assert await repo.delete(999999) is False

    async def test_delete_negative_id_returns_false(self, db, repo):
        assert await repo.delete(-1) is False


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — PIPELINE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryPipeline:

    async def test_get_first_active_returns_active(self, db, repo, sample_animal):
        first = await repo.get_first_active()
        assert first is not None and first.status == AnimalStatus.ACTIVE

    async def test_increment_detection_count_increases(self, db, repo, sample_animal):
        old = sample_animal.total_detections
        await repo.increment_detection_count(sample_animal.id)
        await db.commit()
        await db.refresh(sample_animal)
        assert sample_animal.total_detections == old + 1

    async def test_increment_sets_last_detected(self, db, repo, sample_animal):
        await repo.increment_detection_count(sample_animal.id)
        await db.commit()
        await db.refresh(sample_animal)
        assert sample_animal.last_detected_at is not None

    async def test_increment_nonexistent_no_error(self, db, repo):
        await repo.increment_detection_count(999999)  # Xato bo'lmasligi kerak

    async def test_increment_five_times(self, db, repo, sample_animal):
        start = sample_animal.total_detections
        for _ in range(5):
            await repo.increment_detection_count(sample_animal.id)
        await db.commit()
        await db.refresh(sample_animal)
        assert sample_animal.total_detections == start + 5


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL REPOSITORY — ADVANCED SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalRepositoryAdvancedSearch:

    async def test_no_filters_returns_all(self, db, repo, sample_animals):
        animals, total = await repo.advanced_search()
        assert total >= 3

    async def test_filter_by_tag_id_partial(self, db, repo):
        await repo.create(_make_create(tag_id="SRCH-001"))
        await repo.create(_make_create(tag_id="SRCH-002"))
        await db.commit()
        animals, total = await repo.advanced_search(tag_id="SRCH")
        assert total >= 2
        assert all("SRCH" in a.tag_id for a in animals)

    async def test_filter_by_species(self, db, repo, sample_animals):
        animals, _ = await repo.advanced_search(species=AnimalSpecies.CATTLE)
        assert all(a.species == AnimalSpecies.CATTLE for a in animals)

    async def test_filter_by_status(self, db, repo):
        await repo.create(_make_create(tag_id="SICK-001", status=AnimalStatus.SICK))
        await db.commit()
        animals, total = await repo.advanced_search(status=AnimalStatus.SICK)
        assert total >= 1
        assert all(a.status == AnimalStatus.SICK for a in animals)

    async def test_filter_by_breed_partial(self, db, repo):
        await repo.create(_make_create(tag_id="HOL-001", breed="Holstein"))
        await repo.create(_make_create(tag_id="HOL-002", breed="Holstein Friesian"))
        await db.commit()
        animals, total = await repo.advanced_search(breed="Holst")
        assert total >= 2

    async def test_filter_by_min_detections(self, db, repo):
        a = await repo.create(_make_create(tag_id="DET-ADV-001"))
        await db.commit()
        for _ in range(5):
            await repo.increment_detection_count(a.id)
        await db.commit()
        animals, total = await repo.advanced_search(min_detections=5)
        assert total >= 1
        assert all(a.total_detections >= 5 for a in animals)

    async def test_search_text_in_tag_id(self, db, repo):
        await repo.create(_make_create(tag_id="TXT-FINDME-001"))
        await db.commit()
        animals, total = await repo.advanced_search(search_text="FINDME")
        assert total >= 1

    async def test_search_text_in_notes(self, db, repo):
        await repo.create(_make_create(tag_id="NTE-ADV-001", notes="Excellent milk producer"))
        await db.commit()
        animals, total = await repo.advanced_search(search_text="Excellent")
        assert total >= 1

    async def test_sort_asc(self, db, repo):
        await repo.create(_make_create(tag_id="ZZZ-SORT-999"))
        await repo.create(_make_create(tag_id="AAA-SORT-001"))
        await db.commit()
        animals, _ = await repo.advanced_search(sort_by="tag_id", sort_order="asc")
        tags = [a.tag_id for a in animals]
        assert tags == sorted(tags)

    async def test_sort_desc(self, db, repo):
        await repo.create(_make_create(tag_id="DES-SRT-001"))
        await repo.create(_make_create(tag_id="DES-SRT-002"))
        await db.commit()
        animals, _ = await repo.advanced_search(sort_by="tag_id", sort_order="desc")
        tags = [a.tag_id for a in animals]
        assert tags == sorted(tags, reverse=True)

    async def test_pagination_pages_disjoint(self, db, repo, sample_animals):
        page1, _ = await repo.advanced_search(skip=0, limit=2)
        page2, _ = await repo.advanced_search(skip=2, limit=2)
        assert {a.id for a in page1}.isdisjoint({a.id for a in page2})

    async def test_returns_tuple(self, db, repo):
        result = await repo.advanced_search()
        assert isinstance(result, tuple) and len(result) == 2

    async def test_combined_filters(self, db, repo):
        await repo.create(_make_create(
            tag_id="CMB-001", species=AnimalSpecies.SHEEP,
            status=AnimalStatus.ACTIVE, breed="Merino",
        ))
        await db.commit()
        animals, total = await repo.advanced_search(
            species=AnimalSpecies.SHEEP, status=AnimalStatus.ACTIVE, breed="Merino"
        )
        assert total >= 1


class TestAnimalRepositorySearchByText:

    async def test_finds_in_tag_id(self, db, repo):
        await repo.create(_make_create(tag_id="TXS-UNIQUE-001"))
        await db.commit()
        animals, total = await repo.search_by_text("UNIQUE")
        assert total >= 1

    async def test_finds_in_breed(self, db, repo):
        await repo.create(_make_create(tag_id="BRD-TXS-001", breed="UniqueBreedXYZ"))
        await db.commit()
        animals, total = await repo.search_by_text("UniqueBreedXYZ")
        assert total >= 1

    async def test_finds_in_notes(self, db, repo):
        await repo.create(_make_create(tag_id="NTS-TXS-002", notes="Special treatment"))
        await db.commit()
        animals, total = await repo.search_by_text("Special treatment")
        assert total >= 1

    async def test_case_insensitive(self, db, repo):
        await repo.create(_make_create(tag_id="CSI-TXS-001", breed="Holstein"))
        await db.commit()
        for q in ["holstein", "HOLSTEIN", "HoLsTeIn"]:
            _, total = await repo.search_by_text(q)
            assert total >= 1, f"'{q}' uchun topilmadi"

    async def test_no_results(self, db, repo):
        animals, total = await repo.search_by_text("ZZZ_NONEXISTENT_XYZ_123")
        assert total == 0

    async def test_returns_tuple(self, db, repo):
        result = await repo.search_by_text("test")
        assert isinstance(result, tuple) and len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalServiceCreate:

    async def test_create_success(self, db, svc):
        r = await svc.create_animal(_make_create(tag_id="SVC-001"))
        await db.commit()
        assert r.id is not None and r.tag_id == "SVC-001"

    async def test_create_returns_animal_response(self, db, svc):
        from app.schemas.animal import AnimalResponse
        r = await svc.create_animal(_make_create(tag_id="SVC-002"))
        await db.commit()
        assert isinstance(r, AnimalResponse)

    async def test_create_duplicate_tag_raises(self, db, svc):
        await svc.create_animal(_make_create(tag_id="DUP-001"))
        await db.commit()
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            await svc.create_animal(_make_create(tag_id="DUP-001"))
        assert "DUP-001" in exc_info.value.message
        assert "existing_id" in exc_info.value.details

    async def test_create_duplicate_case_insensitive(self, db, svc):
        await svc.create_animal(_make_create(tag_id="UPP-001"))
        await db.commit()
        with pytest.raises(EntityAlreadyExistsError):
            await svc.create_animal(_make_create(tag_id="upp-001"))

    async def test_create_all_species(self, db, svc):
        for species in AnimalSpecies:
            tag = f"SPE-{species.value[:3].upper()}"
            r = await svc.create_animal(_make_create(tag_id=tag, species=species))
            await db.commit()
            assert r.species == species


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL SERVICE — GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalServiceGet:

    async def test_get_existing(self, db, svc, sample_animal):
        r = await svc.get_animal(sample_animal.id)
        assert r.id == sample_animal.id

    async def test_get_nonexistent_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal(999999)

    async def test_get_animals_returns_list_response(self, db, svc, sample_animals):
        from app.schemas.animal import AnimalListResponse
        r = await svc.get_animals()
        assert isinstance(r, AnimalListResponse)
        assert r.total >= 3

    async def test_get_animals_species_filter(self, db, svc, sample_animals):
        r = await svc.get_animals(species="cattle")
        assert all(a.species == AnimalSpecies.CATTLE for a in r.items)

    async def test_get_animals_status_filter(self, db, svc):
        await svc.create_animal(_make_create(tag_id="QRN-SVC-001", status=AnimalStatus.QUARANTINE))
        await db.commit()
        r = await svc.get_animals(status="quarantine")
        assert all(a.status == AnimalStatus.QUARANTINE for a in r.items)

    async def test_get_animals_pagination_disjoint(self, db, svc, sample_animals):
        p1 = await svc.get_animals(skip=0, limit=2)
        p2 = await svc.get_animals(skip=2, limit=2)
        assert {a.id for a in p1.items}.isdisjoint({a.id for a in p2.items})

    async def test_get_animal_by_tag_existing(self, db, svc):
        await svc.create_animal(_make_create(tag_id="TAG-SVC-001"))
        await db.commit()
        r = await svc.get_animal_by_tag("TAG-SVC-001")
        assert r.tag_id == "TAG-SVC-001"

    async def test_get_animal_by_tag_nonexistent_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal_by_tag("NONEXISTENT-999")


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL SERVICE — UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalServiceUpdate:

    async def test_update_active_success(self, db, svc, sample_animal):
        r = await svc.update_animal(sample_animal.id, AnimalUpdate(breed="Updated"))
        await db.commit()
        assert r.breed == "Updated"

    async def test_update_status_change(self, db, svc, sample_animal):
        r = await svc.update_animal(sample_animal.id, AnimalUpdate(status=AnimalStatus.QUARANTINE))
        await db.commit()
        assert r.status == AnimalStatus.QUARANTINE

    async def test_update_archived_sold_raises(self, db, svc):
        created = await svc.create_animal(_make_create(tag_id="ARC-SLD-001", status=AnimalStatus.SOLD))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError):
            await svc.update_animal(created.id, AnimalUpdate(breed="Fail"))

    async def test_update_archived_deceased_raises(self, db, svc):
        created = await svc.create_animal(_make_create(tag_id="ARC-DEC-001", status=AnimalStatus.DECEASED))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError):
            await svc.update_animal(created.id, AnimalUpdate(breed="Fail"))

    async def test_update_nonexistent_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_animal(999999, AnimalUpdate(breed="Ghost"))

    async def test_update_returns_animal_response(self, db, svc, sample_animal):
        from app.schemas.animal import AnimalResponse
        r = await svc.update_animal(sample_animal.id, AnimalUpdate(breed="X"))
        assert isinstance(r, AnimalResponse)


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL SERVICE — DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnimalServiceDelete:

    async def test_delete_active_success(self, db, svc, sample_animal):
        aid = sample_animal.id
        await svc.delete_animal(aid)
        await db.commit()
        assert await AnimalRepository(db).get_by_id(aid) is None

    async def test_delete_nonexistent_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_animal(999999)

    async def test_delete_sold_raises(self, db, svc):
        r = await svc.create_animal(_make_create(tag_id="DEL-SLD-001", status=AnimalStatus.SOLD))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError):
            await svc.delete_animal(r.id)

    async def test_delete_deceased_raises(self, db, svc):
        r = await svc.create_animal(_make_create(tag_id="DEL-DEC-001", status=AnimalStatus.DECEASED))
        await db.commit()
        with pytest.raises(BusinessRuleViolationError):
            await svc.delete_animal(r.id)


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMAL SERVICE — CSV IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _csv(*rows: dict, header: list[str] | None = None) -> str:
    if header is None:
        header = ["tag_id", "species", "breed", "gender", "status"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(str(row.get(h, "")) for h in header))
    return "\n".join(lines)


class TestAnimalServiceCsvImport:

    async def test_import_single_valid_row(self, db, svc):
        r = await svc.import_from_csv(_csv(
            {"tag_id": "CSV-001", "species": "cattle", "breed": "Holstein",
             "gender": "female", "status": "active"}
        ))
        await db.commit()
        assert r.created == 1 and r.errors == 0 and r.total_rows == 1

    async def test_import_multiple_rows(self, db, svc):
        rows = [{"tag_id": f"CSV-M{i:02d}", "species": "cattle", "gender": "female", "status": "active"}
                for i in range(5)]
        r = await svc.import_from_csv(_csv(*rows))
        await db.commit()
        assert r.created == 5 and r.errors == 0

    async def test_import_skip_duplicates_true(self, db, svc):
        await svc.import_from_csv(_csv({"tag_id": "DUP-CSV-001", "species": "cattle"}))
        await db.commit()
        r = await svc.import_from_csv(
            _csv({"tag_id": "DUP-CSV-001", "species": "cattle"}), skip_duplicates=True
        )
        assert r.skipped == 1 and r.created == 0

    async def test_import_skip_duplicates_false_errors(self, db, svc):
        await svc.import_from_csv(_csv({"tag_id": "ERR-CSV-001", "species": "cattle"}))
        await db.commit()
        r = await svc.import_from_csv(
            _csv({"tag_id": "ERR-CSV-001", "species": "cattle"}), skip_duplicates=False
        )
        assert r.errors >= 1

    async def test_import_mixed_valid_invalid(self, db, svc):
        csv_content = (
            "tag_id,species\n"
            "MIX-001,cattle\n"
            "MIX-002,INVALID_SPECIES\n"
            "MIX-003,sheep\n"
        )
        r = await svc.import_from_csv(csv_content)
        await db.commit()
        assert r.created >= 2 and r.errors >= 1

    async def test_import_empty_raises(self, db, svc):
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.import_from_csv("tag_id,species\n")
        assert "bo'sh" in exc_info.value.message.lower() or "empty" in exc_info.value.message.lower()

    async def test_import_missing_tag_id_column_raises(self, db, svc):
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.import_from_csv("breed,gender\nHolstein,female\n")
        msg = exc_info.value.message.lower()
        assert "tag_id" in msg or "majburiy" in msg

    async def test_import_missing_species_column_raises(self, db, svc):
        with pytest.raises(BusinessRuleViolationError):
            await svc.import_from_csv("tag_id,breed\nCSV-NS-001,Holstein\n")

    async def test_import_result_structure_valid(self, db, svc):
        r = await svc.import_from_csv(_csv({"tag_id": "STR-001", "species": "cattle"}))
        await db.commit()
        assert hasattr(r, "total_rows") and hasattr(r, "created")
        assert hasattr(r, "skipped")   and hasattr(r, "errors")
        assert hasattr(r, "details")
        assert r.total_rows == r.created + r.skipped + r.errors

    async def test_import_details_sorted_by_row(self, db, svc):
        rows = [{"tag_id": f"ORD-{i:03d}", "species": "cattle"} for i in range(3, 0, -1)]
        r = await svc.import_from_csv(_csv(*rows))
        row_numbers = [d.row for d in r.details]
        assert row_numbers == sorted(row_numbers)

    async def test_import_all_species_valid(self, db, svc):
        rows = [{"tag_id": f"SPE-IMP-{s.value[:3].upper()}", "species": s.value}
                for s in AnimalSpecies]
        r = await svc.import_from_csv(_csv(*rows))
        await db.commit()
        assert r.errors == 0 and r.created == len(AnimalSpecies)

    async def test_import_exceeds_max_rows_raises(self, db, svc):
        rows = [{"tag_id": f"MAX-{i:06d}", "species": "cattle"}
                for i in range(_MAX_IMPORT_ROWS + 1)]
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.import_from_csv(_csv(*rows))
        assert str(_MAX_IMPORT_ROWS) in exc_info.value.message or \
               "ko'p" in exc_info.value.message.lower()

    async def test_import_extra_columns_ok(self, db, svc):
        csv_content = (
            "tag_id,species,extra_col\n"
            "EXT-001,cattle,ignored_value\n"
        )
        r = await svc.import_from_csv(csv_content)
        await db.commit()
        assert r.created >= 1 and r.errors == 0

    async def test_import_all_species_types_created(self, db, svc):
        csv_content = (
            "tag_id,species\n"
            "IMP-CAT-001,cattle\n"
            "IMP-SHP-001,sheep\n"
            "IMP-GOT-001,goat\n"
            "IMP-HRS-001,horse\n"
            "IMP-OTH-001,other\n"
        )
        r = await svc.import_from_csv(csv_content)
        await db.commit()
        assert r.created == 5 and r.errors == 0

    async def test_import_only_required_columns(self, db, svc):
        """Faqat tag_id va species bilan import muvaffaqiyatli."""
        csv_content = "tag_id,species\nMIN-001,cattle\n"
        r = await svc.import_from_csv(csv_content)
        await db.commit()
        assert r.created >= 1

    async def test_import_detail_created_has_animal_id(self, db, svc):
        """Muvaffaqiyatli yaratilgan satr animal_id ga ega."""
        r = await svc.import_from_csv(_csv({"tag_id": "AID-001", "species": "cattle"}))
        await db.commit()
        created_details = [d for d in r.details if d.status == "created"]
        assert len(created_details) >= 1
        assert all(d.animal_id is not None for d in created_details)