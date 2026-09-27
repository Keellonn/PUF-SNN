param([Parameter(Mandatory = $true)][string]$Output)

# this exports synthetic bytes from the actual C# writer for Python rejection tests
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$writerPath = Join-Path $repoPath 'src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/BinaryWindowMessageWriter.cs'
Add-Type -Path $writerPath -ReferencedAssemblies System.Numerics
$window = New-Object PufSnn.QuestLogger.BinaryWindow
$window.device_id = 'synthetic-device'
$window.session_id = [byte[]](0..15)
$window.window_id = 'cross-language-negative-window'
$window.capture_start_ns = 1000000000
$window.capture_end_ns = 3000000000
$window.samples = New-Object 'PufSnn.QuestLogger.BinaryWindowSample[]' 120

for ($sampleIndex = 0; $sampleIndex -lt 120; $sampleIndex++) {
    $sample = New-Object PufSnn.QuestLogger.BinaryWindowSample
    $sample.sample_index = $sampleIndex
    $sample.capture_time_ns = 1000000000L + $sampleIndex * 16666667L
    $sample.position_m = [float[]](0.1, -0.25, 0.3)
    $sample.orientation_xyzw = [float[]](0, 0, 0, 1)
    $sample.tracking_valid = $true
    $window.samples[$sampleIndex] = $sample
}

function To-Hex([byte[]]$Bytes) {
    return [BitConverter]::ToString($Bytes).Replace('-', '').ToLowerInvariant()
}

$canonical = [PufSnn.QuestLogger.BinaryWindowMessageWriter]::BuildCanonicalProtectedBytes($window)
$deviceLength = $canonical[19] * 256 + $canonical[20]
$sessionOffset = 21 + $deviceLength
$windowOffset = $sessionOffset + 24
$windowLength = $canonical[$windowOffset] * 256 + $canonical[$windowOffset + 1]
$captureOffset = $windowOffset + 2 + $windowLength
$payloadOffset = $captureOffset + 32
$positionOffset = $payloadOffset + 3 + 10
$vectors = @()

foreach ($caseName in @('wrong_endianness', 'changed_float', 'reordered_binary_fields', 'modified_version', 'altered_payload_length')) {
    $changed = [byte[]]$canonical.Clone()

    if ($caseName -eq 'wrong_endianness') {
        [Array]::Reverse($changed, $positionOffset, 4)
    } elseif ($caseName -eq 'changed_float') {
        $changed[$positionOffset + 3] = $changed[$positionOffset + 3] -bxor 1
    } elseif ($caseName -eq 'reordered_binary_fields') {
        for ($byteIndex = 0; $byteIndex -lt 4; $byteIndex++) {
            $saved = $changed[$positionOffset + $byteIndex]
            $changed[$positionOffset + $byteIndex] = $changed[$positionOffset + 4 + $byteIndex]
            $changed[$positionOffset + 4 + $byteIndex] = $saved
        }
    } elseif ($caseName -eq 'modified_version') {
        $changed[5] = 3
    } else {
        $changed[$captureOffset + 28 + 3] = $changed[$captureOffset + 28 + 3] -bxor 1
    }

    $vectors += @{ name = $caseName; changed_hex = (To-Hex $changed) }
}

$publicKey = [byte[]](0..31)
$sha = [Security.Cryptography.SHA256]::Create()
$mac = New-Object Security.Cryptography.HMACSHA256

try {
    $mac.Key = $publicKey
    $result = @{ source = 'actual C# writer under supplemental .NET; not Unity execution'; canonical_hex = (To-Hex $canonical); sha256 = (To-Hex $sha.ComputeHash($canonical)); key_hex = (To-Hex $publicKey); tag_hex = (To-Hex $mac.ComputeHash($canonical)); vectors = $vectors }
} finally {
    $sha.Dispose()
    $mac.Dispose()
}

$outputPath = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $outputPath) {
    throw "Output already exists: $outputPath"
}

[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
[IO.File]::WriteAllText($outputPath, ($result | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding($false)))
Write-Output "Exported five C# negative protocol vectors to $outputPath"
