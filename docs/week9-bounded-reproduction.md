# One bounded detector table reproduction

This bounded check recomputes the central detector table from retained scores
and frozen validation thresholds. Will returned a local Windows/Python 3.12.4
run on October 29. Both CSVs match the reference hashes. The detailed reviewer
form remains blank; the environment record and companion report identify Will
as the operator. This scope does not rerun inference, data generation,
authentication or the bootstrap intervals.

The [returned evidence](../results/week-9/will/keegan-detector-table-reproduction/README.md)
and [October 30 integrity follow-up](week9-follow-up-20261030.md) document the
local run and checkout line-ending correction. The frozen inputs, manifests and
recorded hashes are unchanged.

The frozen scoped handoff is commit `55dea11b1e3dbae22f7607f85ba2e4741ae37036`
for the eight historical inputs, plus the script overlay and exact hashes in
[the handoff manifest](../results/week-9/keegan/detector-table-handoff-20261027-001/manifest.json).
The script is new work over that base; it is not claimed to exist in 55dea11.
After the session commit, record its full hash in the reviewer's notes as well.
No branch reset or large package installation is needed if the eight inputs match.
For an easier transfer before the next commit, the separately prepared
`Detector_Table_Reproduction_2026-10-27.zip` contains just those exact inputs,
the script, expected CSVs, manifest and blank reviewer record. Extract it into a
new folder and run the same command there. This is a frozen scoped archive with
hash-identified files, not a claim that the new script is in the base commit.

The inputs total 16,290,840 bytes, about 16 MB. They are already tracked score,
threshold, construction, configuration, manifest and reference-table files. Model
binaries, Torch, NumPy and scikit-learn are not required for this scoped check.
The script uses only Python's standard library. The local dry run used CPython
3.13.14 x64 with site packages disabled; the recipient's Python/ARM environment
is not claimed verified in advance. Use Python 3.12 or newer and record it.

From the repository root, with a new output directory:

```powershell
python -I -S tools/reproduce_saved_detector_table.py --output results/week-9/keegan/independent-detector-replay-001
```

If the tool is supplied outside the repo, pass `--root ABSOLUTE_REPO_PATH`.
The command refuses an existing output folder or changed inputs. It writes two
CSVs and a receipt. Compare the CSV hashes with the handoff manifest and expected
copies; retain the receipt and complete reviewer-notes.md. The receipt deliberately
does not certify the identity/independence of its operator.

The check verifies retained per-case flags against `score >= validation cutoff`,
six fixed fits, source/trial ownership within these retained predictions, planned
versus accepted cases, all 28 conditions including one with zero eligible cases,
per-fit counts and both family point estimates. It does not re-audit how the
original train/validation/test files were created.

Expected values: logistic recall 82.8477%, clean false alerts 5.3333%; forest
recall 87.9531%, false alerts 2.9444%. These are means across three fixed fits on
600 source windows, 9,095 eligible medium/high copies and 600 clean controls per
fit. Of 16,800 planned test cases, 1,844 were blocked before tagging and 14,956
reached the retained prediction table. Blocked cases are not detector misses.

Send back the two CSVs, receipt and completed notes, including failures or extra
steps. This meets only the bounded metric-table scope; a successful independent
run would not close full pipeline reproduction or the historical archive gap.
