# Week 6 reconstruction alternatives: design and feasibility audit

Version: `week6-reconstruction-alternatives-v1`. Date: 2026-10-07 (America/New_York). **Design only.** Claims below distinguish repository evidence, deterministic library verification, mathematical implications, and proposed experiments. This document is the only requested file change.

## 1. Research objective and faculty requirement

Compare the frozen single-read reconstruction baseline with majority-3, majority-5, and stronger BCH. The nominal research target is FRR <=0.5%, with latency and entropy tradeoffs reported. Independent verification is a separate pre-HKDF boundary: rejecting a wrong candidate does not repair reconstruction availability.

**Repository evidence:** `docs/week6-start-current-repo-audit.md` records the newest faculty request for a reliability-alternative plan and first results; `docs/research-logs/will.md`, Week 6 Reconstruction Evaluation, proposes these alternatives. These are repository accounts, not an independently inspected original faculty message. The supplied task establishes the present requirement. The older `docs/faculty-decision-memo.md` does not establish this specific experiment. First results remain future work.

Audit provenance: branch `main`, HEAD `acc46478dcde2ecffe706d8eab355b453b94fa30`. No AGENTS.md was found in the repository search or checked parent locations. Initial index was clean. Existing unstaged modifications: `docs/research-logs/will.md`, `src/python/puf_snn/pipeline_timing.py`. Existing untracked files:

- `configs/tier1_v2_experiment_v1.json`
- `docs/authentication-v2-protocol-spec.md`
- `docs/week6-start-current-repo-audit.md`
- `docs/week6-tier1-v2-experiment-plan.md`
- `docs/week6-tier1-v2-final-local-review.md`
- `docs/week6-tier1-v2-implementation-validation.md`
- `docs/week6-tier1-v2-real-artifact-preflight.md`
- `docs/week6-v2-protocol-spec-prep.md`
- `schemas/tier1-v2-attempt-v1.schema.json`
- `schemas/tier1-v2-summary-v1.schema.json`
- `schemas/tier1-v2-trial-plan-v1.schema.json`
- `src/python/puf_snn/tier1_v2.py`
- `src/python/scripts/run_tier1_v2.py`
- `tests/tier1/test_tier1_v2.py`

All are prior user work. A pre-document inventory covered 698 existing tracked/nonignored untracked files. SHA-256 of its sorted JSON path-to-SHA-256 mapping: `f684aac005141c19b0b9e60e92909660f47428e651ca00e39babf2604caf318c`. It excludes this plan and does not claim coverage of ignored artifacts. Sandbox startup failed; inspection used approved unsandboxed processes. No packages were installed.

## 2. Frozen baseline

**Repository evidence:** `configs/puf_baseline.json` defines six devices per population, 128 oscillators, adjacent pairing, nominal frequency 100.0, manufacturing SD 1.0, aging SD 0, noiseless enrollment, zero environmental offset and nominal measurement-noise SD 0.1. Its 100 repeated reads and six-point historical sweep are not automatically inherited here.

`puf/ro_puf.py` returns a 64-element tuple of Python integer bits for ordered pairs `(0,1), (2,3), ..., (126,127)`. `reconstruction/credential.py` fixes indices `tuple(range(63))`, omitting response bit 63. `ReconstructionConfig` rejects every changed field. `HelperData` holds 63 helper bits, frozen config and optional enrollment ID. `enroll(reference64, credential32, config, enrollment_id=...)` encodes four credential bytes MSB first plus four trailing zero bits and XORs the codeword with reference positions 0..62. `reconstruct(noisy64, helper_data, config=None)` performs one decode and returns `ReconstructionResult`, without evaluator truth or verification.

`reconstruction/bch.py` fixes primitive narrow-sense systematic BCH(63,36), designed distance 11, t=5, GF(64) polynomial `0x43` (x^6+x+1), primitive element 2, first root exponent 1, generator `0x86E8113`, and galois 0.4.11. External tuples are highest-degree-first/MSB-first. Backend decode requests `output="codeword", errors=True`; count -1 suppresses the candidate. Other results are checked for shape, binary values, polynomial remainder and distance equal to reported count. A valid codeword is only a candidate; credential reconstruction separately checks padding.

