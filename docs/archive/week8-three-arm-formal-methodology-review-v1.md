# Week 8 formal three-arm methodology review — v1

Review date: **2026-10-20 (America/New_York)**. Status: **proposed methodology
freeze; researcher approval and implementation prerequisites outstanding**.
This document authorizes no execution and changes no existing configuration.

Status labels used throughout:

- **I — Already implemented and validated.** Supported by inspected source,
  existing test coverage, the independently audited pilot where applicable, and
  the user's reported local validation. This does not mean formal-scale or
  statistical validation, nor that this reviewer executed tests.
- **D — Documented but not experimentally validated.** A stated contract or
  scientific interpretation without a completed formal evaluation.
- **F — Requires future implementation.** The present harness cannot yet produce
  the specified formal measurement, analysis or execution artifact.
- **R — Requires researcher decision.** A proposed choice must be approved before
  a final freeze; approval is not implied by this review.

Combined labels separate an existing measurement from a proposed use of it.
The twelve sections below specify the recommended design and identify every
material approval or implementation gap.

## 1. Executive readiness assessment

**I:** The three credential sources converge on the existing Authentication-v2
independent verifier, local admission authorization, HKDF, mutual confirmation,
HMAC-protected window verification, sequence enforcement and verifier-controlled
release gate. Stored retrieval introduces no runtime acquisition, voting or BCH
decode. This study compares credential sources within that common architecture.

The historical October 20 nonformal bundle contains 50 matched trial-condition
identities and 150 completed arm attempts, one population and one device. Saved
session totals are 41/50 single-read, 45/50 Majority-3 and 50/50 stored; accepted
windows and authorized releases have the same totals. Unauthorized releases are
zero. Single-read C/D/I/W counts are 41/6/2/1; Majority-3 counts are 45/5/0/0.
All PUF reconstruction failures occurred in `independent_stress`. These are
descriptive observations, not formal findings or independent population replication.

The independent audit returned **CONDITIONAL PASS — CORRECTABLE GAPS**, with no
identified authentication bypass or source-isolation defect. Its validation-work
scope finding has been corrected in current source. The user now reports local
PowerShell results of **43 + 203 + 237 = 483 test executions, zero failures/errors**
after that correction. This supersedes the addendum's earlier agent-environment
test-pending checkpoint. No tests were rerun for this review. The historical
pilot bundle contains no archived test-execution receipts; obtain hash-bound
receipts before the formal source freeze.

**D/F/R:** Formal execution is **not ready to authorize**. The allocation is
planned, but warmed timing, recurring-window measurement, three-arm inferential
analysis, precision review, resource feasibility and a protected formal execution
path remain outstanding. Current runtime and evidence writer reject
`planned-formal`; the CLI has no formal-run action. Neither this document nor
the earlier conditional pass relaxes those gates.

**D/R — Feedback alignment:** [Week 6 feedback consolidation](week6-feedback-consolidation.md)
asks for matched reliability comparisons under correlation, a same-policy
provisioned-credential control, and reporting that keeps denominators, wrong
candidates, verifier refusals, credential length and timing together. This plan
addresses those requests. The [faculty decision memo](faculty-decision-memo.md)
proposes authentication p95 <=1 ms, post-window p95 <=20 ms and <=10% overhead,
with backup thresholds, as decisions for faculty. They are not approved Week 8
success criteria. Their measurement boundaries must be resolved in section 11.
The stored arm still performs authentication and is not an unauthenticated
pipeline baseline for the memo's overhead target.

## 2. Research questions, hypotheses and estimands

Notation: S=`single-read-v1`, M=`majority-3-v1`, T=`stored-provisioned-v1`;
`c` denotes a configured condition. Let `f(a,c)` be reconstruction FRR for a PUF
arm, and `Delta(c)=f(S,c)-f(M,c)`. Positive Delta favors Majority-3. All target
expectations concern the configured simulator and software boundary in section 3.

| Question | Proposed estimand and direction | Comparison role and interpretation | Status |
| --- | --- | --- | --- |
| RQ1: reconstruction reliability | `Delta(independent_nominal)` and `Delta(independent_stress)`; equivalently `P(C_M)-P(C_S)`. Directional hypotheses: each Delta >0. Report discordant matched counts as well. | Two primary contrasts. A null or floor-limited result is informative; superiority is not presumed. | D/R; F for three-arm formal intervals |
| RQ2: correlated-noise sensitivity | `A90=Delta(independent_nominal)-Delta(differential_rho90)`; directional hypothesis A90 >0 represents attenuation. `A50` defined analogously. | A90 is the third primary contrast; A50 and individual correlated benefits are secondary. Same sigma=.10 for this attenuation comparison. | D/R; F for analysis |
| RQ3: PUF versus stored source | For each PUF arm and condition, admission/session failure-rate difference versus T; paired mean acquisition-or-retrieval and establishment duration differences in ms. Positive timing difference is extra PUF-path cost. | Secondary implementation comparisons. Retrieval and acquisition are different operations; report source components and common downstream stages separately. No equivalent physical custody claim. | I for observations; D/R/F for formal timing/inference |
| RQ4: propagation through authentication | Per-arm/condition end-to-end admission, session, window and release rates; conditional attrition between adjacent eligible stages. Compare differences versus the matched arm/control. | Secondary outcomes. Separate inability to produce a correct candidate from failures after successful admission. | I for stage evidence; D/F for formal reporting |
| RQ5: protocol boundaries | Counts of W candidates refused before either HKDF, HKDF calls without independently verified admission, and releases without valid session/window authorization; dedicated rejection tests for malformed/wrong sources, tags and sequences. | Invariants and finite negative-test evidence, not population security scores or cryptographic forgery-probability estimates. | I for implemented gates/test coverage; D for formal observations |

**D:** Configured rho is correlation of oscillator-frequency noise across
readings, not measured binary response-error correlation. The design has
independent stress at sigma=.25, but correlated conditions only at sigma=.10.
It cannot identify a complete sigma-by-rho interaction or correlated high-stress
performance. No additional condition is approved here. If nominal and correlated
FRRs are all zero, a zero estimated attenuation does not establish immunity to
correlation; the experiment may lack events at those operating points.

## 3. Experimental units, allocation and inferential target

