import os
import tempfile
from pathlib import Path

p = Path(tempfile.mkdtemp()) / 'test.db'
os.environ['DATABASE_URL'] = f'sqlite:///{p}'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_SECRET'] = 'test-only-secret-not-suitable-for-production-123456789'
os.environ['CORS_ORIGINS'] = 'http://localhost:8080'
from fastapi.testclient import TestClient
from app import main as api
from app.main import app, Base, engine

Base.metadata.create_all(engine)
client = TestClient(app)


def test_setup_only_once():
    payload = {'email':'manager@example.com','password':'a-real-long-password','full_name':'Farm Owner','farm_name':'Example Farm'}
    result = client.post('/api/setup', json=payload)
    assert result.status_code == 201, result.text
    assert client.post('/api/setup', json=payload).status_code == 409


def test_auth_and_membership_boundaries():
    assert client.get('/api/farms').status_code == 401
    assert client.post('/api/auth/login',json={'email':'manager@example.com','password':'wrong'}).status_code == 401
    login = client.post('/api/auth/login',json={'email':'manager@example.com','password':'a-real-long-password'})
    assert login.status_code == 200, login.text
    csrf = login.json()['csrf_token']; headers = {'X-CSRF-Token':csrf,'Origin':'http://localhost:8080'}
    farm_id = client.get('/api/farms').json()[0]['id']
    assert client.post(f'/api/farms/{farm_id}/animals',json={'name':'Cora','species':'cattle','tag':'C1'}).status_code == 403
    record = client.post(f'/api/farms/{farm_id}/animals',headers=headers,json={'name':'Cora','species':'cattle','tag':'C1'})
    assert record.status_code == 201, record.text
    animal_id = record.json()['id']
    assert client.post(f'/api/farms/{farm_id}/animals',headers=headers,json={'name':'Other','species':'goat','tag':'C1'}).status_code == 409
    assert client.get('/api/farms/bad-farm/animals').status_code == 404
    confirmed = {'category':'reproduction','kind':'ovulation','status':'confirmed','occurred_at':'2026-11-13T10:00:00Z','payload':{'evidence_reference':'lab-123'}}
    assert client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json=confirmed,headers=headers).status_code == 403
    observed = {**confirmed,'status':'observed'}
    create_event = client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json=observed,headers=headers)
    assert create_event.status_code == 201, create_event.text
    assert len(client.get(f'/api/farms/{farm_id}/animals/{animal_id}/events').json()) == 1
    assert client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json={**observed,'occurred_at':'2026-11-13T10:00:00'},headers=headers).status_code == 422
    assert client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json=observed,headers={**headers,'Origin':'https://evil.example'}).status_code == 403
    assert len(client.get(f'/api/farms/{farm_id}/audit').json()) >= 3
    create_staff = client.post(f'/api/farms/{farm_id}/members',json={'email':'vet@example.com','full_name':'Clinic Vet','password':'strong-vet-password','role':'veterinarian'},headers=headers)
    assert create_staff.status_code == 201, create_staff.text
    assert client.post('/api/auth/logout',headers=headers).status_code == 200
    assert client.get('/api/farms').status_code == 401
    vet_login = client.post('/api/auth/login',json={'email':'vet@example.com','password':'strong-vet-password'})
    vet_headers = {'X-CSRF-Token':vet_login.json()['csrf_token']}
    vet_farm = client.get('/api/farms').json()[0]
    assert vet_farm['permissions'] == sorted(api.ROLE_PERMISSIONS['veterinarian'])
    assert 'animals.create' not in vet_farm['permissions']
    assert client.post(f'/api/farms/{farm_id}/animals',headers=vet_headers,
        json={'name':'Vet Registration','species':'cattle','tag':'VET-1'}).status_code == 403
    result = client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json=confirmed,headers=vet_headers)
    assert result.status_code == 201, result.text
    offspring_event = {'category':'birth','kind':'delivery','status':'observed',
        'occurred_at':'2026-11-14T10:00:00Z','payload':{'delivery_type':'unassisted','outcome':'live_birth','offspring_tag':'VET-CALF-1'}}
    assert client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json=offspring_event,
        headers=vet_headers).status_code == 403
    assert client.post(f'/api/farms/{farm_id}/animals/{animal_id}/events',json={**confirmed,'payload':{}},headers=vet_headers).status_code == 422
    assert client.post(f'/api/farms/{farm_id}/members',json={'email':'other@example.com','full_name':'Other','password':'strong-other-password','role':'farmer'},headers=vet_headers).status_code == 403


def test_cross_farm_access_is_not_inferred_from_client_ids():
    from app.main import SessionLocal, Farm, Membership, User
    with SessionLocal() as db:
        other = Farm(name='Separate Farm')
        db.add(other); db.flush()
        outsider = User(email='outsider@example.com', name='Outsider', password_hash='not-used', role='farmer')
        db.add(outsider); db.flush()
        db.add(Membership(user_id=outsider.id, farm_id=other.id, role='farmer'))
        other_id = other.id
        db.commit()
    signed_in = client.post('/api/auth/login',json={'email':'manager@example.com','password':'a-real-long-password'})
    assert signed_in.status_code == 200
    headers={'X-CSRF-Token':signed_in.json()['csrf_token']}
    assert client.get(f'/api/farms/{other_id}/animals').status_code == 404
    assert client.post(f'/api/farms/{other_id}/animals',headers=headers,json={'name':'Leaked','species':'goat','tag':'X1'}).status_code == 404
    assert client.get(f'/api/farms/{other_id}/audit').status_code == 404