Frozen evidence: `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/` and sibling audit JSON. Saved audit reports PASS, 84,000 attempts/unique readings and 120 enrollments. Saved `baseline_summary.csv`: 12,000 nominal attempts, 11,805 correct, 186 decoder failures, seven invalid-format outcomes, two valid-format wrong credentials, FRR 195/12,000 = 1.625%, selected BER 0.03197089947089947. Other 72,000 attempts cover six sweep cells; sweep SD 0.1 is distinct from primary nominal. Across all cells the saved verifier report identifies 430 wrong valid-format candidates. These are historical observations, not fresh comparison results.

Inspected artifacts include manifest, metadata, summary, audit and formal reports (`docs/layer2-formal-evaluation-week5.md`, `docs/credential-verifier-formal-results-week5.md`). Manifest attempts hash: `8def501bc44a9ab30b66c50665309be6e7e48d20d55222699bd44b830748866a`. This task did not recount all historical rows or rerun their auditor.

`src/python/scripts/run_reconstruction.py` is the formal runner: enforces historical cohort/config, checks archived PUF tables, separates credential streams, times reconstruct only, retains all four outcomes and partial failures, and seals reconciled evidence. It must not be invoked for this design. Existing `configs/reconstruction_experiment_v1.json` pins 20 historical seeds, checkpoint `40da3a388983030b7b696ce7bf2b801e0ed6903f`, credential stream and bootstrap settings. Existing historical latency is not full-path latency.

## 3. Evidence-based rationale for the selected alternatives

**Repository evidence:** Most nominal failures are decoder failures; the saved selected-error histogram includes 159 six-error cases. This motivates an additional correction bit but does not predict a newly measured B1 success count.

**Mathematical implication:** Conditional on a device/bit flip probability p and independent reads, majority-3 error is `3*p^2-2*p^3`; majority-5 error is `10*p^3-15*p^4+6*p^5`. Both improve p when 0<p<0.5. Apply per device/bit manufacturing margin, not to pooled BER as though all bits were identical.

**Hypotheses:** Voting reduces effective BER/FRR at additional acquisition cost. B1 increases guaranteed correction at lower entropy and different decoder cost. Neither alternative is assumed to meet the target. B1 compares a joint code/credential-format tradeoff, not code strength in isolation.

## 4. BCH(63,30,t=6) feasibility findings

**Library verification: PASS for algebra/API feasibility.** Installed Python 3.12.4, galois 0.4.11, numpy 2.5.3, numba 0.67.0, llvmlite 0.49.0, scipy 1.18.1. Galois is pinned in requirements.txt and pyproject.toml; broad constraints for other packages are not a complete environment lock.

Inspected constructor: `galois.BCH(n, k=None, d=None, field=None, extension_field=None, alpha=None, c=1, systematic=True)`. Checked construction:

```python
field = galois.GF(64, irreducible_poly=0x43, primitive_element=2,
                  compile="python-calculate")
code = galois.BCH(63, 30, d=13, field=galois.GF2,
                  extension_field=field, alpha=field(2), c=1,
                  systematic=True)
```

Observed n=63, k=30, d=13, t=6; primitive, narrow-sense and systematic flags true. Generator degree 33, integer `0x37cd0eb67`:

`x^33 + x^32 + x^30 + x^29 + x^28 + x^27 + x^26 + x^23 + x^22 + x^20 + x^15 + x^14 + x^13 + x^11 + x^9 + x^8 + x^6 + x^5 + x^2 + x + 1`.

Designed distance 13 guarantees correction through six errors. This is not an exhaustive computation of true minimum distance. There are 33 parity bits, no shortening or byte padding. `encode(message, output="codeword")` maps GF2 shape `(30,)` to `(63,)`; default decode returns `(30,)`; `decode(word, output="codeword", errors=True)` returns `(63,)` plus scalar count. Coefficients descend in degree; message positions 0..29 form the systematic prefix. Installed `_codes/_bch.py` explicitly documents descending coefficient conversion. Restrict the proposed adapter to these single-vector shapes.

One deterministic check used message `[1]+[0]*28+[1]`, producing:

`100000000000000000000000000001011000010101110001001111011010100`

