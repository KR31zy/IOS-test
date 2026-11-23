# Setup and build instructions

## Prerequisites

- Flutter 3.38.4 stable or another compatible Flutter release with Dart 3.5+ (3.38.4 is the intended local starting point; dependency and native tooling compatibility still must be checked).
- Python 3 to run the included native-project setup and optional auth update.
- Android Studio, Android SDK, JDK and emulator for Android builds. Use `flutter doctor -v` to identify missing requirements. Android minimum SDK is at least 23 in the generated Kotlin Gradle configuration.
- For iOS: macOS, a compatible Xcode installation, simulator, Apple signing account for physical devices, CocoaPods if required by Flutter plugins. A Windows PC cannot compile an iOS IPA. An older macOS/Xcode may support local simulator testing with a matching SDK but not current App Store submissions.
- An existing, working AniRepro 360 FastAPI backend; the mobile app shares its database via REST, not direct DB connections.

## 1. Prepare the folder

Extract the archive into your original project root, replacing only `mobile/` after making a backup. The ZIP has a single top-level `mobile/` directory. Run in Terminal:

```bash
cd /path/to/Anirerepro360-main/mobile
flutter doctor -v
./setup.sh --check
```

Windows PowerShell:

```powershell
cd C:\path\to\Anirerepro360-main\mobile
flutter doctor -v
powershell -ExecutionPolicy Bypass -File .\setup.ps1 --check
```

The Python bootstrap uses `flutter create --no-pub --platforms=android,ios` in a temporary directory, then copies only the platform projects and `.metadata`. It configures the app label, Android internet permission, debug-only cleartext, iOS local-debug ATS settings and Keychain entitlements, resolves dependencies and generates launcher icons. `--check` runs Flutter analyze and test; fix any diagnostics before building. If the Xcode template differs, bootstrap reports an explicit error instead of claiming success. If one native folder exists, it stops instead of overwriting it. If generation/configuration failed partially, move both generated folders aside and rerun after addressing the error.

If necessary, native generation can be done manually in a **temporary** Flutter project and the Android/iOS folders copied here. Do not create over the delivered Dart source. If the bootstrap cannot recognize a newer template, configure:
- Android main manifest: INTERNET permission, app label, no backups. Debug manifest application: `android:usesCleartextTraffic="true"`; never enable HTTP for release.
- iOS Runner Debug target: use `Runner/Info-Debug.plist` with local development ATS allowance; Release/Profile: regular `Runner/Info.plist` without arbitrary loads. Add Keychain Sharing for the Runner using the app identifier group. Use your actual bundle identifier and development team when signing.

## 2. Backend

Keep your existing database and environment variables, and run your server from its backend folder. If you are enabling username authentication, first follow AUTHENTICATION.md and run the migration using the same DB connection that the existing app uses. Do not generate a new database accidentally.

```bash
cd ../backend
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
# Set the same DATABASE_URL, SESSION_SECRET and other environment values used by your web app.
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use `--host 0.0.0.0` for physical-device/LAN testing only on a trusted network. For emulator-only testing the original loopback server may suffice. Confirm `GET /api/health` works. Password recovery needs the backend's SMTP configuration. Evidence uploads need backend file-encryption and storage settings. Do not expose development HTTP to the internet or use real clinical data over unsecured Wi-Fi.

## 3. Launch

From `mobile/`:

```bash
flutter devices
flutter run -d <device-id> --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

| Target | API_BASE_URL for local debug |
| --- | --- |
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator on backend Mac | `http://127.0.0.1:8000` |
| Physical Android or iPhone | `http://<computer-LAN-IP>:8000` (same trusted Wi-Fi, firewall permits 8000) |
| Release | `https://your-real-api-host` |

With the unchanged backend use `--dart-define=USERNAME_AUTH=false`. The source defaults to username-enabled mode. API URLs are defined at compile time. No secrets are bundled. If a development cookie becomes invalid after restarting the backend, sign in again; the server's development session secret can change unless configured persistently.

## 4. Build after tests pass

```bash
flutter analyze
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
# Production examples (replace URL; configure Android signing, iOS signing first):
flutter build appbundle --release --dart-define=API_BASE_URL=https://YOUR_API_HOST
flutter build ipa --release --dart-define=API_BASE_URL=https://YOUR_API_HOST
```

Android debug APK: `build/app/outputs/flutter-apk/app-debug.apk`. This emulator-targeted build does not connect to a real phone; rebuild with its correct API URL. Android app bundle: `build/app/outputs/bundle/release/app-release.aab`. Apple IPA build requires appropriate signing/provisioning. Production HTTPS is required by the API client. Use the real registered app IDs, configure signing privately, review app-store policies, permission disclosures, privacy terms, user-data deletion arrangements and clinical validation before public release. Do not commit signing keys.
