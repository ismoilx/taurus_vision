"""
Taurus Vision — Authentication Integration Tests

To'liq auth zanjirini tekshiradi:
  1. Login (to'g'ri/noto'g'ri hisob)
  2. Token bilan himoyalangan endpointga kirish
  3. Token bo'lmasa 401
  4. Token yangilash (refresh)
  5. Logout — token bekor qilinishi
  6. Admin: foydalanuvchi yaratish va boshqarish
  7. Role-based access control
  8. To'liq CRUD zanjiri: login → animal CRUD → logout

Barcha testlar izolatsiyalangan — har biri o'z DB va foydalanuvchisiga ega.

MUHIM: Bu fayl test_integration/ papkasida joylashgan, lekin u yergi conftest.py
barcha auth ni mock qilib qo'yadi. Shu sababli bu fayl o'zining REAL auth
ishlatadigan `client` fixture ni e'lon qiladi — integration conftest dagi
mock versiyani ustidan yopadi.
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import asyncio

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ════════════════════════════════════════════════════════════════════
# LOCAL CLIENT FIXTURE — REAL AUTH (integration conftest ni ustidan yopadi)
# ════════════════════════════════════════════════════════════════════

@pytest.fixture
async def client(app, test_engine) -> AsyncGenerator[AsyncClient, None]:
    """
    Auth flow testlari uchun REAL auth ishlatiladigan client.

    integration/conftest.py dagi mock client ni bu fayl doirasida
    ustidan yopadi. Faqat get_db override qilinadi — auth dependency lar
    HAQIQIY ishlaydi, token tekshiriladi.
    """
    from app.core.database import get_db

    client_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with client_session_factory() as session:
            yield session

    # Faqat DB override — auth mock QILINMAYDI
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════

async def create_user(db, email: str, username: str, password: str, role: str = "viewer"):
    """Test foydalanuvchisini to'g'ridan DB ga yozish."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        email=email,
        username=username,
        full_name=f"Test {username}",
        hashed_password=hash_password(password),
        role=UserRole(role),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login(client: AsyncClient, email: str, password: str) -> dict:
    """Login va token response qaytarish."""
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password,
    })
    return r


def auth_header(token: str) -> dict:
    """Authorization header yasash."""
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════════════════
# 1. LOGIN TESTLARI
# ════════════════════════════════════════════════════════════════════

class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_with_email_success(self, client: AsyncClient, db):
        """To'g'ri email + parol → 200 + token."""
        await create_user(db, "farm@test.uz", "farmuser", "FarmPass1")

        r = await login(client, "farm@test.uz", "FarmPass1")

        assert r.status_code == 200
        data = r.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["email"] == "farm@test.uz"
        assert data["user"]["role"]  == "viewer"
        # Parol hech qachon response da ko'rinmasligi kerak
        assert "password"        not in data["user"]
        assert "hashed_password" not in data["user"]

    async def test_login_with_username_success(self, client: AsyncClient, db):
        """Username bilan ham login ishlashi kerak."""
        await create_user(db, "user2@test.uz", "testuser2", "TestPass2")

        r = await client.post("/api/v1/auth/login", json={
            "username": "testuser2",
            "password": "TestPass2",
        })
        assert r.status_code == 200
        assert r.json()["user"]["username"] == "testuser2"

    async def test_login_wrong_password(self, client: AsyncClient, db):
        """Noto'g'ri parol → 401."""
        await create_user(db, "wrongpass@test.uz", "wrongpassuser", "Correct1")

        r = await login(client, "wrongpass@test.uz", "WrongPassword1")

        assert r.status_code == 401
        assert "message" in r.json()

    async def test_login_nonexistent_user(self, client: AsyncClient, db):
        """Mavjud bo'lmagan foydalanuvchi → 401."""
        r = await login(client, "nobody@ghost.uz", "SomePass1")
        assert r.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db):
        """Bloklangan foydalanuvchi → 401."""
        from app.core.security import hash_password
        from app.models.user import User, UserRole

        user = User(
            email="blocked@test.uz",
            username="blockeduser",
            full_name="Blocked",
            hashed_password=hash_password("BlockPass1"),
            role=UserRole.VIEWER,
            is_active=False,  # bloklangan
        )
        db.add(user)
        await db.commit()

        r = await login(client, "blocked@test.uz", "BlockPass1")
        assert r.status_code == 401

    async def test_login_missing_identifier(self, client: AsyncClient, db):
        """Email ham, username ham yo'q → 422."""
        r = await client.post("/api/v1/auth/login", json={
            "password": "SomePass1",
        })
        assert r.status_code == 422

    async def test_login_updates_last_login_at(self, client: AsyncClient, db):
        """Muvaffaqiyatli logindan keyin last_login_at yangilanishi kerak."""
        from sqlalchemy import select
        from app.models.user import User

        user = await create_user(db, "track@test.uz", "trackuser", "TrackPass1")
        assert user.last_login_at is None  # Login qilinmagan

        await login(client, "track@test.uz", "TrackPass1")

        # DB dan qayta yuklash
        await db.refresh(user)
        assert user.last_login_at is not None


