# Week 7: expanded selected-test validation

At source commit `3bb91b204fb1fae717bce5aca789dfcf8b698cc8`, the 964-case root discovery and four explicitly selected supplemental modules passed in a separate Windows source checkout using the previously verified external CPython 3.13.14 environment. All 1,035 executed tests passed with zero failures, errors, skips, expected failures or unexpected successes. This covers 58 imported test modules, not every repository test module or a complete shared release.

## Executed scope

| Group | Tests run | Scope |
| --- | ---: | --- |
| Root discovery | 964 | Existing auth, reconstruction, model, data, pipeline and reporting tests |
| Credential-verifier experiment harness | 7 | Synthetic admission counters, evaluator separation, output restrictions and accounting |
| Reconstruction experiment harness | 22 | Small synthetic fixtures, count/statistical accounting, isolation and evidence integrity |
| Reconstruction-alternatives experiment harness | 17 | Registered plan arithmetic, paired read identities, fixture scoring and nonformal evidence safeguards |
| Current-v2 Tier-1 harness | 25 | Plan/schema checks, fail-closed preflight, finite nonformal reason/state/recovery and inference-release checks |
| Total selected scope | 1,035 | All five groups passed without skips |

The 71 additional tests were not included by ordinary root discovery under the non-package `experiments` and `tier1` folders. They were loaded explicitly without editing the original tests or adding package markers. The original 964-case result remains a separate historical scope; it is not retroactively relabeled as all-folder coverage. `test-inventory.json` preserves unique test IDs, module counts, imported-file coverage and the two predeclared unrun modules.

## Unrun modules and remaining inputs

- `tests/experiments/test_reconstruction_alternatives_formal.py` reads the absent original 80-attempt smoke fixture at `tmp/week6-reconstruction-alternatives-smoke-001`. Its pinned manifest is `91b90a2de1df3aa8652dbaa1bb7a0a73527454014a915501b2f93497b7a6bc26`. The fixture includes synthetic enrollment/helper truth and was intentionally excluded from the shareable handoff. Use an approved private transfer and verification of the saved originals, or a separately reviewed, versioned self-contained test redesign. No substitute smoke run, patched fixture or waived hash gate was used.
- `tests/tier1/test_tier1.py` depends on the historical Layer-3 v1 baseline and its supporting plan. The current checkout has 29 missing or byte-mismatching entries against the 32 historical pins, and lacks `docs/tier1-attack-experiment-plan.md`. Byte mismatches can include line-ending differences as well as source changes; they are not automatically security defects. Evaluate the historical source boundary separately or version a current-v2 redesign. The old pins were not changed to force a pass.

These two modules were not executed and are not counted as passing or as runtime skips. No all-module, full-regression or security-completeness claim is made. Current-v2 finite implementation tests do not prove the protocol secure or establish a general forgery bound.

## Environment, source and preservation checks

The test checkout was pinned to `3bb91b2`, with Windows `core.autocrlf=true`, the four byte-preserved compatibility documents and disabled inherited Git configuration/hooks. The installed package/build inputs matched the earlier clean setup at `c62ff15812c9f7bbf3aff56be3f38ba0f225f6f1`. The setup manifest remains `78b1934024e7068c53292329f80fba192bc197c5d1f89c83b14e0f535b8d4736`; no installation or environment replacement occurred.

Project-module origins resolved to the new checkout and dependency metadata to the verified environment. Exact tracked test inputs, installed package bytes, original environment metadata and the working repository were checked unchanged after execution. Ignored frozen models, generated data, original smoke fixtures and private Windows traces were not copied into the test checkout. Unit fixtures can fit small models, perform synthetic measurements, invoke inference/authentication and exercise timing assertions; this is not retraining historical models or rerunning a formal FRR, attack or latency study.

The selected test groups took 307.043 seconds in aggregate. This is test-execution duration, not a pipeline-latency benchmark, engineering-target result or attributable work-hours. Standalone installed-wheel application operation remains unvalidated.

## Published records and claim boundary

The four structured test records and `observed-expanded-tests-manifest.json` are byte-identical copies of the saved local records. The original manifest SHA-256 is `4b240ef9d9637b01c0e1fed224e8a1a24bfbd11cd5f692803c7071979426667b`; its four file pins reconcile. The new publication manifest separately covers those records, this explanation, line-ending rules and provenance. `COMPLETE` denotes only the scoped metadata export, not a complete shared release.

The checkout, environments, caches and raw local logs remain outside Git. This reporting step does not change source code, original tests, models, thresholds, protocol defaults, historical experiments, slides or research-log hours. Full shared formal-evidence closure/reconciliation, the two unrun modules and the remaining reconstruction/control questions are not resolved by this test result. Existing qualified architecture and engineering-target conclusions remain unchanged.
