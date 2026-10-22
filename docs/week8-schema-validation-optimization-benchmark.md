# Week 8 — Schema Validation Optimization and Comparative Resource Benchmark

**Owner:** Will Wallace
**Week:** 8
**Date:** October 21, 2026
**Status:** Complete — Optimization Implemented, Independently Reviewed, and Benchmarked
**Experiment:** `week8-three-arm-auth-v1`
**Scope:** Nonformal Three-Arm Authentication and Evidence-Processing Infrastructure

## Executive Summary
During Week 8, resource profiling of the three-arm simulated PUF authentication experiment identified redundant JSON Schema validation as a major computational bottleneck.

The initial supervised resource benchmark completed 150 authentication attempts in **142.875 seconds**. Instrumentation revealed that the experiment repeatedly parsed and validated unchanged JSON Schema definitions during attempt recording and evidence reconciliation. A total of 459 schema-definition checks were observed, consuming approximately 97.8 seconds of inclusive measured time.

To address this overhead, a bounded, process-local validator cache was implemented. The cache reuses previously checked schema definitions and validator objects while preserving every required instance-validation operation, source-integrity check, and evidence-reconciliation pass.

Following regression testing and an independent source review, a second supervised benchmark was conducted using the same experimental configuration, allocation, and resource limits.

The optimized benchmark completed in **48.734 seconds**, representing,
- 65.9% reduction in observed total runtime
- 2.93x observed speedup
- 98.9% reduction in schema-definition checks
- 88.7% reduction in evidence-finalization time

Both benchmark sessions were accepted by the resource profiler. Each completed 150 arm attempts and two evidence-reconciliation passes, with zero unauthorized inference releases.

These findings demonstrate a substantial improvement in pilot-scale experimental infrastructure efficiency. They do not establish full-scale formal-study feasibility or statistically generalizable runtime performance.

## Experimental Context

### Three-Arm Authentication Experiment

The Week 8 experiment compares three credential-source mechanisms,
- Single-Read PUF (`single-read-v1`): Obtains one noisy simulated PUF response and performs BCH reconstruction to recover credential material
- Majority-3 PUF (`majority-3-v1`): Obtains three noisy simulated PUF responses, performs bitwise majority voting, and applies BCH reconstruction
- Stored-Provisioned Credential (`stored-provisioned-v1`): Retrieves the enrolled credential from a trusted software record without runtime PUF measurements or BCH decoding

All three methods use the same downstream Authentication-v2 implementation, including independent credential verification, admission authorization, HKDF-based session establishment, mutual confirmation, authenticated sensor-window processing, and controlled inference-release authorization.

The third arm provides a non-PUF credential-source control for comparing reliability and implementation costs. It does not bypass authentication or establish security equivalence with a physical PUF.

### Nonformal Benchmark Allocation

The resource benchmarks used the approved nonformal pilot configuration.
| Parameter | Value |
|---|---:|
| Simulated populations | 1 |
| Simulated devices | 1 |
| Trials per noise condition | 10 |
| Noise conditions | 5 |
| Authentication arms | 3 |
| Matched trial-condition identities | 50 |
| Total authentication attempts | 150 |
| Standalone evidence audits | 0 |

The five configured conditions were independent nominal noise, independent stress noise, common-mode control, differential correlation at rho = 0.50, and differential correlation at rho = 0.90.

The resource benchmarks reused the same deterministic scientific configuration and scheduling rules. They were conducted to measure experimental infrastructure performance, not to increase the independent statistical sample size.

Formal execution remained disabled.

## Initial Resource Benchmark

### Baseline Execution
The initial supervised resource benchmark was conducted on October 21, 2026.
**Session identifier:** `first-20261021-01`
The benchmark executed one complete 150-attempt nonformal bundle under the independently reviewed Windows resource profiler.
The profiler measured execution wall time, process memory, file operations, schema validation, source hashing, evidence recording, and finalization.
The session completed successfully,
- Profiler `success: true`
- Profiler `state: accepted`
- One completed worker
- 150 recorded authentication attempts
- Two completed evidence-validation passes
- Zero unauthorized inference releases
- Zero reported resource violations

