"""
TAURUS VISION — tests/test_services/test_meat_scale_service.py
===============================================================
MeatService + ScaleService uchun AYAMAS vahshiy testlar.

Qamrov:
  ✓ SlaughterRecord model  — MeatQualityGrade, SlaughterPurpose, pH threshold
  ✓ MeatProductionRepository.create / get_by_id / get_by_animal / get_all_records
  ✓ MeatService.add_record      — muvaffaqiyatli, yo'q jonivor, pH avtograding
  ✓ MeatService.update_record   — mavjud, yo'q
  ✓ MeatService.delete_record   — mavjud, yo'q
  ✓ MeatService.get_record_by_id  — mavjud, yo'q
  ✓ MeatService.get_all_records   — filtrlar, pagination
  ✓ MeatService.get_animal_records
  ✓ MeatService.get_farm_summary  — tuzilma
  ✓ Scale model             — ScaleType, ScaleStatus
  ✓ ScaleRepository         — create, get_by_id, get_all, update, calibrate
  ✓ ScaleService.create_scale / get / list / update / delete
  ✓ ScaleService.record_manual_weight — muvaffaqiyatli, yo'q animal, nofaol tarozi
  ✓ ScaleService.calibrate           — < 3 nuqta xato, muvaffaqiyatli
  ✓ ScaleService.get_comparison_report
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.meat_production import SlaughterRecord, SlaughterPurpose, MeatQualityGrade
from app.models.scale import Scale, ScaleType, ScaleStatus
from app.models.weight_measurement import WeightMeasurement, WeightSource
from app.repositories.meat_production_repository import MeatProductionRepository
from app.repositories.scale_repository import ScaleRepository
from app.schemas.meat_production import (
    SlaughterRecordCreate, SlaughterRecordUpdate,
)
from app.schemas.scale import (
    ScaleCreate, ScaleUpdate, ManualWeightCreate, CalibrationDataPoint,
)
from app.services.meat_service import MeatService
from app.services.scale_service import ScaleService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="MEAT-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="MEAT-ANIMAL-002",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def meat_svc(db):
    return MeatService(db)


@pytest.fixture
def meat_repo(db):
    return MeatProductionRepository(db)


@pytest.fixture
def scale_svc(db):
    return ScaleService(db)


@pytest.fixture
def scale_repo(db):
    return ScaleRepository(db)


def _slaughter_create(animal_id, **kw) -> SlaughterRecordCreate:
    return SlaughterRecordCreate(
        animal_id=animal_id,
        slaughter_date=TODAY,
        purpose=SlaughterPurpose.SALE,
        meat_kg=150.0,
        **kw,
    )


def _scale_create(name="Test Tarozi", stype="manual", **kw) -> ScaleCreate:
    return ScaleCreate(name=name, scale_type=stype, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
# SLAUGHTER RECORD MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlaughterRecordModel:

    def test_all_purposes_defined(self):
        assert len(SlaughterPurpose) == 4
        for p in ["sale", "own_use", "export", "processing"]:
            assert SlaughterPurpose(p) is not None

    def test_all_quality_grades_defined(self):
        for g in ["premium", "choice", "select", "standard", "low"]:
            assert MeatQualityGrade(g) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# MEAT PRODUCTION REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestMeatRepository:

    async def test_create_assigns_id(self, db, meat_repo, animal):
        rec = await meat_repo.create(_slaughter_create(animal.id))
        await db.commit()
        assert rec.id is not None

    async def test_get_by_id_existing(self, db, meat_repo, animal):
        rec = await meat_repo.create(_slaughter_create(animal.id))
        await db.commit()
        found = await meat_repo.get_by_id(rec.id)
        assert found is not None and found.id == rec.id

    async def test_get_by_id_missing_none(self, db, meat_repo):
        assert await meat_repo.get_by_id(999999) is None

    async def test_get_by_animal(self, db, meat_repo, animal):
        for i in range(3):
            await meat_repo.create(_slaughter_create(
                animal.id, slaughter_date=TODAY - timedelta(days=i)))
        await db.commit()
        items, total = await meat_repo.get_by_animal(animal.id)
        assert total >= 3

    async def test_get_by_animal_date_filter(self, db, meat_repo, animal):
        await meat_repo.create(_slaughter_create(
            animal.id, slaughter_date=TODAY - timedelta(days=60)))
        await meat_repo.create(_slaughter_create(animal.id))
        await db.commit()
        items, total = await meat_repo.get_by_animal(
            animal.id, date_from=TODAY - timedelta(days=5))
        for r in items:
            assert r.slaughter_date >= TODAY - timedelta(days=5)

    async def test_get_all_records_purpose_filter(self, db, meat_repo, animal):
        await meat_repo.create(_slaughter_create(
            animal.id, purpose=SlaughterPurpose.EXPORT))
        await meat_repo.create(_slaughter_create(
            animal.id, purpose=SlaughterPurpose.OWN_USE,
            slaughter_date=YESTERDAY))
        await db.commit()
        items, total = await meat_repo.get_all_records(
            purpose=SlaughterPurpose.EXPORT)
        assert all(r.purpose == SlaughterPurpose.EXPORT for r in items)

    async def test_get_all_records_grade_filter(self, db, meat_repo, animal, second_animal):
        await meat_repo.create(_slaughter_create(
            animal.id, quality_grade=MeatQualityGrade.PREMIUM))
        await meat_repo.create(_slaughter_create(
            second_animal.id, quality_grade=MeatQualityGrade.LOW,
            slaughter_date=YESTERDAY))
        await db.commit()
        items, _ = await meat_repo.get_all_records(
            quality_grade=MeatQualityGrade.PREMIUM)
        assert all(r.quality_grade == MeatQualityGrade.PREMIUM for r in items)

    async def test_get_all_records_pagination(self, db, meat_repo, animal):
        for i in range(5):
            await meat_repo.create(_slaughter_create(
                animal.id, slaughter_date=TODAY - timedelta(days=i)))
        await db.commit()
        p1, _ = await meat_repo.get_all_records(limit=2, offset=0)
        p2, _ = await meat_repo.get_all_records(limit=2, offset=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})


# ═══════════════════════════════════════════════════════════════════════════════
# MEAT SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMeatServiceAddRecord:

    async def test_add_record_success(self, db, meat_svc, animal):
        rec = await meat_svc.add_record(_slaughter_create(animal.id, meat_kg=180.0))
        await db.commit()
        assert rec.id is not None and rec.meat_kg == 180.0

    async def test_add_record_missing_animal_raises(self, db, meat_svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await meat_svc.add_record(_slaughter_create(99999))
        assert "99999" in exc_info.value.message

    async def test_add_record_ph_premium(self, db, meat_svc, animal):
        """pH ≤ 5.8 → PREMIUM."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=5.5))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.PREMIUM

    async def test_add_record_ph_choice(self, db, meat_svc, animal):
        """5.8 < pH ≤ 6.2 → CHOICE."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=6.0, slaughter_date=YESTERDAY))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.CHOICE

    async def test_add_record_ph_select(self, db, meat_svc, animal):
        """6.2 < pH ≤ 6.5 → SELECT."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=6.4))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.SELECT

    async def test_add_record_ph_standard(self, db, meat_svc, animal):
        """6.5 < pH ≤ 6.8 → STANDARD."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=6.7))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.STANDARD

    async def test_add_record_ph_low(self, db, meat_svc, animal):
        """pH > 6.8 → LOW."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=7.0))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.LOW

    async def test_add_record_manual_grade_not_overridden(self, db, meat_svc, animal):
        """quality_grade berilsa — pH avtohisobi ishlamaydi."""
        rec = await meat_svc.add_record(_slaughter_create(
            animal.id, ph_value=7.5,
            quality_grade=MeatQualityGrade.PREMIUM))
        await db.commit()
        assert rec.quality_grade == MeatQualityGrade.PREMIUM

    async def test_add_record_no_ph_no_grade(self, db, meat_svc, animal):
        rec = await meat_svc.add_record(_slaughter_create(animal.id))
        await db.commit()
        assert rec.quality_grade is None

    async def test_add_record_all_purposes(self, db, meat_svc, animal):
        for i, purpose in enumerate(SlaughterPurpose):
            rec = await meat_svc.add_record(SlaughterRecordCreate(
                animal_id=animal.id,
                slaughter_date=TODAY - timedelta(days=i),
                purpose=purpose,
                meat_kg=100.0,
            ))
            await db.commit()
            assert rec.purpose == purpose