**I/D:** Retain the allocation in `configs/three_arm_auth_v1.json`:

| Level | Allocation or expected operation total | Status |
| --- | ---: | --- |
| Independent simulated population clusters | 20 | I for planning; D for formal evaluation |
| Persistent devices per population / total | 6 / 120 | I/D |
| Trials per device and condition | 50 | I/D |
| Configured conditions / arms | 5 / 3 | I/D |
| Matched trial-condition identities | 30,000 | I/D |
| Arm attempts | 90,000; 30,000 per arm | I/D |
| Attempts per arm-condition cell | 6,000; 300 per population | I/D |
| Experimental PUF measurements | 120,000: 30,000 single-read + 90,000 Majority-3 | I/D |
| Runtime BCH decodes / majority votes | 60,000 / 30,000 | I/D |
| Stored invocations | 30,000 | I/D |
| Distinct measurement noise identities, excluding nominal/control duplication | 24,000 | D; derived from the fixed planner |

Operation totals assume complete supported execution, not guaranteed successful
authentication. Enrollment/reference setup is separate: 120 device references,
with the existing noiseless enrollment setting. Validation replay and future
warm-up/cold-start diagnostics are not experimental samples.

| Exact condition | sigma | rho | Uniform common offset C | Analysis role | Status |
| --- | ---: | ---: | --- | --- | --- |
| `independent_nominal` | .10 | 0 | 0 | Primary reliability and attenuation reference | I/D |
| `independent_stress` | .25 | 0 | 0 | Primary reliability stress comparison | I/D |
| `common_control` | .10 | 0 | Seed-selected -1 or +1, one offset per identity | Linked cancellation/invariance control | I/D |
| `differential_rho50` | .10 | .50 | 0 | Secondary correlation comparison | I/D |
| `differential_rho90` | .10 | .90 | 0 | Primary attenuation contrast | I/D |

**D/R — Unit of inference:** One population is the prespecified resampling
cluster, carrying all six devices, trials, conditions and arms. A matched
trial-condition identity is the within-device comparison unit. An arm invocation
is an observation, not an independent population; three Majority-3 readings are
one acquisition and one reconstruction attempt.

`enrollment_material()` draws device manufacturing offsets using device-specific
seed domains. A population label groups six such devices; there is no additional
fitted population-level random effect in the generator. Independence means
disjoint pseudorandom domains under the simulator assumptions, not empirically
sampled physical manufacturing lots. Twenty is the cluster count used for
inference; 120 and 90,000 must not be substituted for it. The master seed fixes
one reproducible simulated cohort. Bootstrap resampling represents uncertainty
under repeated draws from the specified simulation law, conditional on that law,
not uncertainty over unmodeled hardware or proof of PRNG independence.

The target is expected per-attempt behavior for equally weighted simulated
population/device/trial allocations at each specified condition, with the frozen
software protocol and environment. For balanced complete cells, the pooled rate
equals the mean of 20 population rates. Do not infer a deployment noise mixture
by pooling all five conditions. Noiseless enrollment, manufacturing_std=1.0,
128 oscillators, adjacent comparisons, 64-bit responses and first-63-bit
BCH(63,36,t=5) use remain fixed simulation assumptions.

## 4. Matching and repeated-measure dependence

**I/D:** The model is `f(i,r)=100+M(i)+C+sigma*sqrt(rho)*Z(i)
+sigma*sqrt(1-rho)*E(i,r)`: manufacturing M is fixed per device, Z is fixed
across readings of one trial, and E varies by oscillator and indexed reading.
The noise variance remains sigma squared as rho changes; all frequencies are
abstract simulator units. Binary comparisons are nonlinear functions of these
frequencies, so their error correlation is not automatically rho.

**I:** Within each trial-condition identity, PUF arms use the same persistent
device, enrollment, credential, indexed first noisy response and shared
disturbance. Majority-3 additionally obtains indexed readings 1 and 2 and votes
once. Stored provisioning uses the same enrolled four bytes before timing.
Every arm gets fresh sender, verifier, admission service and recording consumer;
enrollment/verifier material is shared without reusing session state.

The planner cycles all six arm permutations with population/device/condition
offsets, then deterministically shuffles blocks. Within 50 trials of one
device-condition cell, each permutation occurs eight or nine times; this is
approximate order balance, not guaranteed exact balance of every position.
Retain execution indices and order in reports. Shared noise preparation and
endpoint allocation are outside measured establishment.

**I/D — OS entropy:** Actual handshake nonces and session bytes retain
`secrets.token_bytes()` randomness. Only measurement inputs are matched. Fresh
handshake entropy is an unmatched nuisance variable; a noise-seed hash is not a
session-entropy match. Do not inject deterministic protocol entropy to improve
pairing. Clustering and balanced order cannot remove all shared-process timing
drift; section 7 limits the timing interpretation accordingly.

Except for the explicit nominal/common-control alias, different conditions use
different measurement noise domains. Equal trial indices across rho or sigma
conditions do not imply identical noisy realizations; matching there is through
the common device/population and paired arm contrast, not common noise bytes.

**I/D — Common-mode control:** `compile_plan()` aliases its noise identity to
`independent_nominal` at the same device/trial index. The uniform additive C
cancels in oscillator-pair differences. The pilot's 50 identities therefore
contained 40 distinct noise identities. Formally, 6,000 control identities are
linked repeats of 6,000 nominal identities: 30,000 scheduled identities contain
24,000 distinct noise identities. These are actual repeated simulator calls,
not extra independent draws. The -1/+1 offsets are not two additional full arms.
Numerical changes in comparison bits cause a simulator error, not a physical
common-mode failure label.

Report control C/D/I/W and pipeline rates with their own scheduled denominators
and a visible "linked nominal realization" label. Plot nominal/control
agreement or paired differences separately. Never combine their denominators
into a larger nominal reliability sample, count them twice in a nominal effect,
or treat exact agreement as 12,000 independent successful trials. Retain both
linked rows inside every resampled population. Protocol/timing outcomes can
differ despite identical PUF bits because sessions use fresh entropy and time.

**I/D — Stored repetition:** Each of 120 provisioned device credentials is used
250 times across five conditions. These invocations describe repeated retrieval
and downstream workload, not independent stored credentials or populations.
The condition label supplies workload/order context, not a noise response for
T. Report separate matched cells; any optional pooled stored timing description
must disclose the scheduled weighting and dependence, and adds no inferential
clusters.

