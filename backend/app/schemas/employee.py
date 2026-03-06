"""
Taurus Vision — Employee & WorkerTask Pydantic Schemas

Request/Response schemalar.
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.employee import (
    EmployeePosition, EmployeeStatus,
    WorkerTaskType, WorkerTaskPriority, WorkerTaskStatus, VerificationStatus,
)


# =============================================================================
# EMPLOYEE SCHEMAS
# =============================================================================

class EmployeeCreate(BaseModel):
    full_name:  str              = Field(..., min_length=2, max_length=200)
    phone:      Optional[str]   = Field(None, max_length=20)
    position:   EmployeePosition = EmployeePosition.OTHER
    status:     EmployeeStatus   = EmployeeStatus.ACTIVE
    hire_date:  Optional[date]  = None
    salary:     Optional[float] = Field(None, ge=0)
    notes:      Optional[str]   = None
    farm_id:    Optional[int]   = None


class EmployeeUpdate(BaseModel):
    full_name:  Optional[str]            = Field(None, min_length=2, max_length=200)
    phone:      Optional[str]            = Field(None, max_length=20)
    position:   Optional[EmployeePosition] = None
    status:     Optional[EmployeeStatus]   = None
    hire_date:  Optional[date]           = None
    salary:     Optional[float]          = Field(None, ge=0)
    notes:      Optional[str]            = None
    farm_id:    Optional[int]            = None


class EmployeeResponse(BaseModel):
    id:           int
    full_name:    str
    phone:        Optional[str]
    position:     EmployeePosition
    status:       EmployeeStatus
    hire_date:    Optional[date]
    salary:       Optional[float]
    notes:        Optional[str]
    farm_id:      Optional[int]
    created_at:   datetime
    updated_at:   datetime

    # Computed
    open_tasks:      int = 0
    completed_tasks: int = 0
    overdue_tasks:   int = 0

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page:  int
    size:  int
    pages: int


class EmployeeStats(BaseModel):
    total:       int
    active:      int
    on_leave:    int
    inactive:    int
    by_position: dict[str, int]
    tasks_today: int
    overdue_tasks: int


# =============================================================================
# WORKER TASK SCHEMAS
# =============================================================================

class WorkerTaskCreate(BaseModel):
    title:                str                  = Field(..., min_length=2, max_length=300)
    description:          Optional[str]        = None
    task_type:            WorkerTaskType       = WorkerTaskType.OTHER
    priority:             WorkerTaskPriority   = WorkerTaskPriority.MEDIUM
    due_date:             Optional[datetime]   = None
    employee_id:          Optional[int]        = None
    animal_id:            Optional[int]        = None
    requires_verification: bool                = False


class WorkerTaskUpdate(BaseModel):
    title:                Optional[str]               = Field(None, min_length=2, max_length=300)
    description:          Optional[str]               = None
    task_type:            Optional[WorkerTaskType]    = None
    priority:             Optional[WorkerTaskPriority] = None
    due_date:             Optional[datetime]          = None
    employee_id:          Optional[int]               = None
    animal_id:            Optional[int]               = None
    requires_verification: Optional[bool]             = None


class WorkerTaskComplete(BaseModel):
    completion_notes: Optional[str] = None


class WorkerTaskVerify(BaseModel):
    verification_status: VerificationStatus
    notes:               Optional[str] = None


class WorkerTaskResponse(BaseModel):
    id:                    int
    title:                 str
    description:           Optional[str]
    task_type:             WorkerTaskType
    priority:              WorkerTaskPriority
    status:                WorkerTaskStatus
    due_date:              Optional[datetime]
    started_at:            Optional[datetime]
    completed_at:          Optional[datetime]
    employee_id:           Optional[int]
    employee_name:         Optional[str]
    employee_position:     Optional[str]
    animal_id:             Optional[int]
    assigned_by:           Optional[int]
    requires_verification: bool
    verification_status:   VerificationStatus
    verified_at:           Optional[datetime]
    verified_by:           Optional[int]
    completion_notes:      Optional[str]
    is_overdue:            bool
    created_at:            datetime
    updated_at:            datetime

    model_config = {"from_attributes": True}


class WorkerTaskListResponse(BaseModel):
    items: list[WorkerTaskResponse]
    total: int
    page:  int
    size:  int
    pages: int


class WorkerTaskStats(BaseModel):
    total:              int
    pending:            int
    in_progress:        int
    completed:          int
    overdue:            int
    cancelled:          int
    needs_verification: int
    completion_rate:    float  # 0-100%
