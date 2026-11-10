# Accepted source replay and interrupted exports

November 10, 2026. The PI supports retaining accepted source records needed for
reproducibility, subject to the final data-management plan. The implemented
export remains an optional development feature, off by default. No research
recording mode or institutional approval is created by these software checks.

## What source means here

The source record retains samples from `HeadPoseCapture`'s queue before
`QuestWindowProcessor` resampling. It is not an untouched headset API dump:
the capture callback currently normalizes readable quaternions and substitutes
unavailable values while retaining validity/availability flags. That behavior
is unchanged. Reproduction starts at this declared queue boundary.

| Linked record | Content and role |
|---|---|
| Accepted pre-resampling source | Ordered capture timestamps, captured float32 position/quaternion bit patterns, tracking validity/state and availability flags |
| Processed window | 120 samples on the 60 Hz grid, after the existing window processing |
| Source quality and ledger | Pose-free counts/rates/gaps, planned/attempted/outcome events, reasons, trial codes and file links |
| Features and transformed copies | Downstream derivatives with a link to the accepted source and processing/configuration identity; not newly generated here |

All linked source/processed/derived motion records must use the same approved
access, withdrawal, retention and deletion rules. Keep source-copy grouping in
splits and resampling. The no-repeat trial policy and current quality thresholds
remain unchanged. Rejected and stopped trials intentionally retain no pose files.

## Exactness supported by the tests

The earlier twenty-seed test compared the complete serialized window and quality
summary. The new test also checks every retained source sample's seven float32
bit patterns, timestamp and tracking fields. After reload, it compares all 120
processed samples' position/quaternion float32 bit patterns, timestamps, indexes
and tracking flags. It compares every quality-metric field, including the exact
IEEE-754 bits of the double-valued observed rate. Metadata/full serialized
windows also match. No epsilon or numerical tolerance is used in these native
comparisons. The twenty seeds exercise JSON encoding/decoding in memory;
separate exported native fixtures cover disk writes and reload checks. The two
twenty-seed tests reuse the same seeds, not forty independent sources. These
are twenty synthetic seeds within this tested Unity runtime,
not universal equality across machines, Unity releases or hardware APIs.

The Python inspector has a different scope. It independently checks the format,
links, hashes, counts, timing/gap summaries and grid/tracking relationships. It
does not reimplement Unity quaternion interpolation or regenerate predictions.
The accepted-source check uses relative tolerance 1e-12 and absolute tolerance
0 for the observed rate. The separate source-quality arithmetic consistency
check uses relative tolerance 1e-9 and absolute tolerance 1e-6 Hz. Other required
counts/timestamps/flags compare exactly. Do not call all Python numerical
checks bit-exact.

## Partial writes and disposition

Several file writes are not one atomic transaction. A source export can fail
after an accepted ledger/window entry. Preserve that acceptance count, report
source availability separately and flag the incomplete bundle. A failed
processed-window/ledger write may instead leave an orphan window. Do not
silently adopt an orphan or relabel a storage failure as a quality rejection.

Proposed operational procedure for the matching protocol/data plan:

1. Stop and disarm the visit after a write failure. Do not append, resume,
   overwrite, salvage trial data or rerun a failed file under the same visit code.
2. Treat any partial source or processed-pose file as motion-bearing, even when
   the intended outcome was no retained motion. Restrict it on the local study
   computer immediately. Do not upload it to public Git, a broadly shared folder
   or a general diagnostic log. Actual restriction controls must be verified.
3. Keep a pose-free incident record: coded visit/trial, stage, reason, affected
   record types, file sizes/hashes and the staff action. Do not copy pose values
   into that record. Exclude partial files from analysis and flag linked records
   until the PI resolves source availability and eligibility.
4. Notify the PI. Proposed default: PI-authorized deletion of unintended partial
   motion and its temporary/derived copies, following the approved storage
   procedure, while retaining the coded incident and trial accounting. Any
   exception to retain motion needs explicit PI review under the approved plan.
5. Document the decision and disposition. If SharePoint received a copy, include
   versions, recycle bins and applicable backups in the reviewed removal process.
   Verify the actual deletion/backup limits before promising erasure. No software
   flag proves secure deletion. Final retention periods and restricted storage
   arrangements remain operational review items.

The read-only validators do not move, repair or delete files. This checkpoint
tests failure detection and exact replay; it does not verify restricted storage,
backup removal or a final approved incident-disposition procedure.
