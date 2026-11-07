# Calibration Evidence Provenance Exception Record

**Status:** Pending Faculty Provenance Review  
**Date:** November 6, 2026  
**Research owner:** Will Wallace  
**Review requested from:** Dr. Garcia

This record discloses an unresolved historical source-byte discrepancy in the completed Week 9 shared-noise calibration. It is not an authorization, acknowledgment, replacement certification, or amendment of historical evidence. No faculty disposition is recorded here.

## Experiment and evidence identification

| Field | Recorded identity |
|---|---|
| Experiment | `week9-shared-noise-calibration-v1` |
| Completed run | `week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318` |
| Original source revision | `6fd13d143fa5c57692851d24d65b62ec3732f98c` |
| Completion timestamp | `2026-10-29T01:17:43.405641+00:00` (UTC) |
| Recovery result | **NOT RECOVERED** |

Repository-relative evidence roots:

- **B:** [completed calibration bundle](../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/).
- **R:** [restart verification and analysis records](../../results/week-9/will/calibration-restart-v1/restart-20261028-01/).

The historical [bundle manifest][manifest] contains 126 entries; the [source manifest][source-manifest] contains 116 source entries. The [completion marker][marker] records PASS and two finalization validation passes. Relevant historical receipts are [B/validation.json][validation], [R/checkout-verification.json][checkout], [R/standalone-audit.json][standalone], and [R/final-verification.json][final]. These establish recorded completion and validation claims at that time, subject to the present integrity qualification below.

## Observed integrity discrepancy

Affected file: [B/source/src/python/puf_snn/pipeline_timing.py][affected]. Both historical manifests record the same expected digest.

| SHA-256 basis | Digest |
|---|---|
| Recorded historical bytes | `1b9ddc6926877babca9a4bc7453b2ac71ff774f230656127416654ad2f052ba2` |
| Current raw bytes of the affected snapshot | `e204b6c5fb2607714aaf713a224ece5230d17737450e4b096c6472f66b446228` |
| Current snapshot after in-memory CRLF-to-LF conversion | `1f0e23de9a17c9e44ee643c70417aa2452f218c016f2eb234ba78ddcc19e80d9` |

The raw and normalized values were reconfirmed by read-only hashing while preparing this record. No normalized bytes were written to disk.

