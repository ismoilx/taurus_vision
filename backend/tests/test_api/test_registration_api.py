"""Registration API Tests — /api/v1/registration/"""
import pytest
import io
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


def make_tiny_png_bytes() -> bytes:
    """
    Endpoint minimum 32x32px talab qiladi — shuning uchun 64x64 PNG yaratamiz.
    Registration endpoint: if h < 32 or w < 32 → 422 "Muzzle crop too small"
    """
    import zlib, struct
    W, H = 64, 64
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    # Har satr: filter byte (0x00) + W*3 ta piksel (RGB)
    row  = b'\x00' + b'\x80\xA0\x60' * W
    raw  = row * H
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


class TestMuzzleRegistration:
    async def test_register_animal_not_found(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/registration/99999/register",
            headers=H(admin_token),
            files={"images": ("muzzle.png", io.BytesIO(make_tiny_png_bytes()), "image/png")},
        )
        assert r.status_code == 404

    async def test_register_no_images(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            f"/api/v1/registration/{sample_animal.id}/register",
            headers=H(admin_token),
        )
        assert r.status_code == 422

    async def test_register_success(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            f"/api/v1/registration/{sample_animal.id}/register",
            headers=H(admin_token),
            files={"images": ("muzzle.png", io.BytesIO(make_tiny_png_bytes()), "image/png")},
        )
        assert r.status_code in (200, 201, 503)

    async def test_no_token(self, client: AsyncClient, sample_animal):
        r = await client.post(
            f"/api/v1/registration/{sample_animal.id}/register",
            files={"images": ("muzzle.png", io.BytesIO(make_tiny_png_bytes()), "image/png")},
        )
        assert r.status_code == 401


class TestAnimalIdentification:
    async def test_identify_no_image(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/registration/identify", headers=H(admin_token))
        assert r.status_code == 422

    async def test_identify_with_image(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            "/api/v1/registration/identify",
            headers=H(admin_token),
            files={"file": ("muzzle.png", io.BytesIO(make_tiny_png_bytes()), "image/png")},
        )
        assert r.status_code in (200, 404, 503)


class TestEmbeddingsList:
    async def test_list_embeddings_not_found_animal(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/registration/99999/embeddings", headers=H(admin_token))
        assert r.status_code == 404

    async def test_list_embeddings_empty(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.get(
            f"/api/v1/registration/{sample_animal.id}/embeddings",
            headers=H(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) or "items" in data or "embeddings" in data


class TestDeleteEmbedding:
    async def test_delete_not_found(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.delete(
            f"/api/v1/registration/{sample_animal.id}/embeddings/99999",
            headers=H(admin_token),
        )
        assert r.status_code == 404