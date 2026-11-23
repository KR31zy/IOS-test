#!/usr/bin/env python3
"""Build a signed Android App Bundle only with an explicitly verified HTTPS origin and upload key."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
import urllib.request
from release import ROOT, execute


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--api',required=True,help='Public production HTTPS API origin')
    a=p.parse_args();u=urlsplit(a.api)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment or u.hostname in ('localhost','127.0.0.1','10.0.2.2','::1'):
        raise SystemExit('Use a publicly reachable HTTPS origin, without a path or credentials.')
    origin=a.api.rstrip('/')
    with urllib.request.urlopen(origin+'/api/health',timeout=10) as r:
        if r.url!=origin+'/api/health' or r.status!=200 or json.load(r)!={'status':'ok','service':'anirepro-api'}:raise SystemExit('Unexpected production API health response.')
    keyfile=ROOT/'android/key.properties'
    if not keyfile.is_file():raise SystemExit('Missing android/key.properties. Supply your private upload keystore properties; see docs/PUBLISH_2_2.md.')
    for k in ('storeFile','storePassword','keyAlias','keyPassword'):
        if not re.search(r'^'+k+r'\s*=\s*\S+',keyfile.read_text(),re.M):raise SystemExit('Missing signing property: '+k)
    execute(sys.executable,ROOT/'tools/bootstrap.py','--check')
    gradle=ROOT/'android/app/build.gradle.kts'
    text=gradle.read_text()
    if 'signingConfigs.getByName("release")' not in text:
        if 'signingConfigs.getByName("debug")' not in text or 'android {' not in text:raise SystemExit('Unknown Gradle signing template. Configure a release signing config manually.')
        text='import java.util.Properties\n'+text
        text=text.replace('android {','''val uploadProperties = Properties().apply {
    rootProject.file("key.properties").inputStream().use { load(it) }
}
android {
    signingConfigs {
        create("release") {
            keyAlias = uploadProperties.getProperty("keyAlias")
            keyPassword = uploadProperties.getProperty("keyPassword")
            storeFile = rootProject.file(uploadProperties.getProperty("storeFile"))
            storePassword = uploadProperties.getProperty("storePassword")
        }
    }''',1).replace('signingConfigs.getByName("debug")','signingConfigs.getByName("release")')
        gradle.write_text(text)
    flutter=shutil.which('flutter')
    if not flutter:raise SystemExit('Flutter unavailable.')
    execute(flutter,'build','appbundle','--release',f'--dart-define=API_BASE_URL={origin}')
    print('Signed release candidate:',ROOT/'build/app/outputs/bundle/release/app-release.aab')
    print('Do not publish until the physical-device, deployment, policy and review gates in docs/PUBLISH_2_2.md pass.')
if __name__=='__main__':main()
