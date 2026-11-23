#!/usr/bin/env python3
"""Opt-in patch for the exact supplied backend. Back up and migrate separately.
Email login and existing accounts remain supported. No credentials are created.
"""
import argparse
import ast
from pathlib import Path

MIGRATION = '''"""Add optional unique usernames for mobile authentication."""
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
'''

def transform(source):
    def replace(old,new):
        nonlocal source
        if source.count(old)!=1:
            raise ValueError('Expected exactly one matching block: '+old[:100])
        source=source.replace(old,new,1)
    replace('import os\n','import os\nimport re\n')
    replace("    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)\n", "    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)\n    username: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)\n")
    replace('class LoginInput(BaseModel):\n    email: EmailStr\n    password: str\n', '''def normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,31}', value):
        raise ValueError('Username must contain 3–32 letters, numbers, dots, underscores or hyphens')
    return value

class LoginInput(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, max_length=32)
    password: str

    @model_validator(mode='after')
    def one_identifier(self):
        if bool(self.email) == bool(self.username):
            raise ValueError('Provide either email or username')
        if self.username is not None:
            self.username = normalize_username(self.username)
        return self

class UsernameInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=32)

    @field_validator('username')
    @classmethod
    def normalized(cls, value: str):
        return normalize_username(value)
''')
    replace("    model_config = ConfigDict(extra='forbid')\n    email: EmailStr\n    password: str = Field(min_length=12, max_length=256)\n    full_name:", "    model_config = ConfigDict(extra='forbid')\n    email: EmailStr\n    username: str | None = Field(default=None, min_length=3, max_length=32)\n    password: str = Field(min_length=8, max_length=256)\n    full_name:")
    replace("    @field_validator('full_name', 'farm_name')", "    @field_validator('username')\n    @classmethod\n    def normalized_username(cls, value):\n        return normalize_username(value) if value is not None else None\n\n    @field_validator('full_name', 'farm_name')")
    replace("    user = User(email=email, name=data.full_name, password_hash=passwords.hash(data.password), role='farm_manager')", "    if data.username and db.scalar(select(User.id).where(User.username == data.username)):\n        db.commit()\n        raise HTTPException(409, 'Username unavailable')\n    user = User(email=email, username=data.username, name=data.full_name, password_hash=passwords.hash(data.password), role='farm_manager')")
    replace("    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))\n    try:\n        verified", "    identity = str(data.email).strip().lower() if data.email else data.username\n    user = db.scalar(select(User).where(User.email == identity if data.email else User.username == identity))\n    try:\n        verified")
    replace("f'login:account:{data.email.strip().lower()}'", "f'login:account:{user.email if user else identity}'")
    replace("    return {**farm_role_view(db, user), 'email': user.email}\n", "    return {**farm_role_view(db, user), 'email': user.email, 'username': user.username}\n\n@app.patch('/api/auth/username')\ndef change_username(data: UsernameInput, user: Auth, db: DB):\n    if db.scalar(select(User.id).where(User.username == data.username, User.id != user.id)):\n        raise HTTPException(409, 'Username unavailable')\n    user.username = data.username\n    record_audit(db, user, None, 'account.username', user.id)\n    try:\n        db.commit()\n    except IntegrityError:\n        db.rollback()\n        raise HTTPException(409, 'Username unavailable') from None\n    return {'username': user.username}\n")
    # Match the user's chosen eight-character minimum in all create/reset flows.
    source=source.replace('password: str = Field(min_length=12', 'password: str = Field(min_length=8')
    # Existing invitation accounts authenticate rather than create a new password.
    replace("    token: str = Field(min_length=32, max_length=160)\n    password: str = Field(min_length=8, max_length=256)\n    full_name:", "    token: str = Field(min_length=32, max_length=160)\n    password: str = Field(min_length=1, max_length=256)\n    full_name:")
    replace("        if len(data.full_name.strip()) < 2:\n", "        if len(data.password) < 8:\n            raise HTTPException(422, 'New passwords require at least 8 characters')\n        if len(data.full_name.strip()) < 2:\n")
    ast.parse(source)
    return source

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend',type=Path,default=Path(__file__).resolve().parents[2]/'backend')
    p.add_argument('--apply',action='store_true',help='Write reviewed patch and migration; without it only validates applicability.')
    args=p.parse_args(); root=args.backend.resolve(); target=root/'app/main.py'; migrations=root/'migrations/versions'; migration=migrations/'m20261119_username.py'; backup=target.with_suffix('.py.before_mobile_username')
    old=target.read_text(encoding='utf-8')
    if migration.exists() and 'def normalize_username(' in old:
        print('Patch already present. Verify database migration.');return
    if not (migrations/'f220261119_merge_notifications_and_archive.py').exists():raise SystemExit('Wrong backend migration baseline; patch not applied.')
    new=transform(old)
    if not args.apply:print('Patch matches backend. No files changed. Run again with --apply to write.');return
    if backup.exists() or migration.exists():raise SystemExit('Existing backup/migration found. Review manually; no files changed.')
    backup.write_text(old,encoding='utf-8');migration.write_text(MIGRATION,encoding='utf-8');target.write_text(new,encoding='utf-8')
    print('Patched source and added migration. Back up DB, run alembic upgrade head, then restart server. Original source backup:',backup)
if __name__=='__main__':main()
