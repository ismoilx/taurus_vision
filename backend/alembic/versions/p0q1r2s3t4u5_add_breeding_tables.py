"""add breeding tables

Revision ID: p0q1r2s3t4u5
Revises: o8p9q0r1s2t3
Create Date: 2026-03-06 10:00:00.000000
"""

from alembic import op

revision = "p0q1r2s3t4u5"
down_revision = "o8p9q0r1s2t3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE mating_method AS ENUM (
                'natural', 'artificial_insemination', 'embryo_transfer'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE breeding_status AS ENUM (
                'planned', 'confirmed_pregnant', 'birthed', 'failed', 'aborted'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE pregnancy_check_method AS ENUM (
                'ultrasound', 'blood_test', 'visual', 'rectal_exam'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE offspring_outcome AS ENUM (
                'alive', 'stillborn', 'died_shortly'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS breeding_records (
            id                     SERIAL PRIMARY KEY,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            farm_id                INTEGER REFERENCES farms(id) ON DELETE SET NULL,
            mother_id              INTEGER NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
            father_id              INTEGER REFERENCES animals(id) ON DELETE SET NULL,
            external_sire_tag      VARCHAR(100),
            external_sire_breed    VARCHAR(100),
            external_sire_farm     VARCHAR(200),
            mating_date            DATE NOT NULL,
            mating_method          mating_method NOT NULL DEFAULT 'natural',
            status                 breeding_status NOT NULL DEFAULT 'planned',
            gestation_days         INTEGER NOT NULL DEFAULT 283,
            expected_birth_date    DATE,
            pregnancy_confirmed_at DATE,
            pregnancy_check_method pregnancy_check_method,
            pregnancy_check_notes  VARCHAR(500),
            actual_birth_date      DATE,
            live_offspring_count   INTEGER NOT NULL DEFAULT 0,
            stillborn_count        INTEGER NOT NULL DEFAULT 0,
            birth_complications    VARCHAR(500),
            abort_date             DATE,
            abort_reason           VARCHAR(300),
            veterinarian           VARCHAR(200),
            notes                  TEXT,
            created_by_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT ck_breeding_sire_required
                CHECK ((father_id IS NOT NULL) OR (external_sire_tag IS NOT NULL)),
            CONSTRAINT ck_breeding_live_non_negative
                CHECK (live_offspring_count >= 0),
            CONSTRAINT ck_breeding_stillborn_non_negative
                CHECK (stillborn_count >= 0),
            CONSTRAINT ck_breeding_gestation_range
                CHECK (gestation_days BETWEEN 100 AND 400)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_records_mother_id   ON breeding_records (mother_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_records_father_id   ON breeding_records (father_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_records_farm_id     ON breeding_records (farm_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_records_status      ON breeding_records (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_records_mating_date ON breeding_records (mating_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_mother_date         ON breeding_records (mother_id, mating_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_status_date         ON breeding_records (status, expected_birth_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_breeding_farm_status         ON breeding_records (farm_id, status);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS offspring_records (
            id                 SERIAL PRIMARY KEY,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            breeding_record_id INTEGER NOT NULL REFERENCES breeding_records(id) ON DELETE CASCADE,
            animal_id          INTEGER REFERENCES animals(id) ON DELETE SET NULL,
            birth_order        INTEGER NOT NULL DEFAULT 1,
            gender             VARCHAR(10),
            birth_weight_kg    FLOAT,
            outcome            offspring_outcome NOT NULL DEFAULT 'alive',
            notes              VARCHAR(500),
            CONSTRAINT ck_offspring_order_positive
                CHECK (birth_order >= 1),
            CONSTRAINT ck_offspring_weight_positive
                CHECK (birth_weight_kg IS NULL OR birth_weight_kg > 0)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_offspring_breeding_id ON offspring_records (breeding_record_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_offspring_animal_id   ON offspring_records (animal_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS offspring_records CASCADE;")
    op.execute("DROP TABLE IF EXISTS breeding_records CASCADE;")
    op.execute("DROP TYPE IF EXISTS offspring_outcome;")
    op.execute("DROP TYPE IF EXISTS pregnancy_check_method;")
    op.execute("DROP TYPE IF EXISTS breeding_status;")
    op.execute("DROP TYPE IF EXISTS mating_method;")