### 3.2 Baseline Performance
| Measurement | Observed Result |
|---|---:|
| Total session wall time | 142.875 s |
| Schema self-check calls | 459 |
| Schema self-check inclusive time | 97.799 s |
| Week 8 schema-validation inclusive time | 103.219 s |
| Evidence-finalization inclusive time | 71.528 s |
| Two reconciliation passes, combined inclusive time | 68.396 s |
| Sampled peak private memory | Approximately 1.40 GiB |
| Explicit fsync calls | 161 |
| Explicit fsync cumulative time | Approximately 0.195 s |
| Evidence-bundle files | 97 |

Inclusive measurements overlap because some operations execute inside other measured operations. Their durations must not be summed as independent contributors to total wall time.

The results indicated that repeated schema-definition validation, rather than file synchronization, was the dominant measured performance issue.

## Root Cause Analysis

### Original Validation Sequence

Before optimization, both the Week 7 and Week 8 study modules used a validation sequence equivalent to,
- Read the JSON Schema file
- Strictly parse the schema JSON
- Execute `Draft202012Validator.check_schema(schema)`
- Construct a new validator object
- Execute `list(validator.iter_errors(instance))`
- Raise the existing validation error when the instance is invalid

The distinction between steps 3 and 5 is central.
**Schema-definition validation** confirms that the schema itself conforms to the Draft 2020-12 meta-schema.
**Instance validation** checks whether an experiment configuration, plan, attempt, or summary satisfies that schema.
The schema definitions generally remained unchanged throughout a run, but the original implementation repeated schema parsing and meta-validation on every instance-validation request.

### Source of the 459 Schema Checks

The supervised 150-attempt workload produced the following validation operations,
| Validation Target | Calls |
|---|---:|
| Week 7 and Week 8 configuration checks | 4 |
| Plan validations | 3 |
| Attempt validations during append | 150 |
| Attempt validations during first reconciliation | 150 |
| Attempt validations during internal-audit reconciliation | 150 |
| Summary validations | 2 |
| **Total** | **459** |

All 459 instance validations were required by the existing evidence lifecycle.
However, repeating definition-level meta-validation for every call was unnecessary when the corresponding schema bytes had not changed.

### Validator Construction Overhead

The original profiler recorded approximately 2.7 million instrumented validator-construction calls.
This count includes recursive construction within the installed `jsonschema` implementation while traversing schemas and instances. It does not represent 2.7 million experiment records or application-level validator objects.
The high number was consistent with repeated meta-schema traversal.
The optimization therefore targeted redundant definition checking and top-level validator construction rather than eliminating record validation.

## Optimization Implementation

### Shared Validator Cache
A shared validator factory was introduced into the inherited Week 7 experiment module and reused by the Week 8 experiment.
The implementation uses a process-local least-recently-used cache with a maximum capacity of 16 successful entries.
Each cache entry is identified by,
- The exact immutable bytes of the JSON Schema definition
- The validator class used to interpret that definition

The cache does not rely on a filename, modification timestamp, file size, or digest-only identity comparison.

### Cache Operation
Every public schema-validation call still reads the current schema file.
On a **cache miss**, the implementation,
- Parses the schema using the existing strict JSON parser
- Performs the Draft 2020-12 schema-definition check
- Constructs the validator
- Stores the successfully checked validator in the bounded cache
- Performs instance validation

On a **cache hit**, the implementation,
- Reuses the previously checked schema and validator
- Performs complete instance validation using `iter_errors`
- Retains the original validation-result and exception behavior

Only schema-definition preparation is reused.
No experiment-instance validation result is cached.

### Cache Invalidation and Failure Behavior