Flips at `[0,10,20,30,40,62]` decoded to the original word with count 6. Shapes, prefix equality and default message decode passed. To reproduce, construct above, call `galois.GF2.compile("python-calculate")`, encode the fixed message, flip those positions in a copy, decode and assert exact equality/count. The check used Python `-B`/disabled bytecode, `NUMBA_DISABLE_JIT=1`, and python-calculate arithmetic. No RNG, PUF call or timing benchmark was used; future ordinary JIT execution must be tested separately.

**Compatibility:** 63 codeword bits map directly to existing positions 0..62. Production BCHCodec/ReconstructionConfig/HelperData reject alternate parameters. B1 requires a separate small experimental adapter, mirroring shape/count/remainder/candidate validation with its own constants. Reuse public PUF and verifier APIs. No shared implementation change is needed. If subsequent validation contradicts this identity, stop B1; do not silently substitute another code.

## 5. Experimental 30-bit credential representation

**Proposal:** One `u = credential_rng.getrandbits(30)` per B1 device enrollment. Four-byte representation: `u.to_bytes(4,"big")`. The top two bits of byte 0 are fixed zero; endpoints are `00 00 00 00` and `3f ff ff ff`. Message bit j is `(u >> (29-j)) & 1` for j=0..29. All 30 BCH information bits carry credential bits. The two fixed representation bits are not BCH padding. No unrestricted 32-bit credential is truncated.

Enroll helper `h[i]=reference64[i] XOR encode(message)[i]`, i=0..62. Decode `response64[i] XOR h[i]`, interpret the 30 decoded bits as a big-endian integer and serialize to four bytes. Every well-formed 30-bit message has valid representation: B1 has no ordinary padding-rejection mechanism. Report invalid-format/padding count zero and structurally inapplicable; malformed backend output is an implementation error. A valid-format different candidate is a wrong credential, regardless of reported correction count.

**Repository evidence:** `auth/credential_verifier.py` checks exactly four bytes, not entropy. Reuse `CredentialVerifierRecord.enroll`, `CredentialVerifierStore`, `InMemoryCredentialVerifierKeyProvider.generate`, and `CredentialAdmissionService.verify(candidate_credential4, device_id=..., enrollment_id=..., reconstruction_id=...)` on isolated in-memory records. B1 binding ID: `w6-recon-bch63-30-v1`. Existing length-prefixed HMAC-SHA-256 bindings and constant-time comparison remain unchanged.

B0/A1/A2 share one baseline helper/credential per device and reconstruction ID `puf-snn-reconstruction-v1`; read policy stays in experimental metadata. B1 has a separate credential/enrollment. Exactly 120 baseline plus 120 B1 helper/verifier records, one generation per code/device. Generate a fresh independent OS-random 32-byte verifier key per run, unrelated to all simulation seeds; warmup uses another key/store. Never serialize keys/tags or generic verifier dataclasses. Runtime gets candidate and trusted bindings only; truth is consulted after verification for scoring. Skip verifier on decoder/format failure with explicit `not_invoked`. No Authentication-v2 record changes, HKDF or session calls.

## 6. Majority voting design

**Proposal:** Each matched device/condition/attempt defines independent read streams r=0..4. B0/B1 use r=0; A1 uses 0..2; A2 uses 0..4. Invoke `generate_response(device, pairs, 100.0, conditions, rng=...)` once per read, returning a full 64-bit tuple. Device and conditions stay fixed; stream seeds differ by read index. Never initialize all readings with the same seed.

For m=3/5 and each j=0..63, vote `int(sum(read[j] for read in reads) >= (m+1)//2)`. Odd counts prevent ties. Validate input shapes/binary types and pass the full voted tuple to unchanged `reconstruct(voted64, baseline_helper)`. It selects only positions 0..62; voted bit 63 cannot affect decoding. One-read configurations bypass voting.

Each configuration regenerates its assigned streams inside its own measured path, paying actual acquisition cost. Sharing cached responses would undercount latency. Reusing identical stream labels across configurations is deliberate matching; distinct read indices within one attempt are distinct measurements. Assert equality of shared prefixes after timing. Naturally identical bit vectors from separate reads must not be discarded/deduplicated.

Voting cannot correct persistent reversal or correlated errors. Conditional p=0.5 gives no improvement; p>0.5 makes majority favor the wrong bit. The present model covers independent measurement noise, not real temporal correlations or drift.

