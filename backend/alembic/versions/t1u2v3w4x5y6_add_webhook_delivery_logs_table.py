"""add_webhook_delivery_logs_table

Revision ID: t1u2v3w4x5y6
Revises: s1t2u3v4w5x6
Create Date: 2025-03-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 't1u2v3w4x5y6'
down_revision = 's1t2u3v4w5x6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_delivery_logs',
        sa.Column('id',              sa.Integer(), nullable=False),
        sa.Column('webhook_id',      sa.Integer(), nullable=False),
        sa.Column('event_type',      sa.String(length=100), nullable=False),
        sa.Column('success',         sa.Boolean(), nullable=False),
        sa.Column('status_code',     sa.Integer(), nullable=True),
        sa.Column('latency_ms',      sa.Integer(), nullable=True),
        sa.Column('error_message',   sa.Text(), nullable=True),
        sa.Column('payload_preview', sa.Text(), nullable=True),
        sa.Column('delivery_id',     sa.String(length=36), nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at',      sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_wdl_webhook_id',  'webhook_delivery_logs', ['webhook_id'])
    op.create_index('ix_wdl_created_at',  'webhook_delivery_logs', ['created_at'])
    op.create_index('ix_wdl_success',     'webhook_delivery_logs', ['success'])
    op.create_index('ix_wdl_delivery_id', 'webhook_delivery_logs', ['delivery_id'])


def downgrade() -> None:
    op.drop_index('ix_wdl_delivery_id', table_name='webhook_delivery_logs')
    op.drop_index('ix_wdl_success',     table_name='webhook_delivery_logs')
    op.drop_index('ix_wdl_created_at',  table_name='webhook_delivery_logs')
    op.drop_index('ix_wdl_webhook_id',  table_name='webhook_delivery_logs')
    op.drop_table('webhook_delivery_logs')