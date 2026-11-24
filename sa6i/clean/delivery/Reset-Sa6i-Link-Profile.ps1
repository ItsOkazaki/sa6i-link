# SPDX-License-Identifier: GPL-3.0-or-later
# Start Sa6i Link with a fresh profile, without touching the old one.
#
# The application keeps a device key in its profile folder, encrypted by Windows
# with material derived from the application itself. The profile in use was
# created before this executable's product name changed, so the key can no
# longer be unlocked:
#
#   storage error: cannot unlock device key: Donnees non valides. (0x8007000B)
#
# Moving that folder is not possible while the application is running - it holds
# its own profile open - so this changes the profile path in the batch file
# instead. The old profile stays exactly where it is, and nothing needs closing.
#
# Put this file and "Reset Sa6i Link Profile.cmd" in the candidate folder, then
# run the .cmd.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'reset-log.txt'

function Say([string] $text) {
    Write-Host $text
    Add-Content -Path $log -Value $text
}

try {
    Set-Content -Path $log -Value ('Sa6i Link profile reset ' + (Get-Date).ToString('s'))
    Say 'Sa6i Link: start with a fresh profile'
    Say ''
    Say ('Folder: ' + $here)
    Say ''

    if ([string]::IsNullOrEmpty($env:LOCALAPPDATA)) { throw 'LOCALAPPDATA is not set, so the profile folder cannot be found.' }

    $batch = $null
    foreach ($folder in @($here, (Split-Path -Parent $here))) {
        if ($batch -ne $null) { break }
        foreach ($file in (Get-ChildItem -LiteralPath $folder -Force | Where-Object {
                    (-not $_.PSIsContainer) -and ($_.Extension -eq '.cmd') -and ($_.Name -like 'Start*')
                })) {
            if ($batch -eq $null) { $batch = $file }
        }
    }
    if ($batch -eq $null) {
        throw 'No "Start ... .cmd" was found here or one folder up. Put this file beside the batch file that starts Sa6i Link.'
    }
    Say ('Batch file: ' + $batch.FullName)

    $lines = [System.IO.File]::ReadAllLines($batch.FullName)
    $index = -1
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match '^set "SA6I_DATA=(.*)"') { $index = $i }
    }
    if ($index -lt 0) {
        throw ('The batch file does not set SA6I_DATA, so the profile location is not something this script can change. Its lines are:' + [Environment]::NewLine + ($lines -join [Environment]::NewLine))
    }

    $current = $matches[1]
    Say ('Profile now: ' + $current)

    # A new name for a new profile: the old folder is left alone, so this works
    # even while the application is open.
    $base = $current
    if ($base -match '-p[0-9]+$') { $base = $base.Substring(0, $base.Length - 3) }
    $choice = $null
    for ($n = 2; $n -lt 40; $n++) {
        $candidate = $base + '-p' + $n
        $expanded = $candidate.Replace('%LOCALAPPDATA%', $env:LOCALAPPDATA)
        if (-not (Test-Path -LiteralPath $expanded)) { $choice = $candidate; break }
    }
    if ($choice -eq $null) { throw 'Every candidate profile name is already in use; nothing was changed.' }

    $replacement = 'set "SA6I_DATA=' + $choice + '"'
    Say ('Will use:  ' + $choice)
    Say ('  that is: ' + $choice.Replace('%LOCALAPPDATA%', $env:LOCALAPPDATA))

    if (-not (Test-Path -LiteralPath ($batch.FullName + '.bak'))) {
        Copy-Item -LiteralPath $batch.FullName -Destination ($batch.FullName + '.bak') -Force
        Say ('Backed up the batch file as: ' + $batch.Name + '.bak')
    }

    $lines[$index] = $replacement
    [System.IO.File]::WriteAllLines($batch.FullName, $lines)
    Say 'Batch file updated. The old profile is untouched and can be deleted later.'

    Say ''
    Say ('Starting ' + $batch.Name + ' ...')
    Start-Process -FilePath $batch.FullName -WindowStyle Hidden
    Say 'The application should come up on a first-run screen; pair the phone again.'
    Say ''
    Say 'If the same storage error appears with the new profile, the executable is'
    Say 'the problem rather than the profile: tell me, and I will ship a build that'
    Say 'skips the product-name rewrite.'
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    Say 'The profile and the batch file are unchanged unless the log says otherwise.'
    exit 1
}