## 7. Controlled PUF noise/variation conditions

**Repository evidence:** `Device` is frozen, with immutable per-oscillator manufacturing offsets. `create_device(..., manufacturing_std=1.0, rng=...)` samples these once. Frequency is nominal + manufacturing + common environment + aging + fresh per-oscillator Gaussian measurement noise. Device identity/manufacturing are never resampled between reads. Enrollment honors supplied reference conditions and does not secretly average.

**Proposal:** 128 oscillators, adjacent pairs, nominal 100.0, manufacturing SD 1.0, environment 0, aging `None`, one noiseless reference per device. Formal conditions: `nominal` SD 0.1; `stress` SD 0.25. Reuse devices/enrollments across conditions with separate evaluation streams. Zero-noise correctness belongs in tests/smoke, not another formal cell.

The common environmental offset cancels mathematically in pair comparisons and is not a meaningful stress variable. Nonzero aging is explicitly rejected. Differential temperature/voltage effects and persistent drift require another model study. Stress here means independent measurement noise only. No stability selection, enrollment averaging, retries, favorable-device filtering or oscillator replacement.

## 8. Experimental groups and trial allocation

**Preregistered proposal:**

- B0: one read; BCH(63,36,t=5); 32-bit credential; existing reconstruction API.
- A1: three reads; majority then BCH(63,36,t=5); same B0 credential/helper.
- A2: five reads; majority then BCH(63,36,t=5); same B0 credential/helper.
- B1: one read; verified BCH(63,30,t=6); separate 30-bit credential/helper.

Use 20 fresh populations of six devices, 120 devices total. Exact population seeds are integers 2026100701 through 2026100720 inclusive; device indices 0..5. One enrollment generation g=0 per code/device. Fifty attempts a=0..49 per condition/configuration. Each cell: `20*6*50=6,000`; each configuration: 12,000; study total: **48,000 reconstructions**, in 12,000 matched four-configuration blocks.

There are 60,000 unique underlying measurement identities (five per block) and 120,000 actual generated responses (1+3+5+1 per block). Report both; paired regeneration is not independent new information. Enrollment/warmup/smoke are separate. This is smaller than copying 84,000 historical trials and uses new devices/streams.

Primary endpoint: nominal reconstruction FRR, each alternative versus paired B0. Stress and latency are secondary. Never use historical B0 results as fresh matched observations. B1 changes both code and credential format; report that confounding tradeoff explicitly.

## 9. Enrollment versus evaluation separation

**Exact stream specification:** For case-sensitive ASCII label S, `seed(S)=int.from_bytes(SHA256(S.encode("ascii")).digest(),"big")`; construct `random.Random(seed(S))`. Numeric fields use unpadded decimal; conditions exactly `nominal`/`stress`. Labels:

- `w6ra-v1:manufacture:{population_seed}:{device_index}`
- `w6ra-v1:reference:{population_seed}:{device_index}:0`
- `w6ra-v1:credential32:{population_seed}:{device_index}:0`
- `w6ra-v1:credential30:{population_seed}:{device_index}:0`
- `w6ra-v1:read:{population_seed}:{device_index}:0:{condition}:{attempt}:{read_index}`

Create each device once. Generate reference once at zero noise (no Gaussian draws consumed). Baseline credential uses one `getrandbits(32).to_bytes(4,"big")`; B1 as section 5. No global RNG or Python `hash()`. These are public nonsecret research seeds: resulting credentials are reproducible synthetic material, not deployable secrets. Store offsets/reference or sufficient deterministic reconstruction evidence and synthetic evaluator truth separately from runtime APIs.

Build blocks ascending by population, device, condition order `[nominal,stress]`, attempt; shuffle once with `random.Random(2026100791)`. Save the complete schedule before execution. For shuffled block b, rotate `[B0,A1,A2,B1]` left by b modulo 4. Each config occupies each slot 3,000 times. Precreate read RNG objects outside timing, fresh per config from its assigned labels. Generate actual responses inside timing in increasing read-index order. No timing-dependent randomization.

Reserve distinct prefixes `w6ra-smoke-v1` and `w6ra-warm-v1`; they never consume formal streams. No formal observations may choose seeds, sample size, noise, read count, code or warmup duration.