**D:** Policy effects on reconstructed candidates can be interpreted as
controlled effects of the configured simulated acquisition policy on shared
inputs. They do not transfer to physical PUFs. Timing differences characterize
the instrumented implementation and execution schedule, including survivor and
cache effects; they are not an isolated hardware causal effect. Week 7 uses
different seeds/device domains and two arms. Do not pool its smoke with Week 8,
claim longitudinal improvement from their unmatched rates, or inherit its
two-arm analysis implementation as a completed three-arm analysis.

## 5. Complete metric definitions

**I/D:** Calculate within each arm-condition cell, with population/device detail
retained. A completed formal analysis requires all scheduled fault-free rows.
Let N be completed arm attempts; N_plan the scheduled count; Q emitted wire
requests; V independent-verifier calls; A successful local admissions; N_sess active
sessions at both endpoints; W_win accepted protected windows; R authorized releases
whose release call completed; and Vw actual protected-window verifier calls.
For this design N_plan=6,000 per arm-condition cell. `request_emitted` distinguishes
wire requests from all N authentication-establishment attempts. D/I refusals are
completed attempts even though no handshake request is emitted.

Status I below covers source observations/current descriptive metrics. D means
the specified interpretation/reporting definition; F marks formal reporting that
is not currently emitted. No zero denominator is converted to a zero rate.

| Metric | Numerator / denominator or measurement definition | Applicable arms and exclusions | Status |
| --- | --- | --- | --- |
| Attempt coverage | Completed N and started/persisted rows separately / N_plan | All. Unknown interrupted work stays unknown; never rename N as successful sessions. | I/D; F for formal coverage report |
| Correct reconstruction C | Count with classification C; correct probability C / (C+D+I+W) | S,M. Candidate equality to enrolled truth is an evaluator observation, not admission authority. | I |
| Decoder failure D | Count `decoder_failure`; descriptive frequency D / (C+D+I+W) | S,M. Decoder-declared failure only; backend exceptions are excluded as infrastructure faults. | I |
| Invalid format/padding I | Count `invalid_format_or_padding`; I / (C+D+I+W) | S,M. A decoded message with invalid padding/format, not a verifier rejection. | I |
| Wrong valid-format W | Count valid-format credential unequal to enrollment; W / (C+D+I+W) | S,M. Not a successful authentication, even if the decoder reports success. | I |
| Reconstruction FRR | (D+I+W) / (C+D+I+W) | S,M only. In complete supported cells the denominator equals N. T is null/inapplicable. | I |
| Stored retrieval outcomes/failure rate | Separate success, unavailable, malformed counts; (unavailable+malformed) / completed stored attempts | T only. Source exceptions/infrastructure errors invalidate completed-run analysis; no PUF fallback. | I |
| Independent-verifier rejection rate | (`credential_mismatch` + `record_disabled`) / V; show both components | All, conditional on reaching actual verification. Missing key/record, unsupported binding, internal errors are infrastructure faults. Post-verification revocation/refusal is admission policy, not verifier rejection. | I for observations; D/F for this derived rate |
| Wrong-candidate refusal fraction | W candidates with observed `credential_mismatch` / W | PUF W subgroup; missing W gives undefined, not 100%. Wrong stored candidates are dedicated-test cases, not labeled W. | I/D/F |
| Admission failure rate | (N-A) / N; separately show source refusals, mismatches and policy refusals | All. Includes inability to reach admission. A counts actual successful `authorize_with_outcome` issuance, not decoder success. | I |
| Admission refusal conditional on verification | (V-A) / V | All; useful only with components and actual stage counts. V=0 is undefined. | D/F |
| Request-emission rate | Q / N using `request_emitted` | All. Q is a protocol-start count, not S and not a replacement denominator for source FRR. | I/D/F |
| Session failure rate | (N-N_sess) / N | All. An admission or receiver-only partial activation is not a completed session. | I |
| Downstream session failure after admission | (A-N_sess) / A; also describe N_sess / Q when Q>0 | All. Distinguishes source loss from failure of the shared handshake. Do not silently equate A and Q. | I for stages; D/F for derived rates |
| Accepted protected-window rate | Primary end-to-end W_win / N; conditional W_win / N_sess; verifier accept fraction W_win / Vw separately | All. One sequence-0 window is eligible per active session; sender sealing refusal reduces the session-conditional rate without a verifier call. | I for counts; D/F for all rate variants |
| Authorized inference-release rate | Primary end-to-end R / N; conditional R / W_win | All. Require accepted-window authority and completed release. In complete validated rows `authorized_release_count`, actual recording release count, release entries/completions and callback evidence reconcile. | I for counts; D/F for rate report |
| Unauthorized release count | Sum `unauthorized_release_count`, checked against actual release/callback observations and protocol stages | All; invariant required to be zero. Do not turn normal-run 0/N into an adversarial false-accept bound. | I/D |
| Callback invocation/completion | Separate preprocessing, motion, anomaly entries and completions; completion / eligible authorized releases | All. Callback completion is not classifier accuracy or actual model execution. A callback fault makes evidence incomplete. | I |
| PUF measurement count | Sum actual instrumented `measurement` calls; per completed attempt S=1, M=3, T=0 | Trial operations only. Exclude reference setup, warm-up and validation replay; retain their separate work accounts. | I |
| Majority-vote count | Actual voting calls; per completed attempt S=0, M=1, T=0 | No fabricated voting duration for single-read or T. | I |
| BCH decode count | Actual `bch_decode` calls; per completed attempt S=1, M=1, T=0 | Runtime operations only; helper encoding and replay are separate. | I |
| Acquisition/retrieval duration | S/M: inclusive `acquisition` span per attempt. T: inclusive provider `retrieval` span per invocation. Report count, mean, median, p95, p99, max. | Different source operations; label separately. Acquisition includes readings/voting/validation overhead; provider binding checks outside the retrieval call are elsewhere in establishment. | I for spans; F for warmed measurement |
| Reconstruction duration | Inclusive `reconstruction` span; BCH subspan separately | S,M; T null, never a fabricated zero decode. Includes wrapper and format handling beyond BCH. | I; F for warmed measurement |
| Verification/authorization duration | Inclusive verification; inclusive authorization and exclusive authorization after subtracting immediate verification child | All only when invoked; state sample counts V. Do not double-count verification in admission cost. | I |
| Total establishment duration | Direct `establishment` root, from before source entry through returned admission/handshake outcome; all-attempt and successful-session-only distributions separately | All. All-attempt N includes ordinary refusals. Excludes setup, endpoint creation and first-window work. | I; F for warmed protocol |
| First-window processing duration | Direct `first_window` root from before sealing through verification and recording callbacks | All N_sess eligible sessions; valid ordinary sealing/window refusal remains a measured first-window attempt. Also provide accepted-window-only distribution. No two-second capture time or actual SNN inference. | I for eligible spans; D/F for extra stratification |
| Recurring-window duration | Direct per-window total after first accepted window, with exact next sequences | Not implemented in this harness. Window count/session design must be approved separately; no inferred throughput from first-window data. | R/F |
| Validation work | Per-pass replay measurements/decodes/reference readings; two-pass finalization total; each later audit's own scoped work | Separate receipt `validation-work-v2`; zero statistical samples added. Legacy historical `validation_work` means one pass. Never add replay operations to N, PUF FRR or research sample totals. | I |

