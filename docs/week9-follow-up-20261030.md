# Week 9 follow-up on October 30

## Returned detector-table replay

Will's commit `596f0922123e1564a8ff18c10037a183c580e00e` includes a local Windows,
CPython 3.12.4 AMD64 run. His environment record identifies Will Wallace as the
executor. Both CSV hashes match the frozen reference and archived outputs:

| Output | SHA-256 |
|---|---|
| detector-family-table.csv | 5126dacb246139d58bdb87ecb5925495aa73f7e90067037cfbf8bef36b74cdaf |
| per-fit-counts.csv | 8b1c7409bc2a4f2fd6e11fea5cdecb469d8472e67a67fa1eb27d42a1a6c9deb2 |

The detailed reviewer form remains blank. The script's operator-verification
field stays false by design; file checks do not attest a person's identity.
The newer local receipt supersedes the older hosted Linux/Python 3.13.5 archive
as the latest reported execution environment. Slide 10 can use the local 3.12.4
description; review documentation should still be identified as unfinished.
No model training, inference, threshold selection or bootstrap was repeated.

## Checkout-byte correction

The newly added nested replay files lacked the exact-byte checkout rule already
used for the original inputs. Windows converted them to CRLF. All 17 package
files matched their expected hashes after accounting solely for that conversion;
both original archived CSVs matched the receipt. The working files were restored
from unchanged Git blobs and a scoped `-text` rule was added. The manifests,
expected hashes, original scientific inputs and retained ZIP were not rewritten.
The eight original inputs still match the returned receipt.

Fresh checkout checks with automatic line-ending conversion both enabled and
disabled are recorded in the [integrity receipt](../results/week-9/keegan/replay-checkout-review-20261030-001/verification.json).
This is file-integrity/packaging evidence, not a new reproduction execution.

## Quest and presentation status

The next development check uses Unity Play Mode through Quest Link. The existing
Android compile receipt remains valid for that recorded APK. Link connection,
desktop XR/runtime configuration, live tracking and controls have not yet been
validated. PC-hosted measurements must be labeled as such. Confirm the final
study headset model and acquisition path before institutional submission.
CITI and connected-headset work are planned for next week. The Word packet
remains version 1.3 for PI review; storage, study-team roles and other decisions
are still open. Presentation wording and speaker notes describe these limits.

The October 29 research-log entry records the meeting, lab advice and slide
preparation. No new hours were inferred or added for this follow-up.
