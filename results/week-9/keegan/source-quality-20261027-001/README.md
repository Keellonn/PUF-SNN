# Source quality summaries with complete trial accounting

October 27, 2026. Artificial inputs only, on Windows. This extends the committed
ledger checkpoint without rewriting its evidence or changing its v1 file format.

| Check | Result |
|---|---|
| Native Unity EditMode | 50 passed; 15 new source-quality cases added to the earlier 35 |
| Focused Python | 32 passed: 17 ledger + 15 source-summary tests; included in 1,117 |
| Selected root Python regression | 1,117 passed, zero failures/errors/skips |
| Native mixed fixture read by Python | COMPLETE: 4 attempts, 4 summaries, 3 measured, 1 explicitly unavailable |
| Injected diagnostic append failure | Ledger COMPLETE, source check INVALID with 1 missing summary, as expected |

The mixed visit schedules five trials. Its first synthetic 90 Hz source becomes
one accepted 120-pose window; the second is rejected for a source gap; the third
is stopped with buffered poses retained for summary; the fourth has an
unconfirmed start and explicit unavailable counters. The fifth is not attempted.
No rejected or stopped raw pose coordinates are saved.

The sidecar records source counts, tracking validity and tracking-API availability,
interval/gap summaries, observed rate, nonfinite poses and zero quaternions before
interpolation. These diagnostics describe source data; they do not change the
quality acceptance rules, predictions, authentication or model defaults.

The native fixtures and reports are retained here. Sanitized test receipts and
source hashes identify the tested overlay over commit 55dea11. Raw Unity XML/logs
remain local because they include machine paths. The initial 49/50 test-reader
failure and its correction are disclosed in native-tests.json. The final receipt
is 50/50. Test durations are workflow observations, not latency measurements.

Android storage, actual tracking APIs, scene controls, rendered prompts, transfer,
device safety review and PI readiness review remain open. This is not participant
data or independent reproduction. See the linked logger documentation for commands.

The final checkout check preserved all 39 source, fixture, replay-tool and frozen replay-input hashes with automatic line-ending conversion enabled and disabled. The project index was untouched; this was a temporary packaging check.
