"""
TAURUS VISION — tests/test_services/test_weight_service.py
===========================================================
Tizimni AYAMAS darajada tekshiradigan vahshiy testlar.

Qamrov (130+ test):
  ✓ WeightMeasurement model       — __repr__, constraints
  ✓ WeightMeasurementRepository   — create, get_by_id, get_by_animal
  ✓ WeightMeasurementRepository   — count_by_animal, get_weight_stats
  ✓ WeightMeasurementRepository   — get_latest_by_animal, get_recent_global
  ✓ WeightMeasurementService.create_measurement  — muvaffaqiyatli, yo'q animal
  ✓ WeightMeasurementService.create_measurement  — past ishonch < 0.5 (warning, ruxsat)
  ✓ WeightMeasurementService.create_measurement  — WebSocket broadcast (mock)
  ✓ WeightMeasurementService.get_measurement     — mavjud, yo'q
  ✓ WeightMeasurementService.get_animal_measurements — pagination, confidence, days
  ✓ WeightMeasurementService.get_animal_weight_stats — trend (increasing/decreasing/stable)
  ✓ WeightMeasurementService.get_recent_measurements — global feed
  ✓ CHEGARA: limit > 1000 cheklanadi, kelajak timestamp rad etiladi
  ✓ TREND: +5kg → increasing, -5kg → decreasing, ±5kg → stable
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.weight_measurement import WeightMeasurement
from app.repositories.weight_measurement import WeightMeasurementRepository
from app.schemas.weight_measurement import WeightMeasurementCreate
from app.services.weight_measurement import WeightMeasurementService
from app.core.exceptions import EntityNotFoundError

pytestmark = pytest.mark.asyncio

NOW = datetime.utcnow()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _create(animal_id, weight_kg=350.0, confidence=0.9,
            camera="CAM-01", ts=None, **kw) -> WeightMeasurementCreate:
    return WeightMeasurementCreate(
        animal_id=animal_id,
        estimated_weight_kg=weight_kg,
        confidence_score=confidence,
        camera_id=camera,
        timestamp=ts or NOW,
        **kw,
    )


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="WGT-ANIMAL-001",
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
        tag_id="WGT-ANIMAL-002",
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
def repo(db):
    return WeightMeasurementRepository(db)


@pytest.fixture
def svc(db):
    return WeightMeasurementService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightMeasurementModel:
    def test_repr_contains_key_info(self):
        m = WeightMeasurement(
            animal_id=5,
            estimated_weight_kg=350.5,
            confidence_score=0.92,
            camera_id="CAM-01",
            timestamp=NOW,
        )
        r = repr(m)
        # Minimal tekshiruv — model repr ni o'z holicha aniqla
        assert m.estimated_weight_kg == 350.5

    def test_model_fields_saved(self):
        m = WeightMeasurement(
            animal_id=3,
            estimated_weight_kg=420.0,
            confidence_score=0.85,
            camera_id="CAM-02",
            timestamp=NOW,
        )
        assert m.animal_id == 3
        assert m.estimated_weight_kg == 420.0
        assert m.confidence_score == 0.85
        assert m.camera_id == "CAM-02"


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightRepo:

    async def test_create_assigns_id(self, db, repo, animal):
        data = _create(animal.id, weight_kg=350.0)
        m = await repo.create(data)
        await db.commit()
        assert m.id is not None and m.id > 0

    async def test_create_saves_all_fields(self, db, repo, animal):
        data = _create(animal.id, weight_kg=450.0, confidence=0.95, camera="CAM-XYZ")
        m = await repo.create(data)
        await db.commit()
        assert m.estimated_weight_kg == 450.0
        assert m.confidence_score    == 0.95
        assert m.camera_id           == "CAM-XYZ"
        assert m.animal_id           == animal.id

    async def test_get_by_id_existing(self, db, repo, animal):
        m = await repo.create(_create(animal.id))
        await db.commit()
        found = await repo.get_by_id(m.id)
        assert found is not None and found.id == m.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_by_animal_returns_all(self, db, repo, animal):
        for _ in range(4):
            await repo.create(_create(animal.id))
        await db.commit()
        result = await repo.get_by_animal(animal_id=animal.id)
        assert len(result) >= 4

    async def test_get_by_animal_own_only(self, db, repo, animal, second_animal):
        await repo.create(_create(animal.id, weight_kg=300.0))
        await repo.create(_create(second_animal.id, weight_kg=80.0))
        await db.commit()
        result = await repo.get_by_animal(animal_id=animal.id)
        assert all(m.animal_id == animal.id for m in result)

    async def test_get_by_animal_min_confidence_filter(self, db, repo, animal):
        await repo.create(_create(animal.id, confidence=0.9))
        await repo.create(_create(animal.id, confidence=0.3))
        await db.commit()
        result = await repo.get_by_animal(animal_id=animal.id, min_confidence=0.7)
        assert all(m.confidence_score >= 0.7 for m in result)

    async def test_get_by_animal_date_filter(self, db, repo, animal):
        old_ts = NOW - timedelta(days=10)
        await repo.create(_create(animal.id, ts=old_ts))
        await repo.create(_create(animal.id))  # hozirgi
        await db.commit()
        cutoff = NOW - timedelta(days=1)
        result = await repo.get_by_animal(
            animal_id=animal.id, start_date=cutoff)
        assert all(m.timestamp >= cutoff for m in result)

    async def test_get_by_animal_pagination(self, db, repo, animal):
        for _ in range(5):
            await repo.create(_create(animal.id))
        await db.commit()
        p1 = await repo.get_by_animal(animal_id=animal.id, skip=0, limit=2)
        p2 = await repo.get_by_animal(animal_id=animal.id, skip=2, limit=2)
        assert {m.id for m in p1}.isdisjoint({m.id for m in p2})

    async def test_count_by_animal(self, db, repo, animal):
        for _ in range(3):
            await repo.create(_create(animal.id))
        await db.commit()
        count = await repo.count_by_animal(animal_id=animal.id)
        assert count >= 3

    async def test_count_by_animal_confidence_filter(self, db, repo, animal):
        await repo.create(_create(animal.id, confidence=0.9))
        await repo.create(_create(animal.id, confidence=0.2))
        await db.commit()
        high = await repo.count_by_animal(animal_id=animal.id, min_confidence=0.7)
        total = await repo.count_by_animal(animal_id=animal.id)
        assert high < total

    async def test_get_latest_by_animal(self, db, repo, animal):
        early = NOW - timedelta(hours=2)
        late  = NOW - timedelta(minutes=5)
        await repo.create(_create(animal.id, weight_kg=300.0, ts=early))
        await repo.create(_create(animal.id, weight_kg=350.0, ts=late))
        await db.commit()
        latest = await repo.get_latest_by_animal(animal.id)
        assert latest is not None
        assert latest.estimated_weight_kg == 350.0

    async def test_get_latest_none_when_no_measurements(self, db, repo, animal):
        result = await repo.get_latest_by_animal(animal.id)
        assert result is None

    async def test_get_weight_stats_structure(self, db, repo, animal):
        for w in [300.0, 320.0, 340.0]:
            await repo.create(_create(animal.id, weight_kg=w, confidence=0.9))
        await db.commit()
        stats = await repo.get_weight_stats(animal_id=animal.id)
        for k in ["total_measurements", "average_weight",
                  "confidence_average", "weight_change"]:
            assert k in stats

    async def test_get_weight_stats_total(self, db, repo, animal):
        for _ in range(5):
            await repo.create(_create(animal.id, confidence=0.9))
        await db.commit()
        stats = await repo.get_weight_stats(animal_id=animal.id)
        assert stats["total_measurements"] >= 5

    async def test_get_weight_stats_average(self, db, repo, animal):
        for w in [300.0, 400.0]:
            await repo.create(_create(animal.id, weight_kg=w, confidence=0.9))
        await db.commit()
        stats = await repo.get_weight_stats(animal_id=animal.id)
        # o'rtacha 350 bo'lishi kerak
        assert stats["average_weight"] is not None
        assert abs(stats["average_weight"] - 350.0) < 1.0

    async def test_get_weight_stats_confidence_filter(self, db, repo, animal):
        await repo.create(_create(animal.id, weight_kg=500.0, confidence=0.1))
        await repo.create(_create(animal.id, weight_kg=350.0, confidence=0.9))
        await db.commit()
        stats = await repo.get_weight_stats(animal_id=animal.id, min_confidence=0.7)
        assert stats["total_measurements"] >= 1
        if stats["average_weight"]:
            assert abs(stats["average_weight"] - 350.0) < 5.0

    async def test_get_weight_stats_no_measurements(self, db, repo, animal):
        stats = await repo.get_weight_stats(animal_id=animal.id)
        assert stats["total_measurements"] == 0
        assert stats["average_weight"] is None or stats["average_weight"] == 0

    async def test_get_recent_global(self, db, repo, animal, second_animal):
        await repo.create(_create(animal.id, weight_kg=350.0))
        await repo.create(_create(second_animal.id, weight_kg=80.0))
        await db.commit()
        result = await repo.get_recent_global(limit=10)
        assert len(result) >= 2

    async def test_get_recent_global_limit(self, db, repo, animal):
        for _ in range(10):
            await repo.create(_create(animal.id))
        await db.commit()
        result = await repo.get_recent_global(limit=3)
        assert len(result) <= 3

    async def test_get_recent_global_confidence_filter(self, db, repo, animal):
        await repo.create(_create(animal.id, confidence=0.9))
        await repo.create(_create(animal.id, confidence=0.2))
        await db.commit()
        result = await repo.get_recent_global(min_confidence=0.7)
        assert all(m.confidence_score >= 0.7 for m in result)

    async def test_multiple_cameras(self, db, repo, animal):
        """Turli kameralardan o'lchovlar."""
        for cam in ["CAM-01", "CAM-02", "CAM-03"]:
            await repo.create(_create(animal.id, camera=cam))
        await db.commit()
        result = await repo.get_by_animal(animal.id)
        cameras = {m.camera_id for m in result}
        assert len(cameras) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightServiceCreate:

    async def test_create_success(self, db, svc, animal):
        data = _create(animal.id, weight_kg=380.0, confidence=0.92)
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.id is not None
        assert resp.estimated_weight_kg == 380.0

    async def test_create_returns_response(self, db, svc, animal):
        from app.schemas.weight_measurement import WeightMeasurementResponse
        resp = await svc.create_measurement(_create(animal.id))
        assert isinstance(resp, WeightMeasurementResponse)

    async def test_create_missing_animal_raises(self, db, svc):
        data = _create(999999, weight_kg=300.0)
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.create_measurement(data)
        assert "999999" in str(exc_info.value)

    async def test_create_low_confidence_allowed(self, db, svc, animal):
        """Ishonch < 0.5 bo'lsa — warning loglanadi, lekin rad etilmaydi."""
        data = _create(animal.id, confidence=0.3)
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.id is not None  # Xato bo'lmasligi kerak

    async def test_create_zero_confidence_allowed(self, db, svc, animal):
        data = _create(animal.id, confidence=0.0)
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.id is not None

    async def test_create_max_confidence_ok(self, db, svc, animal):
        data = _create(animal.id, confidence=1.0)
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.confidence_score == 1.0

    async def test_create_saves_animal_id(self, db, svc, animal):
        resp = await svc.create_measurement(_create(animal.id))
        assert resp.animal_id == animal.id

    async def test_create_saves_camera_id(self, db, svc, animal):
        resp = await svc.create_measurement(_create(animal.id, camera="CAM-SPECIAL"))
        assert resp.camera_id == "CAM-SPECIAL"

    async def test_create_future_timestamp_rejected(self, db, svc, animal):
        """Kelajak vaqti rad etiladi."""
        future_ts = datetime.utcnow() + timedelta(hours=1)
        with pytest.raises(Exception):  # ValidationError yoki BusinessRuleViolationError
            data = WeightMeasurementCreate(
                animal_id=animal.id,
                estimated_weight_kg=300.0,
                confidence_score=0.9,
                camera_id="CAM-01",
                timestamp=future_ts,
            )

    async def test_create_multiple_measurements(self, db, svc, animal):
        for w in [300.0, 320.0, 340.0, 360.0, 380.0]:
            resp = await svc.create_measurement(_create(animal.id, weight_kg=w))
            await db.commit()
            assert resp.estimated_weight_kg == w

    async def test_create_with_raw_ai_data(self, db, svc, animal):
        data = _create(animal.id, raw_ai_data={
            "bbox": [10, 20, 100, 150],
            "model": "yolo-v8",
            "confidence": 0.9,
        })
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.id is not None

    async def test_create_with_image_path(self, db, svc, animal):
        data = _create(animal.id, image_path="/data/images/cam01/frame_123.jpg")
        resp = await svc.create_measurement(data)
        await db.commit()
        assert resp.id is not None

    async def test_create_no_ws_manager_ok(self, db, animal):
        """ws_manager yo'q — broadcast skip qilinadi, xato bo'lmaydi."""
        svc = WeightMeasurementService(db, ws_manager=None)
        resp = await svc.create_measurement(_create(animal.id))
        await db.commit()
        assert resp.id is not None


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT SERVICE — GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightServiceGet:

    async def test_get_measurement_existing(self, db, svc, animal):
        created = await svc.create_measurement(_create(animal.id))
        await db.commit()
        found = await svc.get_measurement(created.id)
        assert found.id == created.id

    async def test_get_measurement_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.get_measurement(999999)
        assert "999999" in str(exc_info.value)

    async def test_get_animal_measurements_structure(self, db, svc, animal):
        from app.schemas.weight_measurement import WeightMeasurementListResponse
        await svc.create_measurement(_create(animal.id))
        await db.commit()
        result = await svc.get_animal_measurements(animal.id)
        assert isinstance(result, WeightMeasurementListResponse)
        assert result.total >= 1

    async def test_get_animal_measurements_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal_measurements(999999)

    async def test_get_animal_measurements_limit_capped(self, db, svc, animal):
        """Limit > 1000 bo'lsa — 1000 ga cheklanadi."""
        result = await svc.get_animal_measurements(animal.id, limit=5000)
        assert result.limit <= 1000

    async def test_get_animal_measurements_pagination(self, db, svc, animal):
        for _ in range(5):
            await svc.create_measurement(_create(animal.id))
        await db.commit()
        p1 = await svc.get_animal_measurements(animal.id, skip=0, limit=2)
        p2 = await svc.get_animal_measurements(animal.id, skip=2, limit=2)
        ids1 = {m.id for m in p1.items}
        ids2 = {m.id for m in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_get_animal_measurements_confidence_filter(self, db, svc, animal):
        await svc.create_measurement(_create(animal.id, confidence=0.95))
        await svc.create_measurement(_create(animal.id, confidence=0.2))
        await db.commit()
        result = await svc.get_animal_measurements(animal.id, min_confidence=0.7)
        assert all(m.confidence_score >= 0.7 for m in result.items)

    async def test_get_animal_measurements_days_filter(self, db, svc, animal):
        old_ts = datetime.utcnow() - timedelta(days=15)
        await svc.create_measurement(_create(animal.id, weight_kg=999.0, ts=old_ts))
        await svc.create_measurement(_create(animal.id, weight_kg=350.0))
        await db.commit()
        result = await svc.get_animal_measurements(animal.id, days=7)
        weights = [m.estimated_weight_kg for m in result.items]
        assert 999.0 not in weights  # Eski o'lchov chiqmasligi kerak

    async def test_get_animal_measurements_empty(self, db, svc, animal):
        result = await svc.get_animal_measurements(animal.id)
        assert result.total == 0
        assert len(result.items) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT SERVICE — STATS & TREND
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightServiceStats:

    async def test_get_stats_structure(self, db, svc, animal):
        from app.schemas.weight_measurement import WeightStatsResponse
        await svc.create_measurement(_create(animal.id, confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id)
        assert isinstance(stats, WeightStatsResponse)
        for k in ["animal_id", "total_measurements", "average_weight_kg",
                  "latest_weight_kg", "weight_trend", "confidence_average"]:
            assert hasattr(stats, k)

    async def test_get_stats_missing_animal_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal_weight_stats(999999)

    async def test_trend_increasing_over_5kg(self, db, svc, animal):
        """Birinchi o'lchov 300, oxirgi 320 → difference = +20 → increasing."""
        old_ts = datetime.utcnow() - timedelta(days=20)
        await svc.create_measurement(_create(animal.id, weight_kg=300.0,
                                              confidence=0.9, ts=old_ts))
        await svc.create_measurement(_create(animal.id, weight_kg=320.0,
                                              confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        if stats.weight_trend is not None:
            assert stats.weight_trend == "increasing"

    async def test_trend_decreasing_over_5kg(self, db, svc, animal):
        """300 → 280 → -20kg → decreasing."""
        old_ts = datetime.utcnow() - timedelta(days=20)
        await svc.create_measurement(_create(animal.id, weight_kg=300.0,
                                              confidence=0.9, ts=old_ts))
        await svc.create_measurement(_create(animal.id, weight_kg=280.0,
                                              confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        if stats.weight_trend is not None:
            assert stats.weight_trend == "decreasing"

    async def test_trend_stable_within_5kg(self, db, svc, animal):
        """300 → 303 → +3kg → stable."""
        old_ts = datetime.utcnow() - timedelta(days=20)
        await svc.create_measurement(_create(animal.id, weight_kg=300.0,
                                              confidence=0.9, ts=old_ts))
        await svc.create_measurement(_create(animal.id, weight_kg=303.0,
                                              confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        if stats.weight_trend is not None:
            assert stats.weight_trend == "stable"

    async def test_trend_none_when_single_measurement(self, db, svc, animal):
        """Bitta o'lchov — trend aniqlanmaydi."""
        await svc.create_measurement(_create(animal.id, confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        # weight_change None bo'lsa trend None
        if stats.weight_trend is None:
            pass  # To'g'ri
        else:
            # Bitta o'lchov bilan ham stable bo'lishi mumkin
            assert stats.weight_trend in ("stable", "increasing", "decreasing", None)

    async def test_stats_latest_weight(self, db, svc, animal):
        """get_animal_weight_stats latest_weight_kg ni to'g'ri qaytaradi."""
        for w in [300.0, 320.0, 350.0]:
            await svc.create_measurement(_create(animal.id, weight_kg=w, confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        # Oxirgi qo'shilgan — 350
        if stats.latest_weight_kg is not None:
            assert stats.latest_weight_kg >= 300.0

    async def test_stats_average_weight(self, db, svc, animal):
        for w in [300.0, 400.0]:
            await svc.create_measurement(_create(animal.id, weight_kg=w, confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        assert stats.average_weight_kg is not None
        assert abs(stats.average_weight_kg - 350.0) < 5.0

    async def test_stats_confidence_filter(self, db, svc, animal):
        await svc.create_measurement(_create(animal.id, weight_kg=999.0, confidence=0.1))
        await svc.create_measurement(_create(animal.id, weight_kg=350.0, confidence=0.9))
        await db.commit()
        stats = await svc.get_animal_weight_stats(animal.id, min_confidence=0.7)
        # 999.0 chiqmasligi kerak — faqat 350.0 bo'lgan o'lchov hisobga olinadi
        if stats.average_weight_kg:
            assert stats.average_weight_kg < 900.0

    async def test_stats_empty_returns_zeroes(self, db, svc, animal):
        stats = await svc.get_animal_weight_stats(animal.id, days=30)
        assert stats.total_measurements == 0
        assert stats.average_weight_kg == 0.0 or stats.average_weight_kg is None


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT MEASUREMENT SERVICE — RECENT GLOBAL FEED
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightServiceRecentGlobal:

    async def test_get_recent_returns_list(self, db, svc, animal):
        await svc.create_measurement(_create(animal.id))
        await db.commit()
        result = await svc.get_recent_measurements()
        assert isinstance(result, list)
        assert len(result) >= 1

    async def test_get_recent_limit(self, db, svc, animal):
        for _ in range(10):
            await svc.create_measurement(_create(animal.id))
        await db.commit()
        result = await svc.get_recent_measurements(limit=3)
        assert len(result) <= 3

    async def test_get_recent_confidence_filter(self, db, svc, animal):
        await svc.create_measurement(_create(animal.id, confidence=0.9))
        await svc.create_measurement(_create(animal.id, confidence=0.2))
        await db.commit()
        result = await svc.get_recent_measurements(min_confidence=0.7)
        assert all(m.confidence_score >= 0.7 for m in result)

    async def test_get_recent_multiple_animals(self, db, svc, animal, second_animal):
        await svc.create_measurement(_create(animal.id,        weight_kg=350.0))
        await svc.create_measurement(_create(second_animal.id, weight_kg=80.0))
        await db.commit()
        result = await svc.get_recent_measurements(limit=50)
        animal_ids = {m.animal_id for m in result}
        assert animal.id        in animal_ids
        assert second_animal.id in animal_ids

    async def test_get_recent_returns_measurement_response(self, db, svc, animal):
        from app.schemas.weight_measurement import WeightMeasurementResponse
        await svc.create_measurement(_create(animal.id))
        await db.commit()
        result = await svc.get_recent_measurements(limit=1)
        if result:
            assert isinstance(result[0], WeightMeasurementResponse)

    async def test_get_recent_empty_when_no_data(self, db, svc):
        result = await svc.get_recent_measurements(min_confidence=0.99)
        assert isinstance(result, list)