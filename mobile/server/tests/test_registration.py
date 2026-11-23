"""Registration acceptance: self-service creates isolated farms, never gives access to existing farms."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app import main as api


@pytest.fixture
def clients(tmp_path):
    test_engine = create_engine(f'sqlite:///{tmp_path / "registration.db"}', connect_args={'check_same_thread':False})
    api.Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    def db():
        with session_factory() as session:
            yield session
    api.app.dependency_overrides[api.get_db] = db
    try:
        with TestClient(api.app) as owner, TestClient(api.app) as other:
            yield owner, other, session_factory
    finally:
        api.app.dependency_overrides.pop(api.get_db, None)
        test_engine.dispose()


def register_payload(email: str, farm: str):
    return {'full_name':'A Farm Owner','email':email,'password':'a-very-long-secure-password', 'farm_name':farm}


def test_signup_creates_server_session_private_farm_and_audit(clients):
    alice, bob, Session = clients
    first = alice.post('/api/auth/register', json=register_payload('ALICE@example.org','Farm A'))
    assert first.status_code == 201, first.text
    assert first.json()['user']['role'] == 'farm_manager'
    assert first.json()['csrf_token'] and first.json()['farm_id']
    assert alice.cookies.get('anirepro_session')
    assert 'HttpOnly' in first.headers['set-cookie']
    farm_a = first.json()['farm_id']
    assert alice.get('/api/farms').json() == [{'id':farm_a, 'name':'Farm A','location':'', 'role':'farm_manager',
        'permissions':sorted(api.ROLE_PERMISSIONS['farm_manager'])}]
    second = bob.post('/api/auth/register', json=register_payload('bob@example.org','Farm B'))
    assert second.status_code == 201, second.text
    farm_b = second.json()['farm_id']
    assert farm_b != farm_a
    assert bob.get('/api/farms').json()[0]['id'] == farm_b
    assert bob.get(f'/api/farms/{farm_a}/animals').status_code == 404
    assert alice.get(f'/api/farms/{farm_b}/animals').status_code == 404
    headers = {'X-CSRF-Token':first.json()['csrf_token']}
    created = alice.post(f'/api/farms/{farm_a}/animals', headers=headers, json={'name':'Lulu','species':'goat','tag':'L1'})
    assert created.status_code == 201, created.text
    assert bob.get(f'/api/farms/{farm_a}/animals/{created.json()["id"]}/events').status_code == 404
    with Session() as db:
        assert len(db.scalars(select(api.Audit).where(api.Audit.action=='account.register')).all()) == 2
        assert len(db.scalars(select(api.Membership)).all()) == 2


def test_signup_rejects_duplicate_weak_password_and_role_escalation(clients):
    first, second, _ = clients
    payload = register_payload('existing@example.org', 'Original Farm')
    assert first.post('/api/auth/register', json=payload).status_code == 201
    assert second.post('/api/auth/register', json=payload).status_code == 409
    assert second.post('/api/auth/register', json={**payload,'email':'another@example.org','password':'short'}).status_code == 422
    assert second.post('/api/auth/register', json={**payload,'email':'another@example.org','role':'administrator'}).status_code == 422
    assert second.post('/api/auth/register', json={**payload,'email':'another@example.org','farm_name':'  '}).status_code == 422
    assert second.post('/api/auth/register', json={**payload,'email':'another@example.org','full_name':'  '}).status_code == 422


def test_signup_respects_disabled_configuration(clients, monkeypatch):
    client, _, _ = clients
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION','false')
    response = client.post('/api/auth/register', json=register_payload('first@example.org','New Farm'))
    assert response.status_code == 403
    assert client.get('/api/farms').status_code == 401