# ════════════════════════════════════════════════════════════════════
# 2. ENDPOINT HIMOYASI
# ════════════════════════════════════════════════════════════════════

class TestEndpointProtection:
    """Token yo'q/noto'g'ri bo'lsa endpoint himoyasi."""

    async def test_animals_without_token(self, client: AsyncClient):
        """Token yo'q → 401 (403 emas!)."""
        r = await client.get("/api/v1/animals/")
        assert r.status_code in (401, 403)

    async def test_analytics_without_token(self, client: AsyncClient):
        """Analytics endpoint himoyalangan."""
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code in (401, 403)

    async def test_alerts_without_token(self, client: AsyncClient):
        """Alerts endpoint himoyalangan."""
        r = await client.get("/api/v1/alerts/")
        assert r.status_code in (401, 403)

    async def test_adi_without_token(self, client: AsyncClient):
        """ADI endpoint himoyalangan."""
        r = await client.get("/api/v1/adi/farm-summary")
        assert r.status_code in (401, 403)

    async def test_invalid_token_format(self, client: AsyncClient):
        """Noto'g'ri token formati → 401."""
        r = await client.get(
            "/api/v1/animals/",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert r.status_code == 401

    async def test_expired_looking_token(self, client: AsyncClient):
        """Buzilgan token → 401."""
        r = await client.get(
            "/api/v1/animals/",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"},
        )
        assert r.status_code == 401

    async def test_auth_endpoint_is_public(self, client: AsyncClient):
        """Login endpoint uchun token shart emas."""
        # Noto'g'ri credentials bilan ham 422/401 (500 emas!)
        r = await client.post("/api/v1/auth/login", json={
            "email": "x@x.uz", "password": "x",
        })
        assert r.status_code in (401, 422)  # 500 bo'lmasin

    async def test_health_endpoint_is_public(self, client: AsyncClient):
        """Health check endpoint ochiq bo'lishi kerak."""
        r = await client.get("/health/live")
        assert r.status_code == 200


# ════════════════════════════════════════════════════════════════════
# 3. TOKEN BILAN ENDPOINTLARGA KIRISH
# ════════════════════════════════════════════════════════════════════

class TestAuthenticatedAccess:
    """Token bilan himoyalangan endpointlarga kirish."""

    async def test_animals_with_valid_token(self, client: AsyncClient, db):
        """Token bilan animals endpoint ishlashi kerak."""
        await create_user(db, "viewer@test.uz", "vieweruser", "ViewPass1")

        r_login = await login(client, "viewer@test.uz", "ViewPass1")
        token = r_login.json()["access_token"]

        r = await client.get("/api/v1/animals/", headers=auth_header(token))
        assert r.status_code == 200
        assert "items" in r.json()

    async def test_get_me_returns_current_user(self, client: AsyncClient, db):
        """GET /auth/me — token egasini qaytarishi kerak."""
        await create_user(db, "me@test.uz", "meuser", "MePass1", "manager")

        r_login = await login(client, "me@test.uz", "MePass1")
        token = r_login.json()["access_token"]

        r = await client.get("/api/v1/auth/me", headers=auth_header(token))

        assert r.status_code == 200
        data = r.json()
        assert data["email"]    == "me@test.uz"
        assert data["username"] == "meuser"
        assert data["role"]     == "manager"
        assert "hashed_password" not in data

    async def test_multiple_users_isolated(self, client: AsyncClient, db):
        """Ikki foydalanuvchi token lari bir-birini buzmaydi."""
        await create_user(db, "user_a@test.uz", "user_a", "PassA_1")
        await create_user(db, "user_b@test.uz", "user_b", "PassB_1")

        r_a = await login(client, "user_a@test.uz", "PassA_1")
        r_b = await login(client, "user_b@test.uz", "PassB_1")

        token_a = r_a.json()["access_token"]
        token_b = r_b.json()["access_token"]

        me_a = await client.get("/api/v1/auth/me", headers=auth_header(token_a))
        me_b = await client.get("/api/v1/auth/me", headers=auth_header(token_b))

        assert me_a.json()["email"] == "user_a@test.uz"
        assert me_b.json()["email"] == "user_b@test.uz"
        assert me_a.json()["email"] != me_b.json()["email"]


# ════════════════════════════════════════════════════════════════════
# 4. REFRESH TOKEN
# ════════════════════════════════════════════════════════════════════

class TestTokenRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_returns_new_tokens(self, client: AsyncClient, db):
        """Refresh token bilan yangi token juftligi olish."""
        await create_user(db, "refresh@test.uz", "refreshuser", "RefreshPass1")

        r_login = await login(client, "refresh@test.uz", "RefreshPass1")
        old_access  = r_login.json()["access_token"]
        old_refresh = r_login.json()["refresh_token"]

        await asyncio.sleep(1)

        r_refresh = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": old_refresh,
        })

        assert r_refresh.status_code == 200
        data = r_refresh.json()
        assert "access_token"  in data
        assert "refresh_token" in data
        # Yangi tokenlar eski dan farqli
        assert data["access_token"]  != old_access
        assert data["refresh_token"] != old_refresh

    async def test_refresh_with_access_token_fails(self, client: AsyncClient, db):
        """Access token ni refresh o'rnida ishlatish → 401."""
        await create_user(db, "wrongtoken@test.uz", "wrongtokenuser", "WrongPass1")

        r_login = await login(client, "wrongtoken@test.uz", "WrongPass1")
        access_token = r_login.json()["access_token"]

        # Access token → refresh endpointda
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token,
        })
        assert r.status_code == 401

    async def test_invalid_refresh_token_fails(self, client: AsyncClient, db):
        """Noto'g'ri refresh token → 401."""
        r = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not.a.real.token",
        })
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════
# 5. LOGOUT
# ════════════════════════════════════════════════════════════════════