**I/D/F — Incomplete executions:** `execution_status="fault"`, non-null
`fault_code`, endpoint incomplete flags, exceptions, missing/duplicate/misordered
rows, hash/schema/replay contradictions, incomplete sentinel or absent/invalid
completion marker prevent a completed formal analysis. Backend faults must not
be recoded as D, legitimate-session FRR or ordinary policy refusal. Report the
scheduled, persisted, completed, faulted and unresolved counts by arm/condition
and last known stage, including partial callback progress. A supported ordinary
source or protocol refusal remains in N; it is not missing data.

Do not discard faulty rows, devices or populations and analyze the remainder
as the planned 20-population cohort. An incomplete bundle is diagnostic only;
identify missing pairs explicitly. If useful, bound an unresolved binary success
count between `known_successes/N_plan` and
`(known_successes+unresolved_outcomes)/N_plan`, labeled worst-case coverage bounds,
not a confidence interval. Do not impute unreached stages as observed
reconstructions. After a fault, any corrected full execution needs a separately
approved source identity/run ID; preserve failed evidence and disclose all
aborted runs. Do not selectively repeat unfavorable noise realizations.

## 6. Proposed statistical analysis

### 6.1 Estimation and clustering — D/R/F

Prespecify exactly three primary reconstruction contrasts: nominal Delta, stress
Delta and A90. A50, per-condition absolute C/D/I/W, stored comparisons, stage
attrition, timings and the cancellation control are secondary. No selection of
the most favorable condition, model or endpoint after viewing formal outcomes.

For each primary contrast compute its value in each population and average the
20 values. For conditional stage rates use the ratio of summed eligible counts,
not an unweighted mean of population rates with different survivor denominators.
Report those denominators. Report percentage-point differences as primary effect
sizes; risk ratios are secondary only when defined, with no automatic pseudocount
for a zero baseline. Report the matched both-correct, S-only-correct,
M-only-correct and neither-correct counts.

Use a paired whole-population nonparametric bootstrap: draw 20 population labels
with replacement, giving one multiplicity to each original population; carry all
its devices, trials, conditions, arms and linked controls together. Recompute
every statistic using the same multiplicities in a draw, including both terms of
attenuation. Use 10,000 draws and the configured bootstrap seed 2026101903 under
a documented Week 8 analysis RNG domain, distinct from measurement/schedule
domains. The exact seed derivation, RNG/library version and quantile convention
must be frozen before execution; reusing Week 7's experiment-version seed
derivation unchanged would be inappropriate.

Recompute pooled conditional rates and timing quantiles within each draw. A draw
with zero eligible denominator is undefined; never set it to zero, silently
drop it or redraw until convenient. Report defined/undefined counts and suppress
that metric's interval if any draws are undefined under this conservative plan.
The unconditional N-based rates remain primary for attrition comparisons.

The present three-arm `summarize()` emits descriptive groups and
`interval_status="not-computed-nonformal"`; it implements none of this formal
inference. Week 7's `bootstrap_populations()` demonstrates paired cluster
resampling for two arms, not a validated three-arm or timing analysis. New
analysis/schema/provenance work is required later. The one-population pilot must
continue to have no population-bootstrap confidence intervals.

### 6.2 Confidence intervals and multiplicity — D/R/F

Recommended freeze: report 95% two-sided **pointwise** percentile intervals
(bootstrap quantiles .025/.975) for each estimand. Use the existing linear
order-statistic interpolation: location `(B-1)*p` between adjacent sorted draws.
Intervals from only 20 clusters have approximate, not guaranteed, coverage;
show all population estimates and sensitivity diagnostics. Nominal sample size
alone is not a power or precision justification.

For any **confirmatory claim across the three primary contrasts**, recommend a
separately labeled Bonferroni family at overall alpha=.05: each two-sided interval
has nominal coverage `1-.05/3=98.333...%`, using quantiles .008333.../.991666....
The union-bound multiplicity adjustment relies on the constituent intervals'
coverage; it does not repair bootstrap undercoverage with few clusters or rare
events. Require the adjusted interval to exclude zero in the hypothesized
direction before a primary superiority/attenuation claim. No p-values are
specified by this plan. Secondary intervals remain pointwise and exploratory;
no familywise or simultaneous interpretation is attached to them.

Current configuration says confidence_level=.95 and interval_scope="pointwise".
Keep those bytes unchanged. The proposed additional confirmatory family requires
researcher approval plus a versioned analysis contract/schema that can record
its separate level and scope. If that proposal is not approved before source
freeze, retain estimation-only pointwise reporting and prohibit joint
confirmatory claims. Do not choose a multiplicity policy after observing results.

### 6.3 Absolute rates, rare outcomes and zero events — D/R/F

Always report event counts, exposure counts and population distribution alongside
absolute rates and paired contrasts. A nonparametric bootstrap cannot invent
unseen events: a [0,0] failure-rate interval or zero-width contrast must be labeled
degenerate and uninformative about unseen events/equivalence. Do not apply the
binomial "rule of three" using 6,000 dependent device trials or 30,000 repeated
stored invocations as if independent.

