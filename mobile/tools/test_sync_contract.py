"""Disposable server-side contract smoke check. Never points at your real database.
Run with backend dependencies installed: python mobile/tools/test_sync_contract.py
"""
import os
import sys
import tempfile
from pathlib import Path


def main():
    backend = Path(__file__).resolve().parents[2] / 'backend'
    if len(sys.argv) > 1:
        backend = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(backend))
    with tempfile.TemporaryDirectory() as d:
        os.environ.update(DATABASE_URL=f'sqlite:///{Path(d)/"sync.db"}',
                          APP_ENV='development', SESSION_SECRET='disposable-sync-contract-only-12345678901234567890')
        from fastapi.testclient import TestClient
        from app.main import app, Base, engine
        Base.metadata.create_all(engine)
        with TestClient(app) as client:
            def post(path, body, key=None):
                headers={'X-CSRF-Token':csrf}
                if key: headers['X-Idempotency-Key']=key
                return client.post(path,json=body,headers=headers)
            result=client.post('/api/auth/register',json={'email':'sync-owner@example.com','username':'syncowner','password':'test-only-long-password','full_name':'Sync Owner','farm_name':'Disposable Farm'})
            if result.status_code != 201 and result.status_code != 200:
                # Original backend rejects additional username field; retry without it.
                result=client.post('/api/auth/register',json={'email':'sync-owner@example.com','password':'test-only-long-password','full_name':'Sync Owner','farm_name':'Disposable Farm'})
            assert result.status_code in (200,201),result.text
            csrf=result.json()['csrf_token']
            farm=client.get('/api/farms').json()[0]['id']
            path=f'/api/farms/{farm}/animals'
            body={'name':'Mother','tag':'OFFLINE-1','species':'cattle','sex':'female'}
            animal=post(path,body,'offline-animal-1')
            replay=post(path,body,'offline-animal-1')
            assert animal.status_code==201 and replay.status_code==201,(animal.text,replay.text)
            assert animal.json()['id']==replay.json()['id']
            assert len(client.get(path).json())==1
            assert post(path,{**body,'name':'Different'},'offline-animal-1').status_code==409
            event_path=f'{path}/{animal.json()["id"]}/events'
            event={'category':'reproduction','kind':'estrus','status':'observed','occurred_at':'2026-11-01T08:00:00Z','payload':{'detection_method':'visual'}}
            a=post(event_path,event,'offline-event-1'); b=post(event_path,event,'offline-event-1')
            assert a.status_code==201 and b.status_code==201,(a.text,b.text)
            assert a.json()['id']==b.json()['id']
            assert len(client.get(event_path).json())==1
            assert post(event_path,{**event,'occurred_at':'2026-11-02T08:00:00Z'},'offline-event-1').status_code==409
            # Birth + offspring is a transactional operation; replay must not create twins.
            birth={'category':'birth','kind':'delivery','status':'observed','occurred_at':'2026-11-02T08:00:00Z','payload':{'offspring_tag':'OFFLINE-CALF','offspring_sex':'female','delivery_type':'unassisted','outcome':'live_birth'}}
            a=post(event_path,birth,'offline-birth-1'); b=post(event_path,birth,'offline-birth-1')
            assert a.status_code==201 and b.status_code==201,(a.text,b.text)
            assert a.json()['id']==b.json()['id'] and a.json()['payload']['offspring_animal_id']==b.json()['payload']['offspring_animal_id']
            assert len(client.get(path).json())==2
            assert len(client.get(event_path).json())==2
            assert client.post('/api/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==200
            assert post(path,body,'offline-animal-1').status_code==401
        engine.dispose()
    print('PASS: animal replay, changed payload rejection, event replay, changed event rejection, transactional offspring replay, authenticated replay requirement.')

if __name__=='__main__': main()