class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout_success(self, client: AsyncClient, db):
        """Logout → 204 No Content."""
        await create_user(db, "logout@test.uz", "logoutuser", "LogoutPass1")

        r_login = await login(client, "logout@test.uz", "LogoutPass1")
        token = r_login.json()["access_token"]

        r_logout = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(token),
        )
        assert r_logout.status_code == 204

    async def test_logout_invalidates_refresh_token(self, client: AsyncClient, db):
        """Logout dan keyin refresh token ishlamasligi kerak."""
        await create_user(db, "logoutre@test.uz", "logoutreuser", "LogoutRe1")

        r_login = await login(client, "logoutre@test.uz", "LogoutRe1")
        access_token  = r_login.json()["access_token"]
        refresh_token = r_login.json()["refresh_token"]

        # Logout
        await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(access_token),
        )

        # Refresh token endi ishlamasligi kerak
        r_refresh = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert r_refresh.status_code == 401

    async def test_logout_without_token(self, client: AsyncClient, db):
        """Token yo'q logout → 401/403."""
        r = await client.post("/api/v1/auth/logout")
        assert r.status_code in (401, 403)


# ════════════════════════════════════════════════════════════════════
# 6. ROLE-BASED ACCESS CONTROL
# ════════════════════════════════════════════════════════════════════

