"""Adversarial acceptance checks for one-time farm team invitations and isolation."""
from datetime import datetime, timedelta, timezone
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app import main as api


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    engine = create_engine(f'sqlite:///{tmp_path / "team.db"}', connect_args={'check_same_thread': False})
    api.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    def get_session():
        with Session() as session:
            yield session
    api.app.dependency_overrides[api.get_db] = get_session
    try:
        with TestClient(api.app) as manager, TestClient(api.app) as member, TestClient(api.app) as outsider:
            yield manager, member, outsider, Session
    finally:
        api.app.dependency_overrides.pop(api.get_db, None)
        engine.dispose()


def owner(client, email, farm):
    result = client.post('/api/auth/register', json={'email': email, 'password': 'really-long-safe-password', 'full_name': 'A Manager', 'farm_name': farm})
    assert result.status_code == 201, result.text
    return result.json()['farm_id'], {'X-CSRF-Token': result.json()['csrf_token']}


def invite(client, farm_id, headers, email, role='farmer'):
    return client.post(f'/api/farms/{farm_id}/invitations', headers=headers,
                       json={'email': email, 'role': role})


def token_from(result):
    return result.json()['invitation_url'].split('token=')[-1]

def test_notifications_are_persisted_recipient_scoped_and_dismissible(env):
    manager, member, outsider, _ = env
    farm_id, manager_headers = owner(manager, 'notice-manager@example.org', 'Notice Farm')
    created = manager.post(f'/api/farms/{farm_id}/members', headers=manager_headers, json={
        'email':'notice-farmer@example.org','full_name':'Farm Worker','password':'farm-worker-long-password','role':'farmer'})
    assert created.status_code == 201, created.text
    login = member.post('/api/auth/login', json={'email':'notice-farmer@example.org','password':'farm-worker-long-password'})
    member_headers = {'X-CSRF-Token':login.json()['csrf_token']}
    animal = manager.post(f'/api/farms/{farm_id}/animals', headers=manager_headers,
        json={'name':'Daisy','species':'cattle','tag':'NOTICE-1'})
    assert animal.status_code == 201, animal.text
    inbox = member.get('/api/notifications')
    assert inbox.status_code == 200
    assert inbox.json()['unread_count'] == 1
    notice = inbox.json()['items'][0]
    assert notice['event_type'] == 'animal.created'
    assert notice['farm_name'] == 'Notice Farm'
    assert notice['href'] == f"/animals/{animal.json()['id']}"
    outsider_login = outsider.post('/api/auth/register', json={'email':'notice-outsider@example.org',
        'password':'outsider-long-safe-password','full_name':'Outsider','farm_name':'Other Farm'})
    outsider_headers={'X-CSRF-Token':outsider_login.json()['csrf_token']}
    assert outsider.patch(f"/api/notifications/{notice['id']}/read",headers=outsider_headers).status_code == 404
    assert outsider.delete(f"/api/notifications/{notice['id']}",headers=outsider_headers).status_code == 404
    assert member.patch(f"/api/notifications/{notice['id']}/read",headers=member_headers).status_code == 200
    assert member.get('/api/notifications/unread-count').json()['count'] == 0
    assert member.delete(f"/api/notifications/{notice['id']}",headers=member_headers).status_code == 200
    assert member.get('/api/notifications').json()['items'] == []


def test_farm_manager_invites_new_staff_once_and_preserves_farm_isolation(env):
    manager, staff, outsider, Session = env
    farm_id, csrf = owner(manager, 'manager@example.org', 'My Farm')
    other_id, _ = owner(outsider, 'outsider@example.org', 'Other Farm')
    assert invite(outsider, farm_id, {}, 'user@example.org').status_code in (403, 404)
    assert staff.get(f'/api/farms/{farm_id}/members').status_code == 401
    invited = invite(manager, farm_id, csrf, 'newvet@example.org', 'veterinarian')
    assert invited.status_code == 201, invited.text
    token = token_from(invited)
    with Session() as db:
        record = db.scalar(select(api.FarmInvitation))
        assert record.token_digest == hashlib.sha256(token.encode()).hexdigest()
        assert token not in record.token_digest
    preview = staff.get('/api/auth/invitations/preview', params={'token': token})
    assert preview.status_code == 200
    assert preview.json()['has_account'] is False
    assert preview.json()['farm_name'] == 'My Farm'
    assert preview.json()['role'] == 'veterinarian'
    joining = staff.post('/api/auth/invitations/accept', json={
        'token': token, 'full_name': 'Clinic Vet', 'password': 'new-vet-very-long-password'})
    assert joining.status_code == 200, joining.text
    assert staff.get('/api/farms').json()[0]['id'] == farm_id
    assert staff.get(f'/api/farms/{other_id}/animals').status_code == 404
    assert staff.post('/api/auth/invitations/accept', json={
        'token': token, 'full_name': 'Clinic Vet', 'password': 'new-vet-very-long-password'}).status_code == 400
    assert staff.get('/api/auth/invitations/preview', params={'token': token}).status_code == 400
    assert manager.get(f'/api/farms/{farm_id}/members').status_code == 200
    assert staff.get(f'/api/farms/{farm_id}/members').status_code == 403
    assert invite(staff, farm_id, {'X-CSRF-Token': joining.json()['csrf_token']}, 'another@example.org').status_code == 403
    with Session() as db:
        assert len(db.scalars(select(api.Membership).where(api.Membership.farm_id == farm_id)).all()) == 2
        assert db.scalar(select(api.Audit).where(api.Audit.action == 'invitation.accepted')) is not None


