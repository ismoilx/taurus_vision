"""add_finance_transactions_table

Revision ID: h1i2j3k4l5m6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-05

Moliyaviy operatsiyalar jadvali.
"""

revision = 'h1i2j3k4l5m6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.create_table(
        'finance_transactions',

        sa.Column('id',               sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Core fields
        sa.Column('type',             sa.String(10),   nullable=False),
        sa.Column('category',         sa.String(30),   nullable=False),
        sa.Column('amount_uzs',       sa.Integer(),    nullable=False),
        sa.Column('amount_usd',       sa.Float(),      nullable=True),
        sa.Column('description',      sa.String(500),  nullable=False),
        sa.Column('notes',            sa.Text(),       nullable=True),

        # Date
        sa.Column('transaction_date', sa.Date(),       nullable=False),

        # Payment
        sa.Column('payment_method',   sa.String(15),   nullable=False, server_default='cash'),
        sa.Column('receipt_number',   sa.String(100),  nullable=True),

        # FK
        sa.Column('animal_id',    sa.Integer(), sa.ForeignKey('animals.id',  ondelete='SET NULL'), nullable=True),
        sa.Column('created_by',   sa.Integer(), sa.ForeignKey('users.id',    ondelete='SET NULL'), nullable=True),

        # Extra
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Indexes
    op.create_index('ix_finance_transactions_type',          'finance_transactions', ['type'])
    op.create_index('ix_finance_transactions_transaction_date','finance_transactions',['transaction_date'])
    op.create_index('ix_finance_transactions_category',      'finance_transactions', ['category'])
    op.create_index('ix_finance_transactions_animal_id',     'finance_transactions', ['animal_id'])
    op.create_index('ix_finance_transactions_created_by',    'finance_transactions', ['created_by'])
    op.create_index('ix_finance_type_date',     'finance_transactions', ['type',     'transaction_date'])
    op.create_index('ix_finance_category_date', 'finance_transactions', ['category', 'transaction_date'])
    op.create_index('ix_finance_animal_date',   'finance_transactions', ['animal_id','transaction_date'])


def downgrade() -> None:
    op.drop_index('ix_finance_animal_date',      table_name='finance_transactions')
    op.drop_index('ix_finance_category_date',    table_name='finance_transactions')
    op.drop_index('ix_finance_type_date',        table_name='finance_transactions')
    op.drop_index('ix_finance_transactions_created_by',  table_name='finance_transactions')
    op.drop_index('ix_finance_transactions_animal_id',   table_name='finance_transactions')
    op.drop_index('ix_finance_transactions_category',    table_name='finance_transactions')
    op.drop_index('ix_finance_transactions_transaction_date', table_name='finance_transactions')
    op.drop_index('ix_finance_transactions_type',        table_name='finance_transactions')
    op.drop_table('finance_transactions')