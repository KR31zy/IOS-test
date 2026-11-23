# AniRepro 360 Mobile — revision 1.1

## Update an existing installation

The archive contains one `mobile/` source folder. If the previous setup already generated `android/`, `ios/`, `.metadata`, and `pubspec.lock`, preserve those files. Back up the current project before overlaying the new source. On macOS, `ditto /path/to/extracted/mobile /path/to/project/mobile` merges the supplied source without deleting files that are only in your project. Do not delete the existing mobile directory or rerun the username patch solely because of this update. The source has no new package dependencies.

## Changes

- Report aggregates count only real API data. The species distribution donut includes counts and percentages; the six-month chart supports category filtering and displays the incomplete current month. The backend returns at most 500 visible events; a warning appears at the cap instead of presenting a full history. The totals endpoint's confirmed pregnancy count is historical, not a current pregnancy census.
- Reduced-motion support for new chart animations, accessible chart labels and visible numeric values.
- Dashboard responsive metric columns and stable tab identity when permissions alter the tab list.
- Network failure messages for timeouts, connectivity, TLS and unexpected responses. No automatic mutation retry, which could duplicate clinical writes.
- While refreshing, keep the current page visible but block its pointer actions; if the request fails, show an error/retry view instead of keeping stale clinical results on screen. Ignore refresh callbacks after disposal.
- Incorporates both previously reported `records.dart` analyzer fixes.
- Three new automated aggregation tests. The tests contain synthetic fixtures only; the app uses no synthetic data.

## Physical phone testing later

For a local debug test, start FastAPI with its correct existing database settings and `--host 0.0.0.0` on a trusted network, and use the computer's LAN IP rather than the emulator address `10.0.2.2` in `API_BASE_URL`. Both devices need access to the same network (and firewall port 8000). For release builds, use a deployed HTTPS backend. Do not use real clinical information over insecure HTTP. iPhone installation requires a supported Xcode version and signing/provisioning; on an Intel Mac running Ventura, a newer supported build host may be necessary. Android APK installation and device tests are also still required. See SETUP.md for the broader process.

## Still outstanding

Encrypted durable offline storage, queued writes and synchronization, native push delivery, deeper clinical longitudinal analytics, clinical workflow verification, real-phone accessibility/performance, release signing and distribution. Profile/animal editing and native deep links require further API/platform work. Source review and packaging are not substitutes for Flutter analysis, tests or builds. No new Flutter commands need to be run immediately if the owner chooses to defer testing.
