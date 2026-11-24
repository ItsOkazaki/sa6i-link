# SPDX-License-Identifier: GPL-3.0-or-later
# Point Sa6i Link's built-in Sa6i Clean tab at the debranded cleaner.
#
# Sa6i Link never launches a cleaner it has not identified: before starting
# "Sa6i Clean\Sa6i Clean Integration.exe" it hashes that executable and its
# resources\app.asar and compares them with two digests compiled into the
# Sa6i Link executable itself. Debranding changes both files, so without this
# step the tab refuses to start the cleaner and says so. Nothing falls back to
# a different executable.
#
# This finds the Sa6i Link executable by looking for one of those pinned
# digests inside it - the file name does not matter - reads the two digests
# from the files that are actually installed, and swaps the pinned pair,
# keeping a .bak. It touches only those 64 bytes.
#
# When that is done it also packs the whole candidate folder into
# "Sa6i-Link-Integrated-Candidate.zip" beside it, using the ZIP support built
# into Windows, so the archive is produced after the digests are correct.
#
# Put this file and "Retarget Sa6i Clean.cmd" in the candidate folder, the one
# that contains the "Sa6i Clean" folder, then run the .cmd.

[CmdletBinding()]
param(
    [string] $Desktop = '',
    [switch] $NoZip,
    [switch] $NoIcon,
    [switch] $IconOnly
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'retarget-log.txt'
$script:latin = [System.Text.Encoding]::GetEncoding(28591)

# Printed in every log: it is the only way to tell which copy of this script
# actually ran, which matters when a download lands as "... (1).ps1".
$scriptBuild = '2026-11-22-icon-watchdog'

# The cleaner builds whose digests a Sa6i Link executable could be pinning.
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

function Get-FileHashText([string] $path) {
    return (ConvertTo-Hex (Get-HashBytes $path))
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

# Counts a byte pattern in a file without holding the whole file in memory.
function Count-InFile([string] $path, [string] $pattern) {
    $stream = [System.IO.File]::OpenRead($path)
    $buffer = New-Object byte[] 1048576
    $carry = ''
    $count = 0
    try {
        while (($n = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $chunk = $carry + $script:latin.GetString($buffer, 0, $n)
            $from = 0
            while ($true) {
                $at = $chunk.IndexOf($pattern, $from, [System.StringComparison]::Ordinal)
                if ($at -lt 0) { break }
                $count = $count + 1
                $from = $at + $pattern.Length
            }
            $tail = $pattern.Length - 1
            if ($chunk.Length -gt $tail) {
                $carry = $chunk.Substring($chunk.Length - $tail)
            } else {
                $carry = $chunk
            }
        }
    } finally {
        $stream.Close()
    }
    return $count
}

# Rename-Item gained -LiteralPath only in PowerShell 3.0, and this has to run on
# the 2.0 that ships with Windows 7, so renaming and moving go through
# System.IO directly: those calls mean the same thing in every version.
#
# System.IO.Compression needs .NET 4.5 and Windows 7 ships .NET 3.5, so packing
# goes through the ZIP support built into Windows. Local backups and logs are
# parked beside the folder while it packs: the executable backup alone would
# double the size of the result.
function New-CandidateZip([string] $root, [string] $outPath) {
    $root = [System.IO.Path]::GetFullPath($root).TrimEnd('\')
    $parent = Split-Path -Parent $root
    $leaf = Split-Path -Leaf $root

    if (Test-Path -LiteralPath $outPath) { [System.IO.File]::Delete($outPath) }
    $emptyZip = New-Object byte[] 22
    $emptyZip[0] = 80; $emptyZip[1] = 75; $emptyZip[2] = 5; $emptyZip[3] = 6
    [System.IO.File]::WriteAllBytes($outPath, $emptyZip)

    $park = Join-Path $parent ('_sa6i_pack_' + [Guid]::NewGuid().ToString('N'))
    [void][System.IO.Directory]::CreateDirectory($park)
    $parked = New-Object System.Collections.ArrayList
    try {
        foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object { -not $_.PSIsContainer })) {
            if ($file.Name -like '*.bak' -or $file.Name -like '*-log.txt') {
                $target = Join-Path $park ([Guid]::NewGuid().ToString('N'))
                [System.IO.File]::Move($file.FullName, $target)
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
            if (Test-Path -LiteralPath $outPath) { $size = (New-Object System.IO.FileInfo($outPath)).Length }
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
                if (Test-Path -LiteralPath $pair[1]) { [System.IO.File]::Delete($pair[1]) }
                [System.IO.File]::Move($pair[0], $pair[1])
            }
        }
        if ([System.IO.Directory]::Exists($park)) { [System.IO.Directory]::Delete($park, $true) }
    }
}


# Windows will not let anything write to an executable that is running, and
# Sa6i Link lives in the notification area, so "closed" is easy to get wrong.
function Test-Writable([string] $path) {
    try {
        $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $stream.Close()
        return $true
    } catch {
        return $false
    }
}

function Stop-Launcher([string] $path) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
    $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
    if ($procs.Count -eq 0) { return $false }
    Say ('Sa6i Link is running as ' + $name + '. Asking it to close...')
    foreach ($proc in $procs) { [void]$proc.CloseMainWindow() }
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Writable $path) {
            Say 'Sa6i Link closed.'
            return $true
        }
    }
    return $false
}


