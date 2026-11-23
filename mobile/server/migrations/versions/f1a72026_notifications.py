"""Durable recipient-scoped notifications."""
from alembic import op
import sqlalchemy as sa

revision = 'f1a72026'
down_revision = 'e20261113'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('notifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('recipient_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('farm_id', sa.String(36), sa.ForeignKey('farms.id'), nullable=True),
        sa.Column('event_type', sa.String(80), nullable=False), sa.Column('resource_type', sa.String(32)),
        sa.Column('resource_id', sa.String(36)), sa.Column('title', sa.String(180), nullable=False),
        sa.Column('message', sa.String(500), nullable=False), sa.Column('priority', sa.String(24), nullable=False),
        sa.Column('deduplication_key', sa.String(180)), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)), sa.Column('dismissed_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('recipient_user_id','deduplication_key',name='uq_notification_recipient_dedupe'))
    for col in ('recipient_user_id','farm_id','event_type','created_at'):
        op.create_index(f'ix_notifications_{col}', 'notifications', [col])
    op.create_index('ix_notifications_recipient_read_created','notifications',['recipient_user_id','read_at','created_at'])

def downgrade():
    op.drop_index('ix_notifications_recipient_read_created', table_name='notifications')
    for col in ('created_at','event_type','farm_id','recipient_user_id'):
        op.drop_index(f'ix_notifications_{col}', table_name='notifications')
    op.drop_table('notifications')
