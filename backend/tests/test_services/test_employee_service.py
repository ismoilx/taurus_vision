"""
TAURUS VISION — tests/test_services/test_employee_service.py
=============================================================
Employee + WorkerTask tizimini AYAMAS darajada vahshiy testlar.

Qamrov:
  ✓ Employee model     — EmployeePosition, EmployeeStatus, WorkerTaskStatus enums
  ✓ EmployeeRepository — create, get, list, update, stats, task CRUD
  ✓ EmployeeService.create_employee / get / list / update / deactivate / stats
  ✓ EmployeeService.create_task   — xodim yo'q, nofaol xodim
  ✓ EmployeeService.get_task / list_tasks — filtrlar
  ✓ EmployeeService.update_task   — yakunlangan/bekor → xato
  ✓ EmployeeService.start_task    — holat mashini
  ✓ EmployeeService.complete_task — holat mashini, allaqachon completed
  ✓ EmployeeService.cancel_task   — holat mashini
  ✓ EmployeeService.verify_task   — completed → verified, tekshiruvsiz → xato
  ✓ EmployeeService.get_task_stats
  ✓ POSITION_LABELS barcha lavozimlar
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import (
    Employee, WorkerTask,
    EmployeePosition, EmployeeStatus,
    WorkerTaskStatus, WorkerTaskPriority, WorkerTaskType, VerificationStatus,
)
from app.repositories.employee_repository import EmployeeRepository
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate,
    WorkerTaskCreate, WorkerTaskUpdate, WorkerTaskComplete, WorkerTaskVerify,
)
from app.services.employee_service import EmployeeService, POSITION_LABELS
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


def _emp_create(name="Ali Valiyev", **kw) -> EmployeeCreate:
    return EmployeeCreate(
        full_name=name,
        position=EmployeePosition.FEEDER,
        status=EmployeeStatus.ACTIVE,
        **kw,
    )


def _task_create(employee_id=None, **kw) -> WorkerTaskCreate:
    return WorkerTaskCreate(
        title="Ertalabki oziqlantirish",
        task_type=WorkerTaskType.FEEDING,
        priority=WorkerTaskPriority.MEDIUM,
        employee_id=employee_id,
        due_date=TOMORROW,
        **kw,
    )


@pytest.fixture
def svc(db):
    return EmployeeService(db)


@pytest.fixture
async def active_employee(db):
    svc = EmployeeService(db)
    return await svc.create_employee(_emp_create(name="Aktiv Xodim"))


@pytest.fixture
async def inactive_employee(db):
    svc = EmployeeService(db)
    emp = await svc.create_employee(_emp_create(name="Nofaol Xodim"))
    return await svc.deactivate_employee(emp.id)


# ═══ POSITION LABELS ═══════════════════════════════════════════════════

class TestPositionLabels:
    def test_all_positions_have_label(self):
        for pos in EmployeePosition:
            assert pos.value in POSITION_LABELS
            assert isinstance(POSITION_LABELS[pos.value], str)

    def test_feeder_label_uzbek(self):
        assert POSITION_LABELS["feeder"] == "Boqituvchi"

    def test_veterinarian_label_uzbek(self):
        assert POSITION_LABELS["veterinarian"] == "Veterinar"

    def test_manager_label_uzbek(self):
        assert POSITION_LABELS["manager"] == "Boshqaruvchi"


# ═══ EMPLOYEE SERVICE — CREATE ══════════════════════════════════════════

class TestEmployeeServiceCreate:

    async def test_create_assigns_id(self, db, svc):
        emp = await svc.create_employee(_emp_create())
        assert emp.id is not None

    async def test_create_all_positions(self, db, svc):
        for pos in EmployeePosition:
            emp = await svc.create_employee(EmployeeCreate(
                full_name=f"Test {pos.value}", position=pos,
                status=EmployeeStatus.ACTIVE))
            assert emp.position == pos

    async def test_create_with_all_fields(self, db, svc):
        emp = await svc.create_employee(EmployeeCreate(
            full_name="To'liq Xodim",
            phone="+998901234567",
            position=EmployeePosition.VETERINARIAN,
            status=EmployeeStatus.ACTIVE,
            hire_date=TODAY,
            salary=3_000_000.0,
            notes="Tajribali veterinar",
        ))
        assert emp.full_name == "To'liq Xodim"
        assert emp.position  == EmployeePosition.VETERINARIAN
        assert emp.salary    == 3_000_000.0

    async def test_create_default_status_active(self, db, svc):
        emp = await svc.create_employee(_emp_create())
        assert emp.status == EmployeeStatus.ACTIVE

    async def test_create_with_open_tasks_zero(self, db, svc):
        emp = await svc.create_employee(_emp_create())
        assert emp.open_tasks      == 0
        assert emp.completed_tasks == 0
        assert emp.overdue_tasks   == 0


# ═══ EMPLOYEE SERVICE — GET / LIST / UPDATE / DEACTIVATE ════════════════

class TestEmployeeServiceGetList:

    async def test_get_existing(self, db, svc, active_employee):
        found = await svc.get_employee(active_employee.id)
        assert found.id == active_employee.id

    async def test_get_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_employee(999999)

    async def test_list_returns_response(self, db, svc, active_employee):
        from app.schemas.employee import EmployeeListResponse
        resp = await svc.list_employees()
        assert isinstance(resp, EmployeeListResponse)
        assert resp.total >= 1

    async def test_list_status_filter(self, db, svc, active_employee, inactive_employee):
        resp = await svc.list_employees(status="active")
        ids = [e.id for e in resp.items]
        assert active_employee.id   in ids
        assert inactive_employee.id not in ids

    async def test_list_position_filter(self, db, svc):
        await svc.create_employee(EmployeeCreate(
            full_name="Vet Ismoilov",
            position=EmployeePosition.VETERINARIAN,
            status=EmployeeStatus.ACTIVE))
        resp = await svc.list_employees(position="veterinarian")
        assert all(e.position == EmployeePosition.VETERINARIAN for e in resp.items)

    async def test_list_search(self, db, svc):
        await svc.create_employee(_emp_create(name="Unique Xodim Qidiruv"))
        resp = await svc.list_employees(search="Unique Xodim")
        assert any("Unique" in e.full_name for e in resp.items)

    async def test_list_pagination(self, db, svc):
        for i in range(5):
            await svc.create_employee(_emp_create(name=f"Pag Xodim {i}"))
        p1 = await svc.list_employees(page=1, size=2)
        p2 = await svc.list_employees(page=2, size=2)
        ids1 = {e.id for e in p1.items}
        ids2 = {e.id for e in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_update_name(self, db, svc, active_employee):
        updated = await svc.update_employee(
            active_employee.id, EmployeeUpdate(full_name="Yangi Ism"))
        assert updated.full_name == "Yangi Ism"

    async def test_update_salary(self, db, svc, active_employee):
        updated = await svc.update_employee(
            active_employee.id, EmployeeUpdate(salary=5_000_000.0))
        assert updated.salary == 5_000_000.0

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_employee(999999, EmployeeUpdate(full_name="Ghost"))

    async def test_deactivate_success(self, db, svc, active_employee):
        result = await svc.deactivate_employee(active_employee.id)
        assert result.status == EmployeeStatus.INACTIVE

    async def test_deactivate_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.deactivate_employee(999999)

    async def test_get_stats_structure(self, db, svc, active_employee):
        from app.schemas.employee import EmployeeStats
        stats = await svc.get_stats()
        assert isinstance(stats, EmployeeStats)
        assert stats.total >= 1
        assert stats.active >= 1


# ═══ EMPLOYEE SERVICE — TASK CREATE ══════════════════════════════════════

class TestEmployeeServiceTaskCreate:

    async def test_create_task_success(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        assert task.id is not None

    async def test_create_task_missing_employee_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.create_task(_task_create(employee_id=999999), assigned_by=1)

    async def test_create_task_inactive_employee_raises(self, db, svc, inactive_employee):
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.create_task(
                _task_create(employee_id=inactive_employee.id), assigned_by=1)
        assert "faol" in exc_info.value.message.lower() or "nofaol" in exc_info.value.message.lower()

    async def test_create_task_no_employee_ok(self, db, svc):
        """employee_id=None — tayinlanmagan vazifa."""
        task = await svc.create_task(
            _task_create(employee_id=None), assigned_by=1)
        assert task.id is not None
        assert task.employee_id is None

    async def test_create_task_default_status_pending(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        assert task.status == WorkerTaskStatus.PENDING

    async def test_create_task_all_types(self, db, svc, active_employee):
        for ttype in WorkerTaskType:
            task = await svc.create_task(
                WorkerTaskCreate(
                    title=f"Vazifa {ttype.value}",
                    task_type=ttype,
                    priority=WorkerTaskPriority.LOW,
                    employee_id=active_employee.id,
                ), assigned_by=1)
            assert task.task_type == ttype

    async def test_create_task_all_priorities(self, db, svc, active_employee):
        for prio in WorkerTaskPriority:
            task = await svc.create_task(
                WorkerTaskCreate(
                    title=f"Priority {prio.value}",
                    task_type=WorkerTaskType.OTHER,
                    priority=prio,
                    employee_id=active_employee.id,
                ), assigned_by=1)
            assert task.priority == prio

    async def test_create_task_requires_verification(self, db, svc, active_employee):
        task = await svc.create_task(
            WorkerTaskCreate(
                title="Tasdiqlash talab etiladi",
                task_type=WorkerTaskType.VACCINATION,
                priority=WorkerTaskPriority.HIGH,
                employee_id=active_employee.id,
                requires_verification=True,
            ), assigned_by=1)
        assert task.requires_verification is True


# ═══ EMPLOYEE SERVICE — TASK GET / LIST ══════════════════════════════════

class TestEmployeeServiceTaskGetList:

    async def test_get_task_existing(self, db, svc, active_employee):
        created = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        found = await svc.get_task(created.id)
        assert found.id == created.id

    async def test_get_task_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_task(999999)

    async def test_list_tasks_all(self, db, svc, active_employee):
        for _ in range(3):
            await svc.create_task(_task_create(employee_id=active_employee.id), assigned_by=1)
        result = await svc.list_tasks()
        assert result.total >= 3

    async def test_list_tasks_employee_filter(self, db, svc, active_employee):
        emp2 = await svc.create_employee(_emp_create(name="Ikkinchi Xodim"))
        await svc.create_task(_task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.create_task(_task_create(employee_id=emp2.id), assigned_by=1)
        result = await svc.list_tasks(employee_id=active_employee.id)
        assert all(t.employee_id == active_employee.id for t in result.items)

    async def test_list_tasks_status_filter(self, db, svc, active_employee):
        t1 = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.start_task(t1.id)
        result = await svc.list_tasks(status="in_progress")
        assert all(t.status == WorkerTaskStatus.IN_PROGRESS for t in result.items)

    async def test_list_tasks_pagination(self, db, svc, active_employee):
        for _ in range(5):
            await svc.create_task(
                _task_create(employee_id=active_employee.id), assigned_by=1)
        p1 = await svc.list_tasks(page=1, size=2)
        p2 = await svc.list_tasks(page=2, size=2)
        ids1 = {t.id for t in p1.items}
        ids2 = {t.id for t in p2.items}
        assert ids1.isdisjoint(ids2)


# ═══ EMPLOYEE SERVICE — TASK HOLAT MASHINI ═══════════════════════════════

class TestEmployeeServiceTaskStateMachine:

    async def test_update_pending_task_ok(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        updated = await svc.update_task(
            task.id, WorkerTaskUpdate(title="Yangi Sarlavha"))
        assert updated.title == "Yangi Sarlavha"

    async def test_update_completed_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.update_task(task.id, WorkerTaskUpdate(title="Fail"))
        assert "yakunlangan" in exc_info.value.message.lower()

    async def test_update_cancelled_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.cancel_task(task.id)
        with pytest.raises(BusinessRuleViolationError):
            await svc.update_task(task.id, WorkerTaskUpdate(title="Fail"))

    async def test_start_pending_ok(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        started = await svc.start_task(task.id)
        assert started.status == WorkerTaskStatus.IN_PROGRESS
        assert started.started_at is not None

    async def test_start_completed_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.start_task(task.id)
        assert "kutilayotgan" in exc_info.value.message.lower() or \
               "boshlash" in exc_info.value.message.lower()

    async def test_start_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.start_task(999999)

    async def test_complete_pending_ok(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        completed = await svc.complete_task(
            task.id, WorkerTaskComplete(completion_notes="Bajarildi"))
        assert completed.status == WorkerTaskStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.completion_notes == "Bajarildi"

    async def test_complete_in_progress_ok(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.start_task(task.id)
        completed = await svc.complete_task(task.id, WorkerTaskComplete())
        assert completed.status == WorkerTaskStatus.COMPLETED

    async def test_complete_already_completed_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.complete_task(task.id, WorkerTaskComplete())
        assert "allaqachon" in exc_info.value.message.lower()

    async def test_complete_cancelled_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.cancel_task(task.id)
        with pytest.raises(BusinessRuleViolationError):
            await svc.complete_task(task.id, WorkerTaskComplete())

    async def test_complete_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.complete_task(999999, WorkerTaskComplete())

    async def test_cancel_pending_ok(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        cancelled = await svc.cancel_task(task.id)
        assert cancelled.status == WorkerTaskStatus.CANCELLED

    async def test_cancel_completed_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        with pytest.raises(BusinessRuleViolationError):
            await svc.cancel_task(task.id)

    async def test_cancel_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.cancel_task(999999)

    async def test_full_lifecycle_pending_start_complete(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        assert task.status == WorkerTaskStatus.PENDING
        started = await svc.start_task(task.id)
        assert started.status == WorkerTaskStatus.IN_PROGRESS
        completed = await svc.complete_task(task.id, WorkerTaskComplete())
        assert completed.status == WorkerTaskStatus.COMPLETED


# ═══ EMPLOYEE SERVICE — VERIFY TASK ══════════════════════════════════════

class TestEmployeeServiceVerifyTask:

    async def test_verify_completed_task(self, db, svc, active_employee):
        task = await svc.create_task(
            WorkerTaskCreate(
                title="Tekshirish", task_type=WorkerTaskType.VACCINATION,
                priority=WorkerTaskPriority.HIGH,
                employee_id=active_employee.id,
                requires_verification=True,
            ), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        verified = await svc.verify_task(
            task.id,
            WorkerTaskVerify(verification_status=VerificationStatus.VERIFIED),
            verifier_id=99)
        assert verified.verification_status == VerificationStatus.VERIFIED
        assert verified.verified_at is not None
        assert verified.verified_by == 99

    async def test_verify_no_verification_required_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            _task_create(employee_id=active_employee.id,
                         requires_verification=False), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.verify_task(
                task.id,
                WorkerTaskVerify(verification_status=VerificationStatus.VERIFIED),
                verifier_id=99)
        assert "tekshirish" in exc_info.value.message.lower() or \
               "talab" in exc_info.value.message.lower()

    async def test_verify_pending_task_raises(self, db, svc, active_employee):
        task = await svc.create_task(
            WorkerTaskCreate(
                title="Pending Verify",
                task_type=WorkerTaskType.OTHER,
                priority=WorkerTaskPriority.LOW,
                employee_id=active_employee.id,
                requires_verification=True,
            ), assigned_by=1)
        with pytest.raises(BusinessRuleViolationError):
            await svc.verify_task(
                task.id,
                WorkerTaskVerify(verification_status=VerificationStatus.VERIFIED),
                verifier_id=99)

    async def test_verify_failed_status(self, db, svc, active_employee):
        task = await svc.create_task(
            WorkerTaskCreate(
                title="Failed Verify",
                task_type=WorkerTaskType.OTHER,
                priority=WorkerTaskPriority.LOW,
                employee_id=active_employee.id,
                requires_verification=True,
            ), assigned_by=1)
        await svc.complete_task(task.id, WorkerTaskComplete())
        result = await svc.verify_task(
            task.id,
            WorkerTaskVerify(
                verification_status=VerificationStatus.FAILED,
                notes="Kameradan ko'rinmadi"),
            verifier_id=99)
        assert result.verification_status == VerificationStatus.FAILED


# ═══ EMPLOYEE SERVICE — TASK STATS ═══════════════════════════════════════

class TestEmployeeServiceTaskStats:

    async def test_get_task_stats_structure(self, db, svc, active_employee):
        from app.schemas.employee import WorkerTaskStats
        await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        stats = await svc.get_task_stats()
        assert isinstance(stats, WorkerTaskStats)

    async def test_get_task_stats_for_employee(self, db, svc, active_employee):
        t1 = await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        await svc.complete_task(t1.id, WorkerTaskComplete())
        await svc.create_task(
            _task_create(employee_id=active_employee.id), assigned_by=1)
        stats = await svc.get_task_stats(employee_id=active_employee.id)
        assert stats is not None