"""
Auth API Tests — /api/v1/auth/

Qamrovi:
  - POST /auth/login    — muvaffaqiyatli, noto'g'ri parol, yo'q user
  - POST /auth/refresh  — yangi token olish, noto'g'ri token
  - POST /auth/logout   — muvaffaqiyatli logout
  - GET  /auth/me       — joriy foydalanuvchi

O'ZGARISHLAR (bugfix):
  - passlib olib tashlandi → app.core.security.hash_password ishlatiladi
  - role="admin" → UserRole.ADMIN enum ishlatiladi
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def admin_user(db):
    """Test uchun ADMIN foydalanuvchi yaratish."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        username="testadmin",
        email="admin@test.com",
        full_name="Test Admin",
        hashed_password=hash_password("TestAdmin1"),
        role=UserRole.ADMIN,
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
        "password": "TestAdmin1",
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


# =============================================================================
# LOGIN TESTS
# =============================================================================

class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_success_username(self, client: AsyncClient, admin_user):
        """Username + parol bilan muvaffaqiyatli login."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "testadmin",
            "password": "TestAdmin1",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        assert data["token_type"]        == "bearer"
        assert data["user"]["username"]  == "testadmin"
        assert data["user"]["role"]      == "admin"
        assert "hashed_password" not in data["user"]

    async def test_login_success_email(self, client: AsyncClient, admin_user):
        """Email + parol bilan muvaffaqiyatli login."""
        r = await client.post("/api/v1/auth/login", json={
            "email":    "admin@test.com",
            "password": "TestAdmin1",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(self, client: AsyncClient, admin_user):
        """Noto'g'ri parol — 401."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "testadmin",
            "password": "WrongPass1",
        })
        assert r.status_code == 401

    async def test_login_unknown_user(self, client: AsyncClient):
        """Mavjud bo'lmagan foydalanuvchi — 401."""
        r = await client.post("/api/v1/auth/login", json={
            "username": "nobody",
            "password": "SomePass1",
        })
        assert r.status_code == 401

    async def test_login_missing_fields(self, client: AsyncClient):
        """Parolsiz so'rov — 422."""
        r = await client.post("/api/v1/auth/login", json={"username": "testadmin"})
        assert r.status_code == 422

    async def test_login_inactive_user(self, client: AsyncClient, db):
        """Nofaol (bloklangan) foydalanuvchi — 401."""
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        inactive = User(
            username="inactive_user",
            email="inactive@test.com",
            hashed_password=hash_password("InactivePass1"),
            role=UserRole.VIEWER,
            is_active=False,
        )
        db.add(inactive)
        await db.commit()

        r = await client.post("/api/v1/auth/login", json={
            "username": "inactive_user",
            "password": "InactivePass1",
        })
        assert r.status_code == 401


# =============================================================================
# REFRESH TOKEN TESTS
# =============================================================================

class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client: AsyncClient, auth_tokens):
        """Refresh token bilan yangi access token olish."""
        import asyncio
        await asyncio.sleep(1)  # 1s — iat farqli bo'lsin
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_tokens["refresh_token"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        assert "user"          in data
        assert data["access_token"] != auth_tokens["access_token"]

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Noto'g'ri refresh token — 401."""
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert r.status_code == 401

    async def test_refresh_empty_token(self, client: AsyncClient):
        """Bo'sh token — 401 yoki 422."""
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": ""})
        assert r.status_code in (401, 422)

    async def test_refresh_access_token_rejected(self, client: AsyncClient, auth_tokens):
        """Access token ni refresh o'rnida ishlatish — 401."""
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_tokens["access_token"],
        })
        assert r.status_code == 401


# =============================================================================
# LOGOUT TESTS
# =============================================================================

class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout_success(self, client: AsyncClient, auth_tokens):
        """Token bilan muvaffaqiyatli logout."""
        r = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        assert r.status_code in (200, 204)

    async def test_logout_without_token(self, client: AsyncClient):
        """Token yo'q holda logout — 401."""
        r = await client.post("/api/v1/auth/logout")
        assert r.status_code == 401

    async def test_refresh_after_logout_fails(self, client: AsyncClient, auth_tokens):
        """Logout dan keyin refresh token ishlamaydi."""
        await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        )
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": auth_tokens["refresh_token"],
        })
        assert r.status_code == 401


# =============================================================================
# /ME TESTS
# =============================================================================

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
        assert data["email"]    == "admin@test.com"
        assert data["role"]     == "admin"
        assert "hashed_password"    not in data
        assert "refresh_token_hash" not in data

    async def test_me_unauthenticated(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        """Noto'g'ri token — 401."""
        r = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert r.status_code == 401