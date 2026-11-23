"""Add optional unique usernames for mobile authentication."""
from alembic import op
import sqlalchemy as sa
revision = 'm20261119_username'
down_revision = 'f220261119'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('username', sa.String(32), nullable=True))
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

def downgrade():
    op.drop_index('ix_users_username', table_name='users')
    op.drop_column('users', 'username')
