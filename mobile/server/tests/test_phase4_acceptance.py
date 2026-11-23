"""Independent adversarial Phase 4 acceptance checks based on the two product PDFs."""
import os
import tempfile
from pathlib import Path
from base64 import b64encode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import main as api

@pytest.fixture
def environment(monkeypatch, tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "phase4.db"}', connect_args={'check_same_thread': False})
    api.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    def open_db():
        with Session() as db:
            yield db
    api.app.dependency_overrides[api.get_db] = open_db
    monkeypatch.setenv('FILE_ENCRYPTION_KEY', b64encode(bytes(range(32))).decode())
    monkeypatch.setenv('ATTACHMENTS_DIR', str(tmp_path / 'private'))
    monkeypatch.setenv('SMTP_HOST', 'mail.private.test')
    monkeypatch.setenv('SMTP_FROM', 'no-reply@example.org')
    mailbox = []
    monkeypatch.setattr(api, 'send_password_reset', lambda dest, token: mailbox.append((dest, token)))
    with TestClient(api.app) as client:
        yield client, Session, mailbox, tmp_path
    api.app.dependency_overrides.pop(api.get_db, None)
    engine.dispose()


def setup(client):
    assert client.post('/api/setup', json={'email':'owner@example.org', 'password':'good-owner-passphrase',
        'full_name':'Farm Owner','farm_name':'Oak Farm'}).status_code == 201
    response = client.post('/api/auth/login', json={'email':'owner@example.org','password':'good-owner-passphrase'})
    assert response.status_code == 200, response.text
    csrf = response.json()['csrf_token']
    farm = client.get('/api/farms').json()[0]['id']
    path = f'/api/farms/{farm}'
    return {'X-CSRF-Token':csrf}, path


def test_replay_safe_records_and_conflicts(environment):
    client, Session, _, _ = environment
    headers, path = setup(client)
    animal_payload = {'name':'Cow One','species':'cattle','tag':'tag-01'}
    headers['X-Idempotency-Key'] = 'offline-animal-001'
    first = client.post(path+'/animals', headers=headers, json=animal_payload)
    assert first.status_code == 201, first.text
    repeated = client.post(path+'/animals', headers=headers, json=animal_payload)
    assert repeated.status_code == 201 and repeated.json()['id'] == first.json()['id']
    assert client.post(path+'/animals', headers=headers, json={**animal_payload,'tag':'tag-02'}).status_code == 409
    headers['X-Idempotency-Key'] = 'offline-event-001'
    event = {'category':'health','kind':'examination','status':'observed',
             'occurred_at':'2026-11-13T11:00:00Z', 'payload':{'temperature_c':38.5}}
    event_path = path + '/animals/' + first.json()['id'] + '/events'
    one = client.post(event_path, json=event, headers=headers)
    two = client.post(event_path, json=event, headers=headers)
    assert one.status_code == 201 and two.status_code == 201, (one.text, two.text)
    assert one.json()['id'] == two.json()['id']
    assert client.post(event_path, json={**event,'status':'completed'}, headers=headers).status_code == 409
    assert len(client.get(event_path).json()) == 1
    with Session() as db:
        assert len(db.scalars(select(api.Idempotency)).all()) == 2
        assert len(db.scalars(select(api.Audit).where(api.Audit.action == 'health.create')).all()) == 1


