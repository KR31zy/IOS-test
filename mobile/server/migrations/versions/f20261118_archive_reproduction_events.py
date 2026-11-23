"""Archive reproduction events without deleting their audit history."""

from alembic import op
import sqlalchemy as sa

revision = 'f20261118'
down_revision = 'e20261113'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('events', sa.Column('archived', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    op.drop_column('events', 'archived')
