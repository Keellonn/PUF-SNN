# Local PowerShell validation

These commands use the existing repository environment. They do not create an
environment, install dependencies, modify authentication source, run a pilot,
or enable formal execution. The test patch adds exactly one new test file.
It does not change existing tests or evidence. Run from your local VS Code
PowerShell terminal.

First check and apply the supplied fallback patch. Stop if either command fails;
do not force it over a pre-existing test file.

```powershell
Set-Location -LiteralPath 'C:\PUF+SNN_SharedRepo\PUF-SNN'
git apply --check -- .\docs\week8-three-arm-auth-tests.patch
if ($LASTEXITCODE -ne 0) { throw 'Test patch check failed; nothing applied.' }
git apply -- .\docs\week8-three-arm-auth-tests.patch
if ($LASTEXITCODE -ne 0) { throw 'Test patch application failed.' }
```

Set the import path in this terminal, then run the new suite. Its authentication
executions are bounded unit fixtures; its formal-allocation checks only compile
a plan. Unit evidence is created in isolated temporary directories and removed
by fixture cleanup.

```powershell
$env:PYTHONPATH = "$PWD\src\python;$PWD\tests"
& .\.venv\Scripts\python.exe -m unittest -v experiments.test_three_arm_auth_v1
if ($LASTEXITCODE -ne 0) { throw 'Three-arm tests failed; do not run the pilot.' }
```

Run the relevant existing pipeline, acquisition, noise and harness regressions:

```powershell
& .\.venv\Scripts\python.exe -m unittest -v test_stored_credential_pipeline test_majority3_pipeline test_pipeline_v2 puf.test_correlated_noise_v1 puf.test_acquisition experiments.test_majority3_auth_v1 experiments.test_majority3_auth_corrections
if ($LASTEXITCODE -ne 0) { throw 'Pipeline/noise/harness regressions failed; do not run the pilot.' }
```

Run the existing authentication and admission suite, including independent
credential verification, handshake, lifecycle, window, sequence and release tests:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s .\tests\auth -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Authentication/admission regressions failed; do not run the pilot.' }
```

Record the actual unittest test counts and terminal outcomes. None of these
suites ran in the agent sandbox. A successful static patch/syntax check is not
a passing unittest result. The authorized nonformal pilot remains unexecuted;
these instructions contain no pilot or formal-study command.
