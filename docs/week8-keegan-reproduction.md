# Reproduce Keegan's Week 8 checks

This is a current-source validation handoff, not a verified original historical
archive or a standalone application release. Run from the project root in
PowerShell. Do not reset an existing working tree or overwrite a result folder.

The prepared handoff directory is
`results/week-8/keegan/handoff-20261022-002/`. Its code overlay preserves the
exact bytes of this session's nine new code/config/test/documentation files;
its receipt archive excludes private logs. `manifest.json` identifies both ZIPs
and every overlaid source file. Neither archive includes the dataset, model
payloads, environments, research-log hours or live cryptographic material.

For an independent reproduction before the final session commit is published,
start with a **new clone** at base commit
`c8a4053f8526b91dd856428fa0924d214f367106`, review the overlay paths/hashes and
copy those additions into that new clone. Do not extract over someone's active
working tree. Obtain the separately pinned dataset/models before preflight.
The overlay plus manifest is the candidate identity, not the base commit alone.
After the end-of-session commit is available, supply that exact commit as well.

## 1. Set up the current source environment

```powershell
Set-Location -LiteralPath 'C:\path\to\PUF-SNN'
$env:PYTHONPATH = "$PWD\src\python;$PWD\tests"
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\.venv\Scripts\python.exe -B -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
```

Change the checkout path for another machine. The observed profile is Windows
x64 / CPython 3.13.14 with NumPy 2.5.3, scikit-learn 1.9.1, CPU Torch 2.14.0+cpu,
galois 0.4.11, Numba 0.67.0, SciPy 1.18.1 and jsonschema 4.26.0. Complete pins
and hashes are in `requirements/week7/win-amd64-cp313-observed-hashed.txt`; the
download-only artifact recipe is `requirements/week7/download-wheels-hashed.txt`.
The historical root requirements file is not an equivalent environment lock.

For a fresh setup, use a new environment and the matching verified wheelhouse
with hash checking. Do not upgrade/substitute dependencies to hide a failure.
Earlier clean-environment work is described in
[release readiness](week7-release-readiness.md); this week's current-source
checks use the existing environment and are not a new installation claim.

## 2. Run focused developer checks

```powershell
& .\.venv\Scripts\python.exe -B -m unittest -v test_quality_dyadic test_quality_benchmark test_quality_differential test_week8_quality_validation
if ($LASTEXITCODE -ne 0) { throw 'Focused quality validation failed.' }
```

There are 73 selected test methods in this group: 26 + 28 + 6 + 13. The standalone
smoke executions overlap this group; do not sum repeated executions as distinct
coverage. These are fixtures, not scientific reliability samples.

For the broader root-discovery scope with a saved receipt:

```powershell
$testRun = 'regression-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& .\.venv\Scripts\python.exe -B tools/run_keegan_week8_checks.py --output "results/week-8/keegan/$testRun"
if ($LASTEXITCODE -ne 0) { throw 'Root-discovery checks did not pass; inspect the retained local log.' }
```

The receipt inventories actual test IDs, successes, errors, failures, skips and
non-package test subdirectories excluded by ordinary discovery. It is not a
claim that all historical experiment modules passed. Raw test output is in a
locally ignored `*.private.log`; share the sanitized summary separately.

Observed checkpoint `regression-20261022-001`: 1,085 selected/executed/passed
tests, zero failures, errors or skips, and no source drift. This count includes
the focused quality tests; it is not 1,085 plus 73 distinct tests.

## 3. Check frozen inputs before executing integration

```powershell
& .\.venv\Scripts\python.exe -B src/python/scripts/validate_week8_quality.py --preflight
if ($LASTEXITCODE -ne 0) { throw 'Frozen-input preflight failed; do not retrain or replace missing inputs.' }
```

This writes no result bundle and performs no session admissions. It verifies
the fixed protocol, dataset identity, existing model files/manifests,
training-only normalization, frozen validation thresholds, source split
ownership and the predeclared semantic controls.

Required local inputs are identified in `configs/week6_smoke.json`. They include
the original synthetic dataset, SNN-32 checkpoints, the saved conventional
storage refits and saved anomaly estimators. Some binary payloads are locally
ignored: a Git clone alone may not supply them. Obtain the exact approved
dataset/model handoff and verify hashes; do not fit replacements and call them
the same frozen models. Hash verification does not make an untrusted pickle
safe: use trusted project artifacts only.

## 4. Run the bounded frozen-model equivalence check

```powershell
$modelRun = 'quality-validation-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& .\.venv\Scripts\python.exe -B src/python/scripts/validate_week8_quality.py --output "results/week-8/keegan/$modelRun"
if ($LASTEXITCODE -ne 0) { throw 'Integration comparison failed; retain its INCOMPLETE directory.' }
```

The fixed protocol plans 360 controlled sessions, 180 arithmetic pairs and 180
cross-recovery downstream pairs. It runs three saved-model combinations, both
quality implementations and both existing recovery policies on 30 fixed
validation sources. Read fixtures are correctable; this is not a recovery FRR
study. It is not a new accuracy/recall estimate or latency benchmark.

The runner refuses existing/nested/linked output locations, records current
code/config hashes including uncommitted files, preserves partial failures,
checks all behavioral signatures and source/model/data hashes again, and emits
`COMPLETE` only after successful reconciliation. A parent commit alone is not
the current source identity while changes are uncommitted. Raw-byte line-ending
changes also change hashes: do not rewrite old manifests to conceal them.

No clean-commit prerequisite is imposed by this new runner. Existing historical
runners keep their original rules and result namespaces; do not modify or rerun
them just to satisfy this new workflow.

## 5. Review and handoff

Read [the decision and limitations](week8-keegan-validation.md). Compare the new
summary with the retained `quality-validation-20261022-001` checkpoint. Return
your source/config/environment identities and actual outcomes, including any
failures or skips. Equivalent behavior is the comparison target, not identical
random cryptographic packets or identical execution duration.

The current packet supports a scoped release candidate, not a complete shared
security release. A fresh-environment check and a second person's reproduction
must be labeled as completed only after someone actually performs them.

## End-of-session Git cadence

Review the complete diff once the session's implementation, tests, result
receipts and explanatory documentation are ready. Stage only the intended
project files and sanitized evidence. Preserve unrelated/user edits and keep
raw private logs, caches, environments and model payloads out of the commit.

Use one descriptive commit for the completed session, followed by a push when
requested. Do not commit or push automatically after each intermediate check.
An appropriate subject for this session would be:

`Validate exact quality checks with frozen models and document Week 8 tradeoffs`

Its body should describe the new differential tests, both recovery-policy
integration checks, actual regression result, frozen identities, retained
default, and the limits on timing/reliability claims. This guide does not execute
a commit or push.
