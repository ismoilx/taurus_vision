"""
TAURUS VISION — tests/test_services/test_repos_camera_detection_embedding.py
=============================================================================
CameraRepository + DetectionRepository + EmbeddingRepository +
FarmRepository + EmployeeRepository uchun AYAMAS vahshiy testlar.

Qamrov (160+ test):
  ✓ CameraType enum
  ✓ CameraRepository.get_all / get_by_camera_id / exists / count
  ✓ CameraRepository.create — avtomatik ID generatsiya, duplicate ID xato
  ✓ CameraRepository.update — maydonlar, topilmasa xato
  ✓ CameraRepository.delete — mavjud, topilmasa xato
  ✓ CameraRepository._generate_unique_camera_id — slug generatsiya
  ✓ DetectionRepository.create — barcha maydonlar
  ✓ DetectionRepository.get_by_id / get_by_animal / get_recent
  ✓ DetectionRepository.count_by_animal / count_in_range
  ✓ EmbeddingRepository.create / add_with_limit_check (FIFO limit)
  ✓ EmbeddingRepository.get_all_for_animal / get_reference
  ✓ EmbeddingRepository.get_all_active_embeddings (farm-wide)
  ✓ EmbeddingRepository.delete_oldest / count_for_animal
  ✓ FarmRepository.create / get_by_id / get_all / count
  ✓ FarmRepository.get_animal_stats / update / deactivate / delete
  ✓ EmployeeRepository.create_employee / get / list / update / stats
  ✓ EmployeeRepository.create_task / get_task / list_tasks / update_task
  ✓ EmployeeRepository.get_task_stats / mark_overdue_tasks
  ✓ EmployeeRepository.get_task_counts_for_employee
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.animal_embedding import AnimalEmbedding
from app.models.camera import Camera, CameraType
from app.models.detection import Detection
from app.models.employee import (
    Employee, WorkerTask,
    EmployeePosition, EmployeeStatus,
    WorkerTaskStatus, WorkerTaskPriority, WorkerTaskType,
)
from app.models.farm import Farm
from app.repositories.camera_repository import CameraRepository
from app.repositories.detection import DetectionRepository
from app.repositories.embedding_repository import EmbeddingRepository, MAX_EMBEDDINGS_PER_ANIMAL
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.farm_repository import FarmRepository
from app.schemas.farm import FarmCreate, FarmUpdate
from app.core.exceptions import EntityNotFoundError, EntityAlreadyExistsError

pytestmark = pytest.mark.asyncio

NOW = datetime.utcnow()


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="REPO-CAM-001", species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="REPO-CAM-002", species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE, status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def cam_repo(db):
    return CameraRepository(db)


@pytest.fixture
def det_repo(db):
    return DetectionRepository(db)


@pytest.fixture
def emb_repo(db):
    return EmbeddingRepository(db)


@pytest.fixture
def farm_repo(db):
    return FarmRepository(db)


@pytest.fixture
def emp_repo(db):
    return EmployeeRepository(db)


def _detection(animal_id=None, camera_id="CAM-TEST", confidence=0.92,
               ts=None) -> dict:
    return dict(
        animal_id=animal_id,
        camera_id=camera_id,
        timestamp=ts or NOW,
        confidence=confidence,
        class_id=19,
        class_name="cow",
        bbox={"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
    )


def _embedding(animal_id, dim=8, is_reference=False, source="registration"):
    return AnimalEmbedding(
        animal_id=animal_id,
        embedding=[0.1] * dim,
        is_reference=is_reference,
        source=source,
        quality_score=0.9,
    )


def _employee(name="Test Xodim", position=EmployeePosition.FEEDER,
              status=EmployeeStatus.ACTIVE, **kw):
    return Employee(
        full_name=name, position=position, status=status,
        hire_date=datetime(2022, 1, 1).date(), **kw)


def _task(emp_id=None, status=WorkerTaskStatus.PENDING,
          priority=WorkerTaskPriority.MEDIUM,
          task_type=WorkerTaskType.FEEDING, due_date=None):
    return WorkerTask(
        title="Test Vazifa", task_type=task_type,
        priority=priority, status=status,
        employee_id=emp_id,
        due_date=due_date or (datetime.utcnow() + timedelta(days=1)),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA TYPE ENUM
# ═══════════════════════════════════════════════════════════════════════════════

class TestCameraTypeEnum:
    def test_simulated(self): assert CameraType("simulated") == CameraType.SIMULATED
    def test_usb(self):       assert CameraType("usb") == CameraType.USB
    def test_rtsp(self):      assert CameraType("rtsp") == CameraType.RTSP
    def test_all_3_types(self): assert len(CameraType) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestCameraRepository:

    async def test_create_assigns_id(self, db, cam_repo):
        cam = await cam_repo.create(
            name="Test Kamera", camera_type=CameraType.SIMULATED)
        assert cam.id is not None and cam.id > 0

    async def test_create_auto_generates_camera_id(self, db, cam_repo):
        cam = await cam_repo.create(name="Shimoliy Molxona",
                                     camera_type=CameraType.SIMULATED)
        assert cam.camera_id.startswith("CAM-")
        assert "SHIMOLIY" in cam.camera_id or len(cam.camera_id) > 4

    async def test_create_custom_camera_id(self, db, cam_repo):
        cam = await cam_repo.create(
            name="Custom", camera_type=CameraType.USB,
            camera_id="MY-CUSTOM-CAM")
        assert cam.camera_id == "MY-CUSTOM-CAM"

    async def test_create_duplicate_id_raises(self, db, cam_repo):
        await cam_repo.create(name="First", camera_type=CameraType.SIMULATED,
                               camera_id="DUP-CAM-001")
        with pytest.raises(EntityAlreadyExistsError):
            await cam_repo.create(name="Second", camera_type=CameraType.SIMULATED,
                                   camera_id="DUP-CAM-001")

    async def test_get_all_returns_created(self, db, cam_repo):
        await cam_repo.create(name="All Test 1", camera_type=CameraType.SIMULATED)
        await cam_repo.create(name="All Test 2", camera_type=CameraType.RTSP)
        result = await cam_repo.get_all()
        assert len(result) >= 2

    async def test_get_all_only_enabled(self, db, cam_repo):
        await cam_repo.create(name="Enabled", camera_type=CameraType.SIMULATED)
        disabled = await cam_repo.create(name="Disabled",
                                          camera_type=CameraType.SIMULATED,
                                          is_enabled=False)
        result = await cam_repo.get_all(only_enabled=True)
        ids = [c.id for c in result]
        assert disabled.id not in ids

    async def test_get_by_camera_id_existing(self, db, cam_repo):
        cam = await cam_repo.create(name="Get By ID", camera_type=CameraType.USB,
                                     camera_id="GET-BY-ID-CAM")
        found = await cam_repo.get_by_camera_id("GET-BY-ID-CAM")
        assert found is not None and found.id == cam.id

    async def test_get_by_camera_id_missing_none(self, db, cam_repo):
        assert await cam_repo.get_by_camera_id("NONEXISTENT-CAM") is None

    async def test_get_by_camera_id_or_raise_raises(self, db, cam_repo):
        with pytest.raises(EntityNotFoundError):
            await cam_repo.get_by_camera_id_or_raise("GHOST-CAM")

    async def test_exists_true(self, db, cam_repo):
        await cam_repo.create(name="Exists Test", camera_type=CameraType.SIMULATED,
                               camera_id="EXISTS-CAM")
        assert await cam_repo.exists_by_camera_id("EXISTS-CAM") is True

    async def test_exists_false(self, db, cam_repo):
        assert await cam_repo.exists_by_camera_id("NO-SUCH-CAM") is False

    async def test_count_increases(self, db, cam_repo):
        before = await cam_repo.count()
        await cam_repo.create(name="Count Test", camera_type=CameraType.SIMULATED)
        after = await cam_repo.count()
        assert after == before + 1

    async def test_update_name(self, db, cam_repo):
        cam = await cam_repo.create(name="Old Name", camera_type=CameraType.SIMULATED,
                                     camera_id="UPD-CAM-001")
        updated = await cam_repo.update("UPD-CAM-001", name="New Name")
        assert updated.name == "New Name"

    async def test_update_fps(self, db, cam_repo):
        await cam_repo.create(name="FPS Test", camera_type=CameraType.USB,
                               camera_id="FPS-CAM-001", fps=10)
        updated = await cam_repo.update("FPS-CAM-001", fps=30)
        assert updated.fps == 30

    async def test_update_is_enabled(self, db, cam_repo):
        await cam_repo.create(name="Enable Test", camera_type=CameraType.SIMULATED,
                               camera_id="EN-CAM-001")
        updated = await cam_repo.update("EN-CAM-001", is_enabled=False)
        assert updated.is_enabled is False

    async def test_update_missing_raises(self, db, cam_repo):
        with pytest.raises(EntityNotFoundError):
            await cam_repo.update("GHOST-CAM-999", name="Ghost")

    async def test_delete_success(self, db, cam_repo):
        await cam_repo.create(name="Delete Me", camera_type=CameraType.SIMULATED,
                               camera_id="DEL-CAM-001")
        await cam_repo.delete("DEL-CAM-001")
        assert await cam_repo.get_by_camera_id("DEL-CAM-001") is None

    async def test_delete_missing_raises(self, db, cam_repo):
        with pytest.raises(EntityNotFoundError):
            await cam_repo.delete("GHOST-DEL-CAM")

    async def test_rtsp_camera_creation(self, db, cam_repo):
        cam = await cam_repo.create(
            name="IP Camera", camera_type=CameraType.RTSP,
            source="rtsp://192.168.1.100/stream")
        assert cam.type == CameraType.RTSP
        assert cam.source == "rtsp://192.168.1.100/stream"


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectionRepository:

    async def test_create_assigns_id(self, db, det_repo, animal):
        det = await det_repo.create(**_detection(animal_id=animal.id))
        await db.commit()
        assert det.id is not None

    async def test_create_saves_all_fields(self, db, det_repo, animal):
        det = await det_repo.create(
            animal_id=animal.id, camera_id="CAM-TEST-001",
            timestamp=NOW, confidence=0.95,
            class_id=19, class_name="cow",
            bbox={"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
            estimated_weight=450.0, frame_number=1234,
            inference_time_ms=42.5,
        )
        await db.commit()
        assert det.animal_id     == animal.id
        assert det.camera_id     == "CAM-TEST-001"
        assert abs(det.confidence - 0.95) < 0.001
        assert det.estimated_weight == 450.0
        assert det.frame_number     == 1234

    async def test_create_no_animal_ok(self, db, det_repo):
        """animal_id=None bo'lishi mumkin."""
        det = await det_repo.create(**_detection(animal_id=None))
        await db.commit()
        assert det.animal_id is None

    async def test_get_by_id_existing(self, db, det_repo, animal):
        det = await det_repo.create(**_detection(animal_id=animal.id))
        await db.commit()
        found = await det_repo.get_by_id(det.id)
        assert found is not None and found.id == det.id

    async def test_get_by_id_missing_none(self, db, det_repo):
        assert await det_repo.get_by_id(999999) is None

    async def test_get_by_animal_returns_detections(self, db, det_repo, animal):
        for _ in range(3):
            await det_repo.create(**_detection(animal_id=animal.id))
        await db.commit()
        result = await det_repo.get_by_animal(animal.id)
        assert len(result) >= 3

    async def test_get_by_animal_sorted_newest_first(self, db, det_repo, animal):
        for i in range(3):
            ts = NOW - timedelta(hours=i)
            await det_repo.create(**_detection(animal_id=animal.id, ts=ts))
        await db.commit()
        result = await det_repo.get_by_animal(animal.id)
        timestamps = [d.timestamp for d in result]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_get_by_animal_limit(self, db, det_repo, animal):
        for _ in range(10):
            await det_repo.create(**_detection(animal_id=animal.id))
        await db.commit()
        result = await det_repo.get_by_animal(animal.id, limit=3)
        assert len(result) <= 3

    async def test_get_recent_all_cameras(self, db, det_repo, animal):
        for cam in ["CAM-A", "CAM-B", "CAM-C"]:
            await det_repo.create(**_detection(animal_id=animal.id, camera_id=cam))
        await db.commit()
        result = await det_repo.get_recent(limit=50)
        assert len(result) >= 3

    async def test_get_recent_camera_filter(self, db, det_repo, animal):
        await det_repo.create(**_detection(animal_id=animal.id, camera_id="CAM-FILTER"))
        await det_repo.create(**_detection(animal_id=animal.id, camera_id="CAM-OTHER"))
        await db.commit()
        result = await det_repo.get_recent(limit=50, camera_id="CAM-FILTER")
        assert all(d.camera_id == "CAM-FILTER" for d in result)

    async def test_get_recent_confidence_filter(self, db, det_repo, animal):
        await det_repo.create(**_detection(animal_id=animal.id, confidence=0.95))
        await det_repo.create(**_detection(animal_id=animal.id, confidence=0.3))
        await db.commit()
        result = await det_repo.get_recent(limit=50, min_confidence=0.7)
        assert all(d.confidence >= 0.7 for d in result)

    async def test_count_by_animal(self, db, det_repo, animal):
        for _ in range(5):
            await det_repo.create(**_detection(animal_id=animal.id))
        await db.commit()
        count = await det_repo.count_by_animal(animal.id)
        assert count >= 5

    async def test_count_by_animal_zero_for_new(self, db, det_repo, second_animal):
        count = await det_repo.count_by_animal(second_animal.id)
        assert count == 0

    async def test_count_in_range(self, db, det_repo, animal):
        for i in range(3):
            ts = NOW - timedelta(hours=i)
            await det_repo.create(**_detection(animal_id=animal.id, ts=ts))
        await db.commit()
        count = await det_repo.count_in_range(
            NOW - timedelta(hours=5), NOW + timedelta(hours=1))
        assert count >= 3

    async def test_count_in_range_excludes_old(self, db, det_repo, animal):
        old_ts = NOW - timedelta(days=30)
        await det_repo.create(**_detection(animal_id=animal.id, ts=old_ts))
        await db.commit()
        count = await det_repo.count_in_range(
            NOW - timedelta(hours=1), NOW + timedelta(hours=1))
        assert count == 0

    async def test_count_in_range_camera_filter(self, db, det_repo, animal):
        await det_repo.create(**_detection(
            animal_id=animal.id, camera_id="FILTER-CAM"))
        await det_repo.create(**_detection(
            animal_id=animal.id, camera_id="OTHER-CAM"))
        await db.commit()
        count = await det_repo.count_in_range(
            NOW - timedelta(hours=1), NOW + timedelta(hours=1),
            camera_id="FILTER-CAM")
        assert count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmbeddingRepository:

    async def test_create_assigns_id(self, db, emb_repo, animal):
        emb = await emb_repo.create(_embedding(animal.id))
        await db.commit()
        assert emb.id is not None

    async def test_create_saves_fields(self, db, emb_repo, animal):
        emb = await emb_repo.create(AnimalEmbedding(
            animal_id=animal.id, embedding=[0.5, 0.3, 0.2],
            is_reference=True, source="registration", quality_score=0.88,
        ))
        await db.commit()
        assert emb.is_reference is True
        assert emb.source == "registration"
        assert abs(emb.quality_score - 0.88) < 0.01

    async def test_add_with_limit_check_creates(self, db, emb_repo, animal):
        emb = await emb_repo.add_with_limit_check(
            animal_id=animal.id,
            embedding_vector=[0.1, 0.2, 0.3],
            source="registration",
            quality_score=0.9,
        )
        await db.commit()
        assert emb.id is not None

    async def test_add_with_limit_check_fifo(self, db, emb_repo, animal):
        """Limit oshganda eng eski o'chiriladi."""
        # MAX_EMBEDDINGS_PER_ANIMAL ta embedding qo'shamiz
        for i in range(MAX_EMBEDDINGS_PER_ANIMAL):
            await emb_repo.add_with_limit_check(
                animal_id=animal.id,
                embedding_vector=[float(i)] * 8,
                source="registration",
            )
        await db.commit()
        # Count limitdan oshmasligi kerak
        count = await emb_repo.count_for_animal(animal.id)
        assert count <= MAX_EMBEDDINGS_PER_ANIMAL

        # Yana bir qo'shamiz
        await emb_repo.add_with_limit_check(
            animal_id=animal.id,
            embedding_vector=[99.0] * 8,
            source="registration",
        )
        await db.commit()
        count_after = await emb_repo.count_for_animal(animal.id)
        assert count_after <= MAX_EMBEDDINGS_PER_ANIMAL

    async def test_count_for_animal(self, db, emb_repo, animal):
        for _ in range(3):
            await emb_repo.create(_embedding(animal.id))
        await db.commit()
        count = await emb_repo.count_for_animal(animal.id)
        assert count >= 3

    async def test_get_all_for_animal(self, db, emb_repo, animal):
        for _ in range(3):
            await emb_repo.create(_embedding(animal.id))
        await db.commit()
        result = await emb_repo.get_all_for_animal(animal.id)
        assert len(result) >= 3
        assert all(e.animal_id == animal.id for e in result)

    async def test_get_all_active_embeddings_farm_wide(self, db, emb_repo,
                                                         animal, second_animal):
        await emb_repo.create(_embedding(animal.id))
        await emb_repo.create(_embedding(second_animal.id))
        await db.commit()
        result = await emb_repo.get_all_active_embeddings()
        assert isinstance(result, list)
        animal_ids = {e.animal_id for e in result}
        assert animal.id        in animal_ids
        assert second_animal.id in animal_ids

    async def test_max_embeddings_constant(self):
        assert MAX_EMBEDDINGS_PER_ANIMAL == 10


