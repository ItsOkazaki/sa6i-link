# Start Sa6i Link with a fresh profile.
#
# The application keeps a device key in its profile folder, encrypted by Windows
# with material derived from the application itself. The profile in use was
# created before this executable's product name changed, so the key can no
# longer be unlocked:
#
#   storage error: cannot unlock device key: Donnees non valides. (0x8007000B)
#
# A new profile makes the application create a new key. The old profile is not
# deleted: it is renamed with a timestamp, so anything in it can still be
# recovered by hand.
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

    # The batch file is where the profile location is defined; read it rather
    # than hard-coding a path that could drift.
    $batch = $null
    foreach ($folder in @($here, (Split-Path -Parent $here))) {
        if ($batch -ne $null) { break }
        foreach ($file in (Get-ChildItem -LiteralPath $folder -Force | Where-Object {
                    (-not $_.PSIsContainer) -and ($_.Extension -eq '.cmd') -and ($_.Name -like 'Start*')
                })) {
            if ($batch -eq $null) { $batch = $file }
        }
    }

    $dataDir = $null
    if ($batch -ne $null) {
        foreach ($line in [System.IO.File]::ReadAllLines($batch.FullName)) {
            if ($line -match 'SA6I_DATA=(.*)"') {
                $dataDir = $matches[1]
            }
        }
    }
    if ([string]::IsNullOrEmpty($dataDir)) {
        $dataDir = Join-Path $env:LOCALAPPDATA 'Sa6i-Link-Candidate-46ed96159a09abaa958e0c99'
        Say 'No SA6I_DATA found in the batch file; using the standard candidate profile.'
    }
    $dataDir = $dataDir.Replace('%LOCALAPPDATA%', $env:LOCALAPPDATA)
    Say ('Profile: ' + $dataDir)

    if (Test-Path -LiteralPath $dataDir) {
        $files = @(Get-ChildItem -LiteralPath $dataDir -Recurse -Force | Where-Object { -not $_.PSIsContainer })
        $total = 0
        foreach ($file in $files) { $total = $total + $file.Length }
        Say ('  holds ' + $files.Count + ' file(s), ' + [Math]::Round($total / 1KB, 1) + ' KB')
        $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
        $moved = $dataDir + '.old-' + $stamp
        [System.IO.Directory]::Move($dataDir, $moved)
        Say ('  moved aside to: ' + $moved)
        Say '  Nothing was deleted.'
    } else {
        Say '  it does not exist, so there is nothing to move aside.'
    }

    Say ''
    if ($batch -eq $null) {
        Say 'No batch file found, so start Sa6i Link yourself with the shortcut.'
    } else {
        Say ('Starting ' + $batch.Name + ' ...')
        Start-Process -FilePath $batch.FullName -WindowStyle Hidden
        Say 'The application should come up on a first-run screen; pair the phone again.'
    }
    Say ''
    Say 'If the same storage error comes back with the new profile, tell me: at that'
    Say 'point the executable itself is the problem, not the profile, and the fix is'
    Say 'to restore the backup executable and re-run the branding in a smaller dose.'
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    Say 'Nothing was deleted; the profile is either in place or renamed.'
    exit 1
}
