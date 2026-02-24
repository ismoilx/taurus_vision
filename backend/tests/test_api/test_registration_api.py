"""
Registration API Tests — /api/v1/registration/

Qamrovi:
  - POST /registration/{animal_id}/register     — muzzle ro'yxatdan o'tkazish
  - POST /registration/identify                 — jonivorni aniqlash
  - GET  /registration/{animal_id}/embeddings   — embedding ro'yxati
  - DELETE /registration/{animal_id}/embeddings/{embedding_id}
"""

import pytest
import io
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


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


class TestMuzzleRegistration:
    """POST /api/v1/registration/{animal_id}/register"""

    async def test_register_animal_not_found(self, client: AsyncClient):
        """Mavjud bo'lmagan jonivor — 404."""
        img_bytes = make_tiny_png_bytes()
        r = await client.post(
            "/api/v1/registration/99999/register",
            files={"images": ("muzzle.png", io.BytesIO(img_bytes), "image/png")},
        )
        assert r.status_code == 404

    async def test_register_no_images(self, client: AsyncClient, sample_animal):
        """Rasm yuborilmasa — 422."""
        r = await client.post(f"/api/v1/registration/{sample_animal.id}/register")
        assert r.status_code == 422

    async def test_register_success(self, client: AsyncClient, sample_animal):
        """Muvaffaqiyatli ro'yxatdan o'tish."""
        img_bytes = make_tiny_png_bytes()

        with patch("app.services.ai.feature_extractor.get_feature_extractor") as mock_fe:
            mock_svc = AsyncMock()
            mock_svc.extract_features.return_value = [0.1] * 512
            mock_fe.return_value = mock_svc

            r = await client.post(
                f"/api/v1/registration/{sample_animal.id}/register",
                files={"images": ("muzzle.png", io.BytesIO(img_bytes), "image/png")},
            )

        # 200, 201, or 503 (model yuklanmagan)
        assert r.status_code in (200, 201, 503)


class TestAnimalIdentification:
    """POST /api/v1/registration/identify"""

    async def test_identify_no_image(self, client: AsyncClient):
        """Rasm yo'q — 422."""
        r = await client.post("/api/v1/registration/identify")
        assert r.status_code == 422

    async def test_identify_with_image(self, client: AsyncClient, sample_animal):
        """Rasm bilan identifikatsiya."""
        img_bytes = make_tiny_png_bytes()

        with patch("app.services.ai.feature_extractor.get_feature_extractor") as mock_fe:
            mock_svc = AsyncMock()
            mock_svc.identify.return_value = {
                "animal_id": sample_animal.id,
                "confidence": 0.95,
                "tag_id": sample_animal.tag_id,
            }
            mock_fe.return_value = mock_svc

            r = await client.post(
                "/api/v1/registration/identify",
                files={"file": ("muzzle.png", io.BytesIO(img_bytes), "image/png")},
            )

        assert r.status_code in (200, 503)

    async def test_identify_no_registered_animals(self, client: AsyncClient):
        """Hech kim ro'yxatdan o'tmagan — 404 yoki no_match."""
        img_bytes = make_tiny_png_bytes()

        with patch("app.services.ai.feature_extractor.get_feature_extractor") as mock_fe:
            mock_svc = AsyncMock()
            mock_svc.identify.return_value = None
            mock_fe.return_value = mock_svc

            r = await client.post(
                "/api/v1/registration/identify",
                files={"file": ("muzzle.png", io.BytesIO(img_bytes), "image/png")},
            )

        assert r.status_code in (200, 404, 503)


class TestEmbeddingsList:
    """GET /api/v1/registration/{animal_id}/embeddings"""

    async def test_list_embeddings_not_found_animal(self, client: AsyncClient):
        """Mavjud bo'lmagan jonivor — 404."""
        r = await client.get("/api/v1/registration/99999/embeddings")
        assert r.status_code == 404

    async def test_list_embeddings_empty(self, client: AsyncClient, sample_animal):
        """Embedding yo'q — bo'sh list."""
        r = await client.get(f"/api/v1/registration/{sample_animal.id}/embeddings")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or "items" in data or "embeddings" in data


class TestDeleteEmbedding:
    """DELETE /api/v1/registration/{animal_id}/embeddings/{embedding_id}"""

    async def test_delete_not_found(self, client: AsyncClient, sample_animal):
        """Mavjud bo'lmagan embedding — 404."""
        r = await client.delete(
            f"/api/v1/registration/{sample_animal.id}/embeddings/99999"
        )
        assert r.status_code == 404