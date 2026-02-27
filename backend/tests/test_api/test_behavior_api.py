"""
Taurus Vision — Behavior Analysis API Tests (Sprint 11-12)

Test qamrovi:
    GET  /behavior/{animal_id}            — Jonivor xatti-harakat tahlili
    POST /behavior/{animal_id}/analyze    — Darhol tahlil (MANAGER)
    GET  /behavior/herd/summary           — Poda xulosasi
    GET  /behavior/{animal_id}/timeline   — Vaqt chizig'i
    GET  /behavior/{animal_id}/anomalies  — Anomaliyalar ro'yxati

Detectionlar bo'lmasa — "critical/no_data" holati qaytadi.
Detectionlar bor bo'lsa — barcha ball va trend hisoblanadi.
"""

import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

_BASE = "/api/v1/behavior"


# =============================================================================
# HELPERS
# =============================================================================

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_detections(
    db: AsyncSession,
    animal_id: int,
    count: int = 30,
    hours_ago: int = 20,
    camera_id: str = "CAM-TEST-01",
) -> list:
    """Behavior tahlili uchun sintetik detectionlar yaratadi."""
    from app.models.detection import Detection
    import random

    now  = datetime.now(timezone.utc)
    recs = []

    for i in range(count):
        ts  = now - timedelta(minutes=int(hours_ago * 60 / count) * i)
        cx  = 0.2 + 0.3 * (i % 5) / 5  # Oziqlanish zonasiga yaqin
        cy  = 0.3 + 0.2 * (i % 3) / 3
        w   = 0.10 + random.random() * 0.05
        h   = 0.15 + random.random() * 0.05

        det = Detection(
            animal_id  = animal_id,
            camera_id  = camera_id,
            timestamp  = ts,
            confidence = 0.85 + random.random() * 0.10,
            class_id   = 0,
            bbox       = {"x": cx - w/2, "y": cy - h/2, "w": w, "h": h},
        )
        db.add(det)
        recs.append(det)

    await db.commit()
    return recs


# =============================================================================
# JONIVOR XATTI-HARAKAT TAHLILI
# =============================================================================