# --- icon replacement -------------------------------------------------------
#
# The icon is not a string: Windows reads it from the executable's resource
# section, as a group of uncompressed or PNG images. Replacing it means
# walking that section, and writing a new image into the space an old one
# already occupies - so only images that are no larger than the slot they land
# in can be used, and each has to carry the same pixel size as the slot.

function Read-U16([byte[]] $bytes, [int] $at) { return [BitConverter]::ToUInt16($bytes, $at) }
function Read-U32([byte[]] $bytes, [int] $at) { return [BitConverter]::ToUInt32($bytes, $at) }

function Get-PeInfo([byte[]] $bytes) {
    if ($bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) { throw 'not an executable: no MZ signature' }
    $peAt = [int](Read-U32 $bytes 0x3C)
    if ($bytes[$peAt] -ne 0x50 -or $bytes[$peAt + 1] -ne 0x45) { throw 'not an executable: no PE signature' }
    $coff = $peAt + 4
    $count = Read-U16 $bytes ($coff + 2)
    $optionalSize = Read-U16 $bytes ($coff + 16)
    $optional = $coff + 20
    $directories = $optional + 96
    if ((Read-U16 $bytes $optional) -eq 0x20B) { $directories = $optional + 112 }
    $resourceRva = Read-U32 $bytes ($directories + 16)
    $table = $optional + $optionalSize
    $sections = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $count; $i++) {
        $base = $table + $i * 40
        [void]$sections.Add(@{
            VirtualAddress = (Read-U32 $bytes ($base + 12))
            VirtualSize    = (Read-U32 $bytes ($base + 8))
            RawSize        = (Read-U32 $bytes ($base + 16))
            RawPointer     = (Read-U32 $bytes ($base + 20))
        })
    }
    return @{ Sections = $sections; ResourceRva = $resourceRva }
}

function Convert-RvaToOffset([byte[]] $bytes, $sections, [long] $rva) {
    foreach ($section in $sections) {
        $span = [Math]::Max([long]$section.VirtualSize, [long]$section.RawSize)
        if ($rva -ge $section.VirtualAddress -and $rva -lt ($section.VirtualAddress + $span)) {
            return [int]($section.RawPointer + ($rva - $section.VirtualAddress))
        }
    }
    throw ('an address in the executable lies outside every section: 0x' + $rva.ToString('x'))
}

function Get-ResourceEntries([byte[]] $bytes, [int] $at) {
    if ($at -lt 0 -or ($at + 16) -gt $bytes.Length) { throw 'a resource directory points outside the executable' }
    $named = Read-U16 $bytes ($at + 12)
    $ids = Read-U16 $bytes ($at + 14)
    # A real directory holds a handful of entries. Anything larger means the
    # offsets are being read from the wrong place, and walking it would take
    # forever instead of failing.
    if (($named + $ids) -gt 4096) { throw ('a resource directory claims ' + ($named + $ids) + ' entries, so the executable is not being read correctly') }
    $list = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt ($named + $ids); $i++) {
        $base = $at + 16 + $i * 8
        [void]$list.Add(@{ Name = (Read-U32 $bytes $base); Target = (Read-U32 $bytes ($base + 4)) })
    }
    return $list
}

