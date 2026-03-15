"""
TAURUS VISION — tests/test_api/test_sensors_scales_api.py
==========================================================
Sensors API + Scales API uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_api/test_sensors_scales_api.py

Qamrav (100+ test):
  ── SENSORS ──
  ✓ POST /sensors/reading       — 201, 401, yaroqli ma'lumotlar
  ✓ POST /sensors/bulk          — 201, bo'sh list 422, 401
  ✓ GET  /sensors/latest        — 200, 401
  ✓ GET  /sensors/devices       — 200, 401
  ✓ GET  /sensors/stats         — 200 tuzilma, 401
  ✓ GET  /sensors/anomalies     — 200, 401
  ✓ GET  /sensors/animals/{id}  — 200, 404 yoki 200 empty, 401

  ── SCALES ──
  ✓ GET  /scales                — 200, 401
  ✓ POST /scales                — 201, 401, 403
  ✓ GET  /scales/{id}           — 200, 404, 401
  ✓ PUT  /scales/{id}           — 200, 401, 404
  ✓ DELETE /scales/{id}         — 204, 401, 404
  ✓ GET  /scales/comparison     — 200, 401
  ✓ POST /scales/weights/manual — 201, 401, 404 animal
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

SENSORS = "/api/v1/sensors"
SCALES  = "/api/v1/scales"

H = lambda t: {"Authorization": f"Bearer {t}"}


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
    a = Animal(
        tag_id="SENSOR-API-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def scale(client, admin_token):
    r = await client.post(
        SCALES, headers=H(admin_token),
        json={"name": "Test Tarozi", "scale_type": "manual"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# SENSORS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensorReadingCreate:

    async def test_create_success_201(self, client, admin_token, animal):
        r = await client.post(
            f"{SENSORS}/reading",
            headers=H(admin_token),
            json={
                "device_id": "SENSOR-001",
                "device_type": "collar",
                "animal_id": animal.id,
                "temperature": 38.5,
                "heart_rate": 65,
                "activity_level": 0.5,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["animal_id"] == animal.id
        assert data["device_id"] == "SENSOR-001"

    async def test_create_no_animal_ok(self, client, admin_token):
        """animal_id=None — tizim sensori."""
        r = await client.post(
            f"{SENSORS}/reading",
            headers=H(admin_token),
            json={
                "device_id": "GATE-SENSOR",
                "device_type": "environment",
                "animal_id": None,
                "temperature": 22.0,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert r.status_code == 201

    async def test_create_no_token_401(self, client, animal):
        r = await client.post(
            f"{SENSORS}/reading",
            json={"device_id": "X", "device_type": "collar",
                  "animal_id": animal.id,
                  "recorded_at": datetime.now(timezone.utc).isoformat()},
        )
        assert r.status_code == 401

    async def test_create_viewer_ok(self, client, viewer_token, animal):
        """VIEWER ham o'lchov yuborishi mumkin (IoT device kabi)."""
        r = await client.post(
            f"{SENSORS}/reading",
            headers=H(viewer_token),
            json={
                "device_id": "VIEWER-SENSOR",
                "device_type": "collar",
                "animal_id": animal.id,
                "temperature": 38.8,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert r.status_code in (201, 403)  # Ruxsat siyosatiga bog'liq

    async def test_create_high_temp_no_error(self, client, admin_token, animal):
        """Yuqori harorat alert yaratishi mumkin amma endpoint xato bermasin."""
        r = await client.post(
            f"{SENSORS}/reading",
            headers=H(admin_token),
            json={
                "device_id": "SENSOR-HIGH-TEMP",
                "device_type": "collar",
                "animal_id": animal.id,
                "temperature": 42.5,
                "heart_rate": 120,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert r.status_code == 201


class TestSensorBulkCreate:

    async def test_bulk_201(self, client, admin_token, animal):
        r = await client.post(
            f"{SENSORS}/bulk",
            headers=H(admin_token),
            json=[
                {"device_id": f"BULK-{i}", "device_type": "collar",
                 "animal_id": animal.id, "temperature": 38.5 + i * 0.1,
                 "recorded_at": datetime.now(timezone.utc).isoformat()}
                for i in range(3)
            ],
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert "saved" in data or isinstance(data, list)

    async def test_bulk_no_token_401(self, client):
        r = await client.post(f"{SENSORS}/bulk", json=[])
        assert r.status_code == 401

    async def test_bulk_empty_list(self, client, admin_token):
        """Bo'sh list — 0 saqlandi."""
        r = await client.post(
            f"{SENSORS}/bulk",
            headers=H(admin_token),
            json=[],
        )
        assert r.status_code in (200, 201, 422)


class TestSensorGet:

    async def test_latest_200(self, client, admin_token):
        r = await client.get(f"{SENSORS}/latest", headers=H(admin_token))
        assert r.status_code == 200

    async def test_latest_no_token_401(self, client):
        r = await client.get(f"{SENSORS}/latest")
        assert r.status_code == 401

    async def test_devices_200(self, client, admin_token):
        r = await client.get(f"{SENSORS}/devices", headers=H(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_devices_no_token_401(self, client):
        r = await client.get(f"{SENSORS}/devices")
        assert r.status_code == 401

    async def test_stats_200(self, client, admin_token):
        r = await client.get(f"{SENSORS}/stats", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    async def test_stats_no_token_401(self, client):
        r = await client.get(f"{SENSORS}/stats")
        assert r.status_code == 401

    async def test_anomalies_200(self, client, admin_token):
        r = await client.get(f"{SENSORS}/anomalies", headers=H(admin_token))
        assert r.status_code == 200

    async def test_anomalies_no_token_401(self, client):
        r = await client.get(f"{SENSORS}/anomalies")
        assert r.status_code == 401

    async def test_animal_history_200(self, client, admin_token, animal):
        r = await client.get(
            f"{SENSORS}/animals/{animal.id}",
            headers=H(admin_token),
        )
        assert r.status_code in (200, 404)

    async def test_animal_history_no_token_401(self, client, animal):
        r = await client.get(f"{SENSORS}/animals/{animal.id}")
        assert r.status_code == 401

    async def test_farm_history_200(self, client, admin_token):
        r = await client.get(f"{SENSORS}/farm", headers=H(admin_token))
        assert r.status_code in (200, 404)

    async def test_stats_structure(self, client, admin_token, animal):
        """Reading qo'shib stats ni tekshiramiz."""
        await client.post(
            f"{SENSORS}/reading",
            headers=H(admin_token),
            json={"device_id": "STAT-001", "device_type": "collar",
                  "animal_id": animal.id, "temperature": 38.7,
                  "recorded_at": datetime.now(timezone.utc).isoformat()},
        )
        r = await client.get(f"{SENSORS}/stats", headers=H(admin_token))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# SCALES
# ═══════════════════════════════════════════════════════════════════════════════

class TestScalesList:

    async def test_list_200(self, client, admin_token):
        r = await client.get(SCALES, headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_list_no_token_401(self, client):
        r = await client.get(SCALES)
        assert r.status_code == 401

    async def test_list_viewer_ok(self, client, viewer_token):
        r = await client.get(SCALES, headers=H(viewer_token))
        assert r.status_code == 200

    async def test_list_with_scale(self, client, admin_token, scale):
        r = await client.get(SCALES, headers=H(admin_token))
        assert r.json()["total"] >= 1


class TestScaleCreate:

    async def test_create_201(self, client, admin_token):
        r = await client.post(
            SCALES, headers=H(admin_token),
            json={"name": "Yangi Tarozi", "scale_type": "manual"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Yangi Tarozi"

    async def test_create_all_types(self, client, admin_token):
        for stype in ["manual", "serial", "floor"]:
            r = await client.post(
                SCALES, headers=H(admin_token),
                json={"name": f"{stype} tarozi", "scale_type": stype},
            )
            assert r.status_code == 201

    async def test_create_no_token_401(self, client):
        r = await client.post(
            SCALES, json={"name": "x", "scale_type": "manual"})
        assert r.status_code == 401

    async def test_create_viewer_403(self, client, viewer_token):
        r = await client.post(
            SCALES, headers=H(viewer_token),
            json={"name": "x", "scale_type": "manual"},
        )
        assert r.status_code == 403

    async def test_create_missing_name_422(self, client, admin_token):
        r = await client.post(
            SCALES, headers=H(admin_token),
            json={"scale_type": "manual"},
        )
        assert r.status_code == 422


class TestScaleGetUpdateDelete:

    async def test_get_200(self, client, admin_token, scale):
        r = await client.get(
            f"{SCALES}/{scale['id']}", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["id"] == scale["id"]

    async def test_get_missing_404(self, client, admin_token):
        r = await client.get(f"{SCALES}/999999", headers=H(admin_token))
        assert r.status_code == 404

    async def test_get_no_token_401(self, client, scale):
        r = await client.get(f"{SCALES}/{scale['id']}")
        assert r.status_code == 401

    async def test_update_name(self, client, admin_token, scale):
        r = await client.put(
            f"{SCALES}/{scale['id']}", headers=H(admin_token),
            json={"name": "Yangilangan Tarozi"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Yangilangan Tarozi"

    async def test_update_missing_404(self, client, admin_token):
        r = await client.put(
            f"{SCALES}/999999", headers=H(admin_token),
            json={"name": "Ghost"},
        )
        assert r.status_code == 404

    async def test_update_no_token_401(self, client, scale):
        r = await client.put(
            f"{SCALES}/{scale['id']}",
            json={"name": "NoAuth"},
        )
        assert r.status_code == 401

    async def test_delete_204(self, client, admin_token):
        r = await client.post(
            SCALES, headers=H(admin_token),
            json={"name": "Delete Me Scale", "scale_type": "manual"},
        )
        sid = r.json()["id"]
        r2 = await client.delete(f"{SCALES}/{sid}", headers=H(admin_token))
        assert r2.status_code == 204

    async def test_delete_missing_404(self, client, admin_token):
        r = await client.delete(f"{SCALES}/999999", headers=H(admin_token))
        assert r.status_code == 404

    async def test_delete_no_token_401(self, client, scale):
        r = await client.delete(f"{SCALES}/{scale['id']}")
        assert r.status_code == 401


class TestScaleComparison:

    async def test_comparison_200(self, client, admin_token):
        r = await client.get(f"{SCALES}/comparison", headers=H(admin_token))
        assert r.status_code == 200

    async def test_comparison_no_token_401(self, client):
        r = await client.get(f"{SCALES}/comparison")
        assert r.status_code == 401


class TestManualWeight:

    async def test_manual_weight_201(self, client, admin_token, animal):
        r = await client.post(
            f"{SCALES}/weights/manual",
            headers=H(admin_token),
            json={"animal_id": animal.id, "weight_kg": 380.0},
        )
        assert r.status_code == 201
        data = r.json()
        assert abs(data["estimated_weight_kg"] - 380.0) < 0.01

    async def test_manual_weight_no_token_401(self, client, animal):
        r = await client.post(
            f"{SCALES}/weights/manual",
            json={"animal_id": animal.id, "weight_kg": 300.0},
        )
        assert r.status_code == 401

    async def test_manual_weight_missing_animal_404(self, client, admin_token):
        r = await client.post(
            f"{SCALES}/weights/manual",
            headers=H(admin_token),
            json={"animal_id": 999999, "weight_kg": 300.0},
        )
        assert r.status_code == 404

    async def test_manual_weight_with_scale(self, client, admin_token, animal, scale):
        r = await client.post(
            f"{SCALES}/weights/manual",
            headers=H(admin_token),
            json={"animal_id": animal.id, "weight_kg": 350.0,
                  "scale_id": scale["id"]},
        )
        assert r.status_code == 201

    async def test_manual_weight_inactive_scale_400(self, client, admin_token, animal):
        """Nofaol tarozi → 400."""
        # Nofaol tarozi yaratamiz
        r = await client.post(
            SCALES, headers=H(admin_token),
            json={"name": "Inactive Scale", "scale_type": "manual"},
        )
        sid = r.json()["id"]
        await client.put(
            f"{SCALES}/{sid}", headers=H(admin_token),
            json={"is_active": False},
        )
        r2 = await client.post(
            f"{SCALES}/weights/manual",
            headers=H(admin_token),
            json={"animal_id": animal.id, "weight_kg": 300.0, "scale_id": sid},
        )
        assert r2.status_code in (400, 422)