Changed schema bytes select a different cache entry, including whitespace-only changes.
Missing or unreadable schema files fail before cache lookup. Malformed JSON, duplicate keys, nonfinite constants, invalid encoding, and invalid schema definitions continue to raise their existing exceptions.
Failed schema parsing or validator construction does not populate the cache.
Restoring previously checked, identical schema bytes may safely reuse the earlier cached validator under the currently supported schema semantics.
Cache entries remain available until LRU eviction, explicit clearing, or process termination.
No validator cache is persisted to disk.
The current Week 7 and Week 8 schemas contain no external JSON Schema references or mutable registry dependencies. Future changes introducing those capabilities would require renewed cache-identity review.

### Preserved Integrity Guarantees
The optimization preserves,
- Every required configuration validation
- Every required plan validation
- Every attempt validation during evidence append
- Both complete reconciliation passes
- Summary validation
- Source-content and source-drift verification
- Schema-snapshot integrity
- Evidence-manifest validation
- Canonical evidence serialization
- Existing validation errors and exception behavior
- Historical evidence source-identity restrictions

The cache does not replace source hashing or authorize changed source contents.
No changes were made to simulated PUF acquisition, majority voting, BCH reconstruction, credential retrieval, authentication cryptography, admission logic, inference-release rules, experimental scheduling, or timing boundaries.

## Files Modified
The optimization implementation modified five files.
| File | Purpose |
|---|---|
| `src/python/puf_snn/experiments/majority3_auth_v1.py` | Shared cached-validator factory and Week 7 integration |
| `src/python/puf_snn/experiments/three_arm_auth_v1.py` | Week 8 integration with the shared cache |
| `tests/experiments/test_auth_schema_cache.py` | Focused cache correctness and invalidation tests |
| `tests/experiments/test_three_arm_auth_v1.py` | Additional reconciliation and evidence-integrity regressions |
| `docs/week8-schema-validation-performance-correction-20261021.md` | Original implementation and regression report |

The correction reused existing schema files, evidence modules, and resource-profiler instrumentation.
No experimental configuration, schema definition, formal allocation, or authorization mechanism was changed.
The original implementation report is retained as the historical record of the optimization before comparative performance measurements were available. This revised document incorporates the subsequent benchmark findings.

## Regression Testing and Independent Review

### Implementation Regression Tests

The implementation agent reported the following completed regression suites,
| Test Group | Passing Tests |
|---|---:|
| Harness, schema cache, pipeline, acquisition, and noise | 256 |
| Authentication and admission | 237 |
| Resource-profiler safety | 55 |
| **Total** | **548** |

All 548 selected test executions were reported as passing, with zero failures or skips.
The eight focused schema-cache tests were included within the 256-test group, not counted as eight additional tests.
The historical-pilot inspection test was deliberately excluded because it attempts to inspect source-bound historical evidence through a changed checkout.
Disposable unit fixtures were used for evidence-reconciliation and tampering tests.

### Focused Native Windows Validation
The eight dedicated schema-cache tests were also executed successfully in the researcher's native Windows project virtual environment.
**Observed local result:** 8 tests passed in 0.765 seconds.
These tests covered,
- Cache-hit reuse with repeated instance validation
- Cold-cache and warm-cache validation equivalence
- Schema modifications with unchanged size or timestamps
- Atomic schema replacement
- Missing and malformed schema handling
- Validator-class identity
- LRU eviction and explicit clearing
- Equivalent validation errors and canonical instance data

### Independent Correctness Review
A separate read-only Codex audit reviewed the cache implementation, both study entry points, evidence reconciliation, existing schemas, and regression coverage.

**Audit decision: PASS — READY FOR A NEW BOUNDED COMPARATIVE BENCHMARK.**
The reviewer identified no reachable cache-related validation or evidence-integrity blocker under the supported current schema definitions and serial worker lifecycle.
The audit confirmed that,
- Cache identity reflects the relevant current schema semantics
- Instance validation remains complete
- Week 7 compatibility is preserved
- Changed or malformed schema contents cannot silently reuse incompatible validators
- Source-hash and evidence-snapshot checks remain independent
- The existing resource profiler can observe the optimization without modifying its instrumentation

