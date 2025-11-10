"""feat: add cluster_label field

Revision ID: fa6355730925
Revises: 7e7fb2e498c2
Create Date: 2025-11-10 13:25:10.338577

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fa6355730925'
down_revision = '7e7fb2e498c2'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Step 1: Create the location table first
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
    
    # Step 2: Add location_id as NULLABLE first
    op.add_column('studysite', sa.Column('location_id', sa.Uuid(), nullable=True))
    
    # Step 3: Migrate existing data - create location records from studysite lat/lon
    op.execute("""
        INSERT INTO location (id, latitude, longitude, created_at)
        SELECT 
            gen_random_uuid(),
            latitude,
            longitude,
            created_at
        FROM studysite
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    
    # Step 4: Update studysite to reference the new location records
    op.execute("""
        UPDATE studysite s
        SET location_id = l.id
        FROM location l
        WHERE s.latitude = l.latitude 
          AND s.longitude = l.longitude
    """)
    
    # Step 5: Now make location_id NOT NULL (all rows should have values)
    op.alter_column('studysite', 'location_id',
                    existing_type=sa.Uuid(),
                    nullable=False)
    
    # Step 6: Create the foreign key and index
    op.create_index(op.f('ix_studysite_location_id'), 'studysite', ['location_id'], unique=False)
    op.create_foreign_key(None, 'studysite', 'location', ['location_id'], ['id'])
    
    # Step 7: Remove old columns
    op.drop_column('studysite', 'latitude')
    op.drop_column('studysite', 'longitude')
    
    op.alter_column('item', 'dateAdded',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               nullable=False)
    op.alter_column('item', 'dateModified',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
    op.add_column('studysite', sa.Column('location_id', sa.Uuid(), nullable=False))
    op.alter_column('studysite', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
    op.alter_column('studysite', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
    op.create_index(op.f('ix_studysite_location_id'), 'studysite', ['location_id'], unique=False)
    op.create_foreign_key(None, 'studysite', 'location', ['location_id'], ['id'])
    op.drop_column('studysite', 'latitude')
    op.drop_column('studysite', 'longitude')
    op.add_column('tag', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('tag', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('user', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('user', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    # ### end Alembic commands ###



def downgrade() -> None:
    # Step 1: Add back the old columns
    op.add_column('studysite', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column('studysite', sa.Column('latitude', sa.Float(), nullable=True))
    
    # Step 2: Migrate data back from location table
    op.execute("""
        UPDATE studysite s
        SET latitude = l.latitude,
            longitude = l.longitude
        FROM location l
        WHERE s.location_id = l.id
    """)
    
    # Step 3: Drop foreign key and location_id
    op.drop_constraint(None, 'studysite', type_='foreignkey')
    op.drop_index(op.f('ix_studysite_location_id'), table_name='studysite')
    op.drop_column('studysite', 'location_id')
    
    # Step 4: Drop location table
    op.drop_index(op.f('ix_location_cluster_label'), table_name='location')
    op.drop_table('location')
    
    # ... reverse other changes

    op.drop_column('user', 'updated_at')
    op.drop_column('user', 'created_at')
    op.drop_column('tag', 'updated_at')
    op.drop_column('tag', 'created_at')
    op.alter_column('item', 'dateModified',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
    op.alter_column('item', 'dateAdded',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               nullable=True)
    # ### end Alembic commands ###