For zero observed failures in a predefined arm-condition endpoint, a conservative
supplement is proposed at the **population** level: let Z_g=1 if any failure occurs
in that population's fixed 300-attempt workload. Assuming 20 independent,
identically distributed population workloads, observing all Z_g=0 gives the
one-sided pointwise 95% upper bound
`q_upper=1-.05^(1/20)`, approximately 13.9%, for the probability q that a new
population workload has any failure. This follows by solving
`P(all zero)=(1-q)^20=.05`; it is an application of binomial inversion to
independent cluster indicators, not to individual attempts. See
[NIST's exact binomial confidence-interval construction](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

That q is a different estimand from per-attempt FRR. Since a population's failure
fraction is bounded above by Z_g, q_upper also gives a deliberately loose upper
bound on the mean failure fraction under the same balanced-workload assumptions;
it must not be presented as a precise attempt-level interval. Report it separately
from the two-sided bootstrap interval, with its one-sided/pointwise scope. Do
not apply it to conditionally eligible cohorts with undefined or varying workload
definitions, nor to a cryptographic adversary's success probability. Approval
and future implementation are required; if its independence assumptions cannot
be justified, report counts and the limitation without this bound.

### 6.4 Precision and practical importance — R/D

Before execution, approve minimum practically important reliability differences
and source/establishment timing costs, and acceptable uncertainty. Do not derive
these thresholds from the pilot's favorable stress result. A statistical
departure from zero need not be practically useful; require the relevant interval
to clear the approved practical threshold for that stronger claim. An interval
containing zero is not evidence of equivalence or noninferiority.

No power or narrow-absolute-rate guarantee is established for 20 populations.
Rare nominal events and floor-limited attenuation may be inconclusive even with
many repeated trials. Researchers must accept those precision limits or approve
a separately versioned design revision before execution; no allocation or
sigma/rho change is made by this document.

## 7. Formal timing measurement plan

### 7.1 Primary estimand and cold-start companion — R/F

Recommend **warmed-process, fresh-endpoint, first-window** timing as the primary
software timing estimand: a process with relevant compilation completed, but a
new isolated pipeline/session for each measured arm attempt. Preserve the
allocation of 30,000 matched identities and 90,000 arm attempts. Reliability remains based on
all formal attempts. A warmed process is not a warm/reused authenticated session.

Report cold-start separately as a diagnostic with a distinct denominator and
process/cache boundary. The pilot's first Majority-3 decode was 2404.1319 ms and
establishment 2405.5401 ms. These saved observations are consistent with first-use
compilation but do not profile its precise cause. Current
`cold-process-no-harness-warmup-v1` mixes one process's first use and subsequent
attempts; it is neither replicated cold-start performance nor steady-state proof.
Keep the historical outlier in the historical summaries.

Cold diagnostics should record interpreter/import, backend initialization,
enrollment/provisioning, establishment and first-window boundaries separately.
Recommend six fresh diagnostic processes, one for each arm permutation; label
which arm performs the process's first BCH decode. Record the first use of every
arm even when its decoder is already warmed by an earlier arm. This describes
order/cache effects, not six independent populations. Process-cold with a stated
disk-cache state is not machine-cold. Diagnostic replication count and cache
policy require approval; these proposed extra diagnostics are outside research
sample denominators and are not authorized now.

### 7.2 Warm-up procedure — R/F

Proposed fixed procedure before formal measurements: provision separate synthetic
warm-up material outside the formal population/measurement seed identities, then
perform **20 complete warm-up attempts per arm**, including one fixed window
and recording callbacks for every activated session. Cycle permutations; use fresh
endpoints and OS handshake randomness. Include fixed valid reconstruction and
ordinary reconstruction-refusal fixtures so expected success/failure paths are
exercised, recording which fixtures and compiler signatures were reached.
Warm-up fixture selection/counts must be frozen; 20 is a proposed operational
choice, not an established sufficiency result. If all 40 PUF warm-ups complete,
their policy work is 80 reads and 40 decodes; any ordinary refusal reduces the
number of warm-up windows. Record actual operations and outcomes rather than
assuming all callbacks ran. All warm-up samples are excluded from research N
and from formal latency distributions and reported separately.

Validate this procedure on separately authorized development fixtures before a
freeze. Require evidence that required JIT signatures are compiled; do not stop
warming merely when timings look favorable. If unexpected lazy compilation is
detected after formal measurement starts, preserve all records, flag the timing
protocol failure and stop the timing claim rather than trimming the slow point.
No adaptive warm-up or post hoc exclusion based on formal latency is permitted.

Record galois/Numba versions, JIT mode, cache configuration/location and whether
cache contents were reused. Never delete or alter a user's cache in this review.
A fresh process can use a disk cache; a warm import need not imply decode
compilation. Week 7's `warmup_iterations=20` field did not execute a harness
warm-up loop, and Week 8's temporary legacy-validation value of 20 also does not
warm anything. Current Week 8 schema/configuration requires zero warm-up and the
cold profile; implementing this recommendation requires future versioned runtime,
schema and configuration changes, approved before formal source freezing.
Because the current planner includes config_sha256 in trial identities and its
shuffle seed, an approved timing-profile configuration change would also change
derived identity values, block order and plan hash even with the same allocation
and seeds. Preserve the scheduler algorithm and review the exact new plan; never
claim that a warmed future plan is byte-identical to the current cold plan.

### 7.3 Environment, scheduling and measurement — I/R/F

| Item | Required formal treatment | Status |
| --- | --- | --- |
| Clock | Retain monotonic `perf_counter_ns`; record resolution and units. No wall-clock subtraction for stage durations. | I; D for formal characterization |
| Environment | Record CPU model, cores/logical processors, RAM, OS/build, Python executable/build, dependencies, process ID, thread/JIT settings, BLAS/OpenMP thread environment, affinity, power plan/AC state, concurrent load and observed thermal/throttling conditions. | Existing Python/platform/package metadata I; expanded record F |
| Process policy | One characterized serial process for the primary cohort; no unplanned parallel execution. Retain scheduler/seeds and six-permutation balance; freeze the exact approved plan after any reviewed profile change. Report that process-to-process performance uncertainty is not estimated by population resampling. | I for serial instrumentation; R for plan |
| Order/drift | Retain six-permutation balancing and deterministic block shuffle; inspect latency versus execution index, condition and arm position. Record interruptions/background events; retain slow valid observations. | I for order; F for formal diagnostics |
| Source boundary | Retain actual acquisition/retrieval spans and disclose in-call independent noise generation versus excluded shared-Z setup. Simulated acquisition time is a software operation, not oscillator hardware measurement time. | I |
| Establishment boundary | Direct root includes selected source, reconstruction if applicable, actual independent verification/admission, OS-random request construction, HKDF and mutual confirmation/audit work. Preserve all-attempt and successful-session distributions separately. | I; F for warmed cohort |
| Excluded setup | Manufacturing/reference enrollment, helper encoding, stored provisioning, verifier records, endpoint allocation, shared-Z generation, fixed-window construction and any model loading are outside establishment. Account separately when discussing total system startup. | I |
| Nested spans | Inclusive parents contain children. Exclusive duration subtracts immediate children only. Authorization exclusive excludes verification; reconstruction includes BCH. T's absent stages stay null. Never sum nested spans or add stage p95 values as total p95. | I |
| Observer/storage | Instrumented wrappers and endpoint in-memory audit are included where called. Source hashing, experiment JSONL writing/fsync and validation replay occur outside timed attempt roots; record wall runtime/resource costs separately. Do not subtract guessed observer overhead. | I for boundaries; F for resource characterization |
| First window | Existing root includes sealing, HMAC/window verification, release and recording callbacks after establishment. Report per eligible session and accepted-only distributions; no two-second capture interval is included. | I; D/F for expanded report |
| Recurring windows | Secondary, separately approved fixture on existing session state with exact-next sequences and the same fixed payload shape. Recommend 20 measured windows after sequence 0, reporting within-session dependence and recording-consumer identity. Do not silently add these to the current formal cohort. | R/F |

The first-window primary cohort is the only window workload fixed by the current
design. A recurring-window diagnostic changes the window workload and must have
an approved measurement/evidence plan or be explicitly deferred without throughput
claims; neither alternative changes the 90,000 establishment attempts automatically.

### 7.4 Timing summaries and comparisons — D/R/F

For each arm-condition-stage, publish span count, arithmetic mean, median, p95,
p99 and maximum with stated nanosecond-to-ms conversion. Total p95 comes from
measured establishment/first-window roots, never stage-quantile addition. Retain
the linear interpolation convention already used by `duration_summary()`.

Primary cost comparisons are matched **all-attempt mean establishment/source
duration differences**, summarized within population then across populations.
Report positive PUF-minus-stored and M-minus-S differences in ms. Use the common
population bootstrap draws for intervals. Quantile differences are separately
defined as differences of marginal pooled quantiles, recomputed in each draw;
they are not quantiles of paired differences. A summary of paired per-trial
differences is a third, explicitly different statistic.

Successful-session-only timing conditions on source-dependent survival. Report
it with N_sess and C/D/I/W strata; do not interpret its contrast as the all-attempt
policy effect. Lower all-attempt time caused by earlier refusal is not faster
successful authentication. A secondary common-success matched subset can be shown, but is
still a selected subset. First-window timing is available only after activation;
absence after source failure is inapplicable, never zero latency. Repeated stored
controls and multiple windows remain inside their population/session clusters.
An observed window-stage speed difference despite identical downstream code is
not a change to cryptographic algorithm complexity or physical sensor latency.
Timing resampling describes input-population variation conditional on the single
recorded process/environment. It does not account for arbitrary temporal
autocorrelation or machine drift. If order diagnostics undermine the required
cluster assumptions, suppress inferential timing intervals and report descriptive
paired results; any independent-process/block replication design needs separate
approval. Never count extra process runs as new simulated population clusters.

## 8. Stored-credential control and the 32-bit limitation

**I/D:** T retrieves a bound four-byte `StoredCredentialRecord` from trusted
in-process storage, provisioned from the same enrollment credential. It performs
zero runtime PUF measurements, majority votes and BCH decodes and never
fabricates reconstruction success. It still invokes the real independent
credential-verification/admission service and the same downstream protocol.

T therefore isolates retrieval cost versus acquisition/reconstruction and
source-dependent access to common authentication. Source timing and end-to-end
timing are complementary: their difference also includes validation, request and
observer effects, not just an idealized BCH subtraction. This control does not
independently establish physical unclonability, physical entropy, extraction
resistance, equivalent key custody or real-headset provisioning security. Both
the receiver's credential registry and local service/key providers are trusted
co-located software assumptions, not secure hardware or remote attestation.

The reconstruction target contains **32 bits**, with four fixed padding bits
forming the BCH message. `derive_session_key()` emits 32 bytes, but a 256-bit
HKDF output does not turn a 32-bit secret into 256 bits of guessing resistance.
HKDF can redistribute existing secret uncertainty; it does not create missing
credential entropy. See [RFC 5869, section 4](https://www.rfc-editor.org/rfc/rfc5869.html#section-4).
Here handshake salt/transcript fields are public, and captured confirmation
proofs permit testing credential guesses as documented in the
[protocol specification](authentication-v2-protocol-spec.md). Public synthetic
seed/replay inputs make this experiment's credentials reconstructible; 32 bits
is an upper bound on nominal credential size, not a secrecy claim for these
published simulation inputs. No new key mechanism or security feature is proposed.

## 9. Required eventual figures and tables

All items in this section are **D/F**: reporting requirements, not existing formal
results. Each display must state condition, eligible denominator, 20 population
clusters, interval method/scope, timing profile and source/configuration identity.

| Display | Required content and dependence disclosure | Status |
| --- | --- | --- |
| Allocation/provenance table | Planned versus persisted/completed coverage, cluster/device counts, seeds, versions, environment, runtime versus setup/warm-up/replay work; all aborted runs disclosed. | D/F |
| C/D/I/W and retrieval table | Per-arm/condition counts and FRR; T reconstruction cells marked inapplicable, not zero; unavailable/malformed retrieval separate. | D/F |
| Primary reliability plot | Nominal/stress paired Delta estimates, population points and interval scopes; show A90 in a contrast panel with A50 secondary. | D/F |
| Noise-response plot | Sigma=.10 panels for rho=0,.50,.90 and a separate sigma=.25/rho=0 stress point. No fabricated correlated-stress grid, continuous fitted response surface or measured-bit-rho label. | D/F |
| Common-mode invariance plot | Linked nominal/control bit/reconstruction agreement and any numeric-fault counts; same realization links, no independent replicate error bars. | D/F |
| Stage-flow table | N, V, A, Q, N_sess, Vw, W_win, R; N-based rates and stage-conditional rates with denominators, source refusal/mismatch/policy/infrastructure distinctions. | D/F |
| Security evidence matrix | Normal-run W opportunities/refusals and zero-invariant counts separately from named negative-test cases/results; no aggregate security percentage. | D/F |
| Timing distributions | Per-condition warmed acquisition/retrieval, reconstruction, establishment and first-window distributions; all-attempt versus successful strata and sample counts; cold diagnostics in separate panels. | D/F |
| Timing/order and cost plots | Population-level paired differences, execution-index/order diagnostics and direct-root p95; exclusive component means may form a partition, stage quantiles may not. | D/F |
| Limitations/resource table | Setup/provisioning exclusions, disk/wall time and peak-memory observations, observer boundaries, credential size, simulation and custody limits, unimplemented recurring/model timing. | D/F |

Do not produce a single pooled nominal/control confidence band or a pooled
three-source reconstruction FRR. Any cohort-wide timing average is a declared
equal-cell workload average rather than an estimate of an actual deployment mix.

## 10. Limitations and prohibited claims

**D:** This is software-only simulated-PUF research. Prohibited conclusions are:

- Quest 3/physical RO-PUF validation, physical unclonability or physical entropy.
- Wireless-network latency, real headset provisioning, hardware key-extraction
  resistance or security equivalence between stored retrieval and a physical PUF.
- Actual SNN/anomaly-model execution, classification accuracy, energy advantage
  or real-time XR compliance from recording callbacks and fixed stationary windows.
- Production-strength security from a 32-bit credential or 256-bit HKDF output;
  cryptographic forgery bounds from zero observed unauthorized releases.
- Every sigma/rho combination, correlated stress, aging, noisy enrollment or
  unmodeled environmental drift. The configured common offset is an algebraic
  cancellation check, not comprehensive environmental robustness.
- Independent samples for readings, repeated stored controls, linked common-mode
  realizations, repeated windows or deterministic evidence replay.
- Statistical superiority, equivalence, zero underlying failure probability or
  practical significance from pilot rates, zero events, degenerate intervals or
  unadjusted multiple comparisons.
- Steady-state or replicated cold-start performance from the historical mixed
  first-use timing cohort; process-to-process or physical transfer uncertainty
  from resampling simulated populations within one Python process.

**I/D — Evidence for RQ5:** A normal legitimate-source run may observe W and show
its refusal before HKDF, and may verify no release after ordinary source failure.
It does not guarantee that W, invalid tags, malicious providers, replay, gaps or
revocation will occur. Dedicated tests such as
`test_real_puf_cdiw_partition_and_original_acquisition_behavior`,
`test_unavailable_malformed_and_wrong_stored_credentials`,
`test_invalid_hmac_never_releases_for_any_source`,
`test_exact_next_replay_rule_applies_to_every_source`, latest-invocation status,
capability refusal and faulting-callback cases provide the corresponding finite
negative evidence. Preserve their exact tested source and archived outcomes.
Report an unobserved W opportunity as unobserved, not "100% rejected". Tests
supplement source review; neither is a formal proof against a compromised process.

## 11. Unresolved decisions requiring researcher approval

Every row is **R**. A decision record must identify approver, date and the approved
alternative before formal source/configuration/analysis freezing.

| Decision | Recommended resolution | Consequence if unresolved |
| --- | --- | --- |
| Inferential target and independence | Approve the 20 disjoint simulated population clusters and conditional simulation-law target; accept no physical-population inference. | Cluster interpretation and uncertainty claims remain provisional. |
| Primary family and multiplicity | Approve the three contrasts and additional Bonferroni confirmatory intervals alongside .95 pointwise estimation, with separate analysis metadata; otherwise estimation-only reporting. | No joint confirmatory claims. Existing configuration must not be silently reinterpreted. |
| Practical thresholds and precision | Approve minimum relevant reliability/timing effects and acceptable uncertainty; accept floor-limited nominal/correlation conclusions or separately approve a design revision. | No practical-success/equivalence claim or assertion allocation is adequately powered. |
| Absolute zero-event uncertainty | Approve the population-workload supplementary bound and its assumptions or retain explicit count-only limitations. | No unsupported independent-attempt binomial bound. |
| Primary timing profile | Approve warmed process/fresh endpoints, fixed warm-up procedure and cache policy; separately approve six-process cold diagnostics or explicitly defer them. | Current cold/no-warm-up implementation cannot supply primary warmed claims. |
| Recurring-window scope | Approve a separate 20-window diagnostic plan or explicitly defer recurring timing. | No recurring throughput/latency claim; current first-window workload stays unchanged. |
| Faculty target mapping | Specify whether "authentication" means establishment or per-window verifier work; map post-window target to exact callbacks and exclusions. Approve thresholds separately from historical provisional 1/20 ms and backup targets. | No faculty-target attainment or unauthenticated-overhead claim. |
| Fault/re-execution policy | Approve all-scheduled coverage, no selective noise retries, diagnostic-only incomplete bundles and disclosure of every aborted run. | No defensible complete-cohort analysis after infrastructure failure. |
| Formal authority and resource budget | Name the execution owner, protected output policy, CPU/process setting, runtime/disk/memory budgets and source-freeze reviewer. | Keep formal execution disabled. |

No allocation revision is intrinsically required to describe the planned study.
Any additional populations/devices, different conditions or confirmatory target
requiring more precision needs explicit approval and a new reviewed configuration.
This document does not request or imply permission to execute such a revision.

## 12. Ordered prerequisites for formal execution

1. **R:** Resolve section 11, record the inferential target, practical thresholds,
   primary family, precision limitations and whether deferred diagnostics remain
   outside the formal claim set. Preserve the current allocation unless separately
   approved.
2. **I/D:** Archive the reported 483-test checkpoint with exact commands, counts,
   environment and source hashes; preserve the historical 475-test attribution
   and original bundle. Do not describe this review as a test rerun.
3. **F:** Implement and independently review the approved three-arm clustered
   analysis, interval/multiplicity/zero-event rules, coverage reporting and analysis
   metadata/schema. Preserve matched population weights and all denominators.
4. **F/R:** Implement only the approved future timing protocol, isolated warm-up
   records and environment characterization under a reviewed version; define
   cold/recurring diagnostics or document their deferral. No such implementation
   is performed in this assignment.
5. **F:** Validate future analysis/timing changes on bounded non-research fixtures,
   including missing evidence, zero denominators/events, population pairing,
   source-isolation, completion and failed-second-pass accounting. Obtain review
   without changing the authentication architecture.
6. **D/F/R:** Establish runtime, storage and peak-memory feasibility for 90,000
   attempts, including current per-attempt hashing/fsync, retained rows, schema
   checks and all validation phases. Current in-memory design has no measured
   formal peak-memory guarantee. No optimization is authorized by this document.
7. **I/D/F:** Keep experimental operations separate from setup/warm-up and scoped
   validation. For the unchanged formal allocation, one complete reconciliation
   would replay 120,000 measurements and 60,000 decodes plus 120 references;
   two-pass finalization would replay 240,000/120,000/240; each later audit would
   add its own 120,000/60,000/120. These are source-derived expectations, not
   observed work, and add zero samples. Failed/partial work is not inferred as
   completed. Formal support for these receipts remains future work.
8. **R/F:** Review a separately protected formal output namespace, authorization,
   exclusive creation, interruption/completion markers and historical-path
   protection. The current nonformal namespace/token is not formal authorization.
9. **R/F:** Freeze approved source, exact configuration/plan hashes, schemas,
   analysis implementation/seed mapping, environment, timing protocol, decision
   record and test receipts. Current corrected source is distinct from the
   historical executed snapshot; never rehash old evidence to claim otherwise.
10. **R:** Obtain a separate explicit execution authorization after prerequisite
    review. Only future authorized engineering may introduce a formal execution
    path. Formal execution remains disabled at the end of this assignment.

## Review inputs and identity record

**I/D:** Read-only inspection covered the following authoritative locations;
relative links refer to the repository checkout reviewed on the date above:

- [Planner/configuration validation](../src/python/puf_snn/experiments/three_arm_auth_v1.py):
  `StudyConfig`, `compile_plan`, `stored_provider`.
- [Runtime](../src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py):
  `instrument`, `ObservedProvider`, `execute_attempt`.
- [Evidence and corrected receipts](../src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py):
  `reconcile`, `group_metrics`, `summarize`, `audit_evidence`, `EvidenceRun.finalize`.
- [CLI](../src/python/scripts/run_three_arm_auth_v1.py),
  [planned configuration](../configs/three_arm_auth_v1.json),
  [nonformal configuration](../configs/three_arm_auth_nonformal_pilot_v1.json),
  and the [configuration](../schemas/three-arm-auth-config-v1.schema.json),
  [plan](../schemas/three-arm-auth-plan-v1.schema.json),
  [attempt](../schemas/three-arm-auth-attempt-v1.schema.json) and
  [summary](../schemas/three-arm-auth-summary-v1.schema.json) schemas.
- [Preserved Week 8 methodology](week8-three-arm-auth-methodology.md),
  [accounting addendum](week8-validation-work-accounting-addendum-20261020.md),
  [pre-pilot report](week8-three-arm-auth-implementation-report.md) and
  [historical static manifest](week8-three-arm-auth-source-manifest.json).
- [Week 7 harness methodology/validation](week7-majority3-auth-correlated-harness-validation.md),
  [noise model record](week7-correlated-noise-model-validation.md),
  [two-arm configuration](../configs/majority3_auth_correlated_v1.json),
  [planner/enrollment](../src/python/puf_snn/experiments/majority3_auth_v1.py),
  [runtime](../src/python/puf_snn/experiments/majority3_auth_runtime_v1.py),
  [analysis](../src/python/puf_snn/experiments/majority3_auth_analysis_v1.py),
  [environment metadata](../src/python/puf_snn/experiments/majority3_auth_evidence_v1.py),
  [noise source](../src/python/puf_snn/experiments/correlated_noise_v1.py), and
  [reconstruction configuration](../src/python/puf_snn/reconstruction/credential.py).
- [Three-arm tests](../tests/experiments/test_three_arm_auth_v1.py),
  [protocol specification](authentication-v2-protocol-spec.md),
  [HKDF/session implementation](../src/python/puf_snn/auth/session.py),
  [faculty decision memo](faculty-decision-memo.md) and
  [feedback consolidation](week6-feedback-consolidation.md).
- Historical executed evidence:
  [October 20 bundle](../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/),
  including its existing source/configuration/plan/attempts/summary/receipts.

Historical executed source ID:
`83001370f5a65f5d8c6cb55c38bd6f239a6c693a065182b22e1b24575e695153`.
Current corrected 87-file source-set digest, computed by read-only hashing of the
same source-manifest paths:
`e0ac0f0763f7466f615770b99ec75e629ffa20f6f4be8c13998e8ad66a30db4c`.
The latter is a **static review fingerprint, not an execution receipt or final
formal source freeze**. It excludes this new document, as the existing runtime
source-path list does. The historical static documentation manifest is also a
different artifact and must not be mistaken for the corrected runtime identity.

Reviewed planned-configuration byte SHA-256:
`2b00e78ec17aa67d5d745ca1ae4cc26e62fa7c4958e59a4cc857fa28d528185a`.
Reviewed nonformal-configuration byte SHA-256:
`7b04d44c7145d99bba61ac6241065a5ddac81e5e47dc43a4eb85821af9ff3713`.
Byte hashes differ from canonical-object configuration identities when formatting
differs; the historical saved canonical config ID is
`f08c74bbc1e44e8a73dfc8038580df9c9a91acdf3fc6da1bce643f58472166ce`.

Only this new versioned review document is created by this assignment. Source,
configurations, allocation, schemas, analysis code, prior documentation, research
logs and historical evidence are preserved. No tests, replay audit, experiment,
package installation, commit, push or formal execution was performed.
