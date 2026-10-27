# Synthetic logger-ledger check

This bundle contains artificial data only. It records a local software check,
not an independent-person reproduction or a completed headset-readiness study.

## Contents

- `verification.json`: sanitized native test results, cross-language outcomes,
  commands, expected refusal, environment and limits.
- `python-regression.json`: actual selected Python regression receipt and source
  hashes. `python-test-ids.json` lists the discovered test IDs.
- `source-manifest.json`: base commit and hashes of the tested ledger source,
  native tests and relevant project settings. The base commit alone does not
  contain these uncommitted changes.
- `git-checkout-20261027.json`: a later local packaging check of all 29 pinned
  source/fixture files under both automatic line-ending settings.
- `mixed/`: native Unity-generated schedule/events and one accepted artificial
  window, plus the read-only Python reconciliation report.
- `orphan/`: native fixture with a window saved before an injected ledger failure,
  plus its expected-invalid reconciliation report.

Private Unity logs/XML and Python console output were retained locally because
they contain environment paths. Their hashes are recorded for comparison; the
sanitized native receipt retains every test name and outcome. Intermediate native
runs passed 15 existing tests before changes, then 32 tests before the final
three cases were added. The final run passed all 35. An initial sandboxed Python
run failed to create temporary files before reaching assertions; the unchanged
17 focused tests then passed with the required filesystem access.

## Recheck the exported fixtures

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/validate_trial_ledger.py results/week-9/keegan/logger-ledger-20261027-001/mixed/ledger.jsonl
.\.venv\Scripts\python.exe -B src/python/scripts/validate_quest_log.py results/week-9/keegan/logger-ledger-20261027-001/mixed/windows.jsonl
.\.venv\Scripts\python.exe -B src/python/scripts/validate_trial_ledger.py results/week-9/keegan/logger-ledger-20261027-001/orphan/ledger.jsonl
```

Expected exits: 0, 0, then **1**. The third command should report
`unreferenced_window_records`, with no closure and one completed trial still
pending processing. Treating that third result as success would hide the
interruption the fixture is meant to expose. The files must remain unchanged.

`COMPLETE` in the first report means complete accounting, including skips/stops;
it is not a claim that all scheduled trials were recorded or accepted. The
fixtures exercise ledger/writer APIs in EditMode, not a rendered visit or an
Android recording. Full controller coroutine, pause/quit timing and user controls
still need actual-build checks.

The repository's `.gitattributes` preserves the source line endings observed in
this run and prevents conversion of this bundle's evidence bytes. A small local
Git index/checkout test retained every recorded source and fixture hash with
`core.autocrlf` both true and false. Source and fixture bytes were unchanged;
the earlier test receipts were not rewritten. Their uncommitted flag describes
the test execution checkpoint. This packaging check is not another person's
independent reproduction.

To generate new native fixtures during the EditMode tests, set
`PUF_SNN_LEDGER_FIXTURE_ROOT` to a new local directory before running Unity.
The tests export `ledger.jsonl`, `windows.jsonl` and an `orphan-case/` child.
Use a new folder to preserve old evidence. The generated schedule is stored in
the plan, so its exact order is available even across runtime differences.

## Boundaries

- No human poses, new model training, alert-cutoff changes, recovery experiments
  or latency measurements were used.
- Windows file hashes support local integrity checking; they are not HMAC,
  attestation or a security proof.
- `Flush(true)` and refusal of incomplete files were tested locally. No sudden
  power loss or Android filesystem durability guarantee is claimed.
- Root Python discovery excludes the historical/non-package experiment,
  tier-1 and profiler folders. The 17 ledger tests are within the 1,102 root
  count; the native 35 are separate.
- Retention, repeats, study access and readiness decisions remain subject to the
  coordinated protocol/consent review.
