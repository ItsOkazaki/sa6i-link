# Read-only diagnostic for the Sa6i Link Clean UI Preview on Windows 7+.
# No files are changed and nothing is uploaded.
param([string]$AppDir)
$ErrorActionPreference = 'Stop'

function Check-File([string]$Label, [string]$RelativePath, [string]$Expected) {
    $path = Join-Path $AppDir $RelativePath
    if (-not [System.IO.File]::Exists($path)) {
        Write-Host ($Label + ': NOT FOUND')
        return
    }
    try {
        $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        try {
            $sha = [System.Security.Cryptography.SHA256]::Create()
            try { $value = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
            finally { $sha.Clear() }
        } finally { $stream.Close() }
        if ($value -eq $Expected) { Write-Host ($Label + ': MATCH') }
        else {
            Write-Host ($Label + ': DIFFERENT')
            Write-Host ('  SHA256: ' + $value)
        }
    } catch {
        Write-Host ($Label + ': READ OR HASH ERROR')
        Write-Host ('  ' + $_.Exception.Message)
    }
}

Write-Host 'Sa6i Clean read-only verification'
Write-Host 'This does not change files or send information.'
Write-Host ''
if (-not (Test-Path -LiteralPath $AppDir -PathType Container)) {
    Write-Host 'The selected preview folder was not found.'
    exit 1
}
Check-File 'Updated desktop' 'nectarlink-desktop.exe' '9f6ed53b2b62bb07a930e4216222400668ba2fe862e95430950dfef8aee2d30b'
Check-File 'Cleaner executable' 'Sa6i Clean\Sa6i Clean Integration.exe' '435923fe5a7404feef6bdf242b444dda5def1a05d68a720038e41294086dbb4e'
Check-File 'Cleaner app.asar' 'Sa6i Clean\resources\app.asar' '62b7546a12ddac85b6fc506b0fb151acd15944ce3a809f9f4c8390965ef1080a'
Write-Host ''
try {
    # Probe the same Windows crypto provider and algorithm used by the host.
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class Sa6iCryptoCheck {
    [DllImport("advapi32.dll", EntryPoint="CryptAcquireContextW", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool Acquire(out IntPtr provider, string container, string name, uint type, uint flags);
    [DllImport("advapi32.dll", EntryPoint="CryptCreateHash", SetLastError=true)]
    static extern bool CreateHash(IntPtr provider, uint algorithm, IntPtr key, uint flags, out IntPtr hash);
    [DllImport("advapi32.dll", EntryPoint="CryptDestroyHash")]
    static extern bool DestroyHash(IntPtr hash);
    [DllImport("advapi32.dll", EntryPoint="CryptReleaseContext")]
    static extern bool Release(IntPtr provider, uint flags);
    public static string Probe() {
        IntPtr provider, hash;
        if (!Acquire(out provider, null, null, 24, 0xF0000000))
            return "CryptAcquireContext failed: " + Marshal.GetLastWin32Error();
        try {
            if (!CreateHash(provider, 0x0000800c, IntPtr.Zero, 0, out hash))
                return "CryptCreateHash failed: " + Marshal.GetLastWin32Error();
            DestroyHash(hash);
            return "OK";
        } finally { Release(provider, 0); }
    }
}
'@
    Write-Host ('Windows SHA-256 provider: ' + [Sa6iCryptoCheck]::Probe())
} catch {
    Write-Host ('Windows SHA-256 provider check failed: ' + $_.Exception.Message)
}
Write-Host ''
Write-Host 'Please share a photo of these results. No personal data is needed.'