The audit was a static review and did not independently execute the 548-test suite.

## Comparative Resource Benchmark

### Experimental Procedure
Following the independent audit and local regression validation, a second supervised nonformal resource benchmark was conducted on October 21, 2026.
**Baseline session:** `first-20261021-01`  
**Optimized session:** `cachecmp-20261021-01`
Both benchmarks used,
- The same 150-attempt nonformal allocation
- The same five configured noise conditions
- The same three authentication arms
- The same reviewed canonical experimental plan
- One fresh worker process per benchmark
- Zero standalone audits
- The same resource-profiler implementation and instrumentation
- Equivalent explicit time, memory, disk, and evidence-growth limits

The reviewed plan SHA-256 remained,
`74a07b7b06edee5dd58b9ad594fe70d00859ea1c4bceeaec2fb6bac52821a016`

The profiler source SHA-256 remained:

`1b5bd36a8ec6bbc8c480ac9f82f11e3897ee96413d7ccba5f001a8c9ed83d14c`

The optimization changed the experiment source identity. The previous source snapshots and historical benchmark evidence were preserved under their original identities.

### Resource Limits
Both benchmarks used the following resource limits,
| Resource | Limit |
|---|---:|
| Maximum bundle runtime | 900 seconds |
| Maximum session runtime | 1,200 seconds |
| Worker memory threshold | 2 GiB |
| Minimum available system RAM | 8 GiB |
| Minimum free disk space | 2 GiB |
| Maximum bundle growth | 32 MiB |
| Maximum aggregate growth | 128 MiB |
| Resource sampling interval | 50 ms |

These thresholds provided bounded execution and monitored the experiment's consumption of system resources.
The limits were sampled stopping conditions rather than strict instantaneous memory or disk quotas.

### Measured Performance Comparison
| Metric | Baseline | Optimized | Relative Reduction |
|---|---:|---:|---:|
| Total session wall time | 142.875 s | 48.734 s | 65.9% |
| Schema self-check calls | 459 | 5 | 98.9% |
| Schema self-check inclusive time | 97.799 s | 1.073 s | 98.9% |
| Week 8 schema-validation inclusive time | 103.219 s | 6.876 s | 93.3% |
| Evidence-finalization inclusive time | 71.528 s | 8.050 s | 88.7% |
| Reconciliation inclusive time | 68.396 s | 5.263 s | 92.3% |

The optimized benchmark reduced total observed execution time by:
**142.875 - 48.734 = 94.141 seconds**
The observed speedup was:
**142.875 / 48.734 = 2.93x**
This corresponds to a **65.9% reduction in total measured wall time**.

### Schema-Validation Improvement
The independent audit predicted that the content-keyed cache would reduce schema-definition checks from 459 to approximately five.
The optimized benchmark recorded exactly five schema self-checks.
These correspond to the distinct schema definitions required by the execution path,
- Week 8 configuration schema
- Week 8 experimental-plan schema
- Week 8 attempt schema
- Week 8 summary schema
- Inherited Week 7 configuration schema

Instance validation remained active for every required record.
The agreement between the predicted and observed check counts supports the conclusion that the cache eliminated redundant schema-definition preparation without eliminating the required record-validation operations.

### Evidence-Finalization Improvement
Evidence-finalization time decreased from approximately 71.53 seconds to 8.05 seconds.
This represents an observed reduction of approximately 88.7%.
The combined reconciliation duration also decreased from approximately 68.40 seconds to 5.26 seconds.
These improvements are consistent with the removal of repeated schema-definition validation during the two reconciliation passes.
Importantly, the reconciliation passes themselves were not removed.
Both continued to verify experimental identities, source-specific outcomes, recorded operations, and evidence integrity.

### Memory Observations

