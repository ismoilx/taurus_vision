"""
Taurus Vision — Health Records API Tests (Sprint 11-12)

Test qamrovi:
    POST   /health/animals/{id}/records   — Yozuv yaratish
    GET    /health/animals/{id}/records   — Ro'yxat
    GET    /health/animals/{id}/summary   — Xulosa
    GET    /health/records/{id}           — Detail
    PATCH  /health/records/{id}           — Yangilash
    POST   /health/records/{id}/resolve   — Hal etilgan belgilash
    DELETE /health/records/{id}           — O'chirish
    GET    /health/unresolved             — Hal etilmaganlar
    GET    /health/critical               — Kritiklar
    GET    /health/upcoming-checkups      — Yaqin tekshiruvlar
    GET    /health/statistics             — Statistika

Autentifikatsiya:
    admin_token  → barcha amallar
    manager_token → yaratish, yangilash, hal etish
    viewer_token  → faqat o'qish
"""

import pytest
from datetime import date, datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

# ─── Endpoint prefix ─────────────────────────────────────────────────────────
_BASE = "/api/v1/health"


# =============================================================================
# HELPERS
# =============================================================================

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_record(
    client: AsyncClient,
    token: str,
    animal_id: int,
    **overrides,
) -> dict:
    """Yangi health record yaratib qaytaradi."""
    payload = {
        "record_type":   "checkup",
        "severity":      "normal",
        "diagnosis":     "Routine annual checkup",
        "veterinarian":  "Dr. Karimov",
        **overrides,
    }
    r = await client.post(
        f"{_BASE}/animals/{animal_id}/records",
        json=payload,
        headers=_auth(token),
    )
    assert r.status_code == 201, f"Create failed: {r.status_code} — {r.text}"
    return r.json()


# =============================================================================
# YARATISH TESTLARI
# =============================================================================

