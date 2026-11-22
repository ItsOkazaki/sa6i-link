# Apply the Sa6i Clean debranded bundle to an installed Sa6i Clean folder, then
# pack the whole candidate folder into one ZIP.
#
# Electron checks that resources\app.asar matches a hash stored inside
# "Sa6i Clean Integration.exe". Replacing the bundle therefore requires
# updating that stored hash, which is what this script does. The hash is read
# from the bundle that is actually installed, so this works for any cleaner
# build, not just one exact version. Both files are backed up first, so the
# folder can be put back exactly as it was.
#
# Run "Apply Sa6i Clean Patch.cmd" instead of this file directly: that keeps
# the window open and saves everything it printed to patch-log.txt.

[CmdletBinding()]
param(
    [switch] $NoZip,
    [string] $ZipRoot = ''
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'patch-log.txt'
$newAsar = Join-Path $here 'app.asar'
$exe = Join-Path $here 'Sa6i Clean Integration.exe'
$oldAsar = Join-Path $here 'resources\app.asar'
$expectedNew = '8e6ee85e794723de784eb1adc1baedf28a612f968e7b88970297f91053e37fb9'

function Say([string] $text) {
    Write-Host $text
    Add-Content -Path $log -Value $text
}

function Get-HeaderHash([string] $path) {
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $head = New-Object byte[] 16
        if ($stream.Read($head, 0, 16) -ne 16) { throw "Not an ASAR file: $path" }
        $size = [BitConverter]::ToUInt32($head, 12)
        if ($size -le 0 -or $size -gt 20000000) { throw "Bad ASAR header size in $path" }
        $header = New-Object byte[] $size
        $offset = 0
        while ($offset -lt $size) {
            $n = $stream.Read($header, $offset, $size - $offset)
            if ($n -le 0) { throw "Truncated ASAR header in $path" }
            $offset += $n
        }
    } finally {
        $stream.Close()
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($header)
    } finally {
        $sha.Dispose()
    }
    $text = ''
    foreach ($b in $hash) { $text = $text + $b.ToString('x2') }
    return $text
}

function Get-FileHashText([string] $path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $hash = $sha.ComputeHash($stream)
    } finally {
        $stream.Close()
        $sha.Dispose()
    }
    $text = ''
    foreach ($b in $hash) { $text = $text + $b.ToString('x2') }
    return $text
}

function New-CandidateZip([string] $root, [string] $outPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $root = (Get-Item -LiteralPath $root).FullName.TrimEnd('\')
    $prefix = $root + '\'
    if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }
    $archive = [System.IO.Compression.ZipFile]::Open($outPath, [System.IO.Compression.ZipArchiveMode]::Create)
    $count = 0
    try {
        $files = Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer }
        foreach ($file in $files) {
            # Backups and logs are local safety copies, not part of the candidate.
            if ($file.Name -like '*.bak') { continue }
            if ($file.Name -eq 'patch-log.txt') { continue }
            if ($file.FullName -eq $outPath) { continue }
            $entry = $file.FullName.Substring($prefix.Length).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $file.FullName, $entry, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
            $count = $count + 1
        }
    } finally {
        $archive.Dispose()
    }
    return $count
}

# ASCII decoding maps one byte to one character, so a character index in this
# text is a byte offset in the file.

