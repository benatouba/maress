"""add item data availability link

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-28 13:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("item", sa.Column("data_availability_link", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("item", "data_availability_link")
