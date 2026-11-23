"""Run from a PATCHED backend root with a disposable SQLite DATABASE_URL only."""
import os
from pathlib import Path
import sys
import uuid
url=os.environ.get('DATABASE_URL','')
if not url.startswith('sqlite:') or os.environ.get('APP_ENV')=='production':raise SystemExit('Disposable SQLite development database required.')
sys.path.insert(0,str(Path.cwd()))
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
suffix=uuid.uuid4().hex[:12]; username='mobile.'+suffix; email=f'{suffix}@example.com'; new='changed.'+suffix; password='A1bc-567'
body={'email':email,'username':username,'password':password,'full_name':'Mobile test','farm_name':'Mobile test farm'}
r=c.post('/api/auth/register',json=body);assert r.status_code==201,r.text
assert c.get('/api/me').json()['username']==username
assert c.post('/api/auth/logout',headers={'X-CSRF-Token':r.json()['csrf_token']}).status_code==200
for login in ({'username':username.upper(),'password':password},{'email':email,'password':password}):
 r=c.post('/api/auth/login',json=login);assert r.status_code==200,r.text
assert c.get('/api/farms').status_code==200
r=c.patch('/api/auth/username',headers={'X-CSRF-Token':r.json()['csrf_token']},json={'username':new});assert r.status_code==200,r.text
assert c.post('/api/auth/login',json={'username':new,'password':password}).status_code==200
assert c.post('/api/auth/register',json={**body,'email':'duplicate-'+email,'username':new}).status_code==409
assert c.post('/api/auth/register',json={**body,'email':'short-'+email,'password':'short'}).status_code==422
print('PASS: registration, username/email login, CSRF logout, farm access, username change, uniqueness, eight-character minimum.')
