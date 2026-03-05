"""add profile_image and animal_photos table

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-01-01 00:00:00.000000

animals jadvaliga profile_image_url ustuni qo'shiladi.
animal_photos yangi jadvali yaratiladi (ko'p rasm saqlovchi).
"""
from typing import Union
import sqlalchemy as sa
from alembic import op


revision:      str               = 'l5m6n7o8p9q0'
down_revision: Union[str, None]  = 'k4l5m6n7o8p9'
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # animals jadvaliga profil rasmi URL
    op.add_column(
        'animals',
        sa.Column(
            'profile_image',
            sa.String(length=500),
            nullable=True,
            comment='Profil rasmi fayl yo\'li (data/images/animals/ ichida)',
        ),
    )

    # Ko'p rasm uchun alohida jadval
    op.create_table(
        'animal_photos',
        sa.Column('id',         sa.Integer(),      nullable=False, autoincrement=True),
        sa.Column('animal_id',  sa.Integer(),      nullable=False),
        sa.Column('file_path',  sa.String(500),    nullable=False, comment='Fayl yo\'li (data/images/animals/ ichida)'),
        sa.Column('file_name',  sa.String(200),    nullable=False, comment='Asl fayl nomi'),
        sa.Column('file_size',  sa.Integer(),      nullable=True,  comment='Fayl hajmi (bayt)'),
        sa.Column('created_at', sa.DateTime(),     nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['animal_id'], ['animals.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_animal_photos_animal_id', 'animal_photos', ['animal_id'])


def downgrade() -> None:
    op.drop_index('ix_animal_photos_animal_id', table_name='animal_photos')
    op.drop_table('animal_photos')
    op.drop_column('animals', 'profile_image')