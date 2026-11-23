#!/usr/bin/env python3
"""One automated verification/build entry point. Never migrates an existing user database."""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVER=ROOT/'server'

def execute(*args,cwd=ROOT,env=None):
    print('>',*map(str,args),flush=True)
    args=list(map(str,args))
    if os.name=='nt' and args[0].lower().endswith(('.bat','.cmd')):args=['cmd','/c',*args]
    subprocess.run(args,cwd=cwd,env=env,check=True)

def verify_backend(python):
    with tempfile.TemporaryDirectory(prefix='anirepro-verification-') as folder:
        root=Path(folder)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SMTP_','SOCIAL_','GOOGLE_OAUTH_','APPLE_OAUTH_','ANIREPRO_PUSH_','GOOGLE_APPLICATION_CREDENTIALS','PYTHONPATH','DATABASE_URL','SESSION_SECRET','FILE_ENCRYPTION_KEY','ATTACHMENTS_DIR','APP_ENV','ALLOW_INITIAL_SETUP','RESET_URL_BASE','INVITE_URL_BASE','CORS_ORIGINS'))}
        env.update(DATABASE_URL='sqlite:///'+(root/'test.db').as_posix(),APP_ENV='development',SESSION_SECRET='disposable-build-check-not-for-production-1234567890',ATTACHMENTS_DIR=str(root/'attachments'))
        execute(python,'-m','alembic','upgrade','head',cwd=SERVER,env=env)
        execute(python,'-m','alembic','current',cwd=SERVER,env=env)
        execute(python,ROOT/'tools/test_username_auth.py',cwd=SERVER,env=env)
        execute(python,'-m','pytest','-q','tests',cwd=SERVER,env=env)
        execute(python,ROOT/'tools/test_sync_contract.py',SERVER,env=env)
        execute(python,ROOT/'tools/test_push_gateway.py',SERVER,env=env)

def backend_python(install):
    if not install:return sys.executable
    # Isolated verification environment, never the original app's virtualenv.
    venv=ROOT/'.release-venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():execute(sys.executable,'-m','venv',venv)
    execute(python,'-m','pip','install','-r',SERVER/'requirements.txt')
    return python

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',choices=['source','android','ios','all'],default='source')
    p.add_argument('--install-backend-deps',action='store_true')
    p.add_argument('--skip-backend',action='store_true',help='Use only for a separate native CI job; backend job must run independently.')
    args=p.parse_args()
    execute(sys.executable,ROOT/'tools/verify_source.py')
    if not args.skip_backend:verify_backend(backend_python(args.install_backend_deps))
    if args.target=='source':print('Source/backend verification complete. No native build attempted.');return
    flutter=shutil.which('flutter')
    if not flutter:raise SystemExit('Flutter SDK is unavailable. Native build was not performed.')
    if args.target in ('ios','all') and platform.system()!='Darwin':raise SystemExit('iOS native build needs macOS and Xcode. Choose android on this host.')
    # Bootstrap generates official Flutter native templates and configures both platforms,
    # then resolves dependencies, analyzes and runs all Dart tests before any build.
    execute(sys.executable,ROOT/'tools/bootstrap.py','--check')
    if args.target in ('android','all'):
        execute(flutter,'build','apk','--debug')
        print('Android debug APK:',ROOT/'build/app/outputs/flutter-apk/app-debug.apk')
    if args.target in ('ios','all'):
        execute(flutter,'build','ios','--release','--no-codesign')
        print('Unsigned iOS device build (not installable until signed):',ROOT/'build/ios/iphoneos/Runner.app')
    print('Build tasks completed. Physical-device and signed release acceptance are separate.')
if __name__=='__main__':main()