The baseline profiler recorded a sampled peak private-memory value of approximately 1.40 GiB.
The optimized benchmark's initial PowerShell extraction displayed approximately 1.4 under a `GiB` label, but that extraction divided the raw byte counter by one billion rather than by 1,073,741,824.
Consequently, the optimized value should be treated as approximately 1.4 decimal GB until its original byte counter is used for an exact binary-unit comparison.
The benchmark therefore establishes a strong runtime improvement, but the rounded memory values do not establish a precise memory reduction.
A full-scale 90,000-attempt workload may also retain substantially more in-memory evidence than either 150-attempt benchmark.

## Evidence Integrity and Acceptance Results

### Comparative Benchmark Acceptance
The optimized session reported,
| Validation Check | Observed Result |
|---|---|
| Profiler success | `true` |
| Profiler state | `accepted` |
| Completed workers | 1 |
| Completed arm attempts | 150 |
| Matched trial-condition identities | 50 |
| Finalization validation passes | 2 |
| Unauthorized releases | 0 |
| Worker supervision | Verified |
| Reported execution errors | None |
| Resource-limit violations | None |

The accepted profiler receipt confirms that the monitored execution completed within its approved resource limits and passed its configured acceptance checks.
The scientific evidence receipt separately confirms successful two-pass validation of the completed experimental bundle.

### Validation Replay Accounting

The experiment performs two deterministic reconciliation passes during evidence finalization.
For the 150-attempt allocation, the validated accounting contract distinguishes experimental operations from replay operations.
Experimental operations include,
- 200 runtime simulated PUF measurements
- 100 runtime BCH decodes
- 50 stored-credential invocations

Two-pass finalization requires,
- 400 replay measurements
- 200 replay BCH decodes
- Two enrollment-reference readings

These replay operations verify recorded evidence. They do not create additional experimental observations or independent statistical samples.
The benchmark preserved this validation scope after the caching optimization.

### Authentication Integrity
The optimized benchmark recorded zero unauthorized inference releases.
The three authentication arms continued to use the shared credential-verification, admission, session-establishment, and protected-window authorization boundaries.

The optimization did not change those mechanisms.
Zero unauthorized releases are a successful finite execution check, not a proof that unauthorized release is impossible or a statistical bound on cryptographic forgery probability.

## Preservation and Reproducibility

### Historical Evidence
The following records must remain unchanged,
- October 20 original nonformal three-arm pilot.
- October 21 baseline resource benchmark.
- October 21 optimized comparative benchmark.
- Their respective source snapshots, manifests, completion markers, and validation receipts.

The implementation agent reported matching preservation fingerprints for the historical evidence available before the optimization.
The optimized benchmark used a separate session identifier and a new source identity, preventing its results from being confused with the baseline.
Historical bundles must not be rewritten, resealed, or rehashed to make them appear compatible with later source revisions.

### Benchmark Artifacts
The profiler sidecar directories are:
**Baseline:**
`tmp/week8-three-arm-resource-profile-v1/first-20261021-01/`
**Optimized:**
`tmp/week8-three-arm-resource-profile-v1/cachecmp-20261021-01/`
Each session contains its authoritative profiler `summary.json` and supporting monitoring information.
The scientific evidence bundles are stored separately under the Week 8 nonformal experiment namespace.
Profiler sidecar files are not inserted into sealed scientific evidence bundles.

### Source Identity

The optimization changed the experiment source implementation while preserving its scientific configuration and reviewed plan.
Therefore,
- The baseline and optimized runs should retain their separate recorded source identities
- Their common plan identity supports comparison of the same planned workload
- Historical source snapshots remain immutable
- Future audits must use the appropriate recorded source and environment
- Neither benchmark authorizes formal execution

These restrictions preserve the distinction between reproducible historical evidence and later development changes.

## Interpretation and Limitations