## 10. Statistical methodology

For each cell/device/population retain counts with denominators. Mutually exclusive ordinary outcomes: C correct, D decoder failure, I invalid format/padding, W valid-format wrong credential. Require `N=C+D+I+W`; FRR=`(D+I+W)/N`. Unexpected implementation/infrastructure exceptions are separate execution errors invalidating complete inference, never relabeled decoder failures or dropped rows.

Raw selected BER is constituent-read mismatches against reference divided by `63*m*N`. Also report first-read BER (denominator `63*N`, identical across matched groups) and effective post-vote decoder-input BER (`63*N`). Store selected errors for each read/effective response separately from decoder-reported correction count. Never pool stress with nominal to assess the target.

Verifier calls `V=C+W`; noninvocations `D+I`. Let CA/CR be correct candidates accepted/rejected, WA/WR wrong candidates accepted/rejected. Require `CA+CR=C`, `WA+WR=W`, `V=CA+CR+WA+WR`. Report rejection count CR+WR and both rates `(CR+WR)/V` and `(CR+WR)/N`. Wrong-candidate catch rate WR/W and correct-candidate verifier FRR CR/C use conditional denominators; zero denominator means null, not zero. Post-verification legitimate admission failure=`(N-CA)/N`: wrong credentials never count as legitimate success. Separately report operational nonadmission `(D+I+CR+WR)/N` and wrong acceptance WA/N, which differ if a wrong candidate is accepted. Any WA or unexpected CR requires correctness review.

For binomial proportions use exact two-sided 95% Clopper-Pearson: lower `BetaQuantile(.025;x,n-x+1)` (0 at x=0), upper `BetaQuantile(.975;x+1,n-x)` (1 at x=n). Record x,n,method,endpoints; use pinned installed scipy in future implementation. Pooled repeated-attempt CP intervals are descriptive binomial intervals, not exact population intervals under clustering. BER bits also cluster; use cluster uncertainty rather than claiming `63*m*N` independent samples.

At N=6,000, FRR 0.5% implies 30 expected failures, with binomial planning SE about 0.091 percentage points. Zero failures gives two-sided CP upper `1-.025**(1/6000)`, about 0.0615%. This supports a useful preliminary comparison with the historical 1.625% scale, not a guaranteed power or target-attainment claim. Spreading 50 attempts across 120 devices helps characterize heterogeneity; device count matters beyond attempt count.

Supplement with 10,000 percentile bootstrap resamples of 20 entire population clusters, seed 2026100792. Retain all six devices, conditions and configurations together; compute FRR/BER and paired alternative-minus-B0 differences. Use linear `(B-1)*q` quantiles at 2.5/97.5%. Report per-device/population distributions and worst observed device without exclusions. Twenty clusters are modest; zero-failure bootstrap intervals can degenerate and must not imply certainty. Preserve paired 2x2 outcome counts for all three contrasts. Comparisons are exploratory; no uncorrected three-comparison significance claim.

Target status: observed nominal FRR <=0.5%; separately indicate whether CP upper <=0.5%, and show cluster sensitivity. Strong generalization requires dependence-aware support with rare-event limitations disclosed. A complete study may find every alternative misses the target.

## 11. Latency measurement methodology

Use sequential execution and `time.perf_counter_ns()`. Initialize algebra, enrollment/helper/verifier records, schedule and RNG objects before timing. Record Python/packages/JIT/thread settings, machine/OS/CPU, clock resolution, power/background-load notes; keep execution settings fixed.

Start total immediately before first `generate_response`, stop after verification or explicit skip. Record total reading duration (sum of m acquisition calls), voting duration, reconstruction duration (helper XOR, BCH, validation/conversion/padding), verification duration and independently measured total. Stage boundaries must be nonoverlapping and within total; total includes local control overhead. Exclude truth comparisons, BER scoring, logging, enrollment and RNG construction. No precomputed response enters the timed path.

One-read groups: `vote_invoked=false`, vote ns=0. No candidate: `verifier_invoked=false`, verify ns=0. Conditional verifier latency uses V samples; all-attempt stage occupancy with zeros is labeled separately. Preserve failures/outliers. Report p50,p95,p99,max,sample count for every stage/total by cell, with outcome/admission strata. Use linear interpolation at `(n-1)*q`, retain ns, display ms, null for empty strata. No trimming or retries.

