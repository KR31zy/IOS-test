# AniRepro 360 Mobile 2.4 — GitHub + Codemagic iPhone test

This project preserves `mobile/` from **AniRepro360-Mobile-2.4-Cow-Hero-Flutter.zip** byte-for-byte and adds a root `codemagic.yaml`, a root `.gitignore` and iOS cloud-testing guidance. No UI, image, logo, backend, business rule or package identifier was changed.

## Start with unsigned iOS compilation

1. Extract ZIP as a folder on your Mac.
2. Create a **private** GitHub repo and push the contents of the extracted folder (including root `codemagic.yaml` and `mobile/`). Do not upload secrets or an existing `.env`.
3. In Codemagic, add that repository and select **Configuration as code**.
4. Choose workflow **`ios-compile-check`** and run it manually.
5. Examine the logs and download `Runner-unsigned.zip` if the build passes. This is **not an installable iPhone app**.

The cloud machine runs Flutter 3.38.4 and Xcode 26.4, generates native `android/` and `ios/` projects with the existing bootstrap tool, checks Flutter, runs the tests, and compiles without signing. A failure is a real failure: do not skip the failing step or treat it as a successful iPhone test.

## To install on a physical iPhone

You need access to the **Apple Developer Program** for TestFlight or for registered-device Ad Hoc distribution; an unsigned `.app` cannot be installed through TestFlight or directly on an iPhone. Codemagic cannot bypass this requirement.

- Use App Store Connect and a properly registered App ID and bundle ID, plus an Apple Distribution certificate and provisioning profile.
- Connect App Store Connect to Codemagic in Team integrations > Developer Portal using an authorized App Store Connect API key.
- Copy the **actual** `PRODUCT_BUNDLE_IDENTIFIER` printed by the unsigned build, excluding `.RunnerTests`. Do not guess or change the app identity just to make signing work.
- Configure the backend's publicly reachable HTTPS origin before a signed release; do not use localhost or private addresses in distribution builds. This mobile package's existing `API_BASE_URL` compile-time parameter must match the deployed API.
- Add the `ios_signing` / `app_store_connect` integration to a separate signed `ios-testflight` workflow only after the Apple team, app record, API host and signing files are ready. Reference: https://docs.codemagic.io/yaml-quick-start/first-signed-build/
- Use `xcode-project use-profiles`, `flutter build ipa --release --dart-define=API_BASE_URL=https://YOUR_REAL_PUBLIC_API_HOST --export-options-plist=/Users/builder/export_options.plist`, then upload the IPA to TestFlight. Never place Apple private keys in source code.
- Alternatively, register the iPhone UDID in the Apple Developer Portal and prepare an Ad Hoc provisioning profile for direct tester installation.

The unsigned workflow does **not** test physical iPhone installation, OAuth provider configuration, push notifications or live farm synchronization. No signed IPA is included in this ZIP. The companion `mobile/server/` is an isolated test backend; use the unified production backend for shared farm accounts and data.

## Mac commands for uploading to a GitHub repository

Open Terminal **in the extracted folder that contains `codemagic.yaml`**, not in `mobile/`:

```bash
ls codemagic.yaml mobile/pubspec.yaml
git init
git add .gitignore codemagic.yaml README_IOS_CODEMAGIC.md mobile
git commit -m "Prepare AniRepro 360 iOS Codemagic compile check"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_PRIVATE_REPOSITORY.git
git push -u origin main
```

Replace `YOUR_ACCOUNT` and `YOUR_PRIVATE_REPOSITORY` with your actual names. GitHub may ask for web or token-based authentication. If you already cloned an existing repository, do not run `git init` or replace its remote; instead copy the new files and commit normally.

## Caveats

- On macOS Ventura, Android testing can still run locally; iOS native builds require a compatible cloud Mac.
- `xcode: "26.4"` and `flutter: "3.38.4"` are pinned for reproducibility, but the remote machine images and package compatibility have **not** been tested here.
- The backend is not automatically deployed by this workflow. Your local test server remains local; an iPhone using cellular data cannot access it unless you provide a securely reachable backend.
- For Google or Apple sign-in, configure genuine server OAuth credentials and public HTTPS callbacks. This package does not embed OAuth secrets.
