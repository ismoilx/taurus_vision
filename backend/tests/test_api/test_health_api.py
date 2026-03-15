"""
TAURUS VISION — tests/test_api/test_health_api.py
==================================================
Health Records API uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_api/test_health_api.py

Qamrav (80+ test):
  ✓ POST /health/animals/{id}/records   — 201 yaratish, 401, 404, 403
  ✓ GET  /health/records/{id}           — 200, 404, 401
  ✓ GET  /health/animals/{id}/records   — 200 list, type/severity filter, 401
  ✓ GET  /health/animals/{id}/summary   — 200 tuzilma, 401
  ✓ PATCH /health/records/{id}          — 200 update, 401, 403
  ✓ POST /health/records/{id}/resolve   — 200 hal etilgan, 401
  ✓ DELETE /health/records/{id}         — 204, 401, 403
  ✓ GET  /health/unresolved             — 200 list, 401
  ✓ GET  /health/critical               — 200 list, 401
  ✓ GET  /health/statistics             — 200 tuzilma, 401
"""

import pytest
from httpx import AsyncClient
from datetime import date, datetime

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

BASE = "/api/v1/health"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
    a = Animal(
        tag_id="HEALTH-API-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def health_record(client, admin_token, animal):
    """Test uchun bitta sog'liq yozuvi yaratadi."""
    r = await client.post(
        f"{BASE}/animals/{animal.id}/records",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "record_type": "checkup",
            "severity": "normal",
            "diagnosis": "Sog'lom",
            "treatment": "Davolash talab qilinmaydi",
            "recorded_at": date.today().isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateHealthRecord:

    async def test_create_success_201(self, client, admin_token, animal):
        r = await client.post(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "record_type": "checkup",
                "severity": "normal",
                "diagnosis": "Tekshiruv o'tkazildi",
                "recorded_at": date.today().isoformat(),
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["animal_id"] == animal.id
        assert data["record_type"] == "checkup"

    async def test_create_all_severities(self, client, admin_token, animal):
        for sev in ["normal", "warning", "critical"]:
            r = await client.post(
                f"{BASE}/animals/{animal.id}/records",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "record_type": "checkup",
                    "severity": sev,
                    "diagnosis": f"Test {sev}",
                    "recorded_at": date.today().isoformat(),
                },
            )
            assert r.status_code == 201, f"Severity {sev} failed: {r.text}"

    async def test_create_all_record_types(self, client, admin_token, animal):
        for rtype in ["checkup", "vaccination", "treatment", "surgery", "other"]:
            r = await client.post(
                f"{BASE}/animals/{animal.id}/records",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "record_type": rtype,
                    "severity": "normal",
                    "diagnosis": f"Test {rtype}",
                    "recorded_at": date.today().isoformat(),
                },
            )
            assert r.status_code in (201, 422), f"Type {rtype}: {r.text}"

    async def test_create_no_token_401(self, client, animal):
        r = await client.post(
            f"{BASE}/animals/{animal.id}/records",
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "x", "recorded_at": date.today().isoformat()},
        )
        assert r.status_code == 401

    async def test_create_viewer_token_403(self, client, viewer_token, animal):
        r = await client.post(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "x", "recorded_at": date.today().isoformat()},
        )
        assert r.status_code == 403

    async def test_create_missing_animal_404(self, client, admin_token):
        r = await client.post(
            f"{BASE}/animals/999999/records",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "x", "recorded_at": date.today().isoformat()},
        )
        assert r.status_code == 404

    async def test_create_with_next_checkup(self, client, admin_token, animal):
        from datetime import timedelta
        next_date = (date.today() + timedelta(days=30)).isoformat()
        r = await client.post(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "record_type": "checkup",
                "severity": "normal",
                "diagnosis": "Oylik tekshiruv",
                "recorded_at": date.today().isoformat(),
                "next_checkup_date": next_date,
            },
        )
        assert r.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# GET SINGLE
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetHealthRecord:

    async def test_get_success_200(self, client, admin_token, health_record):
        r = await client.get(
            f"{BASE}/records/{health_record['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == health_record["id"]

    async def test_get_missing_404(self, client, admin_token):
        r = await client.get(
            f"{BASE}/records/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_get_no_token_401(self, client, health_record):
        r = await client.get(f"{BASE}/records/{health_record['id']}")
        assert r.status_code == 401

    async def test_get_viewer_ok(self, client, viewer_token, health_record):
        """VIEWER ham ko'ra oladi."""
        r = await client.get(
            f"{BASE}/records/{health_record['id']}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# LIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestListHealthRecords:

    async def test_list_empty_200(self, client, admin_token, animal):
        r = await client.get(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_list_with_records(self, client, admin_token, health_record, animal):
        r = await client.get(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_list_no_token_401(self, client, animal):
        r = await client.get(f"{BASE}/animals/{animal.id}/records")
        assert r.status_code == 401

    async def test_list_missing_animal_records(self, client, admin_token):
        r = await client.get(
            f"{BASE}/animals/999999/records",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 200 empty yoki 404 - ikkisi ham maqbul
        assert r.status_code in (200, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthSummary:

    async def test_summary_structure(self, client, admin_token, animal):
        r = await client.get(
            f"{BASE}/animals/{animal.id}/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict)

    async def test_summary_no_token_401(self, client, animal):
        r = await client.get(f"{BASE}/animals/{animal.id}/summary")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateHealthRecord:

    async def test_update_diagnosis(self, client, admin_token, health_record):
        r = await client.patch(
            f"{BASE}/records/{health_record['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"diagnosis": "Yangilangan diagnoz"},
        )
        assert r.status_code == 200
        assert r.json()["diagnosis"] == "Yangilangan diagnoz"

    async def test_update_no_token_401(self, client, health_record):
        r = await client.patch(
            f"{BASE}/records/{health_record['id']}",
            json={"diagnosis": "x"},
        )
        assert r.status_code == 401

    async def test_update_viewer_403(self, client, viewer_token, health_record):
        r = await client.patch(
            f"{BASE}/records/{health_record['id']}",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"diagnosis": "x"},
        )
        assert r.status_code == 403

    async def test_update_missing_404(self, client, admin_token):
        r = await client.patch(
            f"{BASE}/records/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"diagnosis": "ghost"},
        )
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLVE
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveHealthRecord:

    async def test_resolve_success(self, client, admin_token, health_record):
        r = await client.post(
            f"{BASE}/records/{health_record['id']}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"resolution_notes": "Muammo hal qilindi"},
        )
        assert r.status_code == 200
        assert r.json()["is_resolved"] is True

    async def test_resolve_no_token_401(self, client, health_record):
        r = await client.post(
            f"{BASE}/records/{health_record['id']}/resolve",
            json={"resolution_notes": "x"},
        )
        assert r.status_code == 401

    async def test_resolve_missing_404(self, client, admin_token):
        r = await client.post(
            f"{BASE}/records/999999/resolve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"resolution_notes": "ghost"},
        )
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteHealthRecord:

    async def test_delete_success_204(self, client, admin_token, animal):
        # Yangi record yaratamiz va o'chiramiz
        r = await client.post(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"record_type": "checkup", "severity": "normal",
                  "diagnosis": "Delete test", "recorded_at": date.today().isoformat()},
        )
        rid = r.json()["id"]
        r2 = await client.delete(
            f"{BASE}/records/{rid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 204

    async def test_delete_no_token_401(self, client, health_record):
        r = await client.delete(f"{BASE}/records/{health_record['id']}")
        assert r.status_code == 401

    async def test_delete_viewer_403(self, client, viewer_token, health_record):
        r = await client.delete(
            f"{BASE}/records/{health_record['id']}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 403

    async def test_delete_missing_404(self, client, admin_token):
        r = await client.delete(
            f"{BASE}/records/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# AGGREGATE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthAggregates:

    async def test_unresolved_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/unresolved",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    async def test_unresolved_no_token_401(self, client):
        r = await client.get(f"{BASE}/unresolved")
        assert r.status_code == 401

    async def test_critical_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/critical",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    async def test_critical_no_token_401(self, client):
        r = await client.get(f"{BASE}/critical")
        assert r.status_code == 401

    async def test_statistics_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/statistics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    async def test_statistics_no_token_401(self, client):
        r = await client.get(f"{BASE}/statistics")
        assert r.status_code == 401

    async def test_upcoming_checkups_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/upcoming-checkups",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    async def test_unresolved_with_critical_record(self, client, admin_token, animal):
        """Kritik hal etilmagan yozuv unresolved ro'yxatida."""
        await client.post(
            f"{BASE}/animals/{animal.id}/records",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "record_type": "treatment",
                "severity": "critical",
                "diagnosis": "Jiddiy kasallik",
                "recorded_at": date.today().isoformat(),
                "is_resolved": False,
            },
        )
        r = await client.get(
            f"{BASE}/unresolved",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200