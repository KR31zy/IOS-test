# V2.1 — Google and Apple sign-in

All V2.0 features are retained. Read [Social sign-in configuration](docs/SOCIAL_AUTH.md) before enabling providers. The bundled server already contains the new migration and OAuth endpoints. Live provider credentials are not included.

# AniRepro 360 Mobile — 2.0 consolidated release candidate

**One mobile folder. No V1.1–V1.4 overlay or username patch installation is needed.**
This is a source release candidate, not a compiled Android APK, signed iOS IPA, or certified production release. It includes the accumulated mobile implementation, companion FastAPI source with username changes already incorporated, all migrations, automated build scripts, tests, native configuration generator, brand assets, and release documentation. Original web/backend files and records were not changed during development.

## Contents

| Path | Purpose |
|---|---|
| `lib/` | Flutter screens, theme, authentication, dashboard, clinical workspaces, lifecycle/analytics, encrypted offline store, synchronization, reminders, notifications |
| `assets/` | Supplied AniRepro brand logo and application icon |
| `server/` | Companion server copied from supplied project, already updated for optional usernames, 8-character password minimum, UTC clinical event output, original API endpoints and migrations |
| `test/` | Flutter unit/widget tests (not executed in this release environment) |
| `server/tests/` | Backend integration/regression tests (23 passed) |
| `tools/` | Source verification, automated build and native generation, isolated test-server launcher, optional remote push gateway |
| `.github/workflows/mobile-quality.yml` | Automated quality gates when this `mobile/` folder is the GitHub repository root; not executed here |
| `BUILD_ANDROID.command`, `BUILD_ANDROID.cmd`, `BUILD_IOS.command` | One-click build automation for later, when the appropriate SDKs are available |
| `START_TEST_SERVER.command` | Optional isolated development-server launcher (not shared live data) |
| `docs/RELEASE.md`, `docs/QA_FINAL.md`, `docs/VERIFICATION_LOG.txt` | Current handoff, limitations and actual verification evidence |

## Current status

Earlier versions are consolidated. The next action is **device acceptance and deployment**, not an additional source-overlay phase. You do not need to run intermediate upgrade commands or install earlier versions. See `docs/RELEASE.md` for the host and account configuration still required at build/deployment time. The included generator creates official Android/iOS projects automatically on the build host. The actual generated native folders, resolved Flutter lockfile and compiled binaries are not present because Flutter SDK and native build tools were unavailable during this session. You may keep a backup of the locally generated `android/`, `ios/` folders from your existing work; the clean candidate can instead regenerate them in one automated build. It does not need the previous mobile source.

### Shared server versus isolated testing

`server/` is a ready-to-review **source copy**, not a second live database. Its code is already patched; do not run `enable_username_auth.py` on it. If the existing web application and mobile app need to share data, deploy the reviewed server code to the same API environment with the same database and existing persistent secrets, back up the DB, and run the included migration against that DB. An administrator must do this; the package deliberately will not silently overwrite the original backend or migrate your live data. The isolated test-server launcher uses a separate `.runtime` database with no existing web accounts. Never deploy that launcher publicly or enter real animal/clinical data over debug HTTP.

The login has **Set farm server** / **Change farm server** controls, so a physical debug phone can connect to a trusted LAN development server without rebuilding for each IP. Release builds accept HTTPS only. A production server origin is not supplied because it was not provided. Use an administrator-trusted origin.

**Older `docs/UPDATE_1_1.md` through `UPDATE_1_4.md`, `SETUP.md` and `AUTHENTICATION.md` describe the historical incremental packages; their installation instructions are superseded by this README and `docs/RELEASE.md`.** Retained for feature-level reference only.

## V2.2 update
Start with [Connectivity and publication candidate](docs/PUBLISH_2_2.md). This supersedes earlier server-address and build advice.


## UI polish and specification review (v2.3)

See [docs/UI_POLISH_AND_SRS_REVIEW.md](docs/UI_POLISH_AND_SRS_REVIEW.md) for onboarding, Home artwork, back navigation, device-local encrypted profile photos, appearance modes, real-data comparison charts and SRS traceability. This package is derived from the user-supplied `mobile(1).zip`, not the separately maintained unified V3.0 backend.

## Mobile 2.4 visual polish (original branding preserved)

Home and first-use introduction reuse the original cow photo with the translucent navy treatment from the AniRepro web login hero. The animated logo, onboarding, profile photograph picker, Settings back-to-Home behavior, device/light/dark appearances and real-data comparison charts are included. See `docs/UI_2_4_COW_HERO_AND_BUILD.md` for the full scope and clinically unverified SRS requirements.

On an Intel Mac with Flutter and Android SDK installed, run `bash BUILD_ANDROID_TEST_APK.command` inside `mobile/`. This builds a **development APK** and packages it for sharing in a ZIP on your Desktop if—and only if—the native build succeeds. Client registration and online operation still require a reachable AniRepro API server.
