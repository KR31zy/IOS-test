"""AniRepro 360 Phase 4: server-owned records. No browser-state credentials are trusted."""
import os
import re
import base64
import hashlib
import hmac
import io
import json
import math
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from email.utils import formatdate
import secrets
import uuid
from statistics import median, mean, pstdev
from datetime import datetime, timedelta, timezone, date
from typing import Annotated, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile, File, Form, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Integer, create_engine, select, text, func, and_, or_, exists, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.types import JSON
from sqlalchemy.exc import IntegrityError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./anirepro-development.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
if DATABASE_URL.startswith('sqlite:') and os.getenv('APP_ENV', 'development') == 'production':
    raise RuntimeError('Production requires PostgreSQL DATABASE_URL')
SECRET = os.getenv('SESSION_SECRET', '')
if os.getenv('APP_ENV') == 'production' and len(SECRET) < 32:
    raise RuntimeError('SESSION_SECRET must be at least 32 characters in production')
if not SECRET:
    SECRET = secrets.token_urlsafe(48)  # development sessions reset on restart
if os.getenv('APP_ENV') == 'production':
    try:
        file_key = base64.b64decode(os.getenv('FILE_ENCRYPTION_KEY', ''), validate=True)
    except (ValueError, base64.binascii.Error):
        file_key = b''
    if len(file_key) != 32:
        raise RuntimeError('Production requires a persisted, 32-byte FILE_ENCRYPTION_KEY')
    if not os.getenv('SMTP_HOST') or not os.getenv('SMTP_FROM') or not os.getenv('RESET_URL_BASE', '').startswith('https://'):
        raise RuntimeError('Production requires SMTP and an HTTPS password-recovery URL')
    cors_list = [u.strip() for u in os.getenv('CORS_ORIGINS', '').split(',') if u.strip()]
    if not cors_list or any(not u.startswith('https://') for u in cors_list):
        raise RuntimeError('Production requires explicit HTTPS CORS_ORIGINS')
IS_PG = DATABASE_URL.startswith('postgresql')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine)
passwords = PasswordHasher()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(24), default='farmer')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(Integer, default=0)

class Farm(Base):
    __tablename__ = 'farms'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(180))
    location: Mapped[str] = mapped_column(String(255), default='')
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

class Membership(Base):
    __tablename__ = 'memberships'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(24))

class Animal(Base):
    __tablename__ = 'animals'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), index=True)
    name: Mapped[str] = mapped_column(String(180))
    species: Mapped[str] = mapped_column(String(100))
    breed: Mapped[str] = mapped_column(String(100), default='')
    sex: Mapped[str] = mapped_column(String(20), default='unknown')
    tag: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[str | None] = mapped_column(String(10), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint('farm_id', 'tag', name='uq_animal_farm_tag'),)

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), index=True)
    animal_id: Mapped[str] = mapped_column(ForeignKey('animals.id'), index=True)
    category: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, 'postgresql'), default=dict)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    farm_id: Mapped[str | None] = mapped_column(ForeignKey('farms.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(36))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey('farms.id'), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(String(500))
    priority: Mapped[str] = mapped_column(String(24), default='informational')
    deduplication_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint('recipient_user_id', 'deduplication_key', name='uq_notification_recipient_dedupe'),)

class FarmInvitation(Base):
    """One-use, short-lived invitations: plaintext tokens never enter the database."""
    __tablename__ = 'farm_invitations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(24))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class PasswordReset(Base):
    __tablename__ = 'password_resets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class SecurityThrottle(Base):
    __tablename__ = 'security_throttle'
    key_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

class Attachment(Base):
    __tablename__ = 'attachments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), index=True)
    animal_id: Mapped[str] = mapped_column(ForeignKey('animals.id'), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey('events.id'), nullable=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    display_name: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(90), unique=True)
    checksum: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

class Idempotency(Base):
    __tablename__ = 'idempotency'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey('farms.id'), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(25))
    response_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, 'postgresql'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

