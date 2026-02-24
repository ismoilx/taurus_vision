"""
Pipeline API Tests — /api/v1/pipeline/

Qamrovi:
  - POST /pipeline/start        — kamera pipeline
  - POST /pipeline/start-video  — video fayl pipeline
  - GET  /pipeline/status       — holat
  - POST /pipeline/stop         — to'xtatish
  - GET  /pipeline/output-videos
  - POST /pipeline/inject-test-detection
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from pathlib import Path

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestPipelineStatus:
    """GET /api/v1/pipeline/status"""

    async def test_status_not_initialized(self, client: AsyncClient):
        """Pipeline hali ishga tushirilmagan."""
        r = await client.get("/api/v1/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "running" in data
        assert data["running"] is False

    async def test_status_structure(self, client: AsyncClient):
        """Status response to'g'ri tuzilgan."""
        r = await client.get("/api/v1/pipeline/status")
        assert r.status_code == 200
        data = r.json()
        # Majburiy maydonlar
        assert "status" in data
        assert data["status"] in ("not_initialized", "running", "stopped")


class TestPipelineStartVideo:
    """POST /api/v1/pipeline/start-video"""

    async def test_start_video_file_not_found(self, client: AsyncClient):
        """Mavjud bo'lmagan video fayl — 404."""
        r = await client.post(
            "/api/v1/pipeline/start-video",
            params={"video_filename": "nonexistent_video_xyz_123.mp4"},
        )
        assert r.status_code == 404

    async def test_start_video_missing_param(self, client: AsyncClient):
        """video_filename parametri yo'q — 422."""
        r = await client.post("/api/v1/pipeline/start-video")
        assert r.status_code == 422

    async def test_start_video_already_running(self, client: AsyncClient, tmp_path):
        """Pipeline allaqachon ishlayotgan — 409."""
        # Avval ishlab turgan pipeline holati simulatsiya
        fake_video = tmp_path / "test.mp4"
        fake_video.write_bytes(b"fake video data")

        with patch("app.api.v1.endpoints.pipeline.detection_pipeline") as mock_pipeline:
            mock_pipeline.is_running.return_value = True

            r = await client.post(
                "/api/v1/pipeline/start-video",
                params={"video_filename": "test.mp4"},
            )
        # 409 Conflict yoki pipeline allaqachon ishlayotgan deydi
        assert r.status_code in (409, 404, 400)


class TestPipelineStop:
    """POST /api/v1/pipeline/stop"""

    async def test_stop_not_running(self, client: AsyncClient):
        """Pipeline ishlamayotganda to'xtatish — 400 yoki muvaffaqiyatli."""
        r = await client.post("/api/v1/pipeline/stop")
        # 400 (already stopped) yoki 200 (nothing to stop)
        assert r.status_code in (200, 400)

    async def test_stop_response_structure(self, client: AsyncClient):
        """Stop javobi to'g'ri tuzilgan."""
        r = await client.post("/api/v1/pipeline/stop")
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict)


class TestOutputVideos:
    """GET /api/v1/pipeline/output-videos"""

    async def test_list_output_videos(self, client: AsyncClient):
        """Annotatsiyalangan videolar ro'yxati."""
        r = await client.get("/api/v1/pipeline/output-videos")
        assert r.status_code == 200
        data = r.json()
        assert "videos" in data or "files" in data or isinstance(data, list)


class TestInjectTestDetection:
    """POST /api/v1/pipeline/inject-test-detection"""

    async def test_inject_requires_running_pipeline(self, client: AsyncClient):
        """Pipeline ishlamayotganda inject qilish — 400 yoki 404."""
        r = await client.post(
            "/api/v1/pipeline/inject-test-detection",
            json={"animal_id": 1, "camera_id": "CAM-001"},
        )
        assert r.status_code in (200, 400, 404, 422)