#!/usr/bin/env python3
"""Verify local test API, select a USB device, restore port forwarding and launch Flutter."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import urllib.request
from release import ROOT, execute


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', help='ADB serial if multiple USB phones are attached')
    p.add_argument('--port', type=int, default=8000)
    a=p.parse_args()
    origin=f'http://127.0.0.1:{a.port}'
    try:
        with urllib.request.urlopen(origin+'/api/health', timeout=5) as r:
            health=json.load(r)
            if r.status!=200 or health.get('service')!='anirepro-api' or health.get('status')!='ok':raise ValueError('Unexpected API health response')
    except Exception as e:
        raise SystemExit(f'Local API unavailable: {e}. Start START_TEST_SERVER.command in a separate terminal first.')
    sdk=os.getenv('ANDROID_HOME') or os.getenv('ANDROID_SDK_ROOT')
    candidates=[shutil.which('adb'),str(Path(sdk)/'platform-tools'/('adb.exe' if os.name=='nt' else 'adb')) if sdk else None,str(Path.home()/'Library/Android/sdk/platform-tools/adb')]
    adb=next((x for x in candidates if x and Path(x).is_file()),None)
    if not adb:raise SystemExit('ADB not found. Set ANDROID_HOME to your Android SDK path.')
    output=subprocess.check_output([adb,'devices','-l'],text=True)
    print(output)
    phones=[line.split()[0] for line in output.splitlines()[1:] if len(line.split())>=2 and line.split()[1]=='device' and not line.startswith('emulator-') and ':' not in line.split()[0]]
    if a.device:
        if a.device not in phones:raise SystemExit('Requested physical device is not connected/authorized.')
        phone=a.device
    elif len(phones)==1:phone=phones[0]
    else:raise SystemExit('Connect and authorize exactly one USB phone, or pass --device SERIAL.')
    flutter=shutil.which('flutter')
    if not flutter:raise SystemExit('Flutter is not in PATH.')
    execute(sys.executable,ROOT/'tools/bootstrap.py','--check')
    execute(adb,'-s',phone,'reverse',f'tcp:{a.port}',f'tcp:{a.port}')
    forwards=subprocess.check_output([adb,'-s',phone,'reverse','--list'],text=True)
    if f'tcp:{a.port} tcp:{a.port}' not in forwards:raise SystemExit('USB port forwarding failed.')
    print(f'Use fictional test data only. Phone API: {origin}. Keep USB and test server connected.',flush=True)
    execute(flutter,'run','-d',phone,f'--dart-define=API_BASE_URL={origin}')
if __name__=='__main__':main()