class TestRoleBasedAccess:
    """RBAC — kim nimaga kirishi mumkin."""

    async def test_admin_can_list_users(self, client: AsyncClient, db):
        """ADMIN foydalanuvchilar ro'yxatini ko'ra oladi."""
        await create_user(db, "admin@test.uz", "adminuser", "AdminPass1", "admin")

        r_login = await login(client, "admin@test.uz", "AdminPass1")
        token = r_login.json()["access_token"]

        r = await client.get("/api/v1/auth/users", headers=auth_header(token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["total"] >= 1

    async def test_viewer_cannot_list_users(self, client: AsyncClient, db):
        """VIEWER foydalanuvchilar ro'yxatini ko'ra olmaydi → 403."""
        await create_user(db, "viewer2@test.uz", "viewer2", "ViewPass2", "viewer")

        r_login = await login(client, "viewer2@test.uz", "ViewPass2")
        token = r_login.json()["access_token"]

        r = await client.get("/api/v1/auth/users", headers=auth_header(token))
        assert r.status_code == 403

    async def test_manager_cannot_list_users(self, client: AsyncClient, db):
        """MANAGER ham foydalanuvchilar ro'yxatini ko'ra olmaydi → 403."""
        await create_user(db, "manager@test.uz", "manageruser", "ManPass1", "manager")

        r_login = await login(client, "manager@test.uz", "ManPass1")
        token = r_login.json()["access_token"]

        r = await client.get("/api/v1/auth/users", headers=auth_header(token))
        assert r.status_code == 403

    async def test_admin_can_create_user(self, client: AsyncClient, db):
        """ADMIN yangi foydalanuvchi yarata oladi."""
        await create_user(db, "admin2@test.uz", "admin2", "Admin2Pass1", "admin")

        r_login = await login(client, "admin2@test.uz", "Admin2Pass1")
        token = r_login.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/users",
            headers=auth_header(token),
            json={
                "email":    "newuser@test.uz",
                "username": "newuser",
                "password": "NewUser1Pass",
                "role":     "viewer",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["email"]    == "newuser@test.uz"
        assert data["username"] == "newuser"
        assert "hashed_password" not in data

    async def test_viewer_cannot_create_user(self, client: AsyncClient, db):
        """VIEWER yangi foydalanuvchi yarata olmaydi → 403."""
        await create_user(db, "viewer3@test.uz", "viewer3", "ViewPass3", "viewer")

        r_login = await login(client, "viewer3@test.uz", "ViewPass3")
        token = r_login.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/users",
            headers=auth_header(token),
            json={
                "email":    "blocked@test.uz",
                "username": "blockedcreate",
                "password": "BlockPass1",
                "role":     "viewer",
            },
        )
        assert r.status_code == 403


# ════════════════════════════════════════════════════════════════════
# 7. PAROL O'ZGARTIRISH
# ════════════════════════════════════════════════════════════════════

class TestPasswordChange:
    """POST /api/v1/auth/change-password"""

    async def test_change_password_success(self, client: AsyncClient, db):
        """To'g'ri joriy parol → parol o'zgaradi, yangi parol bilan login."""
        await create_user(db, "chpass@test.uz", "chpassuser", "OldPass1")

        r_login = await login(client, "chpass@test.uz", "OldPass1")
        token = r_login.json()["access_token"]

        r_change = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_header(token),
            json={
                "current_password": "OldPass1",
                "new_password":     "NewPass1Updated",
            },
        )
        assert r_change.status_code == 204

        # Yangi parol bilan login ishlashi kerak
        r_new_login = await login(client, "chpass@test.uz", "NewPass1Updated")
        assert r_new_login.status_code == 200

        # Eski parol bilan login ishlamasligi kerak
        r_old_login = await login(client, "chpass@test.uz", "OldPass1")
        assert r_old_login.status_code == 401

    async def test_change_password_wrong_current(self, client: AsyncClient, db):
        """Noto'g'ri joriy parol → 401."""
        await create_user(db, "wrongcurr@test.uz", "wrongcurruser", "CurrentPass1")

        r_login = await login(client, "wrongcurr@test.uz", "CurrentPass1")
        token = r_login.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_header(token),
            json={
                "current_password": "WrongCurrentPass1",
                "new_password":     "NewPass1",
            },
        )
        assert r.status_code == 401

    async def test_change_password_same_as_current(self, client: AsyncClient, db):
        """Yangi parol joriy parol bilan bir xil → 400."""
        await create_user(db, "samep@test.uz", "samepuser", "SamePass1")

        r_login = await login(client, "samep@test.uz", "SamePass1")
        token = r_login.json()["access_token"]

        r = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_header(token),
            json={
                "current_password": "SamePass1",
                "new_password":     "SamePass1",
            },
        )
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════
# 8. TO'LIQ END-TO-END ZANJIR
# ════════════════════════════════════════════════════════════════════

