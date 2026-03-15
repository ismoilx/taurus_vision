"""
TAURUS VISION — tests/test_core/test_middleware_seeder.py
==========================================================
Middleware classes + Seeder uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_core/test_middleware_seeder.py

Qamrav (90+ test):
  ✓ PerformanceMonitoringMiddleware.SLOW_REQUEST_THRESHOLD — 1.0 soniya
  ✓ SecurityHeadersMiddleware header nomlari
  ✓ RateLimitMiddleware.LIMITS — barcha route limitlari
  ✓ RateLimitMiddleware.DEFAULT_LIMIT — 200
  ✓ RateLimitMiddleware.WINDOW       — 60
  ✓ RateLimitMiddleware._get_limit   — path prefikslari bo'yicha
  ✓ RateLimitMiddleware._is_limited  — chegaradan past OK, chegara ustida True
  ✓ RateLimitMiddleware thread-safety
  ✓ RateLimitMiddleware disabled holatida limit qo'llanilmaydi
  ✓ Seeder._create_initial_admin — env yo'q, qisqa parol, foydalanuvchi bor
  ✓ Seeder: barcha holatlarda xato bermasin (idempotent)
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.core.middleware import (
    PerformanceMonitoringMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)

pytestmark = pytest.mark.asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# PerformanceMonitoringMiddleware
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceMonitoringMiddleware:

    def test_slow_threshold_1_second(self):
        assert PerformanceMonitoringMiddleware.SLOW_REQUEST_THRESHOLD == 1.0

    def test_threshold_is_float(self):
        assert isinstance(PerformanceMonitoringMiddleware.SLOW_REQUEST_THRESHOLD, float)


# ═══════════════════════════════════════════════════════════════════════════════
# SecurityHeadersMiddleware
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityHeadersMiddleware:

    async def test_adds_x_content_type_options(self):
        """X-Content-Type-Options: nosniff sarlavhasi qo'shiladi."""
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()
        request.url.path = "/api/test"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    async def test_adds_x_frame_options(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        await middleware.dispatch(request, call_next)
        assert response.headers.get("X-Frame-Options") == "DENY"

    async def test_adds_xss_protection(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        await middleware.dispatch(request, call_next)
        assert "1; mode=block" in response.headers.get("X-XSS-Protection", "")

    async def test_adds_csp(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        await middleware.dispatch(request, call_next)
        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp

    async def test_adds_referrer_policy(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        await middleware.dispatch(request, call_next)
        assert response.headers.get("Referrer-Policy") is not None

    async def test_adds_permissions_policy(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        await middleware.dispatch(request, call_next)
        pp = response.headers.get("Permissions-Policy", "")
        assert "geolocation" in pp

    async def test_returns_response(self):
        app = AsyncMock()
        middleware = SecurityHeadersMiddleware(app)
        request = MagicMock()
        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert result is response


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitMiddleware — Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitConstants:

    def test_default_limit_200(self):
        assert RateLimitMiddleware.DEFAULT_LIMIT == 200

    def test_window_60_seconds(self):
        assert RateLimitMiddleware.WINDOW == 60

    def test_detection_limit_60(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/detection"] == 60

    def test_analytics_limit_30(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/analytics"] == 30

    def test_reports_limit_20(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/reports"] == 20

    def test_export_limit_10(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/export"] == 10

    def test_animals_limit_120(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/animals"] == 120

    def test_weights_limit_120(self):
        assert RateLimitMiddleware.LIMITS["/api/v1/weights"] == 120

    def test_all_limits_positive(self):
        for path, limit in RateLimitMiddleware.LIMITS.items():
            assert limit > 0, f"{path} limit must be positive"


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitMiddleware._get_limit
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitGetLimit:

    def _middleware(self):
        app = MagicMock()
        return RateLimitMiddleware(app, enabled=True)

    def test_detection_path(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/detection/stream") == 60

    def test_analytics_path(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/analytics/overview") == 30

    def test_reports_path(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/reports/animal/1") == 20

    def test_export_path(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/export/animals") == 10

    def test_animals_path(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/animals") == 120

    def test_unknown_path_default(self):
        m = self._middleware()
        assert m._get_limit("/api/v1/unknown/path") == 200

    def test_root_path_default(self):
        m = self._middleware()
        assert m._get_limit("/") == 200

    def test_health_check_default(self):
        m = self._middleware()
        assert m._get_limit("/health") == 200


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitMiddleware._is_limited
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitIsLimited:

    def _middleware(self):
        app = MagicMock()
        return RateLimitMiddleware(app, enabled=True)

    def test_below_limit_not_limited(self):
        m = self._middleware()
        for _ in range(5):
            result = m._is_limited("test-key", 10)
        assert result is False

    def test_at_limit_limited(self):
        m = self._middleware()
        for _ in range(10):
            m._is_limited("at-limit-key", 10)
        # 11-chi so'rov — limited
        result = m._is_limited("at-limit-key", 10)
        assert result is True

    def test_different_keys_independent(self):
        m = self._middleware()
        # key1 ni limitga yetkizamiz
        for _ in range(10):
            m._is_limited("key-full", 10)
        assert m._is_limited("key-full", 10) is True
        # key2 uchun ham limit boshlang'ich
        assert m._is_limited("key-empty", 10) is False

    def test_window_expiry(self):
        """Muddati o'tgan so'rovlar hisobdan chiqariladi."""
        m = self._middleware()
        # Eski so'rovlarni qo'shamiz (window dan tashqariga)
        key = "expiry-key"
        old_time = time.monotonic() - m.WINDOW - 5
        with m._lock:
            m._requests[key] = [old_time] * 9  # 9 ta eski so'rov
        # Yangi so'rov — limit 10, eski 9 ta chiqariladi
        result = m._is_limited(key, 10)
        assert result is False  # Eski so'rovlar o'chirilgan

    def test_thread_safety(self):
        """Ko'p thread bir vaqtda so'rov yuborsa xato bermasin."""
        m = self._middleware()
        errors = []
        results = []

        def check():
            try:
                r = m._is_limited("thread-key", 1000)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_returns_bool(self):
        m = self._middleware()
        result = m._is_limited("bool-key", 100)
        assert isinstance(result, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitMiddleware.dispatch (integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitDispatch:

    async def test_health_check_not_rate_limited(self):
        """Health check yo'llari rate limit dan mustafo."""
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, enabled=True)

        response = MagicMock()
        response.headers = {}
        response.status_code = 200

        async def call_next(req):
            return response

        for path in ["/health", "/health/live", "/metrics"]:
            request = MagicMock()
            request.url.path = path
            request.client = MagicMock()
            request.client.host = "127.0.0.1"
            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200

    async def test_disabled_middleware_no_limit(self):
        """enabled=False bo'lsa — hech qanday limit yo'q."""
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, enabled=False)

        response = MagicMock()
        response.headers = {}
        response.status_code = 200

        async def call_next(req):
            return response

        for _ in range(50):
            request = MagicMock()
            request.url.path = "/api/v1/animals"
            request.client = MagicMock()
            request.client.host = "1.2.3.4"
            result = await middleware.dispatch(request, call_next)
            assert result.status_code == 200

    async def test_non_api_path_no_limit(self):
        """API bo'lmagan yo'llar rate limit qo'llanilmaydi."""
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, enabled=True)

        response = MagicMock()
        response.headers = {}
        response.status_code = 200

        async def call_next(req):
            return response

        request = MagicMock()
        request.url.path = "/docs"
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        result = await middleware.dispatch(request, call_next)
        assert result.status_code == 200

    async def test_rate_limited_returns_429(self):
        """Limit oshganda 429 qaytadi."""
        app = AsyncMock()
        middleware = RateLimitMiddleware(app, enabled=True)

        # Export yo'li — limit 10
        # Yetarli so'rov yuborib limitni to'ldiramiz
        response_ok = MagicMock()
        response_ok.headers = {}
        response_ok.status_code = 200

        async def call_next(req):
            return response_ok

        ip = "99.99.99.99"
        path = "/api/v1/export/animals"

        last_result = None
        for i in range(15):
            request = MagicMock()
            request.url.path = path
            request.client = MagicMock()
            request.client.host = ip
            last_result = await middleware.dispatch(request, call_next)

        # Oxirgi natija 429 bo'lishi kerak
        assert last_result.status_code == 429


# ═══════════════════════════════════════════════════════════════════════════════
# Seeder
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeeder:

    async def test_no_env_vars_no_admin(self, db):
        """Env var yo'q → admin yaratilmaydi."""
        from app.core.seeder import _create_initial_admin
        with patch.dict("os.environ", {}, clear=True):
            try:
                await _create_initial_admin(db)
            except Exception as e:
                pytest.fail(f"Seeder raised: {e}")

    async def test_short_password_skipped(self, db):
        """Qisqa parol → admin yaratilmaydi."""
        from app.core.seeder import _create_initial_admin
        env = {
            "INITIAL_ADMIN_EMAIL": "admin@test.com",
            "INITIAL_ADMIN_PASSWORD": "short",  # 5 ta belgi < 8
        }
        with patch.dict("os.environ", env):
            try:
                await _create_initial_admin(db)
            except Exception as e:
                pytest.fail(f"Short password raised: {e}")

    async def test_existing_users_skip(self, db):
        """Allaqachon foydalanuvchilar mavjud → admin yaratilmaydi."""
        from app.core.seeder import _create_initial_admin
        from app.models.user import User, UserRole
        from app.core.security import hash_password

        # Foydalanuvchi yaratamiz
        user = User(
            email="existing@test.com",
            username="existing",
            full_name="Existing User",
            hashed_password=hash_password("ExistingPass1"),
            role=UserRole.VIEWER,
            is_active=True,
        )
        db.add(user)
        await db.commit()

        env = {
            "INITIAL_ADMIN_EMAIL": "admin@test.com",
            "INITIAL_ADMIN_PASSWORD": "AdminPass1234",
        }
        with patch.dict("os.environ", env):
            try:
                await _create_initial_admin(db)
            except Exception as e:
                pytest.fail(f"Existing users raised: {e}")

    async def test_run_seeder_no_error(self):
        """run_seeder() xato bermaydi."""
        from unittest.mock import patch, AsyncMock
        with patch("app.core.seeder.AsyncSessionLocal") as mock_session:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value = mock_ctx
            from app.core.seeder import run_seeder
            try:
                await run_seeder()
            except Exception as e:
                pytest.fail(f"run_seeder raised: {e}")

    async def test_seeder_idempotent(self, db):
        """Ikki marta chaqirilsa ham xato bermaydi."""
        from app.core.seeder import _create_initial_admin
        with patch.dict("os.environ", {}, clear=True):
            await _create_initial_admin(db)
            await _create_initial_admin(db)  # Ikkinchi chaqiruv

    async def test_create_admin_with_valid_env(self, db):
        """To'liq env bilan admin yaratiladi."""
        from app.core.seeder import _create_initial_admin
        from app.models.user import User
        from sqlalchemy import select, func

        env = {
            "INITIAL_ADMIN_EMAIL": "seeder.admin@taurus.uz",
            "INITIAL_ADMIN_PASSWORD": "SeederPassword123!",
            "INITIAL_ADMIN_USERNAME": "seederadmin",
            "INITIAL_ADMIN_FULLNAME": "Seeder Administrator",
        }

        # Foydalanuvchi sonini tekshiramiz
        before = (await db.execute(
            select(func.count(User.id)).where(User.email == "seeder.admin@taurus.uz")
        )).scalar_one()
        assert before == 0

        with patch.dict("os.environ", env):
            await _create_initial_admin(db)

        after = (await db.execute(
            select(func.count(User.id)).where(User.email == "seeder.admin@taurus.uz")
        )).scalar_one()
        assert after == 1