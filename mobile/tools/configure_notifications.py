#!/usr/bin/env python3
"""Idempotently configure existing Flutter native projects for local reminders."""
from pathlib import Path
import plistlib
import re
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
NS='http://schemas.android.com/apk/res/android'; A='{'+NS+'}'
ET.register_namespace('android',NS)

def configure():
    manifest=ROOT/'android/app/src/main/AndroidManifest.xml'
    gradle=ROOT/'android/app/build.gradle.kts'
    plist=ROOT/'ios/Runner/Info.plist'
    if not all(p.exists() for p in (manifest,gradle,plist)):
        raise RuntimeError('Expected Flutter Kotlin DSL Android and iOS projects. Generate them using setup.sh or follow docs/UPDATE_1_4.md.')
    text=gradle.read_text()
    if 'isCoreLibraryDesugaringEnabled = true' not in text:
        if 'compileOptions {' not in text: raise RuntimeError('Unexpected Gradle project; configure desugaring manually.')
        text=text.replace('compileOptions {','compileOptions {\n        isCoreLibraryDesugaringEnabled = true',1)
    if 'coreLibraryDesugaring(' not in text:
        if re.search(r'^dependencies\s*\{',text,re.M):text=re.sub(r'^dependencies\s*\{','dependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")',text,count=1,flags=re.M)
        else:text+='\n\ndependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}\n'
    text=text.replace('compileSdk = flutter.compileSdkVersion','compileSdk = maxOf(flutter.compileSdkVersion, 35)')
    tree=ET.parse(manifest);root=tree.getroot();app=root.find('application')
    if app is None:raise RuntimeError('No Android application manifest')
    for name in ('android.permission.POST_NOTIFICATIONS','android.permission.RECEIVE_BOOT_COMPLETED'):
        if not any(e.get(A+'name')==name for e in root.findall('uses-permission')):root.insert(0,ET.Element('uses-permission',{A+'name':name}))
    base='com.dexterous.flutterlocalnotifications.'
    for name,actions in [('ScheduledNotificationReceiver',()),('ScheduledNotificationBootReceiver',('android.intent.action.BOOT_COMPLETED','android.intent.action.MY_PACKAGE_REPLACED','android.intent.action.QUICKBOOT_POWERON','com.htc.intent.action.QUICKBOOT_POWERON'))]:
        if not any(r.get(A+'name')==base+name for r in app.findall('receiver')):
            receiver=ET.SubElement(app,'receiver',{A+'name':base+name,A+'exported':'false'})
            if actions:
                f=ET.SubElement(receiver,'intent-filter')
                for action in actions:ET.SubElement(f,'action',{A+'name':action})
    for name,value in [('firebase_messaging_auto_init_enabled','false'),('firebase_analytics_collection_enabled','false')]:
        if not any(m.get(A+'name')==name for m in app.findall('meta-data')):ET.SubElement(app,'meta-data',{A+'name':name,A+'value':value})
    icon=manifest.parent/'res/drawable/ic_stat_anirepro.xml';icon.parent.mkdir(parents=True,exist_ok=True)
    icon.write_text('<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M12,22a2,2 0,0 0,2 -2h-4a2,2 0,0 0,2 2M18,16v-5a6,6 0,0 0,-5 -5.92V4a1,1 0,0 0,-2 0v1.08A6,6 0,0 0,6 11v5l-2,2v1h16v-1z"/></vector>')
    gradle.write_text(text);tree.write(manifest,encoding='unicode',xml_declaration=True)
    for p in (plist,plist.with_name('Info-Debug.plist')):
        if p.exists():
            data=plistlib.loads(p.read_bytes());data['FirebaseMessagingAutoInitEnabled']=False;data['FIREBASE_ANALYTICS_COLLECTION_ENABLED']=False;p.write_bytes(plistlib.dumps(data))
    # Local notifications foreground delegate, preserving existing Flutter template.
    delegate=plist.parent/'AppDelegate.swift'
    if delegate.exists():
        source=delegate.read_text()
        if 'import UserNotifications' not in source:source='import UserNotifications\n'+source
        if 'UNUserNotificationCenter.current().delegate' not in source:
            pattern=r'(didFinishLaunchingWithOptions\s+launchOptions:\s*\[UIApplication\.LaunchOptionsKey:\s*Any\]\?\s*\)\s*->\s*Bool\s*\{)'
            source,n=re.subn(pattern,r'\1\n    UNUserNotificationCenter.current().delegate = self',source,count=1)
            if not n:raise RuntimeError('Unknown iOS AppDelegate template; set notification delegate manually.')
        delegate.write_text(source)
    print('Local notification platform configuration updated. Firebase provisioning is separate.')
if __name__=='__main__':configure()
