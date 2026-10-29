# Week 9 bounded shared-noise calibration implementation readiness

Task 2F, October 28, 2026 (America/New_York). Owner: Will Wallace.
Base checkout: `457050b5361389364fbded464455f1f8684dbe5a`.

**Assessment: implementation ready for review and a separately authorized bounded
calibration run on the validated native Windows environment. Scientific execution
is not authorized by this report.** No 3,840-attempt calibration or formal study
ran, and no scientific operating sigma was selected. Tests are deterministic
implementation checks, not reconstruction-reliability findings or full-scale
resource qualification. No dependency was installed, production behavior changed,
historical evidence/configuration edited, commit made, or push performed.

## Decisions and implemented scope

The faculty-approved general methodological direction supplied for Tasks 2E/2F
is incorporated in the [study specification](week9-shared-noise-study-specification.md).
The 24-device allocation, every numerical gate, administrative resource caps,
and final-study allocation remain **proposed defaults pending final review**.
The shipped configuration explicitly says `proposed-pending-review`; neither
tests nor a qualifying unit fixture changes that approval status.

The new version is `week9-shared-noise-calibration-v1`, with evidence revision
`:evidence-v1` and rule revision `:proposed-rules-v1`. The config/schema freeze
the four sigmas, rho0, S/M only, allocation, seeds, rules, 10,000 resamples,
zero warmups, recording consumer, and provisional limits. CLI overrides cannot
retune thresholds, seeds or allocation. An amendment requires reviewed specification,
new frozen config/schema/source identities and a new approval record.

Unchanged reusable components are oscillator simulation/indexed noise, acquisition
and vote, BCH/credential format, independent credential verification/admission,
Authentication-v2, fresh endpoint construction, fixed window, recording consumer,
timing capture/instrumentation, and the existing strict protocol/timing validators.
The old runner's hard-coded condition/version/mode checks required new planning,
runtime/evidence adapters, schemas, analysis, controller binding and CLI. No old
guard was bypassed by relabeling a scientific run as nonformal or unit-test mode.

## Files delivered

All paths below are relative to the repository root. This task creates these
files and appends a clearly labeled implementation appendix to the existing
Task 2E specification; its scientific rules are unchanged.

- `configs/shared_noise_calibration_v1.json`
- `schemas/shared-noise-calibration-config-v1.schema.json`
- `schemas/shared-noise-calibration-plan-v1.schema.json`
- `schemas/shared-noise-calibration-attempt-v1.schema.json`
- `schemas/shared-noise-calibration-summary-v1.schema.json`
- `schemas/shared-noise-calibration-approval-v1.schema.json`
- `src/python/puf_snn/experiments/shared_noise_calibration_v1.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_runtime_v1.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_analysis_v1.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_evidence_v1.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_resources_v1.py`
- `src/python/scripts/run_shared_noise_calibration_v1.py`
- `tests/experiments/test_shared_noise_calibration_v1.py`
- `docs/week9-shared-noise-calibration-readiness.md` (this report)
- `docs/week9-shared-noise-calibration-dry-plan.json`
- `docs/week9-shared-noise-calibration-preflight.json`
- `docs/week9-shared-noise-calibration-validation.json`
- `docs/week9-shared-noise-study-specification.md` (appendix only in Task 2F)

Dry-plan/preflight/validation JSON files are implementation/readiness artifacts,
not scientific experiment bundles or completion markers. They are outside the
runtime required-source set to avoid self-referential receipt hashes. The runtime
set includes implementation, imported package sources, schemas, config, this
report, the full study specification, and focused tests/safety primitives.

## Workflow and commands

From the repository root, use the native interpreter already present on the
owner's machine. The CLI resolves the local package without installing it.

```powershell
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py plan
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py preflight
```

Both commands are read-only. `plan` builds/validates the entire canonical schedule,
including identities and operation counts. It does not generate a Device,
enrollment, PUF reading, BCH result or scientific selection. `preflight` additionally
checks required source availability/import origins and records current source,
environment and specification digests. It does not approve or qualify a host.

