"""fix: add server defaults to timestamp columns

Revision ID: 72d7480a401f
Revises: 935fdf0c43c9
Create Date: 2025-11-10 14:02:12.290295

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '72d7480a401f'
down_revision = '935fdf0c43c9'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # First, add server defaults to created_at columns
    op.alter_column('item', 'dateAdded',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    op.alter_column('item', 'dateModified',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    op.alter_column('location', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    op.alter_column('studysite', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    op.alter_column('tag', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    op.alter_column('user', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    existing_nullable=False)
    
    # For updated_at columns:
    # Step 1: Populate NULL values with created_at values
    op.execute("""
        UPDATE "user" 
        SET updated_at = created_at 
        WHERE updated_at IS NULL
    """)
    op.execute("""
        UPDATE tag 
        SET updated_at = created_at 
        WHERE updated_at IS NULL
    """)
    op.execute("""
        UPDATE location 
        SET updated_at = created_at 
        WHERE updated_at IS NULL
    """)
    op.execute("""
        UPDATE studysite 
        SET updated_at = created_at 
        WHERE updated_at IS NULL
    """)
    
    # Step 2: Add server defaults and make NOT NULL
    op.alter_column('location', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    nullable=False)
    op.alter_column('studysite', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    nullable=False)
    op.alter_column('tag', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    nullable=False)
    op.alter_column('user', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=sa.text('now()'),
                    nullable=False)


def downgrade() -> None:
    # Reverse updated_at changes
    op.alter_column('user', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    nullable=True)
    op.alter_column('tag', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    nullable=True)
    op.alter_column('studysite', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    nullable=True)
    op.alter_column('location', 'updated_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    nullable=True)
    
    # Reverse created_at changes
    op.alter_column('user', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
    op.alter_column('tag', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
    op.alter_column('studysite', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
    op.alter_column('location', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
    op.alter_column('item', 'dateModified',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)
    op.alter_column('item', 'dateAdded',
                    existing_type=sa.DateTime(timezone=True),
                    server_default=None,
                    existing_nullable=False)

