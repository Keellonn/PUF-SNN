# Reconstruction Alternatives: separate Python 3.13.14 diagnostic

The unchanged formal-readiness module executed all 27 tests on CPython 3.13.14: **24 passed, two failed and one raised an error**. No tests were skipped. The three nonpassing outcomes stopped at the historical runner's explicit Python 3.12.4 requirement. This is a partial diagnostic result, not a 27-test compatibility pass, a complete regression result or a new formal reconstruction experiment.

## Scope and observed restriction

Only `tests/experiments/test_reconstruction_alternatives_formal.py` was loaded. The test inventory preserves all 27 unique identifiers. The preceding 1,035 selected tests remain a separate passing result; repeated executions of this 27-test module are not additive. The 48 legacy Tier-1-v1 tests remain historical evidence, not newly executed current-v2 validation.

| Check | Recorded outcome | Observed stopping point |
| --- | --- | --- |
| Invalid credential representation in preflight | Failure | The version refusal appeared before the expected credential-format refusal |
| Missing packages and wrong code parameters | Failure | The code-parameter subcase reached the version refusal before its expected refusal |
| Read-only preflight without provisioning or measurements | Error | `verify_packages()` rejected the interpreter version |

The saved local tracebacks were reviewed: all three report `Validated Python version mismatch` at the explicit `sys.version_info[:3] == (3, 12, 4)` check in `src/python/scripts/run_reconstruction_alternatives.py`. Required dependency versions matched. This identifies the observed barrier; it does not prove every operation behind that barrier compatible with 3.13.14 or rule out a later problem. No version check, original test, registered plan, configuration or scientific runtime was altered to force a pass.

## Source, fixture and environment boundary

The separate Git checkout was at `3bb91b204fb1fae717bce5aca789dfcf8b698cc8`. The scientific source snapshot identity was `dc75fbc339ff107e0286cc892c5b672125f594425c0ba2fcba2f6b98928c293d`. All 370 recorded source inputs and the original 18-file, 80-attempt NONFORMAL fixture matched their pinned bytes. Its manifest was `91b90a2de1df3aa8652dbaa1bb7a0a73527454014a915501b2f93497b7a6bc26`. The fixture is retained privately and is not part of this publication.

The exact original 31-file source snapshot was preserved. Eight files differed from ordinary Windows checkout bytes only in line endings. Git reported those verified representation changes, while content and staged diffs were empty; the diagnostic checkout is not described as a pristine worktree. Native Git HEAD, loaded project-module origins and dependency origins were checked. Source and fixture bytes, clean distribution metadata and installed project bytes were checked unchanged after execution.

The required packages were galois 0.4.11, numpy 2.5.3, numba 0.67.0, llvmlite 0.49.0, scipy 1.18.1 and jsonschema 4.26.0. The already verified CPython 3.13.14 environment was reused without installation. This is not a reproduction of the original Python 3.12.4 environment. Small synthetic test fixtures may provision enrollment material and exercise authentication; no full formal experiment or historical model retraining occurred. Test execution took 12.776 seconds, which is not a pipeline latency benchmark or research-hours claim.

## Preserved setup recovery

The first execution recorded 22 passes, two failures and three errors. Two errors were caused by missing Git provenance in an exported source copy; those two tests passed in the corrected checkout. Intermediate preparation attempts encountered a Windows path-length issue and an overstrict line-ending-status check before running tests. The source, original fixture, failed attempts and logs were retained. Correcting the diagnostic scaffolding did not change production code or erase the earlier outcomes.

## Published evidence and remaining decision

The four selected structured records and `observed-diagnostic-manifest.json` are byte-identical copies of the saved numeric/identity records. Their original manifest SHA-256 is `4a62e86de41fae13055d76fb74bf68524060da8b0c020e781e0972489de2bf88`. They contain repository-relative source references, counts, version identities and hashes. Absolute workstation paths, usernames, raw tracebacks, fixture payloads, environment payloads, checkouts and local orchestration scripts are excluded. The publication has its own manifest; `RECORDED.json` denotes this scoped evidence export, not passing all tests.

Full Python 3.13 formal-readiness support remains unvalidated. It would require a separately reviewed and versioned support change, or unchanged testing under the historical interpreter. This publication does not authorize either. Shared formal-evidence closure, reconstruction/control experiments and deployment requirements remain distinct pending work; no security-completeness or shared-release-complete claim is made.