After a named reviewer approves the proposed rules/allocation/resources and the
exact source/config/plan/environment/specification identities, they must supply
an approval JSON conforming to the approval schema. Required fields are:
`schema_version=week9-shared-noise-calibration-v1:approval-v1`,
`authorization=RUN-3840-SHARED-NOISE-CALIBRATION-V1`, nonempty `approved_by`,
timezone-aware nonfuture `approved_at`, `rules_version`,
`allocation_rules_and_resources_reviewed=true`, the exact `resource_budgets`,
and all five digests emitted by preflight (`config_sha256`, `plan_sha256`,
`source_id`, `environment_sha256`, `specification_sha256`). These are explicit
local authorization assertions, not cryptographic signatures or remote attestation.
No completed approval file is supplied by this task.

Only after that separate authorization, the execution command is:

```powershell
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py run-calibration --approval-file PATH_TO_REVIEWED_APPROVAL.json --output results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-UNIQUE_LOWERCASE_TOKEN
```

Replace the placeholder with a new lowercase token. The command has **not** been
run in Task 2F. It launches one supervised worker and cannot launch final
evaluation. There are no formal/nonformal/resume/retry actions. `audit --output
PATH_TO_COMPLETED_BUNDLE` performs one additional replay pass outside timing and
adds no samples; it must use the exact frozen source/environment.

## Deterministic dry-plan accounting

The saved [dry-plan output](week9-shared-noise-calibration-dry-plan.json) records:

| Quantity | Planned count |
| --- | ---: |
| Independent groups / devices per group / total devices | 4 / 6 / 24 |
| Trials per device per sigma / candidate sigmas | 20 / 4 |
| Matched trial identities | 1,920 |
| S attempts / M attempts / total policy attempts | 1,920 / 1,920 / 3,840 |
| Experimental PUF measurements / runtime BCH decodes | 7,680 / 3,840 |
| Runtime votes / stored-source attempts | 1,920 / 0 |
| Execution enrollment references | 24 |
| Additional two-pass replay measurements / decodes / references | 15,360 / 7,680 / 48 |
| Samples added by replay / observations generated by dry-plan | 0 / 0 |

Canonical configuration digest:
`79a275d06a8a1997981484f15d27cb5e76b39fd2a28b660a4251ddc35e83e756`.
Canonical complete-plan digest:
`e5d4deaf8b944dd514fbdcf2bba31cd91ec5dc22e66478ca8a55701a594135ff`.
These canonical-object identities differ from raw-file byte hashes.

Every device-sigma cell has ten S-M and ten M-S blocks, deterministically shuffled
with schedule root 2026102802. Simulation root 2026102801 uses the specification's
phase/enrollment/measurement domains and calibration `w9c-` labels. The final
identity helper uses root 2026102811 and the final phase version; there is no
final generation/execution action. Unit fixtures use disjoint `w9u-` labels,
at most two groups/devices per group, two trials per sigma, and temporary outputs.

## Statistical and selection validation

The implementation resamples complete devices with replacement exactly 10,000
times using root 2026102803 and the specified phase/config/domain seed derivation.
One multiplicity vector applies jointly to both policies, all trials and all four
sigmas in each draw. Equal-device FRRs and paired Delta use percentile .025/.975
intervals with the inherited `(B-1)*p` linear interpolation. There is no calibration
attenuation/A calculation. Device and group C/D/I/W counts, FRRs, paired benefits,
both discordance directions, event coverage and delete-one-device/group summaries
are retained. Four-group sensitivity remains descriptive.

Every section 5 gate is implemented, including inclusive versus strict endpoints,
24 S failures/correct outcomes, 20 discordances, six-device/three-group coverage,
CI limits, delete-one-device minimum .01, three positive groups and no group
below -.02. Count-based decisions use exact rational arithmetic to avoid
floating-point equality accidents; CI endpoints retain the prescribed unrounded
percentile values. Lowest qualifying sigma wins; no qualification and incomplete
selection prohibition are explicit, with each failed gate returned. Rules are
never reapplied within bootstrap samples. Zero-failure degenerate intervals are
flagged, fewer than two devices suppress intervals, and undefined conditional
draws suppress the entire conditional interval rather than being discarded.

The passing selection examples in tests are hand-constructed summaries, not new
calibration outcomes. A `selection.json` produced inside a unit bundle is labeled
fixture-only and cannot authorize or select a scientific operating point. In a
future scientific bundle, selection is a candidate until the two-pass completion
marker exists; the receipt binds the complete analysis and named dated approval
to source/config/plan identities.