def test_private_encrypted_attachment_and_permissions(environment):
    client, Session, _, root = environment
    headers, path = setup(client)
    animal = client.post(path+'/animals',json={'name':'Mia','species':'goat','tag':'G-3'},headers=headers).json()['id']
    base = path+f'/animals/{animal}/attachments'
    contents = b'%PDF-1.4\nAnirepro clinical ultrasound private evidence\n%%EOF'
    response = client.post(base, headers={**headers,'X-Idempotency-Key':'scan-upload-00001'},
       files={'file':('scan.pdf',contents,'application/pdf')})
    assert response.status_code == 201, response.text
    file_id = response.json()['id']
    assert response.json()['sha256']
    assert client.get(base).json()[0]['id'] == file_id
    stored = (root/'private'/f'{file_id}.enc').read_bytes()
    assert contents not in stored and len(stored) > len(contents)
    downloaded = client.get(base+f'/{file_id}/download')
    assert downloaded.status_code == 200 and downloaded.content == contents
    assert 'attachment;' in downloaded.headers['content-disposition']
    assert downloaded.headers['x-content-type-options'] == 'nosniff'
    duplicated = client.post(base, headers={**headers,'X-Idempotency-Key':'scan-upload-00001'},
       files={'file':('scan.pdf',contents,'application/pdf')})
    assert duplicated.status_code == 201 and duplicated.json()['id'] == file_id
    assert client.post(base, headers=headers,files={'file':('bad.pdf',b'<script>attack</script>','application/pdf')}).status_code == 415
    assert client.post(base, headers=headers,files={'file':('bad.exe',b'MZ'+b'X'*16,'application/octet-stream')}).status_code == 415
    assert client.post(base, headers=headers,files={'file':('huge.pdf',b'%PDF-'+b'A'*(10*1024*1024),'application/pdf')}).status_code == 413
    assert client.post(base, headers=headers, data={'event_id':'different-farm'},
       files={'file':('scan.pdf',contents,'application/pdf')}).status_code == 404
    assert client.get('/api/farms/wrong/animals/'+animal+f'/attachments/{file_id}/download').status_code == 404
    assert client.delete(base+'/'+file_id, headers={'X-CSRF-Token':'wrong'}).status_code == 403
    archived = client.delete(base+'/'+file_id, headers=headers)
    assert archived.status_code == 200
    assert client.get(base+f'/{file_id}/download').status_code == 404
    assert file_id not in str(client.get(base).json())


def test_password_recovery_revoke_and_replay(environment):
    client, Session, mailbox, _ = environment
    headers, path = setup(client)
    old_session = client.cookies.get('anirepro_session')
    unknown = client.post('/api/auth/recovery/request', json={'email':'unknown@example.org'})
    real = client.post('/api/auth/recovery/request', json={'email':'owner@example.org'})
    assert unknown.status_code == real.status_code == 202
    assert unknown.json() == real.json()
    assert len(mailbox) == 1 and mailbox[0][0] == 'owner@example.org'
    token = mailbox[0][1]
    assert len(token) >= 32
    with Session() as db:
        reset = db.scalars(select(api.PasswordReset)).first()
        assert token != reset.token_digest
    assert client.post('/api/auth/recovery/complete',json={'token':'invalid'*10,'password':'another-secure-password'}).status_code == 400
    done = client.post('/api/auth/recovery/complete',json={'token':token,'password':'another-secure-password'})
    assert done.status_code == 200, done.text
    assert client.post('/api/auth/recovery/complete',json={'token':token,'password':'another-secure-password'}).status_code == 400
    assert client.get('/api/farms').status_code == 401  # session invalidated immediately
    assert client.post('/api/auth/login',json={'email':'owner@example.org','password':'good-owner-passphrase'}).status_code == 401
    assert client.post('/api/auth/login',json={'email':'owner@example.org','password':'another-secure-password'}).status_code == 200
    assert client.get('/api/farms').status_code == 200
    with Session() as db:
        assert any(row.action=='password.recovered' for row in db.scalars(select(api.Audit)).all())


