"""Independent acceptance tests derived from the two supplied specifications."""
import os
import tempfile
import pytest
from pathlib import Path

p = Path(tempfile.mkdtemp()) / 'workflows.db'
os.environ['DATABASE_URL'] = f'sqlite:///{p}'
os.environ['APP_ENV'] = 'development'
os.environ['SESSION_SECRET'] = 'strict-development-integration-secret-123456789'
os.environ['CORS_ORIGINS'] = 'http://localhost:8080'
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app, Base, get_db

client = TestClient(app)

@pytest.fixture(scope='module', autouse=True)
def separate_workflow_database():
    own_engine = create_engine(f'sqlite:///{p}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(own_engine)
    Session = sessionmaker(bind=own_engine)
    def db_session():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = db_session
    yield
    app.dependency_overrides.pop(get_db, None)
    own_engine.dispose()



def post(path, json, csrf):
    return client.post(path, json=json, headers={'X-CSRF-Token': csrf})


def test_birth_history_and_cycle_summary_and_export():
    assert client.post('/api/setup', json={'email':'manager@example.com', 'password':'a-real-long-password', 'full_name':'Farm Owner','farm_name':'Quality Test Farm'}).status_code == 201
    result = client.post('/api/auth/login', json={'email':'manager@example.com', 'password':'a-real-long-password'})
    assert result.status_code == 200
    csrf = result.json()['csrf_token']
    farm = client.get('/api/farms').json()[0]['id']
    base = f'/api/farms/{farm}'
    invalid_birth = post(f'{base}/animals', {'name':'Wrong', 'species':'cattle','tag':'X', 'date_of_birth':'2099-01-01'}, csrf)
    assert invalid_birth.status_code == 422
    birth_issue = invalid_birth.json()['detail'][0]
    assert birth_issue['loc'] == ['body','date_of_birth']
    assert birth_issue['type'] == 'value_error'
    assert birth_issue['msg'] == 'Value error, Date of birth cannot be in the future'
    too_long_tag = post(f'{base}/animals', {'name':'Wrong', 'species':'cattle','tag':'T'*121}, csrf)
    assert too_long_tag.status_code == 422
    tag_issue = too_long_tag.json()['detail'][0]
    assert tag_issue['loc'] == ['body','tag']
    assert tag_issue['type'] == 'string_too_long'
    assert tag_issue['msg'] == 'String should have at most 120 characters'
    invalid_weight = post(f'{base}/animals', {'name':'Wrong','species':'cattle','tag':'W-1','weight_kg':'heavy'}, csrf)
    assert invalid_weight.status_code == 422
    weight_issue = invalid_weight.json()['detail'][0]
    assert weight_issue['loc'] == ['body','weight_kg']
    assert weight_issue['type'] == 'float_parsing'
    assert weight_issue['msg'] == 'Input should be a valid number, unable to parse string as a number'
    animal = post(f'{base}/animals', {'name':'Mother', 'species':'cattle','tag':'C-11','sex':'female','date_of_birth':'2023-01-01','weight_kg':420}, csrf)
    assert animal.status_code == 201, animal.text
    animal_id = animal.json()['id']
    ev_path = f'{base}/animals/{animal_id}/events'
    for onset in ['2026-08-01','2026-08-22','2026-09-12','2026-10-03']:
        e = post(ev_path, {'category':'reproduction','kind':'estrus','status':'observed','occurred_at':onset+'T08:00:00Z','payload':{'detection_method':'visual'}},csrf)
        assert e.status_code == 201, e.text
    summary = client.get(f'{base}/animals/{animal_id}/cycle-summary')
    assert summary.status_code == 200, summary.text
    assert summary.json()['interval_days'] == [21,21,21]
    assert summary.json()['estimated_next_estrus'] == '2026-10-24'
    assert summary.json()['estimate_status'] == 'prediction_not_confirmed'
    record_id = e.json()['id']
    delete_path = f'{ev_path}/{record_id}'
    assert client.delete(delete_path).status_code == 403
    for _ in range(2):
        result = client.delete(delete_path, headers={'X-CSRF-Token': csrf})
        assert result.status_code == 200, result.text
    assert record_id not in {record['id'] for record in client.get(ev_path).json()}
    assert record_id not in client.get(f'{base}/reports/csv').text
    assert client.get(f'{base}/animals/{animal_id}/cycle-summary').json()['estimated_next_estrus'] == '2026-10-03'
    assert client.get(f'{base}/audit').text.count('reproduction.archive') == 1
    service = post(ev_path, {
        'category': 'breeding', 'kind': 'service', 'status': 'observed',
        'occurred_at': '2026-10-03T10:00:00Z',
        'payload': {'method': 'natural', 'planned_pregnancy_check_date': '2026-11-03'},
    }, csrf)
    assert service.status_code == 201, service.text
    service_id = service.json()['id']
    assert client.delete(f'{ev_path}/{service_id}', headers={'X-CSRF-Token': csrf}).status_code == 200
    assert client.get(f'{base}/events?category=breeding').json() == []
    assert client.get(f'{base}/audit').text.count('breeding.archive') == 1
    invalid_hormone = post(ev_path, {'category':'reproduction','kind':'hormone','status':'observed','occurred_at':'2026-10-04T08:00:00Z','payload':{'hormone_value':'4'}},csrf)
    assert invalid_hormone.status_code == 422
    birth = {'category':'birth','kind':'delivery','status':'observed','occurred_at':'2026-10-04T08:00:00Z','payload':{'delivery_type':'unassisted','outcome':'live_birth','offspring_name':'Calf','offspring_tag':'C-12','offspring_sex':'female','birth_weight_kg':28}}
    response = post(ev_path,birth,csrf)
    assert response.status_code == 201, response.text
    child_id = response.json()['payload']['offspring_animal_id']
    assert response.json()['payload']['mother_animal_id'] == animal_id
    assert any(a['id']==child_id for a in client.get(f'{base}/animals').json())
    assert post(ev_path,birth,csrf).status_code == 409
    assert len(client.get(f'{base}/events?category=birth').json()) == 1
    assert client.get(f'{base}/summary').json()['births'] == 1
    csv = client.get(f'{base}/reports/csv')
    assert csv.status_code == 200 and 'offspring' not in csv.text and 'birth' in csv.text
    pdf = client.get(f'{base}/reports/pdf')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
    assert client.get('/api/farms/not-a-farm/reports/csv').status_code == 404
    delivery_id = response.json()['id']
    assert client.delete(f'{ev_path}/{delivery_id}', headers={'X-CSRF-Token': csrf}).status_code == 200
    assert client.get(f'{base}/events?category=birth').json() == []
    assert client.get(f'{base}/summary').json()['births'] == 0
    assert any(a['id'] == child_id for a in client.get(f'{base}/animals').json())
    assert client.get(f'{base}/audit').text.count('birth.archive') == 1


def test_authz_and_clinical_confirmation_are_restricted():
    login=client.post('/api/auth/login',json={'email':'manager@example.com','password':'a-real-long-password'})
    csrf=login.json()['csrf_token']; farm=client.get('/api/farms').json()[0]['id']
    assert client.get('/api/species/profiles').json()['rabbit']['ovulation_type']=='induced'
    assert post(f'/api/farms/{farm}/members',{'email':'farmer2@example.org','full_name':'Farm Worker','password':'long-worker-password','role':'farmer'},csrf).status_code == 201
    assert post('/api/auth/logout',{},csrf).status_code==200
    worker=client.post('/api/auth/login',json={'email':'farmer2@example.org','password':'long-worker-password'})
    csrf=worker.json()['csrf_token']
    animal=client.get(f'/api/farms/{farm}/animals').json()[0]['id']
    confirmed={'category':'pregnancy','kind':'confirmation','status':'confirmed','occurred_at':'2026-10-04T08:00:00Z','payload':{'confirmation_method':'ultrasound','evidence_reference':'US-77'}}
    assert post(f'/api/farms/{farm}/animals/{animal}/events',confirmed,csrf).status_code==403
    assert client.get(f'/api/farms/{farm}/reports/csv').status_code==403
    assert client.get(f'/api/farms/{farm}/audit').status_code==403
