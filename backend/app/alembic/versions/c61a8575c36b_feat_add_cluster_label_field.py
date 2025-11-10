"""feat: add cluster_label field

Revision ID: c61a8575c36b
Revises: fa6355730925
Create Date: 2025-11-10 13:32:33.582911

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c61a8575c36b'
down_revision = 'fa6355730925'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Create the location table
    op.create_table('location',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('cluster_label', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_cluster_label'), 'location', ['cluster_label'], unique=False)
    
    # Step 2: Add location_id as NULLABLE (temporary)
    op.add_column('studysite', sa.Column('location_id', sa.Uuid(), nullable=True))
    
    # Step 3: Migrate data - create location records from existing studysite coordinates
    op.execute("""
        INSERT INTO location (id, latitude, longitude, created_at)
        SELECT 
            gen_random_uuid(),
            latitude,
            longitude,
            MIN(created_at)
        FROM studysite
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY latitude, longitude
    """)
    
    # Step 4: Update studysite to reference the new location records
    op.execute("""
        UPDATE studysite s
        SET location_id = l.id
        FROM location l
        WHERE s.latitude = l.latitude 
          AND s.longitude = l.longitude
    """)
    
    # Step 5: Make location_id NOT NULL now that all rows have values
    op.alter_column('studysite', 'location_id',
                    existing_type=sa.Uuid(),
                    nullable=False)
    
    # Step 6: Create foreign key and index
    op.create_index(op.f('ix_studysite_location_id'), 'studysite', ['location_id'], unique=False)
    op.create_foreign_key(None, 'studysite', 'location', ['location_id'], ['id'])
    
    # Step 7: Remove old latitude/longitude columns
    op.drop_column('studysite', 'latitude')
    op.drop_column('studysite', 'longitude')
    
    # Step 8: Update studysite timestamps
    op.alter_column('studysite', 'created_at',
                    existing_type=sa.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False)
    op.alter_column('studysite', 'updated_at',
                    existing_type=sa.TIMESTAMP(),
                    nullable=False)
    
    # Step 9: Update item timestamps
    op.alter_column('item', 'dateAdded',
                    existing_type=sa.TIMESTAMP(),
                    type_=sa.DateTime(timezone=True),
                    nullable=False)
    op.alter_column('item', 'dateModified',
                    existing_type=sa.TIMESTAMP(),
                    nullable=False)
    
    # Step 10: Add timestamps to tag table
    op.add_column('tag', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('tag', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    
    # Step 11: Add timestamps to user table
    op.add_column('user', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('user', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    # Reverse user timestamps
    op.drop_column('user', 'updated_at')
    op.drop_column('user', 'created_at')
    
    # Reverse tag timestamps
    op.drop_column('tag', 'updated_at')
    op.drop_column('tag', 'created_at')
    
    # Reverse item timestamp changes
    op.alter_column('item', 'dateModified',
                    existing_type=sa.TIMESTAMP(),
                    nullable=True)
    op.alter_column('item', 'dateAdded',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.TIMESTAMP(),
                    nullable=True)
    
    # Reverse studysite timestamp changes
    op.alter_column('studysite', 'updated_at',
                    existing_type=sa.TIMESTAMP(),
                    nullable=True)
    op.alter_column('studysite', 'created_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.TIMESTAMP(),
                    existing_nullable=False)
    
    # Add back latitude/longitude columns
    op.add_column('studysite', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('studysite', sa.Column('latitude', sa.Float(), nullable=True))
    
    # Migrate data back from location table
    op.execute("""
        UPDATE studysite s
        SET latitude = l.latitude,
            longitude = l.longitude
        FROM location l
        WHERE s.location_id = l.id
    """)
    
    # Drop foreign key and index
    op.drop_constraint(None, 'studysite', type_='foreignkey')
    op.drop_index(op.f('ix_studysite_location_id'), table_name='studysite')
    
    # Drop location_id column
    op.drop_column('studysite', 'location_id')
    
    # Drop location table
    op.drop_index(op.f('ix_location_cluster_label'), table_name='location')
    op.drop_table('location')
