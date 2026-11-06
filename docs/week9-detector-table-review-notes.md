# Reviewer reproduction record

**Reviewer name and role:**
William Wallace
**Date and time:**
October 29, 2026, 6:42:06pm - 6:43:34 PM
**Who actually ran and reviewed the commands:**
William Wallace
**AI assistance used:**
ChatGPT used to review commands and detector table output.
**Execution location (reviewer's laptop or hosted environment):**
Local windows machine, WILLPC, through VS Code integrated powershell
**Python version and implementation:**
Python 3.12.4
**Operating system/version and architecture:**
Microsoft Windows NT 10.0.26200.0
x64 (AMD64)
**Published source checkpoint:**
3835ef55f9d6f5795521379ab5541c608fe5e6ac
**Package-manifest SHA-256:**
bb7e83e52183c498c30bdda560fd35c8edab4055194087b82715cb384aa909f7
**Replay script SHA-256:**
27b7311989ab9628cd45c595f298291f62dc067949e62d9059c4d2e26d02f6c8

## Commands and setup

**Working Directory:**
C:\PUF+SNN_SharedRepo\PUF-SNN\results\week-9\will\keegan-detector-table-reproduction\input
**Exact commands:**

python -I -S verify_package.py
$LASTEXITCODE

python -I -S tools/reproduce_saved_detector_table.py --output ..\output\reproduction-output
$LASTEXITCODE

Import-Csv ..\output\reproduction-output\detector-family-table.csv | Format-Table -AutoSize

python -I -S verify_package.py
$LASTEXITCODE

**Prerequisites and extra steps:**
Windows Powershell 5.1, supplied frozen reproduction package
**Failed attempts and their exit status/reason:**
No failed attempts
**Deviations from the supplied instructions:**
No deviations

## Observed results

**Initial package integrity check:**
PASS — verification exited with status 0. The README reports 17/17 supplied files passing SHA-256 checks.
**Replay exit status:**
SUCCESS — exit code 0.
**Final package integrity check:**
PASS — verification exited with status 0.
**Input files remained unchanged:**
VERIFIED, as reported in the README and supported by successful initial and final verification.
**Both CSV hashes matched the reference values:**
MATCH, as reported in the README.

| Generated CSV             | Verified SHA-256                                                 |
| ------------------------- | ---------------------------------------------------------------- |
| detector-family-table.csv | 5126dacb246139d58bdb87ecb5925495aa73f7e90067037cfbf8bef36b74cdaf |
| per-fit-counts.csv        | 8b1c7409bc2a4f2fd6e11fea5cdecb469d8472e67a67fa1eb27d42a1a6c9deb2 |

**Per-fit counts matched:**

| Detector            | Medium/high recall | Clean false-alert rate | Matches reference |
| ------------------- | ------------------ | ---------------------- | ----------------- |
| Logistic regression | 82.848%            | 5.333%                 | Yes               |
| Random forest       | 87.953%            | 2.944%                 | Yes               |

**Generated receipt attached:**
output/reproduction-output/receipt.json — verified present in the saved ZIP
**Environment Record:**
output/reproduction-output/environment.json
**Run log attached:**
run-log.txt
**Outcome (matched, differed, or blocked) and explanation:**
MATCHED — successful saved-score metric reproduction.

## Interpretation and review

This independent reproduction verified the computation of detector evaluation metrics using retained prediction scores, frozen validation cutoffs, and three fixed fits per detector family.

It did not independently retrain the logistic-regression or random-forest models, regenerate predictions, reconstruct the original datasets, execute PUF authentication, perform SNN inference, or rerun bootstrap analysis.

The findings support the reproducibility of the supplied saved-score metric calculations within the scope of the preserved package. They do not establish independent reproducibility of the full model-development pipeline or provide a general security guarantee.

Independent reviewer attestation: William Wallace is not the implementer and completed the reproducibility detector table separate from Keegan's initial results.

This record is a human review and context statement, not a cryptographic identity verification or security proof. The generated receipt's operator-verification field must remain unchanged; do not set it to true on the basis of this document.
