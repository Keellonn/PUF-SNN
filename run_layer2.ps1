param(
    [string]$InputRun,
    [string]$OutputName,
    [switch]$VerboseResults
)

$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
$Runner = Join-Path $PSScriptRoot "src/python/scripts/run_layer2.py"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$RunnerArgs = @("-B", $Runner)
if ($InputRun) { $RunnerArgs += @("--input-run", $InputRun) }
if ($OutputName) { $RunnerArgs += @("--output-name", $OutputName) }
if ($VerboseResults) { $RunnerArgs += "--verbose-results" }

if ($VerboseResults) { Write-Host "Loading saved Layer 1 baseline responses..." }
& $Python @RunnerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Layer 2 reconstruction failed; see the error above."
    exit 1
}
