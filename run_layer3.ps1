param([string]$Output, [string]$Config)
$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$RunnerArgs = @("-B", (Join-Path $PSScriptRoot "src/python/scripts/run_layer3_demo.py"))
if ($Output) { $RunnerArgs += @("--output", $Output) }
if ($Config) { $RunnerArgs += @("--config", $Config) }
& $Python @RunnerArgs
exit $LASTEXITCODE
