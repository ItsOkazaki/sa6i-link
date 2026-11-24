# SPDX-License-Identifier: GPL-3.0-or-later
# Install the debranded Sa6i Clean bundle into an installed cleaner folder.
#
# Electron checks that resources\app.asar matches a hash stored inside
# "Sa6i Clean Integration.exe". Replacing the bundle therefore requires
# updating that stored hash, which is what this script does. It also renames
# the product name in the executable's own file properties, so Windows stops
# describing it as the original product. The hash is read from the bundle that
# is actually installed, so any cleaner build works, not just one version.
# Both files are backed up first, so the folder can be put back exactly.
#
# Written for Windows PowerShell 2.0, which is what Windows 7 ships: no .NET 4
# types and no IDisposable.Dispose() calls.
#
# Put this file, "Apply Sa6i Clean Patch.cmd", README.txt and app.asar in the
# "Sa6i Clean" folder (beside "Sa6i Clean Integration.exe"), then run the .cmd.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'patch-log.txt'
$newAsar = Join-Path $here 'app.asar'
$exe = Join-Path $here 'Sa6i Clean Integration.exe'
$oldAsar = Join-Path $here 'resources\app.asar'
$expectedNew = '653f05e211811d173cd943c6fc44aecb6c9318a3091010abafcb4abca87e5a0a'
# Bundles shipped by earlier versions of this package, so the failure can say
# what happened instead of just quoting a hash.
$olderBundles = @('8e6ee85e794723de784eb1adc1baedf28a612f968e7b88970297f91053e37fb9')

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

# ASCII and Latin-1 decoding both map one byte to one character, so a
# character index in this text is a byte offset in the file.

try {
    Set-Content -Path $log -Value ('Sa6i Clean patch log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Clean: install the debranded bundle'
    Say ''
    Say ('Folder: ' + $here)
    Say ('PowerShell ' + $PSVersionTable.PSVersion.ToString() + ', ' + ([string]([IntPtr]::Size * 8)) + '-bit')
    Say ''

    if (-not (Test-Path -LiteralPath $newAsar)) { throw 'app.asar is not next to this script. Copy all four files of the package into this folder.' }
    if (-not (Test-Path -LiteralPath $exe)) { throw '"Sa6i Clean Integration.exe" is not next to this script.' }
    if (-not (Test-Path -LiteralPath $oldAsar)) { throw 'resources\app.asar is not next to this script.' }

    $newHash = Get-HeaderHash $newAsar
    if ($newHash -ne $expectedNew) {
        if ($olderBundles -contains $newHash) {
            throw ('The app.asar in this folder is the previous debranded bundle (' + $newHash + '), not this one. Copy app.asar from "1 - into the Sa6i Clean folder" over it - it must be 1,420,960 bytes - and run this again. Nothing was changed.')
        }
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
        $position = $text.IndexOf($oldHash, [System.StringComparison]::Ordinal)
        if ($position -lt 0) {
            throw ('The executable does not store the hash of the installed bundle (' + $oldHash + '). Nothing was changed.')
        }
        if ($text.IndexOf($oldHash, $position + $oldHash.Length, [System.StringComparison]::Ordinal) -ge 0) {
            throw 'The executable stores that hash more than once. Nothing was changed.'
        }
        Say ('Found the stored hash at byte ' + $position + '.')

        # Keep the oldest backup: re-running this after an earlier patch must
        # not replace the pristine original with an already patched file.
        if (-not (Test-Path -LiteralPath ($exe + '.bak'))) {
            Copy-Item -LiteralPath $exe -Destination ($exe + '.bak') -Force
            Say 'Backed up the executable as .bak.'
        } else {
            Say 'Kept the existing executable backup; it is the older original.'
        }
        if (-not (Test-Path -LiteralPath ($oldAsar + '.bak'))) {
            Copy-Item -LiteralPath $oldAsar -Destination ($oldAsar + '.bak') -Force
            Say 'Backed up the old bundle as .bak.'
        } else {
            Say 'Kept the existing bundle backup; it is the older original.'
        }

        $replacement = [System.Text.Encoding]::ASCII.GetBytes($newHash)
        [Array]::Copy($replacement, 0, $bytes, $position, $replacement.Length)

        # The executable's own file properties still name the original product;
        # that is the "description" Windows shows in Task Manager and in the
        # file's Details tab. Windows stores those strings as UTF-16 in a
        # fixed-size field, so a shorter name replaces it in place. Only values
        # that end where "Cleanly" ends are touched: anything with more text
        # after it (a file name, say) is reported instead of truncated.
        $latin = [System.Text.Encoding]::GetEncoding(28591)
        $wide = $latin.GetString($bytes)
        $pattern = $latin.GetString([System.Text.Encoding]::Unicode.GetBytes('Cleanly'))
        $replacementBytes = New-Object byte[] ($pattern.Length)
        $short = [System.Text.Encoding]::Unicode.GetBytes('Sa6i')
        [Array]::Copy($short, 0, $replacementBytes, 0, $short.Length)
        $renamed = 0
        $kept = 0
        $from = 0
        while ($true) {
            $at = $wide.IndexOf($pattern, $from, [System.StringComparison]::Ordinal)
            if ($at -lt 0) { break }
            $after = $at + $pattern.Length
            if ($after + 1 -lt $wide.Length -and $wide[$after] -eq [char]0 -and $wide[$after + 1] -eq [char]0) {
                [Array]::Copy($replacementBytes, 0, $bytes, $at, $replacementBytes.Length)
                $renamed = $renamed + 1
            } else {
                $kept = $kept + 1
            }
            $from = $after
        }
        $wide = $null
        $text = $null

        [System.IO.File]::WriteAllBytes($exe, $bytes)
        $bytes = $null
        Copy-Item -LiteralPath $newAsar -Destination $oldAsar -Force

        $after = Get-HeaderHash $oldAsar
        if ($after -ne $newHash) { throw 'The debranded bundle did not install correctly.' }
        Say ''
        Say 'Bundle installed. The cleaner no longer has Tip or Feedback.'
        Say ('Renamed ' + $renamed + ' product-name field(s) in the executable.')
        if ($kept -gt 0) {
            Say ('Left ' + $kept + ' field(s) alone because more text followed the name.')
        }
        Say ''
        Say 'Next: in the candidate folder, one level up, run "Retarget Sa6i Clean.cmd".'
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
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    Say 'Nothing was changed unless the log above says otherwise.'
    exit 1
}
