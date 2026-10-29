# Quest bench scene and Android build

October 28, 2026. This is a disarmed development build and laptop software check.
The lab headset needs developer access before installation and device checks.

- All **60 Unity Editor tests passed**, including the earlier 50 and ten bench
  cases. Two lifecycle cases enter Play Mode. There were no failures or skips.
- The separate scene has a tracked camera, world-space task/status text and
  explicit Arm, Start, Skip, Stop and Continue controls. Recording starts off.
  Pause, disable and visit completion disarm it. Digital stop/skip remain usable
  without requiring a tracked controller position, provided button data exists.
- New bench visits use unique coded identifiers and ten scheduled trials. This
  is not the proposed 25/75-trial study configuration or an approved staff workflow.
- ARM64 APK 003 built successfully. Offline inspection found the OpenXR loader,
  Unity OpenXR native library, Quest VR category and head-tracking metadata.
  The APK is **59,711,216 bytes**, outside Git. The larger BuildReport total
  includes other output; it is not the APK download size.
- Declared permissions are Internet and the two OpenXR permissions. No camera or
  microphone permission is declared. This does not prove zero networking or
  zero processing by the headset platform. Actual account/telemetry settings
  remain part of the data-workflow review.

Read `build-receipt.json`, `summary.json`, `unity-tests.csv` and the source/hash
manifest. The checkout receipt checks 43 files (including 37 source/configuration
files) with Git automatic line-ending conversion both enabled and disabled.
Scoped metadata rules fixed the five line-ending mismatches found initially. Private raw Unity logs stay outside Git because they contain licensing
and machine details. The first two compile errors and the initial 58/60 test
attempt are retained privately and explained in the summary; they are not trials.

The previous **1,117 Python tests** were not rerun or added to for this UI change.
Installation, real controller/camera behavior, source-rate distributions,
rendered-prompt alignment, Android interruption/file behavior and USB transfer
are still untested. No human study collection or independent-person reproduction
is claimed. Earlier timing/quality/reconstruction evidence remains unchanged.