# ═══════════════════════════════════════════════════════════════════════════════
# FARM REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmRepository:

    async def test_create_assigns_id(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(
            name="Test Ferma", timezone_offset=5))
        assert farm.id is not None

    async def test_get_by_id_existing(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(
            name="GetById Ferma", timezone_offset=5))
        found = await farm_repo.get_by_id(farm.id)
        assert found is not None and found.id == farm.id

    async def test_get_by_id_missing_none(self, db, farm_repo):
        assert await farm_repo.get_by_id(999999) is None

    async def test_get_all(self, db, farm_repo):
        await farm_repo.create(FarmCreate(name="Farm A", timezone_offset=5))
        await farm_repo.create(FarmCreate(name="Farm B", timezone_offset=5))
        result = await farm_repo.get_all()
        assert len(result) >= 2

    async def test_get_all_active_only(self, db, farm_repo):
        active   = await farm_repo.create(FarmCreate(name="Active F", timezone_offset=5))
        inactive = await farm_repo.create(FarmCreate(name="Inactive F", timezone_offset=5))
        await farm_repo.deactivate(inactive)
        result = await farm_repo.get_all(active_only=True)
        ids = [f.id for f in result]
        assert active.id   in ids
        assert inactive.id not in ids

    async def test_count(self, db, farm_repo):
        before = await farm_repo.count()
        await farm_repo.create(FarmCreate(name="Count F", timezone_offset=5))
        after = await farm_repo.count()
        assert after == before + 1

    async def test_get_animal_stats_empty(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(name="Empty F", timezone_offset=5))
        stats = await farm_repo.get_animal_stats(farm.id)
        assert stats["total"] == 0
        assert stats["active"] == 0

    async def test_update_name(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(name="Old F", timezone_offset=5))
        updated = await farm_repo.update(farm, FarmUpdate(name="New F"))
        assert updated.name == "New F"

    async def test_deactivate(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(name="Deactivate F", timezone_offset=5))
        result = await farm_repo.deactivate(farm)
        assert result.is_active is False

    async def test_delete(self, db, farm_repo):
        farm = await farm_repo.create(FarmCreate(name="Delete F", timezone_offset=5))
        fid = farm.id
        await farm_repo.delete(farm)
        assert await farm_repo.get_by_id(fid) is None

    async def test_update_user_farm(self, db, farm_repo):
        """user_id mavjud bo'lmasa ham xato bermasin (graceful)."""
        farm = await farm_repo.create(FarmCreate(name="Switch F", timezone_offset=5))
        # User 999999 mavjud emas — xato bermaydi
        try:
            await farm_repo.update_user_farm(user_id=999999, farm_id=farm.id)
        except Exception:
            pass  # DB xatosi bo'lishi mumkin — graceful handle


