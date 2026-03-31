"""add location lon-lat index

Revision ID: 9d2b6a1f4a8b
Revises: 4c15100cec01
Create Date: 2026-04-01 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "9d2b6a1f4a8b"
down_revision = "4c15100cec01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_location_lon_lat", "location", ["longitude", "latitude"], unique=False)


def downgrade():
    op.drop_index("ix_location_lon_lat", table_name="location")
