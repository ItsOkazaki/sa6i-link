# Make a desktop shortcut that starts Sa6i Link the way the batch file does.
#
# The batch file starts the application correctly, but a .cmd is not a launcher
# anyone wants on their desktop: it has no icon of its own and it leaves a
# console window behind. This creates a shortcut that runs that same batch file
# minimised, wearing the application's icon.
#
# It also copies the batch file's contents into shortcut-log.txt. That is the
# one piece of this setup nobody has been able to see, and with it the batch
# file can probably be removed altogether.
#
# Put this file and "Make Sa6i Link Shortcut.cmd" in the candidate folder (the
# one holding the Sa6i Link executable), then run the .cmd.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here 'shortcut-log.txt'

function Say([string] $text) {
    Write-Host $text
    Add-Content -Path $log -Value $text
}

try {
    Set-Content -Path $log -Value ('Sa6i Link shortcut log ' + (Get-Date).ToString('s'))
    Say 'Sa6i Link: make a shortcut that works'
    Say ''
    Say ('Folder: ' + $here)
    Say ''

    # The batch file that is known to start the application, here or one level up.
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
    Say ''
    Say 'Its contents, kept here so the batch file can be removed later:'
    foreach ($line in [System.IO.File]::ReadAllLines($batch.FullName)) {
        Say ('  | ' + $line)
    }
    Say ''

    # The application icon comes from the executable.
    $exe = $null
    foreach ($file in (Get-ChildItem -LiteralPath $here -Force | Where-Object {
                (-not $_.PSIsContainer) -and ($_.Extension -eq '.exe') -and ($_.Length -gt 1048576)
            })) {
        if ($exe -eq $null) { $exe = $file }
    }
    if ($exe -eq $null) {
        Say 'No executable here for the icon; the shortcut will use the default one.'
    } else {
        Say ('Icon from: ' + $exe.Name)
    }

    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $places = @($desktop, $here)
    $made = 0
    foreach ($place in $places) {
        if ([string]::IsNullOrEmpty($place)) { continue }
        $path = Join-Path $place 'Sa6i Link.lnk'
        if ((Test-Path -LiteralPath $path) -and $place -eq $here) { continue }
        $shortcut = $shell.CreateShortcut($path)
        $shortcut.TargetPath = $batch.FullName
        $shortcut.WorkingDirectory = $batch.DirectoryName
        if ($exe -ne $null) { $shortcut.IconLocation = $exe.FullName + ',0' }
        # 7 = minimised, so the console window does not sit over the application
        $shortcut.WindowStyle = 7
        $shortcut.Description = 'Sa6i Link'
        $shortcut.Save()
        Say ('Created ' + $path)
        $made = $made + 1
    }
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)

    Say ''
    if ($made -eq 0) {
        throw 'No shortcut could be created.'
    }
    Say 'Done. "Sa6i Link" on the Desktop starts the application; right-click it to pin it.'
    Say ''
    Say 'Please send me the | lines above, or shortcut-log.txt: with the batch file''s'
    Say 'contents I can usually make the executable start on its own, and the batch'
    Say 'file can go away.'
} catch {
    Say ''
    Say ('ERROR: ' + $_.Exception.Message)
    exit 1
}
