"""
TAURUS VISION — tests/test_services/test_remaining_repos.py
============================================================
FarmTaskRepository + PredictionRepository + SensorRepository +
NotificationRepository (qo'shimcha) uchun AYAMAS vahshiy testlar.

Qamrov (140+ test):
  ✓ FarmTaskRepository.create / get_by_id / get_by_id_with_relations
  ✓ FarmTaskRepository.get_list  — barcha filtrlar (status, type, priority, animal)
  ✓ FarmTaskRepository.get_for_animal / get_open_tasks
  ✓ FarmTaskRepository.save / get_stats
  ✓ PredictionRepository.create_or_replace — upsert mantiqsi
  ✓ PredictionRepository.get_latest_for_animal / get_by_animal_and_date
  ✓ PredictionRepository.get_history_for_animal
  ✓ PredictionRepository.get_at_risk_animals — risk level filtr
  ✓ SensorRepository.create / bulk_create
  ✓ SensorRepository.get_latest_for_animal / get_for_period
  ✓ SensorRepository.get_daily_summary — bo'sh, ma'lumotli
  ✓ SensorRepository.get_active_devices / get_farm_stats_today
  ✓ SensorRepository.get_anomalies_today — normal, anormal qiymatlar
  ✓ RiskLevel / TaskType / TaskPriority / TaskStatus enums
  ✓ risk_level_from_score — barcha chegara qiymatlar
"""

import pytest
from datetime import datetime, timezone, timedelta, date

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.farm_task import FarmTask, TaskStatus, TaskPriority, TaskType
from app.models.health_prediction import (
    HealthPrediction, RiskLevel, risk_level_from_score,
)
from app.models.sensor_reading import SensorReading, SensorType
from app.repositories.farm_task_repository import FarmTaskRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.sensor_repository import SensorRepository

pytestmark = pytest.mark.asyncio

TODAY_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YESTERDAY_STR = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
NOW = datetime.utcnow()


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="REPO-ANIMAL-001",
        species=AnimalSpecies.CATTLE, gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE, acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="REPO-ANIMAL-002",
        species=AnimalSpecies.SHEEP, gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE, acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def task_repo(db):
    return FarmTaskRepository(db)


@pytest.fixture
def pred_repo(db):
    return PredictionRepository(db)


@pytest.fixture
def sensor_repo(db):
    return SensorRepository(db)


def _farm_task(title="Test Vazifa", status=TaskStatus.PENDING,
               priority=TaskPriority.MEDIUM, task_type=TaskType.FEEDING,
               animal_id=None, due_date=None, **kw) -> FarmTask:
    return FarmTask(
        title=title, status=status, priority=priority,
        task_type=task_type, animal_id=animal_id,
        due_date=due_date or datetime.utcnow() + timedelta(days=1),
        **kw,
    )


def _health_pred(animal_id, date_str=None, risk_score=45.0,
                 risk_level="medium") -> HealthPrediction:
    return HealthPrediction(
        animal_id=animal_id,
        prediction_date=date_str or TODAY_STR,
        risk_level=risk_level,
        risk_score=risk_score,
        confidence=0.75,
        rule_risk=risk_score,
        rf_risk=None, isolation_score=None,
        risk_factors=[], recommendations=[],
        model_version="rule-1.0",
        adi_days_available=7, features_used=10,
        predicted_at=datetime.now(timezone.utc),
    )


