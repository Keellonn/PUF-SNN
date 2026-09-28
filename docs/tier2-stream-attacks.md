# Tier 2 Stream Attacks

**Owner:** Keegan Hoyne

## Purpose and threat model

Week 5 evaluates corrupted synthetic sensor input entering a legitimate sender before tag creation. The attack code does not obtain session keys or override authentication decisions. A correctly formed, quality-valid changed window can pass authentication because its altered values are legitimately tagged. This does not demonstrate a failure of HMAC.

Will owns the keyless Tier-1 replay/substitution/post-tag attacks and PUF reconstruction. His confirmation of the existing Wire Protocol 2.0 boundary permits this experiment to reuse the final sender, verifier and accepted-window integration without changing them.

The existing SNN predicts five motion classes. The separate supervised anomaly detector will begin with logistic regression and random forest. A separate SNN anomaly model is not required for the first anomaly experiment.

## Source and splits

The frozen corrected source contains 1,800 windows: 600 each in train, validation and test. Its SHA-256 is `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`. Session 1 trains models, Session 2 selects detector settings/thresholds, and Session 3 evaluates frozen decisions. The same synthetic device profiles appear in all splits.

Every case keeps the original source-trial, session, split and intended motion label. Only its derived window identifier changes. Clean and attacked copies are paired observations, not additional independent trials. The clean-dataset validator is used on the clean source; its clean-only naming/count/sequence rules must not be applied unchanged to the derived case sweep.

Attack metadata is stored in a separate compact plan, never added as extra fields to a Quest sensor record. Labels, split assignment, attack name, severity, random seed and construction outcomes remain outside model inputs and authenticated sensor fields.

## Configured changes

| Change | Low / medium / high nominal values | Meaning |
|---|---|---|
| Position noise | 0.005 / 0.01 / 0.02 m | Independent Gaussian noise per position axis; values specify per-axis SD, not 3D RMS |
| Orientation noise | 0.5 / 1 / 2 degrees | Gaussian signed rotation angle about independently sampled isotropic axes; not additive quaternion-component noise |
| Position drift | 0.02 / 0.05 / 0.10 m | Linear ramp along a sampled direction, reaching this offset at the last sample |
| Orientation drift | 2 / 5 / 10 degrees | Linear rotation-angle ramp about a sampled axis |
| Timestamp jitter | +/-4 / +/-8 / +/-16 ms | Perturbed interior source timestamps followed by reconstruction onto the original grid |
| Dropped samples | 5 / 10 / 20 percent | Random interior source samples removed before reconstruction |
| Frozen pose | 100 / 250 / 500 ms | Contiguous samples repeat the preceding position and orientation; timestamps continue normally |
| Position jump | 0.05 / 0.10 / 0.20 m | Persistent position step at a randomly selected interior onset |
| Orientation jump | 5 / 10 / 20 degrees | Persistent orientation step at a randomly selected interior onset |

Each nominal value is multiplied by an independent seeded draw in [0.8, 1.2]. The severity name refers to the nominal group; actual magnitudes are also recorded. Freeze/drop settings are rounded to whole samples and the realized duration/drop fraction is reported. Rotation axes and jump/freeze onsets vary independently of motion labels. These settings are provisional engineering assumptions, not calibrated human or headset attack distributions.

The attack seed is 5007, separate from data-generation and model/training seeds. SHA-256 derives distinct parameter and transform PCG64 seeds from the configuration version, master attack seed, source window identifier, attack type and severity. Magnitude selection and transformation use separate streams. Reordering sources or changing model seeds does not change their attacks. NumPy version and RNG identity are recorded in the manifest.

## Construction and quality boundaries

Pose transformations preserve 120 samples and timestamps. Rotations are composed as xyzw quaternions, normalized and made sign-continuous. Clean and transformed conditions use the same finite canonical binary32 conversion. Tracking flags are not changed to make an attack pass.

Jitter/drop experiments treat the existing synthetic fixed-grid poses as source samples. They use linear interpolation for position and quaternion SLERP for orientation to produce the original 120-point output grid. Source endpoints are anchored/retained to avoid confusing interior disturbance with missing capture coverage. These cases are not a measurement of real irregular Quest capture, endpoint dropout or changed hardware clock rate.

