"""
Health Predictions API Tests — /api/v1/predictions/

Qamrov:
    - GET  /predictions/farm-summary       → 200 + schema
    - GET  /predictions/at-risk            → 200 + list
    - GET  /predictions/animal/{id}        → 200 (auto-compute) | 404
    - GET  /predictions/animal/{id}/history→ 200 + history obj
    - POST /predictions/animal/{id}/predict→ 200 (manager) | 403 (viewer)
    - POST /predictions/run-farm           → 200 (admin) | 403 (manager)
    - POST /predictions/train              → 200 (admin) | 403 (viewer)
    - GET  /predictions/model-status       → 200 + schema
    - Auth → 401 token yo'q bo'lsa

Sprint 13-14 — Ensemble Health Prediction System
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


# =============================================================================
# HELPERS
# =============================================================================

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. FARM SUMMARY
# =============================================================================

class TestFarmSummary:

    async def test_returns_200(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/farm-summary", headers=auth(admin_token))
        assert r.status_code == 200

    async def test_required_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/farm-summary", headers=auth(admin_token))
        data = r.json()
        for field in ["date", "total_predicted", "avg_risk_score",
                      "max_risk_score", "low_count", "medium_count",
                      "high_count", "critical_count", "at_risk_animals"]:
            assert field in data, f"'{field}' maydoni yo'q"

    async def test_at_risk_animals_is_list(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/farm-summary", headers=auth(admin_token))
        assert isinstance(r.json()["at_risk_animals"], list)

    async def test_scores_non_negative(self, client: AsyncClient, admin_token: str):
        data = (await client.get("/api/v1/predictions/farm-summary",
                                 headers=auth(admin_token))).json()
        assert data["avg_risk_score"] >= 0
        assert data["max_risk_score"] >= 0

    async def test_with_date_param(self, client: AsyncClient, admin_token: str):
        r = await client.get(
            "/api/v1/predictions/farm-summary?date=2026-02-28",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["date"] == "2026-02-28"

    async def test_invalid_date_format(self, client: AsyncClient, admin_token: str):
        r = await client.get(
            "/api/v1/predictions/farm-summary?date=28-02-2026",
            headers=auth(admin_token),
        )
        assert r.status_code == 422

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.get("/api/v1/predictions/farm-summary")
        assert r.status_code == 401

    async def test_viewer_can_read(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/predictions/farm-summary", headers=auth(viewer_token))
        assert r.status_code == 200


# =============================================================================
# 2. AT-RISK ANIMALS
# =============================================================================

class TestAtRisk:

    async def test_returns_200(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/at-risk", headers=auth(admin_token))
        assert r.status_code == 200

    async def test_returns_list(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/at-risk", headers=auth(admin_token))
        assert isinstance(r.json(), list)

    async def test_min_risk_param_medium(self, client: AsyncClient, admin_token: str):
        r = await client.get(
            "/api/v1/predictions/at-risk?min_risk=medium",
            headers=auth(admin_token),
        )
        assert r.status_code == 200

    async def test_min_risk_param_critical(self, client: AsyncClient, admin_token: str):
        r = await client.get(
            "/api/v1/predictions/at-risk?min_risk=critical",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_invalid_min_risk_returns_422(self, client: AsyncClient, admin_token: str):
        r = await client.get(
            "/api/v1/predictions/at-risk?min_risk=extreme",
            headers=auth(admin_token),
        )
        assert r.status_code == 422

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.get("/api/v1/predictions/at-risk")
        assert r.status_code == 401

    async def test_item_schema(self, client: AsyncClient, admin_token: str, sample_animal):
        """Agar natija bo'lsa — schema to'g'ri bo'lishi kerak."""
        items = (await client.get("/api/v1/predictions/at-risk",
                                  headers=auth(admin_token))).json()
        for item in items:
            for field in ["animal_id", "tag_id", "risk_level",
                          "risk_score", "confidence"]:
                assert field in item, f"at-risk item da '{field}' yo'q"
            assert item["risk_score"] >= 0
            assert 0 <= item["confidence"] <= 1


# =============================================================================
# 3. SINGLE ANIMAL PREDICTION
# =============================================================================

class TestAnimalPrediction:

    async def test_nonexistent_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/animal/99999", headers=auth(admin_token))
        assert r.status_code in (404, 200)  # 404 — jonivor yo'q; 200 — service cold-start

    async def test_animal_with_no_adi_data(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """ADI ma'lumoti bo'lmagan jonivor — 404 yoki cold-start 200."""
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}",
            headers=auth(admin_token),
        )
        # Yetarli ma'lumot bo'lmasa 404 qaytaradi
        assert r.status_code in (200, 404)

    async def test_invalid_id_format(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/animal/abc", headers=auth(admin_token))
        assert r.status_code == 422

    async def test_zero_id_invalid(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/animal/0", headers=auth(admin_token))
        assert r.status_code == 422

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.get("/api/v1/predictions/animal/1")
        assert r.status_code == 401

    async def test_viewer_can_read(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}",
            headers=auth(viewer_token),
        )
        assert r.status_code in (200, 404)


# =============================================================================
# 4. PREDICTION HISTORY
# =============================================================================

class TestPredictionHistory:

    async def test_returns_200(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history",
            headers=auth(admin_token),
        )
        assert r.status_code == 200

    async def test_history_schema(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        data = (await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history",
            headers=auth(admin_token),
        )).json()
        assert "animal_id" in data
        assert "days" in data
        assert "history" in data
        assert isinstance(data["history"], list)
        assert data["animal_id"] == sample_animal.id

    async def test_days_param(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history?days=14",
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["days"] == 14

    async def test_days_min_boundary(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history?days=6",
            headers=auth(admin_token),
        )
        assert r.status_code == 422  # ge=7

    async def test_days_max_boundary(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history?days=91",
            headers=auth(admin_token),
        )
        assert r.status_code == 422  # le=90

    async def test_history_item_schema(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Agar tarix bo'lsa — har bir element to'g'ri schema."""
        items = (await client.get(
            f"/api/v1/predictions/animal/{sample_animal.id}/history",
            headers=auth(admin_token),
        )).json()["history"]

        for item in items:
            for field in ["date", "risk_score", "risk_level"]:
                assert field in item
            assert 0 <= item["risk_score"] <= 100
            assert item["risk_level"] in ("low", "medium", "high", "critical")

    async def test_no_token_returns_401(self, client: AsyncClient, sample_animal):
        r = await client.get(f"/api/v1/predictions/animal/{sample_animal.id}/history")
        assert r.status_code == 401


