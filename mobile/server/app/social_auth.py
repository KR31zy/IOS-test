"""Browser-based OIDC for native apps. State, nonce and a separate app-only proof.
Provider tokens are verified on the server and never returned to the mobile client.
"""
import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, EmailStr, TypeAdapter, ValidationError
from sqlalchemy import ForeignKey, String, DateTime, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from argon2.exceptions import VerificationError
from .main import (app, Base, DB, User, Farm, Membership, passwords,
                   recovery_throttle, record_audit, start_session)

PROVIDERS = {
    'google': ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token', 'https://www.googleapis.com/oauth2/v3/certs', ['https://accounts.google.com', 'accounts.google.com']),
    'apple': ('https://appleid.apple.com/auth/authorize', 'https://appleid.apple.com/auth/token', 'https://appleid.apple.com/auth/keys', ['https://appleid.apple.com']),
}
Provider = Literal['google', 'apple']

def now(): return datetime.now(timezone.utc)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def aware(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

class SocialIdentity(Base):
    __tablename__ = 'social_identities'
    provider: Mapped[str] = mapped_column(String(12), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)

class SocialFlow(Base):
    __tablename__ = 'social_flows'
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    proof: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(12))
    nonce: Mapped[str] = mapped_column(String(128))
    verifier: Mapped[str] = mapped_column(String(128))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default='pending')
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')
class Start(Strict):
    provider: Provider
class Proof(Strict):
    flow: str = Field(min_length=40,max_length=100)
    proof: str = Field(min_length=40,max_length=100)
class Finish(Proof):
    full_name: str | None = Field(default=None,min_length=2,max_length=180)
    farm_name: str | None = Field(default=None,min_length=2,max_length=180)
    password: str | None = Field(default=None,max_length=256)

def config(provider):
    origin = os.getenv('SOCIAL_PUBLIC_ORIGIN','').rstrip('/')
    u = urlsplit(origin)
    client = os.getenv(f'{provider.upper()}_OAUTH_CLIENT_ID','').strip()
    secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET','') if provider == 'google' else os.getenv('APPLE_OAUTH_PRIVATE_KEY_FILE','')
    if (u.scheme != 'https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment
            or not client or not secret or (provider == 'apple' and not all(os.getenv(k) for k in ('APPLE_OAUTH_TEAM_ID','APPLE_OAUTH_KEY_ID')))):
        raise HTTPException(503, f'{provider.title()} sign-in is not configured on this server')
    return client, origin + f'/api/auth/social/callback/{provider}'

def client_secret(provider, client):
    if provider == 'google': return os.environ['GOOGLE_OAUTH_CLIENT_SECRET']
    with open(os.environ['APPLE_OAUTH_PRIVATE_KEY_FILE'],encoding='utf-8') as f: key=f.read()
    t=now()
    return jwt.encode({'iss':os.environ['APPLE_OAUTH_TEAM_ID'],'iat':t,'exp':t+timedelta(minutes=10),'aud':'https://appleid.apple.com','sub':client},key,algorithm='ES256',headers={'kid':os.environ['APPLE_OAUTH_KEY_ID']})

def verified_claims(provider, code, flow):
    client, redirect = config(provider)
    _, token_url, keys_url, issuers = PROVIDERS[provider]
    form={'grant_type':'authorization_code','code':code,'client_id':client,'client_secret':client_secret(provider,client),'redirect_uri':redirect}
    if provider=='google': form['code_verifier']=flow.verifier
    response=httpx.post(token_url,data=form,timeout=15);response.raise_for_status()
    token=response.json()['id_token']
    key=jwt.PyJWKClient(keys_url,timeout=10).get_signing_key_from_jwt(token).key
    claims=jwt.decode(token,key,algorithms=['RS256'],audience=client,issuer=issuers,options={'require':['iss','aud','exp','iat','sub','nonce']},leeway=30)
    if not isinstance(claims.get('nonce'),str) or not hmac.compare_digest(claims['nonce'],flow.nonce): raise ValueError('invalid nonce')
    if claims.get('azp',client)!=client or (isinstance(claims['aud'],list) and len(claims['aud'])>1 and claims.get('azp')!=client): raise ValueError('invalid authorized party')
    return claims

def identity_fields(claims):
    sub=claims.get('sub')
    if not isinstance(sub,str) or not 0<len(sub)<=255: raise ValueError('invalid subject')
    email=None
    if claims.get('email_verified') in (True,'true') and isinstance(claims.get('email'),str):
        try: email=str(TypeAdapter(EmailStr).validate_python(claims['email'])).lower()
        except ValidationError: pass
    name=claims.get('name')
    return sub,email,name.strip()[:180] if isinstance(name,str) else None

@app.get('/api/auth/social/providers')
def social_providers():
    result={}
    for p in PROVIDERS:
        try: config(p);result[p]=True
        except HTTPException: result[p]=False
    return result

@app.post('/api/auth/social/start')
def social_start(data:Start, request:Request, db:DB):
    client, redirect=config(data.provider)
    recovery_throttle(db,f'social:start:{request.client.host if request.client else "unknown"}',30,15)
    db.execute(delete(SocialFlow).where(SocialFlow.expires < now()).execution_options(synchronize_session=False))
    state, proof, nonce, verifier=(secrets.token_urlsafe(48) for _ in range(4))
    db.add(SocialFlow(state=digest(state),proof=digest(proof),provider=data.provider,nonce=nonce,verifier=verifier,expires=now()+timedelta(minutes=10)))
    db.commit()
    params={'client_id':client,'redirect_uri':redirect,'response_type':'code','scope':'openid email profile' if data.provider=='google' else 'name email','state':state,'nonce':nonce}
    if data.provider=='google': params.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),code_challenge_method='S256',prompt='select_account')
    else: params['response_mode']='form_post'
    return {'flow':state,'proof':proof,'authorization_url':PROVIDERS[data.provider][0]+'?'+urlencode(params),'expires_in':600}

