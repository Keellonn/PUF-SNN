# Quest bench setup and remaining checks

Updated October 30, 2026. The laptop scene is preserved. The separate
`QuestLoggerBench` scene has a tracked camera, a stationary world-space panel,
visible prepare/record/rest prompts and five controls. The software evidence is
in [the bench checkpoint](../results/week-9/keegan/quest-bench-20261028-001/README.md).

## Next connection check: Quest Link

The next development check will use PC-hosted Unity Play Mode through Quest Link.
Confirm the Link connection, PC OpenXR runtime and desktop XR settings before
checking tracking, prompts and controller behavior. No connected-headset run is
claimed yet. Installation of the Android APK is a separate testing route.

Link runs the application on the laptop, with headset tracking/display and
controller input. Its processing measurements would describe the PC-hosted path.
The existing Android compile receipt remains a separate historical checkpoint.
The protocol currently names Quest 3; the latest development discussion mentions
Quest Pro. Confirm the actual study device and acquisition path before finalizing
the protocol appendix and data workflow.

## Current behavior

Recording and automatic start are off in the saved scene. The operator explicitly
arms a permitted development test, then selects Start. Stop ends capture and
disarms; pause, disabling the interface and a completed visit also disarm.
Resume never automatically starts a new recording. New bench visits use a
unique `bench-...` code, and existing visit files are still refused.

Point the right controller and press its trigger to select a button. X skips,
Y stops/disarms and A continues a break. The digital shortcuts do not require
controller position tracking, but still require a connected controller supplying
button data. A held input after (re)connection must be released before a click.
Mouse buttons and Escape are available for Editor checks. These mappings have
software tests, not an actual-headset validation receipt.

The panel stays in the world; there is no simulated travel or passthrough. Head
pose uses the Input System tracked-pose driver. The camera's display offset is
separate from source capture: stored poses still use the Unity device-origin
frame. The app does not implement PUF recovery or authenticated release.

The bench has two blocks of five trials, one of each task per block. It is not
the proposed Phase 1/2 collection configuration. The recording switch is a local
operator control, not institutional approval or identity authentication.

## What is verified

All 60 Unity tests pass, including the earlier 50 and ten new bench cases.
Two cases enter Play Mode to check disable/pause lifecycle behavior. The final
ARM64 APK has the correct package, OpenXR loader and Quest VR metadata. The
earlier Python receipt remains 1,117; it was not rerun for this UI-only follow-up.

Only Quest support and the Oculus Touch/Quest Touch Plus input profiles are
enabled for this build. Unused AR camera, anchors, scene meshes, eye/hand and
related features are off. API minimum/target are 32 for this development APK.
The declared Internet permission means network behavior still needs review.
No camera/microphone permission is declared; platform tracking is separate.

## Standalone Android installation, if that route is used

1. Use the lab-managed account and a data-capable USB cable. Accept the debug
   prompt on the headset. Confirm that ADB reports one authorized device.
2. Install and launch the recorded APK with recording still off. Verify the
   stereo display, camera tracking, readable prompts and controller controls.
3. Rehearse only the permitted development/non-human bench workflow. Check
   stop, skip, continue, pause, quit, existing-visit refusal and lost tracking.
4. Copy the coded bench ledger, source sidecar and any accepted-window file to a
   private local folder outside public results. Compare whole-file hashes on
   the headset and laptop. Do not copy participant records into public Git.
5. Run the three read-only validators below. Preserve failures and incomplete
   files; do not repair them silently or repeat trials to hide a failure.
6. Save the device/build/account/permission settings, distributions, file
   receipts, exceptions and corrective actions in the readiness report.

Commands from the repository root, using the actual copied bench visit paths:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/validate_trial_ledger.py 'PRIVATE_PATH\bench-VISIT-trials.jsonl'
.\.venv\Scripts\python.exe -B src/python/scripts/validate_source_quality.py 'PRIVATE_PATH\bench-VISIT-trials.jsonl' 'PRIVATE_PATH\bench-VISIT-source-quality.jsonl'
.\.venv\Scripts\python.exe -B src/python/scripts/validate_quest_log.py 'PRIVATE_PATH\bench-VISIT-windows.jsonl'
```

The last command applies when an accepted-window file exists. A visit with only
quality refusals may legitimately have no window file; the ledger/sidecar still
must account for every attempt. A missing file referenced as accepted remains
a failure. USB hashes are integrity checks, not authentication.

Human research phases still need applicable written institutional authorization,
the approved workflow and the PI's Phase 1 readiness review before Phase 2.
Staff access, real device behavior and data retention must match the consent.
