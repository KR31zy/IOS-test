# Verification record — 2.0 release candidate

## Executed in this session

| Check | Result |
|---|---|
| Static source imports and Python syntax | Pass, 28 Dart source/test files checked for local import existence; all bundled Python files parsed |
| PNG brand assets | Pass, valid PNG signatures |
| Android/iOS configuration fixture | Pass, repeated execution, notification receivers, permissions, desugaring, plist/entitlements, debug vs release transport settings |
| SQLite Alembic upgrade | Pass, clean database through `m20261119_username (head)` |
| Username and password contract | Pass, email/username login, uniqueness, change, logout, CSRF, 8-character minimum |
| Backend pytest | Pass, 23 tests including the 22 original tests and one lifecycle/UTC/family-link/cross-farm test |
| Offline idempotency contracts | Pass, duplicate animal and event writes, changed payload rejection, transactional offspring replay, authenticated replay |
| Push gateway contracts | Pass, authenticated registration, CSRF, unread-only, deduplication, unregister, expiry (fake sender) |

`VERIFICATION_LOG.txt` captures the final run. All database checks used disposable SQLite state. Original project files and live records were not accessed or modified.

## Not executed / blockers

- `flutter` / `dart` executables absent; Flutter distribution host DNS unavailable; Android SDK/Gradle wrapper, Xcode and iOS signing unavailable. No actual Flutter analysis, Dart test, native build or dependency resolution performed for this release. Earlier user test on V1.0 does not verify this candidate.
- Source-level native fixture tests do not prove real Android manifest merger, pod installation, iOS signing or phone notifications. Build scripts and CI workflow not executed against native SDKs. No native generated projects, lockfile, APK, AAB or IPA in this candidate.
- No live PostgreSQL, production server, SMTP, Firebase or APNs credentials. No real push delivery, deployment, or web-browser acceptance test. Companion server code changes require administrator review before replacing deployed backend.

## Device acceptance checklist (later)

- Cold start splash, reduced motion, login in small/large displays, keyboard/focus/accessibility, network errors; Android/iOS permission and storage behavior.
- Register with username; email compatibility and existing accounts; password recovery, invitation join, role restrictions, session expiry and logout; correct shared database and no cross-farm access.
- Actual farm animals, health/reproduction/breeding/pregnancy/birth/task forms, attachments, linked offspring, cycle estimates, real-data reports; no unsupported clinical inference.
- Prepare farm, disable network, cache views, save queued animal/event, restart, reconnect, retry idempotent requests, review conflicts and expired permission, verify encrypted local storage and account separation.
- Native reminder permission denied/allowed, scheduled local reminder while closed, timezone change, reboot, cancellation, remote push delivery after Firebase/APNs provisioning.
- Generate release build with appropriate signing; test real Android and iPhone handsets, app-store policy/privacy requirements, database backup/restore, performance with substantial farm data and clinical owner acceptance. Only then approve production release.