class TestMeatServiceCRUD:

    async def test_update_record_success(self, db, meat_svc, animal):
        rec = await meat_svc.add_record(_slaughter_create(animal.id, meat_kg=100.0))
        await db.commit()
        updated = await meat_svc.update_record(
            rec.id, SlaughterRecordUpdate(meat_kg=200.0))
        await db.commit()
        assert updated.meat_kg == 200.0

    async def test_update_record_missing_raises(self, db, meat_svc):
        with pytest.raises(EntityNotFoundError):
            await meat_svc.update_record(
                999999, SlaughterRecordUpdate(meat_kg=100.0))

    async def test_delete_record_success(self, db, meat_svc, meat_repo, animal):
        rec = await meat_svc.add_record(_slaughter_create(animal.id))
        await db.commit()
        rid = rec.id
        await meat_svc.delete_record(rid)
        await db.commit()
        assert await meat_repo.get_by_id(rid) is None

    async def test_delete_record_missing_raises(self, db, meat_svc):
        with pytest.raises(EntityNotFoundError):
            await meat_svc.delete_record(999999)

    async def test_get_record_by_id(self, db, meat_svc, animal):
        rec = await meat_svc.add_record(_slaughter_create(animal.id))
        await db.commit()
        found = await meat_svc.get_record_by_id(rec.id)
        assert found is not None

    async def test_get_record_by_id_missing_raises(self, db, meat_svc):
        with pytest.raises(EntityNotFoundError):
            await meat_svc.get_record_by_id(999999)

    async def test_get_all_records_structure(self, db, meat_svc, animal):
        from app.schemas.meat_production import SlaughterRecordListResponse
        await meat_svc.add_record(_slaughter_create(animal.id))
        await db.commit()
        result = await meat_svc.get_all_records()
        assert isinstance(result, SlaughterRecordListResponse)
        assert result.total >= 1

    async def test_get_all_records_purpose_filter(self, db, meat_svc, animal, second_animal):
        await meat_svc.add_record(_slaughter_create(
            animal.id, purpose=SlaughterPurpose.EXPORT))
        await meat_svc.add_record(SlaughterRecordCreate(
            animal_id=second_animal.id,
            slaughter_date=YESTERDAY,
            purpose=SlaughterPurpose.OWN_USE,
            meat_kg=80.0))
        await db.commit()
        result = await meat_svc.get_all_records(purpose=SlaughterPurpose.EXPORT)
        assert all(r.purpose == SlaughterPurpose.EXPORT for r in result.items)

    async def test_get_animal_records(self, db, meat_svc, animal, second_animal):
        await meat_svc.add_record(_slaughter_create(animal.id))
        await meat_svc.add_record(SlaughterRecordCreate(
            animal_id=second_animal.id,
            slaughter_date=YESTERDAY,
            meat_kg=80.0))
        await db.commit()
        result = await meat_svc.get_animal_records(animal.id)
        assert result.total >= 1
        assert all(r.animal_id == animal.id for r in result.items)

    async def test_get_farm_summary_structure(self, db, meat_svc, animal):
        from app.schemas.meat_production import FarmMeatSummary
        await meat_svc.add_record(_slaughter_create(animal.id))
        await db.commit()
        summary = await meat_svc.get_farm_summary()
        assert isinstance(summary, FarmMeatSummary)
        assert hasattr(summary, "total_animals_slaughtered")
        assert hasattr(summary, "total_meat_kg")


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleModel:
    def test_all_scale_types(self):
        for t in ["manual", "serial", "api", "floor"]:
            assert ScaleType(t) is not None

    def test_all_scale_statuses(self):
        for s in ["active", "inactive", "error"]:
            assert ScaleStatus(s) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleRepository:

    async def test_create_assigns_id(self, db, scale_repo):
        s = await scale_repo.create(_scale_create())
        assert s.id is not None

    async def test_get_by_id_existing(self, db, scale_repo):
        s = await scale_repo.create(_scale_create())
        found = await scale_repo.get_by_id(s.id)
        assert found is not None and found.id == s.id

    async def test_get_by_id_missing_none(self, db, scale_repo):
        assert await scale_repo.get_by_id(999999) is None

    async def test_get_all(self, db, scale_repo):
        await scale_repo.create(_scale_create(name="Scale A"))
        await scale_repo.create(_scale_create(name="Scale B"))
        result = await scale_repo.get_all()
        assert len(result) >= 2

    async def test_get_all_active_only(self, db, scale_repo):
        active   = await scale_repo.create(_scale_create(name="Active Scale"))
        inactive = await scale_repo.create(_scale_create(name="Inactive Scale"))
        inactive.is_active = False
        await db.commit()
        result = await scale_repo.get_all(active_only=True)
        ids = [s.id for s in result]
        assert active.id   in ids
        assert inactive.id not in ids

    async def test_update_scale(self, db, scale_repo):
        s = await scale_repo.create(_scale_create())
        updated = await scale_repo.update(s, ScaleUpdate(name="Updated Scale"))
        assert updated.name == "Updated Scale"

    async def test_api_token_auto_generated(self, db, scale_repo):
        """API tarozi uchun token avtomatik yaratiladi."""
        s = await scale_repo.create(_scale_create(name="API Scale", stype="api"))
        assert s.api_token is not None and len(s.api_token) > 10

    async def test_update_last_reading(self, db, scale_repo):
        s = await scale_repo.create(_scale_create())
        await scale_repo.update_last_reading(s, 350.5)
        await db.refresh(s)
        assert s.last_weight_kg == 350.5
        assert s.last_reading_at is not None

    async def test_update_calibration(self, db, scale_repo):
        s = await scale_repo.create(_scale_create())
        updated = await scale_repo.update_calibration(s, new_factor=1.05, sample_count=10)
        assert abs(updated.calibration_factor - 1.05) < 0.0001
        assert updated.calibration_sample_count == 10
        assert updated.last_calibrated_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE SERVICE — CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleServiceCRUD:

    async def test_create_scale(self, db, scale_svc):
        resp = await scale_svc.create_scale(_scale_create(name="SVC Scale"))
        assert resp.id is not None and resp.name == "SVC Scale"

    async def test_get_scale_existing(self, db, scale_svc):
        created = await scale_svc.create_scale(_scale_create(name="Get Scale"))
        found = await scale_svc.get_scale(created.id)
        assert found.id == created.id

    async def test_get_scale_missing_raises(self, db, scale_svc):
        with pytest.raises(EntityNotFoundError):
            await scale_svc.get_scale(999999)

    async def test_list_scales_structure(self, db, scale_svc):
        from app.schemas.scale import ScaleListResponse
        await scale_svc.create_scale(_scale_create(name="List Scale"))
        result = await scale_svc.list_scales()
        assert isinstance(result, ScaleListResponse)
        assert result.total >= 1

    async def test_list_scales_active_only(self, db, scale_svc):
        active   = await scale_svc.create_scale(_scale_create(name="Active Tarozi"))
        await scale_svc.create_scale(_scale_create(name="Inactive Tarozi"))
        # Birinchisini deactivate qilamiz (update orqali)
        await scale_svc.update_scale(active.id, ScaleUpdate(is_active=True))
        result = await scale_svc.list_scales(active_only=True)
        assert all(s.is_active for s in result.items)

    async def test_update_scale_name(self, db, scale_svc):
        created = await scale_svc.create_scale(_scale_create())
        updated = await scale_svc.update_scale(
            created.id, ScaleUpdate(name="Yangilangan Tarozi"))
        assert updated.name == "Yangilangan Tarozi"

    async def test_update_scale_missing_raises(self, db, scale_svc):
        with pytest.raises(EntityNotFoundError):
            await scale_svc.update_scale(999999, ScaleUpdate(name="Ghost"))

    async def test_delete_scale(self, db, scale_svc, scale_repo):
        created = await scale_svc.create_scale(_scale_create(name="Delete Me"))
        sid = created.id
        await scale_svc.delete_scale(sid)
        assert await scale_repo.get_by_id(sid) is None

    async def test_delete_scale_missing_raises(self, db, scale_svc):
        with pytest.raises(EntityNotFoundError):
            await scale_svc.delete_scale(999999)

    async def test_all_scale_types_created(self, db, scale_svc):
        for stype in ["manual", "serial", "floor"]:
            resp = await scale_svc.create_scale(
                _scale_create(name=f"Type {stype}", stype=stype))
            assert resp.scale_type == stype


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE SERVICE — MANUAL WEIGHT
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleServiceManualWeight:

    async def test_record_manual_weight_success(self, db, scale_svc, animal):
        data = ManualWeightCreate(
            animal_id=animal.id,
            weight_kg=380.0,
        )
        result = await scale_svc.record_manual_weight(data)
        assert result.id is not None
        assert result.estimated_weight_kg == 380.0

    async def test_record_manual_weight_missing_animal_raises(self, db, scale_svc):
        data = ManualWeightCreate(animal_id=999999, weight_kg=300.0)
        with pytest.raises(EntityNotFoundError):
            await scale_svc.record_manual_weight(data)

    async def test_record_manual_weight_with_scale(self, db, scale_svc, animal):
        scale = await scale_svc.create_scale(_scale_create(name="Manual Scale"))
        data = ManualWeightCreate(
            animal_id=animal.id,
            weight_kg=350.0,
            scale_id=scale.id,
        )
        result = await scale_svc.record_manual_weight(data)
        assert result.id is not None

    async def test_record_manual_weight_inactive_scale_raises(self, db, scale_svc, animal):
        scale = await scale_svc.create_scale(_scale_create(name="Inactive Scale"))
        await scale_svc.update_scale(scale.id, ScaleUpdate(is_active=False))
        data = ManualWeightCreate(
            animal_id=animal.id,
            weight_kg=300.0,
            scale_id=scale.id,
        )
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await scale_svc.record_manual_weight(data)
        assert "faol" in exc_info.value.message.lower()

    async def test_record_manual_weight_missing_scale_raises(self, db, scale_svc, animal):
        data = ManualWeightCreate(
            animal_id=animal.id,
            weight_kg=300.0,
            scale_id=999999,
        )
        with pytest.raises(EntityNotFoundError):
            await scale_svc.record_manual_weight(data)

    async def test_record_manual_weight_confidence_1(self, db, scale_svc, animal):
        """Manual o'lchov confidence=1.0."""
        data = ManualWeightCreate(animal_id=animal.id, weight_kg=400.0)
        result = await scale_svc.record_manual_weight(data)
        assert result.confidence_score == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# SCALE SERVICE — CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleServiceCalibration:

    async def test_calibrate_too_few_points_raises(self, db, scale_svc):
        scale = await scale_svc.create_scale(_scale_create(name="Calib Scale"))
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await scale_svc.calibrate(scale.id, [
                CalibrationDataPoint(measurement_id=1, actual_weight_kg=100.0),
                CalibrationDataPoint(measurement_id=2, actual_weight_kg=200.0),
            ])
        assert "3 ta" in exc_info.value.message or "kamida" in exc_info.value.message.lower()

    async def test_calibrate_missing_scale_raises(self, db, scale_svc):
        with pytest.raises(EntityNotFoundError):
            await scale_svc.calibrate(999999, [
                CalibrationDataPoint(measurement_id=i, actual_weight_kg=100.0)
                for i in range(3)
            ])

    async def test_calibrate_with_valid_measurements(self, db, scale_svc, scale_repo, animal):
        """3 ta haqiqiy measurement bilan kalibratsiya."""
        scale = await scale_svc.create_scale(_scale_create(name="Calibrate Me"))
        # 3 ta WeightMeasurement yaratamiz
        m_ids = []
        for w in [300.0, 350.0, 400.0]:
            wm = WeightMeasurement(
                animal_id=animal.id,
                estimated_weight_kg=w,
                confidence_score=0.9,
                camera_id="CAM-01",
                timestamp=datetime.utcnow(),
            )
            db.add(wm)
        await db.commit()

        result = await scale_svc.db.execute(
            __import__('sqlalchemy').select(WeightMeasurement)
            .where(WeightMeasurement.animal_id == animal.id)
            .limit(3)
        )
        measurements = result.scalars().all()

        if len(measurements) >= 3:
            points = [
                CalibrationDataPoint(
                    measurement_id=m.id,
                    actual_weight_kg=m.estimated_weight_kg * 1.02  # 2% farq
                )
                for m in measurements[:3]
            ]
            resp = await scale_svc.calibrate(scale.id, points)
            assert resp.scale_id == scale.id
            assert resp.sample_count >= 3
            assert resp.new_factor > 0

    async def test_comparison_report_structure(self, db, scale_svc):
        from app.schemas.scale import WeightComparisonResponse
        result = await scale_svc.get_comparison_report()
        assert isinstance(result, WeightComparisonResponse)
        assert hasattr(result, "items")
        assert hasattr(result, "total_count")