# Project documentation

Start here for the current work, then use the topic and weekly links below.
Filenames keep the existing naming style. Older reports remain at their recorded
paths because experiment receipts, scripts and research logs refer to them.

## Current work

- [Week 10 overview](week10/README.md)
- [Study decisions and remaining work](week10/week10-study-status.md)
- [Source recording, replay and the two work groups](week10/week10-source-recording-plan.md)
- [Latest technical checkpoint](../results/week-10/keegan/source-integration-20261103-001/README.md)

## Project and study design

- [Project specification](project-specification.md)
- [XR, data and model design](xr-snn-design.md)
- [Literature review](literature-review.md)
- [Original faculty decision memo](faculty-decision-memo.md)
- [Trial ledger, source summaries and denominator definitions](quest-trial-ledger.md)
- [Quest bench setup and remaining device checks](week9-quest-bench.md)

## PUF, reconstruction and authentication

- [Layer 1: simulated PUF](puf-layer1-design.md)
- [Layer 2: reconstruction](puf-layer2-design.md)
- [Layer 3: authentication](puf-layer3-design.md)
- [Independent credential verifier](credential-verifier-setup.md)
- [Authentication-v2 protocol and trust boundary](authentication-v2-protocol-spec.md)
- [Authenticated-window interface](authenticated-window-interface.md)
- [Tier 1 attack design](puf-tier1-attacks.md)
- [Tier 2 sensor perturbations](tier2-stream-attacks.md)

## Reports by week

Current follow-up: [Week 11 technical review and open acquisition checks](week11/README.md).

| Week | Documents |
|---|---|
| 2 | [Implementation and simulator design](week2/README.md) |
| 3 | [Reconstruction results](week3/README.md) |
| 4 | [Authenticated windows and attack evaluation](week4/README.md) |
| 5 | [Formal reconstruction and credential verification](week5/README.md) |
| 6 | [Integration, models, quality checks and timing](week6/README.md) |
| 7 | [Release evidence and correlated-noise validation](week7/README.md) |
| 8 | [Controlled comparisons and reproduction](week8/README.md) |
| 9 | [Logger accounting, calibration and bounded replay](week9/README.md) |
| 10 | [Current source-data proposal and study decisions](week10/README.md) |

## Writing, logs and retained material

- [Keegan's research log](research-logs/keegan.md)
- [Will's research log](research-logs/will.md)
- [Paper outline](paper-outline.md)
- [Earlier evaluation draft](paper-evaluation-draft.md)
- [Earlier preliminary results brief](preliminary-results-brief.md)
- [Consolidated Week 7 writing](week7/README.md)
- [Implementation plans](implementation-plans/)
- [Archived reports and snapshots](archive/)
- [Retained Layer 3 baseline manifest](layer3-baseline-v1-manifest.json)

## Adding future work

Put new weekly documents under `docs/week10/`, `docs/week11/`, and so on, keeping
filenames such as `week10-study-status.md`. Add the entry to that week's README.
Keep shared design documents at the top level. Results belong under the existing
`results/week-N/keegan/` or `results/week-N/will/` structure; small readme indexes can
link to them without copying experimental files.

Institutional Word drafts, participant records, certificates and signed forms stay
outside this public repository. A historical report remains a record of its own
checkpoint; use the current study-status page for later decisions.
