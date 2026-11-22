# Read-only Win32 geometry report. Never prints window titles or paths.
# Reads only the running application executables to identify their versions.
param([string]$ProcessName = 'sa6i-link',
      [string]$CleanerProcessName = 'Sa6i Clean Integration')
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class Sa6iLayoutCheck {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left, top, right, bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x, y; }
    public delegate bool EnumProc(IntPtr h, IntPtr unused);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr param);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr param);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT rect);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT rect);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT point);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder name, int count);
    [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] public static extern int GetDeviceCaps(IntPtr dc, int index);
    public static string Describe(IntPtr h) {
        RECT r, c; POINT origin = new POINT(); uint pid;
        if (!GetWindowRect(h, out r) || !GetClientRect(h, out c) || !ClientToScreen(h, ref origin)) return "Window geometry unavailable";
        GetWindowThreadProcessId(h, out pid);
        StringBuilder cls = new StringBuilder(256); GetClassName(h, cls, cls.Capacity);
        return "handle=" + h.ToInt64() + " parent=" + GetParent(h).ToInt64() + " pid=" + pid +
            " class=" + cls.ToString() + " visible=" + IsWindowVisible(h) +
            " window=(" + r.left + "," + r.top + "," + r.right + "," + r.bottom + ")" +
            " clientOrigin=(" + origin.x + "," + origin.y + ")" +
            " clientSize=(" + c.right + "," + c.bottom + ")";
    }
    public static int SystemDpi() {
        IntPtr dc = GetDC(IntPtr.Zero); if (dc == IntPtr.Zero) return 0;
        try { return GetDeviceCaps(dc, 90); } finally { ReleaseDC(IntPtr.Zero, dc); }
    }
    public static string Report(uint pid) {
        StringBuilder report = new StringBuilder();
        EnumProc top = delegate(IntPtr h, IntPtr unused) {
            uint actual; GetWindowThreadProcessId(h, out actual);
            if (actual != pid || !IsWindowVisible(h)) return true;
            report.AppendLine("HOST " + Describe(h));
            EnumProc child = delegate(IntPtr c, IntPtr ignored) { report.AppendLine("  CHILD " + Describe(c)); return true; };
            EnumChildWindows(h, child, IntPtr.Zero);
            return true;
        };
        EnumWindows(top, IntPtr.Zero);
        return report.ToString();
    }
}
'@
function Get-RunningHash($process) {
    try {
        # Read the loaded executable, not an arbitrary user-supplied file. Do
        # not print paths or exception messages if access is unavailable.
        $stream = [System.IO.File]::Open($process.MainModule.FileName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
            finally { $sha.Clear() }
        } finally { $stream.Close() }
    } catch { return 'UNAVAILABLE' }
}
Write-Host 'Sa6i read-only window layout report'
Write-Host 'No window titles, file paths or personal files are collected.'
Write-Host ('System DPI: ' + [Sa6iLayoutCheck]::SystemDpi())
$processes = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)
if ($processes.Count -eq 0) { Write-Host 'No Sa6i desktop process found.'; exit 1 }
foreach ($process in $processes) {
    Write-Host ('Desktop process ' + $process.Id + ' SHA256: ' + (Get-RunningHash $process))
    $report = [Sa6iLayoutCheck]::Report([uint32]$process.Id)
    if ($report) { Write-Output $report }
    else { Write-Host ('No visible top-level window for process ' + $process.Id) }
}
$cleaners = @(Get-Process -Name $CleanerProcessName -ErrorAction SilentlyContinue)
if ($cleaners.Count -eq 0) { Write-Host 'No cleaner process found. Open the cleaner dashboard first.' }
else {
    Write-Host ('Cleaner processes found: ' + $cleaners.Count)
    Write-Host ('Cleaner executable SHA256: ' + (Get-RunningHash $cleaners[0]))
    foreach ($process in $cleaners) {
        $report = [Sa6iLayoutCheck]::Report([uint32]$process.Id)
        if ($report) { Write-Output ('CLEANER TOP-LEVEL ' + $report) }
    }
}
Write-Host 'Please share a picture of this report.'
