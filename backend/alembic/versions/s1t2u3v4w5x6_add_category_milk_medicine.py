"""add_category_milk_medicine

Revision ID: s1t2u3v4w5x6
Revises: r2s3t4u5v6w7
Create Date: 2026-03-07
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "s1t2u3v4w5x6"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Barcha DDL raw SQL orqali — asyncpg enum muammosini chetlab o'tadi

    op.execute("""
        ALTER TABLE animals ADD COLUMN IF NOT EXISTS category VARCHAR(50);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_animals_category ON animals (category);
    """)

    # Enum types — IF NOT EXISTS bilan
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE milk_session AS ENUM ('morning','midday','evening','daily');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE milk_quality_grade AS ENUM ('premium','standard','low','rejected');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE medicine_type AS ENUM (
                'vaccine','antibiotic','antiparasitic','vitamin',
                'hormone','analgesic','antifungal','disinfectant',
                'supplement','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE medicine_unit AS ENUM (
                'ml','l','mg','g','tablet','dose','vial','pack'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE medicine_admin_route AS ENUM (
                'injection_im','injection_iv','injection_sc',
                'oral','topical','intranasal','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # milk_productions jadvali
    op.execute("""
        CREATE TABLE IF NOT EXISTS milk_productions (
            id                  SERIAL PRIMARY KEY,
            animal_id           INTEGER NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
            record_date         DATE NOT NULL,
            session             milk_session NOT NULL DEFAULT 'daily',
            milk_kg             FLOAT NOT NULL,
            fat_percent         FLOAT,
            protein_percent     FLOAT,
            somatic_cell_count  INTEGER,
            lactose_percent     FLOAT,
            lactation_number    INTEGER,
            days_in_milk        INTEGER,
            quality_grade       milk_quality_grade,
            temperature_c       FLOAT,
            milked_by           VARCHAR(200),
            notes               TEXT,
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT check_milk_kg_positive      CHECK (milk_kg >= 0),
            CONSTRAINT check_fat_range             CHECK (fat_percent IS NULL OR (fat_percent >= 0 AND fat_percent <= 15)),
            CONSTRAINT check_protein_range         CHECK (protein_percent IS NULL OR (protein_percent >= 0 AND protein_percent <= 10)),
            CONSTRAINT check_lactation_number      CHECK (lactation_number IS NULL OR lactation_number >= 1),
            CONSTRAINT check_dim_positive          CHECK (days_in_milk IS NULL OR days_in_milk >= 0)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_milk_animal_date ON milk_productions (animal_id, record_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_milk_date        ON milk_productions (record_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_milk_productions_id ON milk_productions (id);")

    # medicine_inventory jadvali
    op.execute("""
        CREATE TABLE IF NOT EXISTS medicine_inventory (
            id                  SERIAL PRIMARY KEY,
            name                VARCHAR(300) NOT NULL,
            generic_name        VARCHAR(300),
            medicine_type       medicine_type NOT NULL,
            manufacturer        VARCHAR(200),
            batch_number        VARCHAR(100),
            quantity            FLOAT NOT NULL DEFAULT 0,
            unit                medicine_unit NOT NULL DEFAULT 'ml',
            min_stock_quantity  FLOAT NOT NULL DEFAULT 10,
            purchase_price      FLOAT,
            expiry_date         DATE,
            storage_temp_min    FLOAT,
            storage_temp_max    FLOAT,
            dosage_instructions TEXT,
            notes               TEXT,
            is_active           BOOLEAN NOT NULL DEFAULT true,
            species_applicable  VARCHAR(200),
            created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT check_medicine_qty_positive CHECK (quantity >= 0),
            CONSTRAINT check_min_stock_positive    CHECK (min_stock_quantity >= 0)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_inventory_id          ON medicine_inventory (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_inventory_name        ON medicine_inventory (name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_inventory_expiry_date ON medicine_inventory (expiry_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_type_active           ON medicine_inventory (medicine_type, is_active);")

    # medicine_usages jadvali
    op.execute("""
        CREATE TABLE IF NOT EXISTS medicine_usages (
            id                SERIAL PRIMARY KEY,
            medicine_id       INTEGER NOT NULL REFERENCES medicine_inventory(id) ON DELETE RESTRICT,
            animal_id         INTEGER NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
            health_record_id  INTEGER REFERENCES health_records(id) ON DELETE SET NULL,
            given_date        TIMESTAMP NOT NULL DEFAULT NOW(),
            quantity_given    FLOAT NOT NULL,
            admin_route       medicine_admin_route,
            given_by          VARCHAR(200),
            next_dose_date    DATE,
            withdrawal_date   DATE,
            notes             TEXT,
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            CONSTRAINT check_usage_qty_positive CHECK (quantity_given > 0)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usages_id               ON medicine_usages (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usages_medicine_id      ON medicine_usages (medicine_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usages_animal_id        ON medicine_usages (animal_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usages_health_record_id ON medicine_usages (health_record_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usages_given_date       ON medicine_usages (given_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_medicine_usage_animal_date       ON medicine_usages (animal_id, given_date);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS medicine_usages;")
    op.execute("DROP TABLE IF EXISTS medicine_inventory;")
    op.execute("DROP TABLE IF EXISTS milk_productions;")
    op.execute("DROP INDEX IF EXISTS ix_animals_category;")
    op.execute("ALTER TABLE animals DROP COLUMN IF EXISTS category;")
    op.execute("DROP TYPE IF EXISTS milk_session;")
    op.execute("DROP TYPE IF EXISTS milk_quality_grade;")
    op.execute("DROP TYPE IF EXISTS medicine_type;")
    op.execute("DROP TYPE IF EXISTS medicine_unit;")
    op.execute("DROP TYPE IF EXISTS medicine_admin_route;")