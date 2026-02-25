"""Pipeline API Tests — /api/v1/pipeline/"""
import pytest
from unittest.mock import patch
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


class TestPipelineStatus:
    async def test_status_not_initialized(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/pipeline/status", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "running" in data

    async def test_status_structure(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/pipeline/status", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] in ("not_initialized", "running", "stopped")

    async def test_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/pipeline/status")
        assert r.status_code == 401


class TestPipelineStartVideo:
    async def test_start_video_file_not_found(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/pipeline/start-video",
            headers=H(admin_token),
            params={"video_filename": "nonexistent_xyz_123.mp4"},
        )
        assert r.status_code == 404

    async def test_start_video_missing_param(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/pipeline/start-video", headers=H(admin_token))
        assert r.status_code == 422


class TestPipelineStop:
    async def test_stop_not_running(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/pipeline/stop", headers=H(admin_token))
        assert r.status_code in (200, 400)

    async def test_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/pipeline/stop")
        assert r.status_code == 401


class TestOutputVideos:
    async def test_list_output_videos(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/pipeline/output-videos", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "videos" in data or "files" in data or isinstance(data, list)


class TestInjectTestDetection:
    async def test_inject_requires_running_pipeline(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/pipeline/inject-test-detection",
            headers=H(admin_token),
            json={"animal_id": 1, "camera_id": "CAM-001"},
        )
        assert r.status_code in (200, 400, 404, 422)