No interpolation crosses a source gap above 50 ms. Non-increasing timestamps, excessive gaps or incomplete coverage produce `construction_failure`, with no output record and no authentication attempt. The legacy 16,666,667 ns grid means a three-interval gap is 50,000,001 ns and is rejected by the unchanged strict 50 ms rule. Random drop runs may therefore fail construction even at low severity; preserve these results rather than retrying until a case passes.

The constructed window then passes the current adapter/binary quality checks: exactly 120 samples, nominal two-second duration within its existing tolerance, increasing in-bounds timestamps, no adjacent gap above 50 ms, at least 114 valid tracking flags with matching quality counts, finite binary32 values and valid quaternions.

Outcomes are kept separate:

- `construction_failure`: no processed window was produced.
- `quality_failure`: a transformed processed window failed final canonical construction/quality checks.
- `quality_valid`: a constructed window is eligible for legitimate sender sealing; authentication has not yet executed.

The normal sender refuses to tag invalid-quality input. Valid-tag verifier quality-rejection tests need a separate controlled authentication test harness; this stream generator does not bypass the sender or access its key.

## Classification and anomaly interpretation

Motion classification is evaluated against the intended clean-source task, using frozen LR/RF/SNN choices. Severe corruption may erase or change that task, so classifier errors do not necessarily indicate that the corrupted observed motion has an unambiguous class.

Anomaly supervision means a documented transform was applied before authentication. It does not prove malicious behavior. Report results by transform/severity, including construction failures, detector misses and false positives. Low-level changes overlap clean noise/drift, and freezes can resemble legitimate still motion. Targets are not guaranteed outcomes.

Timestamp jitter is reconstructed onto a fixed grid; downstream models cannot observe the original timing offsets directly. A detector may only use effects retained in the authenticated motion. Source drop indexes, jitter offsets and resampling-failure metadata must not be secretly supplied as detector features. Any future raw-timing feature extension needs an explicit documented sensor/interface design.

Constant pose bias is not included in this initial nine-transform sweep. A constant position offset is removed by first-pose-relative preprocessing; a constant starting rotation can also be invariant. These are useful later negative/invariance controls, not transformations that should be claimed detectable from the current relative-pose input.

## Shared accepted-window behavior

Authenticated evaluation will use one composite consumer after the existing accepted-event boundary. Both motion classification and anomaly detection consume the same immutable authenticated sensor data. Rejected authentication events invoke neither model. Delivery remains at most once, not a guarantee that a caller invokes it successfully.

An anomaly flag is downstream inference metadata. It does not change an accepted authentication decision, roll back sequence state or permit another delivery. If the consumer fails, its event remains consumed and the verifier's existing incomplete-evidence behavior applies. Authentication audit records are not rewritten to become anomaly decisions.

## Saved evidence and remaining evaluation

The generator saves a compact plan, configuration, source/config hashes, environment, example construction outcomes, summary, manifest and completion marker. Full transformed records are regenerated from the frozen source and case seeds during evaluation rather than duplicating the dataset dozens of times.

There are 28 planned cases per source: one clean control and nine attacks at three severities. This gives 50,400 planned cases, including 48,600 transformed cases, or 16,800 planned cases per split. These are planned cases, not guaranteed constructed/accepted windows or independent recordings.

The initial example sweep is a smoke check only. It does not establish complete attack acceptance rates, classifier vulnerability, anomaly precision/recall/F1/FPR, or timing with the detector. `COMPLETE` marks successful plan generation, not completion of Week 5.

Next, evaluate frozen motion classifiers, train/validate the separate anomaly models with explicit source-grouped sampling/weighting, and compare matched unauthenticated/authenticated paths. Keep the same source identities and attack instances across conditions, fit normalization from training only, select thresholds from validation only, and report source-level uncertainty rather than treating transformed copies as independent observations.

No physical Quest behavior, cross-person generalization, improved PUF reconstruction, independent pre-HKDF credential verification, formal Tier-1 rejection rate, durable audit timing or full-system availability is established by this work. Human recording remains disabled pending approval.
