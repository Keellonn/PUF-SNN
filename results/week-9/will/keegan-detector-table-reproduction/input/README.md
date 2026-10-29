# Detector table reproduction handoff

Upload this ZIP to your chat and ask it to follow START_HERE_PROMPT.txt.
Everything needed for the scoped table calculation is inside. It expands to
about 16 MB and needs only Python's standard library.

If running manually, extract into a new folder, open a terminal there, then run:

    python -I -S verify_package.py
    python -I -S tools/reproduce_saved_detector_table.py --output reproduction-output

The second command writes two CSVs and receipt.json. Record your actual
environment, exact commands, failures/deviations and comparisons in a copy of
handoff/reviewer-notes.md. Save it with environment.json and run-log.txt alongside
the outputs. Verify package hashes again, then return a ZIP of that output folder.

The expected tables are reference files, not results from your run. A new output
folder is required. Do not change the saved inputs, cutoffs, scripts or hashes.
No model binaries or package installation are required. The local tested Python
was 3.13.14 x64; record your own version, OS, architecture and execution location.

This checks the calculation from saved detector scores. It does not run models,
training, authentication, bootstrap intervals or a split-construction audit.
The reviewer supplies the human context for independence; the software receipt
does not verify who ran it. Published source: 3835ef55f9d6f5795521379ab5541c608fe5e6ac.
