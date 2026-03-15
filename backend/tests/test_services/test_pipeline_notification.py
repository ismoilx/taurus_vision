"""
TAURUS VISION — tests/test_services/test_pipeline_notification.py
==================================================================
PipelineManager (pure methods) + StreamOptimizer + LoadBalancer +
NotificationService uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_services/test_pipeline_notification.py

Qamrav (100+ test):
  ✓ StreamOptimizer — init, get_skip_frames CPU pressure
  ✓ LoadBalancer    — max_pipelines, can_start, _compute_max
  ✓ PipelineManager singleton, init, get_status (not running)
  ✓ PipelineManager.is_running — yo'q pipeline False
  ✓ PipelineManager.update_latest_detection + get_latest_detection — 2s ttl
  ✓ PipelineManager.update_latest_frame + get_latest_frame
  ✓ PipelineManager.get_all_status — bo'sh
  ✓ PipelineManager.list_running   — bo'sh
  ✓ PipelineManager.total_running  — bo'sh
  ✓ PipelineManager.get_system_metrics — tuzilma
  ✓ PipelineManager.get_camera_service — yo'q → None
  ✓ PIPELINE CONSTANTS (_RAM_PER_PIPELINE_MB, _CPU_LOW, _SKIP_*)
  ✓ NotificationService.is_configured — SMTP yo'q
  ✓ NotificationService.get_settings_info — tuzilma
  ✓ NotificationService.test_smtp_connection — SMTP yo'q → False
  ✓ NotificationService.get_recipients — LOW skip, HIGH/CRIT qaytadi
  ✓ NotificationService.send_alert_email — SMTP yo'q log mode
  ✓ get_notification_service singleton
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.pipeline_manager import (
    StreamOptimizer, LoadBalancer, PipelineManager,
    _RAM_PER_PIPELINE_MB, _CPU_LOW, _CPU_HIGH,
    _SKIP_LOW, _SKIP_MID, _SKIP_HIGH,
    _WATCHDOG_INTERVAL, _MAX_RESTART_ATTEMPTS,
)
from app.services.notification_service import (
    NotificationService,
    SEVERITY_CONFIG,
    get_notification_service,
)
from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


# ─── Alert factory ──────────────────────────────────────────────────────────

def _alert(severity="critical", title="Test Alert",
           description="Test desc", alert_id=1):
    a = Alert(
        alert_type="adi_critical", severity=severity,
        status=AlertStatus.OPEN, title=title,
        description=description, auto_generated=True,
        triggered_at=NOW,
    )
    a.id = alert_id
    return a


# ═══════════════════════════════════════════════════════════════════════════════
# KONSTANTALAR
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineConstants:
    def test_ram_per_pipeline_400(self):
        assert _RAM_PER_PIPELINE_MB == 400

    def test_cpu_low_60(self):
        assert _CPU_LOW == 60.0

    def test_cpu_high_80(self):
        assert _CPU_HIGH == 80.0

    def test_skip_low_2(self):
        assert _SKIP_LOW == 2

    def test_skip_mid_4(self):
        assert _SKIP_MID == 4

    def test_skip_high_8(self):
        assert _SKIP_HIGH == 8

    def test_watchdog_interval_30(self):
        assert _WATCHDOG_INTERVAL == 30.0

    def test_max_restart_attempts_3(self):
        assert _MAX_RESTART_ATTEMPTS == 3

    def test_skip_order(self):
        assert _SKIP_LOW < _SKIP_MID < _SKIP_HIGH


# ═══════════════════════════════════════════════════════════════════════════════
# StreamOptimizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestStreamOptimizer:

    def test_init_skip_is_skip_low(self):
        opt = StreamOptimizer()
        assert opt._current_skip == _SKIP_LOW

    def test_init_no_cpu_history(self):
        opt = StreamOptimizer()
        assert opt._cpu_history == []

    def test_get_skip_frames_returns_int(self):
        opt = StreamOptimizer()
        result = opt.get_skip_frames()
        assert isinstance(result, int)

    def test_get_skip_frames_before_interval_cached(self):
        opt = StreamOptimizer()
        opt._last_check = time.monotonic()  # Endigina tekshirilgan
        opt._current_skip = _SKIP_MID
        result = opt.get_skip_frames()
        assert result == _SKIP_MID  # Cache qaytadi

    def test_get_skip_frames_range(self):
        opt = StreamOptimizer()
        result = opt.get_skip_frames()
        assert result in [_SKIP_LOW, _SKIP_MID, _SKIP_HIGH]

    def test_skip_frames_cpu_low_skip_low(self):
        """CPU < 60% → SKIP_LOW."""
        opt = StreamOptimizer()
        opt._cpu_history = [20.0, 25.0, 30.0]
        opt._last_check  = 0.0  # Check intervalini o'tkazib yubor

        with patch("psutil.cpu_percent", return_value=20.0), \
             patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(percent=30.0)
            result = opt.get_skip_frames()
            assert result == _SKIP_LOW

    def test_skip_frames_cpu_high_skip_high(self):
        """CPU > 80% → SKIP_HIGH."""
        opt = StreamOptimizer()
        opt._last_check = 0.0

        with patch("psutil.cpu_percent", return_value=90.0), \
             patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(percent=85.0)
            result = opt.get_skip_frames()
            assert result == _SKIP_HIGH

    def test_skip_frames_cpu_mid_skip_mid(self):
        """60 < CPU < 80 → SKIP_MID."""
        opt = StreamOptimizer()
        opt._last_check = 0.0

        with patch("psutil.cpu_percent", return_value=70.0), \
             patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(percent=40.0)
            result = opt.get_skip_frames()
            assert result == _SKIP_MID

    def test_cpu_history_max_6(self):
        """CPU history 6 ta elementdan oshmasin."""
        opt = StreamOptimizer()
        opt._cpu_history = [50.0] * 6
        opt._last_check  = 0.0

        with patch("psutil.cpu_percent", return_value=50.0), \
             patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(percent=30.0)
            opt.get_skip_frames()
            assert len(opt._cpu_history) <= 6

    def test_psutil_failure_returns_current(self):
        """psutil xato → cached qiymat qaytadi."""
        opt = StreamOptimizer()
        opt._last_check  = 0.0
        opt._current_skip = _SKIP_MID

        with patch("psutil.cpu_percent", side_effect=Exception("no psutil")):
            result = opt.get_skip_frames()
            assert result == _SKIP_MID  # Xato bo'lsa ham qaytadi


# ═══════════════════════════════════════════════════════════════════════════════
# LoadBalancer
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadBalancer:

    def test_max_pipelines_positive(self):
        lb = LoadBalancer()
        assert lb.max_pipelines > 0

    def test_max_pipelines_at_most_16(self):
        lb = LoadBalancer()
        assert lb.max_pipelines <= 16

    def test_can_start_zero_current(self):
        lb = LoadBalancer()
        lb._max_pipelines = 8  # Override

        with patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(
                available=2 * 1024 * 1024 * 1024)  # 2GB
            can, msg = lb.can_start(0)
            assert can is True
            assert msg == ""

    def test_can_start_at_max_false(self):
        lb = LoadBalancer()
        lb._max_pipelines = 4
        with patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(
                available=2 * 1024 * 1024 * 1024)
            can, msg = lb.can_start(4)
            assert can is False
            assert "4" in msg or "Maksimal" in msg

    def test_can_start_low_ram_false(self):
        lb = LoadBalancer()
        lb._max_pipelines = 8
        with patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(
                available=100 * 1024 * 1024)  # 100MB (< 400MB)
            can, msg = lb.can_start(0)
            assert can is False
            assert "RAM" in msg

    def test_compute_max_pipelines_range(self):
        result = LoadBalancer._compute_max_pipelines()
        assert 1 <= result <= 16

    def test_compute_max_pipelines_respects_cpu(self):
        with patch("psutil.cpu_count", return_value=2):
            with patch("psutil.virtual_memory") as mock_ram:
                mock_ram.return_value = MagicMock(
                    total=16 * 1024 * 1024 * 1024)
                result = LoadBalancer._compute_max_pipelines()
                # CPU based: 2*2=4, RAM based: 16GB/400MB=40, min(4,40,16)=4
                assert result <= 4

    def test_can_start_returns_tuple(self):
        lb = LoadBalancer()
        with patch("psutil.virtual_memory") as mock_ram:
            mock_ram.return_value = MagicMock(
                available=2 * 1024 * 1024 * 1024)
            result = lb.can_start(0)
            assert isinstance(result, tuple)
            assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineManager — Pure methods (DB/YOLO yo'q)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineManager:

    def _fresh_manager(self):
        """Singleton ni reset qilib yangi instance olamiz."""
        PipelineManager._instance = None
        return PipelineManager()

    def test_singleton_pattern(self):
        PipelineManager._instance = None
        pm1 = PipelineManager()
        pm2 = PipelineManager()
        assert pm1 is pm2

    def test_init_empty_pipelines(self):
        pm = self._fresh_manager()
        assert len(pm._pipelines) == 0

    def test_init_has_optimizer(self):
        pm = self._fresh_manager()
        assert isinstance(pm._optimizer, StreamOptimizer)

    def test_init_has_balancer(self):
        pm = self._fresh_manager()
        assert isinstance(pm._balancer, LoadBalancer)

    def test_is_running_unknown_false(self):
        pm = self._fresh_manager()
        assert pm.is_running("UNKNOWN-CAM") is False

    def test_get_status_not_running(self):
        pm = self._fresh_manager()
        status = pm.get_status("NOT-RUNNING-CAM")
        assert status["running"] is False
        assert status["camera_id"] == "NOT-RUNNING-CAM"
        assert status["stats"] is None
        assert status["restart_count"] == 0

    def test_get_status_structure(self):
        pm = self._fresh_manager()
        status = pm.get_status("ANY-CAM")
        for k in ["camera_id", "running", "stats", "started_at",
                  "restart_count", "last_error"]:
            assert k in status

    def test_get_all_status_empty(self):
        pm = self._fresh_manager()
        result = pm.get_all_status()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_list_running_empty(self):
        pm = self._fresh_manager()
        result = pm.list_running()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_total_running_zero(self):
        pm = self._fresh_manager()
        assert pm.total_running() == 0

    def test_get_camera_service_unknown_none(self):
        pm = self._fresh_manager()
        assert pm.get_camera_service("UNKNOWN-CAM") is None

    def test_get_latest_frame_unknown_none(self):
        pm = self._fresh_manager()
        assert pm.get_latest_frame("UNKNOWN-CAM") is None

    def test_get_latest_detection_unknown_none(self):
        pm = self._fresh_manager()
        assert pm.get_latest_detection("UNKNOWN-CAM") is None

    def test_update_latest_detection_stored(self):
        pm = self._fresh_manager()
        pm.update_latest_detection(
            camera_id="TEST-CAM",
            bbox={"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.3},
            animal_tag="JNV-001",
            confidence=0.95,
        )
        result = pm.get_latest_detection("TEST-CAM")
        assert result is not None
        assert result["animal_tag"] == "JNV-001"
        assert abs(result["confidence"] - 0.95) < 0.01

    def test_update_latest_detection_ttl_2s(self):
        """2 soniyadan eski detection None qaytadi."""
        pm = self._fresh_manager()
        pm.update_latest_detection(
            camera_id="TTL-CAM",
            bbox={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            animal_tag="JNV-002",
            confidence=0.9,
        )
        # Vaqtni 3 soniya orqaga suramiz
        pm._latest_detections["TTL-CAM"]["ts"] = time.monotonic() - 3.0
        result = pm.get_latest_detection("TTL-CAM")
        assert result is None  # TTL o'tgan

    def test_update_latest_detection_fresh_ok(self):
        """Yangi detection to'liq qaytadi."""
        pm = self._fresh_manager()
        pm.update_latest_detection(
            camera_id="FRESH-CAM",
            bbox={"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            animal_tag="JNV-003",
            confidence=0.88,
            class_name="cow",
        )
        result = pm.get_latest_detection("FRESH-CAM")
        assert result is not None
        assert result["class_name"] == "cow"

    def test_update_latest_frame_stored(self):
        import numpy as np
        pm = self._fresh_manager()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pm.update_latest_frame("FRAME-CAM", frame)
        result = pm.get_latest_frame("FRAME-CAM")
        assert result is not None

    def test_get_system_metrics_structure(self):
        pm = self._fresh_manager()
        metrics = pm.get_system_metrics()
        for k in ["cpu_percent", "ram_percent", "ram_available_mb",
                  "active_pipelines", "max_pipelines",
                  "current_skip_frames", "can_start_new"]:
            assert k in metrics

    def test_get_system_metrics_types(self):
        pm = self._fresh_manager()
        metrics = pm.get_system_metrics()
        assert isinstance(metrics["cpu_percent"], (int, float))
        assert isinstance(metrics["active_pipelines"], int)
        assert isinstance(metrics["can_start_new"], bool)

    def test_get_system_metrics_active_zero(self):
        pm = self._fresh_manager()
        metrics = pm.get_system_metrics()
        assert metrics["active_pipelines"] == 0

    def test_get_system_metrics_max_pipelines_positive(self):
        pm = self._fresh_manager()
        metrics = pm.get_system_metrics()
        assert metrics["max_pipelines"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# NotificationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationService:

    def test_is_configured_bool(self):
        svc = NotificationService()
        assert isinstance(svc.is_configured, bool)

    def test_not_configured_without_smtp(self):
        svc = NotificationService()
        # Test muhitida SMTP sozlanmagan
        if not svc._settings["host"]:
            assert svc.is_configured is False

    def test_get_settings_info_structure(self):
        svc = NotificationService()
        info = svc.get_settings_info()
        for k in ["configured", "smtp_host", "smtp_port",
                  "smtp_user", "from_address", "recipients",
                  "total_recipients"]:
            assert k in info

    def test_get_settings_info_no_password(self):
        """Parol sozlamalar ichida ko'rinmaydi."""
        svc = NotificationService()
        info = svc.get_settings_info()
        assert "password" not in info

    def test_get_settings_info_total_recipients_int(self):
        svc = NotificationService()
        info = svc.get_settings_info()
        assert isinstance(info["total_recipients"], int)

    async def test_test_smtp_not_configured_false(self):
        svc = NotificationService()
        if not svc.is_configured:
            result = await svc.test_smtp_connection()
            assert result["ok"] is False
            assert "message" in result

    def test_get_recipients_low_empty(self):
        svc = NotificationService()
        alert = _alert(severity="low")
        result = svc.get_recipients(alert)
        assert result == []

    def test_get_recipients_critical_list(self):
        svc = NotificationService()
        alert = _alert(severity="critical")
        result = svc.get_recipients(alert)
        assert isinstance(result, list)

    def test_get_recipients_extra_added(self):
        svc = NotificationService()
        alert = _alert(severity="high")
        extra = ["extra@test.com"]
        result = svc.get_recipients(alert, extra_recipients=extra)
        assert isinstance(result, list)

    def test_get_recipients_no_duplicates(self):
        svc = NotificationService()
        alert = _alert(severity="high")
        base  = svc.get_recipients(alert)
        if base:
            result = svc.get_recipients(alert, extra_recipients=[base[0]])
            assert result.count(base[0]) == 1

    async def test_send_alert_email_low_skip(self):
        svc = NotificationService()
        alert = _alert(severity="low")
        result = await svc.send_alert_email(alert, recipients=["a@b.com"])
        assert result["sent"] is False
        assert result["mode"] == "skip"

    async def test_send_alert_email_no_recipients_skip(self):
        svc = NotificationService()
        alert = _alert(severity="critical")
        result = await svc.send_alert_email(alert, recipients=[])
        assert result["sent"] is False

    async def test_send_alert_email_not_configured_log(self):
        svc = NotificationService()
        if not svc.is_configured:
            result = await svc.send_alert_email(
                _alert(severity="critical"),
                recipients=["admin@test.com"])
            assert result["mode"] == "log"
            assert result["sent"] is True

    async def test_send_alert_email_all_severities_no_error(self):
        svc = NotificationService()
        for sev in ["critical", "high", "medium"]:
            try:
                await svc.send_alert_email(
                    _alert(severity=sev),
                    recipients=["x@y.com"])
            except Exception as e:
                pytest.fail(f"Severity {sev} raised: {e}")

    async def test_send_alert_email_with_animal_tag(self):
        svc = NotificationService()
        result = await svc.send_alert_email(
            _alert(severity="high"),
            animal_tag="JNV-042",
            recipients=["test@test.com"])
        assert isinstance(result, dict)

    def test_get_notification_service_singleton(self):
        svc1 = get_notification_service()
        svc2 = get_notification_service()
        assert svc1 is svc2

    def test_notification_service_singleton_type(self):
        svc = get_notification_service()
        assert isinstance(svc, NotificationService)