#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -x "$HOME/development/flutter/bin/flutter" ]]; then
  export PATH="$HOME/development/flutter/bin:$PATH"
fi
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter not found. Configure ~/development/flutter/bin first." >&2
  exit 1
fi
echo 'Preparing the existing native Android project...'
bash setup.sh --check
echo 'Compiling Android TEST APK (development connection settings)...'
flutter build apk --debug --dart-define=APP_ENV=development
source_apk='build/app/outputs/flutter-apk/app-debug.apk'
[[ -s "$source_apk" ]] || { echo "APK missing after compilation" >&2; exit 1; }
target="$HOME/Desktop/AniRepro360-Mobile-2.4-TEST.apk"
cp "$source_apk" "$target"
( cd "$HOME/Desktop" && zip -j -q -FS 'AniRepro360-Mobile-2.4-TEST-APK.zip' 'AniRepro360-Mobile-2.4-TEST.apk' )
echo "TEST APK: $target"
echo "SHARE ZIP: $HOME/Desktop/AniRepro360-Mobile-2.4-TEST-APK.zip"
echo 'Note: New accounts and online farm data still require a reachable AniRepro server.'
