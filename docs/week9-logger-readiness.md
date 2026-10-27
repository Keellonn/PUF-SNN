# Week 9: logger readiness and remaining work

Updated October 27, 2026. Scope: software and synthetic fixtures only.

## First bounded result

The logger previously saved only accepted windows. Rejections were warnings, so
the saved files could not account for every scheduled trial. The controller now
writes a complete schedule and a separate append-only event ledger. Stops, skips,
quality refusals, processing failures and interrupted attempts remain visible.

The native Unity tests passed **35/35** (15 existing and 20 new). The Python
ledger tests passed **17/17**, and are included in the new **1,102/1,102**
selected Python regression result (zero failures, errors or skips). Native Unity
tests are separate. Unity's exported mixed fixture reconciled in Python:
five scheduled, three attempted, two completed, one accepted, one quality
rejected, one stopped, one skipped and one not attempted. An injected failure
after saving a window was correctly reported as an unclosed ledger with one
orphan window and pending processing. The accepted synthetic window also passed
the existing schema/quality validator.

Before the commit handoff, scoped Git attributes were added so checkout does not
alter the pinned file bytes. A local index/checkout check verified all 29 source
and fixture hashes with automatic line-ending conversion enabled and disabled.
This is a packaging check; independent-person reproduction remains pending.

See [ledger behavior and commands](quest-trial-ledger.md) and
[Week 9 evidence](../results/week-9/keegan/README.md). This is not a new latency,
accuracy, credential-reliability or real-motion result. No shared default,
classifier, cutoff, authentication or reconstruction policy was changed.

The current choices are **no saved raw source recordings** and **no repeats**.
They are proposals to synchronize with the PI-reviewed protocol, not approved
collection rules. The schedule supports three balanced blocks of 25 but the
software defaults have not been made a study commitment.

## Phase 1 report required before Phase 2

Passing a row means its behavior is measured and failures handled correctly;
it does not require zero tracking losses or zero rejected trials. An assigned
reviewer must link the measurement and exception handling for each row.

| Readiness item | Current evidence | Still required |
|---|---|---|
| Timestamp meaning and ordering | App stopwatch documented; artificial ordering/gap tests | Verify observed headset behavior, clock origin and prompt/capture timing in the actual build |
| Observed sampling rate | Target output is 120 samples / 2 seconds | Source-rate distribution and missed-frame accounting, before resampling |
| Tracking and source gaps | Processor tests include source gap and 114/120 output tracking boundary | Save source gap/tracking summaries for every attempted trial, including refusals; verify API flags on the assigned headset |
| Prompt-to-window alignment | Ledger stores prompt, capture request and capture-start confirmation | Measure rendered prompt/action boundaries and late/overlong motion handling; software event times alone are insufficient |
| File write/reload | Synthetic Unity write and Python reload/hash checks pass | Verify Android storage, pause/interruption behavior and transfer on the assigned headset |
| Complete trial accounting | Full schedule, reasons, stop/skip paths and orphan detection tested | Wire staff controls, rehearse the procedure with permitted inputs, review counts and unresolved events |
| Transfer integrity | Per-window receipts and local hash reconciliation | Document actual transfer path and compare whole-file hashes before/after transfer |
| Missing/rejected/interrupted trials | Separate counts and valid-prefix reporting; no silent file repair | PI-reviewed retention/repeat rules matching consent; confirm staff handling in the actual build |
| Freeze and review | Source/test hashes saved for this software check | Freeze logger, API/build, preprocessing, normalization, quality rules, weights and cutoffs for evaluation; PI reviews the readiness report |

**Phase 2 gate:** applicable written HRPP determination/IRB approval must cover
the planned activity, and Dr. Garcia must review the Phase 1 readiness report and
confirm that the system and procedure work as described. Equipment access and
passing software tests do not satisfy these gates. Continue synthetic and
permitted non-human bench work while the packet is revised.

After a logger or processing change, record a new version and change log, retain
the old report, repeat all affected checks plus ledger/file regression, and ask
the PI to review the updated readiness report before resuming Phase 2. Changes to
approved procedures or data handling also need the applicable institutional
review before use. Do not silently combine development and evaluation datasets.

## Remaining weekly tasks

| Owner | Next deliverable | Completion evidence |
|---|---|---|
| Keegan | Optimization interpretation | Define tested-case matching across decisions, reasons, processed values, model outputs, calls, release and state; separate downstream matching conditional on successful admission from admission reliability |
| Keegan | Timing table and boundaries | Label both historical blocks, single-read recovery, machine/environment, warm-up/repetitions, existing-session versus setup-plus-first and excluded two-second acquisition; no claim of current three-read timing |
| Keegan | Logger readiness | Finish source summaries, actual build/controls/transfer checks and Phase 1 report above |
| Will | Shared-noise and three-arm accounting | Frozen short specification; matched nominal/stress denominators, failure states, uncertainty and reconstruction/admission timing; define stored credential precisely |
| Together | One independent reproduction | Another person reproduces one central table from a frozen release; record prerequisites, deviations and comparisons |
| Together / PI | One coordinated submission packet | Matching protocol/consent, prompts, recruitment/screening, comfort/incident form, data workflow, retention/withdrawal, roles/training, change log and short PI decision list |

The missing historical timing archive remains a provenance gap. It does not
prevent current software checks or a newly frozen bounded reproduction, and
should not be relabeled as recovered evidence.

Historical test accounting is unchanged: the **73 focused tests are included in
the recorded 1,085** selected root tests; the **55 profiler tests are separate**
because ordinary root discovery excludes `tests/tools`. Native Unity tests are
also separate. New ledger tests do not retroactively enlarge those old receipts.

## Decisions to bring to the PI

1. Recommend metadata-only retention for rejected/stopped trials, without raw
   source recordings, provided the source-quality summaries support readiness.
2. Recommend no automatic repeats in this pilot; any later repeat policy needs
   a reviewed cap, ledger linkage and matching protocol wording.

Actual study location, headset/device inventory, storage service and access,
retention periods, recruitment conflicts, consent personnel, safety procedure
and training still need coordinated confirmation. They have not been invented
or filled in by this software implementation. No participant records were made.
