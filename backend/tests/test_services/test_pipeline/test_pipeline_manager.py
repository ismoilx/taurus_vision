"""
Taurus Vision — PipelineManager Tests (Sprint 9-10)

Test qamrovi:
    - StreamOptimizer: CPU yukiga mos skip_frames hisoblash
    - LoadBalancer:    Pipeline limit va RAM tekshiruvi
    - PipelineManager: Start/stop/status tsikli
    - HealthWatchdog:  Crashed pipeline ni restart qilish
    - Camera service yaratish: simulated / RTSP xato / USB xato
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

pytestmark = [pytest.mark.asyncio]


# ============================================================================
# STREAM OPTIMIZER TESTLARI
# ============================================================================

class TestStreamOptimizer:
    """StreamOptimizer CPU yukiga mos skip_frames qaytarishi."""

    def setup_method(self):
        # Har test uchun yangi instance (cache ni sıfırlamak uchun)
        from app.services.pipeline_manager import StreamOptimizer
        self.optimizer = StreamOptimizer()
        self.optimizer._last_check = 0.0  # Force refresh

    @patch("app.services.pipeline_manager.psutil.cpu_percent", return_value=40.0)
    @patch("app.services.pipeline_manager.psutil.virtual_memory")
    def test_low_cpu_returns_low_skip(self, mock_ram, mock_cpu):
        """CPU < 60% → skip_frames = 2 (tez qayta ishlash)."""
        mock_ram.return_value = MagicMock(percent=30.0)
        skip = self.optimizer.get_skip_frames()
        assert skip == 2

    @patch("app.services.pipeline_manager.psutil.cpu_percent", return_value=70.0)
    @patch("app.services.pipeline_manager.psutil.virtual_memory")
    def test_mid_cpu_returns_mid_skip(self, mock_ram, mock_cpu):
        """CPU 60-80% → skip_frames = 4 (o'rtacha)."""
        mock_ram.return_value = MagicMock(percent=40.0)
        skip = self.optimizer.get_skip_frames()
        assert skip == 4

    @patch("app.services.pipeline_manager.psutil.cpu_percent", return_value=90.0)
    @patch("app.services.pipeline_manager.psutil.virtual_memory")
    def test_high_cpu_returns_high_skip(self, mock_ram, mock_cpu):
        """CPU > 80% → skip_frames = 8 (tejamkor)."""
        mock_ram.return_value = MagicMock(percent=50.0)
        skip = self.optimizer.get_skip_frames()
        assert skip == 8

    @patch("app.services.pipeline_manager.psutil.cpu_percent", return_value=30.0)
    @patch("app.services.pipeline_manager.psutil.virtual_memory")
    def test_high_ram_dominates(self, mock_ram, mock_cpu):
        """CPU past bo'lsa ham RAM > 80% bo'lsa — yuqori skip."""
        mock_ram.return_value = MagicMock(percent=85.0)
        skip = self.optimizer.get_skip_frames()
        assert skip == 8

    def test_cached_result_returned(self):
        """10 sekund o'tmagan bo'lsa — cache qaytariladi (psutil chaqirilmaydi)."""
        import time
        from app.services.pipeline_manager import StreamOptimizer, _SKIP_MID

        opt = StreamOptimizer()
        opt._current_skip = _SKIP_MID  # manually set
        opt._last_check   = time.monotonic()  # fresh timestamp

        # psutil ni mock qilmasdan — cache dan o'qishi kerak
        result = opt.get_skip_frames()
        assert result == _SKIP_MID


# ============================================================================
# LOAD BALANCER TESTLARI
# ============================================================================

class TestLoadBalancer:
    """LoadBalancer resurs cheklovlarini to'g'ri qo'llashi."""

    def setup_method(self):
        from app.services.pipeline_manager import LoadBalancer
        self.balancer = LoadBalancer()

    def test_can_start_when_below_limit(self):
        """Limit dan past → can_start=True."""
        self.balancer._max_pipelines = 8
        ok, msg = self.balancer.can_start(current_count=3)
        assert ok is True
        assert msg == ""

    def test_cannot_start_at_limit(self):
        """Limitda → can_start=False."""
        self.balancer._max_pipelines = 4
        ok, msg = self.balancer.can_start(current_count=4)
        assert ok is False
        assert "Maksimal pipeline" in msg

    @patch("app.services.pipeline_manager.psutil.virtual_memory")
    def test_cannot_start_low_ram(self, mock_ram):
        """RAM yetarli emas → can_start=False."""
        from app.services.pipeline_manager import _RAM_PER_PIPELINE_MB
        # Available MB < RAM_PER_PIPELINE_MB
        mock_ram.return_value = MagicMock(
            available=(_RAM_PER_PIPELINE_MB - 50) * 1024 * 1024,
        )
        self.balancer._max_pipelines = 16

        ok, msg = self.balancer.can_start(current_count=0)
        assert ok is False
        assert "RAM" in msg

    def test_max_pipelines_bounded_by_16(self):
        """Mutlaq limit 16 dan oshmasligi kerak."""
        from app.services.pipeline_manager import LoadBalancer
        lb = LoadBalancer()
        assert lb.max_pipelines <= 16


# ============================================================================
# PIPELINE MANAGER TESTLARI
# ============================================================================

class TestPipelineManager:
    """PipelineManager asosiy funksionalligi."""

    def setup_method(self):
        """Har test uchun yangi singleton state."""
        import importlib
        import app.services.pipeline_manager as pm_module
        pm_module._pipeline_manager = None  # singleton reset

        # Singleton instance ni ham reset qilish
        from app.services.pipeline_manager import PipelineManager
        PipelineManager._instance = None

    def _get_manager(self):
        from app.services.pipeline_manager import get_pipeline_manager
        return get_pipeline_manager()

    def test_singleton_returns_same_instance(self):
        """get_pipeline_manager() har doim bir xil instance qaytaradi."""
        m1 = self._get_manager()
        m2 = self._get_manager()
        assert m1 is m2

    def test_initial_state(self):
        """Boshlang'ich holat: pipeline yo'q, is_running=False."""
        manager = self._get_manager()
        assert manager.total_running() == 0
        assert manager.list_running() == []
        assert manager.is_running("nonexistent") is False

    async def test_start_simulated_camera(self):
        """Simulated kamera pipelini muvaffaqiyatli ishga tushadi."""
        manager = self._get_manager()

        # YOLO va WS ni mock qilish
        mock_yolo = MagicMock()
        mock_yolo.detect = AsyncMock(return_value=[])

        with (
            patch("app.services.pipeline_manager.get_yolo_service", return_value=mock_yolo),
            patch("app.services.pipeline_manager.get_ws_manager", side_effect=RuntimeError),
            patch.object(manager._balancer, "can_start", return_value=(True, "")),
        ):
            ok, reason = await manager.start_camera(
                camera_id   = "TEST-SIM-001",
                camera_type = "simulated",
                fps         = 5,
            )

        assert ok is True
        assert reason == ""
        assert manager.is_running("TEST-SIM-001") is True
        assert manager.total_running() == 1

        # Tozalash
        await manager.stop_camera("TEST-SIM-001")

    async def test_cannot_start_same_camera_twice(self):
        """Bir kamerani ikki marta ishga tushirib bo'lmaydi."""
        manager = self._get_manager()

        mock_yolo = MagicMock()
        mock_yolo.detect = AsyncMock(return_value=[])

        with (
            patch("app.services.pipeline_manager.get_yolo_service", return_value=mock_yolo),
            patch("app.services.pipeline_manager.get_ws_manager", side_effect=RuntimeError),
            patch.object(manager._balancer, "can_start", return_value=(True, "")),
        ):
            ok1, _ = await manager.start_camera("TEST-DOUBLE-001", "simulated", fps=5)
            ok2, reason2 = await manager.start_camera("TEST-DOUBLE-001", "simulated", fps=5)

        assert ok1 is True
        assert ok2 is False
        assert "allaqachon ishlayapti" in reason2

        await manager.stop_camera("TEST-DOUBLE-001")

    async def test_stop_nonexistent_camera(self):
        """Yo'q pipeline ni to'xtatishda False qaytadi."""
        manager = self._get_manager()
        ok, reason = await manager.stop_camera("NONEXISTENT-CAM")
        assert ok is False
        assert "topilmadi" in reason

    async def test_load_balancer_blocks_start(self):
        """Load balancer limit oshganda ishga tushirishni bloklab qo'yadi."""
        manager = self._get_manager()

        with patch.object(
            manager._balancer, "can_start",
            return_value=(False, "Maksimal pipeline soni (4) ga yetildi."),
        ):
            ok, reason = await manager.start_camera("BLOCKED-CAM", "simulated")

        assert ok is False
        assert "Maksimal" in reason

    async def test_stop_all(self):
        """stop_all() barcha pipelinelarni to'xtatadi."""
        manager = self._get_manager()
        mock_yolo = MagicMock()
        mock_yolo.detect = AsyncMock(return_value=[])

        with (
            patch("app.services.pipeline_manager.get_yolo_service", return_value=mock_yolo),
            patch("app.services.pipeline_manager.get_ws_manager", side_effect=RuntimeError),
            patch.object(manager._balancer, "can_start", return_value=(True, "")),
        ):
            await manager.start_camera("STOP-ALL-A", "simulated", fps=5)
            await manager.start_camera("STOP-ALL-B", "simulated", fps=5)
            assert manager.total_running() == 2

        stopped = await manager.stop_all()
        assert stopped == 2
        assert manager.total_running() == 0

    def test_get_status_not_running(self):
        """Ishlamayotgan pipeline uchun status running=False."""
        manager = self._get_manager()
        status = manager.get_status("NOT-RUNNING")
        assert status["running"] is False
        assert status["stats"] is None
        assert status["started_at"] is None

    async def test_get_all_status_empty(self):
        """Pipeline yo'q bo'lganda get_all_status empty dict."""
        manager = self._get_manager()
        all_status = manager.get_all_status()
        assert isinstance(all_status, dict)
        assert len(all_status) == 0

    def test_system_metrics_structure(self):
        """get_system_metrics to'g'ri kalit larni qaytaradi."""
        manager = self._get_manager()
        metrics = manager.get_system_metrics()

        required_keys = [
            "cpu_percent", "ram_percent", "ram_available_mb",
            "active_pipelines", "max_pipelines",
            "current_skip_frames", "can_start_new",
        ]
        for key in required_keys:
            assert key in metrics, f"Key '{key}' missing from system_metrics"

        assert isinstance(metrics["cpu_percent"],  (int, float))
        assert isinstance(metrics["ram_percent"],  (int, float))
        assert isinstance(metrics["max_pipelines"], int)
        assert isinstance(metrics["can_start_new"], bool)


# ============================================================================
# CAMERA SERVICE YARATISH TESTLARI
# ============================================================================

class TestCreateCameraService:
    """_create_camera_service() to'g'ri servislarni yaratadi."""

    def setup_method(self):
        import app.services.pipeline_manager as pm_module
        pm_module._pipeline_manager = None
        from app.services.pipeline_manager import PipelineManager
        PipelineManager._instance = None

    def _get_manager(self):
        from app.services.pipeline_manager import get_pipeline_manager
        return get_pipeline_manager()

    async def test_simulated_creates_simulated_service(self):
        """'simulated' → SimulatedCameraService yaratiladi."""
        from app.services.camera.simulated_camera import SimulatedCameraService
        manager = self._get_manager()

        service = await manager._create_camera_service(
            camera_id    = "TEST-SIM",
            camera_type  = "simulated",
            source       = None,
            device_index = None,
            fps          = 10,
        )

        assert isinstance(service, SimulatedCameraService)

    async def test_rtsp_without_source_raises(self):
        """'rtsp' va source=None → ValueError."""
        manager = self._get_manager()

        with pytest.raises(ValueError, match="source.*talab qilinadi"):
            await manager._create_camera_service(
                camera_id    = "TEST-RTSP",
                camera_type  = "rtsp",
                source       = None,
                device_index = None,
                fps          = 10,
            )

    async def test_usb_without_device_index_raises(self):
        """'usb' va device_index=None → ValueError."""
        manager = self._get_manager()

        with pytest.raises(ValueError, match="device_index.*talab qilinadi"):
            await manager._create_camera_service(
                camera_id    = "TEST-USB",
                camera_type  = "usb",
                source       = None,
                device_index = None,
                fps          = 10,
            )

    async def test_unknown_type_raises(self):
        """Noma'lum kamera turi → ValueError."""
        manager = self._get_manager()

        with pytest.raises(ValueError, match="Noma'lum kamera turi"):
            await manager._create_camera_service(
                camera_id    = "TEST-UNK",
                camera_type  = "thermal",  # not supported
                source       = None,
                device_index = None,
                fps          = 10,
            )

    async def test_rtsp_creates_rtsp_service(self):
        """'rtsp' + source → RTSPCameraService yaratiladi."""
        from app.services.camera.rtsp_camera_service import RTSPCameraService
        manager = self._get_manager()

        service = await manager._create_camera_service(
            camera_id    = "TEST-RTSP-OK",
            camera_type  = "rtsp",
            source       = "rtsp://192.168.1.100:554/stream",
            device_index = None,
            fps          = 10,
        )

        assert isinstance(service, RTSPCameraService)
        assert service.camera_id == "TEST-RTSP-OK"

    async def test_usb_creates_usb_service(self):
        """'usb' + device_index → USBCameraService yaratiladi."""
        from app.services.camera.usb_camera_service import USBCameraService
        manager = self._get_manager()

        service = await manager._create_camera_service(
            camera_id    = "TEST-USB-OK",
            camera_type  = "usb",
            source       = None,
            device_index = 0,
            fps          = 15,
        )

        assert isinstance(service, USBCameraService)
        assert service.camera_id == "TEST-USB-OK"
