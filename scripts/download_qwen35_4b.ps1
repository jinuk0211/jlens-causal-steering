param(
    [string]$OutputDirectory = "D:\jlens\models\Qwen3.5-4B",
    [int]$MaxParallel = 16
)

$ErrorActionPreference = "Stop"
$revision = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
$repositoryUrl = "https://huggingface.co/Qwen/Qwen3.5-4B/resolve"
$chunkSize = [int64]268435456
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
$allowedRoot = [IO.Path]::GetFullPath("D:\jlens\models")
if (-not $outputRoot.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must remain under $allowedRoot"
}

$partsRoot = "$outputRoot.parts"
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
New-Item -ItemType Directory -Path $partsRoot -Force | Out-Null

$shards = @(
    [pscustomobject]@{
        Id = "00001"
        Name = "model.safetensors-00001-of-00002.safetensors"
        Length = [int64]5329398688
        Sha256 = "26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61"
    },
    [pscustomobject]@{
        Id = "00002"
        Name = "model.safetensors-00002-of-00002.safetensors"
        Length = [int64]3990429408
        Sha256 = "cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188"
    }
)

$pending = [System.Collections.Generic.Queue[object]]::new()
foreach ($shard in $shards) {
    $partIndex = 0
    for ($start = [int64]0; $start -lt $shard.Length; $start += $chunkSize) {
        $end = [Math]::Min($start + $chunkSize - 1, $shard.Length - 1)
        $partPath = Join-Path $partsRoot ("$($shard.Id)-{0:D3}.part" -f $partIndex)
        $expectedLength = $end - $start + 1
        $existingLength = [int64]0
        if (Test-Path -LiteralPath $partPath) {
            $existingLength = (Get-Item -LiteralPath $partPath).Length
            if ($existingLength -eq $expectedLength) {
                $partIndex++
                continue
            }
            if ($existingLength -gt $expectedLength) {
                throw "Oversized existing part: $partPath ($existingLength/$expectedLength bytes)"
            }
        }
        $downloadPath = if ($existingLength -gt 0) { "$partPath.resume" } else { $partPath }
        if ($existingLength -gt 0 -and (Test-Path -LiteralPath $downloadPath)) {
            throw "Stale resume file must be inspected before retrying: $downloadPath"
        }
        $pending.Enqueue([pscustomobject]@{
            Shard = $shard.Id
            Index = $partIndex
            Start = $start + $existingLength
            End = $end
            ExpectedDownload = $expectedLength - $existingLength
            ExpectedPart = $expectedLength
            ExistingLength = $existingLength
            PartPath = $partPath
            DownloadPath = $downloadPath
            Url = "$repositoryUrl/$revision/$($shard.Name)"
        })
        $partIndex++
    }
}

$totalParts = ($shards | ForEach-Object {
    [Math]::Ceiling($_.Length / $chunkSize)
} | Measure-Object -Sum).Sum
$completedParts = $totalParts - $pending.Count
$active = @()
Write-Output "RANGE_DOWNLOAD start completed=$completedParts total=$totalParts"

while ($pending.Count -gt 0 -or $active.Count -gt 0) {
    while ($pending.Count -gt 0 -and $active.Count -lt $MaxParallel) {
        $item = $pending.Dequeue()
        $arguments = @(
            "--silent",
            "--show-error",
            "--location",
            "--retry", "10",
            "--retry-all-errors",
            "--range", "$($item.Start)-$($item.End)",
            "--output", $item.DownloadPath,
            $item.Url
        )
        $startArguments = @{
            FilePath = "curl.exe"
            ArgumentList = $arguments
            WindowStyle = "Hidden"
            PassThru = $true
        }
        $process = Start-Process @startArguments
        $active += [pscustomobject]@{ Process = $process; Item = $item }
    }

    Start-Sleep -Seconds 5
    $remaining = @()
    foreach ($job in $active) {
        if (-not $job.Process.HasExited) {
            $remaining += $job
            continue
        }
        $job.Process.Refresh()
        $item = $job.Item
        $actualDownloadLength = if (Test-Path -LiteralPath $item.DownloadPath) {
            (Get-Item -LiteralPath $item.DownloadPath).Length
        } else {
            -1
        }
        if (
            $job.Process.ExitCode -ne 0 -or
            $actualDownloadLength -ne $item.ExpectedDownload
        ) {
            throw (
                "Chunk failed: shard=$($item.Shard), part=$($item.Index), " +
                "exit=$($job.Process.ExitCode), expected=$($item.ExpectedDownload), " +
                "actual=$actualDownloadLength"
            )
        }
        if ($item.ExistingLength -gt 0) {
            $target = [IO.File]::Open(
                $item.PartPath,
                [IO.FileMode]::Append,
                [IO.FileAccess]::Write
            )
            $source = [IO.File]::OpenRead($item.DownloadPath)
            try {
                $source.CopyTo($target)
            } finally {
                $source.Dispose()
                $target.Dispose()
            }
            Remove-Item -LiteralPath $item.DownloadPath -Force
        }
        $actualPartLength = (Get-Item -LiteralPath $item.PartPath).Length
        if ($actualPartLength -ne $item.ExpectedPart) {
            throw (
                "Completed part has wrong length: $($item.PartPath) " +
                "($actualPartLength/$($item.ExpectedPart))"
            )
        }
        $completedParts++
        Write-Output (
            "RANGE_DOWNLOAD completed=$completedParts/$totalParts " +
            "shard=$($item.Shard) part=$($item.Index) bytes=$actualPartLength"
        )
    }
    $active = $remaining
}

$buffer = New-Object byte[] (8MB)
foreach ($shard in $shards) {
    $targetPath = Join-Path $outputRoot $shard.Name
    $target = [IO.File]::Open($targetPath, [IO.FileMode]::Create, [IO.FileAccess]::Write)
    try {
        $partIndex = 0
        for ($start = [int64]0; $start -lt $shard.Length; $start += $chunkSize) {
            $partPath = Join-Path $partsRoot ("$($shard.Id)-{0:D3}.part" -f $partIndex)
            $source = [IO.File]::OpenRead($partPath)
            try {
                while (($read = $source.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $target.Write($buffer, 0, $read)
                }
            } finally {
                $source.Dispose()
            }
            $partIndex++
        }
    } finally {
        $target.Dispose()
    }

    $actualLength = (Get-Item -LiteralPath $targetPath).Length
    if ($actualLength -ne $shard.Length) {
        throw "Merged shard has wrong length: $targetPath ($actualLength/$($shard.Length))"
    }
    $actualHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $shard.Sha256) {
        throw "Merged shard has wrong SHA-256: $targetPath ($actualHash)"
    }
    Write-Output "SHARD_VERIFIED name=$($shard.Name) bytes=$actualLength sha256=$actualHash"
}

Write-Output "MODEL_DOWNLOAD_COMPLETE path=$outputRoot revision=$revision"
