"""add_integration_tables

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-03-05

api_keys va webhooks jadvallari.
"""

revision = 'i2j3k4l5m6n7'
down_revision = 'h1i2j3k4l5m6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # ── api_keys ─────────────────────────────────────────────────────────────
    op.create_table(
        'api_keys',
        sa.Column('id',            sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at',    sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('name',          sa.String(100),  nullable=False),
        sa.Column('description',   sa.Text(),       nullable=True),
        sa.Column('key_prefix',    sa.String(16),   nullable=False, unique=True),
        sa.Column('key_hash',      sa.String(64),   nullable=False),
        sa.Column('scopes',        postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active',     sa.Boolean(),    nullable=False, server_default='true'),
        sa.Column('expires_at',    sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_count', sa.Integer(),    nullable=False, server_default='0'),
        sa.Column('created_by',    sa.Integer(),    sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_api_keys_key_prefix',    'api_keys', ['key_prefix'], unique=True)
    op.create_index('ix_api_keys_prefix_active', 'api_keys', ['key_prefix', 'is_active'])
    op.create_index('ix_api_keys_created_by',    'api_keys', ['created_by'])
    op.create_index('ix_api_keys_is_active',     'api_keys', ['is_active'])

    # ── webhooks ─────────────────────────────────────────────────────────────
    op.create_table(
        'webhooks',
        sa.Column('id',                sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column('created_at',        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at',        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('name',              sa.String(100), nullable=False),
        sa.Column('description',       sa.Text(),      nullable=True),
        sa.Column('url',               sa.String(500), nullable=False),
        sa.Column('secret',            sa.String(128), nullable=False),
        sa.Column('events',            postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active',         sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('failure_count',     sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('success_count',     sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status_code',  sa.Integer(),   nullable=True),
        sa.Column('last_error',        sa.String(500), nullable=True),
        sa.Column('created_by',        sa.Integer(),   sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_webhooks_active',     'webhooks', ['is_active'])
    op.create_index('ix_webhooks_created_by', 'webhooks', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_webhooks_created_by', table_name='webhooks')
    op.drop_index('ix_webhooks_active',     table_name='webhooks')
    op.drop_table('webhooks')

    op.drop_index('ix_api_keys_is_active',     table_name='api_keys')
    op.drop_index('ix_api_keys_created_by',    table_name='api_keys')
    op.drop_index('ix_api_keys_prefix_active', table_name='api_keys')
    op.drop_index('ix_api_keys_key_prefix',    table_name='api_keys')
    op.drop_table('api_keys')