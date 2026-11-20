# Week 12 Experimental Conditions and Implementation Readiness — v1

**Owner:** Will Wallace  
**Week:** 12
**Status:** Plan Complete, Awaiting Experiment Execution
**Date:** 11/20/26

## 1. Experiment overview

The experiment examines **how correlation between repeated PUF readings changes Majority-3's reconstruction advantage over Single-Read**, while holding marginal per-reading measurement-noise variance fixed. The selected design uses six conditions, three credential-source arms and a shared cohort of 120 simulated devices. This document explains the conditions, their scientific roles and the implementation work needed to carry them out [R1–R3]. “Selected” identifies the working experimental design; formal adoption, validation and execution authorization remain separate prerequisites.

Week 11 established the documented calibration-selection and reconstruction/statistical methods and consolidated the correlation-study design. The research log reports closure of the five documentation findings and readiness for methodology review. Faculty feedback supports the comparison and prioritizes provenance closure and the controlled experiment over further infrastructure expansion [R3–R4].

The existing numerical evidence comes from the **24-device, rho=0 calibration: 3,840 attempts across four sigma candidates**. At sigma 0.15, Single-Read failed 49/480 reconstructions (10.208%), while Majority-3 failed 15/480 (3.125%). The observed benefit was **7.083 percentage points**, with a descriptive paired-bootstrap 95% interval of **[3.333, 11.250] percentage points**. These calibration findings establish the operating-point selection basis; they do not measure the effect of correlation. The final experiment has not been executed.

## 2. Why sigma = 0.15 was selected

The calibration used a prespecified rule: evaluate all four candidates and select the **lowest sigma that passes all seven qualification gates**. Sigma 0.10 failed; 0.15, 0.20 and 0.25 passed. The rule therefore selected 0.15 rather than whichever candidate produced the largest observed benefit [R1–R2].

The gates screen for complete and valid evidence, an observable but nonsaturated Single-Read failure rate, a usable Majority-3 region, meaningful independent-read benefit, informative matched outcomes, acceptable sampling uncertainty and benefit distributed across devices/groups. Together, they identify a region where a change in Majority-3's advantage can be studied without starting at a near-zero failure floor or an overwhelmingly failing baseline. These are researcher-prespecified calibration criteria, not demonstrated faculty-approved thresholds or a final-study precision guarantee.

Holding sigma at 0.15 across the four correlation conditions isolates the effect of changing rho. Under the specified noise model, conditional on fixed device characteristics and the controlled offset, each reading's measurement-noise variance remains sigma squared and cross-reading covariance is rho times sigma squared. Rho describes the analog measurement disturbance; it is not the correlation of binary reconstruction errors [R2].

### Calibration evidence and provenance

Reliance on the saved calibration remains conditional on the provenance work described in the decision brief [R1]. Week 10 reported an unresolved `pipeline_timing.py` identity; Week 11 reported agreement for **126/126 manifest entries and 116/116 frozen source entries**. Mixed line endings reproduce the three reported hash representations, but do not establish the historical transformation, executed source or earlier audit's custody history. Preserved dependency tracing identifies no demonstrated numerical effect on reconstruction, bootstrap or selection.

The remaining corrective work is one separately scoped **full saved-evidence audit using exact frozen source in a compatible recorded environment**. It must cover imported-source identity, coverage, deterministic reconstruction replay, summary/selection and authorization/completion checks. Four live source-set mismatches and an unavailable venv-referenced interpreter prevent assuming that the present environment is compatible. Faculty provenance disposition, the full audit and a genuine named/dated/hash-bound researcher acknowledgment outside sealed evidence remain prerequisites to formal operating-point adoption.

Pre-execution records, completion evidence and later audit interpretations serve different purposes. Present hash agreement cannot certify historical execution. Likewise, the separate saved-score reconstructed package-manifest hash supports metric replay within its documented limitation, rather than supplying a retained reference hash [R4]. A new calibration would require a substantive contradictory finding or a separate replication requirement; it would not repair historical custody.

## 3. Selected experimental conditions

The six conditions separate the correlation comparison from the nominal and common-mode controls [R2]. Each condition uses the same devices and trial indices, with 6,000 matched Single-Read/Majority-3/Stored-Provisioned blocks.

