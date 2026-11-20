# SPDX-License-Identifier: GPL-3.0-or-later
# A disposable hosted-Windows test of the real Qt app with an INERT synthetic
# child, not the actual cleaner. Never run this against a real installation.
param([Parameter(Mandatory=$true)][string]$AppDir,
      [Parameter(Mandatory=$true)][string]$FixtureDir)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class Sa6iSmokeWin32 {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left, top, right, bottom; }
    public delegate bool EnumProc(IntPtr hwnd, IntPtr value);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint message, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr v);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    public static IntPtr ChildForProcess(IntPtr parent, uint pid) {
        IntPtr found = IntPtr.Zero;
        EnumProc cb = (h, v) => { uint actual; GetWindowThreadProcessId(h, out actual);
            if (actual == pid) { found = h; return false; } return true; };
        EnumChildWindows(parent, cb, IntPtr.Zero);
        return found;
    }
    public static void Click(IntPtr h, int x, int y) {
        IntPtr pos = new IntPtr((y << 16) | (x & 65535));
        PostMessage(h, 0x200, IntPtr.Zero, pos);
        PostMessage(h, 0x201, new IntPtr(1), pos);
        PostMessage(h, 0x202, IntPtr.Zero, pos);
    }
}
'@
function Wait-Until([scriptblock]$Condition, [int]$Seconds) {
    $until = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $until) {
        $value = & $Condition
        if ($value) { return $value }
        Start-Sleep -Milliseconds 100
    }
    return $null
}
$exe = (Resolve-Path (Join-Path $AppDir 'synthetic-test-desktop.exe')).Path
$fixture = (Resolve-Path $FixtureDir).Path
$data = Join-Path $env:RUNNER_TEMP 'sa6i-full-ui-synthetic-data'
New-Item -ItemType Directory -Path $data | Out-Null
$stderr = Join-Path $env:RUNNER_TEMP 'sa6i-full-ui-synthetic-stderr.txt'
$env:NECTARLINK_NO_ADB = '1'
$env:QT_QUICK_BACKEND = 'software'
$env:QT_SCALE_FACTOR = '1'
$app = $null
try {
    $app = Start-Process $exe -ArgumentList '--data-dir', "`"$data`"", "`"--sa6i-clean-test-dir=$fixture`"" -RedirectStandardError $stderr -PassThru
    $null = $app.Handle
    $window = Wait-Until { $app.Refresh(); if (!$app.HasExited -and $app.MainWindowHandle -ne [IntPtr]::Zero) { $app.MainWindowHandle } } 40
    if (!$window) { throw 'Main window did not appear' }
    # Let the main QML window finish its initial rendering and layout.
    Start-Sleep -Seconds 4
    $rect = New-Object Sa6iSmokeWin32+RECT
    if (![Sa6iSmokeWin32]::GetClientRect($window, [ref]$rect)) { throw 'Could not get client bounds' }
    $entryX = $rect.right - 216
    if ($entryX -lt 0) { throw 'Window too narrow for cleaner button' }
    [Sa6iSmokeWin32]::Click($window, $entryX, 26)
    # Electron can have several same-name subprocesses; only use the one
    # directly launched by this app as the tracked browser process.
    $childProc = Wait-Until {
        $match = Get-CimInstance Win32_Process -Filter "Name='Sa6i Clean Integration.exe' AND ParentProcessId=$($app.Id)" | Select-Object -First 1
        if ($match) { Get-Process -Id $match.ProcessId -ErrorAction SilentlyContinue }
    } 35
    if (!$childProc) { throw 'The synthetic child did not start after clicking Sa6i Clean' }
    $child = Wait-Until { $h = [Sa6iSmokeWin32]::ChildForProcess($window, [uint32]$childProc.Id); if ($h -ne [IntPtr]::Zero -and [Sa6iSmokeWin32]::IsWindowVisible($h)) { $h } } 20
    if (!$child) { throw 'Synthetic child did not become a visible child of the app window' }
    Write-Host '::notice::PASS: actual Qt app opened a synthetic child in the same window'
    [Sa6iSmokeWin32]::Click($window, 50, 80)
    if (!(Wait-Until { if (![Sa6iSmokeWin32]::IsWindowVisible($child)) { $true } } 8)) { throw 'Back did not hide the synthetic child' }
    [Sa6iSmokeWin32]::Click($window, $entryX, 26)
    if (!(Wait-Until { if ([Sa6iSmokeWin32]::IsWindowVisible($child)) { $true } } 8)) { throw 'Reopening did not show the same synthetic child' }
    Write-Host '::notice::PASS: Back and re-open hide and show the same child'
    $quit = Start-Process $exe -ArgumentList '--data-dir', "`"$data`"", '--quit' -PassThru
    $null = $quit.Handle
    if (!$quit.WaitForExit(15000) -or $quit.ExitCode -ne 0) { throw 'Quit request process failed' }
    if (!$app.WaitForExit(30000)) { throw 'Main application did not close after quit request' }
    if ($app.ExitCode -ne 0) { throw "Main application failed on exit: $($app.ExitCode)" }
    $childProc.Refresh()
    if (!$childProc.HasExited -and !$childProc.WaitForExit(5000)) { throw 'Synthetic child outlived app quit' }
    Write-Host '::notice::PASS: quit closed the child and the app'
} catch {
    Write-Host "::error::Full window smoke failed: $_"
    foreach ($log in @(Get-ChildItem $data -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.(log|txt)$' })) {
        Get-Content $log.FullName -Tail 8 -ErrorAction SilentlyContinue | ForEach-Object { if ($_) { Write-Host "::error::LOG $_" } }
    }
    throw
} finally {
    # These names belong solely to the synthetic fixture and disposable CI app.
    Get-Process -Name 'Sa6i Clean Integration' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if ($app) { $app.Refresh(); if (!$app.HasExited) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue } }
}
