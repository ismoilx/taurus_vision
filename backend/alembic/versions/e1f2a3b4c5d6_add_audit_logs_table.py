"""add_audit_logs_table

Revision ID: e1f2a3b4c5d6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_type',   sa.String(64),  nullable=False),
        sa.Column('severity',     sa.String(16),  nullable=False, server_default='info'),
        sa.Column('user_id',      sa.Integer(),   sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('username',     sa.String(64),  nullable=True),
        sa.Column('ip_address',   sa.String(45),  nullable=False),
        sa.Column('user_agent',   sa.String(512), nullable=True),
        sa.Column('endpoint',     sa.String(256), nullable=True),
        sa.Column('http_method',  sa.String(8),   nullable=True),
        sa.Column('details',      sa.JSON(),      nullable=True),
        sa.Column('occurred_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at',   sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',   sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_audit_ip_time',    'audit_logs', ['ip_address', 'occurred_at'])
    op.create_index('ix_audit_user_time',  'audit_logs', ['user_id',    'occurred_at'])
    op.create_index('ix_audit_event_time', 'audit_logs', ['event_type', 'occurred_at'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])

def downgrade() -> None:
    op.drop_index('ix_audit_logs_event_type', table_name='audit_logs')
    op.drop_index('ix_audit_event_time',      table_name='audit_logs')
    op.drop_index('ix_audit_user_time',       table_name='audit_logs')
    op.drop_index('ix_audit_ip_time',         table_name='audit_logs')
    op.drop_table('audit_logs')
