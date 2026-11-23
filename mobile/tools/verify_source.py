#!/usr/bin/env python3
"""Static packaging and native configuration fixture verification, not Dart compilation."""
import ast
from pathlib import Path
import plistlib
import re
import tempfile
import xml.etree.ElementTree as ET
import bootstrap
import configure_notifications
ROOT=Path(__file__).resolve().parents[1]
NS='{http://schemas.android.com/apk/res/android}'

def native_fixture():
    with tempfile.TemporaryDirectory() as directory:
        r=Path(directory)
        def write(path,content):
            p=r/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        write('android/app/src/main/AndroidManifest.xml','<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="old"/></manifest>')
        write('android/app/src/debug/AndroidManifest.xml','<manifest xmlns:android="http://schemas.android.com/apk/res/android"/>')
        write('android/app/build.gradle.kts','android {\n compileSdk = flutter.compileSdkVersion\n compileOptions {\n }\n defaultConfig {\n minSdk = flutter.minSdkVersion\n targetSdk = flutter.targetSdkVersion\n }\n}\n')
        write('ios/Runner/Info.plist',plistlib.dumps({'CFBundleName':'old'}).decode())
        write('ios/Runner/AppDelegate.swift','import Flutter\nimport UIKit\nclass AppDelegate: FlutterAppDelegate {\n override func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {\n return super.application(application, didFinishLaunchingWithOptions: launchOptions)\n }\n}')
        write('ios/Runner.xcodeproj/project.pbxproj','\n'.join(f'{i:024X} /* {name} */ = {{\n isa = XCBuildConfiguration;\n buildSettings = {{\n INFOPLIST_FILE = Runner/Info.plist;\n IPHONEOS_DEPLOYMENT_TARGET = 12.0;\n }};\n name = {name};\n }};' for i,name in enumerate(['Debug','Release','Profile'],1)))
        write('ios/Podfile',"# platform :ios, '12.0'\n")
        old_a,old_b=bootstrap.ROOT,configure_notifications.ROOT
        try:
            bootstrap.ROOT=configure_notifications.ROOT=r
            for _ in range(2):
                bootstrap.config_android();bootstrap.config_ios();configure_notifications.configure()
            main=ET.parse(r/'android/app/src/main/AndroidManifest.xml').getroot();app=main.find('application')
            assert app.get(NS+'usesCleartextTraffic')=='false' and app.get(NS+'allowBackup')=='false'
            assert len(main.findall('uses-permission'))==3
            assert len(app.findall('receiver'))==2
            assert ET.parse(r/'android/app/src/debug/AndroidManifest.xml').getroot().find('application').get(NS+'usesCleartextTraffic')=='true'
            gradle=(r/'android/app/build.gradle.kts').read_text();assert gradle.count('coreLibraryDesugaring(')==1 and 'maxOf(flutter.compileSdkVersion, 36)' in gradle and 'maxOf(flutter.minSdkVersion, 23)' in gradle and 'maxOf(flutter.targetSdkVersion, 36)' in gradle
            ios=(r/'ios/Runner.xcodeproj/project.pbxproj').read_text();assert ios.count('CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;')==3 and ios.count('INFOPLIST_FILE = Runner/Info-Debug.plist;')==1
            assert '12.0' not in ios and "'13.0'" in (r/'ios/Podfile').read_text()
            assert not plistlib.loads((r/'ios/Runner/Info.plist').read_bytes()).get('NSAppTransportSecurity')
            assert plistlib.loads((r/'ios/Runner/Info-Debug.plist').read_bytes())['NSAppTransportSecurity']['NSAllowsArbitraryLoads']
            assert (r/'ios/Runner/AppDelegate.swift').read_text().count('UNUserNotificationCenter.current().delegate')==1
        finally:bootstrap.ROOT,configure_notifications.ROOT=old_a,old_b

def main():
    dart=list((ROOT/'lib').rglob('*.dart'))+list((ROOT/'test').rglob('*.dart'))
    for p in dart:
        for name in re.findall(r"(?:import|export|part)\s+['\"]([^'\"]+)['\"]",p.read_text()):
            if name.startswith('package:anirepro360_mobile/'):
                resolved=ROOT/'lib'/name.removeprefix('package:anirepro360_mobile/')
            elif ':' not in name:resolved=p.parent/name
            else:continue
            assert resolved.is_file(),(p,name)
    for p in list((ROOT/'server').rglob('*.py'))+list((ROOT/'tools').rglob('*.py')):
        ast.parse(p.read_text(),filename=str(p))
    for name in ['logo.png','app_icon.png']:
        assert (ROOT/'assets'/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    native_fixture()
    print(f'PASS: {len(dart)} Dart source/test import checks, Python syntax, PNG headers, Android/iOS configuration fixtures (including repeat execution).')
if __name__=='__main__': main()
