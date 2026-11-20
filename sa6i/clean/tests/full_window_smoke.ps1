# SPDX-License-Identifier: GPL-3.0-or-later
# A disposable hosted-Windows test of the real Qt app with an INERT synthetic
# child, not the actual cleaner. Never run this against a real installation.
param([Parameter(Mandatory=$true)][string]$AppDir,
      [Parameter(Mandatory=$true)][string]$FixtureDir,
      [switch]$VerifyElectronProfile,
      [switch]$IntegratedHeader,
      [switch]$ClippingContainer,
      [switch]$ExpectHostTheme,
      [switch]$ExpectSoftwareFlag,
      [switch]$PixelCheck,
      [double]$Scale = 1.0)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class Sa6iSmokeWin32 {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left, top, right, bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x, y; }
    public delegate bool EnumProc(IntPtr hwnd, IntPtr value);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] public static extern IntPtr ChildWindowFromPointEx(IntPtr h, POINT p, uint flags);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint message, IntPtr wp, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr v);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] public static extern uint GetPixel(IntPtr dc, int x, int y);
    public static uint ScreenPixel(int x, int y) {
        IntPtr dc = GetDC(IntPtr.Zero);
        if (dc == IntPtr.Zero) return 0xffffffff;
        try { return GetPixel(dc, x, y); } finally { ReleaseDC(IntPtr.Zero, dc); }
    }
    [DllImport("user32.dll", EntryPoint="GetWindowLongW")] public static extern int GetWindowLong(IntPtr h, int index);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern uint GetLongPathName(string input, StringBuilder output, uint size);
    public static string LongPath(string input) {
        var output = new StringBuilder(32768);
        uint length = GetLongPathName(input, output, (uint)output.Capacity);
        if (length == 0 || length >= output.Capacity) throw new System.ComponentModel.Win32Exception();
        return output.ToString();
    }
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
function Confirm-SyntheticProfile([int]$ProcessId) {
    $info = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId"
    if (!$info) { throw 'Synthetic Electron process not found' }
    $pathMatch = [regex]::Match($info.CommandLine, '--user-data-dir=([^"\r\n]+)')
    if (!$pathMatch.Success) { throw 'No explicit Electron profile argument' }
    $profile = [System.IO.Path]::GetFullPath($pathMatch.Groups[1].Value)
    $parent = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (!$profile.StartsWith($parent, [StringComparison]::OrdinalIgnoreCase) -or
        [System.IO.Path]::GetFileName($profile) -notmatch '^Sa6i-Clean-HostTest-\d+-\d+$') { throw 'Unexpected synthetic profile location' }
    $marker = Join-Path $profile 'synthetic-profile-path.txt'
    if (!(Wait-Until { if (Test-Path $marker) { $true } } 10)) { throw 'Synthetic Electron did not create its profile marker' }
    $observed = [string](Get-Content $marker -Raw)
    # Windows may return an 8.3 alias such as RUNNER~1 from Electron.
    if (![string]::Equals([Sa6iSmokeWin32]::LongPath($observed), [Sa6iSmokeWin32]::LongPath($profile), [StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "::error::Synthetic profile argument=[$profile] observed=[$observed]"
        throw 'Electron did not use its passed profile directory'
    }
    $themeMarker = Join-Path $profile 'synthetic-theme.txt'
    if (!(Wait-Until { if (Test-Path $themeMarker) { $true } } 10)) { throw 'Synthetic Electron did not create its theme marker' }
    $theme = [string](Get-Content $themeMarker -Raw)
    if ($ExpectHostTheme -and $theme -notin @('light', 'dark')) { throw 'Electron did not receive the host theme switch' }
    if (!$ExpectHostTheme -and $theme -ne 'system') { throw 'Old desktop unexpectedly passed a host theme switch' }
    $gpuMarker = Join-Path $profile 'synthetic-disable-gpu.txt'
    if (!(Wait-Until { if (Test-Path $gpuMarker) { $true } } 10)) { throw 'Synthetic Electron did not create its GPU flag marker' }
    $gpuFlag = [string](Get-Content $gpuMarker -Raw)
    if ($ExpectSoftwareFlag -and $gpuFlag -ne 'yes') { throw 'Electron did not receive --disable-gpu' }
    if (!$ExpectSoftwareFlag -and $gpuFlag -ne 'no') { throw 'Unexpected Electron GPU switch' }
    return $profile
}
$exe = (Resolve-Path (Join-Path $AppDir 'synthetic-test-desktop.exe')).Path
$fixture = (Resolve-Path $FixtureDir).Path
$data = Join-Path $env:RUNNER_TEMP 'sa6i-full-ui-synthetic-data'
New-Item -ItemType Directory -Path $data | Out-Null
$stderr = Join-Path $env:RUNNER_TEMP 'sa6i-full-ui-synthetic-stderr.txt'
$env:NECTARLINK_NO_ADB = '1'
# Exercise both the normal Qt renderer and the opt-in software workaround.
# The synthetic fixture is not the real cleaner and hosted Windows is not Win7.
if ($env:SA6I_SYNTHETIC_QT_BACKEND -eq 'default') {
    Remove-Item Env:QT_QUICK_BACKEND -ErrorAction SilentlyContinue
} else {
    $env:QT_QUICK_BACKEND = 'software'
}
$env:SA6I_CLEAN_WIN7_COMPAT = '1'
if ($ExpectSoftwareFlag) { $env:SA6I_CLEAN_WIN7_SOFTWARE = '1' }
else { Remove-Item Env:SA6I_CLEAN_WIN7_SOFTWARE -ErrorAction SilentlyContinue }
if ($Scale -lt 1 -or $Scale -gt 2) { throw 'Unsupported smoke-test scale' }
$env:QT_SCALE_FACTOR = $Scale.ToString([System.Globalization.CultureInfo]::InvariantCulture)
$app = $null
try {
    $app = Start-Process $exe -ArgumentList '--data-dir', "`"$data`"", "`"--sa6i-clean-test-dir=$fixture`"" -RedirectStandardError $stderr -PassThru
    $null = $app.Handle
    $window = Wait-Until { $app.Refresh(); if (!$app.HasExited -and $app.MainWindowHandle -ne [IntPtr]::Zero) { $app.MainWindowHandle } } 40
    if (!$window) { throw 'Main window did not appear' }
    if (([Sa6iSmokeWin32]::GetWindowLong($window, -20) -band 0x00200000) -ne 0) {
        throw 'Win7 compatibility mode still uses WS_EX_NOREDIRECTIONBITMAP'
    }
    Write-Host '::notice::PASS: Win7 mode avoids the no-redirection window style'
    # Let the main QML window finish its initial rendering and layout.
    Start-Sleep -Seconds 4
    $rect = New-Object Sa6iSmokeWin32+RECT
    if (![Sa6iSmokeWin32]::GetClientRect($window, [ref]$rect)) { throw 'Could not get client bounds' }
    $entryX = $rect.right - [int](216 * $Scale)
    if ($entryX -lt 0) { throw 'Window too narrow for cleaner button' }
    [Sa6iSmokeWin32]::Click($window, $entryX, [int](26 * $Scale))
    # Electron can have several same-name subprocesses; only use the one
    # directly launched by this app as the tracked browser process.
    $childProc = Wait-Until {
        $match = Get-CimInstance Win32_Process -Filter "Name='Sa6i Clean Integration.exe' AND ParentProcessId=$($app.Id)" | Select-Object -First 1
        if ($match) { Get-Process -Id $match.ProcessId -ErrorAction SilentlyContinue }
    } 35
    if (!$childProc) { throw 'The synthetic child did not start after clicking Sa6i Clean' }
    $child = Wait-Until { $h = [Sa6iSmokeWin32]::ChildForProcess($window, [uint32]$childProc.Id); if ($h -ne [IntPtr]::Zero -and [Sa6iSmokeWin32]::IsWindowVisible($h)) { $h } } 20
    if (!$child) { throw 'Synthetic child did not become a visible child of the app window' }
    # Exercise the same read-only geometry reporter intended for Windows 7.
    # Assert it sees the disposable host and nested child; no titles or paths.
    $layout = (& ./sa6i/clean/tests/check_window_layout.ps1 -ProcessName 'synthetic-test-desktop') -join "`n"
    if ($layout -notmatch 'HOST handle=' -or $layout -notmatch 'CHILD handle=' -or $layout -notmatch 'clientOrigin=') {
        throw 'Read-only layout reporter did not capture the synthetic host and child'
    }
    if ($IntegratedHeader) {
        # Clicks posted directly to the host can pass even when a native child
        # visually covers the button. Check real HWND bounds and hit testing.
        $clip = [Sa6iSmokeWin32]::GetParent($child)
        if ($ClippingContainer -and ($clip -eq $window -or [Sa6iSmokeWin32]::GetParent($clip) -ne $window)) {
            throw 'Expected a host-owned clipping container between Qt and the fixture'
        }
        $bounds = New-Object Sa6iSmokeWin32+RECT
        $origin = New-Object Sa6iSmokeWin32+POINT
        if (![Sa6iSmokeWin32]::ClientToScreen($window, [ref]$origin) -or
            ![Sa6iSmokeWin32]::GetWindowRect($clip, [ref]$bounds)) { throw 'Could not inspect header geometry' }
        if ($ClippingContainer -and [Math]::Abs($bounds.top - ($origin.y + [int](52 * $Scale))) -gt 2) {
            throw "Clipping viewport covers or is detached from header: top=$($bounds.top) origin=$($origin.y)"
        }
        $headerPoint = New-Object Sa6iSmokeWin32+POINT
        $headerPoint.x = [int](50 * $Scale); $headerPoint.y = [int](26 * $Scale)
        if ([Sa6iSmokeWin32]::ChildWindowFromPointEx($window, $headerPoint, 1) -ne $window) {
            throw 'A native child is covering the Back button area'
        }
        Write-Host '::notice::PASS: native viewport does not cover the Back header'
        if ($PixelCheck) {
            # Bounds and hit-testing alone don't prove GPU-rendered pixels are
            # clipped. The inert Electron page paints an unmistakable green.
            [void][Sa6iSmokeWin32]::SetForegroundWindow($window)
            $green = [uint32]0x007ad418 # GetPixel returns 0x00bbggrr.
            $bodyX = $origin.x + [int](40 * $Scale)
            $bodyY = $origin.y + [int](150 * $Scale)
            if (!(Wait-Until { if ([Sa6iSmokeWin32]::ScreenPixel($bodyX, $bodyY) -eq $green) { $true } } 12)) {
                throw 'Cannot observe the inert Electron green on screen; pixel clipping check is inconclusive'
            }
            $headerX = $origin.x + [int](400 * $Scale)
            $headerY = $origin.y + [int](26 * $Scale)
            if ([Sa6iSmokeWin32]::ScreenPixel($headerX, $headerY) -eq $green) {
                throw 'Electron pixels visually cover the host header'
            }
            Write-Host '::notice::PASS: synthetic Electron pixels do not cover the header'
        }
    }
    $firstProfile = $null
    if ($VerifyElectronProfile) {
        $firstProfile = Confirm-SyntheticProfile $childProc.Id
        Write-Host '::notice::PASS: synthetic Electron uses the explicit temporary profile'
    }
    Write-Host '::notice::PASS: actual Qt app opened a synthetic child in the same window'
    if ($PixelCheck) {
        # The reported overlap also occurs when the host is maximized. Normal
        # window bounds alone cannot cover the invisible maximized frame edges.
        [void][Sa6iSmokeWin32]::ShowWindow($window, 3) # SW_MAXIMIZE
        if (!(Wait-Until { if ([Sa6iSmokeWin32]::IsZoomed($window)) { $true } } 8)) { throw 'Host did not maximize' }
        Start-Sleep -Seconds 2
        $maxOrigin = New-Object Sa6iSmokeWin32+POINT
        $maxClip = New-Object Sa6iSmokeWin32+RECT
        if (![Sa6iSmokeWin32]::ClientToScreen($window, [ref]$maxOrigin) -or
            ![Sa6iSmokeWin32]::GetWindowRect([Sa6iSmokeWin32]::GetParent($child), [ref]$maxClip)) {
            throw 'Could not inspect maximized viewport'
        }
        if ([Math]::Abs($maxClip.top - ($maxOrigin.y + [int](52 * $Scale))) -gt 2) {
            throw 'Maximized native viewport is not below the header in client coordinates'
        }
        [void][Sa6iSmokeWin32]::SetForegroundWindow($window)
        $maxBodyX = [Math]::Max(0, $maxOrigin.x) + [int](40 * $Scale)
        $maxBodyY = [Math]::Max(0, $maxOrigin.y) + [int](150 * $Scale)
        if (!(Wait-Until { if ([Sa6iSmokeWin32]::ScreenPixel($maxBodyX, $maxBodyY) -eq $green) { $true } } 12)) {
            throw 'Maximized synthetic Electron pixels not visible; check is inconclusive'
        }
        $maxHeaderX = [Math]::Max(0, $maxOrigin.x) + [int](400 * $Scale)
        foreach ($headerY in @(26, 38, 48)) {
            $maxHeaderY = [Math]::Max(0, $maxOrigin.y) + [int]($headerY * $Scale)
            if ([Sa6iSmokeWin32]::ScreenPixel($maxHeaderX, $maxHeaderY) -eq $green) {
                throw "Maximized Electron pixels visually cover the visible header at y=$headerY"
            }
        }
        Write-Host '::notice::PASS: synthetic Electron header clipping when maximized'
        [void][Sa6iSmokeWin32]::ShowWindow($window, 9) # SW_RESTORE
        if (!(Wait-Until { if (![Sa6iSmokeWin32]::IsZoomed($window)) { $true } } 8)) { throw 'Host did not restore' }
        Start-Sleep -Seconds 1
    }
    $oldParent = New-Object Sa6iSmokeWin32+RECT
    $oldChild = New-Object Sa6iSmokeWin32+RECT
    if (![Sa6iSmokeWin32]::GetWindowRect($window, [ref]$oldParent) -or ![Sa6iSmokeWin32]::GetWindowRect($child, [ref]$oldChild)) { throw 'Could not read window geometry' }
    # Keep position and z-order; increase outer dimensions by 120x80 pixels.
    if (![Sa6iSmokeWin32]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, ($oldParent.right - $oldParent.left + 120), ($oldParent.bottom - $oldParent.top + 80), 0x16)) { throw 'Could not resize host window' }
    if (!(Wait-Until {
        $newChild = New-Object Sa6iSmokeWin32+RECT
        $newParent = New-Object Sa6iSmokeWin32+RECT
        if ([Sa6iSmokeWin32]::GetWindowRect($child, [ref]$newChild) -and [Sa6iSmokeWin32]::GetWindowRect($window, [ref]$newParent)) {
            $parentWidthChange = ($newParent.right - $newParent.left) - ($oldParent.right - $oldParent.left)
            $parentHeightChange = ($newParent.bottom - $newParent.top) - ($oldParent.bottom - $oldParent.top)
            $childWidthChange = ($newChild.right - $newChild.left) - ($oldChild.right - $oldChild.left)
            $childHeightChange = ($newChild.bottom - $newChild.top) - ($oldChild.bottom - $oldChild.top)
            # Qt may clamp the requested window size to the hosted screen.
            if ($parentWidthChange -gt 0 -and $parentHeightChange -gt 0 -and
                [Math]::Abs($parentWidthChange - $childWidthChange) -le 2 -and
                [Math]::Abs($parentHeightChange - $childHeightChange) -le 2) { $true }
        }
    } 8)) {
        $newParent = New-Object Sa6iSmokeWin32+RECT
        $newChild = New-Object Sa6iSmokeWin32+RECT
        [void][Sa6iSmokeWin32]::GetWindowRect($window, [ref]$newParent)
        [void][Sa6iSmokeWin32]::GetWindowRect($child, [ref]$newChild)
        Write-Host "::error::Resize oldParent=$($oldParent.right-$oldParent.left)x$($oldParent.bottom-$oldParent.top) newParent=$($newParent.right-$newParent.left)x$($newParent.bottom-$newParent.top) oldChild=$($oldChild.right-$oldChild.left)x$($oldChild.bottom-$oldChild.top) newChild=$($newChild.right-$newChild.left)x$($newChild.bottom-$newChild.top)"
        throw 'Child did not resize with the app'
    }
    if (![Sa6iSmokeWin32]::GetClientRect($window, [ref]$rect)) { throw 'Could not get resized client bounds' }
    $entryX = $rect.right - [int](216 * $Scale)
    Write-Host '::notice::PASS: child resized with the app'
    # The pinned historical desktop uses a separate toolbar. Newer builds
    # with the integrated title header must opt in until their artifact is pinned.
    $backY = if ($IntegratedHeader) { [int](26 * $Scale) } else { [int](80 * $Scale) }
    [Sa6iSmokeWin32]::Click($window, [int](50 * $Scale), $backY)
    if (!(Wait-Until { if (![Sa6iSmokeWin32]::IsWindowVisible($child)) { $true } } 8)) { throw 'Back did not hide the synthetic child' }
    [Sa6iSmokeWin32]::Click($window, $entryX, [int](26 * $Scale))
    if (!(Wait-Until { if ([Sa6iSmokeWin32]::IsWindowVisible($child)) { $true } } 8)) { throw 'Reopening did not show the same synthetic child' }
    Write-Host '::notice::PASS: Back and re-open hide and show the same child'
    # Default Windows close-to-tray should reap the synthetic cleaner before
    # unloading the window, and reactivation must allow a fresh clean launch.
    [void][Sa6iSmokeWin32]::PostMessage($window, 0x10, [IntPtr]::Zero, [IntPtr]::Zero)
    if (!$childProc.WaitForExit(15000)) { throw 'Synthetic child did not exit during close-to-tray' }
    if (!(Wait-Until { $app.Refresh(); if (!$app.HasExited -and ![Sa6iSmokeWin32]::IsWindowVisible($window)) { $true } } 12)) { throw 'Window did not close to tray' }
    $activate = Start-Process $exe -ArgumentList '--data-dir', "`"$data`"" -PassThru
    $null = $activate.Handle
    if (!$activate.WaitForExit(15000) -or $activate.ExitCode -ne 0) { throw 'Reactivation request failed' }
    $window = Wait-Until { $app.Refresh(); $h = $app.MainWindowHandle; if (!$app.HasExited -and $h -ne [IntPtr]::Zero -and [Sa6iSmokeWin32]::IsWindowVisible($h)) { $h } } 20
    if (!$window) { throw 'App window did not reopen after tray close' }
    Start-Sleep -Seconds 2
    if (![Sa6iSmokeWin32]::GetClientRect($window, [ref]$rect)) { throw 'Could not get reopened client bounds' }
    $entryX = $rect.right - [int](216 * $Scale)
    [Sa6iSmokeWin32]::Click($window, $entryX, [int](26 * $Scale))
    $childProc = Wait-Until {
        $match = Get-CimInstance Win32_Process -Filter "Name='Sa6i Clean Integration.exe' AND ParentProcessId=$($app.Id)" | Select-Object -First 1
        if ($match) { Get-Process -Id $match.ProcessId -ErrorAction SilentlyContinue }
    } 35
    if (!$childProc) { throw 'No synthetic child after tray reactivation' }
    $child = Wait-Until { $h = [Sa6iSmokeWin32]::ChildForProcess($window, [uint32]$childProc.Id); if ($h -ne [IntPtr]::Zero -and [Sa6iSmokeWin32]::IsWindowVisible($h)) { $h } } 20
    if (!$child) { throw 'Synthetic child did not attach after tray reactivation' }
    if ($VerifyElectronProfile) {
        $secondProfile = Confirm-SyntheticProfile $childProc.Id
        if ([string]::Equals($firstProfile, $secondProfile, [StringComparison]::OrdinalIgnoreCase)) { throw 'Electron profile was reused after relaunch' }
        Write-Host '::notice::PASS: synthetic Electron relaunch used a fresh profile'
    }
    Write-Host '::notice::PASS: tray close, reactivate and fresh child launch'
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