## Exact focused validation results

Set the package/test paths for these explicit suites:

```powershell
$env:PYTHONPATH='src/python;tests;.'
.\.venv\Scripts\python.exe -m unittest discover -s tests/experiments -p test_shared_noise_calibration_v1.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/tools -p test_profile_three_arm_resources_v1.py -v
.\.venv\Scripts\python.exe -m unittest puf.test_correlated_noise_v1 experiments.test_three_arm_auth_v1.PlanningTests experiments.test_three_arm_auth_v1.RuntimeTests -v
```

| Final relevant execution | Result | Reported test duration |
| --- | --- | ---: |
| New calibration fixture suite | 44 passed; 0 failures/errors/skips | 17.772 s |
| Existing Windows resource safety suite | 55 passed; 0 failures/errors/skips | 5.419 s |
| Existing noise + three-arm planning/runtime regressions | 62 passed; 0 failures/errors/skips | 12.747 s |
| Unique methods across these suites | **161 passed** | Not an experiment runtime |

An earlier 35-test iteration had one exact-float assertion failure
(`28.499999999999996` versus `28.5`); the assertion was corrected to a numerical
tolerance without changing the percentile convention. Its 35-test rerun passed
in 14.814 s. The expanded 44-test execution above supersedes that subset; do not
add repeat test counts to claim more unique validation coverage.

Coverage includes complete count/balance/seed checks with acquisition/decoding
forbidden in dry-plan, actual C/D/I/W measurement and reconstruction fixtures,
pre-HKDF wrong-credential refusal, first-read matching, signed/zero paired effects,
device multiplicities, deterministic bootstrap, all gate boundaries, no/lowest
qualification, missing/duplicate/mismatched rows, deterministic replay, source and
manifest corruption, forbidden outputs, interruption, first/second-pass failure,
atomic marker publication failure, final disk/deadline/partial-receipt refusal,
and a real newly adapted Windows worker refused before observation/output creation.
The inherited native safety suite additionally tests live peer/job containment,
heartbeat loss, controller death and descendant termination. The new controller's
successful-acceptance logic is tested with explicitly fake worker receipts and
metrics; it does not execute the scientific workload.

The complete new evidence integration fixture is only one device, two trials,
four sigmas and two policies: **16 unit attempts**, 32 readings and 16 decodes.
Its two checking passes add 64 replay readings/32 decodes/two references; its
standalone audit is another checking pass. Other tests use constructed faults
and synthetic analysis records. Temporary unit bundles are cleaned up. No unit
bundle is retained or pooled as scientific calibration data. Exact suite results
and post-validation file identities are recorded in
[validation metadata](week9-shared-noise-calibration-validation.json).

## Evidence and execution safety

Attempt records preserve the strict existing shape, newly versioned and narrowed
to S/M and four calibration conditions. Plan validation additionally regenerates
and compares the entire canonical schedule; summary validation recomputes the
entire analysis from replay-checked complete records. No weaker substitute for
semantic/replay validation is introduced by the smaller structural plan/summary
schemas. Independent verifier/admission/session/window/release counts remain
separate, with wrong candidates classified against truth only in the evaluator.

The new source list requires the real
`docs/archive/week8-three-arm-auth-tests.patch`; it does not edit the historical
list or manifests. Source/import-origin checks run before snapshot, per attempt,
and through finalization. The required files are snapshotted and hashed. Audits
check exact manifest membership, all file and snapshot hashes, source/environment
identity, canonical plan, complete paired coverage, actual operations, reconstructed
bits/credentials, protocol invariants, timing nesting, summary and selection.

Outputs are exclusive direct children of
`results/week-9/will/shared-noise-calibration-v1/`, with the calibration version
prefix. Existing/linked/alias/traversal/nested/historical paths are refused.
Scientific mode cannot borrow a unit output root or the old `RUN-150` token.
Runtime/evidence scientific entry points require a live peer-verified permit and
reviewed frozen approval, not a standalone string. Unit mode has a separate small
allocation cap and namespace.

