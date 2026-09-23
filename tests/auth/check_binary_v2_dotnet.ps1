# TEST ONLY / SYNTHETIC PUBLIC FIXTURE / NOT RUNTIME SECRET MATERIAL.
# Supplemental .NET execution of the exact Unity writer source, not Unity tests.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$source = Join-Path $repo 'src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/BinaryWindowMessageWriter.cs'
Add-Type -Path $source -ReferencedAssemblies System.Numerics
$vectors = Get-Content -Raw (Join-Path $PSScriptRoot 'fixtures/binary-v2/vectors.json') | ConvertFrom-Json
function From-Hex([string]$text) {
    $bytes = New-Object byte[] ($text.Length / 2)
    for ($i=0; $i -lt $bytes.Length; $i++) { $bytes[$i] = [Convert]::ToByte($text.Substring($i*2,2),16) }
    return ,$bytes
}
function To-Hex([byte[]]$bytes) { return [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant() }
function Check-Bytes([byte[]]$actual, $vector) {
    $expected = From-Hex $vector.expected_hex
    if ($actual.Length -ne $expected.Length) { throw "Length mismatch: $($vector.id)" }
    for ($i=0; $i -lt $actual.Length; $i++) {
        if ($actual[$i] -ne $expected[$i]) { throw "Byte mismatch: $($vector.id) at $i" }
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    $mac = New-Object Security.Cryptography.HMACSHA256
    try {
        $mac.Key = From-Hex $vectors.key_hex
        if ((To-Hex $sha.ComputeHash($actual)) -cne $vector.sha256) { throw 'SHA256 mismatch' }
        if ((To-Hex $mac.ComputeHash($actual)) -cne $vector.hmac) { throw 'HMAC mismatch' }
    } finally { $sha.Dispose(); $mac.Dispose() }
}
foreach ($v in $vectors.scalars) {
    $actual = New-Object 'System.Collections.Generic.List[byte]'
    foreach ($word in $v.words) {
        $value = [PufSnn.QuestLogger.BinaryWindowMessageWriter]::FromBits([Convert]::ToUInt32($word,16))
        if (-not $v.valid) {
            $rejected = $false
            try { [void][PufSnn.QuestLogger.BinaryWindowMessageWriter]::EncodeFloat($value) } catch { $rejected = $true }
            if (-not $rejected) { throw "Nonfinite accepted: $word" }
        } else {
            $actual.AddRange([PufSnn.QuestLogger.BinaryWindowMessageWriter]::EncodeFloat($value))
        }
    }
    if ($v.valid) { Check-Bytes $actual.ToArray() $v }
}
foreach ($v in $vectors.windows) {
    $w = New-Object PufSnn.QuestLogger.BinaryWindow
    $w.device_id = 'quest-02'; $w.session_id = [byte[]](0..15); $w.window_id = 'binary-golden-000'
    $w.capture_start_ns = 1000000000; $w.capture_end_ns = 3000000000
    $w.samples = New-Object 'PufSnn.QuestLogger.BinaryWindowSample[]' 120
    for ($i=0; $i -lt 120; $i++) {
        $s = New-Object PufSnn.QuestLogger.BinaryWindowSample
        $s.sample_index = $i; $s.capture_time_ns = 1000000000L + $i*16666667L
        $s.position_m = [float[]](0,0,0)
        if ($i -eq 0) { $s.position_m = [float[]]([PufSnn.QuestLogger.BinaryWindowMessageWriter]::FromBits([Convert]::ToUInt32($v.position_word,16)),-0.25,0) }
        $s.orientation_xyzw = [float[]](0,0,0,1)
        if ($v.quaternion) {
            $half = [PufSnn.QuestLogger.BinaryWindowMessageWriter]::FromBits(0x3f3504f3)
            $s.orientation_xyzw = [float[]](0,$half,0,$half)
        }
        $s.tracking_valid = $i -lt $v.tracking_count
        $w.samples[$i] = $s
    }
    if ($v.valid) {
        $actual = [PufSnn.QuestLogger.BinaryWindowMessageWriter]::BuildCanonicalProtectedBytes($w)
        Check-Bytes $actual $v
    } else {
        $rejected = $false
        try { [void][PufSnn.QuestLogger.BinaryWindowMessageWriter]::BuildCanonicalProtectedBytes($w) } catch { $rejected = $true }
        if (-not $rejected) { throw 'Invalid quality accepted' }
    }
}
Write-Output "PASS: 11 scalar groups and 26 complete-window vectors, raw bytes/SHA256/HMAC; supplemental .NET, not Unity."
