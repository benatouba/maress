"""create region table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-01 12:01:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE region (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description VARCHAR(2048) NOT NULL DEFAULT '',
            source_filename VARCHAR(255),
            properties_json TEXT,
            owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            geom geometry(MultiPolygon, 4326) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_region_geom ON region USING GIST(geom)")
    op.execute("CREATE INDEX ix_region_owner_id ON region(owner_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS region")