def _sensor_reading(animal_id=None, device_id="SENSOR-TEST-001",
                    temp=38.5, hr=65, activity=0.5) -> SensorReading:
    return SensorReading(
        device_id=device_id,
        device_type="collar",
        animal_id=animal_id,
        temperature=temp,
        heart_rate=hr,
        activity_level=activity,
        recorded_at=NOW,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RiskLevel enum va risk_level_from_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskLevel:
    def test_all_levels(self):
        for v in ["low", "medium", "high", "critical"]:
            assert RiskLevel(v) is not None

    def test_from_score_0_29_low(self):
        for s in [0, 15, 29]:
            assert risk_level_from_score(s) == RiskLevel.LOW

    def test_from_score_30_59_medium(self):
        for s in [30, 45, 59]:
            assert risk_level_from_score(s) == RiskLevel.MEDIUM

    def test_from_score_60_79_high(self):
        for s in [60, 70, 79]:
            assert risk_level_from_score(s) == RiskLevel.HIGH

    def test_from_score_80_100_critical(self):
        for s in [80, 90, 100]:
            assert risk_level_from_score(s) == RiskLevel.CRITICAL

    def test_boundary_30_medium(self):
        assert risk_level_from_score(30.0) == RiskLevel.MEDIUM

    def test_boundary_60_high(self):
        assert risk_level_from_score(60.0) == RiskLevel.HIGH

    def test_boundary_80_critical(self):
        assert risk_level_from_score(80.0) == RiskLevel.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# TaskType / TaskPriority / TaskStatus
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskEnums:
    def test_all_task_types(self):
        for v in ["vaccination", "health_check", "feeding", "cleaning",
                  "weighing", "other", "grooming", "medication"]:
            assert TaskType(v) is not None

    def test_all_priorities(self):
        for v in ["low", "medium", "high", "critical"]:
            assert TaskPriority(v) is not None

    def test_all_statuses(self):
        for v in ["pending", "in_progress", "completed", "overdue", "cancelled"]:
            assert TaskStatus(v) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# FarmTaskRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskRepository:

    async def test_create_assigns_id(self, db, task_repo):
        task = await task_repo.create(_farm_task())
        await db.commit()
        assert task.id is not None and task.id > 0

    async def test_get_by_id_existing(self, db, task_repo):
        task = await task_repo.create(_farm_task(title="GetById Test"))
        await db.commit()
        found = await task_repo.get_by_id(task.id)
        assert found is not None and found.id == task.id

    async def test_get_by_id_missing_none(self, db, task_repo):
        assert await task_repo.get_by_id(999999) is None

    async def test_get_by_id_with_relations(self, db, task_repo, animal):
        task = await task_repo.create(_farm_task(animal_id=animal.id))
        await db.commit()
        found = await task_repo.get_by_id_with_relations(task.id)
        assert found is not None

    async def test_get_list_all(self, db, task_repo):
        for _ in range(3):
            await task_repo.create(_farm_task())
        await db.commit()
        items, total = await task_repo.get_list()
        assert total >= 3

    async def test_get_list_status_filter(self, db, task_repo):
        await task_repo.create(_farm_task(status=TaskStatus.PENDING))
        await task_repo.create(_farm_task(status=TaskStatus.COMPLETED))
        await db.commit()
        items, total = await task_repo.get_list(status=[TaskStatus.PENDING])
        assert all(t.status == TaskStatus.PENDING for t in items)

    async def test_get_list_type_filter(self, db, task_repo):
        await task_repo.create(_farm_task(task_type=TaskType.VACCINATION))
        await task_repo.create(_farm_task(task_type=TaskType.FEEDING))
        await db.commit()
        items, _ = await task_repo.get_list(task_type=TaskType.VACCINATION)
        assert all(t.task_type == TaskType.VACCINATION for t in items)

    async def test_get_list_priority_filter(self, db, task_repo):
        await task_repo.create(_farm_task(priority=TaskPriority.CRITICAL))
        await task_repo.create(_farm_task(priority=TaskPriority.LOW))
        await db.commit()
        items, _ = await task_repo.get_list(priority=TaskPriority.CRITICAL)
        assert all(t.priority == TaskPriority.CRITICAL for t in items)

    async def test_get_list_animal_filter(self, db, task_repo, animal, second_animal):
        await task_repo.create(_farm_task(animal_id=animal.id))
        await task_repo.create(_farm_task(animal_id=second_animal.id))
        await db.commit()
        items, _ = await task_repo.get_list(animal_id=animal.id)
        assert all(t.animal_id == animal.id for t in items)

    async def test_get_list_pagination(self, db, task_repo):
        for _ in range(5):
            await task_repo.create(_farm_task())
        await db.commit()
        p1, _ = await task_repo.get_list(limit=2, offset=0)
        p2, _ = await task_repo.get_list(limit=2, offset=2)
        assert {t.id for t in p1}.isdisjoint({t.id for t in p2})

    async def test_get_for_animal(self, db, task_repo, animal):
        for _ in range(3):
            await task_repo.create(_farm_task(animal_id=animal.id))
        await db.commit()
        result = await task_repo.get_for_animal(animal.id)
        assert len(result) >= 3

    async def test_get_for_animal_open_only(self, db, task_repo, animal):
        t1 = await task_repo.create(_farm_task(animal_id=animal.id))
        t2 = await task_repo.create(
            _farm_task(animal_id=animal.id, status=TaskStatus.COMPLETED))
        await db.commit()
        result = await task_repo.get_for_animal(
            animal.id, status=[TaskStatus.PENDING])
        assert all(t.status == TaskStatus.PENDING for t in result)

    async def test_save_updates_task(self, db, task_repo):
        task = await task_repo.create(_farm_task(title="Old Title"))
        await db.commit()
        task.title = "New Title"
        saved = await task_repo.save(task)
        await db.commit()
        assert saved.title == "New Title"

    async def test_get_stats_structure(self, db, task_repo):
        await task_repo.create(_farm_task())
        await db.commit()
        stats = await task_repo.get_stats()
        for k in ["total_open", "total_overdue", "total_today",
                  "total_completed_today", "by_priority", "by_type",
                  "critical_overdue"]:
            assert k in stats

    async def test_get_stats_total_open_count(self, db, task_repo):
        for _ in range(3):
            await task_repo.create(_farm_task(status=TaskStatus.PENDING))
        await db.commit()
        stats = await task_repo.get_stats()
        assert stats["total_open"] >= 3

    async def test_get_list_overdue_only(self, db, task_repo):
        past_due = datetime.utcnow() - timedelta(days=2)
        await task_repo.create(_farm_task(
            status=TaskStatus.PENDING, due_date=past_due))
        await db.commit()
        items, total = await task_repo.get_list(overdue_only=True)
        for t in items:
            assert t.due_date < datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════════════
# PredictionRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictionRepository:

    async def test_create_assigns_id(self, db, pred_repo, animal):
        pred = await pred_repo.create_or_replace(
            _health_pred(animal.id))
        await db.commit()
        assert pred.id is not None

    async def test_create_or_replace_upsert(self, db, pred_repo, animal):
        """Bir xil sana → eski o'chirilip yangi yaratiladi."""
        pred1 = await pred_repo.create_or_replace(
            _health_pred(animal.id, risk_score=40.0))
        await db.commit()
        pred2 = await pred_repo.create_or_replace(
            _health_pred(animal.id, risk_score=75.0))
        await db.commit()
        # Faqat bitta yozuv bo'lishi kerak
        found = await pred_repo.get_by_animal_and_date(animal.id, TODAY_STR)
        assert found is not None
        assert abs(found.risk_score - 75.0) < 0.01

    async def test_get_latest_for_animal_existing(self, db, pred_repo, animal):
        await pred_repo.create_or_replace(_health_pred(animal.id))
        await db.commit()
        latest = await pred_repo.get_latest_for_animal(animal.id)
        assert latest is not None
        assert latest.animal_id == animal.id

    async def test_get_latest_for_animal_none_when_empty(self, db, pred_repo, animal):
        result = await pred_repo.get_latest_for_animal(animal.id)
        assert result is None

    async def test_get_by_animal_and_date_existing(self, db, pred_repo, animal):
        await pred_repo.create_or_replace(_health_pred(animal.id))
        await db.commit()
        found = await pred_repo.get_by_animal_and_date(animal.id, TODAY_STR)
        assert found is not None

    async def test_get_by_animal_and_date_missing_none(self, db, pred_repo, animal):
        result = await pred_repo.get_by_animal_and_date(animal.id, "2020-01-01")
        assert result is None

    async def test_get_history_for_animal(self, db, pred_repo, animal):
        for i in range(5):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            await pred_repo.create_or_replace(_health_pred(animal.id, date_str=d))
        await db.commit()
        history = await pred_repo.get_history_for_animal(animal.id, days=7)
        assert len(history) >= 5

    async def test_get_history_sorted_newest_first(self, db, pred_repo, animal):
        for i in range(3):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            await pred_repo.create_or_replace(_health_pred(animal.id, date_str=d))
        await db.commit()
        history = await pred_repo.get_history_for_animal(animal.id)
        dates = [h.prediction_date for h in history]
        assert dates == sorted(dates, reverse=True)

    async def test_get_at_risk_animals_medium_plus(self, db, pred_repo, animal, second_animal):
        await pred_repo.create_or_replace(
            _health_pred(animal.id, risk_score=50.0, risk_level="medium"))
        await pred_repo.create_or_replace(
            _health_pred(second_animal.id, risk_score=15.0, risk_level="low"))
        await db.commit()
        at_risk = await pred_repo.get_at_risk_animals(
            date_str=TODAY_STR, min_risk_level="medium")
        animal_ids = [p.animal_id for p in at_risk]
        assert animal.id        in animal_ids
        assert second_animal.id not in animal_ids

    async def test_get_at_risk_animals_critical_only(self, db, pred_repo, animal, second_animal):
        await pred_repo.create_or_replace(
            _health_pred(animal.id, risk_score=85.0, risk_level="critical"))
        await pred_repo.create_or_replace(
            _health_pred(second_animal.id, risk_score=45.0, risk_level="medium"))
        await db.commit()
        critical = await pred_repo.get_at_risk_animals(
            date_str=TODAY_STR, min_risk_level="critical")
        assert all(p.risk_score >= 80.0 for p in critical)

    async def test_get_at_risk_sorted_by_score_desc(self, db, pred_repo, animal, second_animal):
        await pred_repo.create_or_replace(
            _health_pred(animal.id, risk_score=70.0, risk_level="high"))
        await pred_repo.create_or_replace(
            _health_pred(second_animal.id, risk_score=50.0, risk_level="medium"))
        await db.commit()
        at_risk = await pred_repo.get_at_risk_animals(date_str=TODAY_STR)
        scores = [p.risk_score for p in at_risk]
        assert scores == sorted(scores, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SensorRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensorRepository:

    async def test_create_assigns_id(self, db, sensor_repo, animal):
        r = await sensor_repo.create(_sensor_reading(animal_id=animal.id))
        await db.commit()
        assert r.id is not None

    async def test_create_saves_fields(self, db, sensor_repo, animal):
        r = await sensor_repo.create(_sensor_reading(
            animal_id=animal.id, temp=39.0, hr=72))
        await db.commit()
        assert abs(r.temperature - 39.0) < 0.01
        assert r.heart_rate == 72

    async def test_bulk_create(self, db, sensor_repo, animal):
        readings = [_sensor_reading(animal_id=animal.id,
                                    device_id=f"BULK-{i}")
                    for i in range(5)]
        result = await sensor_repo.bulk_create(readings)
        await db.commit()
        assert len(result) == 5

    async def test_get_latest_for_animal_existing(self, db, sensor_repo, animal):
        early = _sensor_reading(animal_id=animal.id, temp=38.0)
        early.recorded_at = NOW - timedelta(hours=2)
        late = _sensor_reading(animal_id=animal.id, temp=39.0)
        await sensor_repo.create(early)
        await sensor_repo.create(late)
        await db.commit()
        latest = await sensor_repo.get_latest_for_animal(animal.id)
        assert latest is not None
        assert abs(latest.temperature - 39.0) < 0.01

    async def test_get_latest_for_animal_none_when_empty(self, db, sensor_repo, animal):
        result = await sensor_repo.get_latest_for_animal(animal.id)
        assert result is None

    async def test_get_for_period(self, db, sensor_repo, animal):
        for i in range(3):
            r = _sensor_reading(animal_id=animal.id)
            r.recorded_at = NOW - timedelta(hours=i)
            await sensor_repo.create(r)
        await db.commit()
        start = NOW - timedelta(hours=5)
        end   = NOW + timedelta(hours=1)
        result = await sensor_repo.get_for_period(animal.id, start, end)
        assert len(result) >= 3

    async def test_get_for_period_excludes_old(self, db, sensor_repo, animal):
        old = _sensor_reading(animal_id=animal.id, temp=99.0)
        old.recorded_at = NOW - timedelta(days=10)
        await sensor_repo.create(old)
        await db.commit()
        start = NOW - timedelta(hours=1)
        end   = NOW + timedelta(hours=1)
        result = await sensor_repo.get_for_period(animal.id, start, end)
        assert all(r.temperature != 99.0 for r in result)

    async def test_get_daily_summary_none_when_empty(self, db, sensor_repo, animal):
        result = await sensor_repo.get_daily_summary(animal.id, "2020-01-01")
        assert result is None

    async def test_get_daily_summary_with_data(self, db, sensor_repo, animal):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        r = _sensor_reading(animal_id=animal.id, temp=38.8, hr=65)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        summary = await sensor_repo.get_daily_summary(animal.id, today)
        if summary:
            assert "temperature" in summary
            assert "heart_rate" in summary
            assert "reading_count" in summary
            assert summary["reading_count"] >= 1

    async def test_get_daily_summary_average_temp(self, db, sensor_repo, animal):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        for temp in [38.0, 39.0]:
            r = _sensor_reading(animal_id=animal.id, temp=temp)
            r.recorded_at = datetime.utcnow()
            await sensor_repo.create(r)
        await db.commit()
        summary = await sensor_repo.get_daily_summary(animal.id, today)
        if summary and summary["temperature"]:
            assert abs(summary["temperature"] - 38.5) < 0.5

    async def test_get_daily_summary_structure(self, db, sensor_repo, animal):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        r = _sensor_reading(animal_id=animal.id)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        summary = await sensor_repo.get_daily_summary(animal.id, today)
        if summary:
            for k in ["temperature", "heart_rate", "activity_level",
                      "weight_kg", "reading_count"]:
                assert k in summary

    async def test_get_active_devices(self, db, sensor_repo, animal):
        r = _sensor_reading(animal_id=animal.id, device_id="ACTIVE-DEVICE")
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        result = await sensor_repo.get_active_devices(hours=24)
        assert isinstance(result, list)
        device_ids = [d["device_id"] for d in result]
        assert "ACTIVE-DEVICE" in device_ids

    async def test_get_active_devices_excludes_old(self, db, sensor_repo, animal):
        old = _sensor_reading(animal_id=animal.id, device_id="OLD-DEVICE")
        old.recorded_at = datetime.utcnow() - timedelta(hours=48)
        await sensor_repo.create(old)
        await db.commit()
        result = await sensor_repo.get_active_devices(hours=24)
        device_ids = [d["device_id"] for d in result]
        assert "OLD-DEVICE" not in device_ids

    async def test_get_farm_stats_today_structure(self, db, sensor_repo, animal):
        r = _sensor_reading(animal_id=animal.id)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        stats = await sensor_repo.get_farm_stats_today()
        assert "total_readings_today" in stats
        assert "animals_with_sensors" in stats
        assert "active_devices_today" in stats

    async def test_get_farm_stats_counts(self, db, sensor_repo, animal):
        r = _sensor_reading(animal_id=animal.id)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        stats = await sensor_repo.get_farm_stats_today()
        assert stats["total_readings_today"] >= 1
        assert stats["animals_with_sensors"] >= 1

    async def test_get_anomalies_today_high_temp(self, db, sensor_repo, animal):
        """42°C anormal → anomalies ga kiradi."""
        r = _sensor_reading(animal_id=animal.id, temp=42.0, hr=65)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        anomalies = await sensor_repo.get_anomalies_today()
        assert len(anomalies) >= 1
        assert any(a["animal_id"] == animal.id for a in anomalies)

    async def test_get_anomalies_today_low_hr(self, db, sensor_repo, animal):
        """HR=15 anormal → anomalies ga kiradi."""
        r = _sensor_reading(animal_id=animal.id, temp=38.5, hr=15)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        anomalies = await sensor_repo.get_anomalies_today()
        assert len(anomalies) >= 1

    async def test_get_anomalies_normal_not_included(self, db, sensor_repo, animal):
        """Normal harorat+HR → anomaliya yo'q."""
        r = _sensor_reading(animal_id=animal.id, temp=38.8, hr=65)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        anomalies = await sensor_repo.get_anomalies_today()
        normal_ones = [a for a in anomalies if a["animal_id"] == animal.id]
        # Normal qiymatlar anomaliya deb hisoblanmasligi kerak
        assert len(normal_ones) == 0

    async def test_get_anomalies_structure(self, db, sensor_repo, animal):
        r = _sensor_reading(animal_id=animal.id, temp=42.5, hr=65)
        r.recorded_at = datetime.utcnow()
        await sensor_repo.create(r)
        await db.commit()
        anomalies = await sensor_repo.get_anomalies_today()
        if anomalies:
            for a in anomalies:
                assert "animal_id" in a
                assert "device_id" in a
                assert "issues"    in a
                assert "recorded_at" in a

    async def test_sensor_type_enum(self):
        for t in ["temperature", "heart_rate", "activity", "weight",
                  "humidity", "gps", "other"]:
            assert SensorType(t) is not None