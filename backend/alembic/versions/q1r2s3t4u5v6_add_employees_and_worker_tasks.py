"""add_employees_and_worker_tasks

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-03-06 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'q1r2s3t4u5v6'
down_revision: Union[str, None] = 'p0q1r2s3t4u5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── employees ────────────────────────────────────────────────────────
    op.create_table(
        'employees',
        sa.Column('id',         sa.Integer(),     nullable=False),
        sa.Column('full_name',  sa.String(200),   nullable=False),
        sa.Column('phone',      sa.String(20),    nullable=True),
        sa.Column('position',   sa.String(30),    nullable=False, server_default='other'),
        sa.Column('status',     sa.String(20),    nullable=False, server_default='active'),
        sa.Column('hire_date',  sa.Date(),        nullable=True),
        sa.Column('salary',     sa.Numeric(12, 2), nullable=True),
        sa.Column('notes',      sa.Text(),        nullable=True),
        sa.Column('farm_id',    sa.Integer(),     nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_employees_full_name',       'employees', ['full_name'])
    op.create_index('ix_employees_position',        'employees', ['position'])
    op.create_index('ix_employees_status',          'employees', ['status'])
    op.create_index('ix_employees_farm_status',     'employees', ['farm_id', 'status'])
    op.create_index('ix_employees_status_position', 'employees', ['status', 'position'])

    # ── worker_tasks ─────────────────────────────────────────────────────
    op.create_table(
        'worker_tasks',
        sa.Column('id',                    sa.Integer(),     nullable=False),
        sa.Column('title',                 sa.String(300),   nullable=False),
        sa.Column('description',           sa.Text(),        nullable=True),
        sa.Column('task_type',             sa.String(30),    nullable=False),
        sa.Column('priority',              sa.String(20),    nullable=False, server_default='medium'),
        sa.Column('status',                sa.String(20),    nullable=False, server_default='pending'),
        sa.Column('due_date',              sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at',            sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at',          sa.DateTime(timezone=True), nullable=True),
        sa.Column('employee_id',           sa.Integer(),     nullable=True),
        sa.Column('animal_id',             sa.Integer(),     nullable=True),
        sa.Column('assigned_by',           sa.Integer(),     nullable=True),
        sa.Column('requires_verification', sa.Boolean(),     nullable=False, server_default='false'),
        sa.Column('verification_status',   sa.String(20),    nullable=False, server_default='unverified'),
        sa.Column('verified_at',           sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by',           sa.Integer(),     nullable=True),
        sa.Column('completion_notes',      sa.Text(),        nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['animal_id'],   ['animals.id'],   ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'],     ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_worker_tasks_employee_id',   'worker_tasks', ['employee_id'])
    op.create_index('ix_worker_tasks_status',        'worker_tasks', ['status'])
    op.create_index('ix_worker_tasks_task_type',     'worker_tasks', ['task_type'])
    op.create_index('ix_worker_tasks_priority',      'worker_tasks', ['priority'])
    op.create_index('ix_worker_tasks_due_date',      'worker_tasks', ['due_date'])
    op.create_index('ix_worker_tasks_emp_status',    'worker_tasks', ['employee_id', 'status'])
    op.create_index('ix_worker_tasks_status_due',    'worker_tasks', ['status', 'due_date'])
    op.create_index('ix_worker_tasks_type_status',   'worker_tasks', ['task_type', 'status'])
    op.create_index('ix_worker_tasks_animal_status', 'worker_tasks', ['animal_id', 'status'])


def downgrade() -> None:
    op.drop_table('worker_tasks')
    op.drop_table('employees')