def result_page(ok):
    message='Sign-in verified. Return to AniRepro 360 to continue.' if ok else 'Sign-in was cancelled or could not be verified. Return to AniRepro 360 and try again.'
    return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AniRepro 360</title><body><main><h1>AniRepro 360</h1><p>'+message+'</p></main></body></html>',headers={'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"})

def process_callback(provider, params, db):
    state=params.get('state'); code=params.get('code')
    if not isinstance(state,str) or not 40<=len(state)<=100:return result_page(False)
    flow=db.get(SocialFlow,digest(state))
    if not flow or flow.provider!=provider or aware(flow.expires)<=now():return result_page(False)
    claimed=db.execute(update(SocialFlow).where(SocialFlow.state==flow.state,SocialFlow.status=='pending').values(status='verifying')).rowcount
    db.commit()
    if claimed!=1:return result_page(False)
    try:
        if params.get('error') or not isinstance(code,str) or not 1<=len(code)<=4096: raise ValueError('cancelled')
        sub,email,name=identity_fields(verified_claims(provider,code,flow))
        flow.subject,flow.email,flow.name=sub,email,name
        flow.status='ready';db.commit();return result_page(True)
    except Exception:
        db.rollback();flow.status='failed';db.commit();return result_page(False)

@app.get('/api/auth/social/callback/google',response_class=HTMLResponse)
def google_callback(request:Request,db:DB):return process_callback('google',request.query_params,db)

@app.post('/api/auth/social/callback/apple',response_class=HTMLResponse)
async def apple_callback(request:Request,db:DB):
    # Apple's form_post uses a cross-origin browser POST; the random state and
    # server-side code/nonce verification are mandatory, never cookie auth.
    async with request.form(max_fields=10,max_files=0) as form:
        # Avoid blocking the event loop with provider network requests.
        params=dict(form)
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(process_callback,'apple',params,db)

def lookup(data,db):
    flow=db.get(SocialFlow,digest(data.flow))
    if not flow or not hmac.compare_digest(flow.proof,digest(data.proof)) or aware(flow.expires)<=now():raise HTTPException(404,'Sign-in expired. Start again.')
    return flow

def account(flow,db):
    link=db.get(SocialIdentity,(flow.provider,flow.subject)) if flow.subject else None
    if link:return 'login',db.get(User,link.user_id)
    if not flow.email:return 'unavailable',None
    existing=db.scalar(select(User).where(User.email==flow.email))
    return ('link',existing) if existing else ('register',None)

@app.post('/api/auth/social/status')
def social_status(data:Proof,db:DB):
    flow=lookup(data,db)
    if flow.status!='ready':return {'status':flow.status}
    action,user=account(flow,db)
    if user and not user.active:return {'status':'failed'}
    return {'status':'ready','action':action,'email':flow.email,'name':flow.name}

@app.post('/api/auth/social/finish')
def social_finish(data:Finish,request:Request,response:Response,db:DB):
    flow=lookup(data,db)
    if flow.status!='ready':raise HTTPException(409,'Sign-in is not ready or has already been used')
    action,user=account(flow,db)
    if action=='unavailable' or (user and not user.active):raise HTTPException(403,'Account unavailable')
    if action=='link':
        # Never auto-link by matching an email, even a verified provider email.
        recovery_throttle(db,f'social:link:{user.id}',10,15);db.commit()
        try: valid=bool(data.password and passwords.verify(user.password_hash,data.password))
        except VerificationError:valid=False
        if not valid:raise HTTPException(401,'Enter your existing AniRepro password to link this account')
    elif action=='register':
        if os.getenv('ALLOW_PUBLIC_REGISTRATION','true').lower()!='true':raise HTTPException(403,'Public registration is not enabled')
        if not data.full_name or len(data.full_name.strip())<2 or not data.farm_name or len(data.farm_name.strip())<2:raise HTTPException(422,'Enter your name and farm name')
    claimed=db.execute(update(SocialFlow).where(SocialFlow.state==flow.state,SocialFlow.status=='ready',SocialFlow.expires>now()).values(status='consumed').execution_options(synchronize_session=False)).rowcount
    if claimed!=1:db.rollback();raise HTTPException(409,'Sign-in has already been used')
    try:
        if action=='register':
            user=User(email=flow.email,name=data.full_name.strip(),password_hash=passwords.hash(secrets.token_urlsafe(48)),role='farm_manager')
            farm=Farm(name=data.farm_name.strip());db.add_all([user,farm]);db.flush()
            db.add(Membership(user_id=user.id,farm_id=farm.id,role='farm_manager'));record_audit(db,user,farm.id,'account.register',user.id)
        if action!='login':
            db.add(SocialIdentity(provider=flow.provider,subject=flow.subject,user_id=user.id));record_audit(db,user,None,'account.social_link',user.id)
        # Erase transient provider details after consuming the one-use flow.
        flow.email=flow.name=flow.subject=None;flow.nonce=flow.verifier='';db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Account changed during sign-in. Start again.') from None
    return start_session(user,response)