def test_access_controls_no_evidence_leakage_between_farms(environment):
    client, Session, _, root = environment
    headers, path = setup(client)
    animal = client.post(path+'/animals',json={'name':'Local','species':'cow','tag':'AA'},headers=headers).json()['id']
    blob = b'\x89PNG\r\n\x1a\n'+b'private image data'
    res = client.post(path+f'/animals/{animal}/attachments',headers=headers,
       files={'file':('image.png',blob,'image/png')})
    attachment_id = res.json()['id']
    with Session() as db:
        user = db.scalar(select(api.User).where(api.User.email=='owner@example.org'))
        other = api.Farm(name='Other Farm')
        db.add(other); db.flush()
        other_user = api.User(email='stranger@example.org',name='Stranger',
            password_hash=api.passwords.hash('stranger-password-123'),role='farmer')
        db.add(other_user); db.flush()
        db.add(api.Membership(user_id=other_user.id,farm_id=other.id,role='farmer'))
        db.commit()
    assert client.post('/api/auth/logout',headers=headers).status_code == 200
    session = client.post('/api/auth/login',json={'email':'stranger@example.org','password':'stranger-password-123'})
    assert session.status_code == 200
    other_headers={'X-CSRF-Token':session.json()['csrf_token']}
    url = path+f'/animals/{animal}/attachments/{attachment_id}/download'
    assert client.get(url).status_code == 404
    assert client.get(path+f'/animals/{animal}/attachments').status_code == 404
    assert client.post(path+f'/animals/{animal}/attachments',headers=other_headers,
       files={'file':('image.png',blob,'image/png')}).status_code == 404
    assert client.get('/api/farms').json()[0]['name'] == 'Other Farm'


def test_security_rate_limit_expired_recovery_and_integrity(environment):
    from datetime import timedelta
    from datetime import datetime, timezone
    client, Session, mailbox, root = environment
    headers, path = setup(client)
    invalid={'email':'owner@example.org','password':'incorrect-secret'}
    for _ in range(15):
        assert client.post('/api/auth/login',json=invalid).status_code == 401
    assert client.post('/api/auth/login',json=invalid).status_code == 429
    assert client.post('/api/auth/recovery/request',json={'email':'owner@example.org'}).status_code == 202
    token=mailbox[-1][1]
    with Session() as db:
        reset=db.scalar(select(api.PasswordReset))
        reset.expires_at=datetime.now(timezone.utc) - timedelta(seconds=30)
        db.commit()
    assert client.post('/api/auth/recovery/complete',json={'token':token,'password':'new-long-password'}).status_code == 400
    animal=client.post(path+'/animals',headers=headers,json={'name':'Oona','species':'sheep','tag':'SH3'}).json()['id']
    original=b'%PDF-1.6\nbody\n%%EOF'
    result=client.post(path+f'/animals/{animal}/attachments',headers=headers,
        files={'file':('report.pdf',original,'application/pdf')})
    assert result.status_code == 201
    attachment_id=result.json()['id']
    encrypted=root/'private'/f'{attachment_id}.enc'
    ciphertext=bytearray(encrypted.read_bytes());ciphertext[-3] ^= 0x80;encrypted.write_bytes(ciphertext)
    assert client.get(path+f'/animals/{animal}/attachments/{attachment_id}/download').status_code == 503
    assert client.get('/api/health').headers['x-content-type-options']=='nosniff'
    assert client.post('/api/auth/login',headers={'Origin':'https://malicious.example'},json=invalid).status_code == 403


def test_researcher_cannot_download_animal_evidence(environment):
    client, Session, _, _ = environment
    headers, path = setup(client)
    animal=client.post(path+'/animals',headers=headers,json={'name':'Coral','tag':'R1','species':'cattle'}).json()['id']
    pdf=b'%PDF-1.4\nPDF data\n%%EOF'
    upload=client.post(path+f'/animals/{animal}/attachments',headers=headers,
        files={'file':('lab.pdf',pdf,'application/pdf')})
    assert upload.status_code==201
    evidence=upload.json()['id']
    invite=client.post(path+'/members',headers=headers,json={'email':'researcher@example.org',
        'full_name':'Research Analyst','password':'a-secure-research-password','role':'researcher'})
    assert invite.status_code==201
    assert client.post('/api/auth/logout',headers=headers).status_code==200
    login=client.post('/api/auth/login',json={'email':'researcher@example.org','password':'a-secure-research-password'})
    assert login.status_code==200
    assert client.get(path+f'/animals/{animal}/attachments').status_code==403
    assert client.get(path+f'/animals/{animal}/attachments/{evidence}/download').status_code==403
    assert client.get(path+'/reports/csv').status_code==403
