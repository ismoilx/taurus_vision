"""
Auth API Tests — /api/v1/auth/

Qamrovi:
  - POST /auth/login    — muvaffaqiyatli, noto'g'ri parol, yo'q user
  - POST /auth/refresh  — yangi token olish, noto'g'ri token
  - POST /auth/logout   — muvaffaqiyatli logout
  - GET  /auth/me       — joriy foydalanuvchi
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


@pytest.fixture
async def admin_user(db):
    """Test admin user yaratish."""
    from app.models.user import User
    from passlib.context import CryptContext

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        username="testadmin",
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=pwd_ctx.hash("testpass123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def auth_tokens(client: AsyncClient, admin_user):
    """Login qilib access + refresh token olish."""
    r = await client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    assert r.status_code == 200
    return r.json()


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_success_username(self, client: AsyncClient, admin_user):
        """Username + parol bilan muvaffaqiyatli login."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "testadmin",
            "password": "testpass123",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "testadmin"
        assert data["user"]["role"] == "admin"

    async def test_login_success_email(self, client: AsyncClient, admin_user):
        """Email + parol bilan muvaffaqiyatli login."""
        r = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "testpass123",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(self, client: AsyncClient, admin_user):
        """Noto'g'ri parol — 401."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "testadmin",
            "password": "wrongpassword",
        })
        assert r.status_code == 401

    async def test_login_unknown_user(self, client: AsyncClient):
        """Mavjud bo'lmagan foydalanuvchi — 401."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "nobody",
            "password": "pass123",
        })
        assert r.status_code == 401

    async def test_login_missing_fields(self, client: AsyncClient):
        """Parolsiz so'rov — 422."""
        r = await client.post("/api/v1/auth/login", json={"username": "testadmin"})
        assert r.status_code == 422

    async def test_login_inactive_user(self, client: AsyncClient, db):
        """Nofaol foydalanuvchi — 401."""
        from app.models.user import User
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        inactive = User(
            username="inactive",
            email="inactive@test.com",
            hashed_password=pwd_ctx.hash("pass123"),
            role="viewer",
            is_active=False,
        )
        db.add(inactive)
        await db.commit()

        r = await client.post("/api/v1/auth/login", json={
            "username": "inactive",
            "password": "pass123",
        })
        assert r.status_code == 401


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client: AsyncClient, auth_tokens):
        """Yangi access token olish."""
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_tokens["refresh_token"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["access_token"] != auth_tokens["access_token"]  # yangi token

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Noto'g'ri refresh token — 401."""
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert r.status_code == 401

    async def test_refresh_empty_token(self, client: AsyncClient):
        """Bo'sh token — 422."""
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": ""})
        assert r.status_code in (401, 422)


class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout_success(self, client: AsyncClient, auth_tokens):
        """Token bilan logout."""
        r = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert r.status_code in (200, 204)

    async def test_logout_without_token(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.post("/api/v1/auth/logout")
        assert r.status_code == 401


class TestMe:
    """GET /api/v1/auth/me"""

    async def test_me_authenticated(self, client: AsyncClient, auth_tokens):
        """Token bilan joriy foydalanuvchi ma'lumotlari."""
        r = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["username"] == "testadmin"
        assert data["email"] == "admin@test.com"
        assert "hashed_password" not in data  # parol chiqmasligi kerak

    async def test_me_unauthenticated(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        """Noto'g'ri token — 401."""
        r = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert r.status_code == 401