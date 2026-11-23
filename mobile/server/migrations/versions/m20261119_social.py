"""Social identities and short-lived sign-in transactions."""
from alembic import op
import sqlalchemy as sa
revision='m20261119_social'
down_revision='m20261119_username'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('social_identities',sa.Column('provider',sa.String(12),primary_key=True),sa.Column('subject',sa.String(255),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False))
    op.create_index('ix_social_identities_user_id','social_identities',['user_id'])
    op.create_table('social_flows',sa.Column('state',sa.String(64),primary_key=True),sa.Column('proof',sa.String(64),nullable=False),sa.Column('provider',sa.String(12),nullable=False),sa.Column('nonce',sa.String(128),nullable=False),sa.Column('verifier',sa.String(128),nullable=False),sa.Column('expires',sa.DateTime(timezone=True),nullable=False),sa.Column('status',sa.String(24),nullable=False),sa.Column('subject',sa.String(255)),sa.Column('email',sa.String(255)),sa.Column('name',sa.String(180)))
    op.create_index('ix_social_flows_expires','social_flows',['expires'])

def downgrade():
    op.drop_table('social_flows');op.drop_table('social_identities')
