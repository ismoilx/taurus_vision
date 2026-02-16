"""
Create health_records table

Revision ID: 0005_create_health_records
Revises: 18d7c3a397a0
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_create_health_records'
down_revision: Union[str, None] = '18d7c3a397a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create health_records table.
    
    This table stores all health-related records for animals including:
    - Regular checkups
    - Treatments and medications
    - Vaccinations
    - Injuries and surgeries
    - Scheduled follow-ups
    """
    # Create ENUM types for PostgreSQL
    op.execute("""
        CREATE TYPE healthrecordtype AS ENUM (
            'checkup', 'treatment', 'vaccination', 
            'injury', 'surgery', 'illness', 'other'
        )
    """)
    
    op.execute("""
        CREATE TYPE healthrecordseverity AS ENUM (
            'normal', 'warning', 'critical'
        )
    """)
    
    # Create health_records table
    op.create_table(
        'health_records',
        
        # Primary Key
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Foreign Key
        sa.Column('animal_id', sa.Integer(), nullable=False),
        
        # Record Classification
        sa.Column(
            'record_type',
            sa.Enum(
                'checkup', 'treatment', 'vaccination',
                'injury', 'surgery', 'illness', 'other',
                name='healthrecordtype'
            ),
            nullable=False
        ),
        sa.Column(
            'severity',
            sa.Enum(
                'normal', 'warning', 'critical',
                name='healthrecordseverity'
            ),
            nullable=False,
            server_default='normal'
        ),
        
        # Medical Information
        sa.Column('diagnosis', sa.String(length=500), nullable=False),
        sa.Column('symptoms', sa.Text(), nullable=True),
        sa.Column('treatment', sa.Text(), nullable=True),
        sa.Column('medication', sa.String(length=300), nullable=True),
        sa.Column('dosage', sa.String(length=100), nullable=True),
        
        # Medical Personnel
        sa.Column('veterinarian', sa.String(length=200), nullable=True),
        sa.Column('clinic_name', sa.String(length=300), nullable=True),
        
        # Financial
        sa.Column('cost', sa.Float(), nullable=True),
        
        # Additional Information
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('next_checkup_date', sa.Date(), nullable=True),
        
        # Resolution Status
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        
        # Audit Fields
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['animal_id'],
            ['animals.id'],
            ondelete='CASCADE'
        )
    )
    
    # Create indexes for better query performance
    op.create_index('ix_health_records_id', 'health_records', ['id'])
    op.create_index('ix_health_records_animal_id', 'health_records', ['animal_id'])
    op.create_index('ix_health_records_record_type', 'health_records', ['record_type'])
    op.create_index('ix_health_records_severity', 'health_records', ['severity'])
    op.create_index('ix_health_records_recorded_at', 'health_records', ['recorded_at'])
    op.create_index('ix_health_records_next_checkup_date', 'health_records', ['next_checkup_date'])
    op.create_index('ix_health_records_is_resolved', 'health_records', ['is_resolved'])
    
    # Create composite index for common queries
    op.create_index(
        'ix_health_records_animal_recorded',
        'health_records',
        ['animal_id', 'recorded_at']
    )
    
    # Create index for unresolved critical records
    op.create_index(
        'ix_health_records_unresolved_critical',
        'health_records',
        ['is_resolved', 'severity'],
        postgresql_where=sa.text("is_resolved = false AND severity = 'critical'")
    )
    
    # Create trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_health_records_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER health_records_updated_at_trigger
        BEFORE UPDATE ON health_records
        FOR EACH ROW
        EXECUTE FUNCTION update_health_records_updated_at();
    """)


def downgrade() -> None:
    """
    Drop health_records table and related objects.
    """
    # Drop trigger
    op.execute("""
        DROP TRIGGER IF EXISTS health_records_updated_at_trigger ON health_records;
        DROP FUNCTION IF EXISTS update_health_records_updated_at();
    """)
    
    # Drop indexes
    op.drop_index('ix_health_records_unresolved_critical', table_name='health_records')
    op.drop_index('ix_health_records_animal_recorded', table_name='health_records')
    op.drop_index('ix_health_records_is_resolved', table_name='health_records')
    op.drop_index('ix_health_records_next_checkup_date', table_name='health_records')
    op.drop_index('ix_health_records_recorded_at', table_name='health_records')
    op.drop_index('ix_health_records_severity', table_name='health_records')
    op.drop_index('ix_health_records_record_type', table_name='health_records')
    op.drop_index('ix_health_records_animal_id', table_name='health_records')
    op.drop_index('ix_health_records_id', table_name='health_records')
    
    # Drop table
    op.drop_table('health_records')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS healthrecordseverity")
    op.execute("DROP TYPE IF EXISTS healthrecordtype")