The completed [calibration analysis](shared-noise-calibration-analysis.md#evidence-and-reproducibility) and [outcome reconciliation](calibration-outcome-reconciliation.md) report these prior audit results:

| Manifest population | Exact raw-byte matches | Matches only after in-memory CRLF-to-LF conversion | Unresolved |
|---|---:|---:|---:|
| Bundle: 126 entries | 76 | 49 | 1 |
| Source: 116 entries | 76 | 39 | 1 |

The unresolved entry in both populations is `pipeline_timing.py`. Uniform LF/CRLF transformations did not recover its recorded digest. The manifest and completion marker also reproduce their historical hashes only after in-memory newline conversion. These observations do not constitute a passing present exact-byte audit.

## Recovery investigation and boundaries

The prior audit examined the current checkout, available historical Git versions, and available frozen source snapshots without recovering the target digest. Its documented revision comparison includes `6fd13d143fa5c57692851d24d65b62ec3732f98c`: the affected snapshot's LF-normalized content agrees with the corresponding Git blob. The cited reports do not enumerate every historical commit/blob examined; this record therefore makes no exhaustive Git-coverage claim.

Existing snapshots covered by the prior recovery scope include the completed bundle above and these earlier copies, each under its run's `source/src/python/puf_snn/pipeline_timing.py`:

- [Week 7 nonformal run, October 14][snapshot-w7].
- [Week 8 nonformal run, October 20][snapshot-w8].
- [Week 8 resource-first run, October 21][snapshot-first].
- [Week 8 resource-cache comparison run, October 21][snapshot-cache].
- [Earlier interrupted Week 9 calibration run][snapshot-interrupted].

The earlier run identities predate the completed restart, but no examined snapshot recovered the original bytes. Earlier identity alone does not establish an independent byte-preserving chain of custody. The prior Git, snapshot, and newline searches were not repeated during the final bounded workstation investigation.

That investigation found:

- `C:\PUF+SNN_SharedRepo\PUF-SNN`, the original execution/source location named in the run records, and its parent were absent. The historical run directory beneath that root was consequently unavailable.
- `C:\PUF+SNN` existed but was empty.
- Bounded directory-name checks of conventional Desktop, Documents, Downloads, OneDrive, repository, project, archive, and backup locations revealed no additional candidate project copy. Direct checks of `C:\Users\wwall\Backup`, `Backups`, `Archives`, and `Projects` found those locations absent.

The following project-related ZIP packages were inspected without extraction. Every file member was hashed from its unmodified decompressed bytes, checking for the target digest even under another filename.

| Archive location | File members hashed |
|---|---:|
| `C:\Users\wwall\Downloads\Will_Detector_Table_Reproduction_2026-10-28.zip` | 18 |
| `C:\Users\wwall\Downloads\Will_Detector_Table_Reproduction_RESULTS_2026-10-28 (3).zip` | 6 |
| [results/week-9/will/keegan-detector-table-reproduction/output/Will_Detector_Reproduction_Completed.zip](../../results/week-9/will/keegan-detector-table-reproduction/output/Will_Detector_Reproduction_Completed.zip) | 6 |
| [results/week-8/keegan/handoff-20261022-002/validation-receipts.zip](../../results/week-8/keegan/handoff-20261022-002/validation-receipts.zip) | 15 |
| [results/week-8/keegan/handoff-20261022-002/code-overlay.zip](../../results/week-8/keegan/handoff-20261022-002/code-overlay.zip) | 9 |

None of the 54 members had the target digest; none of these packages contained a `pipeline_timing.py` entry or independently preserved the requested source. Some member timestamps precede completion, but ZIP timestamps lack timezone information and do not authenticate preservation history. No new plausible original file was found.

Profile-root enumeration at `C:\Users\wwall` was denied. No unrestricted filesystem scan, access escalation, or inspection of unrelated file contents was undertaken. Other users' data, unrelated archives, offline media, cloud backup contents, and system backup stores were outside scope. A negative result within these boundaries does not prove that no original copy exists elsewhere. The workstation recovery findings were returned in Codex chat; this record captures those findings without claiming a separate persisted machine-audit receipt.

## Scientific interpretation and workflow status

Numerical calibration reconciliation remains supported by saved records: 3,840 attempts comprise 3,369 correct reconstructions, 458 decoder failures, nine invalid-format/padding outcomes, and four valid-format incorrect credentials. The saved downstream records show those four incorrect credentials rejected before session establishment. The [outcome reconciliation](calibration-outcome-reconciliation.md) and [postcompletion analysis receipt][post] support numerical agreement separately from byte provenance; the receipt records agreement with the sealed analysis and zero new scientific samples.

Historical PASS receipts do not establish present exact-byte certification. The cause of the unresolved discrepancy is **unknown**, and **original byte identity remains unrecovered**. The available evidence does not establish source tampering, scientific invalidity, or a line-ending cause for this file's mismatch.

The saved [computational selection][selection] supports **sigma = 0.15**. Formal acknowledgment-v1 has not been completed; the postcompletion receipt records acknowledgment pending and `eligible_for_final_planning=false`. The [acknowledgment workflow][workflow] invokes the [evidence audit][audit], which requires exact artifact and source hashes. Existing discrepancies prevent successful acknowledgment through that workflow against this checkout. This disclosure does not bypass those checks.

Final correlated-noise execution is **not authorized or enabled**. The saved receipt records `final_evaluation_enabled=false`; the calibration's historical execution authority is not authority for a new final experiment.

## Decision requested

Present this exception to **Dr. Garcia** for provenance review and a documented determination of whether further original-byte recovery, a formal exception disposition, or a separately authorized new experiment is required. No outcome is presumed, and this record does not itself transmit the request or record acceptance.

Faculty acceptance of the disclosure would not automatically alter the existing validator, certify the current checkout, complete acknowledgment-v1, or authorize execution. Any subsequent technical or research action requires its own explicit scope and applicable validation and authorization requirements.

Only this new documentation file was created. Historical evidence, frozen sources, manifests, hashes, existing documentation, acknowledgments, execution authorizations, and Git history were not modified. No experiments or fresh authentication data were generated.

[manifest]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/manifest.json
[source-manifest]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source-manifest.json
[marker]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/CALIBRATION_VALIDATED.json
[validation]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/validation.json
[checkout]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/checkout-verification.json
[standalone]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/standalone-audit.json
[final]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/final-verification.json
[affected]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/src/python/puf_snn/pipeline_timing.py
[snapshot-w7]: ../../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/source/src/python/puf_snn/pipeline_timing.py
[snapshot-w8]: ../../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/source/src/python/puf_snn/pipeline_timing.py
[snapshot-first]: ../../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-resource-v1-first-20261021-01-p1-cold/source/src/python/puf_snn/pipeline_timing.py
[snapshot-cache]: ../../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-resource-v1-cachecmp-20261021-01-p1-cold/source/src/python/puf_snn/pipeline_timing.py
[snapshot-interrupted]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t003215z-d55070ef/source/src/python/puf_snn/pipeline_timing.py
[post]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/postcompletion-analysis-receipt.json
[selection]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/selection.json
[workflow]: ../../src/python/puf_snn/experiments/shared_noise_calibration_provenance_v2.py
[audit]: ../../src/python/puf_snn/experiments/shared_noise_calibration_evidence_v1.py