The controller reuses the unchanged reviewed Windows primitives: kill-on-close
Job Object, actual native interpreter identity, OS process/private-memory and
free-resource samples, peer-PID-verified duplex pipe, exact job membership,
sampled-monitor heartbeats and worker watchdog. It adapts the launch to the new
CLI and binds config/output/approval/budgets to a saved request. The legacy
profiler's experiment loader, tokens and scientific workload are not reused.

Both semantic replay passes and manifest audit must succeed in the worker.
Scientific output remains incomplete until the worker exits successfully,
supervision and final resource checks pass, source/config/environment/manifest
are still frozen, and the complete receipt matches 3,840/7,680/3,840. The controller
stages its validation receipt, checks budgets again and publishes
`CALIBRATION_VALIDATED.json` last using an atomic rename. Failure to publish
restores the incomplete sentinel where possible and creates no valid marker.
Absence of the marker always means incomplete, even if interrupted in the tiny
sentinel-removal/marker-commit gap. No automatic resume, replacement draws,
outcome-based retry or final-evaluation action exists.

One completed checking pass is recorded separately from successful two-pass
finalization. Additional audits add checking work, not statistical samples.
Sidecars live separately under `tmp/week9-shared-noise-calibration-v1/RUN_NAME/`
and contain request, stdout/stderr, monitor/worker/resource and controller-validation
records. These files do not override a missing/invalid experiment completion marker.
On interruption, retain the complete partial namespace and disclose any unknown
unrecorded work; do not infer completion from a nearly full JSONL file.

## Environment, provisional resources and remaining gates

Validation used native Windows 11 `10.0.26200`, CPython 3.12.4 x64, galois 0.4.11,
NumPy 2.5.3, Numba 0.67.0, SciPy 1.18.1 and jsonschema 4.26.0. The sandbox account
could not access the owner's native interpreter directly; validation used the
existing environment through the approved execution boundary. The fallback MSYS
Python 3.12.7 lacks the required scientific packages and is **not** the validated
execution environment. No package installation or environment repair was made.

Provisional configuration limits are a 1,800-second worker/session workflow,
4 GiB sampled process-memory stop threshold (the reused monitor checks RSS,
private bytes and recorded OS peak RSS), more than 8 GiB free host RAM and more
than 1 GiB free disk, 512 MiB bundle growth, 1 GiB aggregate growth, .05-second
sampling and up to 2 seconds stop grace. Boundaries fail closed. These are
administrative defaults, not measured calibration requirements or guarantees.
Sampling/grace can permit transient overshoot; the job/lease stops unsupervised
work. Peak-memory, finalization and completion-time feasibility at scientific
allocation have not been established by the unit fixtures. The runtime budget
covers supervised worker startup through analysis/finalization/controller checks;
CLI imports and read-only approval/preflight work precede that supervised epoch.

The expected retained graph/storage risks from the specification remain: all
attempt records are held in memory and finalization parses another complete
graph. Hashing, instance validation, per-row flush/fsync and both replay passes
remain enabled. No optional streaming/hash/persistence optimization was introduced.
No storage/latency projection is promoted to an observed calibration result.

Before execution, a reviewer must approve the numerical rules/allocation/budgets,
name the operator/compatible host and dated approval, inspect the exact final
source/config/plan/specification/environment preflight digests, and verify free
RAM/disk plus the protected output/sidecar namespaces. Re-run read-only preflight
after any file/environment change; old identities cannot authorize changed bytes.
The [saved preflight](week9-shared-noise-calibration-preflight.json) is a readiness
snapshot, not a perpetual approval or host-fit certificate.

No scientific-method deviation was necessary. Implementation-only refinements
are isolated fixture labels, source-list path resolution, exact count-boundary
arithmetic, explicit approval schema and final controller marker commit. Existing
formal five-condition configuration, simulator/protocol/defaults and all historical
evidence remain unchanged. The historical timing provenance/ARM64 reproduction
questions remain outside this implementation and unresolved.

**Next authorized action is review, not execution.** Once a matching explicit
approval is supplied in a later task, the implemented command can perform exactly
one bounded calibration with full checking and supervision. A nonqualifying or
incomplete result must stop selection/final evaluation as specified. Any later
90,000/108,000-attempt study still requires separate implementation, resource
qualification and execution authority.
