param(
    [string]$Config = (Join-Path $PSScriptRoot "configs/puf_baseline.json"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "sim_results")
)

$ErrorActionPreference = "Stop"

$VenvPython = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
$Runner = Join-Path $PSScriptRoot "src/python/scripts/run_puf_baseline.py"

if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
}
else {
    $Python = "python"
}

if (-not (Test-Path -LiteralPath $Config)) {
    Write-Error "Config file not found: $Config"
    exit 1
}

Write-Host "Validating configuration..."
& $Python $Runner `
    --config $Config `
    --validate-config

if ($LASTEXITCODE -ne 0) {
    Write-Error "Configuration validation failed."
    exit 1
}

Write-Host "Running PUF simulation..."
& $Python $Runner `
    --config $Config `
    --output-dir $OutputDir

if ($LASTEXITCODE -ne 0) {
    Write-Error "Simulation failed."
    exit 1
}

Write-Host "Simulation completed successfully."
