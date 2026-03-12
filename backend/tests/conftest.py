"""
Global pytest fixtures — Taurus Vision

Barcha testlar uchun umumiy fixture lar:
  - In-memory SQLite DB (har test uchun yangi)
  - FastAPI TestClient (sinxron)
  - AsyncClient (asinxron API testlar uchun)
  - Mock jonivor, detection, o'lchov yaratuvchilar
"""

import pytest
import asyncio
import numpy as np
from typing import AsyncGenerator
from datetime import datetime, timezone
from fastapi import Request

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport


# ── DB Fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Session-wide event loop."""
    policy = asyncio.get_event_loop_policy()
    loop   = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """
    Har test uchun yangi in-memory SQLite engine (StaticPool).

    StaticPool: barcha sessiyalar bitta SQLite connection orqali ishlaydi.
    Bu bir test ichidagi ikki sessiya (db + client) bitta :memory: DB ni ko'rishini ta'minlaydi.
    """
    from app.models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Har test uchun yangi in-memory SQLite DB.

    - Test boshida jadvallar yaratiladi
    - Test tugagach barcha ma'lumotlar yo'qoladi
    - Testlar bir-birini buzmasligi kafolatlangan
    """
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


# ── App + HTTP Clients ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """FastAPI app instance."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
async def client(app, test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client — DB override bilan (alohida sessiya).

    MUHIM: client ALOHIDA sessiya ishlatadi (db bilan emas),
    bu sample_medicine.quantity kabi fixture ob'ektlarining
    mutatsiyasini oldini oladi. StaticPool orqali bir xil DB ni ko'rishadi.
    """
    from app.core.database import get_db

    client_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with client_session_factory() as session:
            try:
                yield session
                await session.commit()   # Real get_db kabi — flush'ni DB ga yozish
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides.clear()  # Oldingi qoldiqlarni tozalaymiz
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Model Factories ───────────────────────────────────────────────────────────

@pytest.fixture
async def sample_animal(db: AsyncSession):
    """
    Test uchun bitta Animal yaratib beradi.

    acquisition_date: Animal modelida NOT NULL — shuning uchun
    majburiy ravishda berilishi kerak (DB default yo'q).
    """
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus

    animal = Animal(
        tag_id="TEST-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        breed="Holstein",
        acquisition_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(animal)
    await db.commit()
    await db.refresh(animal)
    return animal


@pytest.fixture
async def sample_animals(db: AsyncSession):
    """
    Test uchun 3 ta Animal yaratib beradi.

    Har birida acquisition_date majburiy — NOT NULL constraint.
    """
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus

    animals = [
        Animal(tag_id="TEST-A01", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
               acquisition_date=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        Animal(tag_id="TEST-A02", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.MALE,   status=AnimalStatus.ACTIVE,
               acquisition_date=datetime(2024, 2, 1, tzinfo=timezone.utc)),
        Animal(tag_id="TEST-A03", species=AnimalSpecies.GOAT,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
               acquisition_date=datetime(2024, 3, 1, tzinfo=timezone.utc)),
    ]
    for a in animals:
        db.add(a)
    await db.commit()
    for a in animals:
        await db.refresh(a)
    return animals


@pytest.fixture
async def sample_detection(db: AsyncSession, sample_animal):
    """Test uchun bitta Detection yaratib beradi."""
    from app.models.detection import Detection

    det = Detection(
        animal_id=        sample_animal.id,
        camera_id=        "CAM-TEST-001",
        timestamp=        datetime.now(timezone.utc),
        confidence=       0.92,
        class_id=         19,
        class_name=       "cow",
        bbox=             {"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
        estimated_weight= 285.5,
    )
    db.add(det)
    await db.commit()
    await db.refresh(det)
    return det


@pytest.fixture
async def sample_weight(db: AsyncSession, sample_animal):
    """Test uchun bitta WeightMeasurement yaratib beradi."""
    from app.models.weight_measurement import WeightMeasurement

    w = WeightMeasurement(
        animal_id=          sample_animal.id,
        timestamp=          datetime.now(timezone.utc),
        estimated_weight_kg=285.5,
        confidence_score=   0.92,
        camera_id=          "CAM-TEST-001",
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


# ── Mock Frame ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_frame() -> np.ndarray:
    """640x480 BGR tasodifiy kadr."""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


# ── Legacy Fixtures (test_cameras_api.py uchun) ──────────────────────────────

@pytest.fixture
def test_client(app):
    """Sinxron TestClient — test_cameras_api.py legacy uchun.
    
    Auth dependency override: cameras API testlari token bermaydi,
    shuning uchun get_current_active_user ni mock User bilan override qilamiz.
    """
    from fastapi.testclient import TestClient
    from app.api.v1.deps import get_current_active_user, require_manager

    class _MockUser:
        id = 1
        email = "test@taurus.uz"
        is_active = True
        is_manager = True
        is_admin = True

        @property
        def role(self):
            class _Role:
                value = "admin"
            return _Role()

    _mock_user = _MockUser()

    async def _override_user():
        return _mock_user

    async def _override_manager():
        return _mock_user

    app.dependency_overrides[get_current_active_user] = _override_user
    app.dependency_overrides[require_manager] = _override_manager

    client = TestClient(app)
    yield client

    # Tozalash
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(require_manager, None)


@pytest.fixture
def sample_camera_config():
    return {
        "camera_id": "TEST-CAM-001",
        "type": "simulated",
        "fps": 10,
        "width": 640,
        "height": 480,
        "auto_start": True,
    }


@pytest.fixture
def sample_rtsp_config():
    return {
        "camera_id": "RTSP-TEST-001",
        "type": "rtsp",
        "url": "rtsp://test:test@localhost:554/stream",
        "fps": 25,
        "width": 1920,
        "height": 1080,
        "reconnect_interval": 5,
        "connection_timeout": 10,
        "auto_start": False,
    }


@pytest.fixture
def sample_usb_config():
    return {
        "camera_id": "USB-TEST-001",
        "type": "usb",
        "device_index": 0,
        "fps": 30,
        "width": 640,
        "height": 480,
        "auto_reconnect": True,
        "auto_start": False,
    }


@pytest.fixture(autouse=True)
def cleanup_camera_manager():
    """
    Har test OLDIN va KEYIN camera manager ni tozalash.

    autouse=True — barcha testlarga avtomatik qo'llanadi.

    Sabab: camera_manager singleton bo'lgani uchun bir test qoldirgan
    kameralar keyingi testga o'tib ketishi mumkin. Ikki taraflama tozalash
    test izolyatsiyasini kafolatlaydi.
    """
    # ── Test oldidan tozalash ─────────────────────────────────────────
    try:
        from app.services.camera.camera_manager import camera_manager
        for camera_id in list(camera_manager.list_cameras()):
            try:
                camera_manager.unregister_camera(camera_id)
            except Exception:
                pass
    except Exception:
        pass

    yield

    # ── Test keyin tozalash ───────────────────────────────────────────
    try:
        from app.services.camera.camera_manager import camera_manager
        for camera_id in list(camera_manager.list_cameras()):
            try:
                camera_manager.unregister_camera(camera_id)
            except Exception:
                pass
    except Exception:
        pass

# ── Camera Test Helpers ───────────────────────────────────────────────────────

def assert_camera_stats_valid(stats: dict) -> None:
    """
    Kamera statistika dict to'g'ri strukturaga ega ekanligini tekshiradi.

    Barcha kamera implementatsiyalari (Simulated, USB, RTSP) bir xil
    get_stats() formatini qaytarishi shart. Shu helper shu kontraktni
    test ichida tekshiradi.

    Args:
        stats: get_stats() tomonidan qaytarilgan dict

    Raises:
        AssertionError: Agar birorta majburiy kalit yetishmasa yoki
                        qiymati noto'g'ri turdagi bo'lsa
    """
    assert isinstance(stats, dict), \
        f"stats dict bo'lishi kerak, {type(stats)} keldi"

    required_keys = {
        "camera_id": str,
        "running":   bool,
        "fps":       (int, float),
    }

    for key, expected_type in required_keys.items():
        assert key in stats, f"stats da '{key}' kaliti yo'q"
        assert isinstance(stats[key], expected_type), (
            f"stats['{key}'] = {stats[key]!r} "
            f"({expected_type.__name__} kutilgan)"
        )

    # frame_count bo'lsa — manfiy bo'lmasin
    if "frame_count" in stats:
        assert stats["frame_count"] >= 0, \
            f"frame_count manfiy bo'lmasligi kerak: {stats['frame_count']}"

    # fps manfiy bo'lmasin
    assert stats["fps"] >= 0, \
        f"fps manfiy bo'lmasligi kerak: {stats['fps']}"


def assert_valid_frame(frame, width: int = None, height: int = None) -> None:
    """
    CameraFrame yoki numpy array to'g'ri strukturaga ega ekanligini tekshiradi.

    Ikkita tur qabul qilinadi:
    - CameraFrame dataclass (SimulatedCameraService, RTSPCameraService)
    - numpy.ndarray (SimulatedCamera, eski API)

    Args:
        frame:  CameraFrame instance yoki numpy ndarray
        width:  Kutilgan kadr kengligi (None = tekshirilmaydi)
        height: Kutilgan kadr balandligi (None = tekshirilmaydi)

    Raises:
        AssertionError: Agar frame invalid bo'lsa
    """
    assert frame is not None, "frame None bo'lmasligi kerak"

    # numpy array holati (SimulatedCamera klass)
    if isinstance(frame, np.ndarray):
        assert frame.ndim == 3, \
            f"frame 3-o'lchamli bo'lishi kerak (H,W,C), {frame.ndim}-o'lchamli keldi"
        assert frame.shape[2] == 3, \
            f"frame 3 kanal (BGR) bo'lishi kerak, {frame.shape[2]} keldi"
        if height is not None:
            assert frame.shape[0] == height, \
                f"Balandlik {height} kutilgan, {frame.shape[0]} keldi"
        if width is not None:
            assert frame.shape[1] == width, \
                f"Kenglik {width} kutilgan, {frame.shape[1]} keldi"
        return

    # CameraFrame dataclass holati (SimulatedCameraService va boshqalar)
    assert hasattr(frame, "frame"),       "frame.frame numpy array bo'lishi kerak"
    assert hasattr(frame, "camera_id"),   "frame.camera_id bo'lishi kerak"
    assert hasattr(frame, "timestamp"),   "frame.timestamp bo'lishi kerak"
    assert hasattr(frame, "resolution"),  "frame.resolution bo'lishi kerak"

    assert isinstance(frame.frame, np.ndarray), \
        f"frame.frame np.ndarray bo'lishi kerak, {type(frame.frame)} keldi"
    assert frame.frame.ndim == 3, \
        f"frame.frame 3-o'lchamli bo'lishi kerak (H,W,C), {frame.frame.ndim}-o'lchamli keldi"
    assert frame.frame.shape[2] == 3, \
        f"frame.frame 3 kanal (BGR) bo'lishi kerak, {frame.frame.shape[2]} keldi"

    if width is not None:
        assert frame.resolution[0] == width, \
            f"Kenglik {width} kutilgan, {frame.resolution[0]} keldi"
    if height is not None:
        assert frame.resolution[1] == height, \
            f"Balandlik {height} kutilgan, {frame.resolution[1]} keldi"


# ── Performance Test Helper ───────────────────────────────────────────────────

class PerformanceMonitor:
    """
    Funksiya bajarilish vaqtini o'lchash uchun yordamchi klass.
    test_performance_fps va shunga o'xshash testlarda ishlatiladi.
    """

    def __init__(self) -> None:
        self._times: list[float] = []

    def measure(self, func) -> float:
        """
        Funksiyani bajarish va vaqtini yozib olish.

        Args:
            func: Vaqti o'lchanadigan callable (arg yo'q)

        Returns:
            Bajarilish vaqti (soniyada)
        """
        import time
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        self._times.append(elapsed)
        return elapsed

    def average(self) -> float:
        """O'rtacha bajarilish vaqti (soniyada)."""
        if not self._times:
            return 0.0
        return sum(self._times) / len(self._times)

    def max(self) -> float:
        """Maksimal bajarilish vaqti (soniyada)."""
        return max(self._times) if self._times else 0.0

    def reset(self) -> None:
        self._times.clear()


@pytest.fixture
def performance_monitor() -> PerformanceMonitor:
    """Har test uchun yangi PerformanceMonitor instance."""
    return PerformanceMonitor()

# ── Auth Fixtures (Sprint 5 — Authentication) ─────────────────────────────────

@pytest.fixture
async def admin_user(db):
    """Test uchun ADMIN foydalanuvchi."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email="testadmin@taurus.uz",
        username="testadmin",
        full_name="Test Administrator",
        hashed_password=hash_password("AdminTest1"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def manager_user(db):
    """Test uchun MANAGER foydalanuvchi."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email="testmanager@taurus.uz",
        username="testmanager",
        full_name="Test Manager",
        hashed_password=hash_password("ManagerTest1"),
        role=UserRole.MANAGER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def viewer_user(db):
    """Test uchun VIEWER foydalanuvchi."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email="testviewer@taurus.uz",
        username="testviewer",
        full_name="Test Viewer",
        hashed_password=hash_password("ViewerTest1"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_token(client, admin_user) -> str:
    """ADMIN foydalanuvchi uchun JWT access token."""
    r = await client.post("/api/v1/auth/login", json={
        "email": "testadmin@taurus.uz",
        "password": "AdminTest1",
    })
    return r.json()["access_token"]


@pytest.fixture
async def manager_token(client, manager_user) -> str:
    """MANAGER foydalanuvchi uchun JWT access token."""
    r = await client.post("/api/v1/auth/login", json={
        "email": "testmanager@taurus.uz",
        "password": "ManagerTest1",
    })
    return r.json()["access_token"]


@pytest.fixture
async def viewer_token(client, viewer_user) -> str:
    """VIEWER foydalanuvchi uchun JWT access token."""
    r = await client.post("/api/v1/auth/login", json={
        "email": "testviewer@taurus.uz",
        "password": "ViewerTest1",
    })
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    """Admin token bilan Authorization header."""
    return {"Authorization": f"Bearer {admin_token}"}

# ── Analytics Cache Izolyatsiyasi ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
async def clear_analytics_cache():
    """
    Har test OLDIN analytics Redis kesh kalitlarini tozalaydi.

    autouse=True — barcha testlarga avtomatik qo'llanadi.

    Sabab: analytics endpointlari Redis keshidan foydalanadi.
    Oldingi test bo'sh DB bilan keshga 0 yozishi mumkin.
    Keyingi test ma'lumotli DB bilan ishlasa, keshdan 0 olishi mumkin.

    Redis mavjud bo'lmasa (test muhiti) — bu fixture hech narsa qilmaydi.
    Redis mavjud bo'lsa — analytics kalitlarini tozalaydi.
    """
    from app.core.cache import cache_invalidate
    try:
        await cache_invalidate("analytics:*")
    except Exception:
        pass  # Redis mavjud bo'lmasa — xato yutib yuboriladi

    yield
    # Test keyin ham tozalash (ixtiyoriy, lekin izchillik uchun)
    try:
        await cache_invalidate("analytics:*")
    except Exception:
        pass