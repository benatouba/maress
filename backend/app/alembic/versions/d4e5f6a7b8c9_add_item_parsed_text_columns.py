"""add item parsed text columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-28 09:15:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("item", sa.Column("parsed_text", sa.Text(), nullable=True))
    op.add_column("item", sa.Column("parsed_text_search", postgresql.TSVECTOR(), nullable=True))

    op.execute(
        """
        UPDATE item
        SET parsed_text_search = to_tsvector('simple', COALESCE(parsed_text, ''))
        """
    )

    op.execute(
        """
        CREATE FUNCTION item_parsed_text_search_update() RETURNS trigger AS $$
        BEGIN
            NEW.parsed_text_search := to_tsvector('simple', COALESCE(NEW.parsed_text, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER item_parsed_text_search_trigger
        BEFORE INSERT OR UPDATE OF parsed_text ON item
        FOR EACH ROW
        EXECUTE FUNCTION item_parsed_text_search_update();
        """
    )

    op.create_index(
        "ix_item_parsed_text_search",
        "item",
        ["parsed_text_search"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_item_parsed_text_search", table_name="item")
    op.execute("DROP TRIGGER IF EXISTS item_parsed_text_search_trigger ON item")
    op.execute("DROP FUNCTION IF EXISTS item_parsed_text_search_update")
    op.drop_column("item", "parsed_text_search")
    op.drop_column("item", "parsed_text")
