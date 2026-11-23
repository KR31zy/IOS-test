"""Recoverable accounts, idempotent offline replay and encrypted attachments.

Revision ID: d4e2026
Revises: c0d42026
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = 'd4e2026'
down_revision = 'c0d42026'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('session_version', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('password_resets',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('token_digest',sa.String(64),unique=True,nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('used_at',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_password_resets_user_id','password_resets',['user_id'])
    op.create_table('security_throttle',
        sa.Column('key_digest',sa.String(64),primary_key=True),
        sa.Column('attempt_at',sa.DateTime(timezone=True),primary_key=True))
    op.create_table('attachments',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('farm_id',sa.String(36),sa.ForeignKey('farms.id'),nullable=False),
        sa.Column('animal_id',sa.String(36),sa.ForeignKey('animals.id'),nullable=False),
        sa.Column('event_id',sa.String(36),sa.ForeignKey('events.id'),nullable=True),
        sa.Column('author_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('display_name',sa.String(180),nullable=False),
        sa.Column('media_type',sa.String(80),nullable=False),
        sa.Column('storage_key',sa.String(90),unique=True,nullable=False),
        sa.Column('checksum',sa.String(64),nullable=False),
        sa.Column('byte_size',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('archived',sa.Boolean(),nullable=False))
    op.create_index('ix_attachments_farm_id','attachments',['farm_id'])
    op.create_index('ix_attachments_animal_id','attachments',['animal_id'])
    op.create_table('idempotency',
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('farm_id',sa.String(36),sa.ForeignKey('farms.id'),primary_key=True),
        sa.Column('request_key',sa.String(80),primary_key=True),
        sa.Column('body_hash',sa.String(64),nullable=False),
        sa.Column('resource_type',sa.String(25),nullable=False),
        sa.Column('response_json',sa.JSON().with_variant(postgresql.JSONB(),'postgresql'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('idempotency')
    op.drop_index('ix_attachments_animal_id','attachments')
    op.drop_index('ix_attachments_farm_id','attachments')
    op.drop_table('attachments')
    op.drop_table('security_throttle')
    op.drop_index('ix_password_resets_user_id','password_resets')
    op.drop_table('password_resets')
    op.drop_column('users','session_version')