def test_existing_user_can_join_second_farm_without_recreating_password(env):
    first, second, _, Session = env
    farm1, csrf1 = owner(first, 'primary@example.org', 'Original')
    farm2, csrf2 = owner(second, 'secondary@example.org', 'Second')
    invited = invite(first, farm1, csrf1, 'secondary@example.org', 'researcher')
    token = token_from(invited)
    assert second.get('/api/auth/invitations/preview', params={'token': token}).json()['has_account']
    bad = second.post('/api/auth/invitations/accept', json={'token':token,'password':'wrong-password','full_name':''})
    assert bad.status_code == 401
    joined = second.post('/api/auth/invitations/accept', json={'token':token,'password':'really-long-safe-password','full_name':''})
    assert joined.status_code == 200, joined.text
    farms = second.get('/api/farms').json()
    assert {x['id'] for x in farms} == {farm1, farm2}
    research_farm = next(f for f in farms if f['id']==farm1)
    assert research_farm['role'] == 'researcher'
    assert research_farm['permissions'] == ['farm.view']
    assert second.get(f'/api/farms/{farm1}/animals').status_code == 403
    assert second.get(f'/api/farms/{farm1}/events').status_code == 403
    assert second.get(f'/api/farms/{farm1}/summary').status_code == 403
    assert second.post(f'/api/farms/{farm1}/animals', headers={'X-CSRF-Token': joined.json()['csrf_token']},
        json={'name':'No Write','species':'cattle','tag':'no-write'}).status_code == 403
    with Session() as db:
        users = db.scalars(select(api.User).where(api.User.email=='secondary@example.org')).all()
        assert len(users) == 1


def test_effective_role_is_membership_scoped_and_removal_preserves_other_farm(env):
    first, second, _, Session = env
    farm_a, csrf_a = owner(first, 'manager-a@example.org', 'Farm A')
    farm_b, _ = owner(second, 'member@example.org', 'Farm B')
    invitation = invite(first, farm_a, csrf_a, 'member@example.org', 'veterinarian')
    joined = second.post('/api/auth/invitations/accept', json={
        'token': token_from(invitation), 'password': 'really-long-safe-password', 'full_name': 'Vet Member'})
    assert joined.status_code == 200
    farms = second.get('/api/auth/session').json()['user']['farms']
    assert {row['id']: row['role'] for row in farms} == {farm_a: 'veterinarian', farm_b: 'farm_manager'}
    assert second.get(f'/api/farms/{farm_a}/animals').status_code == 200
    assert second.get(f'/api/farms/{farm_b}/members').status_code == 200
    rows = first.get(f'/api/farms/{farm_a}/members').json()
    vet = next(row for row in rows if row['email'] == 'member@example.org')
    changed = first.patch(f"/api/farms/{farm_a}/members/{vet['id']}", headers=csrf_a,
        json={'role':'farmer'})
    assert changed.status_code == 200
    refreshed_roles = {row['id']:row['role'] for row in second.get('/api/auth/session').json()['user']['farms']}
    assert refreshed_roles[farm_a] == 'farmer'
    assert refreshed_roles[farm_b] == 'farm_manager'
    with Session() as db:
        account = db.scalar(select(api.User).where(api.User.email == 'member@example.org'))
        assert account.role == 'farm_manager'  # a farm role change never rewrites the global account field
    removed = first.delete(f"/api/farms/{farm_a}/members/{vet['id']}", headers=csrf_a)
    assert removed.status_code == 200, removed.text
    assert second.get(f'/api/farms/{farm_a}/animals').status_code == 404
    assert second.get(f'/api/farms/{farm_b}/members').status_code == 200
    with Session() as db:
        account = db.scalar(select(api.User).where(api.User.email == 'member@example.org'))
        assert account is not None
        assert db.get(api.Membership, (account.id, farm_b)) is not None
        assert db.get(api.Membership, (account.id, farm_a)) is None


