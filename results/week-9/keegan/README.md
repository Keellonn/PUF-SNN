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
Android capture, source-quality summaries, prompt alignment, actual transfer and
PI readiness approval remain unfinished. These checks do not establish model
accuracy, headset performance, credential reliability or independent reproduction
by another researcher.

The historical 73 focused tests are inside the old 1,085 receipt. The 55 profiler
tests are separate; ordinary root Python discovery excludes `tests/tools`,
`tests/experiments` and `tests/tier1`. Do not add the focused tests to the root
total or mix these software counts with experimental observations.