### Interpretation of the Performance Improvement
The measured results strongly support the diagnosis that repeated schema-definition validation was a major source of computational overhead.
The number of schema self-checks decreased exactly as predicted, and the corresponding validation and finalization durations decreased substantially.
The observed 2.93x speedup is meaningful for the tested development workload.
However, this is a descriptive comparison of two supervised benchmark executions, not a replicated performance study.
Measured durations can be affected by,
- Instrumentation overhead
- Operating-system scheduling
- Background system activity
- JIT compilation and cache state
- Filesystem and operating-system caching
- Process initialization
- Memory allocation behavior

The reported speedup should therefore be attributed to the tested software environment and benchmark conditions rather than treated as a guaranteed improvement across all machines and workloads.

### Scientific Limitations
The benchmarks used only one simulated population and one simulated device.
They were designed to evaluate infrastructure performance, not to estimate population-level reconstruction reliability or confidence intervals.
Additional limitations include,
- No physical PUF was measured
- No physical Meta Quest 3 device authentication was performed
- No actual SNN or anomaly-model inference was executed
- No warmed formal timing protocol was implemented
- No full-scale formal statistical analysis was performed
- No formal execution path was enabled
- Full-scale memory and runtime feasibility remain unverified

The results demonstrate pilot-scale operational and evidence-processing feasibility.
They do not independently establish reliability under unmodeled physical manufacturing variation or deployment conditions.

### Remaining Performance Work

The caching optimization does not eliminate every source of experimental overhead.
Remaining operations include,
- Repeated source-integrity hashing
- Per-attempt instance validation
- Canonical JSON serialization
- Per-attempt flushing and synchronization
- Retention of experimental records in memory
- Deterministic reconstruction replay
- Evidence-manifest construction and verification
- Two complete reconciliation passes

Future optimization should be justified by additional measurements or formal-scale feasibility analysis.
Source-integrity checks and evidence durability must not be weakened solely to improve runtime.


## Formal Study Readiness
The planned formal experiment uses,
- 20 synthetic population clusters
- Six simulated devices per population
- 50 trials per device and noise condition
- Five noise conditions
- Three authentication arms

This produces 30,000 matched trial-condition identities and **90,000 authentication attempts**.
The successful Week 8 resource benchmarks demonstrate that the corrected infrastructure can execute the bounded 150-attempt workload.
They do not establish the resource requirements of the full formal allocation.
Before formal execution, remaining requirements include,
1. Approval of the statistical methodology and primary reliability comparisons.
2. Finalization of the warmed timing protocol and Numba/JIT handling.
3. Full-scale runtime, memory, and evidence-storage feasibility assessment.
4. Implementation and independent review of formal statistical analysis.
5. Implementation and audit of separately authorized formal execution controls.
6. Final source, configuration, plan, and environment identity freezing.
7. Explicit approval to execute the formal study.

Formal execution remains disabled until those prerequisites are satisfied.

## Week 8 Conclusion

During Week 8, I successfully identified, corrected, and experimentally measured a significant performance bottleneck in the simulated PUF authentication research infrastructure.
The initial monitored benchmark revealed that redundant JSON Schema definition validation accounted for a substantial portion of the experiment's execution time.
I implemented a bounded, content-keyed validator cache that reused validated schema definitions while preserving every required instance-validation call, both evidence-reconciliation passes, and the existing source-integrity mechanisms.
The implementation passed the reported regression suites and an independent correctness review. A subsequent supervised benchmark confirmed that schema-definition checks decreased from 459 to five.
Total observed runtime decreased from **142.875 seconds to 48.734 seconds**, yielding a **65.9% reduction in execution time and a 2.93x speedup**.
The optimized benchmark completed all 150 authentication attempts, preserved two-pass evidence validation, and recorded zero unauthorized inference releases.
This optimization improved the efficiency of the research infrastructure without intentionally changing the underlying simulated PUF model, authentication protocol, or experimental methodology.
The result establishes a stronger foundation for the planned 90,000-attempt formal correlated-noise reliability experiment.

**Week 8 development and pilot-scale performance optimization are complete. Full formal-study execution and statistical analysis remain future research milestones.**