app = FastAPI(title='AniRepro 360 API', version='0.4.0', docs_url='/docs')
origins = [s.strip() for s in os.getenv('CORS_ORIGINS', 'http://localhost:8080,http://127.0.0.1:8080').split(',') if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Content-Type','X-CSRF-Token','X-Idempotency-Key'])

@app.middleware('http')
async def add_secure_headers(request: Request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin not in origins and not (request.url.path == '/api/auth/social/callback/apple' and origin == 'https://appleid.apple.com'):
            return Response(status_code=403, content='Origin not allowed')
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    if os.getenv('APP_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Schema creation is intentionally a separate explicit command (python -m app.init_db).
def get_db():
    with SessionLocal() as db:
        yield db

DB = Annotated[Session, Depends(get_db)]

def require_user(request: Request, db: DB) -> User:
    token = request.cookies.get('anirepro_session')
    if not token:
        raise HTTPException(401, 'Authentication required')
    try:
        claims = jwt.decode(token, SECRET, algorithms=['HS256'], options={'require': ['sub','exp','iat']})
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Invalid or expired session') from None
    user = db.get(User, claims['sub'])
    if not user or not user.active or claims.get('ver') != user.session_version:
        raise HTTPException(401, 'Account inactive or session revoked')
    if request.method not in ('GET','HEAD','OPTIONS'):
        csrf = request.headers.get('X-CSRF-Token')
        if not csrf or csrf != claims.get('csrf'):
            raise HTTPException(403, 'CSRF protection failed')
        origin = request.headers.get('origin')
        if origin and origin not in origins:
            raise HTTPException(403, 'Origin not allowed')
    return user

Auth = Annotated[User, Depends(require_user)]

def farm_role(db: Session, user: User, farm_id: str, accepted: set[str] | None = None) -> str:
    farm = db.get(Farm, farm_id)
    if not farm or farm.archived:
        raise HTTPException(404, 'Farm not found')
    membership = db.get(Membership, (user.id, farm_id))
    if not membership:
        raise HTTPException(404, 'Farm not found')
    if accepted and membership.role not in accepted:
        raise HTTPException(403, 'Insufficient farm permissions')
    return membership.role

WRITERS = {'farm_manager', 'veterinarian', 'farmer', 'breeder'}
CLINICIANS = {'veterinarian'}
MANAGERS = {'farm_manager'}
EVIDENCE_READERS = {'farm_manager', 'veterinarian', 'farmer', 'breeder'}

# Farm permissions are derived only from the active farm membership. There is no
# platform-admin provisioning or research governance model in this release.
ROLE_PERMISSIONS = {
    'farm_manager': {'farm.view','dashboard.view','animals.view','animals.create','health.view','health.observe',
        'reproduction.view','reproduction.observe',
        'breeding.observe','tasks.view','tasks.complete','evidence.view','evidence.create','reports.view','reports.export',
        'members.view','members.invite','members.update_role','members.remove','audit.view'},
    'veterinarian': {'farm.view','dashboard.view','animals.view','health.view','health.record','health.clinical_confirm',
        'reproduction.view','reproduction.observe','reproduction.clinical_confirm','breeding.observe','tasks.view',
        'tasks.complete','evidence.view','evidence.create','reports.view','reports.export','audit.view'},
    'farmer': {'farm.view','dashboard.view','animals.view','animals.create','health.view','health.observe','reproduction.view','reproduction.observe',
        'breeding.observe','tasks.view','tasks.complete','evidence.view','evidence.create'},
    'breeder': {'farm.view','dashboard.view','animals.view','reproduction.view','reproduction.observe',
        'breeding.observe','tasks.view','tasks.complete','evidence.view','evidence.create'},
    # No approved research dataset/consent infrastructure exists; default deny.
    'researcher': {'farm.view'},
}

def require_farm_permission(db: Session, user: User, farm_id: str, permission: str) -> str:
    role = farm_role(db, user, farm_id)
    if permission not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(403, 'Insufficient farm permissions')
    return role

def farm_role_view(db: Session, user: User) -> dict:
    memberships = db.execute(select(Farm, Membership).join(Membership, Membership.farm_id == Farm.id)
        .where(Membership.user_id == user.id, Farm.archived == False)).all()
    return {'id': user.id, 'name': user.name, 'farms': [
        {'id': farm.id, 'name': farm.name, 'role': membership.role,
         'permissions': sorted(ROLE_PERMISSIONS.get(membership.role, set()))}
        for farm, membership in memberships]}

def visible_event_categories(role: str) -> set[str]:
    permissions = ROLE_PERMISSIONS.get(role, set())
    return {category for category, permission in {
        'health':'health.view', 'reproduction':'reproduction.view', 'pregnancy':'reproduction.view',
        'breeding':'breeding.observe', 'birth':'breeding.observe', 'task':'tasks.view'}.items()
        if permission in permissions}

def record_audit(db: Session, user: User, farm_id: str | None, action: str, entity_id: str):
    db.add(Audit(actor_id=user.id, farm_id=farm_id, action=action, entity_id=entity_id))

def normalize_username(value: str) -> str:
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

class BootstrapInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    farm_name: str = Field(min_length=2)

class RegistrationInput(BaseModel):
    """Public sign-up creates a new isolated farm; existing farms require manager approval."""
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    username: str | None = Field(default=None, min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(min_length=2, max_length=180)
    farm_name: str = Field(min_length=2, max_length=180)

    @field_validator('username')
    @classmethod
    def normalized_username(cls, value):
        return normalize_username(value) if value is not None else None

    @field_validator('full_name', 'farm_name')
    @classmethod
    def not_blank(cls, value: str):
        if not value.strip():
            raise ValueError('Name cannot be blank')
        return value.strip()


class AnimalInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=180)
    species: str = Field(min_length=1, max_length=100)
    breed: str = Field(default='', max_length=100)
    sex: Literal['female','male','unknown'] = 'unknown'
    tag: str = Field(min_length=1, max_length=120)
    date_of_birth: str | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=100000)

    @field_validator('date_of_birth')
    @classmethod
    def validate_birth_date(cls, value: str | None):
        if value is not None:
            try:
                d = date.fromisoformat(value)
            except ValueError:
                raise ValueError('Date of birth must be YYYY-MM-DD') from None
            if d > date.today():
                raise ValueError('Date of birth cannot be in the future')
        return value

class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['health','reproduction','breeding','pregnancy','birth','task']
    kind: str = Field(min_length=1, max_length=60)
    status: str = Field(min_length=1, max_length=32)
    occurred_at: datetime
    payload: dict = Field(default_factory=dict)

    @field_validator('occurred_at')
    @classmethod
    def require_offset(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Event datetime must include timezone')
        return value

    @model_validator(mode='after')
    def validate_clinical_payload(self):
        p = self.payload
        kind = self.kind.lower()
        if self.category == 'health':
            for key in ('temperature_c', 'heart_rate_bpm', 'respiratory_rate_bpm', 'weight_kg'):
                if key in p and p[key] not in (None, ''):
                    try:
                        value = float(p[key])
                    except (ValueError, TypeError):
                        raise ValueError(f'{key} must be a number') from None
                    if not math.isfinite(value) or value <= 0 or value > (100000 if key == 'weight_kg' else 1000):
                        raise ValueError(f'{key} is outside safe data-entry bounds')
        if self.category == 'reproduction':
            if kind in ('follicle', 'ultrasound'):
                if p.get('ovary_side') not in ('left', 'right'):
                    raise ValueError('Ultrasound requires left or right ovary')
                if not p.get('examination_method') or not p.get('follicle_diameter_mm'):
                    raise ValueError('Ultrasound requires method and follicle diameter')
                if not math.isfinite(float(p['follicle_diameter_mm'])) or not 0 < float(p['follicle_diameter_mm']) <= 200:
                    raise ValueError('Follicle diameter out of range')
            if kind == 'hormone':
                required = ('hormone_type','hormone_value','hormone_unit','sample_type','laboratory','assay_method')
                if any(p.get(k) in (None, '') for k in required):
                    raise ValueError('Hormone results require value, unit, sample, laboratory and assay')
                if not math.isfinite(float(p['hormone_value'])) or float(p['hormone_value']) < 0:
                    raise ValueError('Hormone value cannot be negative')
        if self.category == 'breeding' and kind == 'service':
            if p.get('method') not in ('natural', 'artificial_insemination'):
                raise ValueError('Breeding method required')
        if self.category == 'birth' and kind == 'delivery':
            if not p.get('delivery_type') or not p.get('outcome'):
                raise ValueError('Delivery type and outcome required')
        if self.category == 'pregnancy' and self.status == 'confirmed':
            if not p.get('confirmation_method'):
                raise ValueError('Pregnancy confirmation method required')
        return self

class InviteInput(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2)
    password: str = Field(min_length=8)
    role: Literal['farm_manager','farmer','breeder','veterinarian','researcher']

def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()

def replay_if_known(db: Session, user: User, farm_id: str, key: str | None, body_hash: str, resource: str):
    if not key:
        return None
    if len(key) > 80 or len(key) < 8 or any(ord(ch) < 33 or ord(ch) > 126 for ch in key):
        raise HTTPException(422, 'Invalid idempotency key')
    prior = db.get(Idempotency, (user.id, farm_id, key))
    if prior:
        if not hmac.compare_digest(prior.body_hash, body_hash) or prior.resource_type != resource:
            raise HTTPException(409, 'Idempotency key was used for a different request')
        return prior.response_json
    return None

def save_idempotency(db: Session, user: User, farm_id: str, key: str | None, body_hash: str, resource: str, result: dict):
    if key:
        db.add(Idempotency(user_id=user.id, farm_id=farm_id, request_key=key,
                           body_hash=body_hash, resource_type=resource, response_json=result))

@app.get('/api/health')
def health():
    return {'status':'ok','service':'anirepro-api'}

@app.post('/api/setup', status_code=201)
def setup(data: BootstrapInput, request: Request, db: DB):
    # Only an empty installation can bootstrap. Disable in production unless explicitly enabled.
    if os.getenv('APP_ENV') == 'production' and os.getenv('ALLOW_INITIAL_SETUP') != 'true':
        raise HTTPException(403, 'Initial setup disabled')
    if db.scalar(select(User.id).limit(1)):
        raise HTTPException(409, 'Initial setup already completed')
    user = User(email=data.email.strip().lower(), name=data.full_name.strip(), password_hash=passwords.hash(data.password), role='farm_manager')
    farm = Farm(name=data.farm_name.strip())
    db.add_all([user, farm]); db.flush()
    db.add(Membership(user_id=user.id, farm_id=farm.id, role='farm_manager'))
    record_audit(db, user, farm.id, 'bootstrap', farm.id)
    db.commit()
    return {'farm_id':farm.id,'user_id':user.id}

def start_session(user: User, response: Response):
    now = datetime.now(timezone.utc)
    csrf = secrets.token_urlsafe(32)
    token = jwt.encode({'sub':user.id,'iat':now,'exp':now + timedelta(hours=8),
                        'csrf':csrf,'ver':user.session_version}, SECRET, algorithm='HS256')
    response.set_cookie('anirepro_session', token, httponly=True,
                        secure=os.getenv('APP_ENV') == 'production', samesite='lax',
                        max_age=28800, path='/api')
    # Retain the legacy account-level field for older clients. It is never used
    # for farm authorization or the selected-farm workspace role.
    return {'csrf_token':csrf,'user':{'id':user.id,'name':user.name,'role':user.role}}


@app.post('/api/auth/register', status_code=201)
def register(data: RegistrationInput, response: Response, request: Request, db: DB):
    """A new registration owns a new farm, never an existing farm.

    Membership in an existing farm is controlled by its manager. Disabling public
    registration does not disable login or manager-managed accounts.
    """
    if os.getenv('ALLOW_PUBLIC_REGISTRATION', 'true').lower() != 'true':
        raise HTTPException(403, 'Public registration is not enabled')
    ip = request.client.host if request.client else 'unknown'
    recovery_throttle(db, f'register:ip:{ip}', 10, 60)
    email = data.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        db.commit()  # persist rate-limit event even on duplicate sign-up attempts
        raise HTTPException(409, 'An account with this email already exists. Sign in instead.')
    if data.username and db.scalar(select(User.id).where(User.username == data.username)):
        db.commit()
        raise HTTPException(409, 'Username unavailable')
    user = User(email=email, username=data.username, name=data.full_name, password_hash=passwords.hash(data.password), role='farm_manager')
    farm = Farm(name=data.farm_name)
    try:
        db.add_all([user, farm]); db.flush()
        db.add(Membership(user_id=user.id, farm_id=farm.id, role='farm_manager'))
        record_audit(db, user, farm.id, 'account.register', user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists. Sign in instead.') from None
    return {'farm_id':farm.id, **start_session(user, response)}


@app.post('/api/auth/login')
def login(data: LoginInput, response: Response, db: DB, request: Request):
    identity = str(data.email).strip().lower() if data.email else data.username
    user = db.scalar(select(User).where(User.email == identity if data.email else User.username == identity))
    try:
        verified = bool(user and user.active and passwords.verify(user.password_hash, data.password))
    except (VerifyMismatchError, VerificationError):
        verified = False
    if not verified:
        recovery_throttle(db, f'login:account:{user.email if user else identity}', 15, 15)
        recovery_throttle(db, f'login:ip:{request.client.host if request.client else "unknown"}', 120, 15)
        db.commit()
        raise HTTPException(401, 'Invalid credentials')
    return start_session(user, response)

@app.post('/api/auth/logout')
def logout(response: Response, user: Auth):
    response.delete_cookie('anirepro_session', path='/api')
    return {'ok':True}

@app.get('/api/me')
def me(user: Auth, db: DB):
    return {**farm_role_view(db, user), 'email': user.email, 'username': user.username}

@app.patch('/api/auth/username')
def change_username(data: UsernameInput, user: Auth, db: DB):
    if db.scalar(select(User.id).where(User.username == data.username, User.id != user.id)):
        raise HTTPException(409, 'Username unavailable')
    user.username = data.username
    record_audit(db, user, None, 'account.username', user.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Username unavailable') from None
    return {'username': user.username}

@app.post('/api/farms/{farm_id}/members', status_code=201)
def invite(farm_id: str, data: InviteInput, user: Auth, db: DB):
    if os.getenv('APP_ENV') == 'production':
        raise HTTPException(410, 'Use one-time invitations instead of sharing staff passwords')
    require_farm_permission(db,user,farm_id,'members.invite')
    email = data.email.strip().lower()
    target = db.scalar(select(User).where(User.email==email))
    if target and db.get(Membership, (target.id,farm_id)):
        raise HTTPException(409, 'User already belongs to farm')
    # Existing accounts can only be invited with a separate, verified flow.
    if target:
        raise HTTPException(409, 'Existing account requires invitation acceptance (not yet supported)')
    target = User(email=email, name=data.full_name, password_hash=passwords.hash(data.password), role=data.role)
    db.add(target); db.flush()
    db.add(Membership(user_id=target.id,farm_id=farm_id,role=data.role))
    record_audit(db,user,farm_id,'member.create',target.id)
    db.commit()
    return {'user_id':target.id}

# Farm invitations allow staff to join an EXISTING farm, rather than creating a new one.
INVITE_ROLES = {'farmer', 'breeder', 'veterinarian', 'researcher'}

class InvitationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    role: Literal['farmer', 'breeder', 'veterinarian', 'researcher']

class InvitationAcceptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(min_length=32, max_length=160)
    password: str = Field(min_length=1, max_length=256)
    full_name: str = Field(default='', max_length=180)

class MemberRoleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['farm_manager', 'farmer', 'breeder', 'veterinarian', 'researcher']


def active_invitation(db: Session, token: str) -> FarmInvitation:
    entry = db.scalar(select(FarmInvitation).where(
        FarmInvitation.token_digest == hashlib.sha256(token.encode()).hexdigest()).with_for_update())
    now = datetime.now(timezone.utc)
    if not entry or entry.used_at or entry.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(400, 'Invalid or expired invitation')
    farm = db.get(Farm, entry.farm_id)
    if not farm or farm.archived:
        raise HTTPException(400, 'Invalid or expired invitation')
    return entry


def deliver_invitation(email: str, farm_name: str, role: str, link: str):
    # Never return an invitation secret in a production API response.
    host = os.getenv('SMTP_HOST','').strip()
    sender = os.getenv('SMTP_FROM','').strip()
    if not host or not sender:
        raise HTTPException(503, 'Invitation delivery is not configured')
    message = EmailMessage()
    message['Subject'] = 'AniRepro 360: invitation to join a farm'
    message['From'] = sender
    message['To'] = email
    message.set_content(f'You have been invited to join {farm_name} as {role}.\n'
                        f'Use this one-time link within 48 hours:\n{link}\n'
                        'If you did not expect this invitation, ignore this message.')
    try:
        with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=10) as smtp:
            smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
            if os.getenv('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(503, 'Invitation delivery unavailable') from exc


@app.get('/api/farms/{farm_id}/members')
def members(farm_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'members.view')
    rows = db.execute(select(Membership, User).join(User, Membership.user_id == User.id)
        .where(Membership.farm_id == farm_id).order_by(User.name)).all()
    return [{'id': person.id, 'name': person.name, 'email': person.email,
             'role': membership.role} for membership, person in rows]

@app.get('/api/farms/{farm_id}/invitations')
def list_invitations(farm_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'members.view')
    rows = db.scalars(select(FarmInvitation).where(FarmInvitation.farm_id == farm_id,
        FarmInvitation.used_at == None).order_by(FarmInvitation.created_at.desc())).all()
    now = datetime.now(timezone.utc)
    return [{'id': row.id, 'email': row.email, 'role': row.role, 'created_at': row.created_at.isoformat(),
        'expires_at': row.expires_at.isoformat(), 'expired': row.expires_at.replace(tzinfo=timezone.utc) <= now}
        for row in rows]

@app.delete('/api/farms/{farm_id}/invitations/{invitation_id}')
def revoke_invitation(farm_id: str, invitation_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'members.invite')
    invitation = db.get(FarmInvitation, invitation_id)
    if not invitation or invitation.farm_id != farm_id or invitation.used_at:
        raise HTTPException(404, 'Pending invitation not found')
    invitation.used_at = datetime.now(timezone.utc)
    record_audit(db, user, farm_id, 'invitation.revoked', invitation.id)
    db.commit()
    return {'revoked': True}

@app.patch('/api/farms/{farm_id}/members/{member_id}')
def change_member_role(farm_id: str, member_id: str, data: 'MemberRoleInput', user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'members.update_role')
    membership = db.get(Membership, (member_id, farm_id))
    if not membership:
        raise HTTPException(404, 'Farm member not found')
    if member_id == user.id and data.role != 'farm_manager':
        raise HTTPException(409, 'Managers cannot remove their own management access')
    if membership.role == 'farm_manager' and data.role != 'farm_manager':
        managers = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.farm_id == farm_id, Membership.role == 'farm_manager')) or 0
        if managers <= 1:
            raise HTTPException(409, 'Transfer management before changing the last manager role')
    membership.role = data.role
    db.add(Notification(recipient_user_id=member_id,farm_id=farm_id,event_type='membership.role_changed',title='Farm Role Updated',message='Your role on a farm was updated.',deduplication_key=f'membership.role_changed:{farm_id}:{member_id}:{data.role}:{uuid.uuid4()}'))
    record_audit(db, user, farm_id, 'member.role_changed', member_id)
    db.commit()
    return {'id': member_id, 'role': membership.role}

@app.delete('/api/farms/{farm_id}/members/{member_id}')
def remove_member(farm_id: str, member_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'members.remove')
    membership = db.get(Membership, (member_id, farm_id))
    if not membership:
        raise HTTPException(404, 'Farm member not found')
    if member_id == user.id:
        raise HTTPException(409, 'Managers cannot remove their own farm membership')
    if membership.role == 'farm_manager':
        managers = db.scalar(select(func.count()).select_from(Membership).where(
            Membership.farm_id == farm_id, Membership.role == 'farm_manager')) or 0
        if managers <= 1:
            raise HTTPException(409, 'Transfer management before removing the last manager')
    db.add(Notification(recipient_user_id=member_id,farm_id=None,event_type='account.access_revoked',title='Farm Access Changed',message='Your access to a farm has changed.',deduplication_key=f'account.access_revoked:{farm_id}:{member_id}:{uuid.uuid4()}'))
    db.delete(membership)
    record_audit(db, user, farm_id, 'member.removed', member_id)
    db.commit()
    return {'removed': True}


@app.post('/api/farms/{farm_id}/invitations', status_code=201)
def create_invitation(farm_id: str, data: InvitationInput, user: Auth, db: DB, request: Request):
    require_farm_permission(db, user, farm_id, 'members.invite')
    email = data.email.strip().lower()
    if db.scalar(select(User.id).join(Membership, User.id == Membership.user_id).where(
        User.email == email, Membership.farm_id == farm_id)):
        raise HTTPException(409, 'This person already belongs to the farm')
    base = os.getenv('INVITE_URL_BASE', 'http://localhost:8080/join?token=')
    if not base.endswith('token=') or not base.startswith(('http://127.0.0.1:', 'http://localhost:', 'https://')):
        raise HTTPException(503, 'Invitation URL is not configured')
    if os.getenv('APP_ENV') == 'production' and not base.startswith('https://'):
        raise HTTPException(503, 'Production invitations require an HTTPS URL')
    recovery_throttle(db, f'invite:manager:{user.id}', 30, 60)
    now = datetime.now(timezone.utc)
    previous = db.scalars(select(FarmInvitation).where(FarmInvitation.farm_id == farm_id,
        FarmInvitation.email == email, FarmInvitation.used_at == None)).all()
    for item in previous:
        item.used_at = now  # replacing an invitation revokes older links
    token = secrets.token_urlsafe(40)
    invite = FarmInvitation(id=str(uuid.uuid4()), farm_id=farm_id, email=email, role=data.role,
                            token_digest=hashlib.sha256(token.encode()).hexdigest(),
                            invited_by=user.id, expires_at=now+timedelta(hours=48))
    db.add(invite)
    record_audit(db, user, farm_id, 'invitation.created', invite.id)
    link = base + token
    if os.getenv('APP_ENV') == 'production':
        deliver_invitation(email, db.get(Farm, farm_id).name, data.role, link)
    db.commit()
    result = {'message': 'Invitation created for ' + email + '.', 'expires_in_hours': 48}
    if os.getenv('APP_ENV', 'development') != 'production':
        result['invitation_url'] = link  # local development ONLY; share it privately with recipient
    return result


@app.get('/api/auth/invitations/preview')
def preview_invitation(token: str, db: DB):
    invite = active_invitation(db, token)
    existing = db.scalar(select(User.id).where(User.email == invite.email)) is not None
    return {'email': invite.email, 'farm_name': db.get(Farm, invite.farm_id).name,
            'role': invite.role, 'has_account': existing, 'expires_at': invite.expires_at.isoformat()}


@app.post('/api/auth/invitations/accept', status_code=200)
def accept_invitation(data: InvitationAcceptInput, response: Response, db: DB):
    invitation = active_invitation(db, data.token)
    person = db.scalar(select(User).where(User.email == invitation.email))
    if person:
        try:
            verified = person.active and passwords.verify(person.password_hash, data.password)
        except (VerifyMismatchError, VerificationError):
            verified = False
        if not verified:
            raise HTTPException(401, 'Unable to verify account credentials')
    else:
        if len(data.password) < 8:
            raise HTTPException(422, 'New passwords require at least 8 characters')
        if len(data.full_name.strip()) < 2:
            raise HTTPException(422, 'Full name is required for new accounts')
        person = User(email=invitation.email, name=data.full_name.strip(),
                      password_hash=passwords.hash(data.password), role='farmer')
        db.add(person); db.flush()
    if db.get(Membership, (person.id, invitation.farm_id)):
        raise HTTPException(409, 'Account already belongs to this farm')
    db.add(Membership(user_id=person.id, farm_id=invitation.farm_id, role=invitation.role))
    invitation.used_at = datetime.now(timezone.utc)
    record_audit(db, person, invitation.farm_id, 'invitation.accepted', invitation.id)
    add_farm_notifications(db, invitation.farm_id, person.id, 'membership.joined', 'New Farm Member', 'An invited member joined your farm.', None, None, invitation.id)
    db.commit()
    return {'farm_id': invitation.farm_id, **start_session(person, response)}


@app.get('/api/farms')
def list_farms(user: Auth, db: DB):
    rows = db.execute(select(Farm,Membership).join(Membership,Membership.farm_id==Farm.id).where(Membership.user_id==user.id,Farm.archived==False)).all()
    return [{'id':f.id,'name':f.name,'location':f.location,'role':m.role,
             'permissions':sorted(ROLE_PERMISSIONS.get(m.role, set()))} for f,m in rows]

@app.get('/api/farms/{farm_id}/animals')
def list_animals(farm_id: str, user: Auth, db: DB):
    require_farm_permission(db,user,farm_id,'animals.view')
    animals = db.scalars(select(Animal).where(Animal.farm_id==farm_id,Animal.archived==False).order_by(Animal.created_at.desc())).all()
    return [animal_view(a) for a in animals]

def animal_view(a: Animal):
    return {'id':a.id,'farm_id':a.farm_id,'name':a.name,'species':a.species,'breed':a.breed,'sex':a.sex,'tag':a.tag,'date_of_birth':a.date_of_birth,'weight_kg':a.weight_kg,'created_at':a.created_at.isoformat()}

@app.delete('/api/farms/{farm_id}/animals/{animal_id}')
def archive_animal(farm_id: str, animal_id: str, user: Auth, db: DB):
    farm_role(db, user, farm_id, MANAGERS)
    animal = db.get(Animal, animal_id)
    if not animal or animal.farm_id != farm_id:
        raise HTTPException(404, 'Animal not found')

    archived = db.execute(
        update(Animal).where(
            Animal.id == animal_id, Animal.farm_id == farm_id, Animal.archived.is_(False)
        ).values(archived=True)
    )
    if archived.rowcount:
        record_audit(db, user, farm_id, 'animal.archive', animal_id)
        db.commit()
    return {'archived': True}

NOTIFICATION_PERMISSION = {'animal.created':'animals.view','health.recorded':'health.view','reproduction.recorded':'reproduction.view','breeding.recorded':'breeding.observe','pregnancy.recorded':'reproduction.view','birth.recorded':'breeding.observe','task.updated':'tasks.view','membership.role_changed':'farm.view','membership.joined':'members.view'}
def add_farm_notifications(db: Session, farm_id: str, actor_id: str, event_type: str, title: str, message: str, resource_type: str | None, resource_id: str | None, dedupe_id: str):
    permission = NOTIFICATION_PERMISSION[event_type]
    members = db.scalars(select(Membership).where(Membership.farm_id == farm_id, Membership.user_id != actor_id)).all()
    for member in members:
        if permission not in ROLE_PERMISSIONS.get(member.role, set()):
            continue
        dedupe = f'{event_type}:{dedupe_id}:{member.user_id}'
        if not db.scalar(select(Notification.id).where(Notification.recipient_user_id == member.user_id, Notification.deduplication_key == dedupe)):
            db.add(Notification(recipient_user_id=member.user_id, farm_id=farm_id, event_type=event_type, title=title, message=message, resource_type=resource_type, resource_id=resource_id, deduplication_key=dedupe))

def notification_visible_query(db: Session, user_id: str):
    rows = db.scalars(select(Notification).where(Notification.recipient_user_id == user_id, Notification.dismissed_at.is_(None)).order_by(Notification.created_at.desc())).all()
    visible = []
    for row in rows:
        if row.farm_id is None:
            if row.event_type == 'account.access_revoked': visible.append(row)
            continue
        member = db.get(Membership, (user_id, row.farm_id))
        permission = NOTIFICATION_PERMISSION.get(row.event_type)
        if member and permission in ROLE_PERMISSIONS.get(member.role, set()):
            farm = db.get(Farm, row.farm_id)
            visible.append((row, farm.name if farm else None))
    return visible

def notification_view(item):
    row, farm_name = item if isinstance(item, tuple) else (item, None)
    href = '/tasks' if row.event_type == 'task.updated' else (f'/animals/{row.resource_id}' if row.resource_type == 'animal' and row.resource_id else None)
    return {'id':row.id,'event_type':row.event_type,'title':row.title,'message':row.message,'priority':row.priority,'created_at':row.created_at.isoformat(),'read_at':row.read_at.isoformat() if row.read_at else None,'farm_id':row.farm_id,'farm_name':farm_name,'resource_type':row.resource_type,'resource_id':row.resource_id,'href':href}

@app.get('/api/notifications')
def get_notifications(user: Auth, db: DB):
    items = notification_visible_query(db, user.id)
    return {'items':[notification_view(i) for i in items], 'unread_count':sum(1 for i in items if (i[0] if isinstance(i,tuple) else i).read_at is None)}

@app.get('/api/notifications/unread-count')
def notification_unread_count(user: Auth, db: DB):
    items = notification_visible_query(db, user.id)
    return {'count':sum(1 for i in items if (i[0] if isinstance(i,tuple) else i).read_at is None)}

@app.patch('/api/notifications/{notification_id}/read')
def read_notification(notification_id: str, user: Auth, db: DB):
    ids = { (i[0] if isinstance(i,tuple) else i).id for i in notification_visible_query(db,user.id) }
    row = db.scalar(select(Notification).where(Notification.id==notification_id, Notification.recipient_user_id==user.id, Notification.dismissed_at.is_(None)))
    if not row or row.id not in ids: raise HTTPException(404,'Notification not found')
    row.read_at = row.read_at or datetime.now(timezone.utc); db.commit(); return {'ok':True}

@app.patch('/api/notifications/read-all')
def read_all_notifications(user: Auth, db: DB):
    now = datetime.now(timezone.utc)
    for item in notification_visible_query(db,user.id):
        row = item[0] if isinstance(item,tuple) else item
        if row.read_at is None: row.read_at = now
    db.commit(); return {'ok':True}

@app.delete('/api/notifications/{notification_id}')
def dismiss_notification(notification_id: str, user: Auth, db: DB):
    ids = { (i[0] if isinstance(i,tuple) else i).id for i in notification_visible_query(db,user.id) }
    row = db.scalar(select(Notification).where(Notification.id==notification_id, Notification.recipient_user_id==user.id, Notification.dismissed_at.is_(None)))
    if not row or row.id not in ids: raise HTTPException(404,'Notification not found')
    row.dismissed_at = datetime.now(timezone.utc); db.commit(); return {'ok':True}

@app.post('/api/farms/{farm_id}/animals', status_code=201)
def create_animal(farm_id: str, data: AnimalInput, user: Auth, db: DB, idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key')):
    require_farm_permission(db,user,farm_id,'animals.create')
    digest = canonical_hash({'farm':farm_id,'animal':data.model_dump()})
    replay = replay_if_known(db, user, farm_id, idempotency_key, digest, 'animal')
    if replay is not None:
        return replay
    if db.scalar(select(Animal.id).where(Animal.farm_id==farm_id,Animal.tag==data.tag)):
        raise HTTPException(409,'Tag already in use at this farm')
    a = Animal(farm_id=farm_id, created_by=user.id, **data.model_dump())
    db.add(a); db.flush()
    add_farm_notifications(db,farm_id,user.id,'animal.created','New Animal Registered','A new animal was registered on your farm.','animal',a.id,a.id)
    record_audit(db,user,farm_id,'animal.create',a.id)
    result = animal_view(a)
    save_idempotency(db,user,farm_id,idempotency_key,digest,'animal',result)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = replay_if_known(db,user,farm_id,idempotency_key,digest,'animal')
        if replay is not None:return replay
        raise HTTPException(409,'A conflicting animal registration already exists') from None
    return result

@app.get('/api/farms/{farm_id}/animals/{animal_id}/events')
def list_events(farm_id: str, animal_id: str, user: Auth, db: DB):
    role = require_farm_permission(db,user,farm_id,'animals.view')
    animal = db.get(Animal,animal_id)
    if not animal or animal.farm_id != farm_id or animal.archived:
        raise HTTPException(404,'Animal not found')
    events = db.scalars(select(Event).where(Event.archived.is_(False), Event.farm_id==farm_id,Event.animal_id==animal_id,
        Event.category.in_(visible_event_categories(role))).order_by(Event.occurred_at.desc())).all()
    return [event_view(e) for e in events]

def event_timestamp(value: datetime) -> str:
    # SQLite loses offsets; new event writes are always normalized to UTC.
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()

def event_view(e: Event):
    return {'id':e.id,'animal_id':e.animal_id,'category':e.category,'kind':e.kind,'status':e.status,'occurred_at':event_timestamp(e.occurred_at),'payload':e.payload,'author_id':e.author_id,'created_at':event_timestamp(e.created_at)}

@app.delete('/api/farms/{farm_id}/animals/{animal_id}/events/{event_id}')
def archive_event(farm_id: str, animal_id: str, event_id: str, user: Auth, db: DB):
    role = farm_role(db, user, farm_id, WRITERS)
    verify_animal(db, farm_id, animal_id)
    event = db.get(Event, event_id)
    if not event or event.farm_id != farm_id or event.animal_id != animal_id or event.category not in ('reproduction', 'breeding', 'birth'):
        raise HTTPException(404, 'Record not found')
    if event.category == 'reproduction' and event.status == 'confirmed' and role not in CLINICIANS:
        raise HTTPException(403, 'Only a veterinarian can delete a clinically confirmed record')
    if user.id != event.author_id and role not in MANAGERS | CLINICIANS:
        raise HTTPException(403, 'Only the recorder, farm manager or veterinarian can delete this record')

    archived = db.execute(update(Event).where(Event.id == event_id, Event.archived.is_(False)).values(archived=True))
    if archived.rowcount:
        record_audit(db, user, farm_id, f'{event.category}.archive', event_id)
        db.commit()
    return {'archived': True}


@app.post('/api/farms/{farm_id}/animals/{animal_id}/events', status_code=201)
def create_event(farm_id: str, animal_id: str, data: EventInput, user: Auth, db: DB, idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key')):
    role = farm_role(db,user,farm_id)
    animal = db.get(Animal,animal_id)
    if not animal or animal.farm_id != farm_id or animal.archived:
        raise HTTPException(404,'Animal not found')
    digest = canonical_hash({'farm':farm_id,'animal':animal_id,'event':data.model_dump(mode='json')})
    replay = replay_if_known(db, user, farm_id, idempotency_key, digest, 'event')
    if replay is not None:
        return replay
    category_permission = {'health': ('health.observe' if data.status in ('observed','not_assessed') else 'health.record'), 'reproduction': 'reproduction.observe',
        'pregnancy': 'reproduction.observe', 'breeding': 'breeding.observe', 'birth': 'breeding.observe',
        'task': 'tasks.complete'}.get(data.category)
    if not category_permission or category_permission not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(403, 'This role cannot record this event category')
    if data.status == 'confirmed' and data.category in ('reproduction','pregnancy') and 'reproduction.clinical_confirm' not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(403,'Clinical confirmation requires veterinarian role')
    if data.category == 'health' and data.status not in ('observed','not_assessed') and role != 'veterinarian':
        raise HTTPException(403, 'Clinical assessments require veterinarian role')
    if data.category in ('reproduction','pregnancy') and data.status == 'confirmed' and not data.payload.get('evidence_reference'):
        raise HTTPException(422,'Clinical confirmation requires evidence_reference')
    if len(str(data.payload)) > 20000:
        raise HTTPException(422,'Event payload is too large')
    # A delivery and its offspring are committed as one transaction. Duplicate tags fail
    # before creating a delivery, preventing orphaned or misleading mother records.
    offspring = None
    if data.category == 'birth' and data.kind.lower() == 'delivery' and data.payload.get('offspring_tag'):
        if 'animals.create' not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(403, 'This role cannot register offspring animal profiles')
        child_tag = str(data.payload['offspring_tag']).strip()
        if db.scalar(select(Animal.id).where(Animal.farm_id == farm_id, Animal.tag == child_tag)):
            raise HTTPException(409, 'Offspring tag is already registered')
        child_sex = str(data.payload.get('offspring_sex') or 'unknown').lower()
        if child_sex not in ('male', 'female', 'unknown'):
            raise HTTPException(422, 'Invalid offspring sex')
        offspring = Animal(farm_id=farm_id, created_by=user.id,
                           name=str(data.payload.get('offspring_name') or child_tag),
                           species=animal.species, breed=animal.breed, sex=child_sex,
                           tag=child_tag, date_of_birth=data.occurred_at.date().isoformat(),
                           weight_kg=float(data.payload['birth_weight_kg']) if data.payload.get('birth_weight_kg') else None)
        db.add(offspring); db.flush()
    event_data = data.model_dump()
    event_data['occurred_at'] = data.occurred_at.astimezone(timezone.utc)
    if offspring:
        event_data['payload'] = {**data.payload, 'offspring_animal_id': offspring.id, 'mother_animal_id': animal.id}
    row = Event(farm_id=farm_id,animal_id=animal_id,author_id=user.id,**event_data)
    db.add(row); db.flush()
    if offspring:
        record_audit(db,user,farm_id,'offspring.create',offspring.id)
    record_audit(db,user,farm_id,f'{data.category}.create',row.id)
    event_type = {'health':'health.recorded','reproduction':'reproduction.recorded','pregnancy':'pregnancy.recorded','breeding':'breeding.recorded','birth':'birth.recorded','task':'task.updated'}.get(data.category)
    if event_type:
        title = {'health':'Clinical Assessment Recorded','reproduction':'Reproductive Event Recorded','pregnancy':'Pregnancy Record Updated','breeding':'Breeding Event Recorded','birth':'Birth Record Added','task':'Task Activity Updated'}[data.category]
        add_farm_notifications(db,farm_id,user.id,event_type,title,'A new farm record is available to authorized team members.', 'event',row.id,row.id)
    result = event_view(row)
    save_idempotency(db,user,farm_id,idempotency_key,digest,'event',result)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = replay_if_known(db,user,farm_id,idempotency_key,digest,'event')
        if replay is not None:return replay
        raise HTTPException(409,'A conflicting clinical entry already exists') from None
    return result

@app.get('/api/farms/{farm_id}/audit')
def audit(farm_id: str, user: Auth, db: DB):
    role = farm_role(db,user,farm_id)
    if 'audit.view' not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(403, 'Insufficient farm permissions')
    rows = db.scalars(select(Audit).where(Audit.farm_id==farm_id).order_by(Audit.at.desc()).limit(200)).all()
    return [{'action':a.action,'entity_id':a.entity_id,'actor_id':a.actor_id,'at':a.at.isoformat()} for a in rows]

@app.get('/api/auth/session')
def session(request: Request, user: Auth, db: DB):
    claims = jwt.decode(request.cookies['anirepro_session'], SECRET, algorithms=['HS256'])
    # Keep the legacy account-role field for API compatibility; farm roles in
    # `farms` are the sole source of farm permissions and workspace context.
    return {'csrf_token': claims['csrf'], 'user': {**farm_role_view(db, user), 'role': user.role}}


@app.get('/api/farms/{farm_id}/events')
def farm_events(farm_id: str, user: Auth, db: DB, category: str | None = None):
    """Farm-scoped event feed; cross-farm data is never visible."""
    role = farm_role(db, user, farm_id)
    if category:
        permission = {'health':'health.view','reproduction':'reproduction.view','pregnancy':'reproduction.view',
            'breeding':'breeding.observe','birth':'breeding.observe','task':'tasks.view'}.get(category)
        if not permission or permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(403, 'Insufficient farm permissions')
    elif 'animals.view' not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(403, 'Insufficient farm permissions')
    query = select(Event).where(Event.archived.is_(False), Event.farm_id == farm_id)
    if category:
        if category not in {'health','reproduction','breeding','pregnancy','birth','task'}:
            raise HTTPException(422, 'Unknown category')
        query = query.where(Event.category == category)
    else:
        categories = visible_event_categories(role)
        if not categories:
            raise HTTPException(403, 'Insufficient farm permissions')
        query = query.where(Event.category.in_(categories))
    rows = db.scalars(query.order_by(Event.occurred_at.desc()).limit(500)).all()
    return [event_view(e) for e in rows]

@app.get('/api/farms/{farm_id}/summary')
def farm_summary(farm_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'dashboard.view')
    animals = db.scalars(select(Animal).where(Animal.farm_id == farm_id, Animal.archived == False)).all()
    events = db.scalars(select(Event).where(Event.archived.is_(False), Event.farm_id == farm_id)).all()
    return {
        'animals': len(animals),
        'health_records': sum(e.category == 'health' for e in events),
        'reproduction_records': sum(e.category == 'reproduction' for e in events),
        'pregnancies_confirmed': len({e.animal_id for e in events if e.category == 'pregnancy' and e.status == 'confirmed'}),
        'tasks': sum(e.category == 'task' for e in events),
        'births': sum(e.category == 'birth' for e in events),
    }

@app.get('/api/farms/{farm_id}/reports/csv')
def export_csv(farm_id: str, user: Auth, db: DB):
    from csv import writer
    from io import StringIO
    from fastapi.responses import StreamingResponse
    farm_role(db, user, farm_id, MANAGERS | CLINICIANS)
    out = StringIO()
    csv = writer(out)
    csv.writerow(['id','animal_id','category','kind','status','occurred_at','author_id'])
    for e in db.scalars(select(Event).where(Event.archived.is_(False), Event.farm_id == farm_id).order_by(Event.occurred_at)).all():
        csv.writerow([e.id,e.animal_id,e.category,e.kind,e.status,e.occurred_at.isoformat(),e.author_id])
    return StreamingResponse(iter([out.getvalue()]), media_type='text/csv', headers={'Content-Disposition':'attachment; filename="anirepro-records.csv"'})


# Source: both attached product specifications. These are general reference patterns,
# not veterinary validated decision thresholds. No default prediction for induced ovulators.
SPECIES_PROFILES = {
    'cattle': {'reference_cycle_days': 21, 'ovulation_type': 'spontaneous'},
    'sheep': {'reference_cycle_days': 17, 'ovulation_type': 'spontaneous', 'seasonality': 'seasonal'},
    'goat': {'reference_cycle_days': 21, 'ovulation_type': 'spontaneous', 'seasonality': 'seasonal'},
    'horse': {'reference_cycle_days': 21, 'ovulation_type': 'spontaneous'},
    'pig': {'reference_cycle_days': 21, 'ovulation_type': 'spontaneous'},
    'dog': {'reference_cycle_days': None, 'ovulation_type': 'variable'},
    'cat': {'reference_cycle_days': None, 'ovulation_type': 'induced'},
    'rabbit': {'reference_cycle_days': None, 'ovulation_type': 'induced'},
}

@app.get('/api/species/profiles')
def species_profiles(user: Auth):
    return {name: {**config, 'source': 'AniRepro 360 SRS section 5, November 2026',
                   'validated_for_clinical_use': False} for name,config in SPECIES_PROFILES.items()}

@app.get('/api/farms/{farm_id}/animals/{animal_id}/cycle-summary')
def cycle_summary(farm_id: str, animal_id: str, user: Auth, db: DB):
    require_farm_permission(db, user, farm_id, 'reproduction.view')
    animal = db.get(Animal, animal_id)
    if not animal or animal.farm_id != farm_id or animal.archived:
        raise HTTPException(404, 'Animal not found')
    profile = SPECIES_PROFILES.get(animal.species.lower(), {'reference_cycle_days': None})
    records = db.scalars(select(Event).where(Event.archived.is_(False), Event.farm_id == farm_id, Event.animal_id == animal_id,
                  Event.category == 'reproduction', Event.kind == 'estrus', Event.status == 'observed')
                  .order_by(Event.occurred_at)).all()
    # Observations are immutable; duplicate onset dates do not create zero-day cycles.
    onsets = sorted(set(r.occurred_at.date() for r in records))
    intervals = [(right-left).days for left,right in zip(onsets,onsets[1:]) if right > left]
    recent = intervals[-5:]
    estimate = int(round(median(recent))) if len(recent) >= 2 and profile.get('ovulation_type') != 'induced' else None
    next_date = (onsets[-1]+timedelta(days=estimate)).isoformat() if estimate and onsets else None
    return {'animal_id':animal_id,'species':animal.species,'observed_onsets':[d.isoformat() for d in onsets],
            'interval_days':intervals,'mean_days':mean(intervals) if intervals else None,
            'median_days':median(intervals) if intervals else None,
            'min_days':min(intervals) if intervals else None,'max_days':max(intervals) if intervals else None,
            'variability_days':pstdev(intervals) if len(intervals)>1 else None,
            'estimated_next_estrus':next_date,'estimate_status':'prediction_not_confirmed' if next_date else 'insufficient_or_inapplicable_history',
            'supporting_cycles':len(recent),'reference_profile':profile,
            'warning':'General reference only. Not a veterinary diagnosis; validated species-specific ranges required.'}

@app.get('/api/farms/{farm_id}/reports/pdf')
def export_pdf(farm_id: str, user: Auth, db: DB):
    """Farm-scoped PDF summary. Predictions are explicitly not diagnostic."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    farm_role(db, user, farm_id, MANAGERS | CLINICIANS)
    farm = db.get(Farm, farm_id)
    records = db.scalars(select(Event).where(Event.archived.is_(False), Event.farm_id == farm_id).order_by(Event.occurred_at.desc()).limit(250)).all()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    y = height - 56
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(48, y, 'AniRepro 360 | Farm Records')
    y -= 25
    pdf.setFont('Helvetica', 10)
    pdf.drawString(48,y, f'Farm: {farm.name[:75]}')
    y -= 17
    pdf.drawString(48,y, f'Exported: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}')
    y -= 17
    pdf.drawString(48,y, 'Record keeping only. Predictions are not clinical diagnoses.')
    y -= 30
    for event in records:
        if y < 62:
            pdf.showPage()
            y=height-60
        animal = db.get(Animal, event.animal_id)
        description = f'{event.occurred_at.date()} | {(animal.tag if animal else "Unknown")[:20]} | {event.category}/{event.kind} | {event.status}'
        pdf.setFont('Helvetica', 9)
        pdf.drawString(48,y,description[:112])
        y -= 15
    pdf.save()
    output.seek(0)
    return StreamingResponse(output, media_type='application/pdf', headers={'Content-Disposition':'attachment; filename="anirepro-farm-records.pdf"'})

# Phase 4: recoverable identities, private encrypted evidence, and replay-safe writes.
class RecoveryRequest(BaseModel):
    email: EmailStr

class RecoveryCompletion(BaseModel):
    token: str = Field(min_length=32, max_length=160)
    password: str = Field(min_length=8, max_length=256)

def recovery_throttle(db: Session, name: str, limit: int, minutes: int = 60):
    """Persistent, hashed, low-volume limit; no plaintext addresses in throttle table."""
    digest = hmac.new(SECRET.encode(), name.encode(), hashlib.sha256).hexdigest()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    count = db.scalar(select(func.count()).select_from(SecurityThrottle).where(
        SecurityThrottle.key_digest == digest, SecurityThrottle.attempt_at >= cutoff)) or 0
    if count >= limit:
        raise HTTPException(429, 'Too many requests. Try again later.')
    db.add(SecurityThrottle(key_digest=digest, attempt_at=datetime.now(timezone.utc)))


def send_password_reset(email: str, raw_token: str):
    host = os.getenv('SMTP_HOST', '').strip()
    sender = os.getenv('SMTP_FROM', '').strip()
    base = os.getenv('RESET_URL_BASE', 'http://localhost:8080/login?reset_token=')
    if not host or not sender or not base.startswith(('https://', 'http://localhost')):
        raise HTTPException(503, 'Account recovery email is not configured')
    link = base + raw_token  # trusted server configuration; no Host/header injection
    message = EmailMessage()
    message['Subject'] = 'AniRepro 360: password recovery'
    message['From'] = sender
    message['To'] = email
    message['Date'] = formatdate(localtime=False)
    message.set_content('A password reset was requested. The link expires in 20 minutes and can be used only once.\n'
                        + link + '\nIf this was not you, ignore this message.')
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)  # never send a reset secret over unencrypted SMTP
            smtp.ehlo()
            if os.getenv('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        # Do not include destination or secret in error messages/logs.
        raise HTTPException(503, 'Account recovery delivery unavailable') from exc


@app.post('/api/auth/recovery/request', status_code=202)
def request_recovery(data: RecoveryRequest, request: Request, db: DB):
    email = data.email.strip().lower()
    # Respond identically for existing and unknown addresses.
    if not os.getenv('SMTP_HOST') or not os.getenv('SMTP_FROM'):
        raise HTTPException(503, 'Account recovery email is not configured')
    recovery_throttle(db, f'recovery:ip:{request.client.host if request.client else "unknown"}', 30)
    recovery_throttle(db, f'recovery:account:{email}', 5)
    db.commit()
    user = db.scalar(select(User).where(User.email == email, User.active == True))
    if user:
        token = secrets.token_urlsafe(40)
        digest = hashlib.sha256(token.encode()).hexdigest()
        # Only the SHA-256 digest reaches the database.
        db.add(PasswordReset(user_id=user.id, token_digest=digest,
                             expires_at=datetime.now(timezone.utc) + timedelta(minutes=20)))
        # A delivery failure rolls the token back, avoiding a dead token.
        send_password_reset(email, token)
        db.commit()
    return {'message': 'If this email has an account, a recovery link has been sent.'}


@app.post('/api/auth/recovery/complete')
def complete_recovery(data: RecoveryCompletion, db: DB):
    digest = hashlib.sha256(data.token.encode()).hexdigest()
    entry = db.scalar(select(PasswordReset).where(PasswordReset.token_digest == digest).with_for_update())
    now = datetime.now(timezone.utc)
    if not entry or entry.used_at is not None or entry.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(400, 'Invalid or expired recovery link')
    user = db.get(User, entry.user_id)
    if not user or not user.active:
        raise HTTPException(400, 'Invalid or expired recovery link')
    user.password_hash = passwords.hash(data.password)
    user.session_version += 1  # revoke all existing JWT sessions, including stolen ones
    for other in db.scalars(select(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at == None)).all():
        other.used_at = now
    record_audit(db, user, None, 'password.recovered', user.id)
    db.commit()
    return {'message': 'Password updated. Sign in again on all devices.'}


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
SUPPORTED_UPLOADS = {'application/pdf', 'image/png', 'image/jpeg'}

def encryption_key():
    encoded = os.getenv('FILE_ENCRYPTION_KEY', '')
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        key = b''
    if len(key) != 32:
        raise HTTPException(503, 'Encrypted attachment storage has not been configured')
    return key


def private_storage_root() -> Path:
    root = Path(os.getenv('ATTACHMENTS_DIR', './private-attachments')).expanduser().resolve()
    # Never place protected clinical data inside the public frontend assets.
    if any(segment in {'public', 'static', 'dist'} for segment in root.parts):
        raise HTTPException(503, 'Unsafe private attachment path')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def media_type_for(content: bytes) -> str | None:
    if content.startswith(b'%PDF-'):
        return 'application/pdf'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    return None


def verify_animal(db: Session, farm_id: str, animal_id: str) -> Animal:
    animal = db.get(Animal, animal_id)
    if not animal or animal.farm_id != farm_id or animal.archived:
        raise HTTPException(404, 'Animal not found')
    return animal


def attachment_view(a: Attachment):
    return {'id': a.id, 'farm_id': a.farm_id, 'animal_id': a.animal_id,
            'event_id': a.event_id, 'name': a.display_name, 'media_type': a.media_type,
            'byte_size': a.byte_size, 'sha256': a.checksum, 'author_id': a.author_id,
            'created_at': a.created_at.isoformat()}


@app.post('/api/farms/{farm_id}/animals/{animal_id}/attachments', status_code=201)
async def upload_attachment(farm_id: str, animal_id: str, user: Auth, db: DB,
                            file: UploadFile = File(...), event_id: str | None = Form(default=None),
                            idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key')):
    role = farm_role(db, user, farm_id)
    if role not in EVIDENCE_READERS:
        raise HTTPException(403, 'Insufficient farm permissions')
    verify_animal(db, farm_id, animal_id)
    if event_id:
        event = db.get(Event, event_id)
        if not event or event.archived or event.farm_id != farm_id or event.animal_id != animal_id:
            raise HTTPException(404, 'Linked clinical record not found')
    key = encryption_key()
    content = await file.read(MAX_ATTACHMENT_BYTES + 1)
    await file.close()
    if not content or len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, 'File must be nonempty and no larger than 10 MiB')
    content_type = media_type_for(content)
    if content_type not in SUPPORTED_UPLOADS or file.content_type != content_type:
        raise HTTPException(415, 'Only verified PDF, PNG and JPEG files are accepted')
    safe_name = (file.filename or 'evidence').replace('\\','/').split('/')[-1]
    safe_name = ''.join(ch for ch in safe_name if ch.isprintable() and ch not in '<>:"|?*')[:180] or 'evidence'
    checksum = hashlib.sha256(content).hexdigest()
    digest = canonical_hash({'farm':farm_id,'animal':animal_id,'event':event_id,
                            'sha256':checksum,'name':safe_name,'media':content_type})
    replay = replay_if_known(db, user, farm_id, idempotency_key, digest, 'attachment')
    if replay is not None:
        return replay
    identifier = str(uuid.uuid4())
    storage_key = identifier + '.enc'
    # Encryption uses per-object fresh nonces; AAD binds ciphertext to database identity.
    nonce = os.urandom(12)
    ciphertext = nonce + AESGCM(key).encrypt(nonce, content, identifier.encode())
    location = private_storage_root() / storage_key
    try:
        fd = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(ciphertext)
        row = Attachment(id=identifier, farm_id=farm_id, animal_id=animal_id,
                         event_id=event_id, author_id=user.id, display_name=safe_name,
                         media_type=content_type, storage_key=storage_key, byte_size=len(content), checksum=checksum)
        db.add(row)
        record_audit(db, user, farm_id, 'attachment.create', identifier)
        db.flush()
        result = attachment_view(row)
        save_idempotency(db, user, farm_id, idempotency_key, digest, 'attachment', result)
        db.commit()
        return result
    except Exception:
        db.rollback()
        location.unlink(missing_ok=True)
        raise


@app.get('/api/farms/{farm_id}/animals/{animal_id}/attachments')
def list_attachments(farm_id: str, animal_id: str, user: Auth, db: DB):
    role = farm_role(db, user, farm_id)
    if role not in EVIDENCE_READERS:
        raise HTTPException(403, 'Insufficient farm permissions')
    verify_animal(db, farm_id, animal_id)
    rows = db.scalars(select(Attachment).where(Attachment.farm_id == farm_id,
        Attachment.animal_id == animal_id, Attachment.archived == False)
        .order_by(Attachment.created_at.desc())).all()
    return [attachment_view(a) for a in rows]


@app.get('/api/farms/{farm_id}/animals/{animal_id}/attachments/{attachment_id}/download')
def download_attachment(farm_id: str, animal_id: str, attachment_id: str, user: Auth, db: DB):
    from fastapi.responses import Response as BinaryResponse
    role = farm_role(db, user, farm_id)
    if role not in EVIDENCE_READERS:
        raise HTTPException(403, 'Insufficient farm permissions')
    verify_animal(db, farm_id, animal_id)
    a = db.get(Attachment, attachment_id)
    if not a or a.farm_id != farm_id or a.animal_id != animal_id or a.archived:
        raise HTTPException(404, 'Attachment not found')
    path = private_storage_root() / a.storage_key
    try:
        raw = path.read_bytes()
        content = AESGCM(encryption_key()).decrypt(raw[:12], raw[12:], a.id.encode())
    except Exception as exc:
        # Never expose private paths or encryption implementation details.
        raise HTTPException(503, 'Protected evidence is temporarily unavailable') from exc
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), a.checksum):
        raise HTTPException(503, 'Protected evidence integrity check failed')
    from urllib.parse import quote
    record_audit(db, user, farm_id, 'attachment.download', attachment_id)
    db.commit()
    return BinaryResponse(content, media_type=a.media_type,
        headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(a.display_name),
                 'X-Content-Type-Options':'nosniff', 'Cache-Control':'no-store'})


@app.delete('/api/farms/{farm_id}/animals/{animal_id}/attachments/{attachment_id}')
def archive_attachment(farm_id: str, animal_id: str, attachment_id: str, user: Auth, db: DB):
    role = farm_role(db, user, farm_id, WRITERS)
    verify_animal(db, farm_id, animal_id)
    a = db.get(Attachment, attachment_id)
    if not a or a.farm_id != farm_id or a.animal_id != animal_id or a.archived:
        raise HTTPException(404, 'Attachment not found')
    if user.id != a.author_id and role not in MANAGERS | CLINICIANS:
        raise HTTPException(403, 'Only the uploader, manager or veterinarian can archive evidence')
    a.archived = True  # retain the encrypted original for audit governance
    record_audit(db, user, farm_id, 'attachment.archive', attachment_id)
    db.commit()
    return {'archived': True}


# Register optional social authentication routes and models.
from . import social_auth  # noqa: E402,F401