class TestAnimalBehavior:
    """GET /behavior/{animal_id}"""

    async def test_behavior_no_data(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Detectionlar bo'lmasa — critical holat, 200 OK."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["detection_count"]  == 0
        assert data["overall_status"]   == "critical"
        assert data["overall_score"]    == 0.0
        assert len(data["anomalies"])   >= 1

    async def test_behavior_response_structure(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Response barcha kerakli fieldlarni qaytaradi."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        top_level = [
            "animal_id", "animal_tag", "period_start", "period_end",
            "detection_count", "activity", "feeding", "movement", "social",
            "overall_score", "overall_status", "anomalies",
            "recommendations", "adi_trend", "adi_7day", "analyzed_at",
        ]
        for key in top_level:
            assert key in data, f"Missing key: '{key}'"

        # Har bir komponent uchun score strukturasi
        for comp in ("activity", "feeding", "movement", "social"):
            assert "value"       in data[comp], f"{comp}.value missing"
            assert "percentage"  in data[comp], f"{comp}.percentage missing"
            assert "status"      in data[comp], f"{comp}.status missing"
            assert "description" in data[comp], f"{comp}.description missing"

    async def test_behavior_with_detections(
        self, client: AsyncClient, viewer_token: str,
        admin_token: str, db: AsyncSession, sample_animal
    ):
        """Detectionlar mavjud bo'lganda — musbat natija."""
        await _seed_detections(db, sample_animal.id, count=40, hours_ago=20)

        r = await client.get(
            f"{_BASE}/{sample_animal.id}?hours=24",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        assert data["detection_count"] > 0
        assert data["activity"]["percentage"] > 0
        # Overall score 0 dan katta bo'lishi kerak
        assert data["overall_score"] > 0

    async def test_behavior_score_range(
        self, client: AsyncClient, viewer_token: str,
        db: AsyncSession, sample_animal
    ):
        """Barcha ball lar 0–100 orasida."""
        await _seed_detections(db, sample_animal.id, count=20)

        r = await client.get(
            f"{_BASE}/{sample_animal.id}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        assert 0 <= data["overall_score"] <= 100
        for comp in ("activity", "feeding", "movement", "social"):
            pct = data[comp]["percentage"]
            assert 0 <= pct <= 100, f"{comp}.percentage={pct} out of range"

    async def test_behavior_status_values(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Status faqat ruxsat etilgan qiymatlardan biri."""
        valid_statuses = {"excellent", "good", "fair", "poor", "critical"}

        r = await client.get(
            f"{_BASE}/{sample_animal.id}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        assert data["overall_status"] in valid_statuses
        for comp in ("activity", "feeding", "movement", "social"):
            assert data[comp]["status"] in valid_statuses

    async def test_behavior_hours_param(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """hours parametri ishlaydi."""
        for hours in [1, 12, 48, 168]:
            r = await client.get(
                f"{_BASE}/{sample_animal.id}?hours={hours}",
                headers=_auth(viewer_token),
            )
            assert r.status_code == 200, f"hours={hours} failed"

    async def test_behavior_hours_invalid(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Noto'g'ri hours — 422."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}?hours=0",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

        r = await client.get(
            f"{_BASE}/{sample_animal.id}?hours=200",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

    async def test_behavior_nonexistent_animal(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.get(
            f"{_BASE}/999999",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404

    async def test_behavior_requires_auth(
        self, client: AsyncClient, sample_animal
    ):
        """Token yo'q — 401/403."""
        r = await client.get(f"{_BASE}/{sample_animal.id}")
        assert r.status_code in (401, 403)

    async def test_behavior_animal_tag_correct(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """animal_tag to'g'ri qaytadi."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        assert r.json()["animal_tag"] == sample_animal.tag_id


# =============================================================================
# DARHOL TAHLIL (MANAGER)
# =============================================================================

class TestTriggerBehaviorAnalysis:
    """POST /behavior/{animal_id}/analyze"""

    async def test_trigger_returns_analysis(
        self, client: AsyncClient, manager_token: str, sample_animal
    ):
        """POST trigger GET bilan bir xil strukturani qaytaradi."""
        r = await client.post(
            f"{_BASE}/{sample_animal.id}/analyze",
            headers=_auth(manager_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "overall_score" in data
        assert data["animal_id"] == sample_animal.id

    async def test_trigger_requires_manager(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """VIEWER trigger yubora olmaydi."""
        r = await client.post(
            f"{_BASE}/{sample_animal.id}/analyze",
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_trigger_nonexistent_animal(
        self, client: AsyncClient, manager_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.post(
            f"{_BASE}/999999/analyze",
            headers=_auth(manager_token),
        )
        assert r.status_code == 404


# =============================================================================
# PODA XULOSASI
# =============================================================================

class TestHerdSummary:
    """GET /behavior/herd/summary"""

    async def test_herd_summary_structure(
        self, client: AsyncClient, viewer_token: str
    ):
        """Poda xulosasi to'g'ri strukturada."""
        r = await client.get(
            f"{_BASE}/herd/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        required = [
            "total_animals", "analyzed_count", "period",
            "excellent_count", "good_count", "fair_count",
            "poor_count", "critical_count", "no_data_count",
            "avg_activity", "avg_feeding", "avg_movement",
            "avg_social", "avg_overall", "attention_needed",
            "generated_at",
        ]
        for key in required:
            assert key in data, f"Herd summary key '{key}' missing"

    async def test_herd_summary_counts_consistent(
        self, client: AsyncClient, viewer_token: str
    ):
        """Sanlar izchil — jami = tahlil qilingan + ma'lumot yo'q."""
        r = await client.get(
            f"{_BASE}/herd/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        status_total = (
            data["excellent_count"] + data["good_count"] +
            data["fair_count"]      + data["poor_count"] +
            data["critical_count"]
        )
        assert status_total == data["analyzed_count"]
        assert data["analyzed_count"] + data["no_data_count"] == data["total_animals"]

    async def test_herd_summary_avg_scores_range(
        self, client: AsyncClient, viewer_token: str
    ):
        """O'rtacha ballar 0–100 orasida."""
        r = await client.get(
            f"{_BASE}/herd/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        for key in ("avg_activity", "avg_feeding", "avg_movement",
                    "avg_social", "avg_overall"):
            val = data[key]
            assert 0 <= val <= 100, f"{key}={val} out of range"

    async def test_herd_summary_hours_param(
        self, client: AsyncClient, viewer_token: str
    ):
        """hours parametri ishlaydi."""
        r = await client.get(
            f"{_BASE}/herd/summary?hours=12",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200

    async def test_herd_summary_invalid_hours(
        self, client: AsyncClient, viewer_token: str
    ):
        """Noto'g'ri hours — 422."""
        r = await client.get(
            f"{_BASE}/herd/summary?hours=100",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

    async def test_herd_summary_attention_needed_structure(
        self, client: AsyncClient, viewer_token: str, db: AsyncSession, sample_animal
    ):
        """attention_needed ro'yxatidagi ob'ektlar to'g'ri tuzilgan."""
        r = await client.get(
            f"{_BASE}/herd/summary",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        for item in data["attention_needed"]:
            assert "animal_id"     in item
            assert "animal_tag"    in item
            assert "overall_score" in item
            assert "status"        in item


# =============================================================================
# VAQT CHIZIG'I
# =============================================================================

class TestBehaviorTimeline:
    """GET /behavior/{animal_id}/timeline"""

    async def test_timeline_empty(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Detectionlar yo'q — bo'sh ro'yxat."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/timeline",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_timeline_with_detections(
        self, client: AsyncClient, viewer_token: str,
        db: AsyncSession, sample_animal
    ):
        """Detectionlar mavjud — soatlik yozuvlar."""
        await _seed_detections(db, sample_animal.id, count=50, hours_ago=24)

        r = await client.get(
            f"{_BASE}/{sample_animal.id}/timeline?hours=24",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_timeline_entry_structure(
        self, client: AsyncClient, viewer_token: str,
        db: AsyncSession, sample_animal
    ):
        """Timeline entry to'g'ri fieldlarga ega."""
        await _seed_detections(db, sample_animal.id, count=10, hours_ago=3)

        r = await client.get(
            f"{_BASE}/{sample_animal.id}/timeline?hours=6",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        if data:
            entry = data[0]
            assert "hour"           in entry
            assert "detections"     in entry
            assert "feeding_visits" in entry
            assert "movement_score" in entry

    async def test_timeline_sorted_chronologically(
        self, client: AsyncClient, viewer_token: str,
        db: AsyncSession, sample_animal
    ):
        """Timeline xronologik tartibda."""
        await _seed_detections(db, sample_animal.id, count=30, hours_ago=24)

        r = await client.get(
            f"{_BASE}/{sample_animal.id}/timeline?hours=24",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        if len(data) > 1:
            hours = [e["hour"] for e in data]
            assert hours == sorted(hours), "Timeline tartibsiz"

    async def test_timeline_hours_minimum(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Minimum 6 soat talab etiladi."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/timeline?hours=3",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

    async def test_timeline_nonexistent_animal(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.get(
            f"{_BASE}/999999/timeline",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404


# =============================================================================
# ANOMALIYALAR
# =============================================================================

class TestBehaviorAnomalies:
    """GET /behavior/{animal_id}/anomalies"""

    async def test_anomalies_no_detections(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Detectionlar yo'q — anomaliya qaytadi."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Detectionlar yo'q — kamida bitta anomaliya bo'lishi kutiladi
        assert len(data) >= 1

    async def test_anomaly_structure(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Anomaliya ob'ekti to'g'ri fieldlarga ega."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        data = r.json()

        if data:
            entry = data[0]
            assert "type"        in entry
            assert "severity"    in entry
            assert "description" in entry
            assert "detected_at" in entry

    async def test_anomaly_severity_values(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Severity faqat ruxsat etilgan qiymatlar."""
        valid = {"warning", "critical"}

        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200
        for item in r.json():
            assert item["severity"] in valid

    async def test_anomalies_days_param(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """days parametri ishlaydi."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies?days=3",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 200

    async def test_anomalies_invalid_days(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        """Noto'g'ri days — 422."""
        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies?days=0",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

        r = await client.get(
            f"{_BASE}/{sample_animal.id}/anomalies?days=100",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 422

    async def test_anomalies_nonexistent_animal(
        self, client: AsyncClient, viewer_token: str
    ):
        """Yo'q jonivor — 404."""
        r = await client.get(
            f"{_BASE}/999999/anomalies",
            headers=_auth(viewer_token),
        )
        assert r.status_code == 404

    async def test_anomalies_requires_auth(
        self, client: AsyncClient, sample_animal
    ):
        """Token yo'q — 401/403."""
        r = await client.get(f"{_BASE}/{sample_animal.id}/anomalies")
        assert r.status_code in (401, 403)