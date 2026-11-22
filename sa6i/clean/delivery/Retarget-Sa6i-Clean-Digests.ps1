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
    [switch] $NoZip
)

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'retarget-log.txt'
$script:latin = [System.Text.Encoding]::GetEncoding(28591)

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

function Get-ExeFiles([string] $folder) {
    return (Get-ChildItem -LiteralPath $folder -Force | Where-Object {
        (-not $_.PSIsContainer) -and ($_.Extension -eq '.exe') -and ($_.Length -gt 1048576) -and ($_.Name -notlike '*.bak')
    })
}

try {
    Set-Content -Path $log -Value ('Sa6i Clean retarget log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean: point Sa6i Link at the debranded cleaner'
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString() + ', ' + ([string]([IntPtr]::Size * 8)) + '-bit')
    Say ''

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
        Say 'The executable is already called ' + $newFile + '.'
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
