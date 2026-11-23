# V1.4 — Farm reminders and notifications

Overlay the **contents** of this mobile folder on V1.3. Preserve local generated `android/`, `ios/`, `.metadata`, and `pubspec.lock` (keep it until dependency resolution updates it). No Flutter commands are necessary during deferred development. No original backend, frontend, or database files have been changed.

## What's new

- Dashboard and More link to Farm reminders. This uses the existing farm-scoped animal and event feeds, not sample data. It shows recorded past/today/upcoming dates. Event history is capped at 500 by the server; the reminder page is not a complete clinical schedule.
- Explicit `next_due_date` (health and pregnancy), `due_date` (incomplete task), `planned_pregnancy_check_date` (breeding), `estimated_delivery_date` (user-recorded estimate) and optional per-animal server `estimated_next_estrus`. No gestation length, medicine dosage, or vaccine intervals are invented. Completion of a recorded task is not inferred from unrelated later records; plans must be clinically reviewed. Archived or unavailable animal records are excluded.
- Device reminders: select local phone time, optionally one day before, then explicitly schedule the next 30 days. One generic notification per date; consecutive schedules replace the old set, even for another farm. Cancellation, notification test and pending count controls. Alerts use the schedule snapshot, not continuous remote reconciliation. Connect and reschedule after changes, travel/timezone change or farm access changes. Generic alerts can remain scheduled while the app is closed and cannot be remotely recalled; explicit sign-out and observed membership changes attempt cancellation. OS restrictions can delay or prevent them. No exact-alarm permission requested. Not a critical clinical alert system.
- V1.3 offline cache and queue remain intact. Cached dates are available if relevant pages were prepared; scheduling requires online refresh. Pending writes are not treated as server-confirmed reminders.
- Server notification inbox remains the source of truth; remote push is optional and disabled by default. No farm, animal, username, clinical content or notification IDs are in push notification bodies. Opening an alert opens the app, not a bypass of the login gate.

## Local native configuration (later, at physical-device build time)

Run `./setup.sh --check` on Mac, or `./setup.ps1 --check` on Windows. The updated bootstrap also configures existing native folders via `tools/configure_notifications.py` (can run directly with Python after backing up native folders). It adds the Android notification permission, boot receivers, small vector icon, Java desugaring and compile SDK minimum 35. It preserves your Dart sources and native projects. It sets up iOS notification delegate and disables Firebase auto-initialization. If native project template differs, the script stops with a message; follow the plugin documentation. Verify Android Gradle plugin >= 8.6, Java 11 or newer compatibility and Android compile SDK >=35. Verify iOS deployment target >=13.0 (or higher if dependencies require it), Xcode and CocoaPods compatibility. If using an older iOS Podfile, update the platform and Runner build settings together. Keep signing and entitlements. Do not manually replace native folders from this ZIP (not included).

`flutter_local_notifications` 19.5: https://pub.dev/packages/flutter_local_notifications/versions/19.5.0

Local reminders need **no Firebase configuration**. Test permission denied, allowed, test alert, scheduled delivery while locked, app background, reboot, sign out and time zone changes. Native alert scheduling uses a UTC instant converted from phone local time; if the timezone changes after scheduling, reschedule. Android inexact alarms may be delayed; iOS and Android can suppress alerts via Focus, battery, or notification settings.

## Optional remote delivery (Firebase Cloud Messaging)

Real remote delivery cannot be tested or enabled until the owner creates the Firebase project and supplies platform setup and server credentials. Do not embed service account JSON in the mobile ZIP or repository; never paste private keys in chat. Firebase client app IDs are distinct from server credentials. Add actual Android package ID and iOS bundle ID from local projects to Firebase. Configure the default native Firebase app using `google-services.json` and the Google Services Gradle plugin for Android; add `GoogleService-Info.plist` to the iOS Runner target, upload an APNs authentication key to Firebase, and enable Push Notifications and Background Modes / Remote notifications in Xcode. Follow https://firebase.google.com/docs/cloud-messaging/flutter/get-started and https://firebase.google.com/docs/flutter/setup. The code uses default native initialization (`Firebase.initializeApp()`); if using FlutterFire CLI generated options instead, explicitly wire `DefaultFirebaseOptions.currentPlatform` in `push_service.dart` and preserve native background configuration. The current optional flag is `--dart-define=ENABLE_REMOTE_PUSH=true` in addition to the real HTTPS `API_BASE_URL`. Local notifications still work with this flag absent.

On the backend host, use the existing environment and database configuration. The optional gateway **imports** the existing `app.main:app` and adds two authenticated, CSRF-protected token registration routes. It is not an automatic patch. No core database migration is needed for the gateway; core migrations still must be current. It uses a separate private SQLite token store and a single polling worker. Configure a stable `SESSION_SECRET` and use the same existing `DATABASE_URL` for both processes. In production provide the existing backend's required environment variables; use HTTPS, access restrictions, server-only credential storage, a private directory, backups, rate limits and service monitoring. Use one worker and one gateway deployment sharing the same token database on the same host. This is a development adapter, not a horizontally scaled delivery service.

Example commands from `backend/` (Mac/Linux, when you are ready for integration):

```sh
source .venv/bin/activate
pip install 'firebase-admin>=6,<8'
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(cd ../mobile/tools && pwd)"
export ANIREPRO_PUSH_DB=/absolute/private/path/push.sqlite3
# DATABASE_URL and SESSION_SECRET must be set to your existing server settings.
uvicorn push_gateway:app --host 127.0.0.1 --port 8000
```

In a second backend terminal with the same configuration, and a securely provisioned service account via Application Default Credentials:

```sh
export GOOGLE_APPLICATION_CREDENTIALS=/secure/server-only/service-account.json
python ../mobile/tools/push_gateway.py
```

Start this wrapper instead of the standard Uvicorn process (do not bind both to port 8000). Open More → Notifications → Settings, or Farm reminders → Remote push settings, and opt in. Register after sign-in; registrations expire no later than the existing session (maximum eight hours). Re-enable after signing in or if token rotation failed. Deregistration and token removal are best effort; an offline sign-out cannot guarantee immediate remote revocation. No confidential information is sent. Expired or revoked users are removed and notification visibility is checked on the server at scan time. The worker deduplicates by token and notification ID, attempts each new unread notification at most once, and does not replay historical notifications or retry uncertain FCM sends. The real inbox remains accessible even if alerts are missed. Only generic notifications are delivered, not due-date alarms generated by the server.

## Verification

- Python gateway smoke test on a disposable backend: `python mobile/tools/test_push_gateway.py /path/to/backend` from project root. Tests use a fake sender and check authentication, CSRF, new unread-only delivery, duplicate suppression, unregistering and expiry. No real FCM credentials used.
- Existing idempotency smoke test: `python mobile/tools/test_sync_contract.py /path/to/backend`.
- Four new Dart unit tests in `test/reminders_test.dart` cover strict dates, recorded-data filtering, estimate status and alert deduplication/time horizon. These tests are written, not executed here because Flutter/Dart is unavailable.
- Device builds, dependencies, permission behavior, actual local notifications, remote push delivery and store submission still require verification. Do not treat this source as production-certified.
