param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$tier1Root = $PSScriptRoot
$tier1Args = @('-B', (Join-Path $tier1Root 'src/python/scripts/run_tier1_attacks.py'), '--config', (Join-Path $tier1Root 'configs/tier1_attack_experiment_v1.json'))
if ($OutputDirectory) { $tier1Args += @('--output', $OutputDirectory) }
& (Join-Path $tier1Root '.venv/Scripts/python.exe') @tier1Args
exit $LASTEXITCODE
