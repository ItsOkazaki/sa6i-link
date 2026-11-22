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
# Written for Windows PowerShell 2.0, which is what Windows 7 ships: no .NET 4
# types, no IDisposable.Dispose() calls, and the packing step goes through
# Windows' own ZIP support instead of System.IO.Compression.
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

function ConvertTo-Hex([byte[]] $bytes) {
    $text = ''
    foreach ($b in $bytes) { $text = $text + $b.ToString('x2') }
    return $text
}

# HashAlgorithm.Dispose() is an explicit interface implementation, which
# Windows PowerShell 2.0 cannot call; Clear() does the same cleanup there.
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
    $hash = $sha.ComputeHash($header)
    [void]$sha.Clear()
    return (ConvertTo-Hex $hash)
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

# Packs one folder into a ZIP using the ZIP support built into Windows, because
# System.IO.Compression needs .NET 4.5 and Windows 7 ships .NET 3.5. Local
# backups and the log are parked beside the folder while it packs: the exe
# backup alone would double the size of the result.
function New-CandidateZip([string] $root, [string] $outPath) {
    $root = (Get-Item -LiteralPath $root).FullName.TrimEnd('\')
    $parent = Split-Path -Parent $root
    $leaf = Split-Path -Leaf $root

    if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }
    # An empty ZIP: "PK\5\6" plus 18 zero bytes. CopyHere can only fill an
    # existing archive.
    $emptyZip = New-Object byte[] 22
    $emptyZip[0] = 80; $emptyZip[1] = 75; $emptyZip[2] = 5; $emptyZip[3] = 6
    [System.IO.File]::WriteAllBytes($outPath, $emptyZip)

    $park = Join-Path $parent ('_sa6i_pack_' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $park -Force | Out-Null
    $parked = New-Object System.Collections.ArrayList
    try {
        foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer })) {
            if ($file.Name -like '*.bak' -or $file.Name -eq 'patch-log.txt') {
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

        # 4 = no progress dialog, 16 = answer "yes to all". The copy runs in
        # the background, so wait until the archive stops growing.
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

# ASCII decoding maps one byte to one character, so a character index in this
# text is a byte offset in the file.

try {
    Set-Content -Path $log -Value ('Sa6i Clean patch log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean debranding patch'
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString() + ', ' + ([string]([IntPtr]::Size * 8)) + '-bit')
    Say ''
    Say 'Step 1 of 2: patch the cleaner'

    if (-not (Test-Path -LiteralPath $newAsar)) { throw 'app.asar is not next to this script. Copy all four files of the package into this folder.' }
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
        if ([IntPtr]::Size -ne 8) {
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
        $text = $null
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
        Say 'This can take a few minutes. Leave this window open.'

        $bytesTotal = 0
        foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer })) { $bytesTotal = $bytesTotal + $file.Length }
        Say ('  size before packing: ' + [Math]::Round($bytesTotal / 1MB, 1) + ' MB')

        try {
            $count = New-CandidateZip $root $zipPath
            $zipSize = (Get-Item -LiteralPath $zipPath).Length
            Say ('Packed ' + $count + ' top-level entries into ' + [Math]::Round($zipSize / 1MB, 1) + ' MB.')
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
