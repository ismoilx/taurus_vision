"""
Taurus Vision — Employees & WorkerTask API Tests
/api/v1/employees/ barcha endpointlarini to'liq test qiladi.

MUAMMO: Xodim qo'shish ishlamagan.
TEKSHIRILADI: create, list, get, update, deactivate, tasks CRUD
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}

# --- Fixtures ---

@pytest.fixture
async def sample_employee(db: AsyncSession):
    """Test uchun xodim yaratadi."""
    from app.models.employee import Employee, EmployeePosition, EmployeeStatus
    emp = Employee(
        full_name="Test Xodim",
        phone="+998901234567",
        position=EmployeePosition.FEEDER,
        status=EmployeeStatus.ACTIVE,
        salary=2500000.0,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


@pytest.fixture
async def sample_worker_task(db: AsyncSession, sample_employee):
    """Test uchun worker task yaratadi."""
    from app.models.employee import WorkerTask, WorkerTaskType, WorkerTaskPriority, WorkerTaskStatus
    task = WorkerTask(
        title="Test Vazifa",
        task_type=WorkerTaskType.FEEDING,
        priority=WorkerTaskPriority.MEDIUM,
        status=WorkerTaskStatus.PENDING,
        employee_id=sample_employee.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


# =============================================================================
# AUTH GUARD
# =============================================================================

class TestEmployeesAuthGuard:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/employees/")
        assert r.status_code == 401

    async def test_create_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/employees/", json={"full_name": "Test"})
        assert r.status_code == 401

    async def test_stats_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/employees/stats")
        assert r.status_code == 401


# =============================================================================
# EMPLOYEE STATS
# =============================================================================

class TestEmployeeStats:
    async def test_stats_empty_db(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/stats", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "active" in data
        assert data["total"] == 0

    async def test_stats_with_employees(self, client: AsyncClient, admin_token: str, sample_employee):
        r = await client.get("/api/v1/employees/stats", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert data["active"] >= 1


# =============================================================================
# EMPLOYEE LIST
# =============================================================================

class TestEmployeeList:
    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_list_with_employees(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.get("/api/v1/employees/", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_pagination(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.get("/api/v1/employees/?page=1&size=5", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "page" in data
        assert "size" in data

    async def test_list_filter_by_status(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.get("/api/v1/employees/?status=active", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_list_search(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.get("/api/v1/employees/?search=Test", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1


# =============================================================================
# EMPLOYEE CREATE
# =============================================================================

class TestEmployeeCreate:
    async def test_create_minimal(self, client: AsyncClient, manager_token: str):
        """Minimal ma'lumotlar bilan xodim yaratish."""
        r = await client.post("/api/v1/employees/", headers=H(manager_token), json={
            "full_name": "Yangi Xodim",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["full_name"] == "Yangi Xodim"
        assert "id" in data

    async def test_create_full(self, client: AsyncClient, manager_token: str):
        """To'liq ma'lumotlar bilan xodim yaratish."""
        r = await client.post("/api/v1/employees/", headers=H(manager_token), json={
            "full_name": "To'liq Xodim",
            "phone": "+998901111111",
            "position": "veterinarian",
            "status": "active",
            "salary": 5000000.0,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["full_name"] == "To'liq Xodim"
        assert data["position"] == "veterinarian"
        assert data["salary"] == 5000000.0

    async def test_create_short_name_rejected(self, client: AsyncClient, manager_token: str):
        """full_name min 2 belgi — 1 belgili rad etiladi."""
        r = await client.post("/api/v1/employees/", headers=H(manager_token), json={
            "full_name": "A",
        })
        assert r.status_code == 422

    async def test_create_empty_name_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/employees/", headers=H(manager_token), json={
            "full_name": "",
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        """VIEWER xodim yarata olmaydi."""
        r = await client.post("/api/v1/employees/", headers=H(viewer_token), json={
            "full_name": "Ruxsatsiz Xodim",
        })
        assert r.status_code == 403

    async def test_create_negative_salary_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/employees/", headers=H(manager_token), json={
            "full_name": "Test Xodim",
            "salary": -1000,
        })
        assert r.status_code == 422


# =============================================================================
# EMPLOYEE GET / UPDATE / DEACTIVATE
# =============================================================================

class TestEmployeeDetail:
    async def test_get_existing(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.get(f"/api/v1/employees/{sample_employee.id}", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == sample_employee.id
        assert data["full_name"] == sample_employee.full_name

    async def test_get_nonexistent(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_update_name(self, client: AsyncClient, manager_token: str, sample_employee):
        r = await client.patch(f"/api/v1/employees/{sample_employee.id}", headers=H(manager_token),
                               json={"full_name": "Yangilangan Ism"})
        assert r.status_code == 200
        assert r.json()["full_name"] == "Yangilangan Ism"

    async def test_update_phone(self, client: AsyncClient, manager_token: str, sample_employee):
        r = await client.patch(f"/api/v1/employees/{sample_employee.id}", headers=H(manager_token),
                               json={"phone": "+998999999999"})
        assert r.status_code == 200
        assert r.json()["phone"] == "+998999999999"

    async def test_viewer_cannot_update(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.patch(f"/api/v1/employees/{sample_employee.id}", headers=H(viewer_token),
                               json={"full_name": "Ruxsatsiz"})
        assert r.status_code == 403

    async def test_deactivate_requires_admin(self, client: AsyncClient, manager_token: str, sample_employee):
        """MANAGER deactivate qila olmaydi — faqat ADMIN."""
        r = await client.post(f"/api/v1/employees/{sample_employee.id}/deactivate",
                              headers=H(manager_token))
        assert r.status_code == 403

    async def test_deactivate_as_admin(self, client: AsyncClient, admin_token: str, sample_employee):
        r = await client.post(f"/api/v1/employees/{sample_employee.id}/deactivate",
                              headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] in ("inactive", "terminated")


# =============================================================================
# WORKER TASKS — STATS
# =============================================================================

class TestWorkerTaskStats:
    async def test_stats_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/tasks/stats", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "total" in data

    async def test_stats_with_tasks(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.get("/api/v1/employees/tasks/stats", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# =============================================================================
# WORKER TASKS — LIST
# =============================================================================

class TestWorkerTaskList:
    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/tasks/", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_list_with_tasks(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.get("/api/v1/employees/tasks/", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_filter_by_status(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.get("/api/v1/employees/tasks/?status=pending", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_filter_by_employee(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.get(
            f"/api/v1/employees/tasks/?employee_id={sample_worker_task.employee_id}",
            headers=H(viewer_token)
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# =============================================================================
# WORKER TASKS — CREATE
# =============================================================================

class TestWorkerTaskCreate:
    async def test_create_minimal(self, client: AsyncClient, manager_token: str, sample_employee):
        r = await client.post("/api/v1/employees/tasks/", headers=H(manager_token), json={
            "title": "Boqish vazifasi",
            "employee_id": sample_employee.id,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Boqish vazifasi"
        assert "id" in data

    async def test_create_full(self, client: AsyncClient, manager_token: str, sample_employee):
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = await client.post("/api/v1/employees/tasks/", headers=H(manager_token), json={
            "title": "Veterinar tekshiruvi",
            "description": "Barcha mollarni tekshirish",
            "task_type": "health_check",
            "priority": "high",
            "employee_id": sample_employee.id,
            "due_date": due,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["priority"] == "high"

    async def test_create_empty_title_rejected(self, client: AsyncClient, manager_token: str, sample_employee):
        r = await client.post("/api/v1/employees/tasks/", headers=H(manager_token), json={
            "title": "",
            "employee_id": sample_employee.id,
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create_task(self, client: AsyncClient, viewer_token: str, sample_employee):
        r = await client.post("/api/v1/employees/tasks/", headers=H(viewer_token), json={
            "title": "Test",
            "employee_id": sample_employee.id,
        })
        assert r.status_code == 403


# =============================================================================
# WORKER TASKS — GET / UPDATE / STATUS
# =============================================================================

class TestWorkerTaskDetail:
    async def test_get_existing(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.get(f"/api/v1/employees/tasks/{sample_worker_task.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_worker_task.id

    async def test_get_nonexistent(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/employees/tasks/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_start_task(self, client: AsyncClient, admin_token: str, sample_worker_task):
        r = await client.post(f"/api/v1/employees/tasks/{sample_worker_task.id}/start",
                              headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    async def test_complete_task(self, client: AsyncClient, admin_token: str, sample_worker_task):
        # Avval boshlash
        await client.post(f"/api/v1/employees/tasks/{sample_worker_task.id}/start",
                          headers=H(admin_token))
        # Keyin yakunlash
        r = await client.post(f"/api/v1/employees/tasks/{sample_worker_task.id}/complete",
                              headers=H(admin_token), json={"completion_notes": "Bajarildi"})
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    async def test_cancel_task(self, client: AsyncClient, manager_token: str, sample_worker_task):
        r = await client.post(f"/api/v1/employees/tasks/{sample_worker_task.id}/cancel",
                              headers=H(manager_token))
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    async def test_viewer_cannot_cancel(self, client: AsyncClient, viewer_token: str, sample_worker_task):
        r = await client.post(f"/api/v1/employees/tasks/{sample_worker_task.id}/cancel",
                              headers=H(viewer_token))
        assert r.status_code == 403
