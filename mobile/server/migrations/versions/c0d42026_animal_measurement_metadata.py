"""Add date of birth and initial weight to animal profiles.

Revision ID: c0d42026
Revises: bff1a7f474c6
"""
from alembic import op
import sqlalchemy as sa
revision = 'c0d42026'
down_revision = 'bff1a7f474c6'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('animals', sa.Column('date_of_birth', sa.String(length=10), nullable=True))
    op.add_column('animals', sa.Column('weight_kg', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('animals', 'weight_kg')
    op.drop_column('animals', 'date_of_birth')