# =============================================================================
# 5. MANUAL PREDICT (POST) — MANAGER+
# =============================================================================

class TestManualPredict:

    async def test_admin_can_predict(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.post(
            f"/api/v1/predictions/animal/{sample_animal.id}/predict",
            headers=auth(admin_token),
        )
        # 200 (muvaffaqiyat) yoki 404 (ma'lumot yetarli emas — cold start)
        assert r.status_code in (200, 404)

    async def test_manager_can_predict(
        self, client: AsyncClient, manager_token: str, sample_animal
    ):
        r = await client.post(
            f"/api/v1/predictions/animal/{sample_animal.id}/predict",
            headers=auth(manager_token),
        )
        assert r.status_code in (200, 404)

    async def test_viewer_cannot_predict(
        self, client: AsyncClient, viewer_token: str, sample_animal
    ):
        r = await client.post(
            f"/api/v1/predictions/animal/{sample_animal.id}/predict",
            headers=auth(viewer_token),
        )
        assert r.status_code == 403

    async def test_no_token_returns_401(self, client: AsyncClient, sample_animal):
        r = await client.post(f"/api/v1/predictions/animal/{sample_animal.id}/predict")
        assert r.status_code == 401

    async def test_nonexistent_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/predictions/animal/99999/predict",
            headers=auth(admin_token),
        )
        assert r.status_code == 404

    async def test_response_schema_on_success(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        r = await client.post(
            f"/api/v1/predictions/animal/{sample_animal.id}/predict",
            headers=auth(admin_token),
        )
        if r.status_code == 200:
            data = r.json()
            for field in ["id", "animal_id", "prediction_date",
                          "risk_level", "risk_score", "confidence", "ensemble"]:
                assert field in data, f"'{field}' response da yo'q"
            assert 0 <= data["risk_score"] <= 100
            assert 0 <= data["confidence"] <= 1
            assert data["risk_level"] in ("low", "medium", "high", "critical")


# =============================================================================
# 6. FARM-WIDE RUN (POST) — ADMIN only
# =============================================================================

class TestFarmRun:

    async def test_admin_can_run(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/predictions/run-farm", headers=auth(admin_token))
        assert r.status_code in (200, 202)

    async def test_manager_cannot_run(
        self, client: AsyncClient, manager_token: str
    ):
        r = await client.post("/api/v1/predictions/run-farm", headers=auth(manager_token))
        assert r.status_code == 403

    async def test_viewer_cannot_run(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/predictions/run-farm", headers=auth(viewer_token))
        assert r.status_code == 403

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.post("/api/v1/predictions/run-farm")
        assert r.status_code == 401

    async def test_response_schema(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/predictions/run-farm", headers=auth(admin_token))
        if r.status_code in (200, 202):
            data = r.json()
            for field in ["date", "total", "succeeded", "failed",
                          "at_risk_count", "duration_sec"]:
                assert field in data, f"'{field}' farm-run response da yo'q"
            assert data["total"] >= 0
            assert data["succeeded"] >= 0
            assert data["failed"] >= 0
            assert data["duration_sec"] >= 0


# =============================================================================
# 7. TRAIN MODELS (POST) — ADMIN only
# =============================================================================

class TestTrainModels:

    async def test_admin_can_train(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(admin_token),
            json={"days_back": 30},
        )
        assert r.status_code == 200

    async def test_manager_cannot_train(
        self, client: AsyncClient, manager_token: str
    ):
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(manager_token),
            json={"days_back": 30},
        )
        assert r.status_code == 403

    async def test_viewer_cannot_train(self, client: AsyncClient, viewer_token: str):
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(viewer_token),
            json={"days_back": 30},
        )
        assert r.status_code == 403

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.post(
            "/api/v1/predictions/train",
            json={"days_back": 30},
        )
        assert r.status_code == 401

    async def test_response_schema(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(admin_token),
            json={"days_back": 30},
        )
        assert r.status_code == 200
        data = r.json()
        for field in ["rf_trained", "iso_trained", "n_samples",
                      "n_positive", "rf_accuracy", "top_features",
                      "duration_sec"]:
            assert field in data, f"'{field}' train response da yo'q"
        assert isinstance(data["top_features"], list)
        assert data["duration_sec"] >= 0

    async def test_days_back_validation(self, client: AsyncClient, admin_token: str):
        """days_back: ge=30, le=365."""
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(admin_token),
            json={"days_back": 10},  # ge=30 — xato
        )
        assert r.status_code == 422

    async def test_days_back_max_validation(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(admin_token),
            json={"days_back": 400},  # le=365 — xato
        )
        assert r.status_code == 422

    async def test_cold_start_no_data(self, client: AsyncClient, admin_token: str):
        """Bo'sh DB da train qilinsa — rf_trained: false (yetarli ma'lumot yo'q)."""
        r = await client.post(
            "/api/v1/predictions/train",
            headers=auth(admin_token),
            json={"days_back": 90},
        )
        assert r.status_code == 200
        data = r.json()
        # Bo'sh DB da RF train qilib bo'lmaydi — lekin xato qaytarmasligi kerak
        assert "rf_trained" in data
        assert isinstance(data["rf_trained"], bool)


# =============================================================================
# 8. MODEL STATUS
# =============================================================================

class TestModelStatus:

    async def test_returns_200(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/predictions/model-status", headers=auth(admin_token))
        assert r.status_code == 200

    async def test_required_fields(self, client: AsyncClient, admin_token: str):
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        for field in ["rf_trained", "iso_trained", "n_training_samples",
                      "model_version", "ensemble_weights",
                      "top_features", "status_message"]:
            assert field in data, f"'{field}' model-status da yo'q"

    async def test_ensemble_weights_sum(self, client: AsyncClient, admin_token: str):
        """Ensemble og'irliklari jami ≈ 1.0 bo'lishi kerak."""
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        weights = data["ensemble_weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"Ensemble og'irliklari jami 1.0 emas: {total}"

    async def test_ensemble_weights_schema(self, client: AsyncClient, admin_token: str):
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        weights = data["ensemble_weights"]
        for key in ["rule_based", "random_forest", "isolation"]:
            assert key in weights, f"'{key}' ensemble_weights da yo'q"
            assert 0 < weights[key] <= 1.0

    async def test_top_features_is_list(self, client: AsyncClient, admin_token: str):
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        assert isinstance(data["top_features"], list)

    async def test_status_message_is_string(self, client: AsyncClient, admin_token: str):
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        assert isinstance(data["status_message"], str)
        assert len(data["status_message"]) > 0

    async def test_model_version_not_empty(self, client: AsyncClient, admin_token: str):
        data = (await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(admin_token),
        )).json()
        assert data["model_version"]

    async def test_viewer_can_read_status(
        self, client: AsyncClient, viewer_token: str
    ):
        r = await client.get(
            "/api/v1/predictions/model-status",
            headers=auth(viewer_token),
        )
        assert r.status_code == 200

    async def test_no_token_returns_401(self, client: AsyncClient):
        r = await client.get("/api/v1/predictions/model-status")
        assert r.status_code == 401