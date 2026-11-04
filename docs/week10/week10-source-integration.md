# Accepted source recording and visit accounting

This November 3 checkpoint connects the source-file format to the trial controller
as an **optional development feature**, tested with artificial poses. It starts off
in code, and neither saved scene enables it. It does not authorize research
collection or establish that Quest Link tracking and controls work.

## Declared policy

With retention off, new visits keep the existing `quest-trial-ledger-v1` and
`quest-source-quality-v1` headers with `raw_retention: not_saved`. Historical
files and result bundles remain unchanged and readable.

With retention explicitly enabled before a development visit, both headers use
v2 and `raw_retention: accepted_source_development_only`. A separate
`quest-accepted-source-visit-v2` manifest declares the same policy, the processing
version, coded identities and exact companion filenames. Source files use
`quest-accepted-source-v2`, marked `development_only`. The acquisition field is
still named `planned_acquisition_mode`; synthetic fixtures are not Link captures.
Neither policy is an approved human-study recording mode. A final research mode
must reflect the reviewed protocol and written authorization before use.

For a permitted development test only, enable **Retain Accepted Source For
Development** on QuestTrialController, or call
`SetDevelopmentSourceRetention(true)` before the visit starts. Changing the
policy during a visit is refused. Recording authorization is a separate control
and still starts off. Do not enable these controls to record research motion
while institutional review and staff preparation remain unfinished.

## Files and write order

Files are saved on the computer hosting Unity, below its actual
`Application.persistentDataPath/puf-snn/` directory:

| File | Content |
|---|---|
| `<visit>-trials.jsonl` | Plan and durable trial events |
| `<visit>-windows.jsonl` | Accepted 120-sample processed windows |
| `<visit>-source-quality.jsonl` | Pose-free source summaries, including rejections and stops |
| `<visit>-accepted-source.jsonl` | Retention declaration, accepted-source receipts and closure |
| `<visit>-accepted-source/<trial>.json` | Original source poses, timestamps and tracking/API flags for an accepted trial |

The controller saves the source-quality summary and completed event first. For a
quality-accepted trial it checks exact source replay in memory, saves and flushes
the processed window, saves and flushes the ledger acceptance, writes and flushes
the source file, then appends its hash/length and window link to the manifest.
The manifest closes only after the ledger closes and their accepted sets match.

The write order does not make several files one atomic transaction. A failed
acceptance append can leave an unreferenced processed window, but no source file.
A source or manifest failure after acceptance can leave an accepted trial without
a complete source receipt. Preserve and flag that discrepancy; do not turn it
into a successful source export or change the observed acceptance into a quality
rejection. The controller stops further trials after a write failure.

Rejected and stopped trials save only their coded accounting and numerical
quality summaries, without source or processed pose files. Their raw buffers are
used in memory for those summaries. A crash can leave a partial source file from
an already accepted trial; that file contains motion and must not be treated as
a pose-free diagnostic. Restrict access, exclude it from analysis, document it
and follow the reviewed deletion/incident procedure. The checker never deletes,
repairs or adopts files automatically. A new visit must use a new code.

## Counts and read-only checks

The existing trial counts remain stage counts:

- scheduled = attempted + not_started
- attempted = completed + stopped + unfinished_attempts
- completed = accepted + quality_rejected + processing_failed + pending_processing

Report source availability separately: accepted trials, valid source receipts,
missing source receipts and unreferenced/partial files. `COMPLETE` requires a
closed ledger, complete source summaries, matching window and source hashes,
correct identities and no extra source files. It means file accounting passed,
not that the visit met an accuracy, safety, tracking or timing target. A missing
source after a recorded acceptance invalidates this file bundle for source
analysis; the acceptance count remains visible.

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/validate_accepted_source_visit.py ABSOLUTE_PATH_TO_TRIAL_LEDGER
```

The normal trial-ledger validator also checks source files automatically for v2
plans. Legacy v1 checks remain unchanged. Python checks identities, strict fields,
file hashes, source timing/gaps, metrics and resampled tracking brackets. Unity
performs exact processed-pose replay; Python does not independently implement
Unity quaternion interpolation or regenerate model predictions.

## Processing and study boundaries

Source files retain the captured float32 values as integer bit patterns, without
adding decimal rounding. Processing rules, saved models, alert cutoffs and
authentication/reconstruction policies are unchanged. The development exporter
caps a record at 20,000 samples and the reader at 16 MiB. Export refusal is a file
or processing failure, not a new sensor-quality rejection rule.

These extra replay and durable-write steps have not been benchmarked as a new
sensor decision path. They do not update the historical 20 ms claims. Keep
acquisition, processing and durable I/O separately timed in a future benchmark.

The proposed study uses a laptop through Quest Link. Accepted source retention
must be reviewed explicitly in the protocol, consent, inventory and withdrawal
plan. VT SharePoint is selected, with PI custody; the actual site, access roles,
encryption, versions/backups and deletion behavior still need verification.
No automated source check proves those operational controls.

See the [second-group results](../../results/week-10/keegan/source-integration-20261103-001/README.md)
and the [current study status](week10-study-status.md).
