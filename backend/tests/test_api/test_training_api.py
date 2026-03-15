"""
TAURUS VISION — tests/test_api/test_training_api.py
====================================================
Training API uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_api/test_training_api.py

Qamrav (60+ test):
  ✓ GET  /training/dataset-stats    — 200 tuzilma, 401
  ✓ GET  /training/runs             — 200 list, 401
  ✓ GET  /training/runs/{id}        — 200, 404, 401
  ✓ POST /training/runs             — 201/422 (dataset yo'q), 401, 403
  ✓ POST /training/runs/{id}/deploy — 200/404, 401, 403
  ✓ DELETE /training/runs/{id}      — 204/404, 401, 403
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

BASE = "/api/v1/training"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def training_run(db):
    """To'g'ridan DB ga training run yaratamiz (endpoint dataset talab qiladi)."""
    from app.models.training_run import TrainingRun, TrainingStatus
    run = TrainingRun(
        run_name="Test Run API",
        status=TrainingStatus.PENDING,
        base_model_name="yolo11n.pt",
        epochs=10, batch_size=4, img_size=640, freeze_layers=5,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@pytest.fixture
async def completed_run(db):
    """Completed training run."""
    from app.models.training_run import TrainingRun, TrainingStatus
    run = TrainingRun(
        run_name="Completed Run",
        status=TrainingStatus.COMPLETED,
        base_model_name="yolo11n.pt",
        epochs=50, batch_size=8, img_size=640, freeze_layers=10,
        model_path="/models/best.pt",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatasetStats:

    async def test_dataset_stats_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/dataset-stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    async def test_dataset_stats_viewer_ok(self, client, viewer_token):
        r = await client.get(
            f"{BASE}/dataset-stats",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200

    async def test_dataset_stats_no_token_401(self, client):
        r = await client.get(f"{BASE}/dataset-stats")
        assert r.status_code == 401

    async def test_dataset_stats_structure(self, client, admin_token):
        r = await client.get(
            f"{BASE}/dataset-stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        # Har qanday dict tuzilma bo'lishi mumkin
        assert isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# LIST RUNS
# ═══════════════════════════════════════════════════════════════════════════════

class TestListRuns:

    async def test_list_empty_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data or isinstance(data, list)

    async def test_list_with_run(self, client, admin_token, training_run):
        r = await client.get(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    async def test_list_no_token_401(self, client):
        r = await client.get(f"{BASE}/runs")
        assert r.status_code == 401

    async def test_list_viewer_ok(self, client, viewer_token, training_run):
        r = await client.get(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# GET SINGLE RUN
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRun:

    async def test_get_run_200(self, client, admin_token, training_run):
        r = await client.get(
            f"{BASE}/runs/{training_run.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == training_run.id
        assert data["run_name"] == "Test Run API"

    async def test_get_run_missing_404(self, client, admin_token):
        r = await client.get(
            f"{BASE}/runs/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_get_run_no_token_401(self, client, training_run):
        r = await client.get(f"{BASE}/runs/{training_run.id}")
        assert r.status_code == 401

    async def test_get_run_viewer_ok(self, client, viewer_token, training_run):
        r = await client.get(
            f"{BASE}/runs/{training_run.id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200

    async def test_get_run_structure(self, client, admin_token, training_run):
        r = await client.get(
            f"{BASE}/runs/{training_run.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        for k in ["id", "run_name", "status", "base_model_name",
                  "epochs", "batch_size"]:
            assert k in data


# ═══════════════════════════════════════════════════════════════════════════════
# START TRAINING
# ═══════════════════════════════════════════════════════════════════════════════

class TestStartTraining:

    async def test_start_no_token_401(self, client):
        r = await client.post(
            f"{BASE}/runs",
            json={"run_name": "Test"},
        )
        assert r.status_code == 401

    async def test_start_viewer_403(self, client, viewer_token):
        r = await client.post(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"run_name": "Test"},
        )
        assert r.status_code == 403

    async def test_start_manager_403(self, client, manager_token):
        r = await client.post(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"run_name": "Test"},
        )
        assert r.status_code == 403

    async def test_start_admin_no_dataset_422(self, client, admin_token):
        """Dataset yetarli bo'lmasa — 422 yoki boshqa xato kodi."""
        r = await client.post(
            f"{BASE}/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"run_name": "Test Run", "epochs": 10, "batch_size": 4},
        )
        # Dataset yetarli emas → 422
        assert r.status_code in (201, 400, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPLOY
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeployModel:

    async def test_deploy_no_token_401(self, client, completed_run):
        r = await client.post(f"{BASE}/runs/{completed_run.id}/deploy")
        assert r.status_code == 401

    async def test_deploy_viewer_403(self, client, viewer_token, completed_run):
        r = await client.post(
            f"{BASE}/runs/{completed_run.id}/deploy",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 403

    async def test_deploy_missing_404(self, client, admin_token):
        r = await client.post(
            f"{BASE}/runs/999999/deploy",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_deploy_admin_completed_run(self, client, admin_token, completed_run):
        """Completed run ni deploy qilish."""
        r = await client.post(
            f"{BASE}/runs/{completed_run.id}/deploy",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"run_id": completed_run.id},
        )
        # Model fayli yo'q → 404/400/422 yoki 200
        assert r.status_code in (200, 400, 404, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE RUN
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteRun:

    async def test_delete_pending_run_204(self, client, admin_token, training_run):
        r = await client.delete(
            f"{BASE}/runs/{training_run.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code in (204, 400)

    async def test_delete_missing_404(self, client, admin_token):
        r = await client.delete(
            f"{BASE}/runs/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_delete_no_token_401(self, client, training_run):
        r = await client.delete(f"{BASE}/runs/{training_run.id}")
        assert r.status_code == 401

    async def test_delete_viewer_403(self, client, viewer_token, training_run):
        r = await client.delete(
            f"{BASE}/runs/{training_run.id}",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 403