# Point Sa6i Link's built-in Sa6i Clean tab at the debranded cleaner.
#
# Sa6i Link never launches a cleaner it has not identified: before starting
# "Sa6i Clean\Sa6i Clean Integration.exe" it hashes that executable and its
# resources\app.asar and compares them with two digests compiled into
# sa6i-link.exe (sa6i/clean/native_embed.c). Debranding changes both files, so
# without this step the tab refuses to start the cleaner and says so. Nothing
# falls back to a different executable.
#
# This reads the two digests from the files that are actually installed, finds
# the pinned digests in sa6i-link.exe, and swaps them, keeping a .bak of the
# executable. It touches only those 64 bytes; no other content changes.
#
# When that is done it also packs the whole candidate folder into
# "Sa6i-Link-Integrated-Candidate.zip" beside it, using the ZIP support built
# into Windows, so the archive is produced after the digests are correct.
#
# Put this file and "Retarget Sa6i Clean.cmd" next to sa6i-link.exe (the
# candidate folder, one level above "Sa6i Clean"), then run the .cmd.

[CmdletBinding()]
param(
    [string] $Desktop = '',
    [switch] $NoZip
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'retarget-log.txt'

# The cleaner builds whose digests an earlier sa6i-link.exe could be pinning.
$pairs = @(
    @('2c9bdd29209ebc58103753a2a66d8b9c840d94054eea368239566b5d42408d74',
      '4cbe981c5a473d61a7b679e61db49b4c5a0a052ba5783ce903054b46562a10ba'),
    @('e991d57efbb8de204a7fb9e9f5b3ef5fe34531e37e77556f66f079545a866a3f',
      'b3af2dd8355194905fc929ccd1d40dcaa78542208cc4b0d0612c50bf9d93e83f')
)

function Say([string] $text) {
    Write-Host $text
    Add-Content -Path $log -Value $text
}

function Get-HashBytes([string] $path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $hash = $sha.ComputeHash($stream)
    } finally {
        $stream.Close()
        [void]$sha.Clear()
    }
    return $hash
}

function ConvertTo-Hex([byte[]] $bytes) {
    $text = ''
    foreach ($b in $bytes) { $text = $text + $b.ToString('x2') }
    return $text
}

function ConvertFrom-Hex([string] $hex) {
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [System.Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    return $bytes
}

function Count-Of([string] $text, [string] $pattern) {
    $count = 0
    $from = 0
    while ($true) {
        $at = $text.IndexOf($pattern, $from, [System.StringComparison]::Ordinal)
        if ($at -lt 0) { break }
        $count = $count + 1
        $from = $at + $pattern.Length
    }
    return $count
}


function Get-FileHashText([string] $path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $hash = $sha.ComputeHash($stream)
    } finally {
        $stream.Close()
        [void]$sha.Clear()
    }
    return (ConvertTo-Hex $hash)
}

# System.IO.Compression needs .NET 4.5 and Windows 7 ships .NET 3.5, so packing
# goes through the ZIP support built into Windows. Local backups and logs are
# parked beside the folder while it packs: the executable backup alone would
# double the size of the result.
function New-CandidateZip([string] $root, [string] $outPath) {
    $root = (Get-Item -LiteralPath $root).FullName.TrimEnd('\')
    $parent = Split-Path -Parent $root
    $leaf = Split-Path -Leaf $root

    if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }
    $emptyZip = New-Object byte[] 22
    $emptyZip[0] = 80; $emptyZip[1] = 75; $emptyZip[2] = 5; $emptyZip[3] = 6
    [System.IO.File]::WriteAllBytes($outPath, $emptyZip)

    $park = Join-Path $parent ('_sa6i_pack_' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $park -Force | Out-Null
    $parked = New-Object System.Collections.ArrayList
    try {
        foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer })) {
            if ($file.Name -like '*.bak' -or $file.Name -like '*-log.txt') {
                $target = Join-Path $park ([Guid]::NewGuid().ToString('N'))
                Move-Item -LiteralPath $file.FullName -Destination $target
                [void]$parked.Add(@($target, $file.FullName))
            }
        }

        $shell = New-Object -ComObject Shell.Application
        $zipNs = $shell.NameSpace($outPath)
        if ($zipNs -eq $null) { throw 'Windows will not open the new ZIP for writing.' }
        $parentNs = $shell.NameSpace($parent)
        if ($parentNs -eq $null) { throw ('Windows cannot open the folder above: ' + $parent) }
        $item = $parentNs.ParseName($leaf)
        if ($item -eq $null) { throw ('Windows cannot see the folder to pack: ' + $root) }

        $zipNs.CopyHere($item, 20)

        $last = ''
        $stable = 0
        $count = 0
        for ($i = 0; $i -lt 900; $i++) {
            Start-Sleep -Seconds 2
            $size = 0
            if (Test-Path -LiteralPath $outPath) { $size = (Get-Item -LiteralPath $outPath).Length }
            try { $count = $zipNs.Items().Count } catch { }
            $sig = ([string]$size) + '/' + ([string]$count)
            if ($sig -eq $last -and $count -ge 1 -and $size -gt 100000) {
                $stable = $stable + 1
                if ($stable -ge 2) { break }
            } else {
                $stable = 0
                $last = $sig
            }
        }

        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($zipNs)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($parentNs)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
        return $count
    } finally {
        foreach ($pair in $parked) {
            if (Test-Path -LiteralPath $pair[0]) {
                Move-Item -LiteralPath $pair[0] -Destination $pair[1] -Force
            }
        }
        if (Test-Path -LiteralPath $park) { Remove-Item -LiteralPath $park -Recurse -Force }
    }
}

