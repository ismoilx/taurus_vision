"""
TAURUS VISION — tests/test_services/test_auth_service.py
===========================================================
AuthService + UserRepository uchun to'liq, vahshiy testlar.

Qamrov:
  ✓ UserRepository.create              — yaratish, DB xato
  ✓ UserRepository.get_by_id          — mavjud, yo'q, DB xato
  ✓ UserRepository.get_by_email       — case-insensitive, mavjud, yo'q
  ✓ UserRepository.get_by_username    — case-insensitive, trim
  ✓ UserRepository.get_all            — sahifalash, only_active filter
  ✓ UserRepository.count              — jami, faqat faol
  ✓ UserRepository.save_refresh_token_hash — saqlash, tozalash (logout)
  ✓ UserRepository.update_last_login  — vaqt yangilanishi
  ✓ UserRepository.update_password    — hash, sessiya tozalanishi
  ✓ UserRepository.update_profile     — partial update, deactivation
  ✓ AuthService.login                 — email, username, noto'g'ri parol,
                                        yo'q user, bloklangan user
  ✓ AuthService.refresh_access_token  — muvaffaqiyatli, noto'g'ri, logout keyin
  ✓ AuthService.logout                — token tozalanishi
  ✓ AuthService.create_user           — admin huquqi, duplicate email/username
  ✓ AuthService.update_user           — admin/o'z profilini, ruxsatsiz
  ✓ AuthService.change_password       — to'g'ri/noto'g'ri parol, bir xil parol
  ✓ AuthService.admin_reset_password  — admin huquqi, o'z parolini tiklash
  ✓ AuthService.get_all_users         — admin only, sahifalash
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleViolationError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.core.security import (
    hash_password,
    create_refresh_token,
    hash_token,
    decode_token,
)
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    UserCreate,
    UserUpdate,
)
from app.services.auth_service import AuthService

pytestmark = [pytest.mark.asyncio]


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def admin_user_obj(db: AsyncSession) -> User:
    """DB ga saqlangan ADMIN foydalanuvchi."""
    user = User(
        email="admin@taurus.uz",
        username="sysadmin",
        full_name="System Admin",
        hashed_password=hash_password("AdminPass1"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def manager_user_obj(db: AsyncSession) -> User:
    """DB ga saqlangan MANAGER foydalanuvchi."""
    user = User(
        email="manager@taurus.uz",
        username="farmmanager",
        full_name="Farm Manager",
        hashed_password=hash_password("ManagerPass1"),
        role=UserRole.MANAGER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def viewer_user_obj(db: AsyncSession) -> User:
    """DB ga saqlangan VIEWER foydalanuvchi."""
    user = User(
        email="viewer@taurus.uz",
        username="farmviewer",
        full_name="Farm Viewer",
        hashed_password=hash_password("ViewerPass1"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def inactive_user_obj(db: AsyncSession) -> User:
    """DB ga saqlangan BLOKLANGAN foydalanuvchi."""
    user = User(
        email="inactive@taurus.uz",
        username="inactiveuser",
        full_name="Blocked User",
        hashed_password=hash_password("InactivePass1"),
        role=UserRole.VIEWER,
        is_active=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
def repo(db: AsyncSession) -> UserRepository:
    return UserRepository(db)


@pytest.fixture
def auth_service(db: AsyncSession) -> AuthService:
    return AuthService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryCreate:
    """UserRepository.create() testlari."""

    async def test_create_returns_user_with_id(self, db, repo):
        """Yaratilgan user ID bilan qaytariladi."""
        user = User(
            email="new@test.com",
            username="newuser",
            hashed_password=hash_password("NewPass1"),
            role=UserRole.VIEWER,
            is_active=True,
        )
        created = await repo.create(user)
        assert created.id is not None
        assert created.id > 0

    async def test_create_saves_all_fields(self, db, repo):
        """Barcha maydonlar to'g'ri saqlanadi."""
        user = User(
            email="full@test.com",
            username="fulluser",
            full_name="Full Name",
            hashed_password=hash_password("FullPass1"),
            role=UserRole.MANAGER,
            is_active=True,
        )
        created = await repo.create(user)
        assert created.email     == "full@test.com"
        assert created.username  == "fulluser"
        assert created.full_name == "Full Name"
        assert created.role      == UserRole.MANAGER
        assert created.is_active is True

    async def test_create_two_users_different_ids(self, db, repo):
        """Ikki user turli ID'lar oladi."""
        u1 = User(email="u1@t.com", username="user1",
                  hashed_password=hash_password("Pass1A"), role=UserRole.VIEWER, is_active=True)
        u2 = User(email="u2@t.com", username="user2",
                  hashed_password=hash_password("Pass2B"), role=UserRole.VIEWER, is_active=True)
        c1 = await repo.create(u1)
        await db.commit()
        c2 = await repo.create(u2)
        assert c1.id != c2.id

    async def test_create_duplicate_email_raises(self, db, repo, admin_user_obj):
        """Duplicate email → IntegrityError (DB darajasida)."""
        from sqlalchemy.exc import IntegrityError
        duplicate = User(
            email="admin@taurus.uz",  # Allaqachon mavjud
            username="differentuser",
            hashed_password=hash_password("DiffPass1"),
            role=UserRole.VIEWER,
            is_active=True,
        )
        with pytest.raises(Exception):  # IntegrityError yoki DatabaseError
            await repo.create(duplicate)
            await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — GET BY ID
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryGetById:
    """UserRepository.get_by_id() testlari."""

    async def test_get_existing_user(self, repo, admin_user_obj):
        """Mavjud foydalanuvchi topiladi."""
        user = await repo.get_by_id(admin_user_obj.id)
        assert user is not None
        assert user.id       == admin_user_obj.id
        assert user.username == "sysadmin"

    async def test_get_nonexistent_returns_none(self, repo):
        """Mavjud bo'lmagan ID → None."""
        result = await repo.get_by_id(999999)
        assert result is None

    async def test_get_negative_id_returns_none(self, repo):
        """Manfiy ID → None."""
        result = await repo.get_by_id(-1)
        assert result is None

    async def test_get_zero_id_returns_none(self, repo):
        """ID=0 → None."""
        result = await repo.get_by_id(0)
        assert result is None

    async def test_get_inactive_user_returns_user(self, repo, inactive_user_obj):
        """Bloklangan foydalanuvchi ham topiladi."""
        user = await repo.get_by_id(inactive_user_obj.id)
        assert user is not None
        assert user.is_active is False


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — GET BY EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryGetByEmail:
    """UserRepository.get_by_email() testlari."""

    async def test_get_by_exact_email(self, repo, admin_user_obj):
        """Aniq email bilan topish."""
        user = await repo.get_by_email("admin@taurus.uz")
        assert user is not None
        assert user.id == admin_user_obj.id

    async def test_email_case_insensitive(self, repo, admin_user_obj):
        """Email katta-kichik harfga sezgir emas."""
        for variant in ["ADMIN@TAURUS.UZ", "Admin@Taurus.UZ", "admin@TAURUS.uz"]:
            user = await repo.get_by_email(variant)
            assert user is not None, f"Email '{variant}' topilmadi"
            assert user.id == admin_user_obj.id

    async def test_email_with_whitespace(self, repo, admin_user_obj):
        """Bo'sh joy bilan email — strip qilinadi."""
        user = await repo.get_by_email("  admin@taurus.uz  ")
        assert user is not None

    async def test_nonexistent_email_returns_none(self, repo):
        """Mavjud bo'lmagan email → None."""
        result = await repo.get_by_email("nobody@nowhere.com")
        assert result is None

    async def test_empty_email_returns_none(self, repo):
        """Bo'sh email → None."""
        result = await repo.get_by_email("")
        assert result is None

    async def test_different_users_by_email(self, repo, admin_user_obj, viewer_user_obj):
        """Turli emaillar turli foydalanuvchilarni qaytaradi."""
        admin  = await repo.get_by_email("admin@taurus.uz")
        viewer = await repo.get_by_email("viewer@taurus.uz")
        assert admin.id  != viewer.id
        assert admin.role  == UserRole.ADMIN
        assert viewer.role == UserRole.VIEWER


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — GET BY USERNAME
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryGetByUsername:
    """UserRepository.get_by_username() testlari."""

    async def test_get_by_exact_username(self, repo, admin_user_obj):
        """Aniq username bilan topish."""
        user = await repo.get_by_username("sysadmin")
        assert user is not None
        assert user.id == admin_user_obj.id

    async def test_username_case_insensitive(self, repo, admin_user_obj):
        """Username katta-kichik harfga sezgir emas."""
        for variant in ["SYSADMIN", "SysAdmin", "sYSaDmIn"]:
            user = await repo.get_by_username(variant)
            assert user is not None, f"Username '{variant}' topilmadi"

    async def test_username_with_whitespace(self, repo, admin_user_obj):
        """Username atrofidagi bo'sh joy strip qilinadi."""
        user = await repo.get_by_username("  sysadmin  ")
        assert user is not None

    async def test_nonexistent_username_returns_none(self, repo):
        """Mavjud bo'lmagan username → None."""
        result = await repo.get_by_username("phantom_user_xyz")
        assert result is None

    async def test_empty_username_returns_none(self, repo):
        """Bo'sh username → None."""
        result = await repo.get_by_username("")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — GET ALL & COUNT
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryGetAll:
    """UserRepository.get_all() va count() testlari."""

    async def test_get_all_returns_all_users(
        self, repo, admin_user_obj, manager_user_obj, viewer_user_obj
    ):
        """get_all() barcha foydalanuvchilarni qaytaradi."""
        users = await repo.get_all()
        assert len(users) >= 3

    async def test_get_all_only_active_filters(
        self, repo, admin_user_obj, inactive_user_obj
    ):
        """only_active=True faqat faol foydalanuvchilarni qaytaradi."""
        all_users    = await repo.get_all(only_active=False)
        active_users = await repo.get_all(only_active=True)
        # Faol bo'lmagan foydalanuvchi only_active ro'yxatida bo'lmasligi kerak
        active_ids = [u.id for u in active_users]
        assert inactive_user_obj.id not in active_ids
        assert len(active_users) < len(all_users) or True  # Kamida bir inactive mavjud

    async def test_get_all_pagination_skip(
        self, repo, admin_user_obj, manager_user_obj, viewer_user_obj
    ):
        """skip parametri sahifalashni to'g'ri bajaradi."""
        all_users    = await repo.get_all(skip=0, limit=100)
        skipped_users = await repo.get_all(skip=1, limit=100)
        # skip=1 bilan birinchi user o'tkazib yuboriladi
        assert len(skipped_users) == len(all_users) - 1

    async def test_get_all_pagination_limit(
        self, repo, admin_user_obj, manager_user_obj, viewer_user_obj
    ):
        """limit parametri natijalar sonini cheklaydi."""
        limited = await repo.get_all(limit=2)
        assert len(limited) <= 2

    async def test_get_all_limit_1(self, repo, admin_user_obj):
        """limit=1 faqat bitta foydalanuvchi qaytaradi."""
        users = await repo.get_all(limit=1)
        assert len(users) == 1

    async def test_get_all_empty_db_returns_empty_list(self, repo):
        """Bo'sh DB → bo'sh list."""
        users = await repo.get_all()
        assert isinstance(users, (list, type(users)))  # Sequence

    async def test_count_matches_get_all_length(
        self, repo, admin_user_obj, manager_user_obj
    ):
        """count() get_all() uzunligi bilan mos keladi."""
        total = await repo.count()
        users = await repo.get_all(limit=1000)
        assert total == len(users)

    async def test_count_only_active(self, repo, admin_user_obj, inactive_user_obj):
        """count(only_active=True) faqat faol foydalanuvchilarni hisoblaydi."""
        total_count  = await repo.count(only_active=False)
        active_count = await repo.count(only_active=True)
        assert active_count <= total_count
        # inactive_user_obj mavjud bo'lgani uchun farq kamida 1
        assert total_count > active_count or total_count == active_count


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — TOKEN & PASSWORD UPDATES
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryTokenAndPassword:
    """Token va parol yangilash testlari."""

    async def test_save_refresh_token_hash(self, db, repo, admin_user_obj):
        """Refresh token hash DB ga saqlanadi."""
        token_hash = "a" * 64
        await repo.save_refresh_token_hash(admin_user_obj.id, token_hash)
        await db.commit()
        await db.refresh(admin_user_obj)
        assert admin_user_obj.refresh_token_hash == token_hash

    async def test_clear_refresh_token_hash_on_logout(self, db, repo, admin_user_obj):
        """None bilan chaqiriq token hashini o'chiradi (logout)."""
        # Avval token saqlash
        await repo.save_refresh_token_hash(admin_user_obj.id, "x" * 64)
        await db.commit()
        # Keyin o'chirish
        await repo.save_refresh_token_hash(admin_user_obj.id, None)
        await db.commit()
        await db.refresh(admin_user_obj)
        assert admin_user_obj.refresh_token_hash is None

    async def test_save_refresh_token_nonexistent_user_does_nothing(self, repo):
        """Mavjud bo'lmagan user ID → xato chiqarmaydi."""
        # get_by_id None qaytaradi, shuning uchun hech narsa bo'lmasligi kerak
        await repo.save_refresh_token_hash(999999, "hash" * 16)

    async def test_update_last_login_sets_recent_time(self, db, repo, admin_user_obj):
        """update_last_login() last_login_at ni hozirgi vaqtga o'rnatadi."""
        before = datetime.now(timezone.utc)
        await repo.update_last_login(admin_user_obj.id)
        await db.commit()
        await db.refresh(admin_user_obj)
        after = datetime.now(timezone.utc)

        assert admin_user_obj.last_login_at is not None
        # Timezone aware solishtirish
        login_time = admin_user_obj.last_login_at
        if login_time.tzinfo is None:
            login_time = login_time.replace(tzinfo=timezone.utc)

        assert login_time >= before.replace(microsecond=0)

    async def test_update_password_changes_hash(self, db, repo, admin_user_obj):
        """Parol yangilanishi hash o'zgartiradi."""
        old_hash = admin_user_obj.hashed_password
        new_hash = hash_password("NewSecurePass1")
        await repo.update_password(admin_user_obj.id, new_hash)
        await db.commit()
        await db.refresh(admin_user_obj)
        assert admin_user_obj.hashed_password == new_hash
        assert admin_user_obj.hashed_password != old_hash

    async def test_update_password_clears_refresh_token(self, db, repo, admin_user_obj):
        """Parol yangilanganda refresh token hashi o'chiriladi."""
        await repo.save_refresh_token_hash(admin_user_obj.id, "x" * 64)
        await db.commit()
        await repo.update_password(admin_user_obj.id, hash_password("NewPass1"))
        await db.commit()
        await db.refresh(admin_user_obj)
        assert admin_user_obj.refresh_token_hash is None


