"""Disposable API and worker checks with a fake FCM sender; no live messages."""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

def main():
    backend=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[2]/'backend'
    sys.path.insert(0,str(backend))
    with tempfile.TemporaryDirectory() as t:
        os.environ.update(DATABASE_URL=f'sqlite:///{t}/core.db',ANIREPRO_PUSH_DB=f'{t}/private/push.sqlite3',APP_ENV='development',SESSION_SECRET='disposable-push-test-key-123456789012345678901')
        from fastapi.testclient import TestClient
        import push_gateway as gateway
        core=gateway.core
        core.Base.metadata.create_all(core.engine)
        token='test-token-not-a-real-fcm-registration-0001'
        with TestClient(gateway.app) as client:
            path='/api/mobile/push/register'
            assert client.post(path,json={'token':token}).status_code==401
            body={'email':'reminders@example.com','password':'long-test-password-only','full_name':'Reminder Owner','farm_name':'Temporary Farm'}
            result=client.post('/api/auth/register',json=body)
            if result.status_code not in (200,201):
                result=client.post('/api/auth/register',json={**body,'username':'reminderowner'})
            assert result.status_code in (200,201),result.text
            uid=result.json()['user']['id']; csrf={'X-CSRF-Token':result.json()['csrf_token']}
            fid=client.get('/api/farms').json()[0]['id']
            assert client.post(path,json={'token':token}).status_code==403
            assert client.post(path,json={'token':token},headers=csrf).status_code==200
            with core.SessionLocal() as db:
                for n in range(3):
                    db.add(core.Notification(recipient_user_id=uid,farm_id=fid,event_type='animal.created',title='test',message='never sent to FCM',created_at=datetime.now(timezone.utc)+timedelta(seconds=1) if n!=0 else datetime.now(timezone.utc)-timedelta(days=1),read_at=datetime.now(timezone.utc) if n==2 else None))
                db.commit()
            sent=[]
            gateway.scan(sent.append);gateway.scan(sent.append)
            assert sent==[token],sent
            assert client.post('/api/mobile/push/unregister',json={'token':token},headers=csrf).status_code==200
            gateway.scan(sent.append);assert sent==[token]
            assert client.post(path,json={'token':token},headers=csrf).status_code==200
            with gateway.store() as con:con.execute('UPDATE devices SET expires=0')
            gateway.scan(sent.append)
            with gateway.store() as con:assert con.execute('SELECT count(*) FROM devices').fetchone()[0]==0
        core.engine.dispose()
    print('PASS: authenticated registration, CSRF, new unread only, deduplication, unregister and expiry; fake FCM sender.')
if __name__=='__main__':main()
