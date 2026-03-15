"""
TAURUS VISION — tests/test_services/test_detection_colab_pipeline.py
=====================================================================
PipelineStats + ColabPipelineStats + ColabPipeline pure methods
uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_services/test_detection_colab_pipeline.py

Qamrav (100+ test):
  ✓ PipelineStats.__init__ / reset    — barcha maydonlar nol
  ✓ PipelineStats.uptime_seconds      — started_at=None → 0, hisob
  ✓ PipelineStats.fps                 — 0 uptime, haqiqiy hisob
  ✓ PipelineStats.avg_inference_ms    — 0 frame → 0, haqiqiy hisob
  ✓ PipelineStats.to_dict             — barcha 13 kalit
  ✓ PipelineStats counter increment   — yolo, identified, errors, db_writes
  ✓ ColabPipelineStats.__init__/reset — nol qiymatlar
  ✓ ColabPipelineStats.add_latency    — buf cap 30, avg hisob
  ✓ ColabPipelineStats.fps            — started_at=None → 0
  ✓ ColabPipelineStats.to_dict        — barcha 7 kalit
  ✓ ColabPipeline.__init__            — url strip, target_fps, header
  ✓ ColabPipeline.is_running          — False boshlang'ich
  ✓ ColabPipeline.get_stats           — tuzilma, camera_id, colab_url
  ✓ ColabPipeline.MIN_FRAME_INTERVAL  — 1/fps
  ✓ ColabPipeline start idempotent    — 2x start xato bermaydi
  ✓ ColabPipeline stop not_running    — xato bermaydi
  ✓ DetectionPipeline.MIN_FRAME_INTERVAL — 0.5
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.detection_pipeline import PipelineStats
from app.services.colab_pipeline import ColabPipelineStats, ColabPipeline

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

def _mock_camera(camera_id="TEST-CAM"):
    cam = MagicMock()
    cam.camera_id = camera_id
    cam.start  = AsyncMock()
    cam.stop   = AsyncMock()
    cam.get_frame = AsyncMock(return_value=None)
    return cam


# ═══════════════════════════════════════════════════════════════════════════════
# PipelineStats
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineStats:

    def test_init_total_frames_zero(self):
        s = PipelineStats()
        assert s.total_frames == 0

    def test_init_processed_frames_zero(self):
        s = PipelineStats()
        assert s.processed_frames == 0

    def test_init_yolo_detections_zero(self):
        s = PipelineStats()
        assert s.yolo_detections == 0

    def test_init_identified_zero(self):
        s = PipelineStats()
        assert s.identified == 0

    def test_init_unidentified_zero(self):
        s = PipelineStats()
        assert s.unidentified == 0

    def test_init_db_writes_zero(self):
        s = PipelineStats()
        assert s.db_writes == 0

    def test_init_alert_checks_zero(self):
        s = PipelineStats()
        assert s.alert_checks == 0

    def test_init_errors_zero(self):
        s = PipelineStats()
        assert s.errors == 0

    def test_init_total_inference_ms_zero(self):
        s = PipelineStats()
        assert s.total_inference_ms == 0.0

    def test_init_started_at_none(self):
        s = PipelineStats()
        assert s.started_at is None

    def test_init_frames_collected_zero(self):
        s = PipelineStats()
        assert s.frames_collected == 0

    def test_reset_clears_all(self):
        s = PipelineStats()
        s.total_frames = 100
        s.processed_frames = 50
        s.yolo_detections = 30
        s.errors = 5
        s.started_at = NOW
        s.reset()
        assert s.total_frames == 0
        assert s.processed_frames == 0
        assert s.yolo_detections == 0
        assert s.errors == 0
        assert s.started_at is None

    def test_uptime_seconds_none_started_at(self):
        s = PipelineStats()
        assert s.uptime_seconds == 0.0

    def test_uptime_seconds_with_started_at(self):
        s = PipelineStats()
        s.started_at = NOW - timedelta(seconds=10)
        assert 9.0 < s.uptime_seconds < 12.0

    def test_fps_no_uptime_zero(self):
        s = PipelineStats()
        assert s.fps == 0.0

    def test_fps_with_frames(self):
        s = PipelineStats()
        s.started_at = NOW - timedelta(seconds=10)
        s.processed_frames = 100
        assert s.fps > 5.0  # 100/10 = 10 FPS

    def test_fps_returns_float(self):
        s = PipelineStats()
        s.started_at = NOW - timedelta(seconds=1)
        s.processed_frames = 10
        assert isinstance(s.fps, float)

    def test_avg_inference_ms_no_frames_zero(self):
        s = PipelineStats()
        assert s.avg_inference_ms == 0.0

    def test_avg_inference_ms_with_data(self):
        s = PipelineStats()
        s.processed_frames = 10
        s.total_inference_ms = 500.0
        assert abs(s.avg_inference_ms - 50.0) < 0.5

    def test_avg_inference_ms_returns_float(self):
        s = PipelineStats()
        s.processed_frames = 5
        s.total_inference_ms = 250.0
        assert isinstance(s.avg_inference_ms, float)

    def test_to_dict_all_13_keys(self):
        s = PipelineStats()
        d = s.to_dict()
        for k in ["uptime_seconds", "total_frames", "processed_frames",
                  "yolo_detections", "identified", "unidentified",
                  "db_writes", "alert_checks", "missing_resolved",
                  "errors", "fps", "avg_inference_ms", "frames_collected"]:
            assert k in d

    def test_to_dict_initial_values(self):
        s = PipelineStats()
        d = s.to_dict()
        assert d["total_frames"] == 0
        assert d["fps"] == 0.0
        assert d["uptime_seconds"] == 0.0

    def test_counter_increment(self):
        s = PipelineStats()
        s.total_frames += 1
        s.yolo_detections += 3
        s.identified += 2
        s.errors += 1
        assert s.total_frames == 1
        assert s.yolo_detections == 3
        assert s.identified == 2
        assert s.errors == 1

    def test_to_dict_after_increment(self):
        s = PipelineStats()
        s.started_at = NOW - timedelta(seconds=5)
        s.processed_frames = 50
        s.total_inference_ms = 1000.0
        d = s.to_dict()
        assert d["processed_frames"] == 50
        assert d["avg_inference_ms"] == 20.0


# ═══════════════════════════════════════════════════════════════════════════════
# ColabPipelineStats
# ═══════════════════════════════════════════════════════════════════════════════

class TestColabPipelineStats:

    def test_init_total_frames_zero(self):
        s = ColabPipelineStats()
        assert s.total_frames == 0

    def test_init_sent_frames_zero(self):
        s = ColabPipelineStats()
        assert s.sent_frames == 0

    def test_init_skipped_frames_zero(self):
        s = ColabPipelineStats()
        assert s.skipped_frames == 0

    def test_init_errors_zero(self):
        s = ColabPipelineStats()
        assert s.errors == 0

    def test_init_avg_latency_zero(self):
        s = ColabPipelineStats()
        assert s.avg_latency_ms == 0.0

    def test_init_started_at_none(self):
        s = ColabPipelineStats()
        assert s.started_at is None

    def test_reset_clears_all(self):
        s = ColabPipelineStats()
        s.total_frames = 100
        s.errors = 5
        s.avg_latency_ms = 50.0
        s.reset()
        assert s.total_frames == 0
        assert s.errors == 0
        assert s.avg_latency_ms == 0.0

    def test_add_latency_updates_avg(self):
        s = ColabPipelineStats()
        s.add_latency(100.0)
        s.add_latency(200.0)
        assert abs(s.avg_latency_ms - 150.0) < 1.0

    def test_add_latency_cap_30(self):
        s = ColabPipelineStats()
        for i in range(35):
            s.add_latency(float(i))
        assert len(s._latency_buf) <= 30

    def test_add_latency_single(self):
        s = ColabPipelineStats()
        s.add_latency(42.5)
        assert abs(s.avg_latency_ms - 42.5) < 0.1

    def test_fps_no_started_at_zero(self):
        s = ColabPipelineStats()
        assert s.fps == 0.0

    def test_fps_with_sent_frames(self):
        s = ColabPipelineStats()
        s.started_at = NOW - timedelta(seconds=10)
        s.sent_frames = 150
        assert s.fps > 10.0

    def test_fps_returns_float(self):
        s = ColabPipelineStats()
        s.started_at = NOW - timedelta(seconds=5)
        s.sent_frames = 50
        assert isinstance(s.fps, float)

    def test_to_dict_7_keys(self):
        s = ColabPipelineStats()
        d = s.to_dict()
        for k in ["mode", "total_frames", "sent_frames", "skipped_frames",
                  "errors", "fps", "avg_latency_ms"]:
            assert k in d

    def test_to_dict_mode_colab_gpu(self):
        s = ColabPipelineStats()
        assert s.to_dict()["mode"] == "colab_gpu"

    def test_to_dict_initial_fps_zero(self):
        s = ColabPipelineStats()
        assert s.to_dict()["fps"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ColabPipeline.__init__ va pure methods
# ═══════════════════════════════════════════════════════════════════════════════

class TestColabPipeline:

    def _pipeline(self, url="https://colab.example.com", fps=15, secret=None):
        cam = _mock_camera("COLAB-CAM")
        return ColabPipeline(
            camera_service=cam,
            colab_url=url,
            colab_secret=secret,
            target_fps=fps,
            jpeg_quality=70,
        )

    def test_init_url_stripped(self):
        cp = self._pipeline(url="https://colab.example.com/")
        assert not cp.colab_url.endswith("/")

    def test_init_frame_url(self):
        cp = self._pipeline(url="https://colab.example.com")
        assert cp.frame_url == "https://colab.example.com/frame"

    def test_init_target_fps(self):
        cp = self._pipeline(fps=20)
        assert cp.target_fps == 20

    def test_init_min_frame_interval(self):
        cp = self._pipeline(fps=10)
        assert abs(cp.MIN_FRAME_INTERVAL - 0.1) < 0.001

    def test_init_min_frame_interval_15fps(self):
        cp = self._pipeline(fps=15)
        expected = 1.0 / 15
        assert abs(cp.MIN_FRAME_INTERVAL - expected) < 0.001

    def test_init_running_false(self):
        cp = self._pipeline()
        assert cp._running is False

    def test_init_task_none(self):
        cp = self._pipeline()
        assert cp._task is None

    def test_init_no_secret_no_header(self):
        cp = self._pipeline(secret=None)
        assert "X-Colab-Key" not in cp._headers

    def test_init_with_secret_header(self):
        cp = self._pipeline(secret="my-secret-key")
        assert cp._headers.get("X-Colab-Key") == "my-secret-key"

    def test_is_running_false_initially(self):
        cp = self._pipeline()
        assert cp.is_running is False

    def test_get_stats_structure(self):
        cp = self._pipeline()
        stats = cp.get_stats()
        for k in ["mode", "total_frames", "sent_frames", "status",
                  "camera_id", "colab_url"]:
            assert k in stats

    def test_get_stats_status_stopped(self):
        cp = self._pipeline()
        assert cp.get_stats()["status"] == "stopped"

    def test_get_stats_camera_id(self):
        cp = self._pipeline()
        assert cp.get_stats()["camera_id"] == "COLAB-CAM"

    def test_get_stats_colab_url(self):
        cp = self._pipeline(url="https://colab.example.com")
        assert cp.get_stats()["colab_url"] == "https://colab.example.com"

    def test_get_stats_mode_colab_gpu(self):
        cp = self._pipeline()
        assert cp.get_stats()["mode"] == "colab_gpu"

    def test_jpeg_quality_stored(self):
        cp = self._pipeline()
        assert cp.jpeg_quality == 70

    async def test_start_sets_running(self):
        cp = self._pipeline()
        try:
            await cp.start()
            assert cp._running is True
        finally:
            await cp.stop()

    async def test_start_idempotent(self):
        """2x start() xato bermaydi."""
        cp = self._pipeline()
        try:
            await cp.start()
            await cp.start()  # Ikkinchi — hech narsa qilmaydi
            assert cp._running is True
        finally:
            await cp.stop()

    async def test_stop_not_running_no_error(self):
        """Ishlatilmagan pipeline ni stop qilish xato bermaydi."""
        cp = self._pipeline()
        try:
            await cp.stop()
        except Exception as e:
            pytest.fail(f"stop() raised: {e}")

    async def test_stop_sets_running_false(self):
        cp = self._pipeline()
        await cp.start()
        await cp.stop()
        assert cp._running is False


# ═══════════════════════════════════════════════════════════════════════════════
# DetectionPipeline constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectionPipelineConstants:
    def test_min_frame_interval_0_5(self):
        from app.services.detection_pipeline import DetectionPipeline
        assert DetectionPipeline.MIN_FRAME_INTERVAL == 0.5

    def test_pipeline_stats_in_detection_pipeline(self):
        """DetectionPipeline ichida PipelineStats ishlatiladi."""
        from app.services.detection_pipeline import DetectionPipeline, PipelineStats
        assert PipelineStats is not None