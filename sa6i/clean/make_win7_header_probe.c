// SPDX-License-Identifier: GPL-3.0-or-later
// Creates a separate restricted probe executable; NEVER patches the source.
// It changes only four PE header bytes in a byte-exact known input, not APIs.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>
unsigned long _tls_index; // Required by the Zig freestanding Windows linker.
static BYTE buffer[65536];
static wchar_t folder[32768], srcpath[32768], dstpath[32768];
static const BYTE source_hash[32] = {
    0xca,0x53,0x9c,0x30,0x6d,0x32,0x92,0x1f,0x9c,0xaa,0x9b,0x55,0xe2,0xfd,0x8e,0xe7,
    0x7e,0x0b,0x44,0xfb,0xf3,0xcf,0xd8,0x1c,0x70,0x66,0x3a,0x20,0x5e,0x99,0x30,0x49
};
static const BYTE output_hash[32] = {
    0x88,0x39,0x33,0x44,0x9d,0x34,0x3d,0xec,0x59,0x25,0xe9,0x06,0x8c,0x7e,0x81,0x05,
    0x26,0x78,0xa1,0x86,0xaf,0x71,0x8f,0xf6,0xa0,0x7c,0x15,0xd6,0xbb,0xb3,0x8a,0xbe
};
static BOOL seek(HANDLE f, LONGLONG offset) {
    LARGE_INTEGER p; p.QuadPart = offset;
    return SetFilePointerEx(f, p, NULL, FILE_BEGIN);
}
static BOOL verify(HANDLE f, const BYTE expected[32]) {
    HCRYPTPROV provider = 0; HCRYPTHASH hash = 0;
    BYTE digest[32]; DWORD n, len = 32; BOOL ok = FALSE;
    if (!seek(f, 0)) goto done;
    if (!CryptAcquireContextW(&provider, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) goto done;
    if (!CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash)) goto done;
    for (;;) {
        if (!ReadFile(f, buffer, sizeof(buffer), &n, NULL)) goto done;
        if (!n) break;
        if (!CryptHashData(hash, buffer, n, 0)) goto done;
    }
    if (!CryptGetHashParam(hash, HP_HASHVAL, digest, &len, 0) || len != 32) goto done;
    ok = TRUE;
    for (unsigned int i = 0; i < 32; ++i) if (digest[i] != expected[i]) { ok = FALSE; break; }
 done:
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    return ok;
}
static BOOL patch(HANDLE f, LONGLONG offset) {
    BYTE old[4], replacement[4] = {6, 0, 1, 0}; DWORD n;
    if (!seek(f, offset) || !ReadFile(f, old, 4, &n, NULL) || n != 4) return FALSE;
    if (old[0] != 10 || old[1] != 0 || old[2] != 0 || old[3] != 0) return FALSE;
    return seek(f, offset) && WriteFile(f, replacement, 4, &n, NULL) && n == 4;
}
void WINAPI main_entry(void) {
    HANDLE src = INVALID_HANDLE_VALUE, dst = INVALID_HANDLE_VALUE;
    const wchar_t *msg = L"Could not create probe. No existing files were replaced.";
    BOOL created = FALSE, ok = FALSE; DWORD size = GetModuleFileNameW(NULL, folder, 32768), n, written;
    wchar_t *slash = NULL;
    if (!size || size >= 32768) goto done;
    for (DWORD i = 0; i < size; ++i) if (folder[i] == L'\\') slash = &folder[i];
    if (!slash) goto done;
    *slash = 0;
    if (lstrlenW(folder) + 40 >= 32768) goto done;
    lstrcpyW(srcpath, folder); lstrcatW(srcpath, L"\\Sa6i Clean.exe");
    lstrcpyW(dstpath, folder); lstrcatW(dstpath, L"\\Sa6i Clean Win7 Probe.exe");
    src = CreateFileW(srcpath, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (src == INVALID_HANDLE_VALUE || !verify(src, source_hash)) {
        msg = L"The restricted Sa6i Clean.exe was not found or did not match. No file was changed.";
        goto done;
    }
    dst = CreateFileW(dstpath, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (dst == INVALID_HANDLE_VALUE) {
        msg = L"Could not create Sa6i Clean Win7 Probe.exe. If it already exists, this tool will not overwrite it. No existing files were changed.";
        goto done;
    }
    created = TRUE;
    if (!seek(src, 0)) goto done;
    for (;;) {
        if (!ReadFile(src, buffer, sizeof(buffer), &n, NULL)) goto done;
        if (!n) break;
        if (!WriteFile(dst, buffer, n, &written, NULL) || written != n) goto done;
    }
    if (!patch(dst, 184) || !patch(dst, 192) || !FlushFileBuffers(dst) || !verify(dst, output_hash)) goto done;
    ok = TRUE;
    msg = L"Created and verified Sa6i Clean Win7 Probe.exe.\n\nEnable VxKex for this NEW file, then run Sa6i Win7 Host Probe.exe. This is not a release.";
 done:
    if (dst != INVALID_HANDLE_VALUE) CloseHandle(dst);
    if (src != INVALID_HANDLE_VALUE) CloseHandle(src);
    if (!ok && created) msg = L"Probe creation failed. A partial Sa6i Clean Win7 Probe.exe may remain in the test folder; delete that partial file manually before retrying. The source was not changed.";
    MessageBoxW(NULL, msg, L"Sa6i Clean Win7 header experiment", MB_OK | (ok ? MB_ICONINFORMATION : MB_ICONERROR));
    ExitProcess(ok ? 0 : 1);
}
