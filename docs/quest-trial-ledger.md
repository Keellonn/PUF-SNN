# Quest trial ledger

This is a software accounting change, tested with artificial poses. Recording
remains disabled by default. It is not authorization to collect participant data.

## What is saved

The controller now creates two files per coded visit, under
`Application.persistentDataPath/puf-snn/`:

- `<visit_code>-trials.jsonl`: the full planned schedule, followed by trial events.
- `<visit_code>-windows.jsonl`: accepted, resampled windows only, when any exist.

The plan is written before prompting or recording. It records participant,
visit, device and session codes; trial IDs and prompted tasks; block and trial
indices; the shuffled schedule and seed; processing/build identity; output
filename; and the time, retention and repeat policies. Use assigned codes, never
names, emails or a credential. `processingVersion` must be filled with the actual
build/configuration identity; it is not automatically a complete freeze manifest.

Every appended line is flushed with `FileStream.Flush(true)` before its
in-memory state advances. Existing visit files are refused rather than replaced
or resumed. A failed ledger append stops the controller and leaves the existing
evidence incomplete. This was tested with injected write failures and incomplete
files on Windows; Android storage and sudden power-loss behavior remain untested.

## Trial states and counts

The ordinary path is:

`scheduled -> prompted -> start_requested -> recording_started -> completed`

Completion is followed by exactly one of `accepted`, `rejected` or
`processing_failed`. Completion means the capture interval ended, not that the
window passed quality checks. A `rejected` event is a quality refusal;
`processing_failed` is a software/storage failure. Neither is an anomaly alert.

| Count | Meaning |
|---|---|
| Scheduled | Every trial in the plan, including trials never started |
| Attempted | A durable `start_requested` event exists |
| Recording began, confirmed | `BeginCapture` returned and a `recording_started` event was saved |
| Recording began, uncertain | Start was requested but confirmation is absent; do not assume capture began |
| Completed | The capture interval finished and its source-sample count was saved |
| Accepted | A completed trial has a saved-window receipt |
| Quality rejected | A completed trial failed the window processor, with a reason code |
| Processing failed | A completed trial could not finish processing or writing |
| Stopped | An attempted trial was stopped before completion |
| Skipped | The trial was deliberately skipped before a capture request |
| Not attempted | A remaining scheduled/prompted trial was closed without a capture request |

The reconciler also retains unfinished attempts, pending processing and unresolved
scheduled trials. Its partitions are:

```
scheduled = attempted + not_started
attempted = completed + stopped + unfinished_attempts
completed = accepted + quality_rejected + processing_failed + pending_processing
```

`not_started` includes skipped, not-attempted and still-unresolved scheduled or
prompted trials. These are overlapping milestones, not columns to add together.

The controller's current proposal allows no repeats and caps the schedule at
75. Three blocks with five trials per class produce three balanced blocks of
25; the saved order is shuffled within each block. The software default remains
one block with one trial per class. Neither default is an approved study design.

## Skips, stops and execution notes

- `SkipCurrentTrial()` skips during the prepare interval, or stops an active
  capture with a separate reason. There is no automatic replacement trial.
- `StopTrialSession()` accounts for the active trial and all remaining scheduled
  trials before saving `visit_closed`, if writing remains possible.
- Pause, disable, quit and the logger-session time limit use separate reason
  codes. The time limit includes logger breaks; it is not the full visit budget
  for consent, fitting and removal.
- Between blocks, the controller waits for `ContinueAfterBreak()`.
- `LogExecutionNote(code)` accepts `participant_reported_mistake`,
  `observed_nonexecution`, `late_movement` or `movement_after_interval`. Notes
  preserve the prompted label and the original outcome. A model prediction never
  relabels a trial.

The public controls still need scene/UI wiring and an authorized usability check.
Do not treat EditMode tests as proof that the stop/skip procedure works on Quest.

## Retention proposal

Unresampled source poses stay in memory during processing; this implementation
does not save them. Rejected/stopped trials retain coded ledger metadata and
reasons, not raw motion. Accepted resampled motion is saved. No repeat is allowed
by this implementation (`repeat_policy: none`).

This is the proposed policy for PI review. It must match the revised protocol,
consent and data inventory before research collection. The trial ledger is
research data, not a public log. The committed examples are artificial fixtures.

## Saved-window receipts and interrupted writes

An acceptance references the filename, window ID, byte offset, exact line length
and SHA-256 of the saved UTF-8 line, including its final newline. The window is
flushed before the acceptance event. A crash between these writes can leave an
orphaned window; the reconciler reports it and does not invent acceptance.
Torn files are preserved, not repaired or silently resumed.

These hashes detect mismatches when compared with the retained ledger. They are
not authentication, device attestation or protection against someone rewriting
both files. The ledger does not change PUF recovery, HMAC or inference policy.

## Read-only checks

From the repository root, using the project environment:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_trial_ledger.py
.\.venv\Scripts\python.exe -B src/python/scripts/validate_trial_ledger.py results/week-9/keegan/logger-ledger-20261027-001/mixed/ledger.jsonl
.\.venv\Scripts\python.exe -B src/python/scripts/validate_quest_log.py results/week-9/keegan/logger-ledger-20261027-001/mixed/windows.jsonl
```

The ledger checker reports counts, event order, file references, hashes,
prompt/window identity mismatches and orphan rows. It does not replace full
window schema/quality validation, which is the third command above.
`--output NEW_REPORT.json` saves a new report and refuses to overwrite a file.

Exit 0 / `COMPLETE` means the closed ledger and file accounting reconcile, even
if a visit ended early with recorded skips or stops. `INCOMPLETE` means a valid
prefix remains open. `INVALID` means an accounting/file problem was found.
None of these statuses establishes tracking performance, model accuracy, readiness
for Phase 2 or institutional approval. Counts after a corrupt record describe
only the valid prefix; an unreadable plan yields no denominators.

Native tests run in the Unity version pinned by `ProjectVersion.txt`, with the
editor otherwise closed:

```powershell
$unityEditor = 'C:\Program Files\Unity\Hub\Editor\6000.6.1f1\Editor\Unity.exe'
& $unityEditor -batchmode -nographics -projectPath "$PWD\src\quest-logger\QuestLogger" -runTests -testPlatform EditMode -assemblyNames PufSnn.QuestLogger.EditModeTests -testResults "$env:TEMP\quest-ledger-tests.xml" -logFile "$env:TEMP\quest-ledger-tests.log"
```

Unity may return control before tests finish. Read the completed XML rather than
the launcher exit code. Keep raw logs/XML local because they can include machine
paths. The current sanitized results are linked in the Week 9 results index.