function Get-ResourceLeaves([byte[]] $bytes, $sections, [int] $root, [int] $typeId) {
    $found = New-Object System.Collections.ArrayList
    foreach ($typeEntry in (Get-ResourceEntries $bytes $root)) {
        if ($typeEntry.Name -ne $typeId) { continue }
        if (($typeEntry.Target -band 0x80000000L) -eq 0) { continue }
        $level1 = $root + [int]($typeEntry.Target -band 0x7FFFFFFFL)
        foreach ($nameEntry in (Get-ResourceEntries $bytes $level1)) {
            if (($nameEntry.Target -band 0x80000000L) -eq 0) { continue }
            $level2 = $root + [int]($nameEntry.Target -band 0x7FFFFFFFL)
            foreach ($languageEntry in (Get-ResourceEntries $bytes $level2)) {
                if (($languageEntry.Target -band 0x80000000L) -ne 0) { continue }
                $leaf = $root + [int]$languageEntry.Target
                $rva = Read-U32 $bytes $leaf
                [void]$found.Add(@{
                    Name      = $nameEntry.Name
                    SizeField = $leaf + 4
                    Data      = (Convert-RvaToOffset $bytes $sections $rva)
                    Size      = (Read-U32 $bytes ($leaf + 4))
                })
            }
        }
    }
    return $found
}

function Get-IconEntries([byte[]] $bytes) {
    if ((Read-U16 $bytes 2) -ne 1) { throw 'the icon file is not an icon' }
    $count = Read-U16 $bytes 4
    $list = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $count; $i++) {
        $at = 6 + $i * 16
        $pixels = $bytes[$at]
        if ($pixels -eq 0) { $pixels = 256 }
        $size = [int](Read-U32 $bytes ($at + 8))
        $offset = [int](Read-U32 $bytes ($at + 12))
        [void]$list.Add(@{
            Pixels = $pixels
            Size   = $size
            Offset = $offset
            Png    = ($bytes[$offset] -eq 0x89 -and $bytes[$offset + 1] -eq 0x50)
        })
    }
    return $list
}

function Set-LauncherIcon([byte[]] $bytes, $sections, [int] $root, [byte[]] $icoBytes) {
    $icons = @(Get-IconEntries $icoBytes)
    $slots = @{}
    foreach ($image in (Get-ResourceLeaves $bytes $sections $root 3)) {
        $slots[[string]$image.Name] = $image
    }
    Say ('  ' + $icons.Count + ' replacement image(s) available')
    $groups = @(Get-ResourceLeaves $bytes $sections $root 14)
    if ($groups.Count -eq 0) { throw 'the executable has no icon group' }
    $replaced = 0
    $skipped = 0
    foreach ($group in $groups) {
        $base = [int]$group.Data
        $count = Read-U16 $bytes ($base + 4)
        for ($i = 0; $i -lt $count; $i++) {
            $entry = $base + 6 + $i * 14
            $pixels = $bytes[$entry]
            if ($pixels -eq 0) { $pixels = 256 }
            $iconId = Read-U16 $bytes ($entry + 12)
            $slot = $slots[[string]$iconId]
            if ($slot -eq $null) { $skipped = $skipped + 1; continue }
            $best = $null
            foreach ($icon in $icons) {
                if ($icon.Pixels -ne $pixels) { continue }
                if ($icon.Size -gt $slot.Size) { continue }
                if ($best -eq $null -or $icon.Size -lt $best.Size) { $best = $icon }
            }
            if ($best -eq $null) {
                Say ('    ' + $pixels + 'x' + $pixels + ': left alone, no replacement of that size fits')
                $skipped = $skipped + 1
                continue
            }
            if ($slot.Size -gt 4194304) {
                Say ('    ' + $pixels + 'x' + $pixels + ': left alone, its slot reports ' + $slot.Size + ' bytes')
                $skipped = $skipped + 1
                continue
            }
            Say ('    ' + $pixels + 'x' + $pixels + ': replacing ' + $best.Size + ' of ' + $slot.Size + ' bytes')
            for ($b = 0; $b -lt $best.Size; $b++) { $bytes[$slot.Data + $b] = $icoBytes[$best.Offset + $b] }
            for ($b = $best.Size; $b -lt $slot.Size; $b++) { $bytes[$slot.Data + $b] = 0 }
            # the length is recorded twice: on the resource, and on the entry
            # in the group that points at it
            $length = [BitConverter]::GetBytes([uint32]$best.Size)
            for ($b = 0; $b -lt 4; $b++) {
                $bytes[$slot.SizeField + $b] = $length[$b]
                $bytes[$entry + 8 + $b] = $length[$b]
            }
            $replaced = $replaced + 1
        }
    }
    return @{ Replaced = $replaced; Skipped = $skipped }
}


