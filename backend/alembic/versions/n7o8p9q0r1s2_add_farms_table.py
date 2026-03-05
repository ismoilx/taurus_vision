"""add_farms_table

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-03-06 10:00:00.000000

Multi-farm support:
  - farms jadvali yaratish
  - animals.farm_id FK qo'shish
  - users.current_farm_id FK qo'shish
  - Default ferma yaratish va mavjud ma'lumotlarni unga bog'lash
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'n7o8p9q0r1s2'
down_revision: Union[str, None] = 'm6n7o8p9q0r1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. farms jadvali
    op.create_table(
        'farms',
        sa.Column('id',               sa.Integer(),     primary_key=True, autoincrement=True, comment='Primary key'),
        sa.Column('name',             sa.String(150),   nullable=False,   comment='Ferma nomi'),
        sa.Column('description',      sa.Text(),        nullable=True),
        sa.Column('location',         sa.String(300),   nullable=True),
        sa.Column('owner_name',       sa.String(150),   nullable=True),
        sa.Column('phone',            sa.String(30),    nullable=True),
        sa.Column('is_active',        sa.Boolean(),     nullable=False, server_default=sa.text('true')),
        sa.Column('timezone_offset',  sa.Integer(),     nullable=False, server_default=sa.text('5')),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_farms_name', 'farms', ['name'])

    # 2. Default ferma yaratish
    op.execute("""
        INSERT INTO farms (name, description, location, is_active, timezone_offset, created_at, updated_at)
        VALUES ('Asosiy Ferma', 'Tizim yaratilganda avtomatik qo''shilgan asosiy ferma', NULL, true, 5, now(), now())
    """)

    # 3. animals.farm_id qo'shish
    op.add_column('animals', sa.Column(
        'farm_id', sa.Integer(),
        sa.ForeignKey('farms.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='Jonivor tegishli bo\'lgan ferma ID si',
    ))

    # 4. Mavjud jonivolarni default fermaga bog'lash
    op.execute("""
        UPDATE animals
        SET farm_id = (SELECT id FROM farms WHERE name = 'Asosiy Ferma' LIMIT 1)
        WHERE farm_id IS NULL
    """)

    # 5. users.current_farm_id qo'shish
    op.add_column('users', sa.Column(
        'current_farm_id', sa.Integer(),
        sa.ForeignKey('farms.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='Foydalanuvchi hozir ishlayotgan ferma ID si',
    ))

    # 6. Mavjud foydalanuvchilarni default fermaga bog'lash
    op.execute("""
        UPDATE users
        SET current_farm_id = (SELECT id FROM farms WHERE name = 'Asosiy Ferma' LIMIT 1)
        WHERE current_farm_id IS NULL
    """)


def downgrade() -> None:
    op.drop_column('users', 'current_farm_id')
    op.drop_column('animals', 'farm_id')
    op.drop_index('ix_farms_name', table_name='farms')
    op.drop_table('farms')