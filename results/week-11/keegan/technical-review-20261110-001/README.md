# Week 11 technical review and synthetic checks

November 10, 2026. Scope: staff-control safeguards, exact source replay,
read-only evidence reconciliation and reporting corrections. No new timing,
model-quality or reconstruction experiment, actual Quest Link capture,
human-motion collection or SharePoint access test is claimed.

## Outcomes

- 89 Unity tests passed: the earlier 85 plus three staff-control/focus cases and
  one all-fields/float-bits replay case across twenty synthetic seeds.
- 1,141 selected Python tests passed; no new Python cases were added. One stale
  archived-config test path was corrected. Dependency check passed.
- Artificial staff Stop and focus-loss visits closed correctly and passed the
  existing read-only Python ledger checker. Pose capture was disabled. These
  are callback/lifecycle tests, not observed mouse or live Link tests.
- Original source fields and processed float32 pose bits match exactly in the
  new native test. All quality fields, including the rate's double bits, match.
  Python has its separate format/link/metrics scope, not a quaternion replay.
- Will's completed human reviewer record and matching saved-score CSVs are
  identified, with the record's provenance/line-ending qualification preserved.
- Historical Week 6 timing is exported with actual arithmetic/model/recovery,
  execution order, release, machine and boundary labels. Values are unchanged.

## Files

- `python-tests.json`, `unity-tests.json`, `test-counts.csv`: included IDs and
  disjoint suite categories; do not sum old and new suite invocations.
- `test-history.json`: initial failures and the specific corrections, followed
  by the successful reruns. Detailed XML/logs stay private and unchanged.
- `staff-controls.json`: reconciled synthetic callback cases and their limits.
- `source-replay.json`: exact native comparisons and separate Python file checks.
- `reproduction-review.json`: completed record/release and unchanged CSV hashes.
- `historical-timing.csv`, `logistic-timing-for-slides.csv`: labeled historical rows.
- `acquisition-checklist.csv`: actual-path checks, all explicitly not run.
- `verification.json`: final source/evidence identities and preservation checks.

Public summaries use dates only. Relative sample/ledger times measure data
ordering and are not human work durations. Private execution records retain
their actual times; historical receipts are not rewritten.

See [the technical review](../../../../docs/week11/README.md) for commands,
interpretation and what remains operationally open. The next study readiness
decision still requires actual acquisition, storage and staff evidence.