Proposed fixed warmup: 20 separate synthetic complete attempts per configuration at nominal noise, 20 deterministic encode/decode fixture cycles per code spanning clean/boundary/pinned beyond-radius cases, and 100 verifier passes plus 100 mismatches alternating. Separate devices/streams/key/store; exclude all warmup observations. Record cold setup/warmup separately. Current pure-Python feasibility check is neither warmup nor performance validation.

Simulation time is Python noise sampling, array operations, BCH software and local HMAC, not physical RO-PUF acquisition or Authentication-v2 handshake/inference latency. Historical nominal reconstruction-only median roughly 1.04 ms suggests tens of seconds of decoder work for 48,000 calls; this is only a rough extrapolation. Plan for minutes with JIT/environment uncertainty; establish runtime in a future nonformal smoke, not during this design task.

## 12. Security/entropy tradeoffs

B0/A1/A2 carry at most 32 credential bits; B1 at most 30, a fourfold smaller exhaustive space (2^30 versus 2^32, roughly half-space average search without replacement). Publicly seeded research credentials provide no secrecy; 30/32 describe the intended uniform format, not secrecy of evidence. Neither is production strength. HKDF/HMAC output length cannot restore missing entropy.

Helper remains 63 public bits. Under ideal uniform independent reference bits, full baseline BCH parity reveals 27 linear coset constraints; its four fixed message-padding bits further restrict the code to dimension 32, giving 31 effective constraints. B1 uses all 30 dimensions, giving 33 constraints. Thus effective dimension loss is two bits, not a claim of 36-bit baseline credential entropy. Bias/correlation/side information may further reduce security; helper length is not an entropy proof.

A credential guess plus helper/encoding yields a candidate reference. An attacker needs auxiliary information/oracle to identify the right guess. A protected independently keyed verifier HMAC tag is not by itself an unkeyed offline oracle without its key. Compromised key, exposed reference, or usable credential-derived protocol confirmation evidence may permit offline checking; neither 30 nor 32 bits resists exhaustive search. Online throttling does not fix offline guessing. Verification catches candidates, not entropy deficiencies; BCH also does not authenticate helper metadata.

B1 experimental public metadata adds code/version, k=30,d=13,t=6,generator and representation. A1/A2 add read/vote policy while preserving production helper schema. Underlying noiseless device uniqueness/pairing is unchanged, but larger correction neighborhoods may alter wrong-device admission behavior; this legitimate-device study measures no wrong-device FAR. Re-enrollment/helper-reuse leakage is outside scope; keep one generation. Production enrollment metadata and protocol remain unchanged.

## 13. Implementation architecture

**Future files only; none created now:**

- `src/python/puf_snn/reconstruction_alternatives.py`: isolated voting and B1 codec/config/helper/result adapter. Enforce constants, shape/count, independent remainder and received-to-candidate distance checks. Do not monkeypatch production cached algebra.
- `src/python/scripts/run_reconstruction_alternatives.py`: thin standalone config/streams/enrollment/schedule/timing/evaluation/evidence harness; call production APIs for B0/A1/A2 and experimental B1 adapter. Reuse public verifier, not session integration.
- `configs/reconstruction_alternatives_v1.json`: fixed complete study settings.
- `tests/reconstruction/test_reconstruction_alternatives.py`, `tests/experiments/test_reconstruction_alternatives_experiment.py`, plus a small versioned deterministic fixture if needed.
- `schemas/reconstruction-alternatives-attempt-v1.schema.json`: strict trial schema; keep schedule/summary checks focused rather than building a framework.

Reuse evidence patterns from the formal runner without executing/importing its historical cohort workflow. Recompute summaries from saved rows; independently test reconciliation expectations. No shared source change is currently required. Estimated complexity: low voting, moderate B1 adapter/fixtures, moderate paired harness/timing/accounting; roughly two to four focused engineering days including tests/review, not a measured estimate. Frozen model artifacts are unnecessary.

## 14. Proposed configuration and evidence artifacts

