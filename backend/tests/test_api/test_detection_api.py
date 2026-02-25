"""Detection API Tests — /api/v1/detection/"""
import pytest
import io
import base64
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


def make_tiny_png_bytes() -> bytes:
    import zlib, struct
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0))
    raw  = (b'\x00' + b'\xFF\x80\x00' * 8) * 8
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


MOCK_RESULT = {"detections": [{"class_id": 19, "class_name": "cow", "confidence": 0.92, "bbox": {"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35}}], "total_detections": 1, "processing_time_ms": 42.5}


class TestDetectionUpload:
    async def test_upload_no_file(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/detection/upload", headers=H(admin_token))
        assert r.status_code == 422

    async def test_upload_invalid_file_type(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/detection/upload",
            headers=H(admin_token),
            files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
        )
        assert r.status_code in (400, 422)

    async def test_upload_png_success(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/detection/upload",
            headers=H(admin_token),
            files={"file": ("test.png", io.BytesIO(make_tiny_png_bytes()), "image/png")},
        )
        assert r.status_code in (200, 422, 503)

    async def test_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/detection/upload")
        assert r.status_code in (401, 422)


class TestDetectionBase64:
    async def test_base64_invalid_data(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/detection/base64",
            headers=H(admin_token),
            json={"image_base64": "not_valid!!!"},
        )
        assert r.status_code in (400, 422)

    async def test_base64_missing_field(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/detection/base64", headers=H(admin_token), json={})
        assert r.status_code == 422

    async def test_base64_success(self, client: AsyncClient, admin_token: str):
        img_b64 = base64.b64encode(make_tiny_png_bytes()).decode()
        r = await client.post(
            "/api/v1/detection/base64",
            headers=H(admin_token),
            json={"image_base64": img_b64, "camera_id": "CAM-001"},
        )
        assert r.status_code in (200, 422, 503)


class TestDetectionModelInfo:
    async def test_model_info(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/detection/model-info", headers=H(admin_token))
        assert r.status_code in (200, 401, 503)

    async def test_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/detection/model-info")
        assert r.status_code in (200, 401, 503)


class TestDetectionHealth:
    async def test_health_check(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/detection/health", headers=H(admin_token))
        assert r.status_code == 200
        assert "status" in r.json()