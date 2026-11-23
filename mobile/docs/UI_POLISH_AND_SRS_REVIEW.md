# AniRepro 360 — mobile UI polish and SRS traceability

## Source and scope

This patch is based **only** on the supplied `mobile(1).zip`, which identifies itself as `2.2.0+8`. It is **not** a replacement for the separately maintained unified V3.0 backend and frontend. No database tables, existing clinical calculations, application logos, API routes, roles, or identifiers were altered. The existing server snapshot is left intact.

The cow image `assets/herd-hero.jpg` is a copy of `frontend/public/herd-hero.jpg` from the previously supplied complete AniRepro project. It is drawn with opacity over the existing AniRepro gradient. The existing `assets/logo.png` and `assets/app_icon.png` are unchanged.

## Changes

- Splash: existing logo now fades/scales into view; no spinning logo. User preference to reduce motion is honored.
- Introduction: a first-use information page explains animal records, reproductive workflows, and offline limitations. **Get started** opens the existing authentication screen. Returning users retain the usual session-restoration behavior.
- Back navigation: on any secondary root tab, Android Back returns to Home instead of exiting. Closing Profile & settings from More also selects Home. Normal back within other pushed screens remains unchanged.
- Dashboard: uses the same existing cow photo as the web application, overlaid at low opacity. Farm selector, counts, real data, and role permission checks are preserved.
- Profile: allows JPEG/PNG selection from the phone (max 2 MiB); stores an AES-256-GCM encrypted file in the app sandbox with an account-and-server-scoped key in platform secure storage. A second account cannot read it through the UI. **The image is device-local; no server avatar API is present in the supplied source. It is not uploaded to the server or synchronized across devices.**
- Appearance: three options — Device default (follows system, the default), Light and Dark. The preference survives reopening using secure storage. Existing blue/green brand tokens remain unchanged.
- Reports: two comparisons based exclusively on returned, authorized API events: (1) two selectable categories by month, (2) categories in previous three vs latest three calendar months. Charts never fabricate data; any partial 500-record API history and incomplete calendar months remain disclosed. No clinical success rates are inferred from record counts.
- Additional tests: onboarding, Back navigation, report comparisons, and image signature/size validation.

## Comparison with two November 2026 SRS documents

| Requirement | Evidence in uploaded mobile/server snapshot | Assessment |
|---|---|---|
| Estrus interval = difference between valid onset dates | `server/app/main.py:cycle_summary` calculates day gaps from distinct observed onsets | Implemented for observed records |
| Mean, median, min, max, variability | `cycle_summary` returns all five | Implemented |
| Median of 3–5 recent cycles for initial estimate | Median of up to last **five** valid intervals, only when at least **two** intervals exist; no validated cycle-range screen | Partially aligned; insufficient validation |
| Irregular-cycle frequency | No implementation verified | Missing |
| Next estrus date | Last onset + median interval for eligible species; marked not confirmed | Implemented as nonclinical estimate |
| Confidence & observation window | No meaningful confidence or interval window | Missing |
| Ovulation statuses and clinical evidence | Observation input, status and evidence fields exist, but not the full SRS status taxonomy or evidence-aware predictor | Partially implemented |
| Follicle growth in mm/day | Serial sizes can be recorded, but no same-follicle growth-rate computation | Missing |
| Hormones with value/unit/sample/assay | Required fields and history are present; no validated species/assay-specific thresholds | Partially implemented |
| Species-specific reference profile | Initial cattle/sheep/goat/horse/pig/dog/cat/rabbit entries; `validated_for_clinical_use: false` | Config present, clinical validation missing |
| Breeding method & sire history | Service event supports natural/AI, sire/donor and batch metadata | Implemented as records |
| Pregnancy confirmation | Method and supporting evidence enforced for confirmed events | Implemented as records |
| Estimated delivery = conception + species gestation, gestational age | A user can manually record an optional delivery estimate; no validated species gestation durations/calculation | Missing automatic formula |
| Birth and offspring relationships | Birth event creates linked offspring; API integration tests cover relation | Implemented |
| Clinical decision support accuracy | Both source SRS documents explicitly require veterinary validation | **Not verified and must not be claimed** |

**Conclusion:** The reproductive system follows the SRS in its core record structures and several cycle-history statistics, but it is **not fully SRS-compliant** for validated species-aware prediction, confidence intervals, follicular growth, gestational calculations, or all ovulation status cases. Clinical calculations were not changed in this UI-polish release because guessing species durations or medical thresholds would violate the SRS and could produce misleading advice. A veterinarian and verified reference profiles are required before implementing these as real decisions.

## Verification classification

- **Passed:** 28 existing Python backend tests on disposable SQLite; Python syntax; source import and Android/iOS fixture validation (`tools/verify_source.py`); image asset and package integrity.
- **Written, Not Run:** Flutter widget/unit tests, including the new onboarding, navigation, photo and comparison tests. No Flutter SDK or Android/iOS device is available in the packaging environment.
- **Not Run:** Full Android/iOS compilation, installation, app restarts, dark-mode accessibility across every clinical screen and real multi-device photo synchronization.

## Developer acceptance steps on Mac

From the updated `mobile` folder:

```bash
export PATH="$HOME/development/flutter/bin:$PATH"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
flutter pub get
flutter analyze
flutter test
bash setup.sh --check
flutter run -d <your-pixel-device-id> --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

For USB loopback testing on the same Mac, start the existing development FastAPI server and run `adb reverse tcp:8000 tcp:8000` before the `flutter run` command. Client-facing APKs still require the deployed HTTPS production backend, release signing and testing.

Verify in this order: fresh install → animated splash → Get started → existing login/registration → Dashboard cow image → More → Profile & settings → Android Back returns to Home → choose profile photo → reopen app → theme Device/Light/Dark → Reports monthly and period comparisons with known actual farm records.

## Production follow-ups

- Add a permission-checked, size-limited user-avatar API and protected media storage in the **main** FastAPI backend to synchronize profile pictures across devices. Do not duplicate the backend.
- Clinically validate species gestation and cycle thresholds, implement the remaining SRS calculations with tests, and keep predictions distinct from observations and confirmations.
- Run Flutter static analysis and device acceptance, resolve any errors, and build a signed release against a public HTTPS server before client rollout.
