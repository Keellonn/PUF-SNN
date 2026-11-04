# Optional accepted-source integration

November 3, 2026. This is the second Week 10 technical group, based on commit
`eb103dae512d5114f785257cac6de44725850013` plus the source hashes in
[verification.json](verification.json). Nothing in this receipt is a new headset,
human-motion, reconstruction-reliability or latency result.

## What changed

The controller can explicitly declare a v2 development retention policy before
starting a visit. It writes original source poses only after a durable accepted
ledger entry, then links the source hash/length to the trial and processed-window
receipt. Rejections and stops keep pose-free summaries. The default remains v1
with no source retention; both saved scenes remain unchanged and disarmed.

Multi-file writes are not atomic. Injected failures leave explicit incomplete or
invalid evidence and stop the path. Checkers preserve files, never fabricate a
receipt, and report source availability separately from ledger acceptance.

## Verification

- **85 Unity EditMode tests passed:** existing core/bench tests and the new
  integration cases. See the exact grouping and test names in the receipt.
- **1,141 selected Python tests passed**, with no skips, failures or errors.
  The 56 focused source/ledger tests are included, including 14 new visit tests.
  Root discovery excludes the nonpackage experiments, tier1 and tools directories;
  it is not a run of every historical-readiness module. Dependency check passed.
- The native fixture has five planned trials: one accepted, one quality rejected,
  one stopped, one skipped and one not attempted. Three were attempted and two
  completed. Only the accepted trial has a source-pose file. These stage counts
  overlap and must not be added together.
- Native replay matched the processed pose values. Separate Python inspection
  reconciled source/ledger/window/summary records. Python does not independently
  implement Unity quaternion interpolation or model inference.
- Copying the artificial fixture into this bundle preserved every file hash;
  read-only checks passed again on the copy. This is a local-copy check, not
  verification of actual SharePoint transfer or permissions.
- Frozen evidence, research logs, models, thresholds, scenes and the two existing
  local XR setting changes were preserved. Current source hashes describe this
  new checkpoint; earlier receipts continue to identify their earlier code.

## Recheck the small fixture

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/validate_accepted_source_visit.py results/week-10/keegan/source-integration-20261103-001/fixture/ledger.jsonl
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_accepted_source*.py'
```

For native checks, with the Editor closed, run Unity 6000.6.1f1 with
`-batchmode -nographics -projectPath ABSOLUTE_PROJECT -runTests -testPlatform EditMode
-testResults ABSOLUTE_NEW_XML -logFile ABSOLUTE_NEW_LOG`.
Add `-pufAcceptedSourceVisitFixtureRoot ABSOLUTE_NEW_FOLDER` to save the mixed
artificial visit. Inspect the completed XML; a process starting is not a pass.
The broader Python command is `python -B -m unittest discover -s tests -p test*.py`.

Actual Link tracking/selection, device interruptions, the SharePoint site and
backup/deletion behavior, CITI and consent preparation, PI source-retention review
and applicable institutional authorization remain open. The coordinated Word
working copies are kept outside public Git.

See [policy, file order and failure handling](../../../../docs/week10/week10-source-integration.md)
and [study status](../../../../docs/week10/week10-study-status.md).