Future config explicitly fixes version/mode, all four groups/code identities/credential layouts, selected indices, PUF settings, exact populations/generations/attempts, named conditions, stream labels/hash conversion, schedule seed 2026100791, bootstrap seed 2026100792 and 10,000 resamples, quantile/CI methods and warmup policy. Include reviewed plan raw-byte SHA-256; snapshot resolved settings instead of inheriting future baseline JSON edits. Freeze exact environment/source identities before execution.

Use exclusive new directories `results/week-6/will/reconstruction-alternatives/<run-id>/`; never overwrite existing/partial runs, historical reconstruction or Tier-1 evidence. Artifacts:

- `config.json`, `trial_plan.json`, `metadata.json`, `warm_up.json`, `enrollments.json` (explicit synthetic evaluator material, no verifier keys/tags).
- `attempts.jsonl`, `summary.json`, `condition_summary.csv`, `per_device_summary.csv`, `per_population_summary.csv`, `latency_summary.csv`, `paired_comparisons.csv`.
- `reconciliation.json`, `manifest.json`, then `COMPLETE`; exceptions/interruption produce `INCOMPLETE.json`, never a full-cohort completion claim.

Trial fields include schema/version/run/mode, unique block/attempt/config ID, execution slot/order, population/device/generation/enrollment/reconstruction binding, noise/condition, read/stream identities, each response64 and effective response64, raw/effective selected error counts/BER numerators-denominators, decoder status/count/reason, candidate message/bytes if available, format result, evaluator C/D/I/W, verifier invocation/outcome and admission/correctness flags, stage/total ns and boundaries. Candidate/response evidence is synthetic only; retain failures without promoting suppressed backend payloads to candidates. Reference source/config/plan digests per row. Never serialize private verifier records through generic dataclass helpers.

Metadata: branch/HEAD, pre/post working-tree/index state, hashes of all runtime sources including dirty/untracked dependencies, plan/config/schedule digest, full package inventory, executable/version, machine/OS/clock, JIT/thread settings, exact command and UTC start/end. HEAD alone cannot reproduce dirty code. Review/freeze source bytes and reject changes during execution; staging/committing user work is not required merely to identify a content snapshot.

Manifest hashes raw bytes of artifacts except itself and completion marker; COMPLETE binds manifest hash/version/provenance/exact counts. Read evidence back for reconciliation before completion. Avoid recursive self-hashing: plan digest lives in config/metadata. Synthetic inputs/non-timing outcomes should reproduce with frozen environment; fresh verifier keys/tags and timing will not reproduce byte-for-byte. Preserve exact denominators and both nonformal/formal labels.

## 15. Tests and reconciliation requirements

**Repository evidence:** Inspected `tests/reconstruction/test_bch.py`, `test_credential.py`, `reference.py`, and `tests/experiments/test_reconstruction_experiment.py`. Existing coverage includes independent polynomial encoding/basis vectors, shapes/count errors, leading zeros, every single-bit position, all 1,953 two-bit patterns, selected higher-error cases, omitted bit, fixed wrong-padding/valid-padding miscorrections, immutable config, helper validation, truth isolation, no retries, partial evidence, source changes and manifest/summary accounting. No tests were run in this design task. Existing independent reference generator uses baseline-specific roots and cannot silently serve as B1 oracle.

Future gates:

1. Voting truth tables for 3/5, one-read identity if exposed, count/length/binary validation, no ties/mutation, omitted bit invariance. Verify call counts and distinct stream identities, not necessarily distinct observed bit vectors.
2. Independently derive B1 generator from roots 1..12 and binary cyclotomic closure over GF(64); test all 30 message basis vectors with independent polynomial division, exact endian/boundary vectors, every single-bit location and fixed patterns through six errors. Pin beyond-radius failure/miscorrection fixtures without assuming every seven-error case fails. No stochastic PUF trials needed for these fixtures.
3. Four-byte round trips for zero/max/individual bits/asymmetric values; reject B1 enrollment bytes with nonzero top two bits, prove all 30 information bits used. Wrong valid candidates remain W and get real verifier rejection, never C based on format alone.
4. Isolated verifier pass/mismatch, missing/disabled record, binding mismatch, missing key and invalid input cases. Truth excluded from runtime, D/I never invoke verifier, no session/HKDF/production record changes.
5. Exact shared read prefixes and separate manufacturing/reference/credential/evaluation streams; one enrollment per code/device; fixed rotated order; no retries/replacements; non-timing reproducibility.
6. Reconcile 48,000 unique row keys, 6,000 per cell, 120 devices/240 helpers, 120,000 formal read calls and all section-10 equations. Effective errors <=t must imply C. First-read selected BER must match across all groups. Verify protected sources/plan/config/manifest and recompute every summary from rows.
7. Nonnegative stage/total durations, no overlap, stage sum <= total, total sample N with ordinary failures, verifier conditional sample V, no warmup contamination. Duplicate/dropped/invalid rows, backend exceptions, source changes or interrupted evidence prevent COMPLETE.

