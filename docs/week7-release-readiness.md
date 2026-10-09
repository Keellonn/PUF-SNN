# Week 7: scoped release and clean-environment checkpoint

## Conclusion and scope

The observed Windows x64 / CPython 3.13.14 dependency profile was installed offline into a new external environment, the local project was built and installed from verified source, and the existing 964-case root-discovery suite passed there with zero failures, errors or skips. This is reproducible setup and source-workflow test evidence for the stated profile. It is not a complete shared release, a standalone installed-wheel application validation, reproduction of the historical experiments, or proof of protocol security.

The examined source commit is `c62ff15812c9f7bbf3aff56be3f38ba0f225f6f1`. Its Week 6 experimental checkpoint is `2c84cf8394bd444188291e254bbf1ddde3cc8661`, identified in the existing revision evidence index. This Week 7 checkpoint adds documentation, dependency pins and scoped evidence only. It does not change default authentication/quality policy, trained models, thresholds, historical numerical results, slides or research-log hours.

The architecture conclusion remains: the evaluated software prototype enforces the tested authentication and inference-release policies, but its original complete motion-plus-anomaly paths do not meet the provisional 20 ms p95 target. The bounded opt-in quality-check comparison is a separate experiment; its limited improvement is not a new default-system or whole-pipeline claim. This environment check measures no new formal pipeline latency or reconstruction FRR.

## Checkpoint results

| Check | Observed result | Limit |
| --- | --- | --- |
| Local release identity/artifacts | 170 file-pin checks, 121 artifact entries and eight completed-bundle closures passed | Does not independently recompute experiment semantics or verify absent shared formal evidence |
| Existing environment declarations | Python/core/SNN constraints satisfied; equivalent project metadata records identified | The old requirements.txt Matplotlib pin does not match this observed environment |
| Public wheel preflight | 36/36 exact external pins had compatible advertised wheels | Availability alone was not installation evidence |
| Downloaded wheelhouse | 36 wheels; 263,894,803 bytes; byte hashes and static closure verified | Does not identify the original installed payloads or recover a historical training environment |
| Offline project setup | 57 raw Git source files, 55 built/installed package files, 37 distributions verified | Installation/build/metadata check, not standalone installed-wheel application execution |
| Clean source-workflow tests | 964 tests; zero failures, errors and skips; runner reported 119.144 s | Covers 54 test modules, not every repository test folder; duration is not a pipeline-latency measurement |

Original output timestamps describe tool execution, not attributable research work-hours. Selected terminal transcriptions are labeled as such. Original structured setup/test records are separately preserved; copied metadata is identified in the provenance record.

## Dependency and source identities

The two observed `puf-snn==0.1.0` declarations were equivalent metadata from the editable source tree and virtual environment, not two different model versions. The external profile contains 36 unique packages, including the observed pip/setuptools build tools. The new environment contains those 36 packages plus one non-editable project installation.

The separate profile is `requirements/week7/win-amd64-cp313-observed-hashed.txt`. Each external pin records the verified SHA-256 of the selected compatible wheel. Its companion `download-wheels-hashed.txt` records exact official artifact URLs and hashes used for the download-only phase. These support the observed Windows/CPython profile, not a universal cross-platform lock. No local project package is retrieved from PyPI. CPU Torch is explicitly `2.14.0+cpu`.

Historical `requirements.txt`, the working `.venv` and existing experiment artifacts were preserved. In particular, historical requirements.txt pins Matplotlib 3.10.6 while this tested observed profile contains 3.11.2. This is a declared environment difference, not a reason to rewrite historical provenance.

The wheelhouse manifest is `32943bc34c8b6807cee67c4e463215377289a62f75b5c38309fb24949d0fa7ee`. The verified offline setup manifest is `78b1934024e7068c53292329f80fba192bc197c5d1f89c83b14e0f535b8d4736`. The clean-test manifest is `e29fd71d20cffa306020cea3b9b5bf87f89f8271f529e762ffa11c187e8d630d`.

The recorded project wheel SHA-256 is `cc6d19a18c6802098ef442fdbfef1fdbb4ff67ff36025d693c42d65a06b9c8f3`. It identifies the built artifact from this run. Future builds may have different container/metadata timestamps; bit-identical wheel rebuilds were not established. The separately checked property is exact package-source bytes from the pinned Git blobs.

## Executed procedure and source boundary

