# Desktop logger controls checkpoint

October 28, 2026. Manual Unity Editor Play Mode checks with no valid XR tracking.
This is a control/accounting result, not Quest or participant-motion validation.

| Observed behavior | Evidence |
|---|---|
| Start blocked while recording disabled | Operator reported the expected Console warning; saved scene has recording and automatic start off. No timestamped refusal is claimed. |
| Start allowed during the desktop check | Both visits saved capture-start intent and confirmation. |
| Skip before recording | Visit 001 contains three skipped trials. |
| Skip during recording | Visit 001 retains stopped/participant_skip_during_recording plus its source summary. |
| Continue after break | Visit 001 reaches block two; the controller cannot pass that break without its continuation request. |
| Stop during preparation | Visit 001 closes with operator_stop and accounts for remaining trials. |
| Stop during active recording | Visit 002 retains stopped/operator_stop plus its source summary; all nine remaining trials are not attempted. |
| File accounting | Both visits return COMPLETE from both Python checkers, with no issues or missing source summaries. |

Visit 001: 10 scheduled, 2 attempted, 1 completed/quality-rejected for tracking,
1 stopped, 3 skipped and 5 not attempted. Two attempts have two source summaries.
Visit 002: 10 scheduled, 1 attempted/stopped and 9 not attempted. The stopped
attempt retains a 651-sample source summary. No accepted windows were produced.

All source tracking-valid counts are zero, as expected without a valid XR input.
Editor render-loop counts and rates are not headset sampling measurements.
Unresampled poses were not saved. Original app files are preserved unchanged.

The local scene and button methods are recorded by hash and a text snapshot.
The saved scene has recording/automatic start disabled; temporary Play-mode
settings are described separately. This does not add to the earlier native or
Python test totals and is not another person's reproduction. Actual Android,
headset input/display controls, transfer and institutional/PI readiness remain.