Proposed future nonformal smoke: two separate devices, five attempts per condition/configuration = 80 attempts, with separate smoke streams and deterministic fixtures. Validate schema/reconciliation and runtime; never pool smoke rows into formal statistics. This smoke is not run or authorized by this design-only task. Provisional practicality gate: projected full warm execution <=15 minutes on intended host. If not, review before formal execution; never adaptively truncate. Fix correctness/schema defects and version/freeze the plan before formal work, retaining smoke evidence.

## 16. Risks and limitations

Uncalibrated software, noiseless enrollment, independent Gaussian noise and fixed heterogeneous manufacturing margins limit generalization. No physical PUF, differential environment, persistent drift, aging, noisy enrollment, re-enrollment or wrong-device attack results are produced. Fresh B0 may differ from 1.625% without indicating a defect.

B1 lacks padding rejection; greater correction radius may not improve every wrong-candidate category. Decoder count is not truth. Verification can block false admission but cannot restore availability. Entropy/helper changes are material. Repeated devices and shared inputs introduce dependence, and 20 clusters may yield unstable rare-event intervals. Timing depends on JIT/CPU/background activity; counterbalancing only reduces some drift. Meeting a simulated FRR target is no deployment/security guarantee.

## 17. Decision gates and readiness

**Stage 2 isolated implementation: ready to begin.** Majority voting has an unchanged production API path. B1 identity/shapes/fixed six-error decode are verified, 30-bit format is precise, and independent verifier isolation is feasible. No critical algebra/API blocker was found; an isolated B1 adapter is required because production config intentionally rejects it.

**Formal execution: NOT ready and not performed.** Requires implemented/reviewed algorithms, ordinary-backend deterministic tests, fixed reviewed config/schedule/plan digest, pinned source/environment, independent-verifier checks, successful separate nonformal smoke, evidence schema/reconciliation and runtime feasibility. This audit is not an implementation test suite or formal-run authorization.

Evidence acceptance: every planned attempt exactly once, no hidden retries/dropped failures, outcome/verifier/timing denominators reconciled, preserved protected sources/history, complete hashed artifacts. Research success separately asks whether nominal FRR meets 0.5% with suitable uncertainty. Complete unfavorable evidence is still valid. Changing conditions after unfavorable formal observations requires a new preregistered follow-up, not retroactive repair.

## 18. Recommended implementation sequence

1. Review/freeze this plan and group identities; preserve historical evidence and existing user modifications.
2. In a future task add isolated voting/B1 adapter with independent deterministic fixtures; no production reconstruction/authentication changes.
3. Add thin harness/config/schema, matched schedule and in-memory verifier provisioning. Test accounting before PUF measurement.
4. When implementation/testing is authorized, run appropriate tests and distinct nonformal smoke; resolve defects and freeze provenance before formal execution.
5. In a separate authorized task run the fixed 48,000-attempt comparison, preserving ordinary failures and partial evidence. Do not rerun the historical 84,000 attempts.
6. Reconcile/seal fresh results and report all groups' reliability, uncertainty, measured local simulation latency and entropy tradeoffs, including failures to meet the target. Adoption into Authentication-v2 remains outside scope.

**NO ALTERNATIVES WERE IMPLEMENTED. NO RECONSTRUCTION EXPERIMENT WAS RUN. NO EXISTING PROTOCOL CODE WAS CHANGED. NO FILES WERE STAGED OR COMMITTED. NOTHING WAS PUSHED.** Only this design document was created; deterministic installed-library checks were performed.
