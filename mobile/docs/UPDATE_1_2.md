# Revision 1.2 — Clinical workspace and mobile UI

## Install without losing local platform configuration

Back up the current `mobile/` first. Extract this archive into a **separate** directory. Merge the contents of its `mobile/` into the existing project `mobile/`. On macOS use Finder Merge or `ditto /path/to/extracted/mobile /path/to/project/mobile`. Preserve locally generated `android/`, `ios/`, `.metadata`, and `pubspec.lock`. Existing backend, frontend, database, and username migration are unchanged. No new dependencies were added. This source includes revision 1.1; it can be overlaid directly on either previous mobile revision. No Flutter commands are required for the update itself.

## UI and behavior

- Six clinical workspaces have individual titles, descriptions, icons, count tiles and action labels. Health uses examination/vaccination/medication/disease counts; reproduction uses observed estrus, ovulation, follicle and hormone record counts; breeding separates natural and artificial insemination service records; pregnancy shows assessment, confirmation, follow-up and outcome records; birth uses deliveries and offspring follow-up; tasks show task-type counts.
- Counts, status options and filtering derive from real authorized API records. Metric taps select a filter; animal, type, status and text filters can be combined or reset. History is ordered newest first. The API's 500-record limit is explicitly disclosed. Counts are records, not unique animals or clinical predictions. Pregnancy records are not active pregnancy counts.
- Searchable animal selection sheet; selecting a record-type metric can preselect the record kind in the form. Existing server write checks and UI permissions remain in place. A disabled add button is visually distinguished when no animals are available.
- Animal registry count, richer animal cards, profile overview, weight placeholder for missing data and newest-first history; More navigation grouped by clinical, farm and personal tools. Status remains a text label as well as a colored indicator.
- Auth, original logo, blue/green theme, splash, report charts and local native setup tools are preserved.

## Verification

Source reviewed against the original API's category keys, event schema and 500-record limit. Five new tests cover metadata, combined filters, service method handling, metric selection and missing weight; these tests have not been executed here. Flutter/Dart and Android/iOS build tools are unavailable in this environment. Previous owner's four passing tests applied to version 1.0 only. The package contains no generated native projects or binaries; retain the owner's installed native folders. No assertion of device rendering, compilation, accessibility or production readiness is made.

## Next development and acceptance

The clinical pages share a reusable layout system rather than six separate data architectures. Further UX refinements (specialized longitudinal and calendar views, accessible forms, long-list performance), encrypted offline persistence and conflict-safe synchronization, native push delivery and platform/release work are outstanding. For physical-phone testing, configure the API address appropriately (LAN IP in debug on a trusted network; HTTPS for release). Once testing resumes, run analysis/tests, build Android, build/sign iOS using a compatible host, and verify actual account/role behavior, device layouts, keyboard, filters, large accessibility text and all server-backed mutations. See SETUP.md and QA.md.