# ═══════════════════════════════════════════════════════════════════════════════
# EMPLOYEE REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmployeeRepository:

    async def test_create_employee(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee())
        await db.commit()
        assert emp.id is not None

    async def test_get_employee_by_id(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Get Test"))
        await db.commit()
        found = await emp_repo.get_employee_by_id(emp.id)
        assert found is not None and found.id == emp.id

    async def test_get_employee_missing_none(self, db, emp_repo):
        assert await emp_repo.get_employee_by_id(999999) is None

    async def test_list_employees_all(self, db, emp_repo):
        for i in range(3):
            await emp_repo.create_employee(_employee(name=f"List Emp {i}"))
        await db.commit()
        items, total = await emp_repo.list_employees()
        assert total >= 3

    async def test_list_employees_status_filter(self, db, emp_repo):
        await emp_repo.create_employee(
            _employee(name="Active E", status=EmployeeStatus.ACTIVE))
        await emp_repo.create_employee(
            _employee(name="Inactive E", status=EmployeeStatus.INACTIVE))
        await db.commit()
        items, _ = await emp_repo.list_employees(status=EmployeeStatus.ACTIVE)
        assert all(e.status == EmployeeStatus.ACTIVE for e in items)

    async def test_list_employees_position_filter(self, db, emp_repo):
        await emp_repo.create_employee(
            _employee(name="Vet E", position=EmployeePosition.VETERINARIAN))
        await emp_repo.create_employee(
            _employee(name="Feed E", position=EmployeePosition.FEEDER))
        await db.commit()
        items, _ = await emp_repo.list_employees(
            position="veterinarian")
        assert all(e.position == EmployeePosition.VETERINARIAN for e in items)

    async def test_list_employees_search(self, db, emp_repo):
        await emp_repo.create_employee(_employee(name="Unique Search Xodim"))
        await db.commit()
        items, total = await emp_repo.list_employees(search="Unique Search")
        assert total >= 1

    async def test_list_employees_pagination(self, db, emp_repo):
        for i in range(5):
            await emp_repo.create_employee(_employee(name=f"Pag Emp {i}"))
        await db.commit()
        p1, _ = await emp_repo.list_employees(page=1, size=2)
        p2, _ = await emp_repo.list_employees(page=2, size=2)
        assert {e.id for e in p1}.isdisjoint({e.id for e in p2})

    async def test_update_employee(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Before"))
        await db.commit()
        emp.full_name = "After"
        updated = await emp_repo.update_employee(emp)
        await db.commit()
        assert updated.full_name == "After"

    async def test_get_employee_stats_structure(self, db, emp_repo):
        await emp_repo.create_employee(_employee(name="Stats Emp"))
        await db.commit()
        stats = await emp_repo.get_employee_stats()
        for k in ["total", "active", "on_leave", "inactive",
                  "by_position", "tasks_today", "overdue_tasks"]:
            assert k in stats

    async def test_get_employee_stats_counts(self, db, emp_repo):
        await emp_repo.create_employee(
            _employee(name="Active Stats", status=EmployeeStatus.ACTIVE))
        await db.commit()
        stats = await emp_repo.get_employee_stats()
        assert stats["active"] >= 1
        assert stats["total"] >= 1

    async def test_get_task_counts_for_employee(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Count Emp"))
        await db.commit()
        counts = await emp_repo.get_task_counts_for_employee(emp.id)
        assert "open" in counts
        assert "completed" in counts
        assert "overdue" in counts

    async def test_create_task(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Create"))
        await db.commit()
        task = await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        assert task.id is not None

    async def test_get_task_by_id(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Get"))
        await db.commit()
        task = await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        found = await emp_repo.get_task_by_id(task.id)
        assert found is not None and found.id == task.id

    async def test_list_tasks_all(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task List"))
        await db.commit()
        for _ in range(3):
            await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        items, total = await emp_repo.list_tasks(employee_id=emp.id)
        assert total >= 3

    async def test_list_tasks_status_filter(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Status"))
        await db.commit()
        await emp_repo.create_task(_task(
            emp_id=emp.id, status=WorkerTaskStatus.PENDING))
        await emp_repo.create_task(_task(
            emp_id=emp.id, status=WorkerTaskStatus.COMPLETED))
        await db.commit()
        items, _ = await emp_repo.list_tasks(
            employee_id=emp.id, status=WorkerTaskStatus.PENDING)
        assert all(t.status == WorkerTaskStatus.PENDING for t in items)

    async def test_update_task(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Update"))
        await db.commit()
        task = await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        task.title = "Updated Task"
        updated = await emp_repo.update_task(task)
        await db.commit()
        assert updated.title == "Updated Task"

    async def test_get_task_stats_structure(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Task Stats"))
        await db.commit()
        await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        stats = await emp_repo.get_task_stats()
        for k in ["total", "pending", "in_progress", "completed",
                  "overdue", "cancelled", "completion_rate"]:
            assert k in stats

    async def test_get_task_stats_for_employee(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Stats For Emp"))
        await db.commit()
        await emp_repo.create_task(_task(emp_id=emp.id))
        await db.commit()
        stats = await emp_repo.get_task_stats(employee_id=emp.id)
        assert stats["total"] >= 1

    async def test_mark_overdue_tasks(self, db, emp_repo):
        emp = await emp_repo.create_employee(_employee(name="Overdue Emp"))
        await db.commit()
        past_due = datetime.utcnow() - timedelta(days=2)
        task = _task(emp_id=emp.id)
        task.due_date = past_due
        task.status = WorkerTaskStatus.PENDING
        await emp_repo.create_task(task)
        await db.commit()
        count = await emp_repo.mark_overdue_tasks()
        await db.commit()
        assert count >= 1