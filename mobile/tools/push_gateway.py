#!/usr/bin/env python3
"""Optional single-server FCM gateway. Run from backend with PYTHONPATH=../mobile/tools.
Shares core API authentication/permissions, but keeps tokens in a separate private DB.
No Firebase credentials belong in the mobile package.
"""
import os
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from pydantic import BaseModel, Field
import jwt
from app import main as core

app=core.app

@contextmanager
def store():
    path=Path(os.environ.get('ANIREPRO_PUSH_DB','./private/push.sqlite3')).resolve()
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Create owner-only file before sqlite opens it.
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600);os.close(fd)
    if os.name!='nt':os.chmod(path,0o600)
    con=sqlite3.connect(path,timeout=20)
    con.row_factory=sqlite3.Row
    try:
        con.execute('CREATE TABLE IF NOT EXISTS devices(token TEXT PRIMARY KEY, user_id TEXT NOT NULL, version INTEGER NOT NULL, expires REAL NOT NULL, since REAL NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS delivered(token TEXT NOT NULL, notification_id TEXT NOT NULL, PRIMARY KEY(token,notification_id))')
        yield con
        con.commit()
    finally:con.close()

class Registration(BaseModel):
    token:str=Field(min_length=20,max_length=4096)
    previous_token:str|None=Field(default=None,max_length=4096)

def remove(con,token):
    con.execute('DELETE FROM delivered WHERE token=?',(token,))
    con.execute('DELETE FROM devices WHERE token=?',(token,))

@app.post('/api/mobile/push/register')
def register(data:Registration,request:Request,user:core.Auth):
    claims=jwt.decode(request.cookies['anirepro_session'],core.SECRET,algorithms=['HS256'])
    now=time.time();expires=min(float(claims['exp']),now+8*3600)
    if expires<=now:raise HTTPException(401,'Session expired')
    with store() as con:
        con.execute('BEGIN IMMEDIATE')
        if data.previous_token and data.previous_token!=data.token:
            prev=con.execute('SELECT user_id FROM devices WHERE token=?',(data.previous_token,)).fetchone()
            if prev and prev['user_id']==user.id:remove(con,data.previous_token)
        old=con.execute('SELECT * FROM devices WHERE token=?',(data.token,)).fetchone()
        since=now
        if old:
            if old['user_id']==user.id and old['expires']>now and old['version']==user.session_version:since=old['since']
            else:remove(con,data.token)
        count=con.execute('SELECT count(*) FROM devices WHERE user_id=? AND expires>? AND token!=?',(user.id,now,data.token)).fetchone()[0]
        if count>=10:raise HTTPException(429,'Too many registered devices')
        con.execute('INSERT OR REPLACE INTO devices VALUES(?,?,?,?,?)',(data.token,user.id,user.session_version,expires,since))
    return {'registered':True,'expires_at':datetime.fromtimestamp(expires,timezone.utc).isoformat()}

@app.post('/api/mobile/push/unregister')
def unregister(data:Registration,user:core.Auth):
    with store() as con:
        con.execute('BEGIN IMMEDIATE')
        old=con.execute('SELECT user_id FROM devices WHERE token=?',(data.token,)).fetchone()
        if old and old['user_id']==user.id:remove(con,data.token)
    return {'registered':False}

def epoch(dt):
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).timestamp()

def scan(send):
    """One worker only. Recheck auth before each generic push. Best effort, no token logging."""
    now=time.time()
    with store() as con:
        con.execute('BEGIN IMMEDIATE')
        for r in con.execute('SELECT token FROM devices WHERE expires<=?',(now,)).fetchall():remove(con,r['token'])
        devices=con.execute('SELECT * FROM devices').fetchall()
    for d in devices:
        with core.SessionLocal() as db:
            user=db.get(core.User,d['user_id'])
            if not user or not user.active or user.session_version!=d['version']:
                with store() as con:remove(con,d['token'])
                continue
            for item in core.notification_visible_query(db,user.id):
                n=item[0] if isinstance(item,tuple) else item
                if n.read_at is not None or epoch(n.created_at)<d['since']:continue
                # Claim first: at-most-once attempt, avoids repeats on uncertain FCM response.
                # The authoritative inbox always retains the real notification.
                with store() as con:
                    con.execute('BEGIN IMMEDIATE')
                    live=con.execute('SELECT * FROM devices WHERE token=?',(d['token'],)).fetchone()
                    if not live or live['user_id']!=d['user_id'] or live['since']!=d['since'] or live['expires']<=time.time():break
                    claimed=con.execute('INSERT OR IGNORE INTO delivered VALUES(?,?)',(d['token'],n.id)).rowcount
                if claimed:
                    try:send(d['token'])
                    except Exception as e:print('Push attempt failed:',type(e).__name__,flush=True)

def main():
    import firebase_admin
    from firebase_admin import messaging
    firebase_admin.initialize_app()
    def send(token):
        messaging.send(messaging.Message(token=token,notification=messaging.Notification(title='AniRepro 360',body='New farm activity. Open the app to review.'),android=messaging.AndroidConfig(ttl=timedelta(minutes=5)),apns=messaging.APNSConfig(headers={'apns-expiration':str(int(time.time()+300))})))
    print('FCM worker running; generic alerts only.',flush=True)
    while True:
        try:scan(send)
        except Exception as e:print('Push scan failed:',type(e).__name__,flush=True)
        time.sleep(30)
if __name__=='__main__':main()