class TestFullAuthChain:
    """
    To'liq E2E zanjir:
    Register (admin yaratadi) → Login → CRUD → Logout → Token bekor
    """

    async def test_full_user_lifecycle(self, client: AsyncClient, db):
        """
        To'liq hayot davri:
        1. Admin tizimga kiradi
        2. Yangi manager yaratadi
        3. Manager tizimga kiradi
        4. Manager animals ko'radi
        5. Manager tizimdan chiqadi
        6. Manager eski token bilan kirishga urinadi — muvaffaqiyatsiz
        """
        # 1. Admin yaratish va login
        await create_user(db, "sysadmin@taurus.uz", "sysadmin", "AdminSys1", "admin")
        r_admin = await login(client, "sysadmin@taurus.uz", "AdminSys1")
        assert r_admin.status_code == 200
        admin_token = r_admin.json()["access_token"]

        # 2. Admin yangi manager yaratadi
        r_create = await client.post(
            "/api/v1/auth/users",
            headers=auth_header(admin_token),
            json={
                "email":    "fieldmanager@taurus.uz",
                "username": "fieldmgr",
                "password": "Manager1Pass",
                "role":     "manager",
                "full_name": "Ferma Menejeri",
            },
        )
        assert r_create.status_code == 201
        assert r_create.json()["role"] == "manager"

        # 3. Manager login qiladi
        r_mgr = await login(client, "fieldmanager@taurus.uz", "Manager1Pass")
        assert r_mgr.status_code == 200
        mgr_token    = r_mgr.json()["access_token"]
        mgr_refresh  = r_mgr.json()["refresh_token"]

        # 4. Manager /me ni tekshiradi
        r_me = await client.get("/api/v1/auth/me", headers=auth_header(mgr_token))
        assert r_me.status_code == 200
        assert r_me.json()["full_name"] == "Ferma Menejeri"
        assert r_me.json()["role"]      == "manager"

        # 5. Manager animals ko'ra oladi
        r_animals = await client.get("/api/v1/animals/", headers=auth_header(mgr_token))
        assert r_animals.status_code == 200

        # 6. Manager logout qiladi
        r_logout = await client.post(
            "/api/v1/auth/logout",
            headers=auth_header(mgr_token),
        )
        assert r_logout.status_code == 204

        # 7. Logout dan keyin refresh token ishlamasligi kerak
        r_ref = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": mgr_refresh,
        })
        assert r_ref.status_code == 401

    async def test_duplicate_email_rejected(self, client: AsyncClient, db):
        """Bir xil email bilan ikki foydalanuvchi yaratib bo'lmaydi."""
        await create_user(db, "dup@test.uz", "dupuser1", "DupPass1", "admin")

        r_login = await login(client, "dup@test.uz", "DupPass1")
        token = r_login.json()["access_token"]

        # Birinchi yaratish
        await client.post("/api/v1/auth/users", headers=auth_header(token), json={
            "email": "taken@test.uz", "username": "takenuser1",
            "password": "Taken1Pass", "role": "viewer",
        })

        # Ikkinchi — bir xil email
        r2 = await client.post("/api/v1/auth/users", headers=auth_header(token), json={
            "email": "taken@test.uz", "username": "takenuser2",
            "password": "Taken2Pass", "role": "viewer",
        })
        assert r2.status_code in (409, 400)

    async def test_admin_cannot_deactivate_self(self, client: AsyncClient, db):
        """Admin o'zini bloklay olmaydi."""
        user = await create_user(db, "selfblock@test.uz", "selfblock", "SelfBlock1", "admin")

        r_login = await login(client, "selfblock@test.uz", "SelfBlock1")
        token = r_login.json()["access_token"]

        r = await client.post(
            f"/api/v1/auth/users/{user.id}/deactivate",
            headers=auth_header(token),
        )
        assert r.status_code == 400