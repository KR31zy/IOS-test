"""One-time secure team invitations for farm membership.

Revision ID: e20261113
Revises: d4e2026
"""
from alembic import op
import sqlalchemy as sa

revision = 'e20261113'
down_revision = 'd4e2026'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('farm_invitations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('farm_id', sa.String(length=36), sa.ForeignKey('farms.id'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=24), nullable=False),
        sa.Column('token_digest', sa.String(length=64), nullable=False, unique=True),
        sa.Column('invited_by', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_farm_invitations_farm_id', 'farm_invitations', ['farm_id'])
    op.create_index('ix_farm_invitations_email', 'farm_invitations', ['email'])

def downgrade():
    op.drop_index('ix_farm_invitations_email', table_name='farm_invitations')
    op.drop_index('ix_farm_invitations_farm_id', table_name='farm_invitations')
    op.drop_table('farm_invitations')
