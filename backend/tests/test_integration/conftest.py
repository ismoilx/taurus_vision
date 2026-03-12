"""
Integration testlar uchun conftest.

Weight pipeline va boshqa integration testlar auth token bermaydi —
shuning uchun auth dependency'larni mock Manager bilan override qilamiz.

Faqat test_integration/ ichidagi testlarga qo'llanadi.
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class _MockManagerUser:
    """Integration testlar uchun mock MANAGER foydalanuvchi.

    UserResponse.model_validate() muvaffaqiyatli o'tishi uchun
    barcha kerakli maydonlar to'liq ko'rsatilgan.
    """
    id            = 999
    email         = "integration_test@taurus.uz"
    username      = "integration_test"
    full_name     = "Integration Test Manager"
    is_active     = True
    is_manager    = True
    is_admin      = True
    last_login_at = None

    @property
    def created_at(self):
        from datetime import datetime, timezone
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @property
    def role(self):
        from app.models.user import UserRole
        return UserRole.MANAGER


_mock_manager = _MockManagerUser()


@pytest.fixture
async def client(app, test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Integration test uchun AsyncClient.

    Farqi: auth dependency'lar mock Manager bilan override qilinadi,
    shuning uchun testlar token bermasa ham 200 oladi.
    DB ham alohida sessiya orqali (StaticPool).
    """
    from app.core.database import get_db
    from app.api.v1.deps import (
        get_current_active_user,
        require_manager,
        require_admin,
    )

    client_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with client_session_factory() as session:
            yield session

    async def override_user():
        return _mock_manager

    async def override_manager():
        return _mock_manager

    async def override_admin():
        return _mock_manager

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db]                  = override_get_db
    app.dependency_overrides[get_current_active_user] = override_user
    app.dependency_overrides[require_manager]         = override_manager
    app.dependency_overrides[require_admin]           = override_admin

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Camera Detection Integration Fixtures ────────────────────────────────────

@pytest.fixture
def mock_detection_result():
    """Mock YOLO detection natijasi."""
    from unittest.mock import MagicMock
    result = MagicMock()
    result.boxes = []
    result.names = {0: "cow"}
    result.conf = []
    return [result]


@pytest.fixture
def mock_yolo():
    """Mock YOLOv8 model."""
    from unittest.mock import patch, MagicMock
    with patch("ultralytics.YOLO") as mock_cls:
        yield mock_cls