try {
    Set-Content -Path $log -Value ('Sa6i Clean patch log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean debranding patch'
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString())
    Say ''
    Say 'Step 1 of 2: patch the cleaner'

    if (-not (Test-Path -LiteralPath $newAsar)) { throw 'app.asar is not next to this script.' }
    if (-not (Test-Path -LiteralPath $exe)) { throw '"Sa6i Clean Integration.exe" is not next to this script.' }
    if (-not (Test-Path -LiteralPath $oldAsar)) { throw 'resources\app.asar is not next to this script.' }

    $newHash = Get-HeaderHash $newAsar
    if ($newHash -ne $expectedNew) {
        throw ('app.asar next to this script is not the debranded bundle (its hash is ' + $newHash + '). Nothing was changed.')
    }

    $oldHash = Get-HeaderHash $oldAsar
    Say ('Bundle in the folder: ' + $oldHash)
    Say ('Debranded bundle:     ' + $newHash)

    if ($oldHash -eq $newHash) {
        Say 'This folder already holds the debranded bundle. Skipping the executable patch.'
    } else {
        if (-not [Environment]::Is64BitProcess) {
            Say 'Note: this is 32-bit PowerShell; the read may run out of memory. If it fails, use the 64-bit one.'
        }
        Say 'Reading the executable (about 110 MB, this takes a moment)...'
        $bytes = [System.IO.File]::ReadAllBytes($exe)
        $text = [System.Text.Encoding]::ASCII.GetString($bytes)
        $bytes = $null
        $position = $text.IndexOf($oldHash, [System.StringComparison]::Ordinal)
        if ($position -lt 0) {
            throw ('The executable does not store the hash of the installed bundle (' + $oldHash + '). Nothing was changed.')
        }
        if ($text.IndexOf($oldHash, $position + $oldHash.Length, [System.StringComparison]::Ordinal) -ge 0) {
            throw 'The executable stores that hash more than once. Nothing was changed.'
        }
        Say ('Found the stored hash at byte ' + $position + '.')

        Copy-Item -LiteralPath $exe -Destination ($exe + '.bak') -Force
        Copy-Item -LiteralPath $oldAsar -Destination ($oldAsar + '.bak') -Force
        Say 'Backed up the executable and the old bundle as .bak.'

        $bytes = [System.IO.File]::ReadAllBytes($exe)
        $replacement = [System.Text.Encoding]::ASCII.GetBytes($newHash)
        [Array]::Copy($replacement, 0, $bytes, $position, $replacement.Length)
        [System.IO.File]::WriteAllBytes($exe, $bytes)
        $bytes = $null
        Copy-Item -LiteralPath $newAsar -Destination $oldAsar -Force

        $after = Get-HeaderHash $oldAsar
        if ($after -ne $newHash) { throw 'The debranded bundle did not install correctly.' }
        Say 'Patched. The cleaner no longer has Tip or Feedback.'
    }

    Say ''
    if ($NoZip) {
        Say 'Step 2 of 2: skipped (-NoZip was given).'
    } else {
        $root = $ZipRoot
        if ([string]::IsNullOrEmpty($root)) {
            if ((Split-Path -Leaf $here) -eq 'Sa6i Clean') { $root = Split-Path -Parent $here }
            else { $root = $here }
        }
        $root = $root.TrimEnd('\')
        if (-not (Test-Path -LiteralPath $root)) { throw ('The folder to pack does not exist: ' + $root) }

        $parent = Split-Path -Parent $root
        if ([string]::IsNullOrEmpty($parent)) { $parent = $root }
        $zipPath = Join-Path $parent 'Sa6i-Link-Integrated-Candidate.zip'

        Say 'Step 2 of 2: pack the candidate folder'
        Say ('  from: ' + $root)
        Say ('  to:   ' + $zipPath)
        Say 'This can take a couple of minutes. Leave this window open.'

        $bytesTotal = 0
        foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer })) { $bytesTotal = $bytesTotal + $file.Length }
        Say ('  size before packing: ' + [Math]::Round($bytesTotal / 1MB, 1) + ' MB')

        try {
            $count = New-CandidateZip $root $zipPath
            $zipSize = (Get-Item -LiteralPath $zipPath).Length
            Say ('Packed ' + $count + ' files into ' + [Math]::Round($zipSize / 1MB, 1) + ' MB.')
            Say ('ZIP SHA-256: ' + (Get-FileHashText $zipPath))
        } catch {
            Say ('Could not build the ZIP: ' + $_.Exception.Message)
            Say 'The patch itself is done; only the ZIP failed.'
            Say 'Do it by hand instead: right-click the candidate folder, then Send to, then Compressed (zipped) folder.'
        }
    }

    Say ''
    Say 'Done.'
    if ($oldHash -ne $newHash) {
        Say 'Backups kept as:'
        Say ('  ' + $exe + '.bak')
        Say ('  ' + $oldAsar + '.bak')
    } else {
        Say 'Nothing was patched, so the earlier .bak files are untouched.'
    }
    Say 'Start Sa6i Link as usual.'
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    Say 'Nothing was changed unless the log above says otherwise.'
    exit 1
}
