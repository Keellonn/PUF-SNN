# Week 7: current release evidence and scope

**Reporting base:** `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`, October 12, 2026. **Shared release complete:** no.

This is the current status authority for the received/setup/test evidence. The earlier [release-readiness checkpoint](../week7-release-readiness.md), historical result manifests and original compatibility documents remain unchanged. Their dated missing-input and test-count statements describe their original checkpoints, not today's inventory. The separate [reporting index](../../results/week-7/keegan/reporting-index.json) pins this pass and its references without altering an upstream manifest.

## Source and publication boundaries

| Work | Tested / scientific source | Published checkpoint |
| --- | --- | --- |
| Offline project setup and original 964-test scope | `c62ff15` | `f0fbfb1` |
| Exact historical document restoration and partial receipt | Sources supplied by Will; report review `0fb5168` | `3bb91b2` |
| 1,035 selected tests | `3bb91b2`, using the earlier verified dependency environment | `e7c04a1` |
| Unchanged 27-test diagnostic | Git context `3bb91b2`; exact reconstruction snapshot `dc75fbc339ff107e0286cc892c5b672125f594425c0ba2fcba2f6b98928c293d` | `0895f92` |

A publication commit is not automatically the execution source. Check each historical cross-folder manifest at its retained publication boundary, not as a claim that all referenced working-tree paths must stay unchanged forever. Selected metadata/result bundles have their own scopes; a completed export marker is not a complete shared-release or all-tests-passed assertion.

## Local evidence now available

- **Observed installation profile:** 36 exact external wheel identities/byte hashes and static closure; a new offline environment with 37 distributions including the project, 57 raw source/build inputs and 55 installed project files checked. Use [the separate hashed profile](../../requirements/week7/win-amd64-cp313-observed-hashed.txt); historical requirements and existing environments are unchanged. This does not certify another platform, historical training payloads or bit-identical future wheel containers.
- **Selected implementation validation:** [1,035 tests in 58 modules passed](../../results/week-7/keegan/expanded-test-validation/README.md), zero failures/errors/skips. Explicit supplementary discovery preserved original tests and did not add package markers or inflate root-discovery counts.
- **Additional interpreter diagnostic:** [27 tests executed, 24 passed, two failed, one errored](../../results/week-7/keegan/reconstruction-compatibility/README.md). The final tracebacks identify the unchanged historical 3.12.4 guard. No version-policy edit or full formal run occurred; operations behind that guard are not thereby validated on 3.13.14.
- **Original inputs received:** four byte-preserved historical compatibility documents, exact execution-source material and compact formal-evidence subsets. The privately received original 18-file, 80-attempt smoke fixture also verified, but is not published.

The historical Matplotlib 3.10.6 requirement differs from the observed/tested 3.11.2 profile. The project metadata permits 3.12/3.13, but the original formal runner separately pins 3.12.4. Neither difference is silently erased from provenance. Legacy Tier-1-v1 is kept separate from the 25 current-v2 Tier-1 tests included in the selected passing scope.

## Compact handoff versus full formal-run closure

| Shared run | Included primary entries verified | Primary entries omitted | Interpretation |
| --- | ---:| ---:| --- |
| Current-v2 Tier-1 | 12 | 12 | Original manifest/completion identities and execution-source bytes checked; full raw closure not established here |
| Reconstruction alternatives | 43 | 6 | Original manifest/completion identities and all 31 source-snapshot files checked; full raw closure not established here |

The [receipt](../../results/week-7/keegan/shared-handoff-receipt/README.md) lists the omissions. Tier-1 omissions include raw attempts, traffic, audits, recovery and full plans; reconstruction omissions include raw attempts, enrollment/helper truth and device-level detail. The manifests themselves were received, so they are no longer described as wholly unavailable. The authoritative original formal-run directories have not been installed as complete runs in this checkout. Received upstream independent-analysis certificates are not a newly executed independent raw analysis by Keegan.

A scoped, approved access/transfer decision is still required for omitted evidence. Do not force-add private folders or substitute regenerated runs. A matching artifact hash establishes identity/integrity, not safe arbitrary model deserialization, physical attestation or protocol-security completeness.

## Reproduction boundary and privacy

Current experimental runners use source-checkout resources. The tested installation plus source-workflow tests does not establish a standalone installed-wheel application. Generated motion data and 11 frozen model binaries are not supplied by a clone; obtain trusted originals and verify the [Week 6 frozen-input index](../week6-release-evidence.md) before loading. Do not retrain or regenerate to satisfy historical hashes.

Only public dependency pins, numeric/test inventories, repository-relative references and scoped provenance are committed. Absolute workstation paths, usernames, private fixture truth, raw logs, Windows captures, environments, checkouts and local orchestration scripts are excluded. Historical omissions, negative results and earlier attempts remain retained rather than rewritten. This documentation pass performs no test, installation, model loading, inference, training, authentication, latency measurement or private trace scan.

## Decisions still open

1. Complete or explicitly scope shared original-evidence access and semantic reconciliation; retain separate source/manifest identities for each experiment.
2. Review majority-3 integration, shared-noise reliability, the provisioned-credential control and key/availability assumptions; none is newly solved by setup/test counts.
3. Decide whether future formal-readiness support is separately versioned for 3.13 or stays at the unchanged historical interpreter. The partial diagnostic is preserved either way.
4. Faculty/lab must specify a headset custodian/access date, institutional human-data determination and permitted fields/storage/access/retention/transfer rules before recording. Initial access should validate the logger, not silently begin a population study.

Current status, conclusions and ownership: [study status](study-status.md). Research-log and slide work remain deferred.
