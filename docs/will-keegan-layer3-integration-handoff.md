# Layer 3 to classifier integration handoff

## Repository state

- Branch: `main`.
- Commit before this integration change: `00c0f20c2b06d56392963510928880cde374ba4c`.
- Before editing, the working tree was clean and `HEAD`, `origin/main`, and
  `origin/HEAD` all named that commit.
- Commit `00c0f20c2b06d56392963510928880cde374ba4c` contains the current PUF
  reconstruction, session establishment and key confirmation, Wire Protocol
  2.0 encoder, HMAC verification, replay protection, Tier 1 runner/tests, and
  latency reporting. Earlier commits `e1c4bf4775e1b4c63657167f46edc5d6e7e72cee`
  and `9bb890c84a23dfef2ecf087292e5d772328c92c5` contain the superseded decimal
  protocol and gate; `f6017f9e4a107c0adc09ac4721c37daa662bb4bc`
  documents that older integration.
- This change adds only the shared adapter, its tests, and this handoff. It does
  not change Layer 1, Layer 2, Layer 3, Tier 1, dataset, training, or classifier
  source.

## Supported entry points and ownership

- Layer 2: `puf_snn.reconstruction.enroll` and
  `puf_snn.reconstruction.reconstruct`; the single-run command is
  `run_layer2.ps1`, backed by `src/python/scripts/run_layer2.py`.
- Layer 3: `puf_snn.auth.sender.Sender`,
  `puf_snn.auth.verifier.Verifier`, and the establishment flow demonstrated by
  `src/python/scripts/run_layer3_demo.py`.
- Processed input adapter:
  `puf_snn.integration.processed_record_to_wire_window(record: dict) -> Window`.
  It accepts the JSON-decoded dict already used by the Quest processing and
  baseline code. It maps window ID, capture bounds, exactly 120 consecutive
  indexes, sample timestamps, three position values, four quaternion values,
  tracking flags, and the computed valid count/fraction.
- The adapter returns an immutable Wire-2 `puf_snn.auth.binary_window.Window`
  with explicit unbound placeholders. Dataset device/session/sequence fields
  are ignored. `Sender.seal_window()` owns and replaces device ID,
  cryptographic session ID, and sequence number.
- Accepted output adapter:
  `ExactlyOnceClassifierRelease(verifier, preprocess, classifier).deliver(result)`.
  The Window-to-record conversion is internal so it cannot be used as a public
  sender-side bypass. `deliver()` calls `Verifier.release_accepted()` and converts
  only the immutable Window supplied to that callback. It records the accepted
  event before preprocessing, preventing a retry from delivering the same result
  twice even if preprocessing or inference raises.
- The actual classifier API differs from the requested `[120, 8]` assumption.
  `src/python/scripts/train_baselines.py::record_to_features()` consumes the
  record and returns a flat `(840,)` NumPy array, equivalent to `[120, 7]`: three
  relative-position and four relative-quaternion channels. `tracking_valid` is
  retained in the authenticated record but is not a model feature. No model or
  training behavior was changed. Labels and split IDs are absent from the
  accepted record; identifiers and timestamps stay outside the resulting model
  tensor.

## Numeric conversion policy

At the processed-record boundary, each exact Python `int` or `float` is checked
for finiteness and rounded once using IEEE-754 binary32 round-to-nearest/even.
Negative zero is encoded as canonical positive zero. Booleans, strings, NaN,
positive or negative infinity, and binary32 overflow are rejected. This policy
lives in the adapter and does not weaken `F32.from_exact_float()` or use the old
eight-decimal JSON representation. On accepted output, each `F32.bits` value is
decoded to a Python float; widening from binary32 to Python binary64 is exact.
Existing finite synthetic JSON records can therefore be converted with the
usual single binary32 quantization at the authenticated boundary.

## Tests executed on 2026-09-23

All Python commands used Python 3.12.4 and set `src/python` as the source root:

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'src/python').Path
```

- New shared boundary:
  `.\.venv\Scripts\python.exe -m unittest tests.auth.test_classifier_integration -v`
  — 12 passed, 0 failed, 0 skipped.
- Known valid-format wrong credential:
  `.\.venv\Scripts\python.exe -m unittest tests.auth.test_session.SessionTests.test_real_six_error_miscorrection_no_retry_or_active_state -v`
  — 1 passed, 0 failed, 0 skipped. It confirms failed key confirmation, no
  retry, and no active session.
- Layer 1:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests/puf -v`
  — 47 passed, 0 failed, 0 skipped.
- Layer 2 reconstruction:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests/reconstruction -v`
  — 50 passed, 0 failed, 0 skipped.
- Layer 2 experiment/single-run workflow tests (the repository has no
  `tests/layer2_single_run` directory):
  `.\.venv\Scripts\python.exe -m unittest discover -s tests/experiments -v`
  — 21 passed, 1 error, 0 skipped. The existing
  `test_frozen_plan_rejects_seed_selection` is blocked because
  `configs/reconstruction_experiment_v1.json` is absent.
- Layer 3 authentication, including the new test:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests/auth -v`
  — 151 passed, 0 failed, 0 skipped.
- Tier 1 runner:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests/tier1 -v`
  — 40 passed, 8 errors, 0 skipped. The eight errors share the pre-existing
  frozen-baseline mismatch described below.
- Python/.NET Wire-2 parity:
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/auth/check_binary_v2_dotnet.ps1`
  — passed 11 scalar groups and 26 complete-window byte/SHA-256/HMAC vectors.
- Unity was not run: neither `Unity`/`Unity.exe` on `PATH` nor
  `C:\Program Files\Unity\Hub\Editor` was available.

