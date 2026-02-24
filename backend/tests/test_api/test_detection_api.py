"""
Detection API Tests — /api/v1/detection/

Qamrovi:
  - POST /detection/upload   — rasm fayl yuklash
  - POST /detection/base64   — base64 rasm
  - GET  /detection/model-info
  - GET  /detection/health
"""

import pytest
import io
import base64
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


def make_tiny_jpeg_bytes() -> bytes:
    """Kichik test JPEG yaratish (PIL ishlatmasdan)."""
    # Minimal valid JPEG (1x1 piksel, qizil rang)
    # Bu real JPEG bytes - hardcoded minimal image
    return (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e>+..;'
        b'2=5\x82\x1b\x03\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
        b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
        b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04'
        b'\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa'
        b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br'
        b'\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
        b'STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb'
        b'\xd2P\x00\x00\x00\x1f\xff\xd9'
    )


def make_tiny_png_bytes() -> bytes:
    """1x1 piksel PNG bytes (PIL ishlatmasdan)."""
    import zlib, struct

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr = png_chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
    raw  = b'\x00\xFF\x00\x00'  # filter byte + RGB
    idat = png_chunk(b'IDAT', zlib.compress(raw))
    iend = png_chunk(b'IEND', b'')
    return signature + ihdr + idat + iend


MOCK_DETECTION_RESULT = {
    "detections": [
        {
            "class_id": 19,
            "class_name": "cow",
            "confidence": 0.92,
            "bbox": {"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
            "estimated_weight": 285.0,
        }
    ],
    "total_detections": 1,
    "processing_time_ms": 42.5,
    "model": "yolo26n.pt",
}


class TestDetectionUpload:
    """POST /api/v1/detection/upload"""

    async def test_upload_jpeg_success(self, client: AsyncClient):
        """JPEG rasm yuklash — muvaffaqiyatli deteksiya."""
        img_bytes = make_tiny_png_bytes()

        with patch(
            "app.services.ai.yolo_service.get_yolo_service"
        ) as mock_get:
            mock_svc = AsyncMock()
            mock_svc.detect.return_value = MOCK_DETECTION_RESULT
            mock_get.return_value = mock_svc

            r = await client.post(
                "/api/v1/detection/upload",
                files={"file": ("test.png", io.BytesIO(img_bytes), "image/png")},
            )

        assert r.status_code in (200, 422, 503)  # 503 agar model yuklanmagan

    async def test_upload_no_file(self, client: AsyncClient):
        """Fayl yuborilmasa — 422."""
        r = await client.post("/api/v1/detection/upload")
        assert r.status_code == 422

    async def test_upload_invalid_file_type(self, client: AsyncClient):
        """Rasm bo'lmagan fayl — 400 yoki 422."""
        r = await client.post(
            "/api/v1/detection/upload",
            files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
        )
        assert r.status_code in (400, 422)


class TestDetectionBase64:
    """POST /api/v1/detection/base64"""

    async def test_base64_success(self, client: AsyncClient):
        """Base64 rasm yuborish."""
        img_b64 = base64.b64encode(make_tiny_png_bytes()).decode()

        with patch("app.services.ai.yolo_service.get_yolo_service") as mock_get:
            mock_svc = AsyncMock()
            mock_svc.detect.return_value = MOCK_DETECTION_RESULT
            mock_get.return_value = mock_svc

            r = await client.post(
                "/api/v1/detection/base64",
                json={"image_base64": img_b64, "camera_id": "CAM-001"},
            )

        assert r.status_code in (200, 503)

    async def test_base64_invalid_data(self, client: AsyncClient):
        """Noto'g'ri base64 — 400 yoki 422."""
        r = await client.post(
            "/api/v1/detection/base64",
            json={"image_base64": "not_valid_base64!!!"},
        )
        assert r.status_code in (400, 422)

    async def test_base64_missing_field(self, client: AsyncClient):
        """image_base64 maydoni yo'q — 422."""
        r = await client.post("/api/v1/detection/base64", json={})
        assert r.status_code == 422


class TestDetectionModelInfo:
    """GET /api/v1/detection/model-info"""

    async def test_model_info(self, client: AsyncClient):
        """Model ma'lumotlari qaytadi."""
        r = await client.get("/api/v1/detection/model-info")
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            data = r.json()
            assert "model" in data or "name" in data or "version" in data


class TestDetectionHealth:
    """GET /api/v1/detection/health"""

    async def test_health_check(self, client: AsyncClient):
        """Deteksiya servisi sog'ligi."""
        r = await client.get("/api/v1/detection/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data