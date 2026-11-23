import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app import main as api
from app import social_auth as social
from urllib.parse import urlparse, parse_qs
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import timedelta

@pytest.fixture
def clients(tmp_path,monkeypatch):
    for key,value in {'SOCIAL_PUBLIC_ORIGIN':'https://farm.example.org','GOOGLE_OAUTH_CLIENT_ID':'google-id','GOOGLE_OAUTH_CLIENT_SECRET':'test-only','APPLE_OAUTH_CLIENT_ID':'apple-id','APPLE_OAUTH_PRIVATE_KEY_FILE':'test-only','APPLE_OAUTH_TEAM_ID':'team','APPLE_OAUTH_KEY_ID':'key','ALLOW_PUBLIC_REGISTRATION':'true'}.items():monkeypatch.setenv(key,value)
    engine=create_engine(f'sqlite:///{tmp_path / "social.db"}',connect_args={'check_same_thread':False})
    api.Base.metadata.create_all(engine);factory=sessionmaker(bind=engine)
    def db():
        with factory() as s:yield s
    api.app.dependency_overrides[api.get_db]=db
    try:
        with TestClient(api.app) as c,TestClient(api.app) as other:yield c,other,factory
    finally:api.app.dependency_overrides.pop(api.get_db,None);engine.dispose()

def begin(c,provider='google'):
    r=c.post('/api/auth/social/start',json={'provider':provider});assert r.status_code==200,r.text
    v=r.json();q=parse_qs(urlparse(v['authorization_url']).query)
    assert q['state']==[v['flow']] and 'nonce' in q and v['proof'] not in v['authorization_url']
    if provider=='google':assert q['code_challenge_method']==['S256']
    else:assert q['response_mode']==['form_post']
    return {'flow':v['flow'],'proof':v['proof']}

def verify(c,monkeypatch,p,provider='google',subject='immutable-id',email='farmer@example.org',verified=True):
    monkeypatch.setattr(social,'verified_claims',lambda *args:{'sub':subject,'email':email,'email_verified':verified,'name':'Farm Owner'})
    payload={'state':p['flow'],'code':'simulated-code'}
    if provider=='google':return c.get('/api/auth/social/callback/google',params=payload)
    return c.post('/api/auth/social/callback/apple',data=payload,headers={'Origin':'https://appleid.apple.com'})

def test_registration_login_and_replay(clients,monkeypatch):
    c,other,db=clients;p=begin(c)
    assert other.post('/api/auth/social/status',json={**p,'proof':'x'*64}).status_code==404
    assert c.post('/api/auth/social/finish',json=p).status_code==409
    assert 'verified' in verify(c,monkeypatch,p).text
    assert c.post('/api/auth/social/status',json=p).json()['action']=='register'
    assert c.post('/api/auth/social/finish',json=p).status_code==422
    r=c.post('/api/auth/social/finish',json={**p,'full_name':'Test Farmer','farm_name':'Private Farm'});assert r.status_code==200,r.text
    uid=r.json()['user']['id']; assert c.get('/api/farms').json()[0]['name']=='Private Farm'
    assert other.post('/api/auth/social/finish',json=p).status_code==409
    p2=begin(other);verify(other,monkeypatch,p2,email='changed@example.org')
    assert other.post('/api/auth/social/status',json=p2).json()['action']=='login'
    assert other.post('/api/auth/social/finish',json=p2).json()['user']['id']==uid
    with db() as d:assert len(d.scalars(select(api.Farm)).all())==1

def test_existing_email_requires_password_and_apple_callback(clients,monkeypatch):
    c,other,db=clients;r=c.post('/api/auth/register',json={'email':'farmer@example.org','password':'long-password','full_name':'Original Owner','farm_name':'Original Farm'});assert r.status_code==201
    p=begin(other,'apple');assert verify(other,monkeypatch,p,'apple').status_code==200
    assert other.post('/api/auth/social/status',json=p).json()['action']=='link'
    assert other.post('/api/auth/social/finish',json={**p,'password':'wrong'}).status_code==401
    assert other.get('/api/farms').status_code==401
    r2=other.post('/api/auth/social/finish',json={**p,'password':'long-password'});assert r2.status_code==200,r2.text
    assert r2.json()['user']['id']==r.json()['user']['id']
    assert other.get('/api/farms').json()[0]['name']=='Original Farm'
    assert other.post('/api/auth/login',json={'email':'farmer@example.org','password':'long-password'}).status_code==200

def test_unverified_email_and_disabled_registration(clients,monkeypatch):
    c,_,_=clients;p=begin(c);verify(c,monkeypatch,p,verified=False)
    assert c.post('/api/auth/social/status',json=p).json()['action']=='unavailable'
    assert c.post('/api/auth/social/finish',json=p).status_code==403
    p=begin(c);verify(c,monkeypatch,p);monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION','false')
    assert c.post('/api/auth/social/finish',json={**p,'full_name':'Test User','farm_name':'New Farm'}).status_code==403

def test_expiry_cancel_and_unconfigured(clients,monkeypatch):
    c,_,db=clients;p=begin(c)
    with db() as d:
        f=d.get(social.SocialFlow,social.digest(p['flow']));f.expires=social.now()-timedelta(seconds=1);d.commit()
    assert c.post('/api/auth/social/status',json=p).status_code==404
    p=begin(c);c.get('/api/auth/social/callback/google',params={'state':p['flow'],'error':'access_denied'})
    assert c.post('/api/auth/social/status',json=p).json()['status']=='failed'
    monkeypatch.delenv('GOOGLE_OAUTH_CLIENT_SECRET');assert c.get('/api/auth/social/providers').json()['google'] is False
    assert c.post('/api/auth/social/start',json={'provider':'google'}).status_code==503

def test_real_jwt_signature_audience_issuer_and_nonce_checks(clients,monkeypatch):
    c,_,db=clients;p=begin(c)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    with db() as d:
        flow=d.get(social.SocialFlow,social.digest(p['flow']));t=social.now()
        claims={'iss':'https://accounts.google.com','aud':'google-id','iat':t,'exp':t+timedelta(minutes=5),'sub':'provider-sub','nonce':flow.nonce}
        class FakeResponse:
            def raise_for_status(self):pass
            def json(self):return {'id_token':jwt.encode(claims,key,algorithm='RS256',headers={'kid':'test'})}
        class FakeJwks:
            def __init__(self,*args,**kw):pass
            def get_signing_key_from_jwt(self,*args):
                from types import SimpleNamespace
                return SimpleNamespace(key=key.public_key())
        def exchange(url,**kw):
            assert kw['data']['code_verifier']==flow.verifier
            return FakeResponse()
        monkeypatch.setattr(social.httpx,'post',exchange);monkeypatch.setattr(social.jwt,'PyJWKClient',FakeJwks)
        assert social.verified_claims('google','test-code',flow)['sub']=='provider-sub'
        for field,bad in [('nonce','wrong'),('aud','other-client'),('iss','https://evil.example'),('exp',t-timedelta(minutes=5))]:
            old=claims[field];claims[field]=bad
            with pytest.raises((ValueError,jwt.InvalidTokenError)):social.verified_claims('google','test-code',flow)
            claims[field]=old
