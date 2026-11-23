#!/usr/bin/env python3
"""Generate native projects using the locally installed Flutter SDK; never replace lib/."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
ANDROID='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',ANDROID)
TOOLS='http://schemas.android.com/tools'
ET.register_namespace('tools',TOOLS)
def run(*args,cwd=ROOT):
    print('>',*args,flush=True)
    if os.name=='nt' and str(args[0]).lower().endswith('.bat'):
        subprocess.run(['cmd','/c',*map(str,args)],cwd=cwd,check=True)
    else:subprocess.run(list(map(str,args)),cwd=cwd,check=True)

def config_android():
    main=ROOT/'android/app/src/main/AndroidManifest.xml'
    tree=ET.parse(main);root=tree.getroot();app=root.find('application');app.set('{'+ANDROID+'}label','AniRepro 360');app.set('{'+ANDROID+'}allowBackup','false');app.set('{'+ANDROID+'}usesCleartextTraffic','false')
    if not any(x.get('{'+ANDROID+'}name')=='android.permission.INTERNET' for x in root.findall('uses-permission')):
        root.insert(0,ET.Element('uses-permission',{'{'+ANDROID+'}name':'android.permission.INTERNET'}))
    tree.write(main,encoding='unicode',xml_declaration=True)
    debug=ROOT/'android/app/src/debug/AndroidManifest.xml';debug.parent.mkdir(parents=True,exist_ok=True)
    tree=ET.parse(debug) if debug.exists() else ET.ElementTree(ET.Element('manifest'));root=tree.getroot();app=root.find('application')
    if app is None:app=ET.SubElement(root,'application')
    app.set('{'+ANDROID+'}usesCleartextTraffic','true');replace=app.get('{'+TOOLS+'}replace','').split(',');replace=[x.strip() for x in replace if x.strip()];
    if 'android:usesCleartextTraffic' not in replace:replace.append('android:usesCleartextTraffic')
    app.set('{'+TOOLS+'}replace',','.join(replace));tree.write(debug,encoding='unicode',xml_declaration=True)
    # Release builds never receive the debug HTTP opt-in.
    p=ROOT/'android/app/build.gradle.kts'
    if p.exists():
        text=p.read_text();text=text.replace('minSdk = flutter.minSdkVersion','minSdk = maxOf(flutter.minSdkVersion, 23)');text=text.replace('compileSdk = flutter.compileSdkVersion','compileSdk = maxOf(flutter.compileSdkVersion, 36)').replace('targetSdk = flutter.targetSdkVersion','targetSdk = maxOf(flutter.targetSdkVersion, 36)');p.write_text(text)

def config_ios():
    runner=ROOT/'ios/Runner'; plist=runner/'Info.plist'
    data=plistlib.loads(plist.read_bytes());data['CFBundleDisplayName']='AniRepro 360';data['CFBundleName']='AniRepro 360'
    plist.write_bytes(plistlib.dumps(data));debug=dict(data);debug['NSAppTransportSecurity']={'NSAllowsArbitraryLoads':True};debug['NSLocalNetworkUsageDescription']='Connect to your local development farm server.'
    (runner/'Info-Debug.plist').write_bytes(plistlib.dumps(debug))
    ent=runner/'Runner.entitlements'; rights=plistlib.loads(ent.read_bytes()) if ent.exists() else {};groups=rights.setdefault('keychain-access-groups',[]);group='$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)'
    if group not in groups:groups.append(group)
    ent.write_bytes(plistlib.dumps(rights))
    project=ROOT/'ios/Runner.xcodeproj/project.pbxproj';text=project.read_text()
    # Match XCBuildConfiguration blocks with Runner's plist, excluding RunnerTests.
    pattern=r'([A-F0-9]+ /\* (Debug|Release|Profile) \*/ = \{\s*isa = XCBuildConfiguration;\s*.*?\n\s*name = \2;\s*\};)'
    def patch(m):
        block=m.group(0)
        if 'INFOPLIST_FILE = Runner/Info.plist;' not in block and 'INFOPLIST_FILE = Runner/Info-Debug.plist;' not in block:return block
        if 'CODE_SIGN_ENTITLEMENTS =' not in block:
            block=block.replace('INFOPLIST_FILE =', 'CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;\n\t\t\t\tINFOPLIST_FILE =',1)
        block=re.sub(r'INFOPLIST_FILE = Runner/Info(?:-Debug)?\.plist;', 'INFOPLIST_FILE = '+('Runner/Info-Debug.plist' if m.group(2)=='Debug' else 'Runner/Info.plist')+';',block)
        return block
    new=re.sub(pattern,patch,text,flags=re.S)
    if 'Runner/Info-Debug.plist' not in new or new.count('CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;')<3:
        raise RuntimeError('Unexpected Xcode template. Configure Debug plist and Runner keychain entitlements manually; see docs/SETUP.md.')
    # Firebase and local notification dependencies require at least iOS 13.
    new=re.sub(r'IPHONEOS_DEPLOYMENT_TARGET = (\d+(?:\.\d+)?);',lambda m: 'IPHONEOS_DEPLOYMENT_TARGET = '+('13.0' if float(m.group(1))<13 else m.group(1))+';',new)
    project.write_text(new)
    podfile=ROOT/'ios/Podfile'
    if podfile.exists():
        source=podfile.read_text();source=re.sub(r'(?m)^\s*#?\s*platform :ios, ["\']([0-9.]+)["\']',lambda m: "platform :ios, '"+('13.0' if float(m.group(1))<13 else m.group(1))+"'",source,count=1);podfile.write_text(source)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skip-icons',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    flutter=shutil.which('flutter')
    if not flutter:raise SystemExit('Flutter is not in PATH. Install the compatible SDK and retry.')
    required={
        'android':('app/src/main/AndroidManifest.xml','app/build.gradle.kts','settings.gradle.kts','gradlew'),
        'ios':('Runner.xcodeproj/project.pbxproj','Runner/Info.plist','Runner/AppDelegate.swift'),
    }
    missing=[name for name,files in required.items() if not all((ROOT/name/f).is_file() for f in files)]
    if missing:
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'anirepro360_mobile'
            run(flutter,'create','--no-pub','--platforms=android,ios','--org','com.anirepro','--project-name','anirepro360_mobile',str(p))
            for name in missing:
                if not all((p/name/f).is_file() for f in required[name]):raise RuntimeError(f'Flutter failed to generate complete {name} project')
            backup=ROOT.parent/('anirepro-native-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            for name in missing:
                if (ROOT/name).exists():
                    backup.mkdir(exist_ok=True);shutil.move(str(ROOT/name),str(backup/name))
                    print('Incomplete native project backed up:',backup/name)
                shutil.copytree(p/name,ROOT/name)
            if not (ROOT/'.metadata').exists() and (p/'.metadata').exists():shutil.copy2(p/'.metadata',ROOT/'.metadata')
    config_android();config_ios()
    from configure_notifications import configure
    configure()
    run(flutter,'pub','get')
    if not args.skip_icons:
        dart=Path(flutter).resolve().with_name('dart.bat' if os.name=='nt' else 'dart')
        if dart.exists():run(dart,'run','flutter_launcher_icons')
        else:run(flutter,'pub','run','flutter_launcher_icons')
    if args.check:
        run(flutter,'analyze');run(flutter,'test')
    print('Setup finished. Run flutter devices, then flutter run with your API_BASE_URL.')
if __name__=='__main__':main()