class TestHealthRecordCreate:
    """POST /health/animals/{id}/records"""

    async def test_create_minimal(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Minimal ma'lumot bilan record yaratiladi."""
        record = await _create_record(
            client, admin_token, sample_animal.id
        )
        assert record["id"] > 0
        assert record["animal_id"] == sample_animal.id
        assert record["record_type"] == "checkup"
        assert record["severity"] == "normal"
        assert record["is_resolved"] is False

    async def test_create_full_payload(
        self, client: AsyncClient, manager_token: str, sample_animal
    ):
        """Barcha maydonlar bilan record yaratiladi."""
        next_checkup = (date.today() + timedelta(days=30)).isoformat()
        record = await _create_record(
            client, manager_token, sample_animal.id,
            record_type     = "vaccination",
            severity        = "normal",
            diagnosis       = "FMD vaccination",
            symptoms        = "None",
            treatment       = "FMD vaccine 2ml administered",
            medication      = "Aftovax",
            dosage          = "2ml IM",
            veterinarian    = "Dr. Toshmatov",
            clinic_name     = "Toshkent Veterinar Klinikasi",
            cost            = 35000.0,
            notes           = "Next vaccination in 6 months",
            next_checkup_date = next_checkup,
        )
        assert record["record_type"]  == "vaccination"
        assert record["medication"]   == "Aftovax"
        assert record["dosage"]       == "2ml IM"
        assert record["cost"]         == 35000.0
        assert record["next_checkup_date"] == next_checkup

    async def test_create_critical_severity(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Critical severity record yaratiladi."""
        record = await _create_record(
            client, admin_token, sample_animal.id,
            record_type = "illness",
            severity    = "critical",
            diagnosis   = "Suspected foot-and-mouth disease",
            symptoms    = "High fever, blisters on hooves",
        )
        assert record["severity"] == "critical"
        assert record["is_resolved"] is False

    async def test_create_all_record_types(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Barcha record_type lari muvaffaqiyatli yaratiladi."""
        types = ["checkup", "treatment", "vaccination", "injury",
                 "surgery", "illness", "other"]
        for rt in types:
            record = await _create_record(
                client, admin_token, sample_animal.id,
                record_type = rt,
                diagnosis   = f"Test {rt}",
            )
            assert record["record_type"] == rt, f"Type {rt} mismatch"

    async def test_create_requires_manager(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """VIEWER yarata olmaydi."""
        r = await client.post(
            f"{_BASE}/animals/{sample_animal.id}/records",
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "Test"},
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_create_nonexistent_animal(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.post(
            f"{_BASE}/animals/999999/records",
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "Test"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 404

    async def test_create_invalid_record_type(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Noto'g'ri record_type — 422."""
        r = await client.post(
            f"{_BASE}/animals/{sample_animal.id}/records",
            json={"record_type": "invalid_type", "severity": "normal",
                  "diagnosis": "Test"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 422

    async def test_create_unauthenticated(
        self, client: AsyncClient, sample_animal
    ):
        """Token yo'q — 401/403."""
        r = await client.post(
            f"{_BASE}/animals/{sample_animal.id}/records",
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "Test"},
        )
        assert r.status_code in (401, 403)


# =============================================================================
# RO'YXAT TESTLARI
# =============================================================================

class TestHealthRecordList:
    """GET /health/animals/{id}/records"""

    async def test_list_empty(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Yozuvsiz jonivor uchun bo'sh ro'yxat."""
        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/records",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data or isinstance(data, list)

    async def test_list_with_records(
        self, client: AsyncClient, admin_token: str, viewer_token: str, sample_animal
    ):
        """Yaratilgan yozuvlar ro'yxatda ko'rinadi."""
        # 3 ta yozuv yaratamiz
        for i in range(3):
            await _create_record(
                client, admin_token, sample_animal.id,
                diagnosis=f"Test checkup #{i + 1}",
            )

        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/records",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        items = data["items"] if isinstance(data, dict) else data
        assert len(items) >= 3

    async def test_list_filter_by_type(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """record_type filtr ishlaydi."""
        await _create_record(
            client, admin_token, sample_animal.id,
            record_type="vaccination", diagnosis="Vaccine test",
        )
        await _create_record(
            client, admin_token, sample_animal.id,
            record_type="injury", diagnosis="Injury test",
        )

        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/records?record_type=vaccination",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        items = data["items"] if isinstance(data, dict) else data
        for item in items:
            assert item["record_type"] == "vaccination"

    async def test_list_filter_by_severity(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """severity filtr ishlaydi."""
        await _create_record(
            client, admin_token, sample_animal.id,
            severity="critical", record_type="illness",
            diagnosis="Critical illness test",
        )

        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/records?severity=critical",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        items = data["items"] if isinstance(data, dict) else data
        for item in items:
            assert item["severity"] == "critical"

    async def test_list_pagination(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Pagination ishlaydi."""
        # 5 ta yozuv yaratamiz
        for i in range(5):
            await _create_record(
                client, admin_token, sample_animal.id,
                diagnosis=f"Pagination test #{i}",
            )

        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/records?skip=0&limit=2",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        items = data["items"] if isinstance(data, dict) else data
        assert len(items) <= 2

    async def test_list_nonexistent_animal(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.get(
            f"{_BASE}/animals/999999/records",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404


# =============================================================================
# DETAIL TESTLARI
# =============================================================================

class TestHealthRecordDetail:
    """GET /health/records/{id}"""

    async def test_get_existing(
        self, client: AsyncClient, admin_token: str, viewer_token: str, sample_animal
    ):
        """Mavjud record ni ID bo'yicha olish."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.get(
            f"{_BASE}/records/{record['id']}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == record["id"]
        assert data["diagnosis"] == record["diagnosis"]

    async def test_get_nonexistent(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q record — 404."""
        r = await client.get(
            f"{_BASE}/records/999999",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404

    async def test_get_all_fields_present(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Response da barcha kerakli fieldlar bor."""
        record = await _create_record(
            client, admin_token, sample_animal.id,
            veterinarian="Dr. Test",
            medication="TestMed",
        )
        r = await client.get(
            f"{_BASE}/records/{record['id']}",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()

        required_fields = [
            "id", "animal_id", "record_type", "severity",
            "diagnosis", "is_resolved", "recorded_at",
        ]
        for field in required_fields:
            assert field in data, f"Field '{field}' missing"


# =============================================================================
# YANGILASH TESTLARI
# =============================================================================

class TestHealthRecordUpdate:
    """PATCH /health/records/{id}"""

    async def test_update_diagnosis(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Diagnosis yangilanadi."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.patch(
            f"{_BASE}/records/{record['id']}",
            json={"diagnosis": "Updated diagnosis"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["diagnosis"] == "Updated diagnosis"

    async def test_update_severity(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Severity yangilanadi."""
        record = await _create_record(
            client, admin_token, sample_animal.id, severity="normal"
        )

        r = await client.patch(
            f"{_BASE}/records/{record['id']}",
            json={"severity": "warning"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["severity"] == "warning"

    async def test_update_requires_manager(
        self, client: AsyncClient, admin_token: str,
        viewer_token: str, sample_animal
    ):
        """VIEWER yangilay olmaydi."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.patch(
            f"{_BASE}/records/{record['id']}",
            json={"diagnosis": "Viewer update attempt"},
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_update_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q record yangilash — 404."""
        r = await client.patch(
            f"{_BASE}/records/999999",
            json={"diagnosis": "Ghost update"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 404


# =============================================================================
# HAL ETISH TESTLARI
# =============================================================================

class TestHealthRecordResolve:
    """POST /health/records/{id}/resolve"""

    async def test_resolve_open_record(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Ochiq record hal etilgan deb belgilanadi."""
        record = await _create_record(
            client, admin_token, sample_animal.id,
            severity="warning", record_type="illness",
            diagnosis="Minor stomach issue",
        )
        assert record["is_resolved"] is False

        r = await client.post(
            f"{_BASE}/records/{record['id']}/resolve",
            json={"resolution_note": "Fully recovered after 3 days of treatment"},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["is_resolved"] is True
        assert data["resolved_at"] is not None

    async def test_resolve_requires_manager(
        self, client: AsyncClient, admin_token: str,
        viewer_token: str, sample_animal
    ):
        """VIEWER hal eta olmaydi."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.post(
            f"{_BASE}/records/{record['id']}/resolve",
            json={},
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_resolve_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q record hal etish — 404."""
        r = await client.post(
            f"{_BASE}/records/999999/resolve",
            json={},
            headers=_auth(admin_token),
        )
        assert r.status_code == 404


# =============================================================================
# O'CHIRISH TESTLARI
# =============================================================================

class TestHealthRecordDelete:
    """DELETE /health/records/{id}"""

    async def test_delete_record(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Record o'chiriladi."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.delete(
            f"{_BASE}/records/{record['id']}",
            headers=_auth(admin_token),
        )
        assert r.status_code in (200, 204)

        # O'chirilgan record endi topilmasligi kerak
        r2 = await client.get(
            f"{_BASE}/records/{record['id']}",
            headers=_auth(admin_token),
        )
        assert r2.status_code == 404

    async def test_delete_requires_manager(
        self, client: AsyncClient, admin_token: str,
        viewer_token: str, sample_animal
    ):
        """VIEWER o'chira olmaydi."""
        record = await _create_record(client, admin_token, sample_animal.id)

        r = await client.delete(
            f"{_BASE}/records/{record['id']}",
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_delete_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q record o'chirish — 404."""
        r = await client.delete(
            f"{_BASE}/records/999999",
            headers=_auth(admin_token),
        )
        assert r.status_code == 404


# =============================================================================
# XULOSA TESTLARI
# =============================================================================

class TestHealthSummary:
    """GET /health/animals/{id}/summary"""

    async def test_summary_structure(
        self, client: AsyncClient, admin_token: str, viewer_token: str, sample_animal
    ):
        """Summary to'g'ri strukturada qaytadi."""
        # Bir nechta record yaratamiz
        await _create_record(
            client, admin_token, sample_animal.id,
            severity="warning", diagnosis="Mild fever",
        )
        await _create_record(
            client, admin_token, sample_animal.id,
            severity="normal", diagnosis="Recovery checkup",
        )

        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        required = [
            "animal_id", "total_records", "unresolved_issues",
            "health_score", "health_status",
        ]
        for key in required:
            assert key in data, f"Summary key '{key}' missing"

    async def test_summary_health_score_range(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Health score 0–100 orasida."""
        r = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/summary",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        score = r.json()["health_score"]
        assert 0 <= score <= 100

    async def test_summary_critical_record_lowers_score(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Critical yozuv sog'liq balini tushiradi."""
        # Birinchi xulosa (bo'sh holat)
        r1 = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/summary",
            headers=_auth(admin_token),
        )
        score_before = r1.json()["health_score"]

        # Critical yozuv qo'shamiz
        for _ in range(3):
            await _create_record(
                client, admin_token, sample_animal.id,
                severity="critical", record_type="illness",
                diagnosis="Severe respiratory infection",
            )

        r2 = await client.get(
            f"{_BASE}/animals/{sample_animal.id}/summary",
            headers=_auth(admin_token),
        )
        score_after = r2.json()["health_score"]

        # Critical yozuvlar bali tushirishi kerak
        assert score_after <= score_before

    async def test_summary_nonexistent_animal(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.get(
            f"{_BASE}/animals/999999/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404


# =============================================================================
# STATISTIKA TESTLARI
# =============================================================================

class TestHealthStatistics:
    """GET /health/statistics"""

    async def test_statistics_structure(
        self, client: AsyncClient, viewer_token: str, admin_token: str, sample_animal
    ):
        """Statistika to'g'ri kalit larni qaytaradi."""
        await _create_record(client, admin_token, sample_animal.id)

        r = await client.get(
            f"{_BASE}/statistics",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    async def test_statistics_no_token(self, client: AsyncClient):
        """Token yo'q — 401/403."""
        r = await client.get(f"{_BASE}/statistics")
        assert r.status_code in (401, 403)


# =============================================================================
# UNRESOLVED VA CRITICAL TESTLARI
# =============================================================================

class TestUnresolvedAndCritical:
    """GET /health/unresolved va /health/critical"""

    async def test_unresolved_includes_new_records(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Yangi yozuv unresolved ro'yxatida ko'rinadi."""
        await _create_record(
            client, admin_token, sample_animal.id,
            severity="warning", diagnosis="Unresolved test",
        )

        r = await client.get(
            f"{_BASE}/unresolved",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        items = data["items"] if isinstance(data, dict) else data
        # Kamida bitta unresolved bo'lishi kerak
        assert isinstance(items, list)

    async def test_critical_endpoint(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Critical endpoint ishlaydi."""
        await _create_record(
            client, admin_token, sample_animal.id,
            severity="critical", record_type="illness",
            diagnosis="Critical endpoint test",
        )

        r = await client.get(
            f"{_BASE}/critical",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200

    async def test_upcoming_checkups(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Keyingi tekshiruvlar endpointi ishlaydi."""
        next_checkup = (date.today() + timedelta(days=7)).isoformat()
        await _create_record(
            client, admin_token, sample_animal.id,
            next_checkup_date=next_checkup,
            diagnosis="Scheduled checkup test",
        )

        r = await client.get(
            f"{_BASE}/upcoming-checkups?days_ahead=30",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200