# Keegan's Week 8 results

Recorded October 22, 2026. These are current-source software checks with
synthetic inputs and saved models, not a new human-data or timing study.

## Main result

The original and faster exact quality checks produced matching model inputs,
predictions, anomaly scores, decisions, rejection reasons, call counts, and
final state in all **180 matched arithmetic comparisons**. A further **180
matched downstream comparisons** agreed across single-read and Majority-3
session setup. Rejected controls made **zero model calls**. The faster checks
remain optional; the shared default was not changed.

| Evidence | Recorded outcome | Where to look |
| --- | --- | --- |
| Bounded saved-model comparison | 360 admitted sessions; 1,080 accepted windows; 1,080 rejection controls | [Summary](quality-validation-20261022-001/summary.json), [manifest](quality-validation-20261022-001/manifest.json), [completion marker](quality-validation-20261022-001/COMPLETE) |
| Frozen-input checks | 30 validation sources; three saved-model combinations; 18 model/data artifact pins checked before and after | [Preflight](quality-validation-20261022-001/preflight.json), [source selection](quality-validation-20261022-001/source-selection.json), [input hashes](quality-validation-20261022-001/frozen-input-hashes.json) |
| Root-discovery regression | 1,085 tests selected, run, and passed; zero failures, errors, or skips | [Test receipt](regression-20261022-001/summary.json) |
| Reproduction packet | Nine code/config/test/documentation additions and sanitized result receipts, with hashes | [Handoff manifest](handoff-20261022-002/manifest.json) |

The [decision report](../../../docs/week8-keegan-validation.md) explains the
equivalence coverage, the existing configuration-specific timing results, model
tradeoffs, and remaining work. Use the
[reproduction guide](../../../docs/week8-keegan-reproduction.md) for commands
and the separately required frozen dataset/model files.

## What these results do not establish

- The 360 sessions used controlled, correctable response fixtures. They are
  not the larger independent/shared-noise reconstruction reliability study.
- This comparison did not remeasure latency or estimate new accuracy, recall,
  security strength, or performance on people or a physical headset.
- The 1,085-test count includes the 73 focused quality tests. Do not add the
  counts together. Ordinary root discovery excludes the non-package
  `experiments`, `tier1`, and `tools` test folders.
- Tests ran in the existing environment. A new clean installation and another
  person's reproduction must not be claimed until performed.
- The missing verified original timing archive remains a historical evidence
  gap. It does not prevent reporting these separately identified current-source
  checks, and its old hashes have not been rewritten.

## Evidence handling

The recorded base commit is
`c8a4053f8526b91dd856428fa0924d214f367106`. The run also records the exact current
code/config file hashes because the new work was not committed at execution
time. Later commits do not replace those recorded identities.

The handoff ZIPs preserve their original nine-file overlay; this result index
and the root README navigation were added afterward and are not represented
as part of that earlier overlay. Use the final session commit for the complete
checkout when it becomes available. Keep the earlier packet unchanged.

Raw `*.private.log` output is locally ignored. Commit the sanitized receipts,
not private logs, environments, caches, participant records, or model payloads.
No human data or IRB consent records are included here.
