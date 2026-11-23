"""Integration of real measurement fields, registered family links and farm isolation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main as api

@pytest.fixture
def clients(tmp_path):
    engine=create_engine(f'sqlite:///{tmp_path / "lifecycle.db"}',connect_args={'check_same_thread':False})
    api.Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine)
    def get_db():
        with sessions() as session:yield session
    api.app.dependency_overrides[api.get_db]=get_db
    try:
        with TestClient(api.app) as owner, TestClient(api.app) as other:yield owner,other
    finally:
        api.app.dependency_overrides.pop(api.get_db,None)
        engine.dispose()

def test_mobile_lifecycle_fields_and_utc_roundtrip(clients):
    owner,other=clients
    def register(client,username):
        r=client.post('/api/auth/register',json={'email':f'{username}@example.org','username':username,'password':'test-1234','full_name':'Lifecycle test','farm_name':'Disposable farm'})
        assert r.status_code==201,r.text
        return r.json()
    account=register(owner,'lifecycle-owner');register(other,'lifecycle-other')
    headers={'X-CSRF-Token':account['csrf_token']};farm=account['farm_id'];path=f'/api/farms/{farm}'
    mother=owner.post(f'{path}/animals',headers=headers,json={'name':'Mother','tag':'M01','species':'cattle','sex':'female'}).json();m=mother['id'];events=f'{path}/animals/{m}/events'
    def event(category,kind,payload,at='2026-01-10T12:00:00+03:00'):
        r=owner.post(events,headers=headers,json={'category':category,'kind':kind,'status':'observed','occurred_at':at,'payload':payload})
        assert r.status_code==201,r.text
        return r.json()
    event('health','examination',{'weight_kg':250,'temperature_c':38.4})
    event('health','examination',{'weight_kg':255},'2026-01-11T12:00:00+03:00')
    event('reproduction','hormone',{'hormone_type':'P4','hormone_value':3,'hormone_unit':'ng/ml','sample_type':'serum','laboratory':'Test lab','assay_method':'Test assay'})
    birth=event('birth','delivery',{'delivery_type':'unassisted','outcome':'live_birth','offspring_tag':'C01','offspring_name':'Child','offspring_sex':'female'})
    child=birth['payload']['offspring_animal_id'];assert birth['payload']['mother_animal_id']==m
    history=owner.get(events).json();assert len(history)==4
    assert {e['payload']['weight_kg'] for e in history if e['category']=='health'}=={250,255}
    assert all(e['occurred_at'].endswith('+00:00') for e in history)
    assert any(e['occurred_at']=='2026-01-10T09:00:00+00:00' for e in history)
    assert any(a['id']==child for a in owner.get(f'{path}/animals').json())
    assert owner.get(f'{path}/events?category=birth').json()[0]['payload']['offspring_animal_id']==child
    assert other.get(events).status_code==404
    assert other.get(f'{path}/events?category=birth').status_code==404
