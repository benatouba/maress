"""enable postgis and add geometry column to location

Revision ID: a1b2c3d4e5f6
Revises: 9d2b6a1f4a8b
Create Date: 2026-04-01 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9d2b6a1f4a8b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Add geometry column to location table
    op.execute(
        "ALTER TABLE location ADD COLUMN geom geometry(Point, 4326)"
    )

    # Backfill from existing lat/lon data
    op.execute(
        "UPDATE location SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)"
    )

    # Set NOT NULL after backfill
    op.execute("ALTER TABLE location ALTER COLUMN geom SET NOT NULL")

    # Create spatial index
    op.execute(
        "CREATE INDEX ix_location_geom ON location USING GIST(geom)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_location_geom")
    op.execute("ALTER TABLE location DROP COLUMN IF EXISTS geom")