# The icon lives in the executable's resources, so replacing it means walking
# the resource section and writing into slots the old images already occupy.
# This is the one step that reads the executable's structure, and the one that
# failed on the user's machine, so it runs in its own process with a time
# limit: a stuck icon must never stop the archive from being produced.
function Invoke-IconReplacement([string] $exePath) {
    $iconPath = Join-Path $here 'Sa6i-Link-Icon.ico'
    if (-not (Test-Path -LiteralPath $iconPath)) {
        Say 'No Sa6i-Link-Icon.ico beside this script, so the icon is left as it was.'
        return
    }
    Say 'Replacing the icon in the executable'
    $icoBytes = [System.IO.File]::ReadAllBytes($iconPath)
    Say ('  icon file: ' + [Math]::Round($icoBytes.Length / 1024) + ' KB')
    $raw = [System.IO.File]::ReadAllBytes($exePath)
    Say ('  executable read: ' + [Math]::Round($raw.Length / 1MB, 1) + ' MB')
    $original = [byte[]]$raw.Clone()
    try {
        $info = Get-PeInfo $raw
        Say ('  executable parses: ' + $info.Sections.Count + ' sections')
        $root = Convert-RvaToOffset $raw $info.Sections $info.ResourceRva
        Say ('  resource section at byte ' + $root)
        $groupsBefore = @(Get-ResourceLeaves $raw $info.Sections $root 14)
        $imagesBefore = @(Get-ResourceLeaves $raw $info.Sections $root 3)
        Say ('  found ' + $groupsBefore.Count + ' icon group(s) and ' + $imagesBefore.Count + ' image(s)')
        $result = Set-LauncherIcon $raw $info.Sections $root $icoBytes
        $check = @(Get-ResourceLeaves $raw $info.Sections $root 14)
        if ($check.Count -lt 1) { throw 'the rewritten executable no longer has a readable icon group' }
        Say ('  writing ' + [Math]::Round($raw.Length / 1MB, 1) + ' MB back to disk (antivirus may hold this up)')
        [System.IO.File]::WriteAllBytes($exePath, $raw)
        Say '  written.'
        Say ('Replaced ' + $result.Replaced + ' icon image(s) with the Sa6i Link icon.')
        if ($result.Skipped -gt 0) {
            Say ('Left ' + $result.Skipped + ' image(s) alone: no replacement of that size fits the space they occupy.')
        }
    } catch {
        [System.IO.File]::WriteAllBytes($exePath, $original)
        Say ('Could not replace the icon: ' + $_.Exception.Message)
        Say 'The executable was put back exactly as it was before this step.'
        throw
    }
}

function Get-ExeFiles([string] $folder) {
    return (Get-ChildItem -LiteralPath $folder -Force | Where-Object {
        (-not $_.PSIsContainer) -and ($_.Extension -eq '.exe') -and ($_.Length -gt 1048576) -and ($_.Name -notlike '*.bak')
    })
}

