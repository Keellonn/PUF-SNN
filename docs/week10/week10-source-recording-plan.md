# Source recording and replay: first-half development checkpoint

November 3, 2026. The planned study acquisition route is **PC-hosted Unity through
Quest Link**, with application files saved on the laptop. This is a planning
choice, not a successful Link run or permission to collect research motion.

## Why the existing records need a change

The current logger saves accepted 120-sample windows and source-quality summaries.
The original source poses are discarded. Counts, rates and largest gaps cannot
reconstruct the complete sample timing, tracking sequence or original poses.
Those summaries therefore cannot reproduce every planned source-level timing,
tracking or perturbation analysis.

The proposal is to retain **accepted pre-resampling source recordings**, with
their original values, sample times and tracking/API flags, alongside processed
windows. This additional retention must appear in the protocol, consent, data
inventory and retention/withdrawal plan before study use. The PI still needs to
review it. It is not enabled by this checkpoint.

## Follow-up

The second group is now implemented as an optional development feature; see
[controller integration and file accounting](week10-source-integration.md). The
first-half description below retains its original checkpoint scope.

## The two work groups

1. **This checkpoint:** define a source-file candidate; test offline export and
   replay with artificial poses; independently check source metrics and output
   links; save evidence and document the acquisition choice.
2. **Later:** connect the reviewed policy to the live controller and visit plan;
   reconcile source receipts with accepted ledger outcomes; test interrupted
   multi-file writes; update the matching Word packet and operational readiness
   instructions. Verify actual Link and SharePoint behavior.

## Candidate format and boundaries

`quest-accepted-source-candidate-v1` is a single JSON record with a final newline.
It is marked `synthetic_development_only`. `planned_acquisition_mode` identifies
the intended route, not the method used to generate the artificial test data.

The header identifies the processing version, device/session/trial codes, prompt
label, sequence number and split. Source samples retain:

- Capture timestamp in integer nanoseconds from the capture stopwatch.
- Three position components in metres and quaternion components in x/y/z/w order.
- The original tracking-valid flag, tracking-state bit mask, and availability of
  the tracking flag/state APIs.

Float values are stored as their signed 32-bit IEEE-754 bit patterns, so writing
and reloading the candidate does not round the captured float values. This is a
file encoding choice, separate from the earlier integer quality-check optimization.
Pose units, coordinate frame and existing quality rules stay as documented in the
current processor. The candidate limits one record to 20,000 samples and 16 MiB;
these are development file limits, not a measured headset sampling limit.

The native exporter requires an accepted outcome and reruns the existing processor
before writing. The reproduced processed window must match the supplied window.
Rejected, stopped or failed outcomes produce no source file. Existing output files
are refused. Unity replay checks the processed window and source metrics after
reloading the exact source values.

The separate Python checker validates the exact field sets, identifiers, numeric
encoding, source timing/gaps, summary metrics, processed-window identity and the
60 Hz target grid/tracking brackets. It does **not** independently implement Unity
quaternion interpolation or model predictions. Native replay is the evidence for
processed-pose matching. Neither check is a live-ledger integration test.

## Later live-file accounting

The current live ledger and source-quality headers explicitly say `raw_retention:
not_saved`. A live source-retention feature must introduce a declared, versioned
policy and linked receipts; it must not quietly reuse that statement while saving
new motion fields. No scene, controller or build setting enables this prototype.

An accepted-source export must be linked to a durable accepted ledger outcome.
An interrupted write or missing receipt must be reported as incomplete/invalid,
not reconstructed into a successful trial. That integration belongs to the second
work group and is not implemented here.

Preserving an incomplete ledger or pose-free diagnostic summary is different from
retaining interrupted motion. Rejected/stopped motion remains excluded under the
proposal. Any orphaned/partial file containing poses needs a defined restricted
review/deletion procedure and must not be treated as a harmless diagnostic file.
The final procedure must match the PI-reviewed packet and verified storage rules.

## PC-hosted acquisition workflow to verify

Quest 3 tracking/controllers -> Meta Link/OpenXR on the laptop -> Unity capture,
quality processing and coded files in `Application.persistentDataPath/puf-snn/`
-> verified copy to restricted VT SharePoint -> offline analysis on an authorized
computer. Actual local path, accounts, permissions, temporary copies and backup
behavior must be recorded on the study machine.

Capture times currently mark the laptop stopwatch when Unity reads the pose;
they are not independently measured headset sensor-exposure times. Link timing
includes a PC-hosted acquisition path and does not establish standalone headset
CPU latency or motion-onset-to-decision latency. App-created files and underlying
Meta/platform processing must be described separately.

Only synthetic inputs/non-human bench checks are in scope now. CITI completion,
protocol instruction, consent rehearsal, PI authorization and the applicable
written HRPP determination/IRB approval remain prerequisites for study activities.

## Commands for this checkpoint

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_accepted_source.py
.\.venv\Scripts\python.exe -B src/python/scripts/validate_accepted_source_candidate.py results/week-10/keegan/source-replay-20261103-001/fixture/accepted-source.json results/week-10/keegan/source-replay-20261103-001/fixture/windows.jsonl results/week-10/keegan/source-replay-20261103-001/fixture/source-metrics.json
```

Native tests use Unity 6000.6.1f1 and the existing EditMode test assembly. The new
class is `PufSnn.QuestLogger.Tests.AcceptedSourceCandidateTests`. Add
`-pufAcceptedSourceFixtureRoot ABSOLUTE_NEW_FOLDER` to export the artificial native
fixture. Keep the Editor closed during a headless run. Raw XML/logs remain local;
the public checkpoint contains a sanitized summary and artificial fixture only.

For a new native run, with the Editor closed:

```powershell
$sourceRun = Join-Path $env:TEMP ('puf-snn-source-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sourceRun | Out-Null
& 'C:\Program Files\Unity\Hub\Editor\6000.6.1f1\Editor\Unity.exe' -batchmode -nographics -projectPath "$PWD\src\quest-logger\QuestLogger" -runTests -testPlatform EditMode -assemblyNames PufSnn.QuestLogger.EditModeTests -testResults "$sourceRun\native.xml" -logFile "$sourceRun\native.log" -pufAcceptedSourceFixtureRoot "$sourceRun\fixture"
```

Unity may return control before the run ends. Check the completed XML for the
actual result before running the Python checker on the three exported fixture
files. The fixture directory must be new; the exporter refuses existing files.
