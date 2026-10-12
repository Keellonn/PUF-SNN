# Week 7: receipt of the shareable Week 6 handoff

The received ZIP supplies four missing original-execution compatibility documents and compact original-evidence subsets for Will's Tier-1 v2 and reconstruction-alternatives experiments. Included bytes match the supplied inventories and manifests; the original manifest identities also match the current reports at `0fb5168427475af55b562eef0e1d747fa550c03e`. This is receipt and integrity evidence, not independent recomputation of the raw experiments or a complete shared release.

## Restored documents

- `docs/week6-tier1-v2-experiment-plan.md`
- `docs/week6-reconstruction-alternatives-experiment-plan.md`
- `docs/week6-reconstruction-alternatives-implementation-validation.md`
- `docs/week6-reconstruction-alternatives-formal-readiness.md`

These are unchanged historical compatibility inputs, not newly approved plans or the current results authority. Their original dated/readiness statements describe the original checkpoints. The current narrative authorities remain `docs/week6-tier1-v2-experiment.md`, `docs/week6-reconstruction-alternatives-experiment.md`, and the actual `docs/authentication-v2-protocol-spec.md`.

The narrowly scoped `docs/.gitattributes` additions prevent line-ending conversion for these four documents. The received reconstruction documents contain mixed LF/CRLF bytes, and the Tier-1 plan contains three original Markdown hard-break lines. Per-file whitespace handling preserves those original line-end details; the complete SHA-256 checks remain mandatory. Existing documentation rules and all other documents are unchanged. See [Git's text and whitespace attributes](https://git-scm.com/docs/gitattributes).

## What was verified

- The received ZIP is 2,205,234 bytes, SHA-256 `e2abfb56756ba8c275e05d73840aef92ce432f0e2d03e7af323cdbe74302d9c1`.
- Archive paths, entry types, duplicate names, bounded sizes, encryption flags and CRC reads were checked without executing received code.
- Both nested subset ZIPs match their supplied size/hash records and their corresponding expanded copies in the outer archive byte-for-byte.
- All 27 inventoried Tier-1 originals and 45 inventoried reconstruction originals match their supplied sizes and SHA-256 values.
- Each original `COMPLETE` points to the included original manifest hash. All included primary-manifest entries match; absent entries remain explicitly excluded, not waived.
- The Tier-1 exact-byte source ZIP matches its saved hash; all 188 archived files match the source-byte inventory, including all 185 primary execution-source entries.
- All 31 reconstruction source-snapshot files match their saved source manifest; its hash matches the original completion marker.
- All four restored documents retain their received bytes and recorded hashes.

## What remains incomplete

The Tier-1 primary manifest references 12 omitted files, including raw attempts, traffic, audits, recovery records, timing traces and the full trial plan. The reconstruction primary manifest references six omitted files, including raw attempts, enrollment/helper truth, detailed device results and the trial plan. Both package notices explicitly say full-manifest verification is unsupported by the compact subset.

Full primary and supplemental manifest closure, independent raw-outcome reconciliation, original Git-history recovery and a fresh experiment reproduction are not established by this receipt. Saved independent-analysis certificates in Will's package are received evidence, not a newly executed independent analysis by Keegan. No new reconstruction reliability, conventional-credential control, integrated majority-3, latency or security result is claimed.

The original ZIP and compact evidence remain outside Git. No partial bundle is installed under the authoritative original formal-run paths, and no original `COMPLETE` is copied into a location that could be mistaken for a closed run. This checkpoint publishes only the four documents, the scoped Git rules, this explanation and `receipt.json`.

The unchanged historical Tier-1 plan retains its original faculty-feedback file-path citation. That citation is preserved source provenance, not a newly exported local file or a promise that all historical documentation was redacted. The new receipt contains no absolute local paths; raw traffic, audit, session and enrollment material is not published.

Supplementary test modules have not yet been run after document restoration. The earlier 964-case clean test result remains explicitly root-discovery scope. The shared release remains incomplete. Models, dataset payloads, protocol defaults, historical experiment artifacts, working environments, private Windows traces, slides and research-log hours are not modified by the import.