try {
    Set-Content -Path $log -Value ('Sa6i Clean retarget log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean: point Sa6i Link at the debranded cleaner'
    Say ('script build ' + $scriptBuild)
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString() + ', ' + ([string]([IntPtr]::Size * 8)) + '-bit')
    Say ''

    # When started only to replace the icon, do that and stop. This is what
    # keeps the step isolated: it cannot fall through into the rest of the
    # script, which would start another copy of itself.
    if ($IconOnly) {
        if ([string]::IsNullOrEmpty($Desktop)) { throw '-IconOnly needs -Desktop with the executable to change.' }
        Say 'Icon step only.'
        Invoke-IconReplacement $Desktop
        Say 'Icon step finished.'
        exit 0
    }

    $cleanExe = Join-Path $here 'Sa6i Clean\Sa6i Clean Integration.exe'
    $cleanAsar = Join-Path $here 'Sa6i Clean\resources\app.asar'
    if (-not (Test-Path -LiteralPath $cleanExe)) { throw 'Sa6i Clean\Sa6i Clean Integration.exe was not found below this folder. Put these two retarget files in the candidate folder, the one that contains the "Sa6i Clean" folder.' }
    if (-not (Test-Path -LiteralPath $cleanAsar)) { throw 'Sa6i Clean\resources\app.asar was not found below this folder.' }

    # A function that returns byte[] hands back Object[] in Windows PowerShell,
    # so every digest that gets written back is cast explicitly.
    [byte[]] $newExe = Get-HashBytes $cleanExe
    [byte[]] $newAsar = Get-HashBytes $cleanAsar
    $newExeText = $script:latin.GetString($newExe)
    $newAsarText = $script:latin.GetString($newAsar)
    Say ('Cleaner executable SHA-256: ' + (ConvertTo-Hex $newExe))
    Say ('Cleaner bundle SHA-256:     ' + (ConvertTo-Hex $newAsar))
    Say ''

    # Find the Sa6i Link executable by its content. Its name differs between
    # builds, and a wrong guess must not be reported as a missing file.
    Say 'Looking for the Sa6i Link executable...'
    $search = New-Object System.Collections.ArrayList
    if (-not [string]::IsNullOrEmpty($Desktop)) {
        if (-not (Test-Path -LiteralPath $Desktop)) { throw ('The path given with -Desktop does not exist: ' + $Desktop) }
        [void]$search.Add((Get-Item -LiteralPath $Desktop))
    }
    foreach ($file in (Get-ExeFiles $here)) { [void]$search.Add($file) }
    if ($search.Count -eq 0) {
        foreach ($folder in (Get-ChildItem -LiteralPath $here -Force | Where-Object { $_.PSIsContainer })) {
            foreach ($file in (Get-ExeFiles $folder.FullName)) { [void]$search.Add($file) }
        }
    }
    if ($search.Count -eq 0) {
        $backups = @(Get-ChildItem -LiteralPath $here -Force | Where-Object { (-not $_.PSIsContainer) -and ($_.Name -like '*.bak') })
        if ($backups.Count -gt 0) {
            $names = ''
            foreach ($backup in $backups) { $names = $names + '  ' + $backup.Name + ' (' + [Math]::Round($backup.Length / 1MB, 1) + ' MB)' + [Environment]::NewLine }
            throw ('There is no executable in ' + $here + ', but these backups are here:' + [Environment]::NewLine + $names + 'If the executable was deleted, rename the .bak back and run this again.')
        }
        throw ('No executable larger than 1 MB was found in ' + $here + '. Sa6i Link may live somewhere else; tell me the full path of its .exe and I will point this at it.')
    }

    $target = $null
    $bytes = $null
    $text = $null
    $chosen = $null
    $already = $false
    foreach ($file in $search) {
        Say ('  checking ' + $file.FullName + ' (' + [Math]::Round($file.Length / 1MB, 1) + ' MB)')
        $candidateBytes = [System.IO.File]::ReadAllBytes($file.FullName)
        $candidateText = $script:latin.GetString($candidateBytes)
        if ((Count-Of $candidateText $newExeText) -eq 1 -and (Count-Of $candidateText $newAsarText) -eq 1) {
            $target = $file
            $bytes = $candidateBytes
            $text = $candidateText
            $already = $true
            break
        }
        foreach ($pair in $pairs) {
            $exeCount = Count-Of $candidateText ($script:latin.GetString([byte[]](ConvertFrom-Hex $pair[0])))
            $asarCount = Count-Of $candidateText ($script:latin.GetString([byte[]](ConvertFrom-Hex $pair[1])))
            if ($exeCount -eq 1 -and $asarCount -eq 1) {
                $target = $file
                $bytes = $candidateBytes
                $text = $candidateText
                $chosen = $pair
                break
            }
        }
        if ($target -ne $null) { break }
        $candidateBytes = $null
        $candidateText = $null
        Say '    no cleaner digests in this one'
    }

    if ($target -eq $null) {
        Say ''
        Say 'No Sa6i Link executable here carries the pins I know. Files checked:'
        foreach ($file in $search) { Say ('  ' + $file.FullName + '  ' + [Math]::Round($file.Length / 1MB, 1) + ' MB') }
        throw 'This Sa6i Link build verifies its cleaner some other way. Nothing was changed.'
    }

    Say ''
    Say ('Sa6i Link executable: ' + $target.FullName)
    Say ('  name: ' + $target.Name + ', ' + [Math]::Round($target.Length / 1MB, 1) + ' MB')
    Say ''

    # Both the digest swap and the rename write to this file, so establish up
    # front that it can be written, instead of failing halfway through.
    if (-not (Test-Writable $target.FullName)) {
        if (-not (Stop-Launcher $target.FullName)) {
            throw 'Sa6i Link is still running, so its executable cannot be written. It is probably minimised to the notification area: right-click its icon there, choose Quit, then run this again. Nothing was changed.'
        }
    }
    $Desktop = $target.FullName

    if ($already) {
        Say 'It already accepts these two files. No digest change needed.'
    } else {
        if (-not (Test-Path -LiteralPath ($Desktop + '.bak'))) {
            Copy-Item -LiteralPath $Desktop -Destination ($Desktop + '.bak') -Force
            Say 'Backed up the executable as .bak.'
        } else {
            Say 'Kept the existing executable backup.'
        }

        $pinnedExe = $script:latin.GetString([byte[]](ConvertFrom-Hex $chosen[0]))
        $pinnedAsar = $script:latin.GetString([byte[]](ConvertFrom-Hex $chosen[1]))
        $offset = $text.IndexOf($pinnedExe, 0, [System.StringComparison]::Ordinal)
        for ($i = 0; $i -lt $newExe.Length; $i++) { $bytes[$offset + $i] = $newExe[$i] }
        $offset = $text.IndexOf($pinnedAsar, 0, [System.StringComparison]::Ordinal)
        for ($i = 0; $i -lt $newAsar.Length; $i++) { $bytes[$offset + $i] = $newAsar[$i] }
        $text = $null
        $pinnedExe = $null
        $pinnedAsar = $null

        [System.IO.File]::WriteAllBytes($Desktop, $bytes)
        $bytes = $null

        if ((Count-InFile $Desktop $newExeText) -ne 1 -or (Count-InFile $Desktop $newAsarText) -ne 1) {
            throw 'The new digests are not in the executable exactly once. Restore the .bak file.'
        }
        Say 'Done. Sa6i Link will now start the debranded cleaner from its Sa6i Clean tab.'
    }


    # Sa6i Link itself is a rebranded build of another product, and its own
    # executable still carries that product's name: the file name, and the
    # strings Windows shows in Task Manager and in the file's Details tab.
    # Those strings are UTF-16 in a fixed field, so a shorter name replaces one
    # in place. Only the UTF-16 form is touched: the UTF-8 bytes in the same
    # file include configuration the application parses, and a NUL-truncated
    # config value would stop it from starting.
    Say ''
    Say 'Branding the Sa6i Link executable'
    $launcherPath = $Desktop
    $raw = [System.IO.File]::ReadAllBytes($launcherPath)
    $wide = $script:latin.GetString($raw)
    $oldName = [System.Text.Encoding]::Unicode.GetBytes('NectarLink')
    $newName = [System.Text.Encoding]::Unicode.GetBytes('Sa6i Link')
    $pattern = $script:latin.GetString($oldName)
    $replacement = New-Object byte[] $oldName.Length
    for ($i = 0; $i -lt $newName.Length; $i++) { $replacement[$i] = $newName[$i] }
    $strings = 0
    $from = 0
    while ($true) {
        $at = $wide.IndexOf($pattern, $from, [System.StringComparison]::Ordinal)
        if ($at -lt 0) { break }
        for ($i = 0; $i -lt $replacement.Length; $i++) { $raw[$at + $i] = $replacement[$i] }
        $strings = $strings + 1
        $from = $at + $oldName.Length
    }
    if ($strings -gt 0) {
        [System.IO.File]::WriteAllBytes($launcherPath, $raw)
        Say ('Renamed ' + $strings + ' product-name string(s) in the executable.')
    } else {
        Say 'No product-name strings left to rename in the executable.'
    }
    $raw = $null
    $wide = $null

    $oldFile = Split-Path -Leaf $launcherPath
    $newFile = 'Sa6i Link.exe'
    if ($oldFile -ne $newFile) {
        $newPath = Join-Path (Split-Path -Parent $launcherPath) $newFile
        if (Test-Path -LiteralPath $newPath) {
            Say ('A file called ' + $newFile + ' already exists, so the executable keeps its name: ' + $oldFile)
        } else {
            [System.IO.File]::Move($launcherPath, $newPath)
            Say ('Renamed the executable: ' + $oldFile + ' -> ' + $newFile)
            $launcherPath = $newPath
            $Desktop = $newPath
            # Any batch file that starts it by name has to learn the new name.
            $folders = @($here, (Split-Path -Parent $here))
            foreach ($folder in $folders) {
                foreach ($cmd in (Get-ChildItem -LiteralPath $folder -Force | Where-Object { (-not $_.PSIsContainer) -and ($_.Extension -eq '.cmd') })) {
                    $cbytes = [System.IO.File]::ReadAllBytes($cmd.FullName)
                    $ctext = $script:latin.GetString($cbytes)
                    if ($ctext.IndexOf($oldFile, [System.StringComparison]::Ordinal) -ge 0) {
                        $ctext = $ctext.Replace($oldFile, $newFile)
                        [System.IO.File]::WriteAllBytes($cmd.FullName, $script:latin.GetBytes($ctext))
                        Say ('Updated ' + $cmd.Name + ' to start ' + $newFile)
                    }
                }
            }
        }
    } else {
        Say ('The executable is already called ' + $newFile + '.')
    }

    Say ''


    # --- the icon, in a child process with a time limit
    if ($NoIcon) {
        Say ''
        Say 'Icon replacement skipped (-NoIcon was given).'
    } elseif (-not (Test-Path -LiteralPath (Join-Path $here 'Sa6i-Link-Icon.ico'))) {
        Say ''
        Say 'No Sa6i-Link-Icon.ico beside this script, so the icon is left as it was.'
    } else {
        Say ''
        $self = $MyInvocation.MyCommand.Path
        $tempCmd = Join-Path $env:TEMP ('sa6i-icon-' + [Guid]::NewGuid().ToString('N') + '.cmd')
        $inner = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $self + '" -IconOnly -NoZip -Desktop "' + $launcherPath + '"'
        [System.IO.File]::WriteAllText($tempCmd, '@echo off' + "`r`n" + $inner + "`r`n")
        Say 'Icon replacement runs on its own, with a 4 minute limit.'
        $child = $null
        try {
            $child = Start-Process -FilePath $tempCmd -NoNewWindow -PassThru
        } catch {
            Say ('Could not start the icon step: ' + $_.Exception.Message)
        }
        if ($child -ne $null) {
            $waited = 0
            while (-not $child.HasExited -and $waited -lt 240) {
                Start-Sleep -Seconds 2
                $waited = $waited + 2
                if (($waited % 30) -eq 0) { Say ('  still working (' + $waited + ' s)') }
            }
            if (-not $child.HasExited) {
                try { $child.Kill() } catch { }
                Say 'The icon step did not finish within 4 minutes and was stopped.'
                Say 'The executable is untouched by it; continuing without the icon.'
            } else {
                Say ('Icon step exit code: ' + $child.ExitCode)
            }
            if (Test-Path -LiteralPath $tempCmd) { [System.IO.File]::Delete($tempCmd) }
        }
    }

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
            $zipSize = (New-Object System.IO.FileInfo($zipPath)).Length
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