The shared test proves valid delivery exactly once and exact feature equality
with the verifier-accepted payload. Modified payload, invalid tag, duplicate,
future gap, wrong device, wrong session, low quality with a valid tag, and
malformed envelope cases make zero classifier calls and leave accepted sequence
state unchanged. The existing authentication suite also covers stale packets,
inactive sessions, concurrent duplicates, and verifier precedence.

## Existing frozen-baseline blocker

`docs/layer3-baseline-v1-manifest.json` does not describe clean `HEAD`. Its
referenced `docs/authentication-v1.md` and
`docs/layer3-final-status-and-tier1-handoff.md` are absent. The working copies of
`schemas/auth-audit-v1.schema.json`, `schemas/authenticated-window-v2.schema.json`,
`src/python/puf_snn/auth/audit.py`, `src/python/puf_snn/auth/session.py`, and
`src/python/puf_snn/auth/verifier.py` do not match the manifest hashes. This
integration does not rewrite the frozen manifest or those sources. The Tier 1
runner consequently stops before execution in eight lifecycle tests. Windows
line-ending conversion also means committed blob hashes are not a substitute
for the runner's working-tree byte hashes.

## Tier 1 evidence and timing

The existing local completed evidence directory is
`results/week-4/will/authentication/tier1-20260923T205156Z-343cb4a2`. It is
ignored by Git and was not present in `origin/main` at the pre-change commit.
Its configuration is `configs/tier1_attack_experiment_v1.json`; within the run,
the raw attempts are `attempts.jsonl`, summaries are `attack_summary.csv`,
`control_summary.csv`, `supporting_summary.csv`, `reason_summary.csv`, and
`variant_summary.csv`, latency is `latency_summary.csv` and
`endpoint_latency_summary.csv`, audit evidence is `audit.jsonl`, and integrity
evidence is `manifest.json` plus `COMPLETE`. No plots are present; the CSV files
are the presentation-ready tables.

That recorded run scheduled all 700 trials. All 500 primary attacks and all 100
supporting cross-session attacks were rejected for the expected reasons; all 100
legitimate controls were accepted. It records zero state-mutation or
payload-release violations. The plan is reproducible from seed `20260923`, but
nonces, tags, and timings intentionally use nondeterministic OS/runtime inputs.

Recorded verifier authentication median/p95 values are:

- Legitimate accepted controls: 2.828100 ms / 3.119715 ms.
- Same-session replay: 2.825900 ms / 3.085100 ms.
- Prior-session replay: 0.892900 ms / 1.041710 ms.
- Cross-device substitution: 0.906750 ms / 1.104675 ms.
- Payload modification: 0.907450 ms / 1.039085 ms.
- Metadata modification: 0.912950 ms / 1.088285 ms.
- Supporting cross-session substitution: 0.908000 ms / 1.073065 ms.
- Accepted sender preparation: 2.213750 ms / 2.449960 ms.
- Accepted total Layer 3 (`sender_prepare + verifier_auth` per observation):
  5.104350 ms / 5.302070 ms.

The measurements came from Python 3.12.4 on Windows 11 10.0.26200, AMD64,
Intel64 Family 6 Model 151 Stepping 2, 20 logical CPUs, with galois 0.4.11,
NumPy 2.5.3, and jsonschema 4.26.0. For the classifier experiment, calculate
each accepted observation as `sender_prepare + verifier_auth +
classifier_preprocess + classifier_inference`, then summarize those totals.
Do not add independently summarized percentiles. `sender_hmac` is nested in
`sender_prepare`; KDF/session establishment is separate. Disk audit persistence
is also outside `verifier_auth` under the existing contract.

## Setup and commands for Keegan

No dependency was added. `pyproject.toml` remains the source of truth:
NumPy `>=2.0,<3.0`, scikit-learn `>=1.5,<2.0`, matplotlib `>=3.9,<4.0`,
jsonschema `>=4.23,<5.0`, and galois `==0.4.11`. Use:

```powershell
git switch main
git pull --ff-only origin main
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
$env:PYTHONPATH = (Resolve-Path -LiteralPath 'src/python').Path
.\.venv\Scripts\python.exe -m unittest tests.auth.test_classifier_integration -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/auth -v
```

Required runtime configuration is `configs/authentication_v1.json`; Tier 1 uses
`configs/tier1_attack_experiment_v1.json`. The missing reconstruction experiment
configuration and stale Layer 3 manifest must be resolved by their owners before
claiming a completely green historical regression or regenerating formal Tier 1
evidence.

## Legacy interface status and readiness

`src/python/puf_snn/auth/window_message.py`,
`src/python/puf_snn/auth/inference_gate.py`,
`schemas/authenticated-window.schema.json`,
`docs/authenticated-window-interface.md`, and
`results/week-4/shared/golden-vector/` are retained legacy decimal-protocol
source/evidence. Several are named by the frozen manifest or were authored by
Keegan, so they were not deleted or edited. New integration must use
`binary_window.py`, `schemas/authenticated-window-v2.schema.json`, and
`Verifier.release_accepted()` through `ExactlyOnceClassifierRelease`.

The authentication-to-classifier boundary is ready for the existing official
three-seed baseline that uses the current 840-value/120-by-7 preprocessing API.
It is not evidence for a 120-by-8 model contract. Remaining repository work is
to restore or deliberately supersede the missing reconstruction configuration,
repair and re-freeze the Layer 3 baseline manifest, publish or regenerate Tier 1
evidence from that exact baseline, and run Unity parity when Unity is available.
