"""Live PostgreSQL API/persistence smoke test; run only against a disposable test DB.
Exits nonzero if the tested connection is not PostgreSQL or persisted data cannot be recovered.
"""
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.main import app, engine, SessionLocal, Animal, Event

if engine.dialect.name != 'postgresql':
    raise SystemExit('FAIL: Real PostgreSQL is required for this acceptance gate.')
with engine.connect() as conn:
    assert conn.execute(text('select version()')).scalar().startswith('PostgreSQL')
with TestClient(app) as client:
    initial = client.post('/api/setup', json={'email':'pg-ci-owner@example.org',
        'password':'pg-ci-strong-password','full_name':'PostgreSQL QA','farm_name':'Verification Farm'})
    assert initial.status_code == 201, initial.text
    login = client.post('/api/auth/login', json={'email':'pg-ci-owner@example.org','password':'pg-ci-strong-password'})
    assert login.status_code == 200, login.text
    csrf = login.json()['csrf_token']
    farm = client.get('/api/farms').json()[0]['id']
    headers={'X-CSRF-Token':csrf,'X-Idempotency-Key':'postgresql-check-animal-1'}
    animal = client.post(f'/api/farms/{farm}/animals',headers=headers,
        json={'name':'PG Cow','tag':'PG-TEST-1','species':'cattle'})
    assert animal.status_code == 201, animal.text
    animal_id=animal.json()['id']
    headers['X-Idempotency-Key']='postgresql-check-event-1'
    event=client.post(f'/api/farms/{farm}/animals/{animal_id}/events',headers=headers,json={
        'category':'health','kind':'examination','status':'observed',
        'occurred_at':'2026-11-13T10:00:00+03:00','payload':{'temperature_c':38.2}})
    assert event.status_code == 201, event.text
    assert client.get(f'/api/farms/{farm}/summary').json()['health_records'] == 1
    event_id=event.json()['id']
# After TestClient exits, reopen a clean SQLAlchemy session to prove PostgreSQL durability.
with SessionLocal() as db:
    a=db.get(Animal,animal_id)
    e=db.get(Event,event_id)
    assert a and a.name == 'PG Cow' and a.farm_id == farm
    assert e and e.animal_id == animal_id and e.payload['temperature_c'] == 38.2
print('PASS PostgreSQL migration/API/clinical event persistence/identity/farm scope')