| Condition | Settings | Purpose |
| --- | --- | --- |
| Independent operating reference | sigma 0.15, rho 0 | Establish Majority-3's benefit with independent measurement disturbances at the selected operating point, using fresh final devices/seeds rather than reusing calibration outcomes. |
| Intermediate correlation | sigma 0.15, rho 0.50 | Measure the benefit at an intermediate level of shared measurement noise. |
| High correlation | sigma 0.15, rho 0.90 | Supply the principal comparison of attenuation relative to the independent operating reference. |
| Fully shared boundary | sigma 0.15, rho 1 | Check the model boundary: all three readings within an attempt agree, so matched Single-Read and Majority-3 reconstruction outcomes must agree. |
| Nominal reference | sigma 0.10, rho 0 | Retain a separate descriptive reference at the lower noise level. It is not the baseline for the correlation-attenuation contrast. |
| Common-mode control | sigma 0.15, rho 0, uniform additive offset of either −1 or +1 | Check cancellation of an offset applied equally to every oscillator, using the same measurement-noise realization as the operating reference. |

At rho 1, identical readings imply zero Single-Read/Majority-3 reconstruction difference, not zero absolute failure. The identity must be checked through the actual acquisition, vote and reconstruction paths. The common-mode condition likewise tests an expected identity: a uniform additive offset cancels in oscillator comparisons, preserving response bits and reconstruction categories. Floating-point ordering violations are numerical faults requiring explicit handling [R2].

For the common-mode control, one seeded offset sign is chosen per device/trial and applied uniformly across oscillators, readings and both PUF arms. The control deliberately shares the full operating-rho0 measurement-noise identity, including every reading seed. It retains separate scheduled attempts and actual acquisitions; its outcomes are not pooled into the reference denominator. The two possible signs belong to one condition.

Because the selected sigma differs from the nominal sigma, those references remain separate. The six-condition design therefore contains 108,000 attempts rather than the legacy five-condition total of 90,000. A standalone sigma 0.25 stress condition is not part of this design [R2].

## 4. Credential-source arms, matching and allocation

The three arms distinguish PUF reconstruction from downstream credential use:

- **S — Single-Read:** one actual PUF reading followed by one reconstruction/decode.
- **M — Majority-3:** three actual PUF readings, one majority vote and one reconstruction/decode.
- **T — Stored-Provisioned:** retrieval of the enrolled credential from trusted memory, with no PUF readings, voting or decoding. This is a downstream control; PUF reconstruction metrics are inapplicable.

Within each block, S and M share device, enrollment, credential material and indexed reading zero; M additionally acquires readings one and two. Each arm receives fresh downstream session state. This pairing keeps the reconstruction comparison tied to the same device and initial disturbance while preserving each policy's actual acquisition work [R2].

The allocation is **120 devices in 20 groups of six, with 50 matched trials per device per condition**. Each condition contains 6,000 matched blocks and 18,000 arm attempts. Across six conditions, that yields **36,000 blocks and 108,000 attempts**, or 36,000 attempts per arm. Attempts are repeated observations, not independent devices.

Devices are the primary sampling unit because the specified generator has independent device manufacturing draws and no shared group latent effect. Whole-group resampling provides a separately reported sensitivity analysis. Repeated trials characterize within-device behavior; they do not replace independent device replication. The allocation and variability rationale in R2 do not establish a guaranteed final interval width. A change that introduces group dependence would require reconsidering the sampling unit and analysis before freeze.

## 5. Analysis and reporting choices

For each PUF arm, reconstruction outcomes remain **C** (correct credential), **D** (decoder failure), **I** (invalid format) and **W** (wrong credential). Reconstruction failure rate is **FRR = (D + I + W) / N**. Majority-3's benefit at a given rho is **Delta(rho) = FRR_S − FRR_M**; attenuation relative to independent readings is **A(rho) = Delta(0) − Delta(rho)** [R2].

The principal contrast is **A(0.90)**. Reporting also includes the full Delta curve, A(0.50) and the rho1 boundary. Positive, zero and negative attenuation are admissible. The study estimates effects with signed, two-sided 95% pointwise percentile intervals; it does not set a confirmatory significance, equivalence or guaranteed-precision target.

The analysis uses **10,000 paired whole-device bootstrap draws**, preserving cross-condition resampling multiplicities, plus a separate **10,000 whole-group sensitivity draws**. A fresh final rho0 reference supplies Delta(0); the selected calibration results remain descriptive and are not substituted into the final contrast.