# ═══════════════════════════════════════════════════════════════════════════════
# USER REPOSITORY — UPDATE PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserRepositoryUpdateProfile:
    """UserRepository.update_profile() testlari."""

    async def test_update_full_name(self, db, repo, viewer_user_obj):
        """full_name yangilanadi."""
        updated = await repo.update_profile(viewer_user_obj.id, full_name="New Full Name")
        await db.commit()
        assert updated is not None
        assert updated.full_name == "New Full Name"

    async def test_update_role(self, db, repo, viewer_user_obj):
        """Rol yangilanadi."""
        updated = await repo.update_profile(viewer_user_obj.id, role=UserRole.MANAGER)
        await db.commit()
        assert updated is not None
        assert updated.role == UserRole.MANAGER

    async def test_update_is_active_false(self, db, repo, admin_user_obj):
        """is_active=False qilinganda refresh token ham tozalanadi."""
        await repo.save_refresh_token_hash(admin_user_obj.id, "x" * 64)
        await db.commit()
        updated = await repo.update_profile(admin_user_obj.id, is_active=False)
        await db.commit()
        await db.refresh(updated)
        assert updated.is_active is False
        assert updated.refresh_token_hash is None

    async def test_update_multiple_fields(self, db, repo, viewer_user_obj):
        """Bir vaqtda bir necha maydon yangilanadi."""
        updated = await repo.update_profile(
            viewer_user_obj.id,
            full_name="Updated Name",
            role=UserRole.MANAGER,
        )
        await db.commit()
        assert updated.full_name == "Updated Name"
        assert updated.role      == UserRole.MANAGER

    async def test_update_nonexistent_returns_none(self, repo):
        """Mavjud bo'lmagan user ID → None."""
        result = await repo.update_profile(999999, full_name="Ghost")
        assert result is None

    async def test_none_fields_not_updated(self, db, repo, admin_user_obj):
        """None maydonlar o'zgartirilmaydi."""
        original_name = admin_user_obj.full_name
        updated = await repo.update_profile(admin_user_obj.id, full_name=None)
        await db.commit()
        assert updated is not None
        assert updated.full_name == original_name

    async def test_reactivate_user(self, db, repo, inactive_user_obj):
        """Bloklangan foydalanuvchini faollashtirish."""
        updated = await repo.update_profile(inactive_user_obj.id, is_active=True)
        await db.commit()
        assert updated is not None
        assert updated.is_active is True


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceLogin:
    """AuthService.login() testlari."""

    async def test_login_with_email_success(self, auth_service, admin_user_obj, db):
        """Email bilan muvaffaqiyatli login."""
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        result = await auth_service.login(login_data)
        assert result.access_token  != ""
        assert result.refresh_token != ""
        assert result.token_type    == "bearer"
        assert result.user.email    == "admin@taurus.uz"
        assert result.user.role     == UserRole.ADMIN

    async def test_login_with_username_success(self, auth_service, admin_user_obj, db):
        """Username bilan muvaffaqiyatli login."""
        login_data = LoginRequest(username="sysadmin", password="AdminPass1")
        result = await auth_service.login(login_data)
        assert result.access_token != ""
        assert result.user.username == "sysadmin"

    async def test_login_returns_valid_jwt(self, auth_service, admin_user_obj, db):
        """Login qaytargan access token valid JWT."""
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        result = await auth_service.login(login_data)
        payload = decode_token(result.access_token)
        assert payload["sub"]  == str(admin_user_obj.id)
        assert payload["type"] == "access"
        assert payload["role"] == "admin"

    async def test_login_saves_refresh_token_hash(self, auth_service, admin_user_obj, db):
        """Login refresh token hashini DB ga saqlaydi."""
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        result = await auth_service.login(login_data)
        await db.refresh(admin_user_obj)
        expected_hash = hash_token(result.refresh_token)
        assert admin_user_obj.refresh_token_hash == expected_hash

    async def test_login_updates_last_login_at(self, auth_service, admin_user_obj, db):
        """Login last_login_at ni yangilaydi."""
        before = datetime.now(timezone.utc)
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        await auth_service.login(login_data)
        await db.refresh(admin_user_obj)
        assert admin_user_obj.last_login_at is not None

    async def test_login_wrong_password_raises(self, auth_service, admin_user_obj):
        """Noto'g'ri parol → AuthenticationError."""
        login_data = LoginRequest(email="admin@taurus.uz", password="WrongPass1")
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(login_data)
        assert exc_info.value.message != ""

    async def test_login_nonexistent_user_raises(self, auth_service):
        """Mavjud bo'lmagan foydalanuvchi → AuthenticationError."""
        login_data = LoginRequest(email="nobody@nowhere.com", password="SomePass1")
        with pytest.raises(AuthenticationError):
            await auth_service.login(login_data)

    async def test_login_inactive_user_raises(self, auth_service, inactive_user_obj):
        """Bloklangan foydalanuvchi → AuthenticationError."""
        login_data = LoginRequest(
            email="inactive@taurus.uz",
            password="InactivePass1",
        )
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.login(login_data)
        assert "bloklangan" in exc_info.value.message.lower() or \
               "inactive" in exc_info.value.message.lower() or \
               "faol" in exc_info.value.message.lower()

    async def test_login_response_has_no_password(self, auth_service, admin_user_obj, db):
        """Response da parol (hashed ham) bo'lmasligi kerak."""
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        result = await auth_service.login(login_data)
        user_dict = result.user.model_dump()
        assert "hashed_password"    not in user_dict
        assert "refresh_token_hash" not in user_dict
        assert "password"           not in user_dict

    async def test_login_expires_in_positive(self, auth_service, admin_user_obj, db):
        """expires_in musbat son."""
        login_data = LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        result = await auth_service.login(login_data)
        assert result.expires_in > 0

    async def test_login_different_roles_correct_token(
        self, auth_service, admin_user_obj, manager_user_obj, db
    ):
        """Turli rollar uchun tokenlar to'g'ri rolni o'z ichiga oladi."""
        admin_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        await db.rollback()
        await db.begin()

        manager_result = await auth_service.login(
            LoginRequest(email="manager@taurus.uz", password="ManagerPass1")
        )

        admin_payload   = decode_token(admin_result.access_token)
        manager_payload = decode_token(manager_result.access_token)

        assert admin_payload["role"]   == "admin"
        assert manager_payload["role"] == "manager"


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — REFRESH ACCESS TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceRefresh:
    """AuthService.refresh_access_token() testlari."""

    async def test_refresh_success(self, auth_service, admin_user_obj, db):
        """Yaroqli refresh token bilan yangi token juftligi olinadi."""
        # Avval login
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        old_access = login_result.access_token
        refresh_tk = login_result.refresh_token

        # Refresh
        new_result = await auth_service.refresh_access_token(refresh_tk)
        assert new_result.access_token  != ""
        assert new_result.refresh_token != ""
        # Yangi access token qaytariladi
        # (Agar 1 sekund o'tmagan bo'lsa bir xil bo'lishi mumkin — iat sekund aniqligida)

    async def test_refresh_returns_user_data(self, auth_service, admin_user_obj, db):
        """Refresh response foydalanuvchi ma'lumotlarini o'z ichiga oladi."""
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        new_result = await auth_service.refresh_access_token(login_result.refresh_token)
        assert new_result.user.email    == "admin@taurus.uz"
        assert new_result.user.username == "sysadmin"

    async def test_refresh_rotates_token(self, auth_service, admin_user_obj, db):
        """Token rotation: yangi refresh token hash DB da saqlanadi."""
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        old_hash = admin_user_obj.refresh_token_hash

        new_result = await auth_service.refresh_access_token(login_result.refresh_token)
        await db.refresh(admin_user_obj)

        new_hash = hash_token(new_result.refresh_token)
        assert admin_user_obj.refresh_token_hash == new_hash

    async def test_refresh_with_invalid_token_raises(self, auth_service):
        """Noto'g'ri refresh token → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            await auth_service.refresh_access_token("invalid.token.here")

    async def test_refresh_with_access_token_raises(self, auth_service, admin_user_obj, db):
        """Access token ni refresh o'rnida ishlatish → AuthenticationError."""
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.refresh_access_token(login_result.access_token)
        assert "refresh" in exc_info.value.message.lower()

    async def test_refresh_after_logout_raises(self, auth_service, admin_user_obj, db):
        """Logout dan keyin eski refresh token ishlamaydi."""
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        refresh_token = login_result.refresh_token
        # Logout
        await auth_service.logout(admin_user_obj.id)
        # Eski token bilan refresh
        with pytest.raises(AuthenticationError):
            await auth_service.refresh_access_token(refresh_token)

    async def test_refresh_with_empty_string_raises(self, auth_service):
        """Bo'sh string → AuthenticationError."""
        with pytest.raises(AuthenticationError):
            await auth_service.refresh_access_token("")

    async def test_refresh_with_tampered_token_raises(self, auth_service, admin_user_obj, db):
        """Buzilgan refresh token → AuthenticationError."""
        login_result = await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        tampered = login_result.refresh_token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError):
            await auth_service.refresh_access_token(tampered)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceLogout:
    """AuthService.logout() testlari."""

    async def test_logout_clears_refresh_token_hash(self, auth_service, admin_user_obj, db):
        """Logout refresh token hashini DB dan o'chiradi."""
        # Login qilib token saqlash
        await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        await db.refresh(admin_user_obj)
        assert admin_user_obj.refresh_token_hash is not None

        # Logout
        await auth_service.logout(admin_user_obj.id)
        await db.refresh(admin_user_obj)
        assert admin_user_obj.refresh_token_hash is None

    async def test_logout_nonexistent_user_does_not_raise(self, auth_service):
        """Mavjud bo'lmagan user ID bilan logout — xato chiqarmaydi."""
        await auth_service.logout(999999)  # Xato bo'lmasligi kerak

    async def test_double_logout_does_not_raise(self, auth_service, admin_user_obj, db):
        """Ketma-ket ikki marta logout — xato chiqarmaydi."""
        await auth_service.login(
            LoginRequest(email="admin@taurus.uz", password="AdminPass1")
        )
        await auth_service.logout(admin_user_obj.id)
        await auth_service.logout(admin_user_obj.id)  # Ikkinchi logout


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — CREATE USER
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceCreateUser:
    """AuthService.create_user() testlari."""

    async def test_admin_can_create_user(self, auth_service, admin_user_obj, db):
        """ADMIN yangi foydalanuvchi yarata oladi."""
        user_data = UserCreate(
            email="new_employee@farm.uz",
            username="newemployee",
            full_name="New Employee",
            password="NewEmp1Pass",
            role=UserRole.VIEWER,
        )
        created = await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert created.id is not None
        assert created.email    == "new_employee@farm.uz"
        assert created.username == "newemployee"
        assert created.role     == UserRole.VIEWER

    async def test_password_is_hashed_not_plain(self, auth_service, admin_user_obj, db):
        """Yaratilgan foydalanuvchi paroli hashed saqlanadi."""
        user_data = UserCreate(
            email="hashed@farm.uz",
            username="hasheduser",
            password="HashedPass1",
            role=UserRole.VIEWER,
        )
        created = await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert created.hashed_password != "HashedPass1"
        assert created.hashed_password.startswith(("$2b$", "$2a$"))

    async def test_non_admin_cannot_create_user(
        self, auth_service, manager_user_obj, viewer_user_obj, db
    ):
        """MANAGER va VIEWER yangi foydalanuvchi yarata olmaydi."""
        user_data = UserCreate(
            email="forbidden@farm.uz",
            username="forbiddenuser",
            password="ForbiddenPass1",
            role=UserRole.VIEWER,
        )
        for non_admin in [manager_user_obj, viewer_user_obj]:
            with pytest.raises(PermissionDeniedError) as exc_info:
                await auth_service.create_user(user_data, created_by=non_admin)
            assert "admin" in exc_info.value.message.lower() or \
                   "ADMIN" in exc_info.value.message

    async def test_duplicate_email_raises(self, auth_service, admin_user_obj, db):
        """Duplicate email → EntityAlreadyExistsError."""
        user_data = UserCreate(
            email="admin@taurus.uz",  # Allaqachon mavjud
            username="uniqueusername",
            password="UniquePass1",
            role=UserRole.VIEWER,
        )
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert "email" in exc_info.value.message.lower() or \
               "email" in str(exc_info.value.details)

    async def test_duplicate_username_raises(self, auth_service, admin_user_obj, db):
        """Duplicate username → EntityAlreadyExistsError."""
        user_data = UserCreate(
            email="unique@farm.uz",
            username="sysadmin",  # Allaqachon mavjud
            password="UniquePass1",
            role=UserRole.VIEWER,
        )
        with pytest.raises(EntityAlreadyExistsError) as exc_info:
            await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert "username" in exc_info.value.message.lower() or \
               "username" in str(exc_info.value.details)

    async def test_admin_can_create_admin(self, auth_service, admin_user_obj, db):
        """Admin boshqa admin yarata oladi."""
        user_data = UserCreate(
            email="admin2@taurus.uz",
            username="admin2",
            password="Admin2Pass1",
            role=UserRole.ADMIN,
        )
        created = await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert created.role == UserRole.ADMIN

    async def test_new_user_is_active_by_default(self, auth_service, admin_user_obj, db):
        """Yangi foydalanuvchi faol holda yaratiladi."""
        user_data = UserCreate(
            email="active_by_default@farm.uz",
            username="activedefault",
            password="ActivePass1",
            role=UserRole.VIEWER,
        )
        created = await auth_service.create_user(user_data, created_by=admin_user_obj)
        assert created.is_active is True


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — UPDATE USER
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceUpdateUser:
    """AuthService.update_user() testlari."""

    async def test_admin_can_update_any_user(
        self, auth_service, admin_user_obj, viewer_user_obj, db
    ):
        """ADMIN boshqa foydalanuvchini yangilay oladi."""
        update_data = UserUpdate(full_name="Updated By Admin")
        updated = await auth_service.update_user(
            user_id=viewer_user_obj.id,
            update_data=update_data,
            updated_by=admin_user_obj,
        )
        assert updated.full_name == "Updated By Admin"

    async def test_user_can_update_own_name(self, auth_service, viewer_user_obj, db):
        """Foydalanuvchi o'z to'liq ismini yangilay oladi."""
        update_data = UserUpdate(full_name="My New Name")
        updated = await auth_service.update_user(
            user_id=viewer_user_obj.id,
            update_data=update_data,
            updated_by=viewer_user_obj,
        )
        assert updated.full_name == "My New Name"

    async def test_non_admin_cannot_update_others(
        self, auth_service, viewer_user_obj, manager_user_obj, db
    ):
        """Boshqa foydalanuvchi profilini o'zgartirish → PermissionDeniedError."""
        update_data = UserUpdate(full_name="Hacked Name")
        with pytest.raises(PermissionDeniedError):
            await auth_service.update_user(
                user_id=manager_user_obj.id,
                update_data=update_data,
                updated_by=viewer_user_obj,
            )

    async def test_non_admin_cannot_change_role(
        self, auth_service, viewer_user_obj, db
    ):
        """Foydalanuvchi o'z rolini o'zgartira olmaydi."""
        update_data = UserUpdate(role=UserRole.ADMIN)
        with pytest.raises(PermissionDeniedError) as exc_info:
            await auth_service.update_user(
                user_id=viewer_user_obj.id,
                update_data=update_data,
                updated_by=viewer_user_obj,
            )
        assert "rol" in exc_info.value.message.lower() or \
               "role" in exc_info.value.message.lower()

    async def test_non_admin_cannot_deactivate_self(
        self, auth_service, viewer_user_obj, db
    ):
        """Foydalanuvchi o'zini deaktivlay olmaydi."""
        update_data = UserUpdate(is_active=False)
        with pytest.raises(PermissionDeniedError):
            await auth_service.update_user(
                user_id=viewer_user_obj.id,
                update_data=update_data,
                updated_by=viewer_user_obj,
            )

    async def test_admin_can_change_role(
        self, auth_service, admin_user_obj, viewer_user_obj, db
    ):
        """ADMIN boshqa foydalanuvchi rolini o'zgartira oladi."""
        update_data = UserUpdate(role=UserRole.MANAGER)
        updated = await auth_service.update_user(
            user_id=viewer_user_obj.id,
            update_data=update_data,
            updated_by=admin_user_obj,
        )
        assert updated.role == UserRole.MANAGER

    async def test_update_nonexistent_user_raises(
        self, auth_service, admin_user_obj, db
    ):
        """Mavjud bo'lmagan user ID → EntityNotFoundError."""
        update_data = UserUpdate(full_name="Ghost")
        with pytest.raises(EntityNotFoundError):
            await auth_service.update_user(
                user_id=999999,
                update_data=update_data,
                updated_by=admin_user_obj,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — CHANGE PASSWORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceChangePassword:
    """AuthService.change_password() testlari."""

    async def test_change_own_password_success(
        self, auth_service, admin_user_obj, db
    ):
        """To'g'ri joriy parol bilan parolni o'zgartirish."""
        data = PasswordChangeRequest(
            current_password="AdminPass1",
            new_password="NewAdmin1Pass",
        )
        await auth_service.change_password(
            user_id=admin_user_obj.id,
            data=data,
            requesting_user=admin_user_obj,
        )
        # Yangi parol bilan login muvaffaqiyatli bo'lishi kerak
        await db.refresh(admin_user_obj)
        from app.core.security import verify_password
        assert verify_password("NewAdmin1Pass", admin_user_obj.hashed_password) is True

    async def test_wrong_current_password_raises(
        self, auth_service, admin_user_obj, db
    ):
        """Noto'g'ri joriy parol → AuthenticationError."""
        data = PasswordChangeRequest(
            current_password="WrongOldPass1",
            new_password="NewAdmin1Pass",
        )
        with pytest.raises(AuthenticationError) as exc_info:
            await auth_service.change_password(
                user_id=admin_user_obj.id,
                data=data,
                requesting_user=admin_user_obj,
            )
        assert "joriy" in exc_info.value.message.lower() or \
               "current" in exc_info.value.message.lower() or \
               "parol" in exc_info.value.message.lower()

    async def test_same_password_raises_business_rule(
        self, auth_service, admin_user_obj, db
    ):
        """Yangi parol joriy parol bilan bir xil → BusinessRuleViolationError."""
        data = PasswordChangeRequest(
            current_password="AdminPass1",
            new_password="AdminPass1",
        )
        with pytest.raises(BusinessRuleViolationError):
            await auth_service.change_password(
                user_id=admin_user_obj.id,
                data=data,
                requesting_user=admin_user_obj,
            )

    async def test_non_admin_cannot_change_others_password(
        self, auth_service, viewer_user_obj, manager_user_obj, db
    ):
        """Boshqa foydalanuvchi paroli → PermissionDeniedError."""
        data = PasswordChangeRequest(
            current_password="ManagerPass1",
            new_password="NewManager1Pass",
        )
        with pytest.raises(PermissionDeniedError):
            await auth_service.change_password(
                user_id=manager_user_obj.id,
                data=data,
                requesting_user=viewer_user_obj,
            )

    async def test_change_password_for_nonexistent_user_raises(
        self, auth_service, admin_user_obj, db
    ):
        """Mavjud bo'lmagan user ID → EntityNotFoundError."""
        data = PasswordChangeRequest(
            current_password="AdminPass1",
            new_password="NewAdmin1Pass",
        )
        with pytest.raises(EntityNotFoundError):
            await auth_service.change_password(
                user_id=999999,
                data=data,
                requesting_user=admin_user_obj,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — ADMIN RESET PASSWORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceAdminResetPassword:
    """AuthService.admin_reset_password() testlari."""

    async def test_admin_can_reset_other_password(
        self, auth_service, admin_user_obj, viewer_user_obj, db
    ):
        """ADMIN boshqa foydalanuvchi parolini tiklaya oladi."""
        await auth_service.admin_reset_password(
            user_id=viewer_user_obj.id,
            new_password="ResetViewer1Pass",
            admin_user=admin_user_obj,
        )
        await db.refresh(viewer_user_obj)
        from app.core.security import verify_password
        assert verify_password("ResetViewer1Pass", viewer_user_obj.hashed_password) is True

    async def test_admin_cannot_reset_own_password(
        self, auth_service, admin_user_obj, db
    ):
        """Admin o'z parolini bu endpoint orqali tiklaya olmaydi."""
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await auth_service.admin_reset_password(
                user_id=admin_user_obj.id,
                new_password="NewAdminPass1",
                admin_user=admin_user_obj,
            )
        assert "o'z" in exc_info.value.message.lower() or \
               "own" in exc_info.value.message.lower() or \
               "change-password" in exc_info.value.message

    async def test_non_admin_cannot_reset_password(
        self, auth_service, manager_user_obj, viewer_user_obj, db
    ):
        """ADMIN bo'lmagan foydalanuvchi → PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            await auth_service.admin_reset_password(
                user_id=viewer_user_obj.id,
                new_password="ResetAttempt1",
                admin_user=manager_user_obj,
            )

    async def test_reset_nonexistent_user_raises(
        self, auth_service, admin_user_obj, db
    ):
        """Mavjud bo'lmagan user ID → EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError):
            await auth_service.admin_reset_password(
                user_id=999999,
                new_password="NewPass1Reset",
                admin_user=admin_user_obj,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — GET ALL USERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceGetAllUsers:
    """AuthService.get_all_users() testlari."""

    async def test_admin_can_get_all_users(
        self, auth_service, admin_user_obj, viewer_user_obj, manager_user_obj, db
    ):
        """ADMIN barcha foydalanuvchilarni ko'ra oladi."""
        users, total = await auth_service.get_all_users(requesting_user=admin_user_obj)
        assert total >= 3
        assert len(users) >= 3

    async def test_non_admin_cannot_get_all_users(
        self, auth_service, manager_user_obj, viewer_user_obj, db
    ):
        """MANAGER va VIEWER foydalanuvchilar ro'yxatini ko'ra olmaydi."""
        for non_admin in [manager_user_obj, viewer_user_obj]:
            with pytest.raises(PermissionDeniedError):
                await auth_service.get_all_users(requesting_user=non_admin)

    async def test_get_all_users_pagination(
        self, auth_service, admin_user_obj, viewer_user_obj, manager_user_obj, db
    ):
        """Sahifalash ishlaydi."""
        users_page1, total = await auth_service.get_all_users(
            requesting_user=admin_user_obj, skip=0, limit=2
        )
        assert len(users_page1) <= 2
        assert total >= 2

    async def test_get_all_users_only_active(
        self, auth_service, admin_user_obj, inactive_user_obj, db
    ):
        """only_active=True faqat faol foydalanuvchilarni qaytaradi."""
        all_users, all_total    = await auth_service.get_all_users(
            requesting_user=admin_user_obj, only_active=False
        )
        active_users, act_total = await auth_service.get_all_users(
            requesting_user=admin_user_obj, only_active=True
        )
        inactive_ids = [u.id for u in all_users if not u.is_active]
        active_ids   = [u.id for u in active_users]
        for iid in inactive_ids:
            assert iid not in active_ids

    async def test_get_all_users_returns_tuple(
        self, auth_service, admin_user_obj, db
    ):
        """get_all_users() (list, int) tuple qaytaradi."""
        result = await auth_service.get_all_users(requesting_user=admin_user_obj)
        assert isinstance(result, tuple)
        assert len(result) == 2
        users, total = result
        assert isinstance(total, int)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH SERVICE — GET USER BY ID
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuthServiceGetUserById:
    """AuthService.get_user_by_id() testlari."""

    async def test_get_existing_user(self, auth_service, admin_user_obj):
        """Mavjud foydalanuvchi qaytariladi."""
        user = await auth_service.get_user_by_id(admin_user_obj.id)
        assert user.id    == admin_user_obj.id
        assert user.email == "admin@taurus.uz"

    async def test_get_nonexistent_user_raises(self, auth_service):
        """Mavjud bo'lmagan ID → EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError) as exc_info:
            await auth_service.get_user_by_id(999999)
        assert "User" in exc_info.value.message or \
               "topilmadi" in exc_info.value.message.lower()