1. Capture dependency metadata without importing models; check project declarations and equivalent editable metadata. Preserve old requirements and environment.
2. Select compatible wheels from public PyPI release metadata and the official PyTorch CPU index. Download only exact artifact URLs with hashes, no source distributions, dependency substitution or installation. Verify wheel identity, bytes, metadata, tags and static dependency closure.
3. Create a fresh external environment without pip; bootstrap it using the existing pinned pip's explicit new-interpreter target and the verified offline wheelhouse. Build and install the project with the new pinned tools, no build isolation/index access or dependency download. Check installed metadata and package bytes.
4. Make a separate local, non-hardlinked test checkout at the pinned commit. Disable Git hooks and inherited global/system Git configuration. Use the new interpreter, explicit source-checkout imports, external temp/cache directories and a complete local log. Verify test-module coverage, module locations, dependency metadata and exact input bytes after the test run.

The first setup attempt failed before installation because Git archive applied LF-to-CRLF conversion to 54 of 57 source files. The raw-object check correctly rejected those bytes. Its incomplete evidence was preserved. The corrected setup exporter uses `git cat-file blob` without filters, then checks every object ID; it does not silently normalize a mismatching artifact or change Git settings in the working repository.

The subsequent test checkout intentionally used Windows `core.autocrlf=true`, which matches the existing checkout and CRLF-sensitive experimental configuration pins. Installed package byte checks and source-checkout tests are distinct checks. Current experimental runners use repository-relative resource paths; standalone wheel application operation remains unvalidated. No source/test files were modified to force a pass.

Some unit tests fit small fixture models, execute fixture inference/authentication, or exercise timing instrumentation. These are implementation checks, not reruns of the saved model training, formal attack/FRR studies or a fresh formal latency benchmark. No Windows recording or private ETL scan was run.

## Explicit test coverage gap

The historical and reproduced command is `python -m unittest discover -s tests -v`. In Python 3.13, recursive test subdirectories need package `__init__.py` files. The ordinary discovery scope imported 54 modules. The following six modules, in non-package subdirectories, were not included:

- `tests/experiments/test_credential_verifier_experiment.py`
- `tests/experiments/test_reconstruction_alternatives_experiment.py`
- `tests/experiments/test_reconstruction_alternatives_formal.py`
- `tests/experiments/test_reconstruction_experiment.py`
- `tests/tier1/test_tier1.py`
- `tests/tier1/test_tier1_v2.py`

The inventory records individual test IDs and per-module/category counts. Those labels describe test scope, not security completeness. Do not describe either 964-test result as passing all repository test modules. Explicit supplementary discovery needs its own result and must not silently alter the historical count.

Four supporting documents referenced by the supplementary runners are absent from both the pinned commit and the working checkout:

- `docs/week6-tier1-v2-experiment-plan.md`
- `docs/week6-reconstruction-alternatives-experiment-plan.md`
- `docs/week6-reconstruction-alternatives-implementation-validation.md`
- `docs/week6-reconstruction-alternatives-formal-readiness.md`

Receive and verify the exact supporting documents and their expected hashes before validating the expanded shared scope. Do not invent replacement plans, regenerate frozen records or relax the hash gates. This does not imply that every individual unrun module depends on every missing document.

## Shared-release blockers and next actions

The protocol specification and narrative reports are present. The two expected raw formal-result manifests are still absent locally:

- `results/week-6/will/authentication/tier1-v2-formal-001/manifest.json`
- `results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001/manifest.json`

Those result locations are excluded by the current Git ignore rules. Receipt should use an appropriate scoped, reviewed evidence transfer rather than assume they were included by a normal pull. Do not force-add entire private result directories. Supporting-document receipt, raw formal-evidence receipt, independent semantic reconciliation and test validation are distinct tasks.

Next priorities are to obtain those exact shared inputs, validate the supplementary tests under an explicit discovery scope, and reconcile the shared experiment evidence/manifest. Faculty/lab decisions on headset access, a custodian and human-data/institutional authorization remain outside this software setup result. Slides and research-log updates remain deferred.

## Published metadata versus external payloads

The scoped published manifest covers the copied metadata, requirement pins and this document. Dependency wheel payloads, the built project wheel, raw source ZIP, environments, test checkout/object database, caches and raw local logs are not committed. Original upstream manifests identify external artifacts as well as copied metadata; they are not claims that every upstream payload is inside Git. Downloaded bytes were verified locally, and the direct-URL pins enable a later independent download. Frozen model/data transfer and experiment recomputation remain separate release dependencies.

References: [Python 3.13 test discovery](https://docs.python.org/3.13/library/unittest.html#test-discovery), [Git raw object reads](https://git-scm.com/docs/git-cat-file), [pip hash-checked installation](https://pip.pypa.io/en/stable/topics/secure-installs/), [pip managing another interpreter](https://pip.pypa.io/en/stable/topics/python-option/).