try {
    Set-Content -Path $log -Value ('Sa6i Clean retarget log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean: point Sa6i Link at the debranded cleaner'
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString())
    Say ''

    if ([string]::IsNullOrEmpty($Desktop)) { $Desktop = Join-Path $here 'sa6i-link.exe' }
    $cleanExe = Join-Path $here 'Sa6i Clean\Sa6i Clean Integration.exe'
    $cleanAsar = Join-Path $here 'Sa6i Clean\resources\app.asar'

    if (-not (Test-Path -LiteralPath $Desktop)) { throw 'sa6i-link.exe is not next to this script. Put the two retarget files in the candidate folder, beside sa6i-link.exe.' }
    if (-not (Test-Path -LiteralPath $cleanExe)) { throw 'Sa6i Clean\Sa6i Clean Integration.exe was not found below this folder.' }
    if (-not (Test-Path -LiteralPath $cleanAsar)) { throw 'Sa6i Clean\resources\app.asar was not found below this folder.' }

    $newExe = Get-HashBytes $cleanExe
    $newAsar = Get-HashBytes $cleanAsar
    Say ('Cleaner executable SHA-256: ' + (ConvertTo-Hex $newExe))
    Say ('Cleaner bundle SHA-256:     ' + (ConvertTo-Hex $newAsar))
    Say ''

    # One byte maps to one character in Latin-1, so a character index is a byte
    # offset; that lets the pinned digests be found as text.
    $latin = [System.Text.Encoding]::GetEncoding(28591)
    $bytes = [System.IO.File]::ReadAllBytes($Desktop)
    $text = $latin.GetString($bytes)
    Say ('sa6i-link.exe: ' + [Math]::Round($bytes.Length / 1MB, 1) + ' MB')

    $newExeText = $latin.GetString($newExe)
    $newAsarText = $latin.GetString($newAsar)
    $already = $false
    if ((Count-Of $text $newExeText) -eq 1 -and (Count-Of $text $newAsarText) -eq 1) {
        Say 'This executable already accepts these two files. No digest change needed.'
        $already = $true
    }

    if (-not $already) {
    $chosen = $null
    foreach ($pair in $pairs) {
        $oldExeText = $latin.GetString((ConvertFrom-Hex $pair[0]))
        $oldAsarText = $latin.GetString((ConvertFrom-Hex $pair[1]))
        $exeCount = Count-Of $text $oldExeText
        $asarCount = Count-Of $text $oldAsarText
        Say ('Known build ' + $pair[0].Substring(0, 8) + ': ' + $exeCount + ' executable digest, ' + $asarCount + ' bundle digest')
        if ($exeCount -eq 1 -and $asarCount -eq 1) { $chosen = $pair; break }
    }
    if ($chosen -eq $null) {
        throw 'This sa6i-link.exe does not pin either cleaner build this script knows. Nothing was changed.'
    }

    if (-not (Test-Path -LiteralPath ($Desktop + '.bak'))) {
        Copy-Item -LiteralPath $Desktop -Destination ($Desktop + '.bak') -Force
        Say 'Backed up sa6i-link.exe as .bak.'
    } else {
        Say 'Kept the existing sa6i-link.exe backup.'
    }

    $offset = $text.IndexOf($latin.GetString((ConvertFrom-Hex $chosen[0])), 0, [System.StringComparison]::Ordinal)
    [Array]::Copy($newExe, 0, $bytes, $offset, $newExe.Length)
    $offset = $text.IndexOf($latin.GetString((ConvertFrom-Hex $chosen[1])), 0, [System.StringComparison]::Ordinal)
    [Array]::Copy($newAsar, 0, $bytes, $offset, $newAsar.Length)
    $text = $null

    [System.IO.File]::WriteAllBytes($Desktop, $bytes)
    $bytes = $null

    $check = $latin.GetString([System.IO.File]::ReadAllBytes($Desktop))
    if ((Count-Of $check $newExeText) -ne 1 -or (Count-Of $check $newAsarText) -ne 1) {
        throw 'The new digests are not in the executable exactly once. Restore sa6i-link.exe.bak.'
    }
    Say ''
    Say 'Sa6i Link will now start the debranded cleaner from its Sa6i Clean tab.'
    Say ('Backup: ' + $Desktop + '.bak')
    }

    Say ''
    if ($NoZip) {
        Say 'Packing skipped (-NoZip was given).'
    } else {
        $zipPath = Join-Path (Split-Path -Parent $here) 'Sa6i-Link-Integrated-Candidate.zip'
        Say 'Packing the candidate folder'
        Say ('  from: ' + $here)
        Say ('  to:   ' + $zipPath)
        Say 'This can take a few minutes. Leave this window open.'

        $bytesTotal = 0
        foreach ($file in (Get-ChildItem -LiteralPath $here -Recurse -Force | Where-Object { -not $_.PSIsContainer })) { $bytesTotal = $bytesTotal + $file.Length }
        Say ('  size before packing: ' + [Math]::Round($bytesTotal / 1MB, 1) + ' MB')

        try {
            $count = New-CandidateZip $here $zipPath
            $zipSize = (Get-Item -LiteralPath $zipPath).Length
            Say ('Packed ' + $count + ' top-level entries into ' + [Math]::Round($zipSize / 1MB, 1) + ' MB.')
            Say ('ZIP SHA-256: ' + (Get-FileHashText $zipPath))
        } catch {
            Say ('Could not build the ZIP: ' + $_.Exception.Message)
            Say 'Everything else is done; only the ZIP failed.'
            Say 'Do it by hand instead: right-click the candidate folder, then Send to, then Compressed (zipped) folder.'
        }
    }

    Say ''
    Say 'Done.'
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    Say 'Nothing was changed unless the log above says otherwise.'
    exit 1
}