The working secondary reporting plan includes intervals for T's all-attempt retrieval failure rate and each arm's all-attempt admission/session failure rates. Other secondary rates, BER/histograms and cold-process, zero-warmup timing remain descriptive. The exact secondary interval list and denominator contracts still require acceptance before analysis implementation/freeze and final outcomes [R2]. Reconstruction, retrieval, verifier refusal, admission/session outcomes and authorized callbacks remain distinct. A verifier rejecting a wrong credential does not establish correct BCH recovery, and a callback is not actual inference [R4].

## 6. Implementation sequence and remaining dependencies

The following milestones translate the design into a reviewable implementation. They are dependency-based rather than calendar deadlines. Will coordinates the work; resource, independent-review and final-authorization roles still require designation.

| Milestone | Responsibility | Deliverable and dependency |
| --- | --- | --- |
| 1. Close evidence and design prerequisites | Dr. Garcia; Will coordinates audit and acknowledgment | Documented provenance disposition, compatible full-audit receipt, genuine external acknowledgment and formal operating-point/design/reporting adoption. |
| 2. Build final configuration, planner and schemas | Will | Six-condition config, 36,000-block/108,000-attempt plan, canonical schemas/hash recipes and analysis code, following milestone 1 and agreed identity/reporting contracts. |
| 3. Validate deterministic boundaries and statistics | Will | Rho1/common-mode, signed-A, pairing, bootstrap-multiplicity and denominator validation receipts from scoped isolated validation of milestone 2. |
| 4. Implement protected execution and evidence controls | Will; designated reviewer | Single-use controller, protected outputs, source/stop checks, two-pass replay and completion controls, following milestones 2–3 and reviewed lifecycle definitions. |
| 5. Qualify resources | Designated resource owner; Will | Named compatible host, qualification receipt, numeric budgets/reserves and supervision acceptance covering replay, finalization and analysis; depends on milestone 4 and separately reviewed nonfinal scope. |
| 6. Complete independent review and freeze | Reviewer other than implementer; Will assembles | Resolved findings and exact specification/source/config/plan/analysis/environment/resource package after acceptance of milestones 1–5. |
| 7. Obtain final execution authorization | Explicitly designated authorizer | Identity/run/path-bound single-use authorization for the accepted milestone 6 freeze. |
| 8. Execute and analyze the final study | Will; designated supervision | Complete fixed allocation, both validation passes, estimates/intervals, sensitivity and limitations, using valid authorization, qualified host and intact freeze. |

Full-scale memory use and finalization remain unqualified; host, numeric caps and supervision acceptance are unset. Bounded resource qualification must have its own nonfinal scope and cannot use reserved final outcomes for tuning. Infrastructure, numerical, integrity, resource or controller faults stop execution and preserve incomplete evidence. There is no outcome-driven stopping or automatic retry; a restart requires separate review and new authorization [R2].

The faculty-requested training-record item for the coordinated IRB packet also requires verification and closure [R4]. Its completion is unverified here and remains distinct from simulator execution authority.

## 7. Scope and current status

The design supports a **simulator-conditional comparison of reconstruction reliability**. The PUF is simulated, and the 32-bit pilot credential does not establish production-grade security. Tested releases do not establish general adversarial security, physical-device reliability or trained-SNN performance. Historical timing retains its recorded release, environment, Single-Read and additional-acquisition scope [R4].

The conditions and analysis above describe the selected working design. The experiment remains unexecuted, the specification unfrozen and resources unqualified. Provenance disposition/audit/acknowledgment, formal design/reporting adoption, implementation, independent acceptance and separate final execution authorization remain open. This documentation revision changes the explanation and organization of the design; it records no new experimental results or approvals.

## References

| Ref. | Source |
| --- | --- |
| R1 | [Week 11 calibration provenance decision brief](../week11/week11-calibration-provenance-decision-brief-v1-proposed.md), §§3–7: discrepancy, evidence chronology, consequences and corrective action. |
| R2 | [Week 11 final correlated-noise study specification](../week11/week11-final-correlated-noise-study-specification-v1-proposed.md), including the November 18 revision: detailed conditions, equations, original calibration gates, allocation rationale and implementation/freeze requirements. The source specification retains its proposed status. |
| R3 | [Week 11 research-log narrative](../research-logs/will.md#week-11-puf-calibration-verification-experimental-provenance-and-correlated-noise-study-design): accomplishments, saved results and reported documentation-review closure. |
| R4 | [Week 11 Research Feedback.txt](<C:/Users/wwall/Downloads/Week 11 Research Feedback.txt>), supplied by researcher and read for the original memo on November 18, 2026; external source, not copied into the repository. |
