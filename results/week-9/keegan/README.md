# Week 9: Keegan's logger checks

Checkpoint: October 27, 2026. Artificial inputs only; no participant collection.

The first completed task closes a software accounting gap: the Quest controller
now records the full schedule and every trial's progress separately from the
accepted-window file. Skips, stops and rejections no longer disappear from the
saved trial accounting.

| Check | Result |
|---|---|
| Native Unity EditMode | 35 passed: 15 existing, 20 new ledger cases |
| Python ledger tests | 17 passed; included in the regression below |
| Selected Python regression | 1,102 passed, zero failures/errors/skips |
| Unity-generated mixed visit, reconciled in Python | Complete accounting: 5 scheduled, 3 attempted, 2 completed, 1 accepted, 1 quality rejection, 1 stop, 1 skip, 1 not attempted |
| Accepted synthetic window | Existing window schema/quality validation passed |
| Injected failure after window write | Expected refusal: no visit close, 1 orphan window, 1 pending processing outcome |
| Git checkout packaging | All 29 pinned source/fixture files retained their recorded hashes with automatic line-ending conversion both enabled and disabled |

Bundle: [logger-ledger-20261027-001](logger-ledger-20261027-001/README.md).
Source hashes identify uncommitted tested files over the recorded base commit.
No commit or push was made as part of this check.

See [ledger documentation](../../../docs/quest-trial-ledger.md) and
[readiness / remaining weekly work](../../../docs/week9-logger-readiness.md).
The retention/repeat choices still need PI review and matching study documents.
Android capture, prompt alignment, actual transfer and
PI readiness approval remain unfinished. These checks do not establish model
accuracy, headset performance, credential reliability or independent reproduction
by another researcher.

The historical 73 focused tests are inside the old 1,085 receipt. The 55 profiler
tests are separate; ordinary root Python discovery excludes `tests/tools`,
`tests/experiments` and `tests/tier1`. Do not add the focused tests to the root
total or mix these software counts with experimental observations.


## Current follow-up

- [Source diagnostics](source-quality-20261027-001/README.md): 50 Unity and 1,117 selected Python tests passed; summaries survive synthetic rejection/stop paths; missing diagnostics are refused.
- [Optimization and historical timing](../../../docs/week9-optimization-and-timing.md): tested matching, exact labels, scope and outliers; defaults unchanged.
- [Research status and corrections](../../../docs/week9-research-status.md): model targets, evidence accounting and workflow timing distinguished.
- [Small reproduction handoff](../../../docs/week9-bounded-reproduction.md): about 16 MB of already tracked inputs; no model binaries needed for the score-table scope. Local dry run matches; independent person still pending.

These follow-up files are an uncommitted tested overlay over 55dea11. The earlier
checkpoint bundle remains unchanged. No new human recordings or scientific
accuracy/latency/reliability measurements were made in this follow-up.
