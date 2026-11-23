# AniRepro 360 Mobile 2.4 — Cow Hero & Flutter build

## Source and preservation

This update is derived from the user's uploaded `mobile(1).zip`, incorporating the earlier 2.3 UI improvements. It preserves the original app logo, launcher icon, app name, brand colors, server API contract, screen structure, and clinical data model. The cow photo `assets/herd-hero.jpg` is the exact existing web-project hero image, not a substitute.

## Existing 2.3 features retained

- Animated original-logo splash, first-use introduction, **Get started**, then existing sign in and sign up.
- Android Settings back behavior: previous route returns to Home (including Settings opened from More).
- Account-scoped encrypted device-local PNG/JPEG profile photo. No unsupported server photo synchronization is claimed.
- System / light / dark appearance preference, persisted through the existing secure storage.
- Reports compare authorized categories and periods from actual API records, not fabricated clinical results. The event endpoint may limit older history.

## 2.4 corrections

- Replaced the older shallow farm hero treatment with the same cow photo behind a navy translucent overlay, with original AniRepro logo, responsive farm name, role label, readable white text and existing farm selector.
- Changed reports panel headings to use theme-aware foreground colors for readability in dark mode.
- Made estrus cycle interval rendering null-safe and labels estimates as non-confirmed, including the count of observed cycles.
- Added a real-asset cow hero widget regression test.
- Added `BUILD_ANDROID_TEST_APK.command` for one-command Android debug test build and desktop ZIP on an Intel Mac.

## Running on a MacBook (Android only)

```bash
cd ~/Downloads/mobile
export PATH="$HOME/development/flutter/bin:$PATH"
bash BUILD_ANDROID_TEST_APK.command
```

If extraction creates a different folder location, `cd` into its actual `mobile/` directory. The script runs existing setup and Flutter checks, builds an Android *development* APK, and copies it to the Desktop alongside a shareable ZIP.

Direct build if you want to diagnose a failure:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=APP_ENV=development
```

## Independent client testing

A development APK requires a reachable local test server for login, registration and fresh records. A client on another network cannot use `localhost` or the developer's private LAN address. For independent testing, deploy the existing FastAPI service with HTTPS and compile the signed client build using that production or staging endpoint. No new APK has been compiled in this workspace because the Flutter and Android SDK executables are unavailable.

## SRS clinical scope

The uploaded backend supports historical estrus interval calculation, mean/median/min/max/variability and a provisional next-estrus estimate based on observed history. It retains breeding, pregnancy and birth record entry. It does *not* yet fully satisfy the November 2026 SRS: irregular-cycle rates, prediction confidence windows, validated ovulation windows, follicular growth rates and species-configured gestation/delivery estimates need a dedicated clinically validated backend implementation. This UI update does not invent those results.

## Data integrity

Report chart values derive from the shared authorized farm endpoints (`/summary`, `/animals`, `/events`). The API may return a capped recent event history, so old months may be incomplete. The mobile report explicitly warns about this. Pending offline drafts are not counted as server-confirmed records.
