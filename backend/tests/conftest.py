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

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
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
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Har test uchun yangi in-memory SQLite DB.

    - Test boshida jadvallar yaratiladi
    - Test tugagach barcha ma'lumotlar yo'qoladi
    - Testlar bir-birini buzmasligi kafolatlangan
    """
    from app.models.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


# ── App + HTTP Clients ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """FastAPI app instance."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
async def client(app, db) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client — DB override bilan.

    Har request haqiqiy DB o'rniga test DB ga boradi.
    """
    from app.core.database import get_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Model Factories ───────────────────────────────────────────────────────────

@pytest.fixture
async def sample_animal(db: AsyncSession):
    """Test uchun bitta Animal yaratib beradi."""
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus

    animal = Animal(
        tag_id="TEST-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        breed="Holstein",
    )
    db.add(animal)
    await db.commit()
    await db.refresh(animal)
    return animal


@pytest.fixture
async def sample_animals(db: AsyncSession):
    """Test uchun 3 ta Animal yaratib beradi."""
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus

    animals = [
        Animal(tag_id="TEST-A01", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE),
        Animal(tag_id="TEST-A02", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.MALE,   status=AnimalStatus.ACTIVE),
        Animal(tag_id="TEST-A03", species=AnimalSpecies.GOAT,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE),
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
    """Sinxron TestClient — test_cameras_api.py legacy uchun."""
    from fastapi.testclient import TestClient
    return TestClient(app)


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
    """Har test dan keyin camera manager ni tozalash."""
    yield
    try:
        from app.services.camera.camera_manager import camera_manager
        for camera_id in list(camera_manager.list_cameras()):
            try:
                camera_manager.unregister_camera(camera_id)
            except Exception:
                pass
    except Exception:
        pass