def test_manager_can_revoke_pending_invitation_but_cannot_remove_last_manager(env):
    manager, _, _, _ = env
    farm_id, csrf = owner(manager, 'only-manager@example.org', 'Farm')
    created = invite(manager, farm_id, csrf, 'pending@example.org')
    assert created.status_code == 201
    pending_id = manager.get(f'/api/farms/{farm_id}/invitations').json()[0]['id']
    assert manager.get(f'/api/farms/{farm_id}/invitations').json()[0]['id'] == pending_id
    assert manager.delete(f'/api/farms/{farm_id}/invitations/{pending_id}', headers=csrf).status_code == 200
    assert manager.get(f'/api/farms/{farm_id}/invitations').json() == []
    manager_id = manager.get(f'/api/farms/{farm_id}/members').json()[0]['id']
    assert manager.delete(f'/api/farms/{farm_id}/members/{manager_id}', headers=csrf).status_code == 409


def test_invite_requires_manager_csrf_and_rejects_expired_or_replaced(env):
    manager, staff, outsider, Session = env
    farm_id, csrf = owner(manager, 'owner@example.org', 'Farm')
    assert invite(manager, farm_id, {}, 'someone@example.org').status_code == 403
    assert invite(manager, farm_id, csrf, 'someone@example.org', 'farm_manager').status_code == 422
    first = invite(manager, farm_id, csrf, 'someone@example.org')
    assert first.status_code == 201
    first_token = token_from(first)
    next_invite = invite(manager, farm_id, csrf, 'someone@example.org')
    assert next_invite.status_code == 201
    assert staff.get('/api/auth/invitations/preview', params={'token':first_token}).status_code == 400
    next_token = token_from(next_invite)
    with Session() as db:
        row = db.scalar(select(api.FarmInvitation).where(api.FarmInvitation.token_digest==hashlib.sha256(next_token.encode()).hexdigest()))
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert staff.get('/api/auth/invitations/preview', params={'token':next_token}).status_code == 400
    assert staff.post('/api/auth/invitations/accept', json={'token':next_token,'password':'long-suitable-password','full_name':'Anyone'}).status_code == 400


def test_production_invitation_email_does_not_expose_secret(env, monkeypatch):
    manager, _, _, Session = env
    farm_id, csrf = owner(manager, 'mail-manager@example.org', 'Confidential Farm')
    sent = []
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('INVITE_URL_BASE','https://farm.example.org/join?token=')
    monkeypatch.setattr(api, 'deliver_invitation', lambda email, farm_name, role, link: sent.append((email, farm_name, role, link)))
    reply = invite(manager, farm_id, csrf, 'new-staff@example.org', 'farmer')
    assert reply.status_code == 201, reply.text
    assert 'invitation_url' not in reply.json()
    assert len(sent) == 1
    assert sent[0][0] == 'new-staff@example.org'
    assert sent[0][1] == 'Confidential Farm'
    assert sent[0][3].startswith('https://farm.example.org/join?token=')
    assert len(sent[0][3].split('token=')[-1]) > 40
    with Session() as db:
        stored = db.scalar(select(api.FarmInvitation))
        assert stored.token_digest != sent[0][3].split('token=')[-1]


def test_animal_creation_is_manager_and_farmer_only(env):
    manager, _, _, _ = env
    farm_id, csrf = owner(manager, 'animal-owner@example.org', 'Animal Roles Farm')
    mother = manager.post(f'/api/farms/{farm_id}/animals', headers=csrf,
        json={'name':'Mother','species':'cattle','tag':'M-1'})
    assert mother.status_code == 201, mother.text
    assert manager.post(f'/api/farms/{farm_id}/animals', headers=csrf,
        json={'name':'Manager Animal','species':'cattle','tag':'M-2'}).status_code == 201

    for role, allowed in [('farmer', True), ('veterinarian', False), ('breeder', False)]:
        email = f'{role}@animal-roles.example.org'
        invitation = invite(manager, farm_id, csrf, email, role)
        assert invitation.status_code == 201, invitation.text
        with TestClient(api.app) as member:
            joined = member.post('/api/auth/invitations/accept', json={
                'token': token_from(invitation), 'password':'really-long-safe-password', 'full_name':role.title()})
            assert joined.status_code == 200, joined.text
            headers = {'X-CSRF-Token':joined.json()['csrf_token']}
            permissions = next(row['permissions'] for row in member.get('/api/farms').json() if row['id']==farm_id)
            assert ('animals.create' in permissions) is allowed
            created = member.post(f'/api/farms/{farm_id}/animals', headers=headers,
                json={'name':f'{role.title()} Animal','species':'goat','tag':f'{role.upper()}-1'})
            assert created.status_code == (201 if allowed else 403), created.text
            if allowed:
                listed = member.get(f'/api/farms/{farm_id}/animals')
                assert listed.status_code == 200 and any(row['id']==created.json()['id'] for row in listed.json())
            if not allowed:
                birth = {'category':'birth','kind':'delivery','status':'observed',
                    'occurred_at':'2026-11-14T10:00:00Z','payload':{'delivery_type':'unassisted','outcome':'live_birth','offspring_tag':f'{role.upper()}-CALF'}}
                reply = member.post(f"/api/farms/{farm_id}/animals/{mother.json()['id']}/events",
                    headers=headers, json=birth)
                assert reply.status_code == 403, reply.text
