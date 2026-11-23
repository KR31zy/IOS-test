#!/usr/bin/env python3
"""Start isolated development-only server bundled with this source release."""
import argparse
import base64
import os
from pathlib import Path
import secrets
import subprocess
import sys
from release import ROOT, SERVER, backend_python

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lan',action='store_true',help='Explicitly allow trusted LAN debug-device access. No real clinical data.');p.add_argument('--port',type=int,default=8000);a=p.parse_args()
    python=backend_python(True);d=ROOT/'.runtime';d.mkdir(mode=0o700,exist_ok=True)
    def secret(name,make):
        f=d/name
        if not f.exists():
            with os.fdopen(os.open(f,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as handle:handle.write(make())
        return f.read_text().strip()
    env={k:v for k,v in os.environ.items() if not k.startswith(('SMTP_','SOCIAL_','GOOGLE_OAUTH_','APPLE_OAUTH_','DATABASE_URL','SESSION_SECRET','FILE_ENCRYPTION_KEY','ATTACHMENTS_DIR','APP_ENV','ALLOW_INITIAL_SETUP','RESET_URL_BASE','INVITE_URL_BASE','CORS_ORIGINS','PYTHONPATH'))}
    env.update(DATABASE_URL='sqlite:///'+(d/'test.db').as_posix(),APP_ENV='development',SESSION_SECRET=secret('session.secret',lambda:secrets.token_urlsafe(48)),FILE_ENCRYPTION_KEY=secret('attachments.secret',lambda:base64.b64encode(secrets.token_bytes(32)).decode()),ATTACHMENTS_DIR=str(d/'attachments'),CORS_ORIGINS='http://localhost:8080,http://127.0.0.1:8080')
    subprocess.run([str(python),'-m','alembic','upgrade','head'],cwd=SERVER,env=env,check=True)
    print('ISOLATED TEST SERVER: fresh test accounts; no connection to your existing farm database.',flush=True)
    if a.lan:print('LAN debug only. Do not enter real clinical data or expose port to internet.',flush=True)
    subprocess.run([str(python),'-m','uvicorn','app.main:app','--host','0.0.0.0' if a.lan else '127.0.0.1','--port',str(a.port)],cwd=SERVER,env=env,check=True)
if __name__=='__main__':main()
